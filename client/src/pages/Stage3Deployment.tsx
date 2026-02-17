import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { BarChart3, Trophy, Loader2 } from "lucide-react";
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
      } catch {}
      toast({ title: "Evaluation Complete", description: "Results are ready" });
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
    // Higher reward is better (rewards are typically negative costs)
    if (res.rl_reward >= res.oracle_reward && res.rl_reward >= res.rule_reward) return "agent";
    if (res.oracle_reward >= res.rule_reward) return "oracle";
    return "rule";
  }

  const bestStrategy = results ? getBestStrategy(results) : null;

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Step 5: Evaluate & Compare" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left: Evaluation Controls */}
            <Card className="col-span-1 border-border/50 shadow-lg bg-card/50">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <Badge className="bg-primary/20 text-primary border-primary/20">Step 5</Badge>
                </div>
                <CardTitle className="flex items-center gap-2">
                  <BarChart3 className="w-5 h-5 text-primary" /> Evaluation Settings
                </CardTitle>
                <CardDescription>Compare agent vs oracle vs rule-based policy</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-2">
                  <Label className="text-xs">Horizon (Days)</Label>
                  <Input
                    type="number"
                    min={7}
                    max={365}
                    value={horizonDays}
                    onChange={(e) => setHorizonDays(Number.parseInt(e.target.value) || 90)}
                    disabled={evaluating}
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Initial Inventory</Label>
                  <Input
                    type="number"
                    min={0}
                    value={initialInventory}
                    onChange={(e) => setInitialInventory(Number.parseInt(e.target.value) || 500)}
                    disabled={evaluating}
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-xs">Service Level Target</Label>
                  <Input
                    type="number"
                    step={0.01}
                    min={0.5}
                    max={1}
                    value={serviceLevel}
                    onChange={(e) => setServiceLevel(Number.parseFloat(e.target.value) || 0.95)}
                    disabled={evaluating}
                  />
                </div>

                <Button
                  onClick={handleEvaluate}
                  disabled={evaluating}
                  className="w-full gap-2 h-12 text-lg font-bold shadow-lg shadow-primary/20"
                >
                  {evaluating ? <Loader2 className="w-5 h-5 animate-spin" /> : <BarChart3 className="w-5 h-5" />}
                  {evaluating ? "Evaluating..." : "Run Evaluation"}
                </Button>
              </CardContent>
            </Card>

            {/* Right: Results */}
            <div className="col-span-1 lg:col-span-2 space-y-6">
              {/* Comparison Cards */}
              {results ? (
                <>
                  {/* Cost savings banner */}
                  {costSavings && Number.parseFloat(costSavings) > 0 && (
                    <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                      <Trophy className="w-5 h-5 text-emerald-400" />
                      <div>
                        <p className="text-sm font-semibold text-emerald-400">
                          DQN Agent outperforms Rule-Based by {costSavings}%
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {results.message}
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Strategy comparison cards */}
                  <div className="grid grid-cols-3 gap-4">
                    {/* Agent */}
                    <Card className={`border-border/50 shadow-lg ${bestStrategy === "agent" ? "ring-2 ring-emerald-500/50 bg-emerald-500/5" : "bg-card/50"}`}>
                      <CardContent className="p-6 text-center space-y-3">
                        <div className="flex items-center justify-center gap-2">
                          {bestStrategy === "agent" && <Trophy className="w-4 h-4 text-emerald-400" />}
                          <p className="text-xs font-bold uppercase tracking-wider text-blue-400">DQN Agent</p>
                        </div>
                        <div>
                          <p className="text-3xl font-display font-bold">
                            {results.rl_reward.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                          </p>
                          <p className="text-[10px] text-muted-foreground mt-1">Total Reward</p>
                        </div>
                        {results.rl_vs_oracle_pct != null && (
                          <div className="pt-3 border-t border-border/50">
                            <span className="text-sm font-mono">{results.rl_vs_oracle_pct.toFixed(1)}%</span>
                            <p className="text-[10px] text-muted-foreground">vs Oracle</p>
                          </div>
                        )}
                      </CardContent>
                    </Card>

                    {/* Oracle */}
                    <Card className={`border-border/50 shadow-lg ${bestStrategy === "oracle" ? "ring-2 ring-emerald-500/50 bg-emerald-500/5" : "bg-card/50"}`}>
                      <CardContent className="p-6 text-center space-y-3">
                        <div className="flex items-center justify-center gap-2">
                          {bestStrategy === "oracle" && <Trophy className="w-4 h-4 text-emerald-400" />}
                          <p className="text-xs font-bold uppercase tracking-wider text-purple-400">Oracle</p>
                        </div>
                        <div>
                          <p className="text-3xl font-display font-bold">
                            {results.oracle_reward.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                          </p>
                          <p className="text-[10px] text-muted-foreground mt-1">Total Reward</p>
                        </div>
                        <div className="pt-3 border-t border-border/50">
                          <span className="text-sm font-mono text-muted-foreground">Perfect Foresight</span>
                        </div>
                      </CardContent>
                    </Card>

                    {/* Rule-based */}
                    <Card className={`border-border/50 shadow-lg ${bestStrategy === "rule" ? "ring-2 ring-emerald-500/50 bg-emerald-500/5" : "bg-card/50"}`}>
                      <CardContent className="p-6 text-center space-y-3">
                        <div className="flex items-center justify-center gap-2">
                          {bestStrategy === "rule" && <Trophy className="w-4 h-4 text-emerald-400" />}
                          <p className="text-xs font-bold uppercase tracking-wider text-orange-400">Rule (s,S)</p>
                        </div>
                        <div>
                          <p className="text-3xl font-display font-bold">
                            {results.rule_reward.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                          </p>
                          <p className="text-[10px] text-muted-foreground mt-1">Total Reward</p>
                        </div>
                      </CardContent>
                    </Card>
                  </div>

                  {/* Evaluation graph */}
                  <Card className="border-border/50 shadow-lg bg-card/50">
                    <CardHeader>
                      <CardTitle>Inventory & Ordering Comparison</CardTitle>
                      <CardDescription>Visual comparison of all three strategies over the evaluation horizon</CardDescription>
                    </CardHeader>
                    <CardContent>
                      {graphSrc ? (
                        <img
                          src={graphSrc}
                          alt="Evaluation Comparison Graph"
                          className="w-full rounded-lg border border-border/50"
                        />
                      ) : (
                        <div className="h-[400px] flex items-center justify-center text-muted-foreground">
                          <Loader2 className="w-8 h-8 animate-spin" />
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </>
              ) : (
                <Card className="border-border/50 shadow-lg bg-card/50">
                  <CardContent className="p-0">
                    {evaluating ? (
                      <div className="h-[500px] flex flex-col items-center justify-center">
                        <Loader2 className="w-12 h-12 animate-spin text-primary mb-4" />
                        <p className="text-sm font-medium text-muted-foreground">Running evaluation...</p>
                        <p className="text-xs text-muted-foreground/70 mt-1">{horizonDays} day simulation in progress</p>
                      </div>
                    ) : (
                      <div className="h-[500px] flex flex-col items-center justify-center text-muted-foreground">
                        <BarChart3 className="w-12 h-12 mb-4 opacity-10" />
                        <p className="text-sm font-medium">No evaluation results yet</p>
                        <p className="text-xs text-muted-foreground/70 mt-1">Configure parameters and run the evaluation</p>
                      </div>
                    )}
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
