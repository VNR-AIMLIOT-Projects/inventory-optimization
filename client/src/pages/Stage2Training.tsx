import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Brain, Settings2, TrendingUp, Loader2, ImageIcon, ArrowRight, ChevronDown, Activity } from "lucide-react";
import { useState, useEffect, useRef, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import { startTraining as apiStartTraining, getTrainingStatus, getRewardCurveBase64 } from "@/lib/api";
import type { TrainStatus } from "@/lib/api";

export default function Stage2Training() {
  const { toast } = useToast();
  const [, navigate] = useLocation();

  // Training params
  const [episodes, setEpisodes] = useState(300);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // Training state
  const [isTraining, setIsTraining] = useState(false);
  const [status, setStatus] = useState<TrainStatus | null>(null);
  const [trainingComplete, setTrainingComplete] = useState(false);
  const [rewardCurveSrc, setRewardCurveSrc] = useState<string | null>(null);
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Check initial status on mount
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
          } catch {}
        }
      } catch {}
    })();
    return () => {
      if (pollingRef.current) clearInterval(pollingRef.current);
    };
  }, []);

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
          } catch {}
          toast({ title: "Training Complete", description: `Finished ${s.total_episodes} episodes. Avg reward: ${s.avg_reward_last_50?.toFixed(1)}` });
        } else if (s.status === "failed") {
          clearInterval(pollingRef.current!);
          pollingRef.current = null;
          setIsTraining(false);
          toast({ title: "Training Failed", description: "An error occurred during training", variant: "destructive" });
        }
      } catch {}
    }, 2500);
  }, [toast]);

  const handleStartTraining = async () => {
    setIsTraining(true);
    setTrainingComplete(false);
    setStatus(null);
    try {
      await apiStartTraining({
        episodes,
      });
      toast({ title: "Training Started", description: `Running ${episodes} episodes...` });
      startPolling();
    } catch (err: any) {
      setIsTraining(false);
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  function getStatusDotClass() {
    if (status?.status === "running") return "bg-blue-400 animate-pulse";
    if (status?.status === "completed") return "bg-emerald-400";
    if (status?.status === "failed") return "bg-red-400";
    return "bg-muted-foreground";
  }

  function getDescriptionText() {
    if (trainingComplete) return "Training complete — reward vs episode curve";
    if (isTraining) return "Training in progress — curve will appear on completion";
    return "Start training to see the reward curve";
  }

  function renderRewardCurveContent() {
    if (trainingComplete && rewardCurveSrc) {
      return (
        <img
          src={rewardCurveSrc}
          alt="Reward Curve"
          className="w-full rounded-lg border border-border/50"
        />
      );
    }
    if (isTraining) {
      return (
        <div className="h-[500px] flex flex-col items-center justify-center text-muted-foreground">
          <Loader2 className="w-12 h-12 animate-spin text-primary mb-4" />
          <p className="text-sm font-medium">Training in progress...</p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            Episode {status?.current_episode || 0} of {status?.total_episodes || episodes}
          </p>
        </div>
      );
    }
    return (
      <div className="h-[500px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
        <ImageIcon className="w-12 h-12 mb-4 opacity-10" />
        <p className="text-sm font-medium">No training data yet</p>
        <p className="text-xs text-muted-foreground/70 mt-1">Configure parameters and click "Start Training"</p>
      </div>
    );
  }

  const progressPercent = status?.current_episode && status?.total_episodes
    ? Math.round((status.current_episode / status.total_episodes) * 100)
    : 0;

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Step 4: Train DQN Agent" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left: Training Controls */}
            <div className="col-span-1 space-y-6">
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className="bg-primary/20 text-primary border-primary/20">Step 4</Badge>
                  </div>
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
                      onChange={(e) => setEpisodes(Number.parseInt(e.target.value) || 300)}
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

                  <Button
                    onClick={handleStartTraining}
                    disabled={isTraining}
                    className="w-full gap-2 h-12 text-lg font-bold shadow-lg shadow-primary/20"
                  >
                    {isTraining ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Brain className="w-5 h-5" />
                    )}
                    {isTraining ? "Training in Progress..." : "Start Training"}
                  </Button>
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
                    {/* Progress bar */}
                    <div className="space-y-2">
                      <div className="flex justify-between text-xs font-mono">
                        <span>Episode {status.current_episode || 0} / {status.total_episodes || episodes}</span>
                        <span>{progressPercent}%</span>
                      </div>
                      <Progress value={progressPercent} className="h-2" />
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Last Reward</p>
                        <p className="text-lg font-mono font-bold">{status.latest_reward?.toFixed(1) ?? "—"}</p>
                      </div>
                      <div className="p-3 rounded-lg bg-muted/30 border border-border/50">
                        <p className="text-[10px] font-bold text-muted-foreground uppercase mb-1">Avg (50)</p>
                        <p className="text-lg font-mono font-bold">{status.avg_reward_last_50?.toFixed(1) ?? "—"}</p>
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
                </CardTitle>
                <CardDescription>
                  {getDescriptionText()}
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
