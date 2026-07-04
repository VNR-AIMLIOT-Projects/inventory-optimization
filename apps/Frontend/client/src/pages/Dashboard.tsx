import { Sidebar } from "@/components/common/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { Header } from "@/components/common/Header";
import { useStats, useSimulationState, useResetSimulation } from "@/hooks/use-simulation";
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from "recharts";
import { Package, DollarSign, AlertTriangle, RefreshCw, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export default function Dashboard() {
  const { isCollapsed } = useSidebar();
  const { data: stats } = useStats();
  const { data: simState } = useSimulationState();
  const { mutate: reset, isPending: isResetting } = useResetSimulation();

  if (!stats || !simState) return (
    <div className="flex min-h-screen bg-background text-foreground items-center justify-center">
      <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
    </div>
  );

  return (
    <div className="flex min-h-screen bg-transparent">
      <Sidebar />
      <main className={cn("flex-1", isCollapsed ? "lg:ml-[112px]" : "lg:ml-[288px]", "flex flex-col")}>
        <Header title="Warehouse Dashboard" />
        
        <div className="px-6 pb-6 pt-2 space-y-4 animate-in fade-in duration-500 slide-in-from-bottom-4">
          <div className="flex justify-between items-center">
            <div className="space-y-1">
              <h2 className="text-lg font-medium text-muted-foreground">Operational Overview</h2>
              <p className="text-sm text-muted-foreground">Automation active since <span className="text-primary font-mono font-bold">Jan 1, 2025</span></p>
            </div>
            <Button 
              variant="outline" 
              onClick={() => reset()} 
              disabled={isResetting}
              className="gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${isResetting ? 'animate-spin' : ''}`} />
              Reset Stats
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            <MetricCard 
              title="Projected Profit" 
              value={`$${stats.totalRevenue.toLocaleString()}`} 
              icon={DollarSign} 
              color="text-emerald-500"
              subtext="YTD Performance"
            />
            <MetricCard 
              title="Active Inventory" 
              value={simState.inventory.toString()} 
              icon={Package} 
              color="text-blue-500"
              subtext="Units on hand"
            />
            <MetricCard 
              title="Stockout Incidents" 
              value={stats.stockoutDays.toString()} 
              icon={AlertTriangle} 
              color="text-red-500"
              subtext="Fulfillment gaps"
            />
            <MetricCard 
              title="Auto-Orders" 
              value={stats.pendingDecisions.toString()} 
              icon={CheckCircle2} 
              color="text-yellow-500"
              subtext="Pending verification"
            />
          </div>

          <Card className="border-border/50 shadow-lg">
            <CardHeader>
              <CardTitle>Inventory Health Monitor</CardTitle>
            </CardHeader>
            <CardContent className="h-[400px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={simState.recentHistory}>
                  <defs>
                    <linearGradient id="colorInv" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="colorDem" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f43f5e" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#f43f5e" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                  <XAxis dataKey="day" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip 
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b' }}
                    itemStyle={{ color: '#e2e8f0' }}
                  />
                  <Area type="monotone" dataKey="inventoryLevel" stroke="#3b82f6" fillOpacity={1} fill="url(#colorInv)" strokeWidth={2} name="Current Stock" />
                  <Area type="monotone" dataKey="demand" stroke="#f43f5e" fillOpacity={1} fill="url(#colorDem)" strokeWidth={2} name="Customer Demand" />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}

function MetricCard({ title, value, icon: Icon, subtext, color }: any) {
  return (
    <Card className="border-border/50 shadow-lg hover:border-primary/20 transition-all duration-300">
      <CardContent className="p-6 text-center">
        <div className={`mx-auto mb-4 p-3 rounded-full bg-muted/50 w-fit ${color}`}>
          <Icon className="w-6 h-6" />
        </div>
        <p className="text-sm font-medium text-muted-foreground mb-1 uppercase tracking-wider">{title}</p>
        <h3 className="text-3xl font-bold font-display">{value}</h3>
        {subtext && <p className="text-xs text-muted-foreground mt-2">{subtext}</p>}
      </CardContent>
    </Card>
  );
}
