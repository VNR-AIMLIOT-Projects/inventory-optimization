import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { BarChart3, Trophy, Loader2, TrendingUp, Target, Scale } from "lucide-react";
import { useState, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { evaluateMultiSku, getMultiSkuEvalGraph } from "@/lib/api";
import type { MultiSkuEvalResponse, SkuEvalResult } from "@/lib/api";

export default function Stage3Deployment() {
  const { toast } = useToast();

  const [evaluating, setEvaluating] = useState(false);
  const [results, setResults] = useState<Record<string, SkuEvalResult>>({});
  const [graphSrcs, setGraphSrcs] = useState<Record<string, string>>({});
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [message, setMessage] = useState<string>("");

  const skuNames = Object.keys(results).sort();

  useEffect(() => {
    if (!selectedSku && skuNames.length > 0) {
      setSelectedSku(skuNames[0]);
    }
  }, [skuNames, selectedSku]);

  const handleEvaluate = async () => {
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

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col h-screen overflow-hidden">
        <Header title="Multi-SKU Evaluation" />

        <div className="flex-1 p-8 space-y-8 overflow-y-auto">
          <StageNav />
          <div className="grid grid-cols-12 gap-8">

            {/* Left: Controls + SKU list */}
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
                  <Button onClick={handleEvaluate} disabled={evaluating} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground h-12 font-bold text-lg shadow-lg shadow-primary/20">
                    {evaluating ? <Loader2 className="w-5 h-5 animate-spin mr-2" /> : <BarChart3 className="w-5 h-5 mr-2" />}
                    {evaluating ? "Loading..." : "Load Evaluation Results"}
                  </Button>
                </CardContent>
              </Card>

              {/* SKU selector */}
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
                            <span>{r.rl_vs_oracle_pct != null ? `${r.rl_vs_oracle_pct.toFixed(1)}% of Oracle` : ""}</span>
                          </div>
                        </button>
                      );
                    })}
                  </CardContent>
                </Card>
              )}
            </div>

            {/* Right: Per-SKU Results */}
            <div className="col-span-8 space-y-8">

              {/* SKU tabs */}
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
