import { Sidebar } from "@/components/common/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { StageNav } from "@/components/common/StageNav";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Brain, Settings2, TrendingUp, Loader2, ImageIcon, ArrowRight, ChevronDown, Activity, Wifi, WifiOff, Square, History, RotateCcw, X } from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import {
  startMultiSkuTraining,
  stopMultiSkuTraining,
  getMultiSkuTrainingStatus,
  stopTraining,
  startSweepTraining,
  stopSweepTraining,
  getSweepResults,
  getTrainingHistory,
  getMultiSkuRewards,
  getTrainingRuns,
  getTrainingRun,
  getCurrentLoadedRun,
  loadTrainingRun,
} from "@/lib/api";
import type { SkuTrainStatus, TrainingRunSummary, TrainingRunDetail } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import {
  getActiveLoadedHistoricalRunId,
  getLoadedHistoricalRuns,
  removeLoadedHistoricalRun,
  saveLoadedHistoricalRuns,
  setActiveLoadedHistoricalRunId,
  upsertLoadedHistoricalRun,
} from "@/lib/loaded-runs";
import { useTrainingWs } from "@/hooks/use-training-ws";
import type { EpisodeData, TrainingWsStatus } from "@/hooks/use-training-ws";
import { PageCopilot } from "@/features/copilot/PageCopilot";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, ReferenceLine
} from "recharts";

interface ChartPoint {
  episode: number;
  reward: number;
  avg50: number;
  bestEval: number;
}

function getSkuStatusDot(status: string) {
  if (status === "running") return "bg-blue-400 animate-pulse";
  if (status === "completed") return "bg-emerald-400";
  if (status === "stopped") return "bg-yellow-400";
  if (status === "failed") return "bg-red-400";
  return "bg-muted-foreground";
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
  const { isCollapsed } = useSidebar();
  const { toast } = useToast();
  const [, navigate] = useLocation();

  const [episodes, setEpisodes] = useState<number | string>(500);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  const [holdingCost, setHoldingCost] = useState<number | string>(5);
  const [stockoutPenalty, setStockoutPenalty] = useState<number | string>(200);
  const [gamma, setGamma] = useState<number | string>(0.98);
  const [learningRate, setLearningRate] = useState<number | string>(0.0001);

  const [sweepMode, setSweepMode] = useState(false);
  const [isSweeping, setIsSweeping] = useState(false);
  const [currentSweepId, setCurrentSweepId] = useState<string | null>(null);
  const [sweepResults, setSweepResults] = useState<any[]>([]);
  const [sweepParam, setSweepParam] = useState("learning_rate");
  const [sweepValuesStr, setSweepValuesStr] = useState("0.0001, 0.001, 0.01");
  const sweepPollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startSweepPolling = (runId: string) => {
    if (sweepPollingRef.current) clearInterval(sweepPollingRef.current);
    
    sweepPollingRef.current = setInterval(async () => {
      try {
        const res = await getSweepResults(runId);
        if (res.status === 'completed' || res.status === 'failed') {
          if (sweepPollingRef.current) clearInterval(sweepPollingRef.current);
          setIsSweeping(false);
          if (res.results) {
            setSweepResults(res.results);
          }
        } else if (res.status === 'running') {
          if (res.results) {
            setSweepResults(res.results);
          }
        }
      } catch (err) {
        console.error("Sweep poll error:", err);
      }
    }, 2000);
  };

  const handleStartSweep = async () => {
    try {
      setIsSweeping(true);
      setSweepResults([]);
      
      const paramMap: Record<string, string> = {
        "learning_rate": "learning_rate",
        "gamma": "gamma",
        "holding_cost": "holding_cost",
        "stockout_penalty": "stockout_penalty",
        "episodes": "episodes"
      };

      const sweepValues = sweepValuesStr.split(',').map(v => parseFloat(v.trim())).filter(v => !isNaN(v));
      if (sweepValues.length === 0) {
        toast({ title: "Error", description: "Please enter valid sweep values", variant: "destructive" });
        setIsSweeping(false);
        return;
      }

      const payload = {
        base_params: {
          episodes: Number(episodes),
          holding_cost: Number(holdingCost),
          stockout_penalty: Number(stockoutPenalty),
          gamma: Number(gamma),
          learning_rate: Number(learningRate)
        },
        sweep_param: paramMap[sweepParam] || "learning_rate",
        sweep_values: sweepValues
      };

      const res = await startSweepTraining(payload);
      toast({
        title: "Sweep Started",
        description: res.message
      });
      
      setCurrentSweepId(res.sweep_id);
      startSweepPolling(res.sweep_id);
    } catch (err: any) {
      setIsSweeping(false);
      toast({
        title: "Failed to start sweep",
        description: friendlyError(err),
        variant: "destructive",
      });
    }
  };

  const handleStopSweep = async () => {
    if (!currentSweepId) return;
    try {
      const res = await stopSweepTraining(currentSweepId);
      toast({
        title: "Sweep Stopped",
        description: res.message
      });
      setIsSweeping(false);
      setCurrentSweepId(null);
      if (pollingRef.current) clearInterval(pollingRef.current);
    } catch (err) {
      toast({
        title: "Failed to stop sweep",
        description: friendlyError(err),
        variant: "destructive"
      });
    }
  };

  const [isTraining, setIsTraining] = useState(false);
  const overallStatusRef = useRef<string>("idle");
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
  const [loadedRuns, setLoadedRuns] = useState<TrainingRunDetail[]>([]);

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

  const buildChartDataFromRewards = useCallback((rewards: number[]) => {
    return rewards.map((reward, index) => {
      const start = Math.max(0, index - 49);
      const slice = rewards.slice(start, index + 1);
      const avg = slice.reduce((sum, value) => sum + value, 0) / slice.length;
      const best = Math.max(...rewards.slice(0, index + 1));
      return {
        episode: index + 1,
        reward: Math.round(reward),
        avg50: Math.round(avg),
        bestEval: Math.round(best),
      };
    });
  }, []);

  const historicalStatuses: Record<string, SkuTrainStatus> = Object.fromEntries(
    loadedRuns.map((run) => {
      const rewards = run.rewards || [];
      const totalEpisodes = run.episodes || rewards.length;
      return [run.sku, {
        sku: run.sku,
        status: "completed",
        current_episode: totalEpisodes,
        total_episodes: totalEpisodes,
        best_reward: run.best_reward ?? 0,
        latest_reward: rewards.length > 0 ? (rewards.at(-1) ?? 0) : 0,
        avg_reward_last_50: run.final_avg_reward ?? 0,
        message: `Loaded historical run #${run.id}`,
      } satisfies SkuTrainStatus];
    }),
  );

  const historicalChartData: Record<string, ChartPoint[]> = Object.fromEntries(
    loadedRuns.map((run) => [run.sku, buildChartDataFromRewards(run.rewards || [])]),
  );

  const setOverallStatus = useCallback((status: string) => {
    overallStatusRef.current = status;
  }, []);

  const combinedStatuses = { ...skuStatuses, ...historicalStatuses };
  const combinedChartData = { ...skuChartData, ...historicalChartData };
  const currentHistoricalRun = selectedSku ? loadedRuns.find((run) => run.sku === selectedSku) ?? null : null;
  const combinedSkuNames = Object.keys(combinedStatuses).sort((left, right) => left.localeCompare(right));

  useEffect(() => {
    if (!selectedSku && combinedSkuNames.length > 0) {
      setSelectedSku(combinedSkuNames[0]);
    }
  }, [combinedSkuNames, selectedSku]);

  const selectSku = useCallback((sku: string) => {
    setSelectedSku(sku);
    const historicalRun = loadedRuns.find((run) => run.sku === sku);
    if (historicalRun) {
      setActiveLoadedHistoricalRunId(historicalRun.id);
    }
  }, [loadedRuns]);

  const addLoadedRun = useCallback((run: TrainingRunDetail) => {
    const nextLoadedRuns = upsertLoadedHistoricalRun(run);
    setLoadedRuns(nextLoadedRuns);
    setIsTraining(false);
    setTrainingComplete(true);
    setOverallStatus("completed");
    setSkuLiveEpisode({});
    setSelectedSku(run.sku);
  }, []);

  const handleRemoveLoadedRun = useCallback((run: TrainingRunDetail) => {
    const nextLoadedRuns = removeLoadedHistoricalRun(run.id);
    setLoadedRuns(nextLoadedRuns);
    if (selectedSku === run.sku) {
      const fallbackSku = nextLoadedRuns.at(-1)?.sku ?? Object.keys(skuStatuses)[0] ?? null;
      setSelectedSku(fallbackSku);
    }
  }, [selectedSku, skuStatuses]);

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
    const storedRuns = getLoadedHistoricalRuns();
    if (storedRuns.length > 0) {
      setLoadedRuns(storedRuns);
      const activeRunId = getActiveLoadedHistoricalRunId();
      const activeRun = storedRuns.find((run) => run.id === activeRunId) ?? storedRuns.at(-1);
      if (activeRun) {
        setSelectedSku(activeRun.sku);
      }
    }

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
        } else {
          const currentRun = await getCurrentLoadedRun();
          if (currentRun) addLoadedRun(currentRun);
        }
      } catch { }
    })();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, [addLoadedRun, backfillChartData]);

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
                const lastEp = existing.at(-1)?.episode ?? 0;
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
    setLoadedRuns([]);
    saveLoadedHistoricalRuns([]);
    setActiveLoadedHistoricalRunId(null);
    setSkuStatuses({});
    setSkuChartData({});
    setSkuLiveEpisode({});
    setSelectedSku(null);
    try {
      const parsedEpisodes = Number(episodes);
      const numEpisodes = Number.isFinite(parsedEpisodes) && parsedEpisodes >= 1 ? Math.floor(parsedEpisodes) : 500;
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
      toast({ title: "Training Start Failed", description: friendlyError(err, "training"), variant: "destructive" });
    }
  };

  const handleStopTraining = async () => {
    try {
      await stopMultiSkuTraining();
      toast({ title: "Stopping...", description: "Training will stop after current episodes." });
    } catch (err: any) {
      toast({ title: "Stop Failed", description: friendlyError(err, "training"), variant: "destructive" });
    }
  };

  const handleLoadRun = async (runId: number) => {
    setLoadingRunId(runId);
    try {
      const [result, run] = await Promise.all([loadTrainingRun(runId), getTrainingRun(runId)]);
      addLoadedRun(run);
      toast({ title: "Model Loaded", description: result.message });
    } catch (err: any) {
      toast({ title: "Load Failed", description: friendlyError(err, "training"), variant: "destructive" });
    } finally {
      setLoadingRunId(null);
    }
  };

  const formatReward = (value: number) => {
    if (Math.abs(value) >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M";
    if (Math.abs(value) >= 1_000) return (value / 1_000).toFixed(0) + "K";
    return value.toFixed(0);
  };

  const totalEpisodesAll = Object.values(combinedStatuses).reduce((sum, s) => sum + (s.total_episodes || 0), 0);
  const currentEpisodesAll = Object.values(combinedStatuses).reduce((sum, s) => sum + (s.current_episode || 0), 0);
  const overallProgressPercent = totalEpisodesAll > 0 ? Math.round((currentEpisodesAll / totalEpisodesAll) * 100) : 0;

  let historyContent: JSX.Element;
  if (loadingHistory) {
    historyContent = (
      <div className="flex items-center justify-center py-6">
        <Loader2 className="w-5 h-5 animate-spin text-primary" />
      </div>
    );
  } else if (pastRuns.length === 0) {
    historyContent = <p className="text-sm text-muted-foreground text-center py-6">No training runs yet</p>;
  } else {
    historyContent = (
      <div className="space-y-2 max-h-[300px] overflow-y-auto pr-1">
        {pastRuns.map((run) => {
          const loadedRun = loadedRuns.find((entry) => entry.id === run.id || entry.sku === run.sku);
          const isLoaded = loadedRun?.id === run.id;
          const isSkuAlreadyLoaded = Boolean(loadedRun && loadedRun.id !== run.id);
          const actionIcon = isLoaded ? <X className="w-3 h-3" /> : <RotateCcw className="w-3 h-3" />;
          let actionLabel = "Add";
          if (isLoaded) actionLabel = "Remove";
          else if (isSkuAlreadyLoaded) actionLabel = "Replace";

          return (
            <div
              key={run.id}
              className="flex items-center justify-between p-3 rounded-lg border border-border/50 bg-muted/20 hover:bg-muted/40 transition-colors"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-bold truncate">{run.sku}</span>
                  <StatusBadge status={run.status} />
                </div>
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-[10px] text-muted-foreground">
                  <span>{run.episodes} ep</span>
                  {run.best_reward != null && <span>Best: {formatReward(run.best_reward)}</span>}
                  {run.evaluation?.rl_vs_oracle_pct != null && (
                    <span className="text-emerald-500 font-medium">
                      {run.evaluation.rl_vs_oracle_pct.toFixed(1)}% of Oracle
                    </span>
                  )}
                  {run.created_at && <span>{new Date(run.created_at).toLocaleDateString()}</span>}
                </div>
              </div>
              {run.status === "success" && run.model_path && (
                <Button
                  variant={isLoaded ? "destructive" : "outline"}
                  size="sm"
                  className="ml-2 gap-1 shrink-0"
                  disabled={loadingRunId === run.id}
                  onClick={() => isLoaded && loadedRun ? handleRemoveLoadedRun(loadedRun) : handleLoadRun(run.id)}
                >
                  {loadingRunId === run.id ? <Loader2 className="w-3 h-3 animate-spin" /> : actionIcon}
                  {actionLabel}
                </Button>
              )}
            </div>
          );
        })}
      </div>
    );
  }

  function renderSkuChart(sku: string) {
    const data = combinedChartData[sku] || [];
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

    const skuStatus = combinedStatuses[sku];
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
    <>
      <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className={cn("flex-1", isCollapsed ? "lg:ml-[112px]" : "lg:ml-[288px]", "flex flex-col")}>
        <Header title="Multi-SKU DQN Training" />
        <div className="px-6 pb-6 pt-2 space-y-4 animate-in fade-in duration-500">
          <StageNav />

          <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 lg:gap-8">
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
                      min={1}
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
                        if (episodes === "" || Number(episodes) < 1) setEpisodes(1);
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
                        Each SKU gets its own independent agent with auto-configured parameters. Adjust these global hyperparameters if needed.
                      </p>
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs">Holding Cost</Label>
                          <Input
                            type="number"
                            min={0.1}
                            step={0.1}
                            value={holdingCost}
                            onChange={(e) => setHoldingCost(e.target.value)}
                            onBlur={() => { if (!holdingCost || Number(holdingCost) <= 0) setHoldingCost(5); }}
                            disabled={isTraining}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">Stockout Penalty</Label>
                          <Input
                            type="number"
                            min={1}
                            step={1}
                            value={stockoutPenalty}
                            onChange={(e) => setStockoutPenalty(e.target.value)}
                            onBlur={() => { if (!stockoutPenalty || Number(stockoutPenalty) <= 0) setStockoutPenalty(200); }}
                            disabled={isTraining}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">Gamma (Discount Factor)</Label>
                          <Input
                            type="number"
                            min={0.1}
                            max={0.999}
                            step={0.01}
                            value={gamma}
                            onChange={(e) => setGamma(e.target.value)}
                            onBlur={() => { if (!gamma || Number(gamma) <= 0 || Number(gamma) >= 1) setGamma(0.98); }}
                            disabled={isTraining}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">Learning Rate</Label>
                          <Input
                            type="number"
                            min={0.00001}
                            max={0.1}
                            step={0.0001}
                            value={learningRate}
                            onChange={(e) => setLearningRate(e.target.value)}
                            onBlur={() => { if (!learningRate || Number(learningRate) <= 0) setLearningRate(0.0001); }}
                            disabled={isTraining}
                          />
                        </div>
                      </div>
                    </CollapsibleContent>
                  </Collapsible>

                  <div className="flex items-center gap-2 pt-2 border-t mt-4">
                    <Switch id="sweep-mode" checked={sweepMode} onCheckedChange={setSweepMode} disabled={isTraining || isSweeping} />
                    <Label htmlFor="sweep-mode">Sensitivity Sweep Mode</Label>
                  </div>
                  
                  {sweepMode && (
                    <div className="space-y-4 p-4 bg-muted/20 border rounded-lg mt-2">
                      <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                          <Label className="text-xs">Parameter to Sweep</Label>
                          <select 
                            className="flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                            value={sweepParam} 
                            onChange={e => setSweepParam(e.target.value)}
                            disabled={isSweeping}
                          >
                            <option value="learning_rate">Learning Rate</option>
                            <option value="gamma">Gamma</option>
                            <option value="holding_cost">Holding Cost</option>
                            <option value="stockout_penalty">Stockout Penalty</option>
                            <option value="episodes">Episodes</option>
                          </select>
                        </div>
                        <div className="space-y-2">
                          <Label className="text-xs">Values (comma-separated)</Label>
                          <Input 
                            value={sweepValuesStr} 
                            onChange={e => setSweepValuesStr(e.target.value)} 
                            disabled={isSweeping}
                            placeholder="e.g. 0.001, 0.01, 0.1"
                          />
                        </div>
                      </div>
                    </div>
                  )}

                  <div className={`grid gap-3 ${isTraining || isSweeping ? 'grid-cols-[1fr_auto]' : 'grid-cols-1'}`}>
                    {sweepMode ? (
                      <Button
                        onClick={handleStartSweep}
                        disabled={isSweeping || isTraining}
                        className="gap-2 h-11 text-sm font-bold shadow-lg shadow-primary/20 w-full bg-indigo-600 hover:bg-indigo-700 text-white"
                      >
                        {isSweeping ? <Loader2 className="w-4 h-4 animate-spin shrink-0" /> : <Brain className="w-4 h-4 shrink-0" />}
                        <span className="truncate">{isSweeping ? "Running Sweep..." : "Run Sweep"}</span>
                      </Button>
                    ) : (
                      <Button
                        onClick={handleStartTraining}
                        disabled={isTraining}
                        className="gap-2 h-11 text-sm font-bold shadow-lg shadow-primary/20 w-full"
                      >
                        {isTraining ? (
                          <Loader2 className="w-4 h-4 animate-spin shrink-0" />
                        ) : (
                          <Brain className="w-4 h-4 shrink-0" />
                        )}
                        <span className="truncate">{isTraining ? "Training All SKUs..." : "Start Multi-SKU Training"}</span>
                      </Button>
                    )}
                    {(isTraining || isSweeping) && (
                      <Button
                        onClick={sweepMode ? handleStopSweep : handleStopTraining}
                        variant="destructive"
                        className="gap-2 h-11 px-4 font-bold shadow-lg shrink-0"
                      >
                        <Square className="w-4 h-4 shrink-0" />
                        Stop
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>

              {/* Overall Progress */}
              {!sweepMode && (isTraining || trainingComplete) && combinedSkuNames.length > 0 && (
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
                      {combinedSkuNames.map((sku) => {
                        const s = combinedStatuses[sku];
                        const pct = s?.total_episodes ? Math.round((s.current_episode / s.total_episodes) * 100) : 0;
                        return (
                          <button
                            key={sku}
                            onClick={() => selectSku(sku)}
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

              {trainingComplete && loadedRuns.length === 0 && (
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
                  {historyContent}
                </CardContent>
              </Card>
            </div>

            {/* Right: Per-SKU Reward Chart & Stats */}
            <div className="col-span-1 xl:col-span-2 space-y-6">
              {sweepMode ? (
                <Card className="border-border/50 shadow-lg bg-card/50 h-[500px] flex flex-col">
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <TrendingUp className="w-4 h-4 text-primary" /> Sensitivity Sweep Results
                    </CardTitle>
                    <CardDescription>Compare service levels across {sweepParam} values</CardDescription>
                  </CardHeader>
                  <CardContent className="flex-1 min-h-0 relative">
                    {sweepResults.length > 0 ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={sweepResults} margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
                          <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                          <XAxis 
                            dataKey={sweepParam} 
                            label={{ value: sweepParam, position: "insideBottomRight", offset: -10 }} 
                          />
                          <YAxis 
                            domain={[0, 100]} 
                            label={{ value: "Service Level %", angle: -90, position: "insideLeft", offset: -10 }} 
                          />
                          <Tooltip 
                            contentStyle={{ backgroundColor: "hsl(var(--card))", borderRadius: 8 }}
                            formatter={(val: number) => [`${val.toFixed(2)}%`, 'Service Level']}
                          />
                          <Legend />
                          <Line 
                            type="monotone" 
                            dataKey="service_level" 
                            name="Service Level %" 
                            stroke="hsl(var(--primary))" 
                            strokeWidth={3} 
                            dot={{ r: 6 }} 
                            activeDot={{ r: 8 }} 
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    ) : (
                      <div className="h-full flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
                        {isSweeping ? (
                          <>
                            <Loader2 className="w-10 h-10 animate-spin text-primary mb-3" />
                            <p className="text-sm font-medium">Running sweep jobs...</p>
                          </>
                        ) : (
                          <>
                            <Activity className="w-10 h-10 mb-3 opacity-10" />
                            <p className="text-sm font-medium">Run sweep to see results</p>
                          </>
                        )}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ) : (
                <>
                  {combinedSkuNames.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {combinedSkuNames.map((sku) => (
                    <Button
                      key={sku}
                      variant={selectedSku === sku ? "default" : "outline"}
                      size="sm"
                      onClick={() => selectSku(sku)}
                      className="gap-2 shrink-0"
                    >
                      <div className={"w-2 h-2 rounded-full shrink-0 " + getSkuStatusDot(combinedStatuses[sku]?.status || "idle")} />
                      <span className="truncate max-w-[150px]">{sku}</span>
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
                    {currentHistoricalRun && `Historical training curve for run #${currentHistoricalRun.id}`}
                    {!currentHistoricalRun && trainingComplete && "Training complete \u2014 select a SKU to view its reward curve"}
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

              {selectedSku && combinedStatuses[selectedSku] && combinedStatuses[selectedSku].status !== "idle" && (
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
                          {combinedStatuses[selectedSku].latest_reward == null ? "\u2014" : formatReward(combinedStatuses[selectedSku].latest_reward)}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Avg (50)</p>
                        <p className="text-lg font-mono font-bold">
                          {combinedStatuses[selectedSku].avg_reward_last_50 == null ? "\u2014" : formatReward(combinedStatuses[selectedSku].avg_reward_last_50)}
                        </p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Best Reward</p>
                        <p className="text-lg font-mono font-bold text-emerald-500">
                          {combinedStatuses[selectedSku].best_reward == null ? "\u2014" : formatReward(combinedStatuses[selectedSku].best_reward)}
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

              {loadedRuns.length > 0 && (
                <Card className="border-border/50 shadow-lg bg-card/50">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-base flex items-center gap-2">
                      <RotateCcw className="w-4 h-4 text-primary" /> Loaded Historical Models
                    </CardTitle>
                    <CardDescription>
                      Add one or more previously trained models, switch between them, and remove them individually.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      {loadedRuns.map((run) => (
                        <div key={run.id} className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 px-3 py-2">
                          <button className="text-left" onClick={() => selectSku(run.sku)}>
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-sm">{run.sku}</span>
                              <StatusBadge status={run.status} />
                            </div>
                            <p className="text-xs text-muted-foreground mt-1">Run #{run.id} • {run.episodes} episodes</p>
                          </button>
                          <Button variant="ghost" size="sm" className="gap-1" onClick={() => handleRemoveLoadedRun(run)}>
                            <X className="w-3 h-3" /> Remove
                          </Button>
                        </div>
                      ))}
                    </div>
                    <Button onClick={() => navigate("/evaluate")} className="w-full gap-2">
                      Evaluate Results <ArrowRight className="w-4 h-4" />
                    </Button>
                  </CardContent>
                </Card>
              )}
                </>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
    <PageCopilot
      page="train"
      title="Training Assistant"
      subtitle={isTraining ? "● Training in progress..." : trainingComplete ? "● Training complete" : "○ Ready"}
      quickActions={[
        "Start training with 500 episodes",
        "What is the current training status?",
        "Explain what the reward curve means",
        "Go to evaluate results",
      ]}
      pageContext={{
        status: isTraining ? "running" : trainingComplete ? "completed" : overallStatusRef.current || "idle",
        current_episode: Object.values(skuStatuses).reduce((s, v) => s + (v.current_episode || 0), 0),
        total_episodes: Object.values(skuStatuses).reduce((s, v) => s + (v.total_episodes || 0), 0),
        best_reward: Object.values(skuStatuses).length > 0
          ? Object.values(skuStatuses).reduce((best, v) =>
              v.best_reward != null && v.best_reward > best ? v.best_reward : best, -Infinity)
          : null,
        avg_reward_last_50: selectedSku ? (skuStatuses[selectedSku]?.avg_reward_last_50 ?? null) : null,
        skus: Object.keys(skuStatuses),
        selected_sku: selectedSku,
        num_episodes: episodes,
        ws_connected: connected,
      }}
      onAction={async (action) => {
        const a = action as Record<string, unknown>;
        if (a.action === "start_training") {
          if (!isTraining) await handleStartTraining();
        } else if (a.action === "stop_training") {
          if (isTraining) await handleStopTraining();
        } else if (a.action === "navigate_to_evaluate") {
          navigate("/evaluate");
        }
      }}
    />
  </>
  );
}
