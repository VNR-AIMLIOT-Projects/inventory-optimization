import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BarChart3, Trophy, Loader2, TrendingUp, Target, Scale, RotateCcw, History, Rocket } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import { evaluateAgent, getEvaluationGraphBase64, evaluateMultiSku, getMultiSkuEvalGraph, loadTrainingRun, getTrainingRuns } from "@/lib/api";
import type { EvaluateResponse, LoadedTrainingRun, MultiSkuEvalResponse, SkuEvalResult } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import {
  getActiveLoadedHistoricalRunId,
  getLoadedHistoricalRuns,
  saveLoadedHistoricalRuns,
  setActiveLoadedHistoricalRunId as setStoredActiveLoadedHistoricalRunId,
} from "@/lib/loaded-runs";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from "recharts";

export default function Stage3Deployment() {
  const { toast } = useToast();
  const [, navigate] = useLocation();

  const [evaluating, setEvaluating] = useState(false);
  const [loadingCurrentRun, setLoadingCurrentRun] = useState(true);
  const [loadedRuns, setLoadedRuns] = useState<LoadedTrainingRun[]>([]);
  const [activeLoadedRunId, setActiveLoadedRunId] = useState<number | null>(null);
  const [loadedRunResult, setLoadedRunResult] = useState<EvaluateResponse | null>(null);
  const [loadedRunGraph, setLoadedRunGraph] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, SkuEvalResult>>({});
  const [graphSrcs, setGraphSrcs] = useState<Record<string, string>>({});
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [message, setMessage] = useState<string>("");
  const [hasTrainedModel, setHasTrainedModel] = useState(false);
  const [deploying, setDeploying] = useState(false);

  const currentRun = loadedRuns.find((run) => run.id === activeLoadedRunId) ?? null;

  // Check if there's a trained model in the current session
  useEffect(() => {
    async function checkTrainedModel() {
      try {
        const res = await fetch("http://localhost:8000/api/health");
        const data = await res.json();
        setHasTrainedModel(data.agent_trained === true);
      } catch {
        setHasTrainedModel(false);
      }
    }
    checkTrainedModel();
  }, []);

  const skuNames = Object.keys(results).sort((left, right) => left.localeCompare(right));

  const formatReward = (value: number) => {
    if (Math.abs(value) >= 1_000_000) return (value / 1_000_000).toFixed(1) + "M";
    if (Math.abs(value) >= 1_000) return (value / 1_000).toFixed(0) + "K";
    return value.toFixed(0);
  };

  const trainingCurve = (currentRun?.rewards || []).map((reward, index, rewards) => {
    const start = Math.max(0, index - 49);
    const slice = rewards.slice(start, index + 1);
    const avg = slice.reduce((sum, value) => sum + value, 0) / slice.length;
    const best = Math.max(...rewards.slice(0, index + 1));
    return {
      episode: index + 1,
      reward: Math.round(reward),
      avg50: Math.round(avg),
      best: Math.round(best),
    };
  });

  const fetchCurrentRun = useCallback(() => {
    // Use only localStorage as the source of truth.
    // If empty → no loaded historical models → show batch evaluation mode.
    // The backend's "current loaded run" is intentionally NOT consulted here;
    // it would reflect the last explicitly loaded run even after a fresh training.
    const storedRuns = getLoadedHistoricalRuns() as LoadedTrainingRun[];
    if (storedRuns.length > 0) {
      setLoadedRuns(storedRuns);
      const activeId = getActiveLoadedHistoricalRunId();
      setActiveLoadedRunId(activeId ?? storedRuns.at(-1)?.id ?? null);
    } else {
      setLoadedRuns([]);
      setActiveLoadedRunId(null);
    }
    setLoadingCurrentRun(false);
  }, []);

  useEffect(() => {
    fetchCurrentRun();
  }, [fetchCurrentRun]);

  useEffect(() => {
    setLoadedRunGraph(null);
    if (currentRun?.evaluation) {
      setLoadedRunResult({
        rl_reward: currentRun.evaluation.rl_reward,
        oracle_reward: currentRun.evaluation.oracle_reward,
        rule_reward: currentRun.evaluation.rule_reward,
        rl_vs_oracle_pct: currentRun.evaluation.rl_vs_oracle_pct,
        config: currentRun.evaluation.config || {},
        message: `Stored evaluation for run #${currentRun.id}`,
      });
    } else {
      setLoadedRunResult(null);
    }
  }, [currentRun]);

  useEffect(() => {
    if (!selectedSku && skuNames.length > 0) {
      setSelectedSku(skuNames[0]);
    }
  }, [skuNames, selectedSku]);

  const handleEvaluateLoadedRun = async () => {
    if (!currentRun) return;
    setEvaluating(true);
    try {
      await loadTrainingRun(currentRun.id);
      const result = await evaluateAgent();
      setLoadedRunResult(result);
      const graph = await getEvaluationGraphBase64();
      setLoadedRunGraph(`data:image/png;base64,${graph.image_base64}`);
      const nextRuns = loadedRuns.map((run) => run.id === currentRun.id
        ? {
          ...run,
          evaluation: {
            rl_reward: result.rl_reward,
            oracle_reward: result.oracle_reward,
            rule_reward: result.rule_reward,
            rl_vs_oracle_pct: result.rl_vs_oracle_pct,
            config: result.config,
          },
        }
        : run);
      setLoadedRuns(nextRuns);
      saveLoadedHistoricalRuns(nextRuns);
      toast({ title: "Loaded Model Evaluated", description: result.message });
    } catch (err: any) {
      toast({ title: "Evaluation Failed", description: friendlyError(err, "evaluation"), variant: "destructive" });
    } finally {
      setEvaluating(false);
    }
  };

  const handleSelectLoadedRun = useCallback(async (run: LoadedTrainingRun) => {
    setStoredActiveLoadedHistoricalRunId(run.id);
    setActiveLoadedRunId(run.id);
    try {
      await loadTrainingRun(run.id);
    } catch {
      // Ignore activation failures here; explicit evaluation will surface errors.
    }
  }, []);

  const handleEvaluateBatch = async () => {
    setEvaluating(true);
    try {
      const res: MultiSkuEvalResponse = await evaluateMultiSku();
      setResults(res.skus);
      setMessage(res.message);

      // Fetch graphs for all SKUs in parallel
      const graphPromises = Object.keys(res.skus).map(async (sku) => {
        try {
          const g = await getMultiSkuEvalGraph(sku);
          return { sku, src: `data:image/png;base64,${g.image_base64}` };
        } catch {
          return null;
        }
      });
      const graphResults = await Promise.all(graphPromises);
      const srcs: Record<string, string> = {};
      for (const g of graphResults) {
        if (g) srcs[g.sku] = g.src;
      }
      setGraphSrcs(srcs);

      toast({ title: "Evaluation Loaded", description: res.message });
    } catch (err: any) {
      toast({ title: "Evaluation Failed", description: err.message, variant: "destructive" });
    } finally {
      setEvaluating(false);
    }
  };

  function getBestStrategy(r: SkuEvalResult): string {
    if (r.rl_reward >= r.oracle_reward && r.rl_reward >= r.rule_reward) return "agent";
    if (r.oracle_reward >= r.rule_reward) return "oracle";
    return "rule";
  }

  const currentResult = selectedSku ? results[selectedSku] : null;
  const currentGraph = selectedSku ? graphSrcs[selectedSku] : null;
  const bestStrategy = currentResult ? getBestStrategy(currentResult) : null;

  const loadedRunBestStrategy = loadedRunResult ? getLoadedRunBestStrategy(loadedRunResult) : null;

  let content;
  if (loadingCurrentRun) {
    content = (
      <Card className="border-border/50 shadow-lg bg-card/50">
        <CardContent className="py-10 flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </CardContent>
      </Card>
    );
  } else if (currentRun) {
    content = (
      <div className="space-y-8">
        {loadedRuns.length > 1 && (
          <div className="flex gap-2 flex-wrap">
            {loadedRuns.map((run) => (
              <Button
                key={run.id}
                variant={currentRun.id === run.id ? "default" : "outline"}
                size="sm"
                onClick={() => handleSelectLoadedRun(run)}
              >
                {run.sku}
              </Button>
            ))}
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <Card className="border-border/50 bg-gradient-to-br from-card to-muted/20 shadow-xl lg:col-span-1">
            <CardHeader>
              <CardTitle className="text-xl flex items-center gap-2">
                <RotateCcw className="w-5 h-5 text-primary" />
                Loaded Historical Model{loadedRuns.length > 1 ? "s" : ""}
              </CardTitle>
              <CardDescription>
                Review run #{currentRun.id} and continue evaluation for {currentRun.sku}. {loadedRuns.length > 1 ? `You currently have ${loadedRuns.length} historical models selected.` : ""}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="grid grid-cols-2 gap-3">
                <MetricTile label="SKU" value={currentRun.sku} />
                <MetricTile label="Episodes" value={String(currentRun.episodes)} />
                <MetricTile label="Best Reward" value={currentRun.best_reward == null ? "\u2014" : formatReward(currentRun.best_reward)} />
                <MetricTile label="Status" value={currentRun.status} />
              </div>
              <div className="flex items-center justify-between rounded-lg border border-border/50 bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
                <span>Stored metrics</span>
                {currentRun.evaluation ? (
                  <Badge variant="outline" className="text-emerald-500 border-emerald-500/30">Available</Badge>
                ) : (
                  <Badge variant="outline">Not yet saved</Badge>
                )}
              </div>
              <Button onClick={handleEvaluateLoadedRun} disabled={evaluating} className="w-full gap-2 h-12 text-lg font-bold shadow-lg shadow-primary/20">
                {evaluating ? <Loader2 className="w-5 h-5 animate-spin" /> : <BarChart3 className="w-5 h-5" />}
                {currentRun.evaluation ? "Refresh Evaluation" : "Evaluate Loaded Model"}
              </Button>
              <p className="text-xs text-muted-foreground">
                Stored metrics appear immediately. Run evaluation again to regenerate the comparison graph with the restored demand context.
              </p>
            </CardContent>
          </Card>

          <div className="lg:col-span-2 space-y-6">
            {loadedRunResult ? (
              <>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                  <RewardCard label="RL Agent" value={loadedRunResult.rl_reward} color="text-blue-500" best={loadedRunBestStrategy === "agent"} />
                  <RewardCard label="Oracle (Optimal)" value={loadedRunResult.oracle_reward} color="text-emerald-500" best={loadedRunBestStrategy === "oracle"} />
                  <RewardCard label="Rule-Based" value={loadedRunResult.rule_reward} color="text-amber-500" best={loadedRunBestStrategy === "rule"} />
                </div>

                {loadedRunResult.rl_vs_oracle_pct != null && (
                  <Card className="border-border/50 shadow-lg bg-card/50">
                    <CardContent className="p-6 flex items-center justify-between gap-6">
                      <div className="flex items-center gap-3">
                        <Target className="w-6 h-6 text-primary" />
                        <div>
                          <p className="text-sm font-bold">Loaded model efficiency</p>
                          <p className="text-xs text-muted-foreground">Current loaded run vs Oracle baseline</p>
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-3xl font-display font-bold">{loadedRunResult.rl_vs_oracle_pct.toFixed(1)}%</span>
                        <p className="text-xs text-muted-foreground">of optimal</p>
                      </div>
                    </CardContent>
                  </Card>
                )}
              </>
            ) : (
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardContent className="h-[220px] flex flex-col items-center justify-center text-muted-foreground">
                  <Target className="w-12 h-12 mb-4 opacity-10" />
                  <p className="text-lg font-medium">No evaluation loaded yet</p>
                  <p className="text-sm mt-1">Use the button on the left to evaluate the loaded historical model.</p>
                </CardContent>
              </Card>
            )}

            {loadedRunGraph && (
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <CardTitle>Evaluation Comparison — {currentRun.sku}</CardTitle>
                  <CardDescription>RL vs Oracle vs Rule-Based for the loaded run</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="rounded-xl overflow-hidden border border-border/50 bg-black/20">
                    <img src={loadedRunGraph} alt={`Evaluation ${currentRun.sku}`} className="w-full h-auto" />
                  </div>
                </CardContent>
              </Card>
            )}



            <Card className="border-border/50 shadow-lg bg-card/50">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <History className="w-5 h-5 text-primary" /> Training Curve — {currentRun.sku}
                </CardTitle>
                <CardDescription>
                  Historical reward trajectory for run #{currentRun.id}.
                </CardDescription>
              </CardHeader>
              <CardContent>
                {trainingCurve.length > 0 ? (
                  <ResponsiveContainer width="100%" height={360}>
                    <LineChart data={trainingCurve} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" opacity={0.15} />
                      <XAxis dataKey="episode" tick={{ fontSize: 11 }} />
                      <YAxis tickFormatter={formatReward} tick={{ fontSize: 11 }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8, fontSize: 12 }}
                        formatter={(value: number, name: string) => [formatReward(value), name]}
                        labelFormatter={(episode: number) => `Episode ${episode}`}
                      />
                      <ReferenceLine y={0} stroke="hsl(var(--muted-foreground))" strokeDasharray="3 3" />
                      <Line type="monotone" dataKey="reward" name="Episode Reward" stroke="hsl(var(--primary))" dot={false} strokeWidth={1.5} isAnimationActive={false} />
                      <Line type="monotone" dataKey="avg50" name="Avg (Last 50)" stroke="#f97316" dot={false} strokeWidth={2} isAnimationActive={false} />
                      <Line type="monotone" dataKey="best" name="Best So Far" stroke="#22c55e" dot={false} strokeWidth={2} strokeDasharray="6 3" isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[240px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
                    <TrendingUp className="w-10 h-10 mb-3 opacity-10" />
                    <p className="text-sm font-medium">No reward history stored for this run</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    );
  } else {
    content = (
      <div className="grid grid-cols-12 gap-8">
      <div className="col-span-4 space-y-6">
        <Card className="border-border/50 bg-gradient-to-br from-card to-muted/20 shadow-xl">
          <CardHeader>
            <CardTitle className="text-xl flex items-center gap-2">
              <Scale className="w-6 h-6 text-primary" />
              Evaluation
            </CardTitle>
            <CardDescription>Compare RL agent vs Oracle & Rule-Based for each SKU</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <p className="text-xs text-muted-foreground">
              Results are computed during training. Click below to load the comparison for all trained SKUs.
            </p>
            <Button onClick={handleEvaluateBatch} disabled={evaluating} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground h-12 font-bold text-lg shadow-lg shadow-primary/20">
              {evaluating ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <BarChart3 className="w-5 h-5 mr-2" />}
              {evaluating ? "Loading..." : "Load Evaluation Results"}
            </Button>
          </CardContent>
        </Card>

        {skuNames.length > 0 && (
          <Card className="border-border/50 shadow-lg bg-card/50">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">SKUs ({skuNames.length})</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {skuNames.map((sku) => {
                const r = results[sku];
                const best = getBestStrategy(r);
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
                      <span className="text-sm font-bold">{sku}</span>
                      {best === "agent" && <Badge variant="outline" className="text-[10px] text-emerald-500 border-emerald-500/30">Best</Badge>}
                    </div>
                    <div className="flex justify-between text-[10px] text-muted-foreground">
                      <span>RL: {r.rl_reward.toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                      <span>{r.rl_vs_oracle_pct == null ? "" : `${r.rl_vs_oracle_pct.toFixed(1)}% of Oracle`}</span>
                    </div>
                  </button>
                );
              })}
            </CardContent>
          </Card>
        )}
      </div>

      <div className="col-span-8 space-y-8">
        {skuNames.length > 0 && (
          <div className="flex gap-2 flex-wrap">
            {skuNames.map((sku) => (
              <Button
                key={sku}
                variant={selectedSku === sku ? "default" : "outline"}
                size="sm"
                onClick={() => setSelectedSku(sku)}
              >
                {sku}
              </Button>
            ))}
          </div>
        )}

        {currentResult ? (
          <>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <RewardCard label="RL Agent" value={currentResult.rl_reward} color="text-blue-500" best={bestStrategy === "agent"} />
              <RewardCard label="Oracle (Optimal)" value={currentResult.oracle_reward} color="text-emerald-500" best={bestStrategy === "oracle"} />
              <RewardCard label="Rule-Based" value={currentResult.rule_reward} color="text-amber-500" best={bestStrategy === "rule"} />
            </div>

            {currentResult.rl_vs_oracle_pct != null && (
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardContent className="p-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <Target className="w-6 h-6 text-primary" />
                      <div>
                        <p className="text-sm font-bold">RL Agent Efficiency — {selectedSku}</p>
                        <p className="text-xs text-muted-foreground">Percentage of Oracle-optimal performance</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-3xl font-display font-bold">{currentResult.rl_vs_oracle_pct.toFixed(1)}%</span>
                      <p className="text-xs text-muted-foreground">of optimal</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {currentGraph && (
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <CardTitle>Performance Comparison — {selectedSku}</CardTitle>
                  <CardDescription>Inventory levels & order quantities: RL vs Oracle vs Rule-Based</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="rounded-xl overflow-hidden border border-border/50 bg-black/20">
                    <img src={currentGraph} alt={`Evaluation ${selectedSku}`} className="w-full h-auto" />
                  </div>
                </CardContent>
              </Card>
            )}
          </>
        ) : (
          <Card className="border-border/50 shadow-lg bg-card/50">
            <CardContent className="p-0">
              <div className="h-[500px] flex flex-col items-center justify-center text-muted-foreground">
                <TrendingUp className="w-16 h-16 mb-6 opacity-10" />
                <p className="text-lg font-medium">No evaluation results yet</p>
                <p className="text-sm text-muted-foreground mt-1">
                  Train all SKUs first (Stage 4), then click "Load Evaluation Results"
                </p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 lg:ml-[320px] flex flex-col h-screen overflow-hidden">
        <Header title={currentRun ? "Loaded Model Evaluation" : "Multi-SKU Evaluation"} />

        <div className="flex-1 px-6 pb-6 pt-2 space-y-4 overflow-y-auto">
          <StageNav />

          {content}

          {/* Deploy Button - Show whenever there's a trained model or eval results loaded */}
          {(currentRun || hasTrainedModel || skuNames.length > 0) && (
            <Card className="border-green-500/30 shadow-lg bg-gradient-to-r from-green-500/5 to-transparent">
              <CardContent className="p-6 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="p-3 rounded-lg bg-green-500/10">
                    <Rocket className="w-6 h-6 text-green-500" />
                  </div>
                  <div>
                    <p className="font-semibold">Ready to Deploy</p>
                    <p className="text-sm text-muted-foreground">
                      Launch an interactive simulation with human-in-the-loop overrides
                    </p>
                  </div>
                </div>
                <Button 
                  disabled={deploying}
                  onClick={async () => {
                    setDeploying(true);
                    try {
                      // If we have a loaded run, load it first
                      if (currentRun) {
                        await loadTrainingRun(currentRun.id);
                      } else {
                        // Batch mode: find run matching selected SKU or first completed
                        const allRuns = await getTrainingRuns();
                        const targetSku = selectedSku || skuNames[0];
                        const matchingRun = allRuns.find(r => (r.status === "completed" || r.status === "success") && r.model_path && r.sku === targetSku)
                          || allRuns.find(r => (r.status === "completed" || r.status === "success") && r.model_path);
                        if (matchingRun) {
                          await loadTrainingRun(matchingRun.id);
                        } else {
                          toast({ title: "No completed run found", description: "Train a model first.", variant: "destructive" });
                          setDeploying(false);
                          return;
                        }
                      }
                      navigate("/deploy");
                    } catch (err: any) {
                      toast({ title: "Deployment Setup Failed", description: friendlyError(err, "deployment"), variant: "destructive" });
                    } finally {
                      setDeploying(false);
                    }
                  }}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {deploying ? (
                    <><Loader2 className="w-4 h-4 mr-2 animate-spin" /> Loading...</>
                  ) : (
                    <><Rocket className="w-4 h-4 mr-2" /> Deploy Agent</>
                  )}
                </Button>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  );
}

function MetricTile({ label, value }: Readonly<{ label: string; value: string }>) {
  return (
    <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
      <p className="text-[10px] uppercase text-muted-foreground mb-1">{label}</p>
      <p className="font-semibold truncate">{value}</p>
    </div>
  );
}

function RewardCard({ label, value, color, best }: Readonly<{ label: string; value: number; color: string; best: boolean }>) {
  return (
    <Card className={`border-border/50 shadow-lg ${best ? "ring-1 ring-emerald-500/30 bg-emerald-500/5" : "bg-card/50"}`}>
      <CardContent className="p-6">
        <div className="flex justify-between items-start">
          <div>
            <p className={`text-[10px] font-bold uppercase tracking-widest mb-1 ${color}`}>{label}</p>
            <h3 className="text-2xl font-bold font-display">{value.toLocaleString(undefined, { maximumFractionDigits: 0 })}</h3>
            <span className="text-[10px] text-muted-foreground">total reward</span>
          </div>
          {best && (
            <div className="p-2 rounded-lg bg-emerald-500/10">
              <Trophy className="w-5 h-5 text-emerald-500" />
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function getLoadedRunBestStrategy(result: EvaluateResponse): string {
  if (result.rl_reward >= result.oracle_reward && result.rl_reward >= result.rule_reward) return "agent";
  if (result.oracle_reward >= result.rule_reward) return "oracle";
  return "rule";
}
