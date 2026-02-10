import { Link, useLocation } from "wouter";
import { LayoutDashboard, Database, Zap, Package, Activity } from "lucide-react";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const [location] = useLocation();

  const stages = [
    {
      id: 1,
      title: "Stage 1: Pre-Processing",
      url: "/",
      icon: Database,
      description: "Data Upload & Fitting"
    },
    {
      id: 2,
      title: "Stage 2: Agent Training",
      url: "/training",
      icon: Activity,
      description: "Reward Tuning & Learning"
    },
    {
      id: 3,
      title: "Stage 3: Operations",
      url: "/operations",
      icon: Zap,
      description: "Human-in-the-Loop"
    },
  ];

  return (
    <div className="w-72 h-screen bg-card border-r border-border flex flex-col fixed left-0 top-0 z-50">
      <div className="p-6 border-b border-border/50">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center shadow-lg shadow-primary/20">
            <Package className="w-6 h-6 text-primary-foreground" />
          </div>
          <div>
            <span className="font-display font-bold text-lg text-foreground block leading-tight">Replenix</span>
            <span className="text-xs text-muted-foreground font-medium uppercase tracking-widest">Intelligent Inventory Automated</span>
          </div>
        </div>
      </div>

      <div className="flex-1 p-4 space-y-6 overflow-y-auto">
        <div>
          <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest px-4 mb-4">Workflow Stages</p>
          <nav className="space-y-2">
            {stages.map((stage) => {
              const isActive = location === stage.url;
              const Icon = stage.icon;
              return (
                <Link key={stage.url} href={stage.url}>
                  <div
                    className={cn(
                      "flex flex-col gap-1 px-4 py-3 rounded-xl transition-all duration-200 cursor-pointer group relative overflow-hidden",
                      isActive
                        ? "bg-primary/10 border border-primary/20"
                        : "text-muted-foreground hover:bg-muted/50 border border-transparent"
                    )}
                  >
                    <div className="flex items-center gap-3">
                      <Icon className={cn("w-5 h-5", isActive ? "text-primary" : "text-muted-foreground")} />
                      <span className={cn("font-semibold text-sm", isActive ? "text-foreground" : "text-muted-foreground")}>
                        {stage.title}
                      </span>
                    </div>
                    <span className="text-[10px] ml-8 opacity-70">{stage.description}</span>
                    {isActive && <div className="absolute left-0 top-0 w-1 h-full bg-primary" />}
                  </div>
                </Link>
              );
            })}
          </nav>
        </div>
      </div>

      <div className="p-4 m-4 rounded-xl bg-muted/30 border border-border/50">
        <div className="flex items-center gap-2 mb-2">
          <Activity className="w-4 h-4 text-emerald-400" />
          <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">System Engine</span>
        </div>
        <div className="space-y-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-muted-foreground">RL Status</span>
            <span className="text-emerald-400">Ready</span>
          </div>
          <div className="flex justify-between text-[10px]">
            <span className="text-muted-foreground">Version</span>
            <span className="text-foreground font-mono">v3.1.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}
