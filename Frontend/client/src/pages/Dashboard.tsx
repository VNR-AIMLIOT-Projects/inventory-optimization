import { Sidebar } from "@/components/common/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { Header } from "@/components/common/Header";
import { useStats, useSimulationState, useResetSimulation } from "@/hooks/use-simulation";
import { XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area, Legend } from "recharts";
import { Package, DollarSign, AlertTriangle, RefreshCw, CheckCircle2, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

function MetricCard({ title, value, icon: Icon, subtext, trend }: {
  title: string; value: string; icon: any; subtext?: string; trend?: "up" | "down" | "warn";
}) {
  const iconBg =
    trend === "up"   ? "bg-success/10 text-success" :
    trend === "down" ? "bg-primary/10 text-primary"  :
    trend === "warn" ? "bg-amber-500/10 text-amber-500" :
                       "bg-muted text-muted-foreground";

  return (
    <div className="bg-card border border-border rounded-2xl p-5 shadow-amber flex items-center gap-4 animate-fade-in-up hover:border-primary/30 transition-colors duration-200">
      <div className={cn("w-11 h-11 rounded-xl flex items-center justify-center shrink-0", iconBg)}>
        <Icon className="w-5 h-5" />
      </div>
      <div>
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{title}</p>
        <p className="font-display font-bold text-2xl text-foreground tabular mt-0.5">{value}</p>
        {subtext && <p className="text-xs text-muted-foreground mt-0.5">{subtext}</p>}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { isCollapsed } = useSidebar();
  const { data: stats } = useStats();
  const { data: simState } = useSimulationState();
  const { mutate: reset, isPending: isResetting } = useResetSimulation();

  if (!stats || !simState) {
    return (
      <div className="flex min-h-dvh bg-background items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="flex min-h-dvh bg-background">
      <Sidebar />
      <main className={cn(
        "flex-1 flex flex-col transition-all duration-300 ease-spring",
        isCollapsed ? "lg:ml-[5.5rem]" : "lg:ml-[17rem]",
      )}>
        <Header title="Warehouse dashboard" />

        <div className="px-6 pb-10 pt-6 max-w-container mx-auto w-full space-y-6">
          {/* ── Header row ── */}
          <div className="flex items-center justify-between animate-fade-in-up">
            <div>
              <h1 className="font-display font-bold text-2xl text-foreground">Live simulation</h1>
              <p className="text-sm text-muted-foreground mt-1">
                Automation active since{" "}
                <span className="text-primary font-semibold font-mono">Jan 1, 2025</span>
              </p>
            </div>
            <button
              onClick={() => reset()}
              disabled={isResetting}
              className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-xl border border-border text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-all duration-200 active:scale-[0.97]"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isResetting && "animate-spin")} />
              Reset stats
            </button>
          </div>

          {/* ── Metric cards ── */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard
              title="Projected profit"
              value={`$${stats.totalRevenue.toLocaleString()}`}
              icon={DollarSign}
              subtext="YTD performance"
              trend="up"
            />
            <MetricCard
              title="Active inventory"
              value={simState.inventory.toString()}
              icon={Package}
              subtext="Units on hand"
              trend="down"
            />
            <MetricCard
              title="Stockout incidents"
              value={stats.stockoutDays.toString()}
              icon={AlertTriangle}
              subtext="Fulfillment gaps"
              trend="warn"
            />
            <MetricCard
              title="Auto-orders"
              value={stats.pendingDecisions.toString()}
              icon={CheckCircle2}
              subtext="Pending verification"
            />
          </div>

          {/* ── Chart ── */}
          <Card className="border-border shadow-amber rounded-2xl animate-fade-in-up delay-150">
            <CardHeader className="pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="font-display font-semibold text-lg">Inventory health monitor</CardTitle>
                  <p className="text-sm text-muted-foreground mt-1">Stock level vs customer demand — recent history</p>
                </div>
                <div className="flex items-center gap-3 text-xs">
                  <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-primary rounded-full inline-block" />Stock</span>
                  <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-destructive rounded-full inline-block" />Demand</span>
                </div>
              </div>
            </CardHeader>
            <CardContent className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={simState.recentHistory} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="fillStock" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="hsl(var(--primary))" stopOpacity={0.22} />
                      <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0}    />
                    </linearGradient>
                    <linearGradient id="fillDemand" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor="hsl(var(--destructive))" stopOpacity={0.18} />
                      <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0}    />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
                  <XAxis dataKey="day" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={{
                      background: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "0.75rem",
                    }}
                    itemStyle={{ color: "hsl(var(--foreground))" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="inventoryLevel"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    fill="url(#fillStock)"
                    name="Current stock"
                    dot={false}
                  />
                  <Area
                    type="monotone"
                    dataKey="demand"
                    stroke="hsl(var(--destructive))"
                    strokeWidth={2}
                    fill="url(#fillDemand)"
                    name="Customer demand"
                    dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  );
}
