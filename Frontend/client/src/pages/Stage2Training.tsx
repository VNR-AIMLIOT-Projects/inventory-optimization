import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Brain, Settings2, TrendingUp, Loader2, ImageIcon, ArrowRight, ChevronDown, Activity, Wifi, WifiOff, Square, History, RotateCcw } from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import {
  startMultiSkuTraining,
  stopMultiSkuTraining,
  getMultiSkuTrainingStatus,
  getMultiSkuRewards,
  getTrainingRuns,
  loadTrainingRun,
} from "@/lib/api";
import type { MultiSkuTrainStatusResponse, SkuTrainStatus, TrainingRunSummary } from "@/lib/api";
import { useTrainingWs } from "@/hooks/use-training-ws";
import type { EpisodeData, TrainingWsStatus } from "@/hooks/use-training-ws";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from "recharts";

interface ChartPoint {
  episode: number;
  reward: number;
  avg50: number;
  bestEval: number;
}

function StatusBadge({ status }: Readonly<{ status: string }>) {
  const variants: Record<string, string> = {
    success: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
    completed: "bg-emerald-500/15 text-emerald-500 border-emerald-500/30",
    failure: "bg-red-500/15 text-red-500 border-red-500/30",
    failed: "bg-red-500/15 text-red-500 border-red-500/30",
    in_progress: "bg-blue-500/15 text-blue-500 border-blue-500/30",
    initiated: "bg-yellow-500/15 text-yellow-500 border-yellow-500/30",
    pending: "bg-muted text-muted-foreground border-border",
  };
  const cls = variants[status] || variants.pending;
  return (
    <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${cls}`}>
      {status}
    </Badge>
  );
}

export default function Stage2Training() {
  const { toast } = useToast();
  const [, navigate] = useLocation();

  const [episodes, setEpisodes] = useState<number | string>(500);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [isTraining, setIsTraining] = useState(false);
  const [overallStatus, setOverallStatus] = useState<string>("idle");
  const [trainingComplete, setTrainingComplete] = useState(false);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const [skuStatuses, setSkuStatuses] = useState<Record<string, SkuTrainStatus>>({});
  const [skuChartData, setSkuChartData] = useState<Record<string, ChartPoint[]>>({});
  const [skuLiveEpisode, setSkuLiveEpisode] = useState<Record<string, EpisodeData>>({});
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  // Training history state
  const [pastRuns, setPastRuns] = useState<TrainingRunSummary[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingRunId, setLoadingRunId] = useState<number | null>(null);

  const skuNames = Object.keys(skuStatuses).sort();

  useEffect(() => {
    if (!selectedSku && skuNames.length > 0) {
      setSelectedSku(skuNames[0]);
    }
  }, [skuNames, selectedSku]);

  // Fetch training history on mount
  useEffect(() => {
    (async () => {
      setLoadingHistory(true);
      try {
        const runs = await getTrainingRuns();
        setPastRuns(runs);
      } catch { }
      setLoadingHistory(false);
    })();
  }, []);

  // Refresh history when training completes
  const refreshHistory = useCallback(async () => {
    try {
      const runs = await getTrainingRuns();
      setPastRuns(runs);
    } catch { }
  }, []);

  // Backfill chart data from rewards endpoint (fallback when WS misses data)
  const backfillChartData = useCallback(async () => {
    try {
      const rewardsMap = await getMultiSkuRewards();
      setSkuChartData((prev) => {
        const updated = { ...prev };
        for (const [sku, rewards] of Object.entries(rewardsMap)) {
          // Only backfill if WS didn't already provide data
          if (!prev[sku] || prev[sku].length < rewards.length * 0.5) {
            updated[sku] = rewards.map((r: number, i: number) => {
              const start = Math.max(0, i - 49);
              const slice = rewards.slice(start, i + 1);
              const avg = slice.reduce((a: number, b: number) => a + b, 0) / slice.length;
              return {
                episode: i + 1,
                reward: Math.round(r),
                avg50: Math.round(avg),
                bestEval: Math.round(Math.max(...rewards.slice(0, i + 1))),
              };
            });
          }
        }
        return updated;
      });
    } catch { }
  }, []);

  const onEpisode = useCallback((data: EpisodeData) => {
    const sku = data.sku || "unknown";

    setSkuLiveEpisode((prev) => ({ ...prev, [sku]: data }));

    setSkuStatuses((prev) => ({
      ...prev,
      [sku]: {
        ...prev[sku],
        sku,
        status: "running",
        current_episode: data.episode,
        total_episodes: data.total_episodes,
        best_reward: data.best_reward,
        latest_reward: data.reward,
        avg_reward_last_50: data.avg_reward_last_50,
        message: "Training " + sku + "...",
      },
    }));

    setSkuChartData((prev) => ({
      ...prev,
      [sku]: [
        ...(prev[sku] || []),
        {
          episode: data.episode,
          reward: Math.round(data.reward),
          avg50: Math.round(data.avg_reward_last_50),
          bestEval: Math.round(data.best_eval_reward),
        },
      ],
    }));
  }, []);

  const onStatusChange = useCallback((data: TrainingWsStatus) => {
    if (data.status === "completed" || data.status === "success") {
      setIsTraining(false);
      setTrainingComplete(true);
      setOverallStatus("completed");
      backfillChartData();
      refreshHistory();
      toast({
        title: "Multi-SKU Training Complete",
        description: data.message ?? "All SKUs trained successfully.",
      });
    } else if (data.status === "stopped" || data.status === "cancelled") {
      setIsTraining(false);
      setTrainingComplete(true);
      setOverallStatus("stopped");
      backfillChartData();
      refreshHistory();
      toast({ title: "Training Stopped", description: data.message ?? "Training was stopped early." });
    } else if (data.status === "failed" || data.status === "failure") {
      setIsTraining(false);
      setOverallStatus("failed");
      refreshHistory();
      toast({
        title: "Training Failed",
        description: data.message ?? "An error occurred during training",
        variant: "destructive",
      });
    }
  }, [toast, refreshHistory]);

  const { connected } = useTrainingWs(isTraining, { onEpisode, onStatusChange });

  useEffect(() => {
    (async () => {
      try {
        const s = await getMultiSkuTrainingStatus();
        setOverallStatus(s.overall_status);
        if (Object.keys(s.skus).length > 0) {
          setSkuStatuses(s.skus);
        }
        if (s.overall_status === "running") {
          setIsTraining(true);
          startPolling();
          // Backfill existing chart data on page reload (WS may miss earlier episodes)
          backfillChartData();
        } else if (s.overall_status === "completed" || s.overall_status === "stopped") {
          setTrainingComplete(true);
          backfillChartData();
        }
      } catch { }
    })();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  const startPolling = useCallback(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const s = await getMultiSkuTrainingStatus();
        setOverallStatus(s.overall_status);
        setSkuStatuses(s.skus);

        // Build chart points from polling data when WS isn't connected
        if (s.overall_status === "running") {
          setSkuChartData((prev) => {
            const updated = { ...prev };
            for (const [sku, st] of Object.entries(s.skus)) {
              if (st.current_episode > 0) {
                const existing = updated[sku] || [];
                const lastEp = existing.length > 0 ? existing[existing.length - 1].episode : 0;
                if (st.current_episode > lastEp) {
                  updated[sku] = [
                    ...existing,
                    {
                      episode: st.current_episode,
                      reward: Math.round(st.latest_reward),
                      avg50: Math.round(st.avg_reward_last_50),
                      bestEval: Math.round(st.best_reward),
                    },
                  ];
                }
              }
            }
            return updated;
          });
        }

        if (s.overall_status === "completed" || s.overall_status === "stopped") {
          clearInterval(pollingRef.current!);
          pollingRef.current = null;
          setIsTraining(false);
          setTrainingComplete(true);
          backfillChartData();
          toast({
            title: s.overall_status === "completed" ? "Training Complete" : "Training Stopped",
            description: s.message || "Done.",
          });
        } else if (s.overall_status === "failed") {
          clearInterval(pollingRef.current!);
          pollingRef.current = null;
          setIsTraining(false);
          toast({ title: "Training Failed", description: s.message || "Error", variant: "destructive" });
        }
      } catch { }
    }, 2500);
  }, [toast]);

  const handleStartTraining = async () => {
    setIsTraining(true);
    setTrainingComplete(false);
    setOverallStatus("running");
    setSkuStatuses({});
    setSkuChartData({});
    setSkuLiveEpisode({});
    setSelectedSku(null);
    try {
      const parsedEpisodes = Number(episodes);
      const numEpisodes = Number.isFinite(parsedEpisodes) && parsedEpisodes >= 10 ? Math.floor(parsedEpisodes) : 500;
      setEpisodes(numEpisodes);
      const res = await startMultiSkuTraining({ episodes: numEpisodes });
      setSkuStatuses(res.skus);
      toast({ title: "Multi-SKU Training Started", description: res.message });
      startPolling();
    } catch (err: any) {
      const msg = String(err?.message || "");
      if (msg.toLowerCase().includes("already") && msg.toLowerCase().includes("active")) {
        setIsTraining(true);
        setOverallStatus("running");
        startPolling();
        toast({ title: "Training Already Running", description: "Reconnected to active training session." });
        return;
      }
      setIsTraining(false);
      setOverallStatus("failed");
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  const handleStopTraining = async () => {
    try {
      await stopMultiSkuTraining();
      toast({ title: "Stopping...", description: "Training will stop after current episodes." });
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  const handleLoadRun = async (runId: number) => {
    setLoadingRunId(runId);
    try {
      const result = await loadTrainingRun(runId);
      toast({ title: "Model Loaded", description: result.message });
      setTrainingComplete(true);
    } catch (err: any) {
      toast({ title: "Load Failed", description: err.message, variant: "destructive" });
    } finally {
      setLoadingRunId(null);
    }
  };

  const formatReward = (value: number) => {
    if (Math.abs(value) >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M";
    if (Math.abs(value) >= 1_000) return (value / 1_000).toFixed(0) + "K";
    return value.toFixed(0);
  };

  function getSkuStatusDot(status: string) {
    if (status === "running") return "bg-blue-400 animate-pulse";
    if (status === "completed") return "bg-emerald-400";
    if (status === "stopped") return "bg-yellow-400";
    if (status === "failed") return "bg-red-400";
    return "bg-muted-foreground";
  }

  const totalEpisodesAll = Object.values(skuStatuses).reduce((sum, s) => sum + (s.total_episodes || 0), 0);
  const currentEpisodesAll = Object.values(skuStatuses).reduce((sum, s) => sum + (s.current_episode || 0), 0);
  const overallProgressPercent = totalEpisodesAll > 0 ? Math.round((currentEpisodesAll / totalEpisodesAll) * 100) : 0;

  function renderSkuChart(sku: string) {
    const data = skuChartData[sku] || [];
    if (data.length > 0) {
      return (
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={data} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
            <XAxis dataKey="episode" tick={{ fontSize: 11 }} label={{ value: "Episode", position: "insideBottomRight", offset: -5, fontSize: 12 }} />
            <YAxis tickFormatter={formatReward} tick={{ fontSize: 11 }} label={{ value: "Reward", angle: -90, position: "insideLeft", fontSize: 12 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
              formatter={(value: number, name: string) => [formatReward(value), name]}
              labelFormatter={(ep: number) => "Episode " + ep}
            />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
            <Line type="monotone" dataKey="reward" name="Episode Reward" stroke="hsl(var(--primary))" dot={false} strokeWidth={1} opacity={0.4} isAnimationActive={false} />
            <Line type="monotone" dataKey="avg50" name="Avg (Last 50)" stroke="#f97316" dot={false} strokeWidth={2} isAnimationActive={false} />
            <Line type="monotone" dataKey="bestEval" name="Best Eval" stroke="#22c55e" dot={false} strokeWidth={2} strokeDasharray="6 3" isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      );
    }

    const skuStatus = skuStatuses[sku];
    if (skuStatus && (skuStatus.status === "running" || skuStatus.status === "completed")) {
      return (
        <div className="h-[380px] flex flex-col items-center justify-center text-muted-foreground">
          <Loader2 className="w-10 h-10 animate-spin text-primary mb-3" />
          <p className="text-sm font-medium">Waiting for data from {sku}...</p>
        </div>
      );
    }

    return (
      <div className="h-[380px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
        <ImageIcon className="w-10 h-10 mb-3 opacity-10" />
        <p className="text-sm font-medium">No data for {sku}</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Multi-SKU DQN Training" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">
          <StageNav />

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left: Training Controls */}
            <div className="col-span-1 space-y-6">
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Brain className="w-5 h-5 text-primary" /> Training Configuration
                  </CardTitle>
                  <CardDescription>Train DQN agents for all SKUs in parallel</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-2">
                    <Label className="text-xs">Episodes (per SKU)</Label>
                    <Input
                      type="number"
                      min={10}
                      max={5000}
                      value={episodes}
                      onChange={(e) => {
                        const raw = e.target.value;
                        if (raw === "") setEpisodes("");
                        else {
                          const n = Number.parseInt(raw);
                          if (!Number.isNaN(n)) setEpisodes(n);
                        }
                      }}
                      onBlur={() => {
                        if (episodes === "" || Number(episodes) < 10) setEpisodes(10);
                      }}
                      disabled={isTraining}
                    />
                  </div>

                  <Collapsible open={advancedOpen} onOpenChange={setAdvancedOpen}>
                    <CollapsibleTrigger asChild>
                      <Button variant="ghost" size="sm" className="w-full justify-between gap-2 text-muted-foreground">
                        <span className="flex items-center gap-2">
                          <Settings2 className="w-4 h-4" /> Advanced Settings
                        </span>
                        <ChevronDown className={"w-4 h-4 transition-transform " + (advancedOpen ? "rotate-180" : "")} />
                      </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-4 pt-4">
                      <p className="text-xs text-muted-foreground">
                        Each SKU gets its own independent agent with auto-configured parameters.
                      </p>
                    </CollapsibleContent>
                  </Collapsible>

                  <div className="flex gap-2">
                    <Button
                      onClick={handleStartTraining}
                      disabled={isTraining}
                      className="flex-1 gap-2 h-12 text-lg font-bold shadow-lg shadow-primary/20"
                    >
                      {isTraining ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <Brain className="w-5 h-5" />
                      )}
                      {isTraining ? "Training All SKUs..." : "Start Multi-SKU Training"}
                    </Button>
                    {isTraining && (
                      <Button
                        onClick={handleStopTraining}
                        variant="destructive"
                        className="gap-2 h-12 px-5 text-lg font-bold shadow-lg"
                      >
                        <Square className="w-5 h-5" />
                        Stop
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Overall Progress */}
              {(isTraining || trainingComplete) && skuNames.length > 0 && (
                <Card className="border-border/50 shadow-lg bg-card/50">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Activity className="w-4 h-4 text-primary" /> All SKUs Progress
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {isTraining && (
                      <div className="flex items-center gap-2 text-xs">
                        {connected ? (
                          <>
                            <Wifi className="w-3 h-3 text-emerald-500" />
                            <span className="text-emerald-500 font-medium">Live WebSocket</span>
                          </>
                        ) : (
                          <>
                            <WifiOff className="w-3 h-3 text-yellow-500" />
                            <span className="text-yellow-500 font-medium">Polling (WS connecting...)</span>
                          </>
                        )}
                      </div>
                    )}

                    <div className="space-y-2">
                      <div className="flex justify-between text-xs font-mono">
                        <span>Overall: {currentEpisodesAll} / {totalEpisodesAll} episodes</span>
                        <span>{overallProgressPercent}%</span>
                      </div>
                      <Progress value={overallProgressPercent} className="h-2" />
                    </div>

                    <div className="space-y-3">
                      {skuNames.map((sku) => {
                        const s = skuStatuses[sku];
                        const pct = s?.total_episodes ? Math.round((s.current_episode / s.total_episodes) * 100) : 0;
                        return (
                          <button
                            key={sku}
                            onClick={() => setSelectedSku(sku)}
                            className={"w-full text-left p-3 rounded-lg border transition-all " +
                              (selectedSku === sku
                                ? "border-primary/50 bg-primary/5 ring-1 ring-primary/20"
                                : "border-border/50 bg-muted/30 hover:bg-muted/50"
                              )
                            }
                          >
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-2">
                                <div className={"w-2 h-2 rounded-full " + getSkuStatusDot(s?.status || "idle")} />
                                <span className="text-sm font-bold">{sku}</span>
                              </div>
                              <span className="text-xs font-mono text-muted-foreground">{pct}%</span>
                            </div>
                            <Progress value={pct} className="h-1.5" />
                            <div className="flex justify-between mt-1 text-[10px] text-muted-foreground">
                              <span>Ep {s?.current_episode || 0}/{s?.total_episodes || 0}</span>
                              <span>Best: {s?.best_reward ? formatReward(s.best_reward) : "\u2014"}</span>
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </CardContent>
                </Card>
              )}

              {trainingComplete && (
                <Button onClick={() => navigate("/evaluate")} className="w-full gap-2">
                  Next: Evaluate Results <ArrowRight className="w-4 h-4" />
                </Button>
              )}

              {/* Training History */}
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <History className="w-4 h-4 text-primary" /> Past Training Runs
                  </CardTitle>
                  <CardDescription>Browse and reload previous training runs</CardDescription>
                </CardHeader>
                <CardContent>
                  {loadingHistory ? (
                    <div className="flex items-center justify-center py-6">
                      <Loader2 className="w-5 h-5 animate-spin text-primary" />
                    </div>
                  ) : pastRuns.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-6">No training runs yet</p>
                  ) : (
                    <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
                      {pastRuns.map((run) => (
                        <div
                          key={run.id}
                          className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/20 hover:bg-muted/40 transition-colors"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-bold truncate">{run.sku}</span>
                              <StatusBadge status={run.status} />
                            </div>
                            <div className="flex items-center gap-3 mt-1 text-[10px] text-muted-foreground">
                              <span>{run.episodes} ep</span>
                              {run.best_reward != null && <span>Best: {formatReward(run.best_reward)}</span>}
                              {run.evaluation?.rl_vs_oracle_pct != null && (
                                <span className="text-emerald-500 font-medium">
                                  {run.evaluation.rl_vs_oracle_pct.toFixed(1)}% of Oracle
                                </span>
                              )}
                              {run.created_at && (
                                <span>{new Date(run.created_at).toLocaleDateString()}</span>
                              )}
                            </div>
                          </div>
                          {run.status === "success" && run.model_path && (
                            <Button
                              variant="outline"
                              size="sm"
                              className="ml-2 gap-1 shrink-0"
                              disabled={loadingRunId === run.id}
                              onClick={() => handleLoadRun(run.id)}
                            >
                              {loadingRunId === run.id ? (
                                <Loader2 className="w-3 h-3 animate-spin" />
                              ) : (
                                <RotateCcw className="w-3 h-3" />
                              )}
                              Load
                            </Button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Right: Per-SKU Reward Chart & Stats */}
            <div className="col-span-1 lg:col-span-2 space-y-6">
              {skuNames.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {skuNames.map((sku) => (
                    <Button
                      key={sku}
                      variant={selectedSku === sku ? "default" : "outline"}
                      size="sm"
                      onClick={() => setSelectedSku(sku)}
                      className="gap-2"
                    >
                      <div className={"w-2 h-2 rounded-full " + getSkuStatusDot(skuStatuses[sku]?.status || "idle")} />
                      {sku}
                    </Button>
                  ))}
                </div>
              )}

              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <TrendingUp className="w-5 h-5 text-primary" />
                    {selectedSku ? "Reward Curve \u2014 " + selectedSku : "Reward Curve"}
                    {isTraining && connected && (
                      <span className="ml-auto flex items-center gap-1 text-xs font-normal text-emerald-500">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> LIVE
                      </span>
                    )}
                  </CardTitle>
                  <CardDescription>
                    {trainingComplete && "Training complete \u2014 select a SKU to view its reward curve"}
                    {!trainingComplete && isTraining && "Live training progress for each SKU"}
                    {!trainingComplete && !isTraining && "Start training to see per-SKU reward curves"}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {selectedSku ? renderSkuChart(selectedSku) : (
                    <div className="h-[380px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
                      <ImageIcon className="w-12 h-12 mb-4 opacity-10" />
                      <p className="text-sm font-medium">No training data yet</p>
                      <p className="text-xs text-muted-foreground/70 mt-1">Configure parameters and click &quot;Start Multi-SKU Training&quot;</p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {selectedSku && skuStatuses[selectedSku] && skuStatuses[selectedSku].status !== "idle" && (
                <Card className="border-border/50 shadow-lg bg-card/50">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <Activity className="w-4 h-4 text-primary" /> Stats &mdash; {selectedSku}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Last Reward</p>
                        <p className="text-lg font-mono font-bold">
                          {skuStatuses[selectedSku].latest_reward != null ? formatReward(skuStatuses[selectedSku].latest_reward) : "\u2014"}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Avg (50)</p>
                        <p className="text-lg font-mono font-bold">
                          {skuStatuses[selectedSku].avg_reward_last_50 != null ? formatReward(skuStatuses[selectedSku].avg_reward_last_50) : "\u2014"}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Best Reward</p>
                        <p className="text-lg font-mono font-bold text-emerald-500">
                          {skuStatuses[selectedSku].best_reward != null ? formatReward(skuStatuses[selectedSku].best_reward) : "\u2014"}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Epsilon</p>
                        <p className="text-lg font-mono font-bold">
                          {skuLiveEpisode[selectedSku]?.epsilon?.toFixed(4) ?? "\u2014"}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
