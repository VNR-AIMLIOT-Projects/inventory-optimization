import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { 
  Terminal, Database, Play, Square, Activity, AlertTriangle, RefreshCcw, Command, ChevronRight, RotateCcw
} from "lucide-react";
import { useState, useEffect, useRef } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import { 
  startDeployment, 
  getDeploymentState, 
  stepDeployment, 
  applyOverride, 
  resetDeployment,
  getCurrentLoadedRun,
  loadTrainingRun,
  getTrainingRuns,
  runAllDeployment
} from "@/lib/api";
import type { SimulationState, DeploymentConfig, LoadedTrainingRun, TrainingRunSummary } from "@/lib/api";

export default function DeploymentDashboard() {
  const { toast } = useToast();
  const [, navigate] = useLocation();
  const ledgerRef = useRef<HTMLDivElement>(null);
  
  // State
  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(false);
  const [session, setSession] = useState<DeploymentConfig | null>(null);
  const [simState, setSimState] = useState<SimulationState | null>(null);
  
  // Current Day Override
  const [overrideValue, setOverrideValue] = useState<string>("");
  const [isExecuting, setIsExecuting] = useState(false);

  useEffect(() => {
    async function init() {
      try {
        let run: LoadedTrainingRun | null = null;
        try { run = await getCurrentLoadedRun(); } catch {}

        if (!run) {
          // Try to auto-load the most recent completed training run
          try {
            const allRuns = await getTrainingRuns();
            const completedRun = allRuns.find((r: TrainingRunSummary) => (r.status === "completed" || r.status === "success") && r.model_path);
            if (completedRun) {
              await loadTrainingRun(completedRun.id);
              try { run = await getCurrentLoadedRun(); } catch {}
            }
          } catch {}

          // Still no run — redirect back to evaluate with an error
          if (!run) {
            toast({ title: "SYS.ERR: NO MODEL", description: "Train or load a model first.", variant: "destructive" });
            navigate("/evaluate");
            return;
          }
        }

        try {
          const state = await getDeploymentState();
          if (state && state.session_id) {
            setSimState(state);
            setSession({
              session_id: state.session_id,
              sku: run?.sku || state.session_id,
              total_days: state.total_days,
              start_day: 0,
              initial_inventory: 0,
              max_order: run?.max_order || 100,
              action_step: run?.action_step || 10,
              holding_cost: run?.holding_cost || 5,
              stockout_penalty: run?.stockout_penalty || 200,
            });
            if (state.next_rl_action !== null) {
              setOverrideValue(String(state.next_rl_action));
            }
          }
        } catch {
          // No active deployment session yet — user will click START
        }
      } catch (err) {
        console.error("Init error:", err);
      } finally {
        setLoading(false);
      }
    }
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // Run once on mount only — navigate is stable within the effect closure

  // Auto-scroll the ledger whenever history grows
  useEffect(() => {
    if (ledgerRef.current) {
      ledgerRef.current.scrollTop = ledgerRef.current.scrollHeight;
    }
  }, [simState?.history]);

  // Pre-fill the override input whenever the RL recommended action changes
  useEffect(() => {
    if (simState?.next_rl_action != null) {
      setOverrideValue(String(simState.next_rl_action));
    }
  }, [simState?.next_rl_action]);

  const handleStart = async () => {
    setInitializing(true);
    try {
      const run = await getCurrentLoadedRun();
      if (!run) throw new Error("No model loaded in terminal");
      const sess = await startDeployment(run.id, 0);
      setSession(sess);
      const state = await getDeploymentState(sess.session_id);
      setSimState(state);
      if (state.next_rl_action !== null) setOverrideValue(String(state.next_rl_action));
      toast({ title: "SYS.START: ONLINE", description: `Session established for ${sess.sku}` });
    } catch (err: any) {
      toast({ title: "SYS.ERR: START FAILED", description: err.message, variant: "destructive" });
    } finally {
      setInitializing(false);
    }
  };

  const handleExecute = async () => {
    if (!session || !simState || simState.current_day >= simState.total_days) return;
    setIsExecuting(true);
    
    try {
      const qty = parseInt(overrideValue, 10);
      if (!isNaN(qty) && qty !== simState.next_rl_action) {
        // Enforce max and steps
        let clamped = Math.min(Math.max(0, qty), session.max_order);
        clamped = Math.round(clamped / session.action_step) * session.action_step;
        await applyOverride(simState.current_day, clamped, session.session_id);
      }
      
      const nextState = await stepDeployment(session.session_id);
      setSimState(nextState);
      setOverrideValue(nextState.next_rl_action !== null ? String(nextState.next_rl_action) : "");
    } catch (err: any) {
      toast({ title: "SYS.ERR: EXECUTE FAILED", description: err.message, variant: "destructive" });
    } finally {
      setIsExecuting(false);
    }
  };

  const handleAutoRun = async () => {
    if (!session) return;
    setIsExecuting(true);
    try {
      const result = await runAllDeployment(session.session_id);
      setSimState(prev => prev ? {
        ...prev,
        current_day: result.final_metrics.current_day,
        history: result.history,
        metrics: result.final_metrics,
      } : null);
      setOverrideValue("");
    } catch (err: any) {
      toast({ title: "SYS.ERR: AUTO FAILED", description: err.message, variant: "destructive" });
    } finally {
      setIsExecuting(false);
    }
  }

  const handleReset = async () => {
    if (!session) return;
    try {
      const sess = await resetDeployment(session.session_id);
      setSession(sess);
      const state = await getDeploymentState(sess.session_id);
      setSimState(state);
      setOverrideValue(state.next_rl_action !== null ? String(state.next_rl_action) : "");
      toast({ title: "SYS.RESET: OK" });
    } catch (err: any) {
      toast({ title: "SYS.ERR: RESET FAILED", description: err.message, variant: "destructive" });
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-foreground font-mono">
        <div className="flex items-center gap-2 border border-border px-6 py-4">
          <Activity className="w-5 h-5 animate-pulse text-green-500" />
          <span>BOOTING CORE...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col h-screen overflow-hidden font-mono text-sm">
        <Header title="DEPLOYMENT // TERMINAL" />
        <div className="px-6 border-b border-border/50 py-3 flex justify-between items-center bg-muted/10">
           <StageNav /> 
           {session && (
             <div className="flex gap-4 items-center">
               <span className="text-muted-foreground text-xs uppercase tracking-widest">SKU:</span>
               <span className="font-bold border border-border px-2 py-0.5 bg-card">{session.sku}</span>
             </div>
           )}
        </div>

        <div className="flex-1 overflow-auto p-6 flex flex-col gap-6">
          {!session && (
            <div className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-border/50 bg-card/20 p-12">
              <Database className="w-12 h-12 text-muted-foreground mb-4 opacity-50" />
              <h2 className="text-xl font-bold uppercase tracking-widest mb-2">Simulation Engine Offline</h2>
              <p className="text-muted-foreground mb-6 max-w-md text-center">
                Initialize the interactive historical playback engine.
              </p>
              <Button onClick={handleStart} disabled={initializing} className="rounded-none border-2 border-primary font-bold uppercase tracking-widest px-8">
                {initializing ? "INIT..." : "START SYSTEM"}
              </Button>
            </div>
          )}

          {session && simState && (
            <>
              {/* TOP: METRICS ROW (Industrial Dashboard Style) */}
              <div className="grid grid-cols-5 gap-0 border border-border">
                <MetricBlock label="DAY" value={`${simState.current_day} / ${simState.total_days}`} />
                <MetricBlock label="CUMULATIVE REWARD" value={simState.metrics.cumulative_reward.toFixed(0)} color={simState.metrics.cumulative_reward >= 0 ? "text-green-500" : "text-amber-500"} />
                <MetricBlock label="TOTAL REVENUE" value={`$${simState.metrics.total_revenue.toFixed(0)}`} color="text-foreground" />
                <MetricBlock label="TOTAL COSTS" value={`-$${simState.metrics.total_cost.toFixed(0)}`} color="text-red-500" />
                <MetricBlock label="STOCKOUT DAYS" value={String(simState.metrics.stockout_days)} color={simState.metrics.stockout_days > 0 ? "text-amber-500" : "text-foreground"} />
              </div>

              {/* MAIN: TWO COLUMNS */}
              <div className="flex-1 grid grid-cols-12 gap-6 min-h-[400px]">
                
                {/* LEFT: NEXT DAY EXECUTION CONTROL */}
                <div className="col-span-4 border border-border bg-card/10 flex flex-col">
                  <div className="border-b border-border p-3 bg-muted/30 font-bold uppercase flex items-center gap-2">
                    <Terminal className="w-4 h-4" />
                    SIM.EXEC
                  </div>
                  
                  {simState.current_day < simState.total_days ? (
                    <div className="p-6 flex flex-col gap-6 flex-1 justify-center">
                      <div className="space-y-2">
                        <div className="text-xs text-muted-foreground uppercase flex justify-between">
                          <span>Date Target</span>
                          <span className="font-bold text-foreground">{simState.next_date || "END"}</span>
                        </div>
                        <div className="text-xs text-muted-foreground uppercase flex justify-between">
                          <span>Demand</span>
                          <span className="font-bold text-foreground">{simState.next_demand ?? "END"}</span>
                        </div>
                        <div className="text-xs text-muted-foreground uppercase flex justify-between">
                          <span>RL Advised Action</span>
                          <span className="font-bold text-blue-500">{simState.next_rl_action ?? 0}</span>
                        </div>
                      </div>

                      <div className="h-px bg-border my-2" />

                      <div className="space-y-3">
                        <label className="text-xs uppercase font-bold tracking-widest text-primary flex items-center gap-2">
                          <Command className="w-3 h-3" />
                          Final Order Quantity
                        </label>
                        <Input 
                          type="number" 
                          min={0} 
                          max={session.max_order} 
                          step={session.action_step}
                          className="h-14 text-2xl font-bold bg-background border-2 focus-visible:ring-0 focus-visible:border-primary rounded-none"
                          value={overrideValue}
                          onChange={(e) => setOverrideValue(e.target.value)}
                        />
                        <p className="text-[10px] text-muted-foreground uppercase">
                          Values clamped to multiples of {session.action_step} (max {session.max_order}).
                        </p>
                      </div>

                      <Button 
                        onClick={handleExecute} 
                        disabled={isExecuting}
                        className="h-14 w-full rounded-none font-bold uppercase tracking-widest bg-primary text-primary-foreground hover:bg-primary/90 mt-4"
                      >
                        {isExecuting ? "EXECUTING..." : "COMMIT & STEP"}
                        {!isExecuting && <ChevronRight className="w-4 h-4 ml-2" />}
                      </Button>
                      <Button 
                        onClick={handleAutoRun} 
                        disabled={isExecuting}
                        variant="outline"
                        className="rounded-none uppercase tracking-widest text-xs border-dashed"
                      >
                        AUTO-RUN REMAINING
                      </Button>
                    </div>
                  ) : (
                    <div className="p-6 flex flex-col items-center justify-center flex-1 text-center border-t border-border mt-auto h-full">
                      <Square className="w-12 h-12 text-muted-foreground mb-4 opacity-30" />
                      <h3 className="font-bold uppercase tracking-widest mb-1">Simulation Complete</h3>
                      <p className="text-xs text-muted-foreground mb-4">All days processed in this session.</p>
                      <Button onClick={handleReset} variant="outline" className="rounded-none">
                        <RotateCcw className="w-4 h-4 mr-2" /> RESTART SESSION
                      </Button>
                    </div>
                  )}
                </div>

                {/* RIGHT: LEDGER */}
                <div className="col-span-8 border border-border bg-card flex flex-col overflow-hidden">
                  <div className="border-b border-border p-3 bg-muted/30 font-bold uppercase flex justify-between items-center">
                    <span>SYS.LOG</span>
                    {simState.current_day >= simState.total_days && (
                      <span className="text-green-500 text-xs">END OF FILE</span>
                    )}
                  </div>
                  
                  <div className="flex-1 overflow-auto relative" ref={ledgerRef}>
                    <table className="w-full text-left border-collapse">
                      <thead className="sticky top-0 bg-card border-b border-border text-[10px] uppercase text-muted-foreground">
                        <tr>
                          <th className="p-3 w-12 font-normal border-r border-border">Day</th>
                          <th className="p-3 font-normal">Demand</th>
                          <th className="p-3 font-normal bg-muted/10">Inv</th>
                          <th className="p-3 font-normal text-blue-500/70 border-l border-border">RL</th>
                          <th className="p-3 font-normal text-amber-500/70">OVR</th>
                          <th className="p-3 font-normal border-r border-border font-bold">ACT</th>
                          <th className="p-3 font-normal text-right">Rwd</th>
                        </tr>
                      </thead>
                      <tbody className="text-xs">
                        {simState.history.length === 0 && (
                          <tr>
                            <td colSpan={7} className="p-6 text-center text-muted-foreground/50 italic">
                              Awaiting initialization...
                            </td>
                          </tr>
                        )}
                        {simState.history.map((h) => {
                          const isOverride = h.human_action !== null && h.human_action !== h.rl_action;
                          return (
                            <tr key={h.day} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                              <td className="p-3 font-bold border-r border-border/50 text-muted-foreground">{(h.day + 1).toString().padStart(3, '0')}</td>
                              <td className="p-3">{h.demand}</td>
                              <td className="p-3 bg-muted/10">{h.inventory}</td>
                              <td className="p-3 text-blue-500 border-l border-border/50">{h.rl_action}</td>
                              <td className="p-3 text-amber-500">{h.human_action !== null ? h.human_action : "-"}</td>
                              <td className={`p-3 font-bold border-r border-border/50 ${isOverride ? 'text-amber-500' : 'text-primary'}`}>
                                {h.final_action}
                              </td>
                              <td className={`p-3 text-right ${h.reward >= 0 ? "text-green-500" : "text-red-500"}`}>
                                {h.reward > 0 ? "+" : ""}{h.reward.toFixed(0)}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>

              </div>
            </>
          )}
        </div>
      </main>
    </div>
  );
}

function MetricBlock({ label, value, color = "text-foreground" }: { label: string, value: string, color?: string }) {
  return (
    <div className="p-4 border-r border-border last:border-r-0 bg-card/30 flex flex-col justify-center">
      <p className="text-[10px] uppercase text-muted-foreground mb-1 tracking-widest">{label}</p>
      <p className={`text-xl font-bold truncate ${color}`}>{value}</p>
    </div>
  );
}
