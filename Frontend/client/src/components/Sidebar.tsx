import { Link, useLocation } from "wouter";
import { Upload, Edit3, Eye, Brain, BarChart3, Package, Activity, Rocket } from "lucide-react";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const [location] = useLocation();

  const stages = [
    {
      id: 1,
      title: "Step 1: Upload",
      url: "/",
      icon: Upload,
      description: "Load demand data"
    },
    {
      id: 2,
      title: "Step 2: Modify",
      url: "/modify",
      icon: Edit3,
      description: "Scenario builder"
    },
    {
      id: 3,
      title: "Step 3: Preview",
      url: "/preview",
      icon: Eye,
      description: "Visualize demand"
    },
    {
      id: 4,
      title: "Step 4: Train",
      url: "/train",
      icon: Brain,
      description: "DQN agent training"
    },
    {
      id: 5,
      title: "Step 5: Evaluate",
      url: "/evaluate",
      icon: BarChart3,
      description: "Compare results"
    },
    {
      id: 6,
      title: "Step 6: Deploy",
      url: "/deploy",
      icon: Rocket,
      description: "Interactive simulation"
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
    </div>
  );
}
