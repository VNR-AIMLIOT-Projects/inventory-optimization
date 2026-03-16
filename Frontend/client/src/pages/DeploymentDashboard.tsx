import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from "@/components/ui/dialog";
import { 
  Play, Pause, RotateCcw, FastForward, 
  Settings, Package, TrendingUp, TrendingDown,
  AlertTriangle, DollarSign, Calendar, Edit3, 
  Check, X, Loader2, ArrowRight, History
} from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import { 
  startDeployment, 
  getDeploymentState, 
  stepDeployment, 
  applyOverride, 
  removeOverride,
  resetDeployment,
  runAllDeployment,
  getOverrides,
  getCurrentLoadedRun,
  loadTrainingRun,
  getTrainingRuns,
} from "@/lib/api";
import type { SimulationState, SimulationDay, SimulationMetrics, DeploymentConfig, LoadedTrainingRun, TrainingRunSummary } from "@/lib/api";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine, Area, ComposedChart } from "recharts";

export default function DeploymentDashboard() {
  const { toast } = useToast();
  const [, navigate] = useLocation();
  
  // State
  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(false);
  const [session, setSession] = useState<DeploymentConfig | null>(null);
  const [simState, setSimState] = useState<SimulationState | null>(null);
  const [overrides, setOverrides] = useState<Record<number, number>>({});
  
  // Override dialog
  const [overrideDialogOpen, setOverrideDialogOpen] = useState(false);
  const [overrideDay, setOverrideDay] = useState<number | null>(null);
  const [overrideQty, setOverrideQty] = useState<number>(0);
  
  // Current run info
  const [currentRun, setCurrentRun] = useState<LoadedTrainingRun | null>(null);

  // Load current run on mount
  useEffect(() => {
    async function init() {
      try {
        // Try to get the currently loaded run
        let run: LoadedTrainingRun | null = null;
        try {
          run = await getCurrentLoadedRun();
        } catch {
          // Endpoint may fail if no run loaded — that's OK
        }

        if (!run) {
          // No explicit loaded run — try to auto-load the latest completed run from DB
          try {
            const allRuns = await getTrainingRuns();
            const completedRun = allRuns.find((r: TrainingRunSummary) => r.status === "completed" && r.model_path);
            if (completedRun) {
              const loadResult = await loadTrainingRun(completedRun.id);
              // Re-fetch the loaded run
              try {
                run = await getCurrentLoadedRun();
              } catch { /* ignore */ }
            }
          } catch { /* ignore */ }

          // Still no run? Check health as last resort
          if (!run) {
            try {
              const health = await fetch("http://localhost:8000/api/health");
              const data = await health.json();
              if (!data.agent_trained) {
                toast({ title: "No Model Loaded", description: "Please train or load a model first.", variant: "destructive" });
                navigate("/evaluate");
                return;
              }
            } catch {
              toast({ title: "Backend Unreachable", description: "Cannot connect to the backend.", variant: "destructive" });
              navigate("/evaluate");
              return;
            }
          }
        }

        if (run) {
          setCurrentRun(run);
        }
        
        // Try to get existing deployment state
        try {
          const state = await getDeploymentState();
          if (state && state.session_id) {
            setSimState(state);
            // Get overrides
            const overrideInfo = await getOverrides(state.session_id);
            setOverrides(overrideInfo.overrides || {});
            
            // Get session config
            setSession({
              session_id: state.session_id,
              sku: run?.sku || state.session_id,
              total_days: state.total_days,
              start_day: 0,
              initial_inventory: 100, // Will be updated
              max_order: run?.max_order || 100,
              action_step: run?.action_step || 10,
              holding_cost: run?.holding_cost || 5,
              stockout_penalty: run?.stockout_penalty || 200,
            });
          }
        } catch {
          // No active deployment session — that's normal
        }
      } catch (err) {
        console.error("Init error:", err);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  const handleStartDeployment = async () => {
    if (!currentRun) return;
    
    setInitializing(true);
    try {
      // First load the model
      await loadTrainingRun(currentRun.id);
      
      // Then start deployment
      const sess = await startDeployment(currentRun.id, 0);
      setSession(sess);
      
      // Get initial state
      const state = await getDeploymentState(sess.session_id);
      setSimState(state);
      setOverrides({});
      
      toast({ title: "Deployment Started", description: `Simulation ready for ${sess.sku}` });
    } catch (err: any) {
      toast({ title: "Failed to Start", description: err.message, variant: "destructive" });
    } finally {
      setInitializing(false);
    }
  };

  const handleStep = async () => {
    if (!session) return;
    
    try {
      const state = await stepDeployment(session.session_id);
      setSimState(state);
    } catch (err: any) {
      toast({ title: "Step Failed", description: err.message, variant: "destructive" });
    }
  };

  const handleRunAll = async () => {
    if (!session) return;
    
    try {
      const result = await runAllDeployment(session.session_id);
      setSimState(prev => prev ? {
        ...prev,
        current_day: result.final_metrics.current_day,
        history: result.history,
        metrics: result.final_metrics,
      } : null);
      toast({ title: "Simulation Complete", description: result.message });
    } catch (err: any) {
      toast({ title: "Run All Failed", description: err.message, variant: "destructive" });
    }
  };

  const handleReset = async () => {
    if (!session) return;
    
    try {
      const sess = await resetDeployment(session.session_id);
      setSession(sess);
      const state = await getDeploymentState(sess.session_id);
      setSimState(state);
      setOverrides({});
      toast({ title: "Simulation Reset", description: "All progress cleared. Overrides preserved." });
    } catch (err: any) {
      toast({ title: "Reset Failed", description: err.message, variant: "destructive" });
    }
  };

  const openOverrideDialog = (day: number, currentRlAction: number, currentOverride?: number) => {
    setOverrideDay(day);
    setOverrideQty(currentOverride ?? currentRlAction);
    setOverrideDialogOpen(true);
  };

  const handleApplyOverride = async () => {
    if (!session || overrideDay === null) return;
    
    try {
      await applyOverride(overrideDay, overrideQty, session.session_id);
      
      // Refresh state
      const state = await getDeploymentState(session.session_id);
      setSimState(state);
      
      // Refresh overrides
      const overrideInfo = await getOverrides(session.session_id);
      setOverrides(overrideInfo.overrides || {});
      
      setOverrideDialogOpen(false);
      toast({ title: "Override Applied", description: `Day ${overrideDay} will now order ${overrideQty} units.` });
    } catch (err: any) {
      toast({ title: "Override Failed", description: err.message, variant: "destructive" });
    }
  };

  const handleRemoveOverride = async (day: number) => {
    if (!session) return;
    
    try {
      await removeOverride(day, session.session_id);
      
      // Refresh state
      const state = await getDeploymentState(session.session_id);
      setSimState(state);
      
      // Refresh overrides
      const overrideInfo = await getOverrides(session.session_id);
      setOverrides(overrideInfo.overrides || {});
      
      toast({ title: "Override Removed", description: `Day ${day} will use RL decision.` });
    } catch (err: any) {
      toast({ title: "Remove Failed", description: err.message, variant: "destructive" });
    }
  };

  // Prepare chart data
  const chartData = simState?.history.map((h) => ({
    day: h.day,
    date: h.date,
    demand: h.demand,
    inventory: h.inventory,
    rl_action: h.rl_action,
    final_action: h.final_action,
    reward: h.reward,
    cumulative_reward: simState.history.slice(0, h.day + 1).reduce((sum, d) => sum + d.reward, 0),
  })) || [];

  const formatNumber = (num: number) => {
    if (Math.abs(num) >= 1000000) return (num / 1000000).toFixed(1) + "M";
    if (Math.abs(num) >= 1000) return (num / 1000).toFixed(1) + "K";
    return num.toFixed(0);
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <Header title="RL Agent Deployment" />
      <div className="flex">
        <Sidebar />
        <main className="flex-1 p-6 ml-72">
          <StageNav />
          
          <div className="mt-6">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h1 className="text-3xl font-bold">RL Agent Deployment</h1>
                <p className="text-muted-foreground">
                  Interactive simulation with human-in-the-loop overrides
                </p>
              </div>
              {session && (
                <Badge variant="outline" className="text-lg px-4 py-2">
                  SKU: {session.sku}
                </Badge>
              )}
            </div>

            {/* Start Button */}
            {!session && (
              <Card className="border-border/50 bg-card/50">
                <CardContent className="py-10 flex flex-col items-center justify-center gap-4">
                  <Package className="w-16 h-16 text-muted-foreground" />
                  <h2 className="text-xl font-semibold">Ready to Deploy</h2>
                  <p className="text-muted-foreground text-center max-w-md">
                    Start an interactive simulation where you can override the RL agent's 
                    decisions for future days and see the impact on inventory management.
                  </p>
                  <Button 
                    onClick={handleStartDeployment} 
                    disabled={initializing}
                    size="lg"
                    className="mt-4"
                  >
                    {initializing ? (
                      <><Loader2 className="w-5 h-5 mr-2 animate-spin" /> Starting...</>
                    ) : (
                      <><Play className="w-5 h-5 mr-2" /> Start Deployment</>
                    )}
                  </Button>
                </CardContent>
              </Card>
            )}

            {/* Main Dashboard */}
            {session && simState && (
              <div className="space-y-6">
                {/* Controls */}
                <Card>
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2">
                      <Settings className="w-5 h-5" />
                      Simulation Controls
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <div className="flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-muted-foreground" />
                          <span className="text-sm text-muted-foreground">Day:</span>
                          <span className="font-mono font-bold text-lg">
                            {simState.current_day} / {simState.total_days}
                          </span>
                        </div>
                        
                        {simState.next_rl_action !== null && (
                          <div className="flex items-center gap-2 ml-4">
                            <span className="text-sm text-muted-foreground">Next RL Decision:</span>
                            <Badge variant="secondary" className="font-mono">
                              {simState.next_rl_action} units
                            </Badge>
                          </div>
                        )}
                      </div>
                      
                      <div className="flex gap-2">
                        <Button 
                          onClick={handleStep} 
                          disabled={simState.current_day >= simState.total_days}
                          variant="outline"
                        >
                          <ArrowRight className="w-4 h-4 mr-1" /> Step
                        </Button>
                        <Button 
                          onClick={handleRunAll}
                          disabled={simState.current_day >= simState.total_days}
                          variant="outline"
                        >
                          <FastForward className="w-4 h-4 mr-1" /> Run All
                        </Button>
                        <Button onClick={handleReset} variant="outline">
                          <RotateCcw className="w-4 h-4 mr-1" /> Reset
                        </Button>
                        {simState.current_day < simState.total_days && (
                          <Button 
                            onClick={() => openOverrideDialog(
                              simState.current_day, 
                              simState.next_rl_action ?? 0, 
                              overrides[simState.current_day]
                            )}
                            variant="outline"
                            className="border-green-500/50 text-green-500 hover:bg-green-500/10"
                          >
                            <Edit3 className="w-4 h-4 mr-1" /> Override Next Day
                          </Button>
                        )}
                      </div>
                    </div>
                    
                    {/* Progress bar */}
                    <div className="mt-4">
                      <div className="h-2 bg-muted rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-primary transition-all duration-300"
                          style={{ width: `${(simState.current_day / simState.total_days) * 100}%` }}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Metrics */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                  <MetricCard 
                    title="Cumulative Reward"
                    value={formatNumber(simState.metrics.cumulative_reward)}
                    icon={<TrendingUp className="w-5 h-5" />}
                    trend={simState.metrics.cumulative_reward >= 0 ? "up" : "down"}
                  />
                  <MetricCard 
                    title="Total Revenue"
                    value={formatNumber(simState.metrics.total_revenue)}
                    icon={<DollarSign className="w-5 h-5" />}
                  />
                  <MetricCard 
                    title="Total Costs"
                    value={formatNumber(simState.metrics.total_cost)}
                    icon={<TrendingDown className="w-5 h-5" />}
                    variant="cost"
                  />
                  <MetricCard 
                    title="Stockout Days"
                    value={String(simState.metrics.stockout_days)}
                    icon={<AlertTriangle className="w-5 h-5" />}
                    variant={simState.metrics.stockout_days > 0 ? "warning" : "default"}
                  />
                </div>

                {/* Charts */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <Card>
                    <CardHeader>
                      <CardTitle>Inventory Levels</CardTitle>
                      <CardDescription>Inventory over time with demand</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={250}>
                        <ComposedChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                          <XAxis dataKey="day" fontSize={12} />
                          <YAxis fontSize={12} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: 'var(--card)', border: '1px solid var(--border)' }}
                          />
                          <Area 
                            type="monotone" 
                            dataKey="demand" 
                            fill="rgba(148, 163, 184, 0.3)" 
                            stroke="none"
                            name="Demand"
                          />
                          <Line 
                            type="monotone" 
                            dataKey="inventory" 
                            stroke="#3b82f6" 
                            strokeWidth={2}
                            dot={false}
                            name="Inventory"
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>

                  <Card>
                    <CardHeader>
                      <CardTitle>Order Quantities</CardTitle>
                      <CardDescription>RL decisions vs final actions</CardDescription>
                    </CardHeader>
                    <CardContent>
                      <ResponsiveContainer width="100%" height={250}>
                        <ComposedChart data={chartData}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                          <XAxis dataKey="day" fontSize={12} />
                          <YAxis fontSize={12} />
                          <Tooltip 
                            contentStyle={{ backgroundColor: 'var(--card)', border: '1px solid var(--border)' }}
                          />
                          <Line 
                            type="stepAfter" 
                            dataKey="rl_action" 
                            stroke="#6b7280" 
                            strokeWidth={1.5}
                            strokeDasharray="5 5"
                            dot={false}
                            name="RL Decision"
                          />
                          <Line 
                            type="stepAfter" 
                            dataKey="final_action" 
                            stroke="#22c55e" 
                            strokeWidth={2}
                            dot={false}
                            name="Final Action"
                          />
                        </ComposedChart>
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </div>

                {/* Decision Timeline */}
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <History className="w-5 h-5" />
                      Decision Timeline
                    </CardTitle>
                    <CardDescription>
                      Click edit on future days to override RL decisions
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <div className="flex gap-1 pb-2" style={{ minWidth: 'max-content' }}>
                        {Array.from({ length: Math.min(simState.total_days, 60) }).map((_, idx) => {
                          const day = Math.floor((idx / 60) * simState.total_days);
                          const historyItem = simState.history.find(h => h.day === day);
                          const isPast = day < simState.current_day;
                          const isCurrent = day === simState.current_day;
                          const isFuture = day > simState.current_day;
                          const hasOverride = overrides[day] !== undefined;
                          
                          return (
                            <div
                              key={day}
                              className={`
                                w-8 h-12 flex flex-col items-center justify-center text-xs rounded
                                ${isPast ? 'bg-muted' : isCurrent ? 'bg-primary text-primary-foreground' : 'bg-muted/50'}
                                ${hasOverride ? 'ring-2 ring-green-500' : ''}
                                ${!isPast ? 'hover:ring-2 hover:ring-primary cursor-pointer' : 'cursor-default opacity-60'}
                                transition-all
                              `}
                              onClick={() => {
                                if (!isPast) {
                                  openOverrideDialog(
                                    day, 
                                    historyItem?.rl_action ?? simState.next_rl_action ?? 0, 
                                    overrides[day]
                                  );
                                }
                              }}
                              title={isPast 
                                ? `Day ${day + 1}: RL=${historyItem?.rl_action ?? '?'}, Final=${historyItem?.final_action ?? '?'} (past)` 
                                : `Day ${day + 1}: Click to override${hasOverride ? ` (override: ${overrides[day]})` : ''}`
                              }
                            >
                              <span className="font-mono text-[10px]">{day + 1}</span>
                              {hasOverride && <Edit3 className="w-3 h-3 text-green-500" />}
                            </div>
                          );
                        })}
                      </div>
                    </div>
                    
                    <div className="mt-4 flex items-center gap-6 text-sm">
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 bg-muted rounded" />
                        <span>Past Days</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 bg-primary rounded" />
                        <span>Current Day</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="w-4 h-4 bg-muted/50 rounded ring-2 ring-green-500" />
                        <span>Overridden</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Edit3 className="w-4 h-4 text-muted-foreground" />
                        <span>Click to edit future</span>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                {/* Recent History Table */}
                <Card>
                  <CardHeader>
                    <CardTitle>Recent Decisions</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="border-b">
                            <th className="text-left py-2 px-3">Day</th>
                            <th className="text-left py-2 px-3">Date</th>
                            <th className="text-right py-2 px-3">Demand</th>
                            <th className="text-right py-2 px-3">Inventory</th>
                            <th className="text-right py-2 px-3">RL Action</th>
                            <th className="text-right py-2 px-3">Final</th>
                            <th className="text-right py-2 px-3">Reward</th>
                            <th className="text-center py-2 px-3">Override</th>
                          </tr>
                        </thead>
                        <tbody>
                          {simState.history.slice(-10).reverse().map((h) => (
                            <tr key={h.day} className="border-b hover:bg-muted/50">
                              <td className="py-2 px-3 font-mono">{h.day + 1}</td>
                              <td className="py-2 px-3">{h.date}</td>
                              <td className="py-2 px-3 text-right">{h.demand}</td>
                              <td className="py-2 px-3 text-right">{h.inventory}</td>
                              <td className="py-2 px-3 text-right text-muted-foreground">{h.rl_action}</td>
                              <td className="py-2 px-3 text-right font-medium">
                                {h.human_action !== null ? (
                                  <Badge variant="outline" className="text-green-500 border-green-500">
                                    {h.final_action}
                                  </Badge>
                                ) : (
                                  h.final_action
                                )}
                              </td>
                              <td className={`py-2 px-3 text-right ${h.reward >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                {h.reward.toFixed(0)}
                              </td>
                              <td className="py-2 px-3 text-center">
                                {h.human_action !== null && (
                                  <Button 
                                    variant="ghost" 
                                    size="sm"
                                    onClick={() => handleRemoveOverride(h.day)}
                                  >
                                    <X className="w-4 h-4" />
                                  </Button>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Override Dialog */}
      <Dialog open={overrideDialogOpen} onOpenChange={setOverrideDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Override RL Decision</DialogTitle>
            <DialogDescription>
              Override the RL agent's decision for Day {overrideDay !== null ? overrideDay + 1 : ''}.
              This will replace the RL's decision with your custom order quantity.
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-4">
            <Label htmlFor="override-qty">Order Quantity (0 - {session?.max_order || 100})</Label>
            <Input
              id="override-qty"
              type="number"
              min={0}
              max={session?.max_order || 100}
              value={overrideQty}
              onChange={(e) => setOverrideQty(parseInt(e.target.value) || 0)}
              className="mt-2"
            />
            <p className="text-sm text-muted-foreground mt-2">
              Set to 0 to order nothing, or any value up to {session?.max_order} units.
              The value will be rounded to the nearest valid action step ({session?.action_step || 10}).
            </p>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setOverrideDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleApplyOverride}>
              <Check className="w-4 h-4 mr-2" /> Apply Override
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function MetricCard({ 
  title, 
  value, 
  icon, 
  trend,
  variant = "default" 
}: { 
  title: string; 
  value: string; 
  icon: React.ReactNode;
  trend?: "up" | "down";
  variant?: "default" | "cost" | "warning";
}) {
  const variantClasses = {
    default: "",
    cost: "text-red-500",
    warning: "text-amber-500",
  };
  
  return (
    <Card>
      <CardContent className="pt-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">{title}</span>
          <span className="text-muted-foreground">{icon}</span>
        </div>
        <p className={`text-2xl font-bold mt-2 ${variantClasses[variant]}`}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
