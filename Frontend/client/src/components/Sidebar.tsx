import { Link, useLocation } from "wouter";
import { Upload, Edit3, Eye, Brain, BarChart3, Package, Activity, Rocket } from "lucide-react";
import { cn } from "@/lib/utils";

export function SidebarContent() {
  const [location] = useLocation();

  const stages = [
    {
      id: 1,
      title: "Step 1: Upload",
      url: "/upload",
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
    <div className="flex flex-col h-full bg-background/40">
      {/* App Branding */}
      <div className="p-6">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20">
            <Package className="w-5 h-5 text-primary-foreground" />
          </div>
          <div>
            <span className="font-display font-bold text-lg text-foreground block leading-tight tracking-tight">Replenix</span>
            <span className="text-[9px] text-muted-foreground font-semibold uppercase tracking-[0.15em]">Intelligent Inventory Automated</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 px-4 space-y-6 overflow-y-auto">
        <div>
          <p className="text-[10px] font-bold text-primary/60 uppercase tracking-widest px-2 mb-4">Workflow</p>
          <nav className="space-y-1">
            {stages.map((stage) => {
              const isActive = location === stage.url;
              const Icon = stage.icon;
              return (
                <Link key={stage.url} href={stage.url}>
                  <div
                    className={cn(
                      "flex items-start gap-3 px-3 py-3 rounded-2xl transition-all duration-300 cursor-pointer group relative overflow-hidden",
                      isActive
                        ? "bg-primary/10 shadow-[inset_0_1px_0_0_rgba(255,255,255,0.1)] border border-primary/20"
                        : "text-muted-foreground hover:bg-muted/40 border border-transparent"
                    )}
                  >
                    <div className={cn(
                      "mt-0.5 p-1.5 rounded-lg transition-colors border",
                      isActive ? "bg-background border-primary/20 shadow-sm" : "bg-muted/30 border-transparent group-hover:bg-background group-hover:shadow-sm"
                    )}>
                      <Icon className={cn("w-4 h-4", isActive ? "text-primary" : "text-muted-foreground")} />
                    </div>
                    
                    <div className="flex flex-col">
                      <span className={cn("font-medium text-[13px] tracking-tight", isActive ? "text-foreground" : "text-muted-foreground")}>
                        {stage.title}
                      </span>
                      <span className="text-[10px] opacity-70 mt-0.5 tracking-wide">{stage.description}</span>
                    </div>

                    {/* Active Indicator Glow */}
                    {isActive && (
                      <div className="absolute inset-0 bg-gradient-to-r from-primary/10 to-transparent opacity-50 pointer-events-none" />
                    )}
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

export function Sidebar() {
  return (
    <>
      {/* 
        Floating Antigravity Sidebar 
        We use calc(100vh - 2rem) to leave a 1rem margin top & bottom 
      */}
      <div className="hidden lg:flex w-64 h-[calc(100vh-2rem)] fixed left-4 top-4 z-50 rounded-3xl glass shadow-2xl overflow-hidden shadow-primary/5">
        <SidebarContent />
      </div>
    </>
  );
}
