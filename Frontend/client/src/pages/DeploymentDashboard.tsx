import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Activity,
  AlertTriangle,
  BarChart2,
  CheckCircle2,
  ChevronRight,
  CircleDollarSign,
  Database,
  Layers,
  PackageCheck,
  RotateCcw,
  Square,
  TrendingDown,
  TrendingUp,
  Zap,
  Info,
} from "lucide-react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import {
  startMultiSkuDeployment,
  getMultiSkuState,
  stepAllSkus,
  stepSingleSku,
  setMultiSkuOverride,
  resetMultiSkuDeployment,
  getSkuHistory,
} from "@/lib/api";
import type { MultiSkuState, SkuSummary, LedgerRow } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { PageCopilot } from "@/components/PageCopilot";

// ──────────────────────────────────────────────────────────────
// helpers
// ──────────────────────────────────────────────────────────────
function fmt(n: number, decimals = 0) {
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(decimals) + "K";
  return n.toFixed(decimals);
}

function healthColor(h: SkuSummary["health"]) {
  return h === "stockout"
    ? "text-red-500"
    : h === "low"
    ? "text-amber-400"
    : "text-emerald-400";
}
function healthDot(h: SkuSummary["health"]) {
  return h === "stockout" ? "🔴" : h === "low" ? "🟡" : "🟢";
}

// ──────────────────────────────────────────────────────────────
// component
// ──────────────────────────────────────────────────────────────
export default function DeploymentDashboard() {
  const { toast } = useToast();
  const [, navigate] = useLocation();
  const ledgerRef = useRef<HTMLDivElement>(null);

  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(false);
  const [state, setState] = useState<MultiSkuState | null>(null);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [overrideValues, setOverrideValues] = useState<Record<string, string>>({});
  const [isStepping, setIsStepping] = useState(false);
  const [isAutoRunning, setIsAutoRunning] = useState(false);
  const autoRunRef = useRef(false);
  const [ledgerHistory, setLedgerHistory] = useState<Record<string, LedgerRow[]>>({});

  // ── per-SKU inventory history for sparklines
  const [inventoryHistory, setInventoryHistory] = useState<Record<string, number[]>>({});

  // ── On mount: try to resume existing session, else show "start" screen
  useEffect(() => {
    async function init() {
      try {
        const s = await getMultiSkuState();
        applyState(s);
      } catch {
        // no session yet — show start screen
      } finally {
        setLoading(false);
      }
    }
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Auto-scroll ledger when history grows
  useEffect(() => {
    if (ledgerRef.current) {
      ledgerRef.current.scrollTop = ledgerRef.current.scrollHeight;
    }
  }, [state]);

  const applyState = useCallback((s: MultiSkuState) => {
    setState(s);
    // Default selected SKU
    setSelectedSku((prev) => prev ?? Object.keys(s.skus)[0] ?? null);
    // Pre-fill override inputs with RL's recommendation
    setOverrideValues((prev) => {
      const next = { ...prev };
      for (const [sku, info] of Object.entries(s.skus)) {
        if (!(sku in next) && info.next_rl_action !== null) {
          next[sku] = String(info.next_rl_action);
        } else if (info.next_rl_action !== null && prev[sku] === undefined) {
          next[sku] = String(info.next_rl_action);
        }
      }
      return next;
    });
  }, []);

  // Fetch ledger history for the selected SKU
  const fetchLedger = useCallback(async (sku: string) => {
    try {
      const result = await getSkuHistory(sku);
      setLedgerHistory((prev) => ({ ...prev, [sku]: result.history }));
    } catch {
      // ignore — no history yet if day 0
    }
  }, []);

  // Re-fetch ledger whenever selected SKU changes
  useEffect(() => {
    if (selectedSku) fetchLedger(selectedSku);
  }, [selectedSku, fetchLedger]);

  // ── Start deployment
  const handleStart = async () => {
    setInitializing(true);
    try {
      const s = await startMultiSkuDeployment();
      applyState(s);
      toast({
        title: "Deployment Online",
        description: `${s.aggregate.sku_count} SKU agents deployed. Day ${s.aggregate.global_day} / ${s.aggregate.total_days}`,
      });
    } catch (err: any) {
      toast({ title: "Start Failed", description: friendlyError(err, "deployment"), variant: "destructive" });
    } finally {
      setInitializing(false);
    }
  };

  // ── Step ALL SKUs +1 day
  const handleStepAll = async () => {
    if (!state || state.is_all_complete) return;
    setIsStepping(true);
    try {
      const s = await stepAllSkus();
      // Track inventory history per SKU
      setInventoryHistory((prev) => {
        const next = { ...prev };
        for (const [sku, info] of Object.entries(s.skus)) {
          next[sku] = [...(prev[sku] ?? []), info.current_inventory];
        }
        return next;
      });
      applyState(s);
      // Refresh ledger for selected SKU
      if (selectedSku) await fetchLedger(selectedSku);
    } catch (err: any) {
      toast({ title: "Step Failed", description: friendlyError(err, "deployment"), variant: "destructive" });
    } finally {
      setIsStepping(false);
    }
  };

  // ── Step a single SKU +1 day, applying override if set
  const handleStepSku = async (sku: string) => {
    if (!state) return;
    const info = state.skus[sku];
    if (!info || info.is_complete) return;
    setIsStepping(true);
    try {
      const overrideStr = overrideValues[sku];
      const overrideQty = overrideStr !== undefined ? parseInt(overrideStr, 10) : NaN;
      if (!isNaN(overrideQty) && overrideQty !== info.next_rl_action) {
        await setMultiSkuOverride(sku, info.current_day, overrideQty);
      }
      const s = await stepSingleSku(sku);
      setInventoryHistory((prev) => ({
        ...prev,
        [sku]: [...(prev[sku] ?? []), s.skus[sku]?.current_inventory ?? 0],
      }));
      // Refresh ledger
      await fetchLedger(sku);
      // Reset override to new RL suggestion
      if (s.skus[sku]?.next_rl_action !== null) {
        setOverrideValues((prev) => ({ ...prev, [sku]: String(s.skus[sku].next_rl_action) }));
      }
      applyState(s);
    } catch (err: any) {
      toast({ title: "Step Failed", description: friendlyError(err, "deployment"), variant: "destructive" });
    } finally {
      setIsStepping(false);
    }
  };

  // ── Auto-run all: step all until complete
  const handleAutoRunAll = async () => {
    if (!state) return;
    setIsAutoRunning(true);
    autoRunRef.current = true;
    try {
      let current = state;
      while (!current.is_all_complete && autoRunRef.current) {
        const s = await stepAllSkus();
        setInventoryHistory((prev) => {
          const next = { ...prev };
          for (const [sku, info] of Object.entries(s.skus)) {
            next[sku] = [...(prev[sku] ?? []), info.current_inventory];
          }
          return next;
        });
        applyState(s);
        current = s;
        // Small yield to allow React to re-render
        await new Promise((r) => setTimeout(r, 30));
      }
      // Refresh ledger at end
      if (selectedSku) await fetchLedger(selectedSku);
      toast({ title: "Auto-run complete", description: "All SKUs have finished their simulation." });
    } catch (err: any) {
      toast({ title: "Auto-Run Failed", description: friendlyError(err, "deployment"), variant: "destructive" });
    } finally {
      setIsAutoRunning(false);
      autoRunRef.current = false;
    }
  };

  const handleStopAutoRun = () => {
    autoRunRef.current = false;
  };

  // ── Reset all
  const handleResetAll = async () => {
    if (!state) return;
    try {
      const s = await resetMultiSkuDeployment();
      setInventoryHistory({});
      setOverrideValues({});
      setLedgerHistory({});
      applyState(s);
      toast({ title: "Simulation Reset", description: "All SKUs reset to Day 0." });
    } catch (err: any) {
      toast({ title: "Reset Failed", description: friendlyError(err, "deployment"), variant: "destructive" });
    }
  };

  // ─────────────────────────────────────────────────────────────
  // RENDER
  // ─────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="flex items-center gap-3 text-muted-foreground">
          <Activity className="w-5 h-5 animate-pulse text-primary" />
          <span className="font-mono text-sm">Loading deployment session...</span>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="min-h-screen bg-background flex">
      <Sidebar />
      <main className="flex-1 lg:ml-[320px] flex flex-col h-screen overflow-hidden">
        <Header title={
          <div className="flex items-center gap-2">
            Live Deployment
            <TooltipProvider delayDuration={100}>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Button variant="ghost" size="icon" className="h-[22px] w-[22px] rounded-full hover:bg-muted text-muted-foreground transition-colors cursor-help">
                    <Info className="w-3.5 h-3.5" />
                  </Button>
                </TooltipTrigger>
                <TooltipContent align="start" sideOffset={8} className="w-[320px] p-3 text-xs bg-card border border-border/50 shadow-2xl glass font-sans">
                  <p className="font-bold mb-2 uppercase tracking-widest text-[10px] text-primary">Terminology Guide</p>
                  <div className="space-y-2 text-muted-foreground text-[11px] leading-relaxed">
                    <p><strong className="text-foreground">Step All SKUs:</strong> Advances every agent simulation strictly by 1 day.</p>
                    <p><strong className="text-foreground">Auto-Run All:</strong> Continuously streams all SKUs until reaching their final day.</p>
                    <div className="mt-3 pt-3 border-t border-border/50">
                      <p className="mb-2 uppercase tracking-widest text-[10px] text-primary font-bold">Ledger Metrics</p>
                      <div className="grid grid-cols-[40px_1fr] gap-x-2 gap-y-1.5">
                        <span className="text-foreground font-bold">Inv</span><span>Current quantity of stock on hand at day's start.</span>
                        <span className="text-foreground font-bold">Inv $</span><span>Calculated monetary value of the held inventory.</span>
                        <span className="text-foreground font-bold text-blue-400">RL</span><span>Restock order quantity determined by the trained AI.</span>
                        <span className="text-foreground font-bold text-amber-500">Ovr</span><span>Manual override quantity bypassing the AI decision.</span>
                        <span className="text-foreground font-bold text-primary">Act</span><span>Final executed order action entered into simulation.</span>
                      </div>
                    </div>
                  </div>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        } />

        {/* Stage nav + global controls */}
        <div className="px-6 pt-0 pb-1 shrink-0 flex flex-col gap-2">
          <div className="w-full">
            <StageNav />
          </div>
          {state && (
            <div className="flex items-center justify-end gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={handleResetAll}
                disabled={isStepping || isAutoRunning}
                className="gap-1.5 rounded-none border-border/50 text-xs"
              >
                <RotateCcw className="w-3 h-3" /> Reset All
              </Button>
              {isAutoRunning ? (
                <Button
                  size="sm"
                  onClick={handleStopAutoRun}
                  className="gap-1.5 rounded-none bg-red-600 hover:bg-red-700 text-xs"
                >
                  <Square className="w-3 h-3 fill-current" /> Stop
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={handleAutoRunAll}
                  disabled={isStepping || !state || state.is_all_complete}
                  className="gap-1.5 rounded-none bg-amber-500 hover:bg-amber-600 text-black text-xs font-bold"
                >
                  <Zap className="w-3 h-3" /> Auto-Run All
                </Button>
              )}
              <Button
                size="sm"
                onClick={handleStepAll}
                disabled={isStepping || isAutoRunning || !state || state.is_all_complete}
                className="gap-1.5 rounded-none bg-primary text-primary-foreground text-xs font-bold px-4"
              >
                {isStepping ? (
                  <Activity className="w-3 h-3 animate-pulse" />
                ) : (
                  <ChevronRight className="w-3 h-3" />
                )}
                Step All SKUs
              </Button>
            </div>
          )}
        </div>

        {/* ═══ NO SESSION — START SCREEN ═══ */}
        {!state && (
          <div className="flex-1 flex flex-col items-center justify-center gap-6 p-12 text-center">
            <div className="p-5 rounded-full bg-primary/10">
              <Database className="w-12 h-12 text-primary opacity-60" />
            </div>
            <div>
              <h2 className="text-2xl font-bold mb-2">Deployment Engine Offline</h2>
              <p className="text-muted-foreground max-w-md">
                Initialize the live production simulation. All trained SKU agents will be loaded and
                ready for day-by-day supervision.
              </p>
            </div>
            <Button
              onClick={handleStart}
              disabled={initializing}
              size="lg"
              className="gap-2 px-10 font-bold"
            >
              {initializing ? <Activity className="w-4 h-4 animate-pulse" /> : <Zap className="w-4 h-4" />}
              {initializing ? "Initializing..." : "Start Deployment"}
            </Button>
          </div>
        )}

        {/* ═══ ACTIVE SESSION ═══ */}
        {state && (
          <div className="flex-1 overflow-hidden flex flex-col">
            {/* ── TOP: AGGREGATE KPI BAR ── */}
            <div className="grid grid-cols-7 shrink-0 mx-6 mt-1 rounded-3xl overflow-hidden glass shadow-2xl pb-1">
              <KpiBlock
                label="Global Day"
                value={`${state.aggregate.global_day} / ${state.aggregate.total_days}`}
                icon={<BarChart2 className="w-3.5 h-3.5" />}
              />
              <KpiBlock
                label="Total Revenue"
                value={`$${fmt(state.aggregate.total_revenue, 1)}`}
                color="text-emerald-400"
                icon={<CircleDollarSign className="w-3.5 h-3.5" />}
              />
              <KpiBlock
                label="Total Cost"
                value={`-$${fmt(state.aggregate.total_cost, 1)}`}
                color="text-red-400"
                icon={<TrendingDown className="w-3.5 h-3.5" />}
              />
              <KpiBlock
                label="Net Profit"
                value={`$${fmt(state.aggregate.net_profit, 1)}`}
                color={state.aggregate.net_profit >= 0 ? "text-emerald-400" : "text-red-400"}
                icon={<TrendingUp className="w-3.5 h-3.5" />}
              />
              <KpiBlock
                label="Stockout Days"
                value={String(state.aggregate.total_stockout_days)}
                color={state.aggregate.total_stockout_days > 0 ? "text-amber-400" : "text-muted-foreground"}
                icon={<AlertTriangle className="w-3.5 h-3.5" />}
              />
              <KpiBlock
                label="Avg Inventory"
                value={`${fmt(state.aggregate.avg_inventory)} u`}
                icon={<Layers className="w-3.5 h-3.5" />}
              />
              <KpiBlock
                label="Inventory Value"
                value={`$${fmt(state.aggregate.total_inventory_value, 1)}`}
                color="text-blue-400"
                icon={<PackageCheck className="w-3.5 h-3.5" />}
              />
            </div>

            {/* ── MAIN: LEFT + RIGHT ── */}
            <div className="flex-1 grid grid-cols-12 overflow-hidden mx-6 mt-3 mb-3 rounded-3xl glass shadow-2xl border-white/5">

              {/* ═══ LEFT: SKU LIST PANEL ═══ */}
              <div className="col-span-4 border-r border-border/50 flex flex-col overflow-hidden bg-card/20">
                <div className="px-4 py-2.5 border-b border-border/50 bg-muted/20 text-[10px] uppercase tracking-widest text-muted-foreground font-bold">
                  SKU Agents ({state.aggregate.sku_count})
                </div>
                <div className="flex-1 overflow-y-auto p-3 space-y-2">
                  {Object.entries(state.skus)
                    .sort(([a], [b]) => a.localeCompare(b))
                    .map(([sku, info]) => (
                      <SkuCard
                        key={sku}
                        info={info}
                        selected={selectedSku === sku}
                        onClick={() => setSelectedSku(sku)}
                      />
                    ))}
                </div>

                {/* Step All button (duplicate in left panel for quick access) */}
                <div className="p-3 border-t border-border/50 space-y-2">
                  {state.is_all_complete ? (
                    <div className="flex items-center gap-2 text-emerald-400 text-xs font-mono px-1">
                      <CheckCircle2 className="w-4 h-4" />
                      All simulations complete
                    </div>
                  ) : (
                    <Button
                      onClick={handleStepAll}
                      disabled={isStepping || isAutoRunning}
                      className="w-full rounded-none font-bold gap-2 bg-primary/90 text-xs"
                    >
                      {isStepping ? <Activity className="w-3 h-3 animate-pulse" /> : <ChevronRight className="w-3 h-3" />}
                      STEP ALL SKUS ▶▶
                    </Button>
                  )}
                </div>
              </div>

              {/* ═══ RIGHT: SELECTED SKU DETAIL ═══ */}
              <div className="col-span-8 flex flex-col overflow-hidden">
                {selectedSku && state.skus[selectedSku] ? (
                  <SkuDetailPanel
                    sku={selectedSku}
                    info={state.skus[selectedSku]}
                    overrideValue={overrideValues[selectedSku] ?? ""}
                    onOverrideChange={(v) =>
                      setOverrideValues((p) => ({ ...p, [selectedSku]: v }))
                    }
                    onCommit={() => handleStepSku(selectedSku)}
                    isStepping={isStepping || isAutoRunning}
                    inventoryHistory={inventoryHistory[selectedSku] ?? []}
                    ledgerRows={ledgerHistory[selectedSku] ?? []}
                    ledgerRef={ledgerRef}
                  />
                ) : (
                  <div className="flex-1 flex items-center justify-center text-muted-foreground text-sm">
                    Select a SKU from the left panel
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
    <PageCopilot
      page="deploy"
      title="Deployment Copilot"
      subtitle={state ? (state.is_all_complete ? "● Simulation complete" : isStepping ? "● Stepping..." : "● Live") : "○ Offline"}
      quickActions={[
        "Step all SKUs one day",
        "Auto-run entire simulation",
        "Which SKU has the best profit?",
        "Explain the ledger metrics",
      ]}
      pageContext={{
        session_active: state !== null,
        global_day: state?.aggregate.global_day ?? null,
        total_days: state?.aggregate.total_days ?? null,
        all_complete: state?.is_all_complete ?? false,
        selected_sku: selectedSku,
        aggregate: state?.aggregate ? {
          sku_count: state.aggregate.sku_count,
          net_profit: state.aggregate.net_profit,
          total_revenue: state.aggregate.total_revenue,
          total_cost: state.aggregate.total_cost,
          total_stockout_days: state.aggregate.total_stockout_days,
        } : null,
        selected_sku_info: selectedSku && state?.skus[selectedSku] ? {
          health: state.skus[selectedSku].health,
          current_inventory: state.skus[selectedSku].current_inventory,
          net_profit: state.skus[selectedSku].net_profit,
          next_rl_action: state.skus[selectedSku].next_rl_action,
          is_complete: state.skus[selectedSku].is_complete,
        } : null,
        is_stepping: isStepping,
        is_auto_running: isAutoRunning,
      }}
      onAction={async (action) => {
        const a = action as Record<string, unknown>;
        if (a.action === "start_deployment" && !state) {
          await handleStart();
        } else if (a.action === "step_all" && state) {
          await handleStepAll();
        } else if (a.action === "auto_run" && state) {
          await handleAutoRunAll();
        } else if (a.action === "stop_auto_run") {
          handleStopAutoRun();
        } else if (a.action === "reset" && state) {
          await handleResetAll();
        }
      }}
    />
  </>
  );
}

// ──────────────────────────────────────────────────────────────
// Sub-components
// ──────────────────────────────────────────────────────────────

function KpiBlock({
  label,
  value,
  color = "text-foreground",
  icon,
}: {
  label: string;
  value: string;
  color?: string;
  icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col justify-center px-4 py-3 border-r border-border/10 last:border-r-0 bg-background/20 transition-colors hover:bg-background/40">
      <div className="flex items-center gap-1 text-[9px] uppercase tracking-widest text-muted-foreground mb-1 font-bold">
        {icon}
        {label}
      </div>
      <p className={`text-lg font-bold font-mono truncate ${color}`}>{value}</p>
    </div>
  );
}

function SkuCard({
  info,
  selected,
  onClick,
}: {
  info: SkuSummary;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded-lg border transition-all ${
        selected
          ? "border-primary/50 bg-primary/5 ring-1 ring-primary/20"
          : "border-border/40 bg-card/30 hover:bg-muted/30"
      }`}
    >
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm">{healthDot(info.health)}</span>
          <span className="text-sm font-bold truncate max-w-[140px]">{info.sku}</span>
        </div>
        <span className="text-[10px] text-muted-foreground font-mono">
          Day {info.current_day}/{info.total_days}
        </span>
      </div>
      <div className="grid grid-cols-3 gap-1 text-[10px]">
        <div>
          <p className="text-muted-foreground">Inventory</p>
          <p className={`font-bold font-mono ${healthColor(info.health)}`}>
            {info.current_inventory.toLocaleString()} u
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">Inv. Value</p>
          <p className="font-bold font-mono text-blue-400">
            ${fmt(info.current_inventory_value, 1)}
          </p>
        </div>
        <div>
          <p className="text-muted-foreground">Profit</p>
          <p className={`font-bold font-mono ${info.net_profit >= 0 ? "text-emerald-400" : "text-red-400"}`}>
            ${fmt(info.net_profit, 1)}
          </p>
        </div>
      </div>
      {info.health === "stockout" && (
        <div className="mt-1.5 flex items-center gap-1 text-red-500 text-[10px] font-bold animate-pulse">
          <AlertTriangle className="w-3 h-3" /> STOCKOUT
        </div>
      )}
    </button>
  );
}

function SkuDetailPanel({
  sku,
  info,
  overrideValue,
  onOverrideChange,
  onCommit,
  isStepping,
  inventoryHistory,
  ledgerRows,
  ledgerRef,
}: {
  sku: string;
  info: SkuSummary;
  overrideValue: string;
  onOverrideChange: (v: string) => void;
  onCommit: () => void;
  isStepping: boolean;
  inventoryHistory: number[];
  ledgerRows: LedgerRow[];
  ledgerRef: React.RefObject<HTMLDivElement>;
}) {
  const sparkData = inventoryHistory.slice(-60).map((v, i) => ({ i, value: v }));
  const isOverride =
    overrideValue !== "" && parseInt(overrideValue, 10) !== info.next_rl_action;

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-5 py-3 border-b border-border/50 bg-muted/10 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2.5">
          <span className="text-lg">{healthDot(info.health)}</span>
          <span className="font-bold text-base">{sku}</span>
          <span className="text-xs text-muted-foreground font-mono">
            Day {info.current_day} / {info.total_days}
          </span>
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground font-mono">
          <span>Stockouts: <strong className="text-foreground">{info.stockout_days}</strong></span>
          <span>Avg Inv: <strong className="text-foreground">{info.avg_inventory} u</strong></span>
        </div>
      </div>

      <div className="flex-1 overflow-hidden flex">
        {/* ── ORDER CONTROL PANEL ── */}
        <div className="w-[280px] shrink-0 border-r border-border/50 flex flex-col gap-0 overflow-y-auto">
          {/* KPIs */}
          <div className="grid grid-cols-2 gap-px bg-border/30">
            <StatCell label="Current Inventory" value={`${info.current_inventory.toLocaleString()} u`} color={healthColor(info.health)} />
            <StatCell label="Inventory Value" value={`$${fmt(info.current_inventory_value, 1)}`} color="text-blue-400" />
            <StatCell label="Revenue" value={`$${fmt(info.cumulative_revenue, 1)}`} color="text-emerald-400" />
            <StatCell label="Cost" value={`-$${fmt(info.cumulative_cost, 1)}`} color="text-red-400" />
            <StatCell label="Net Profit" value={`$${fmt(info.net_profit, 1)}`} color={info.net_profit >= 0 ? "text-emerald-400" : "text-red-400"} />
            <StatCell label="Last Reward" value={info.last_reward.toFixed(0)} color={info.last_reward >= 0 ? "text-emerald-400" : "text-red-400"} />
          </div>

          {/* Next day info + override */}
          {!info.is_complete ? (
            <div className="p-4 space-y-4">
              <div className="space-y-2 text-xs">
                <InfoRow label="Date" value={info.next_date ?? "—"} />
                <InfoRow label="Simulated Demand" value={`${info.next_demand ?? "—"} units`} />
                <InfoRow
                  label="RL Recommended Order"
                  value={`${info.next_rl_action ?? 0} units`}
                  valueClass="text-blue-400 font-bold"
                />
              </div>

              <div className="space-y-1.5">
                <label className="text-[10px] uppercase tracking-widest text-primary font-bold block">
                  Your Order (override)
                </label>
                <Input
                  type="number"
                  min={0}
                  value={overrideValue}
                  onChange={(e) => onOverrideChange(e.target.value)}
                  className={`h-12 text-xl font-bold font-mono bg-background border-2 rounded-none focus-visible:ring-0
                    ${isOverride ? "border-amber-500/60" : "border-border/50 focus-visible:border-primary"}`}
                />
                {isOverride && (
                  <p className="text-[10px] text-amber-400">
                    ⚠ Override active — RL suggests {info.next_rl_action}
                  </p>
                )}
              </div>

              <Button
                onClick={onCommit}
                disabled={isStepping}
                className="w-full h-11 rounded-none font-bold tracking-wide gap-2"
              >
                {isStepping ? (
                  <Activity className="w-4 h-4 animate-pulse" />
                ) : (
                  <ChevronRight className="w-4 h-4" />
                )}
                Commit & Step
              </Button>
            </div>
          ) : (
            <div className="p-6 text-center text-muted-foreground text-sm space-y-2">
              <CheckCircle2 className="w-10 h-10 mx-auto text-emerald-400 mb-2" />
              <p className="font-bold">Simulation Complete</p>
              <p className="text-xs">This SKU has finished all {info.total_days} days.</p>
            </div>
          )}
        </div>

        {/* ── SPARKLINE + LEDGER ── */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Sparkline */}
          {sparkData.length > 1 && (
            <div className="h-[100px] border-b border-border/50 px-4 py-2 shrink-0">
              <p className="text-[9px] uppercase tracking-widest text-muted-foreground mb-1 font-bold">
                Inventory History (last {sparkData.length} days)
              </p>
              <ResponsiveContainer width="100%" height={68}>
                <LineChart data={sparkData} margin={{ top: 2, right: 4, left: -30, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.08} />
                  <XAxis dataKey="i" hide />
                  <YAxis tick={{ fontSize: 9 }} />
                  <RechartsTooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      fontSize: 11,
                      borderRadius: 4,
                    }}
                    formatter={(v: number) => [`${v.toLocaleString()} units`, "Inventory"]}
                    labelFormatter={(i: number) => `Day ${i + 1}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="hsl(var(--primary))"
                    dot={false}
                    strokeWidth={1.5}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Ledger */}
          <div
            ref={ledgerRef}
            className="flex-1 overflow-y-auto"
          >
            <table className="w-full text-left border-collapse">
              <thead className="sticky top-0 bg-card border-b border-border text-[9px] uppercase text-muted-foreground z-10">
                <tr>
                  <th className="p-2.5 font-normal border-r border-border/40 w-10">Day</th>
                  <th className="p-2.5 font-normal">Demand</th>
                  <th className="p-2.5 font-normal">Inv</th>
                  <th className="p-2.5 font-normal">Inv $</th>
                  <th className="p-2.5 font-normal text-blue-400/70">RL</th>
                  <th className="p-2.5 font-normal text-amber-400/70">Ovr</th>
                  <th className="p-2.5 font-normal font-bold border-r border-border/40">Act</th>
                  <th className="p-2.5 font-normal text-right">Reward</th>
                </tr>
              </thead>
              <tbody className="text-xs font-mono">
                {ledgerRows.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="p-4 text-center text-muted-foreground/50 italic text-xs">
                      {info.current_day === 0
                        ? "Click 'Commit & Step' to start stepping through this SKU's simulation."
                        : "Loading history..."}
                    </td>
                  </tr>
                ) : (
                  ledgerRows.map((h) => {
                    const isOverrideRow = h.human_action !== null && h.human_action !== h.rl_action;
                    return (
                      <tr key={h.day} className="border-b border-border/30 hover:bg-muted/20 transition-colors">
                        <td className="p-2.5 border-r border-border/30 text-muted-foreground">{(h.day + 1).toString().padStart(3, "0")}</td>
                        <td className="p-2.5">{h.demand.toLocaleString()}</td>
                        <td className="p-2.5">{h.inventory.toLocaleString()}</td>
                        <td className="p-2.5 text-blue-400">${fmt(h.inventory_value, 0)}</td>
                        <td className="p-2.5 text-blue-400/70">{h.rl_action}</td>
                        <td className="p-2.5 text-amber-400">{h.human_action !== null ? h.human_action : "—"}</td>
                        <td className={`p-2.5 font-bold border-r border-border/30 ${isOverrideRow ? "text-amber-400" : "text-primary"}`}>
                          {h.final_action}
                        </td>
                        <td className={`p-2.5 text-right ${h.reward >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                          {h.reward > 0 ? "+" : ""}{h.reward.toFixed(0)}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCell({
  label,
  value,
  color = "text-foreground",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="bg-card/30 p-3">
      <p className="text-[9px] uppercase text-muted-foreground mb-0.5 tracking-wider">{label}</p>
      <p className={`text-sm font-bold font-mono truncate ${color}`}>{value}</p>
    </div>
  );
}

function InfoRow({
  label,
  value,
  valueClass = "text-foreground font-bold",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-muted-foreground">{label}</span>
      <span className={valueClass}>{value}</span>
    </div>
  );
}
