import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { BarChart3, Trophy, Loader2, TrendingUp, Target, Scale } from "lucide-react";
import { useState } from "react";
import { useToast } from "@/hooks/use-toast";
import { evaluateAgent, getEvaluationGraphBase64 } from "@/lib/api";
import type { EvaluateResponse } from "@/lib/api";

export default function Stage3Deployment() {
  const { toast } = useToast();

  // Evaluation params
  const [horizonDays, setHorizonDays] = useState(90);
  const [initialInventory, setInitialInventory] = useState(500);
  const [serviceLevel, setServiceLevel] = useState(0.95);

  // Results state
  const [evaluating, setEvaluating] = useState(false);
  const [results, setResults] = useState<EvaluateResponse | null>(null);
  const [graphSrc, setGraphSrc] = useState<string | null>(null);

  const handleEvaluate = async () => {
    setEvaluating(true);
    try {
      const res = await evaluateAgent({
        horizon_days: horizonDays,
        initial_inventory: initialInventory,
        service_level_target: serviceLevel,
      });
      setResults(res);
      try {
        const graphData = await getEvaluationGraphBase64();
        setGraphSrc(`data:image/png;base64,${graphData.image_base64}`);
      } catch { }
      toast({ title: "Evaluation Complete", description: res.message });
    } catch (err: any) {
      toast({ title: "Evaluation Failed", description: err.message, variant: "destructive" });
    } finally {
      setEvaluating(false);
    }
  };

  const costSavings = results
    ? (((results.rule_reward - results.rl_reward) / Math.abs(results.rule_reward)) * 100).toFixed(1)
    : null;

  function getBestStrategy(res: EvaluateResponse): string {
    if (res.rl_reward >= res.oracle_reward && res.rl_reward >= res.rule_reward) return "agent";
    if (res.oracle_reward >= res.rule_reward) return "oracle";
    return "rule";
  }

  const bestStrategy = results ? getBestStrategy(results) : null;

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col h-screen overflow-hidden">
        <Header title="Evaluation & Deployment" />

        <div className="flex-1 p-8 space-y-8 overflow-y-auto">
          <StageNav />
          <div className="grid grid-cols-12 gap-8">

            {/* Left Column: Evaluation Config */}
            <div className="col-span-4 space-y-6">
              <Card className="border-border/50 bg-gradient-to-br from-card to-muted/20 shadow-xl">
                <CardHeader>

                  <CardTitle className="text-xl flex items-center gap-2">
                    <Scale className="w-6 h-6 text-primary" />
                    Evaluation Setup
                  </CardTitle>
                  <CardDescription>Compare RL agent vs Oracle & Rule-Based baselines</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <div className="space-y-3">
                    <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Horizon (days)</Label>
                    <Input type="number" value={horizonDays} onChange={(e) => setHorizonDays(Number(e.target.value))} className="font-mono" disabled={evaluating} />
                  </div>
                  <div className="space-y-3">
                    <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Initial Inventory</Label>
                    <Input type="number" value={initialInventory} onChange={(e) => setInitialInventory(Number(e.target.value))} className="font-mono" disabled={evaluating} />
                  </div>
                  <div className="space-y-3">
                    <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Service Level Target</Label>
                    <Input type="number" step="0.01" min="0.5" max="1" value={serviceLevel} onChange={(e) => setServiceLevel(Number(e.target.value))} className="font-mono" disabled={evaluating} />
                  </div>

                  <div className="pt-4 border-t border-border/50">
                    <Button onClick={handleEvaluate} disabled={evaluating} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground h-12 font-bold text-lg shadow-lg shadow-primary/20">
                      {evaluating ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <BarChart3 className="w-5 h-5 mr-2" />}
                      {evaluating ? "Evaluating..." : "Run Evaluation"}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Right Column: Results */}
            <div className="col-span-8 space-y-8">

              {/* Reward Comparison Cards */}
              {results ? (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    <RewardCard label="RL Agent" value={results.rl_reward} color="text-blue-500" best={bestStrategy === "agent"} />
                    <RewardCard label="Oracle (Optimal)" value={results.oracle_reward} color="text-emerald-500" best={bestStrategy === "oracle"} />
                    <RewardCard label="Rule-Based" value={results.rule_reward} color="text-amber-500" best={bestStrategy === "rule"} />
                  </div>

                  {/* RL vs Oracle % */}
                  {results.rl_vs_oracle_pct != null && (
                    <Card className="border-border/50 shadow-lg bg-card/50">
                      <CardContent className="p-6">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <Target className="w-6 h-6 text-primary" />
                            <div>
                              <p className="text-sm font-bold">RL Agent Efficiency</p>
                              <p className="text-xs text-muted-foreground">Percentage of Oracle-optimal performance</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <span className="text-3xl font-display font-bold">{results.rl_vs_oracle_pct.toFixed(1)}%</span>
                            <p className="text-xs text-muted-foreground">of optimal</p>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  )}

                  {/* Evaluation Graph */}
                  {graphSrc && (
                    <Card className="border-border/50 shadow-lg bg-card/50">
                      <CardHeader>

                        <CardTitle>Performance Comparison</CardTitle>
                        <CardDescription>Inventory levels & order quantities: RL vs Oracle vs Rule-Based</CardDescription>
                      </CardHeader>
                      <CardContent>
                        <div className="rounded-xl overflow-hidden border border-border/50 bg-black/20">
                          <img src={graphSrc} alt="Evaluation Comparison" className="w-full h-auto" />
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
                      <p className="text-sm text-muted-foreground mt-1">Train the agent first (Stage 4), then run evaluation</p>
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

function RewardCard({ label, value, color, best }: { label: string; value: number; color: string; best: boolean }) {
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
