import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Brain, Settings2, TrendingUp, Loader2, ImageIcon, ArrowRight, ChevronDown, Activity, Wifi, WifiOff, Square } from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import { startTraining as apiStartTraining, stopTraining as apiStopTraining, getTrainingStatus, getRewardCurveBase64 } from "@/lib/api";
import type { TrainStatus } from "@/lib/api";
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

export default function Stage2Training() {
  const { toast } = useToast();
  const [, navigate] = useLocation();

  // Training params
  const [episodes, setEpisodes] = useState<number | string>(300);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // Training state
  const [isTraining, setIsTraining] = useState(false);
  const [status, setStatus] = useState<TrainStatus | null>(null);
  const [trainingComplete, setTrainingComplete] = useState(false);
  const [rewardCurveSrc, setRewardCurveSrc] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Live chart data
  const [chartData, setChartData] = useState<ChartPoint[]>([]);
  const [liveEpisode, setLiveEpisode] = useState<EpisodeData | null>(null);

  // WebSocket
  const onEpisode = useCallback((data: EpisodeData) => {
    setLiveEpisode(data);
    setStatus((prev) => ({
      status: "running",
      current_episode: data.episode,
      total_episodes: data.total_episodes,
      best_reward: data.best_reward,
      latest_reward: data.reward,
      avg_reward_last_50: data.avg_reward_last_50,
      message: prev?.message ?? "Training in progress...",
    }));
    setChartData((prev) => [
      ...prev,
      {
        episode: data.episode,
        reward: Math.round(data.reward),
        avg50: Math.round(data.avg_reward_last_50),
        bestEval: Math.round(data.best_eval_reward),
      },
    ]);
  }, []);

  const onStatusChange = useCallback((data: TrainingWsStatus) => {
    if (data.status === "completed") {
      setIsTraining(false);
      setTrainingComplete(true);
      setStatus((prev) => ({
        ...prev!,
        status: "completed",
        message: data.message ?? "Training complete",
        best_reward: data.best_reward ?? prev?.best_reward ?? 0,
        avg_reward_last_50: data.avg_reward_last_50 ?? prev?.avg_reward_last_50 ?? 0,
      }));
      toast({
        title: "Training Complete",
        description: data.message ?? "Training finished successfully.",
      });
      // Also fetch the server-side reward curve image
      getRewardCurveBase64()
        .then((graphData) => setRewardCurveSrc(`data:image/png;base64,${graphData.image_base64}`))
        .catch(() => {});
    } else if (data.status === "stopped") {
      setIsTraining(false);
      setTrainingComplete(true);
      setStatus((prev) => ({
        ...prev!,
        status: "stopped",
        message: data.message ?? "Training stopped by user",
      }));
      toast({ title: "Training Stopped", description: data.message ?? "Training was stopped early." });
      getRewardCurveBase64()
        .then((graphData) => setRewardCurveSrc(`data:image/png;base64,${graphData.image_base64}`))
        .catch(() => {});
    } else if (data.status === "failed") {
      setIsTraining(false);
      setStatus((prev) => ({
        ...prev!,
        status: "failed",
        message: data.message ?? "Training failed",
      }));
      toast({
        title: "Training Failed",
        description: data.message ?? "An error occurred during training",
        variant: "destructive",
      });
    }
  }, [toast]);

  const { connected } = useTrainingWs(isTraining, { onEpisode, onStatusChange });

  // Check initial status on mount (handles page refresh during training)
  useEffect(() => {
    (async () => {
      try {
        const s = await getTrainingStatus();
        setStatus(s);
        if (s.status === "running") {
          setIsTraining(true);
          startPolling();
        } else if (s.status === "completed") {
          setTrainingComplete(true);
          try {
            const graphData = await getRewardCurveBase64();
            setRewardCurveSrc(`data:image/png;base64,${graphData.image_base64}`);
          } catch { }
        }
      } catch { }
    })();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

  // Fallback polling — only when WS is not connected
  const startPolling = useCallback(() => {
    if (pollingRef.current) clearInterval(pollingRef.current);
    pollingRef.current = setInterval(async () => {
      try {
        const s = await getTrainingStatus();
        setStatus(s);
        if (s.status === "completed") {
          clearInterval(pollingRef.current!);
          pollingRef.current = null;
          setIsTraining(false);
          setTrainingComplete(true);
          try {
            const graphData = await getRewardCurveBase64();
            setRewardCurveSrc(`data:image/png;base64,${graphData.image_base64}`);
          } catch { }
          toast({ title: "Training Complete", description: `Finished ${s.total_episodes} episodes. Avg reward: ${s.avg_reward_last_50?.toFixed(1)}` });
        } else if (s.status === "stopped") {
          clearInterval(pollingRef.current!);
          pollingRef.current = null;
          setIsTraining(false);
          setTrainingComplete(true);
          toast({ title: "Training Stopped", description: s.message || "Training was stopped early." });
          try {
            const graphData = await getRewardCurveBase64();
            setRewardCurveSrc(`data:image/png;base64,${graphData.image_base64}`);
          } catch { }
        } else if (s.status === "failed") {
          clearInterval(pollingRef.current!);
          pollingRef.current = null;
          setIsTraining(false);
          toast({ title: "Training Failed", description: s.message || "An error occurred during training", variant: "destructive" });
        }
      } catch { }
    }, 2500);
  }, [toast]);

  // Stop polling when WS connects
  useEffect(() => {
    if (connected && pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, [connected]);

  const handleStartTraining = async () => {
    setIsTraining(true);
    setTrainingComplete(false);
    setStatus(null);
    setChartData([]);
    setLiveEpisode(null);
    setRewardCurveSrc(null);
    try {
      const numEpisodes = Number(episodes) || 300;
      await apiStartTraining({ episodes: numEpisodes });
      toast({ title: "Training Started", description: `Running ${numEpisodes} episodes...` });
      // Start fallback polling in case WS doesn't connect
      startPolling();
    } catch (err: any) {
      setIsTraining(false);
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  const handleStopTraining = async () => {
    try {
      await apiStopTraining();
      toast({ title: "Stopping...", description: "Training will stop after the current episode." });
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  function getStatusDotClass() {
    if (status?.status === "running") return "bg-blue-400 animate-pulse";
    if (status?.status === "completed") return "bg-emerald-400";
    if (status?.status === "stopped") return "bg-yellow-400";
    if (status?.status === "failed") return "bg-red-400";
    return "bg-muted-foreground";
  }

  const progressPercent = status?.current_episode && status?.total_episodes
    ? Math.round((status.current_episode / status.total_episodes) * 100)
    : 0;

  // Format large numbers for chart axis
  const formatReward = (value: number) => {
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(0)}K`;
    return value.toFixed(0);
  };

  function renderRewardCurveContent() {
    // Live chart while training (or after if we have data)
    if (chartData.length > 0) {
      return (
        <div className="space-y-4">
          <ResponsiveContainer width="100%" height={460}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
              <XAxis
                dataKey="episode"
                tick={{ fontSize: 11 }}
                label={{ value: "Episode", position: "insideBottomRight", offset: -5, fontSize: 12 }}
              />
              <YAxis
                tickFormatter={formatReward}
                tick={{ fontSize: 11 }}
                label={{ value: "Reward", angle: -90, position: "insideLeft", fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                formatter={(value: number, name: string) => [formatReward(value), name]}
                labelFormatter={(ep) => `Episode ${ep}`}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="reward"
                name="Episode Reward"
                stroke="hsl(var(--primary))"
                dot={false}
                strokeWidth={1}
                opacity={0.4}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="avg50"
                name="Avg (Last 50)"
                stroke="#f97316"
                dot={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey="bestEval"
                name="Best Eval"
                stroke="#22c55e"
                dot={false}
                strokeWidth={2}
                strokeDasharray="6 3"
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>

          {/* Epsilon indicator */}
          {liveEpisode && (
            <div className="flex items-center justify-between text-xs text-muted-foreground px-2">
              <span>Exploration (ε): <span className="font-mono font-bold text-foreground">{liveEpisode.epsilon.toFixed(4)}</span></span>
              <span>Best Eval Reward: <span className="font-mono font-bold text-emerald-500">{formatReward(liveEpisode.best_eval_reward)}</span></span>
            </div>
          )}
        </div>
      );
    }

    // Completed with server-side image but no live data (e.g. page refresh after completion)
    if (trainingComplete && rewardCurveSrc) {
      return (
        <img
          src={rewardCurveSrc}
          alt="Reward Curve"
          className="w-full rounded-lg border border-border/50"
        />
      );
    }

    // Training in progress but WS hasn't sent data yet
    if (isTraining) {
      return (
        <div className="h-[500px] flex flex-col items-center justify-center text-muted-foreground">
          <Loader2 className="w-12 h-12 animate-spin text-primary mb-4" />
          <p className="text-sm font-medium">Connecting to training stream...</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            Episode {status?.current_episode || 0} of {status?.total_episodes || Number(episodes) || 300}
          </p>
        </div>
      );
    }

    // Idle — no training yet
    return (
      <div className="h-[500px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
        <ImageIcon className="w-12 h-12 mb-4 opacity-10" />
        <p className="text-sm font-medium">No training data yet</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Configure parameters and click &quot;Start Training&quot;</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Train DQN Agent" />
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
                  <CardDescription>Configure and start DQN agent training</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-2">
                    <Label className="text-xs">Episodes</Label>
                    <Input
                      type="number"
                      min={10}
                      max={5000}
                      value={episodes}
                      onChange={(e) => {
                        const raw = e.target.value;
                        if (raw === "") {
                          setEpisodes("");
                        } else {
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
                        <ChevronDown className={`w-4 h-4 transition-transform ${advancedOpen ? "rotate-180" : ""}`} />
                      </Button>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="space-y-4 pt-4">
                      <p className="text-xs text-muted-foreground">
                        Max order quantity and season type are auto-configured by the API based on your loaded demand data.
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
                      {isTraining ? "Training in Progress..." : "Start Training"}
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

              {/* Live Stats */}
              {(isTraining || trainingComplete) && status && status.status !== "idle" && (
                <Card className="border-border/50 shadow-lg bg-card/50">
                  <CardHeader className="pb-3">
                    <CardTitle className="flex items-center gap-2 text-base">
                      <Activity className="w-4 h-4 text-primary" /> Live Stats
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Connection indicator */}
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

                    {/* Progress bar */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs font-mono">
                        <span>Episode {status.current_episode || 0} / {status.total_episodes || Number(episodes) || 300}</span>
                        <span>{progressPercent}%</span>
                      </div>
                      <Progress value={progressPercent} className="h-2" />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Last Reward</p>
                        <p className="text-lg font-mono font-bold">{status.latest_reward !== null && status.latest_reward !== undefined ? formatReward(status.latest_reward) : "—"}</p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Avg (50)</p>
                        <p className="text-lg font-mono font-bold">{status.avg_reward_last_50 !== null && status.avg_reward_last_50 !== undefined ? formatReward(status.avg_reward_last_50) : "—"}</p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Best Reward</p>
                        <p className="text-lg font-mono font-bold text-emerald-500">{status.best_reward !== null && status.best_reward !== undefined ? formatReward(status.best_reward) : "—"}</p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Epsilon</p>
                        <p className="text-lg font-mono font-bold">{liveEpisode?.epsilon?.toFixed(4) ?? "—"}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <div className={`w-2 h-2 rounded-full ${getStatusDotClass()}`} />
                      <span className="text-xs font-medium capitalize">{status.status}</span>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Navigation */}
              {trainingComplete && (
                <Button onClick={() => navigate("/evaluate")} className="w-full gap-2">
                  Next: Evaluate Results <ArrowRight className="w-4 h-4" />
                </Button>
              )}
            </div>

            {/* Right: Reward Curve */}
            <Card className="col-span-1 lg:col-span-2 border-border/50 shadow-lg bg-card/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="w-5 h-5 text-primary" /> Reward Curve
                  {isTraining && connected && (
                    <span className="ml-auto flex items-center gap-1 text-xs font-normal text-emerald-500">
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" /> LIVE
                    </span>
                  )}
                </CardTitle>
                <CardDescription>
                  {trainingComplete && "Training complete — reward vs episode curve"}
                  {!trainingComplete && isTraining && "Live training progress — rewards streamed via WebSocket"}
                  {!trainingComplete && !isTraining && "Start training to see the reward curve"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {renderRewardCurveContent()}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
