import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useStats, useSimulationState, useStepSimulation } from "@/hooks/use-simulation";
import { usePendingDecisions } from "@/hooks/use-decisions";
import { DecisionCard } from "@/components/DecisionCard";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from "recharts";
import { Play, ClipboardCheck, History, Package, DollarSign, AlertTriangle, Activity } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

export default function Stage3Deployment() {
  const { data: stats } = useStats();
  const { data: simState } = useSimulationState();
  const { data: pendingDecisions } = usePendingDecisions();
  const { mutate: step } = useStepSimulation();

  if (!stats || !simState) return (
    <div className="flex min-h-screen bg-background text-foreground items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col h-screen overflow-hidden">
        <Header title="Stage 3: Operations Dashboard" />
        
        <div className="flex-1 p-8 space-y-8 overflow-y-auto">
          {/* Step 11: Dashboard Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            <MetricCard title="Cumulative Profit" value={`$${stats.totalRevenue.toLocaleString()}`} icon={DollarSign} color="text-emerald-500" />
            <MetricCard title="Inventory Level" value={simState.inventory.toString()} icon={Package} color="text-blue-500" />
            <MetricCard title="Stockouts" value={stats.stockoutDays.toString()} icon={AlertTriangle} color="text-red-500" />
            <MetricCard title="Avg. Fulfillment" value="96.4%" icon={Activity} color="text-primary" />
          </div>

          <div className="grid grid-cols-12 gap-8">
            {/* Step 12: Human-in-the-Loop */}
            <div className="col-span-5 space-y-6">
              <Card className="border-border/50 bg-gradient-to-br from-card to-muted/20 shadow-xl">
                <CardHeader>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className="bg-primary/20 text-primary border-primary/20 uppercase text-[10px] tracking-widest font-bold">Step 12</Badge>
                  </div>
                  <CardTitle className="text-xl flex items-center gap-2">
                    <ClipboardCheck className="w-6 h-6 text-yellow-500" />
                    Automation Verification
                  </CardTitle>
                  <CardDescription>Agent proposals requiring supervisor approval</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  <Button onClick={() => step()} className="w-full bg-primary hover:bg-primary/90 text-primary-foreground h-12 font-bold text-lg shadow-lg shadow-primary/20">
                    Execute Next Simulation Day
                  </Button>
                  
                  <div className="space-y-4 pt-4 border-t border-border/50">
                    <h3 className="text-sm font-bold uppercase tracking-wider text-muted-foreground">Pending Queue ({pendingDecisions?.length || 0})</h3>
                    <AnimatePresence mode="popLayout">
                      {pendingDecisions?.length === 0 ? (
                        <motion.div 
                          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                          className="h-40 flex flex-col items-center justify-center text-muted-foreground bg-muted/20 rounded-xl border border-dashed border-border"
                        >
                          <p className="text-xs">All inventory tasks synced</p>
                        </motion.div>
                      ) : (
                        pendingDecisions?.map((decision) => (
                          <DecisionCard key={decision.id} decision={decision} />
                        ))
                      )}
                    </AnimatePresence>
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Step 13: Live Tracking */}
            <div className="col-span-7 space-y-8">
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className="bg-primary/20 text-primary border-primary/20 uppercase text-[10px] tracking-widest font-bold">Step 13</Badge>
                  </div>
                  <CardTitle>Live Performance Pulse</CardTitle>
                </CardHeader>
                <CardContent className="h-[300px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart data={simState.recentHistory}>
                      <defs>
                        <linearGradient id="colorInv" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.2}/>
                          <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.1} />
                      <XAxis dataKey="day" hide />
                      <YAxis stroke="#94a3b8" fontSize={10} />
                      <Tooltip contentStyle={{ backgroundColor: '#0f172a' }} />
                      <Area type="monotone" dataKey="inventoryLevel" stroke="#3b82f6" fillOpacity={1} fill="url(#colorInv)" strokeWidth={2} name="Stock Level" />
                      <Area type="monotone" dataKey="demand" stroke="#f43f5e" fillOpacity={0.1} strokeWidth={1} name="Customer Demand" />
                    </AreaChart>
                  </ResponsiveContainer>
                </CardContent>
              </Card>

              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader className="py-4">
                  <CardTitle className="text-sm font-bold flex items-center gap-2">
                    <History className="w-4 h-4 text-muted-foreground" />
                    Operational History
                  </CardTitle>
                </CardHeader>
                <CardContent className="p-0 max-h-[300px] overflow-auto">
                  <Table>
                    <TableHeader className="bg-muted/50 sticky top-0 z-10">
                      <TableRow className="border-border/50">
                        <TableHead className="text-[10px] uppercase font-bold py-2">Day</TableHead>
                        <TableHead className="text-[10px] uppercase font-bold py-2">Fulfillment</TableHead>
                        <TableHead className="text-[10px] uppercase font-bold py-2 text-right">Profit</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {simState?.recentHistory?.slice().reverse().map((day) => (
                        <TableRow key={day.id} className="border-border/50 hover:bg-muted/30">
                          <TableCell className="font-mono text-[10px] py-2">#{day.day}</TableCell>
                          <TableCell className="py-2">
                            <div className="flex items-center gap-2">
                              <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden w-20">
                                <div 
                                  className={cn("h-full rounded-full", day.lostSales > 0 ? "bg-amber-500" : "bg-emerald-500")}
                                  style={{ width: `${Math.min(100, (day.unitsSold / (day.demand || 1)) * 100)}%` }}
                                />
                              </div>
                              <span className="text-[10px] font-mono">{((day.unitsSold / (day.demand || 1)) * 100).toFixed(0)}%</span>
                            </div>
                          </TableCell>
                          <TableCell className="text-right font-mono text-[10px] py-2">${Number(day.reward).toFixed(0)}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

function MetricCard({ title, value, icon: Icon, color }: any) {
  return (
    <Card className="border-border/50 shadow-lg bg-card/50">
      <CardContent className="p-6">
        <div className="flex justify-between items-start">
          <div className={`p-2 rounded-lg bg-muted/50 ${color}`}>
            <Icon className="w-5 h-5" />
          </div>
          <div className="text-right">
            <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">{title}</p>
            <h3 className="text-2xl font-bold font-display">{value}</h3>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
