import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, AreaChart, Area } from "recharts";
import { Play, Settings2, Brain, TrendingUp, AlertTriangle, Coins } from "lucide-react";
import { useState, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

export default function Stage2Training() {
  const [isTraining, setIsTraining] = useState(false);
  const [progress, setProgress] = useState(0);
  const [learningCurve, setLearningCurve] = useState<{ep: number, reward: number}[]>([]);
  const [stockoutPenalty, setStockoutPenalty] = useState([100]);
  const [holdingCost, setHoldingCost] = useState([2]);
  const { toast } = useToast();

  const startTraining = async () => {
    setIsTraining(true);
    setProgress(0);
    setLearningCurve([]);
    
    // Simulate training process
    const duration = 5000;
    const interval = 50;
    const steps = duration / interval;
    let currentStep = 0;
    
    const timer = setInterval(() => {
      currentStep++;
      const p = Math.round((currentStep / steps) * 100);
      setProgress(p);
      
      setLearningCurve(prev => [
        ...prev, 
        { ep: currentStep, reward: -500 + (currentStep * 5) + (Math.random() * 50 - 25) }
      ]);

      if (currentStep >= steps) {
        clearInterval(timer);
        setIsTraining(false);
        toast({ title: "Training Completed", description: "Agent has converged to optimal policy." });
      }
    }, interval);
  };

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Stage 2: Agent Training" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">
          
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Step 6: Reward Customization */}
            <Card className="col-span-1 border-border/50 shadow-lg bg-card/50">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <Badge className="bg-primary/20 text-primary border-primary/20">Step 6</Badge>
                </div>
                <CardTitle className="flex items-center gap-2">
                  <Settings2 className="w-5 h-5 text-primary" />
                  Objective Tuning
                </CardTitle>
                <CardDescription>Define how the agent values stock vs cost</CardDescription>
              </CardHeader>
              <CardContent className="space-y-8">
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                      <AlertTriangle className="w-3 h-3 text-red-400" /> Stockout Penalty
                    </label>
                    <span className="text-xs font-mono font-bold">${stockoutPenalty[0]}</span>
                  </div>
                  <Slider value={stockoutPenalty} onValueChange={setStockoutPenalty} max={500} min={10} step={10} />
                  <p className="text-[10px] text-muted-foreground italic">Higher penalty makes agent keep more buffer stock.</p>
                </div>

                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                      <Coins className="w-3 h-3 text-yellow-400" /> Holding Cost
                    </label>
                    <span className="text-xs font-mono font-bold">${holdingCost[0]} / unit</span>
                  </div>
                  <Slider value={holdingCost} onValueChange={setHoldingCost} max={20} min={1} step={1} />
                  <p className="text-[10px] text-muted-foreground italic">Higher cost forces agent to be more lean.</p>
                </div>

                <div className="pt-4 border-t border-border/50">
                  <Button 
                    onClick={startTraining} 
                    disabled={isTraining} 
                    className="w-full gap-2 h-12 text-lg font-bold shadow-lg shadow-primary/20"
                  >
                    <Brain className={`w-5 h-5 ${isTraining ? 'animate-pulse' : ''}`} />
                    {isTraining ? 'Optimizing...' : 'Train Agent'}
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Step 7, 8, 9: Results */}
            <Card className="col-span-2 border-border/50 shadow-lg bg-card/50">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className="bg-primary/20 text-primary border-primary/20">Step 7, 8, 9</Badge>
                  </div>
                  <CardTitle>Learning Performance</CardTitle>
                  <CardDescription>Agent reward convergence over training episodes</CardDescription>
                </div>
                {learningCurve.length > 0 && (
                  <Badge variant="outline" className="border-emerald-500/50 text-emerald-500 bg-emerald-500/10">
                    Convergence High
                  </Badge>
                )}
              </CardHeader>
              <CardContent className="space-y-6">
                {isTraining && (
                  <div className="space-y-2">
                    <div className="flex justify-between text-xs font-mono">
                      <span>Neural Network Training...</span>
                      <span>{progress}%</span>
                    </div>
                    <Progress value={progress} className="h-1" />
                  </div>
                )}

                <div className="h-[350px]">
                  {learningCurve.length > 0 ? (
                    <ResponsiveContainer width="100%" height="100%">
                      <AreaChart data={learningCurve}>
                        <defs>
                          <linearGradient id="colorReward" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                          </linearGradient>
                        </defs>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                        <XAxis dataKey="ep" stroke="#94a3b8" fontSize={10} label={{ value: 'Episodes', position: 'insideBottom', offset: -5, fontSize: 10 }} />
                        <YAxis stroke="#94a3b8" fontSize={10} />
                        <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b' }} />
                        <Area type="monotone" dataKey="reward" stroke="#3b82f6" fillOpacity={1} fill="url(#colorReward)" strokeWidth={2} name="Total Reward" />
                      </AreaChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="h-full flex flex-col items-center justify-center text-muted-foreground bg-muted/20 rounded-xl border border-dashed border-border">
                      <TrendingUp className="w-12 h-12 mb-4 opacity-10" />
                      <p className="text-sm font-medium">No training data available</p>
                      <p className="text-xs">Adjust rewards and click 'Train Agent' to start</p>
                    </div>
                  )}
                </div>

                {learningCurve.length > 100 && (
                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-4 rounded-xl bg-primary/5 border border-primary/10">
                      <p className="text-[10px] font-bold text-primary uppercase mb-1">Baseline Comparison</p>
                      <div className="flex items-end gap-2">
                        <span className="text-2xl font-display font-bold">+24%</span>
                        <span className="text-[10px] text-muted-foreground pb-1">Efficiency over Rule-based</span>
                      </div>
                    </div>
                    <div className="p-4 rounded-xl bg-emerald-500/5 border border-emerald-500/10">
                      <p className="text-[10px] font-bold text-emerald-500 uppercase mb-1">Fulfillment Rate</p>
                      <div className="flex items-end gap-2">
                        <span className="text-2xl font-display font-bold">98.2%</span>
                        <span className="text-[10px] text-muted-foreground pb-1">Agent optimized</span>
                      </div>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
