import { Link, useLocation } from "wouter";
import { Upload, Edit3, Eye, Brain, BarChart3, Package, Activity, Rocket } from "lucide-react";
import { cn } from "@/lib/utils";

import { useSidebar } from "@/hooks/use-sidebar";

export function SidebarContent({ isCollapsed = false }: { isCollapsed?: boolean }) {
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
          <Link href="/home" className="shrink-0 cursor-pointer">
            <div className="w-10 h-10 rounded-xl bg-primary flex items-center justify-center shadow-lg shadow-primary/20 transition-transform hover:scale-105 active:scale-95">
              <Package className="w-5 h-5 text-primary-foreground" />
            </div>
          </Link>
          {!isCollapsed && (
            <div className="overflow-hidden whitespace-nowrap transition-all duration-300 opacity-100">
              <span className="font-display font-bold text-lg text-foreground block leading-tight tracking-tight">Replenix</span>
              <span className="text-[9px] text-muted-foreground font-semibold uppercase tracking-[0.15em]">Intelligent Inventory</span>
            </div>
          )}
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 px-4 space-y-6 overflow-y-auto overflow-x-hidden">
        <div>
          {!isCollapsed && (
            <p className="text-[10px] font-bold text-primary/60 uppercase tracking-widest px-2 mb-4">Workflow</p>
          )}
          <nav className="space-y-1">
            {stages.map((stage) => {
              const isActive = location === stage.url;
              const Icon = stage.icon;
              return (
                <Link key={stage.url} href={stage.url}>
                  <div
                    className={cn(
                      "flex items-start rounded-xl transition-all duration-300 cursor-pointer group relative overflow-hidden",
                      isCollapsed ? "justify-center py-3 px-0 w-12 mx-auto" : "gap-3 px-3 py-3",
                      isActive
                        ? "bg-muted/60 text-foreground font-medium"
                        : "text-muted-foreground hover:bg-muted/40 hover:text-foreground"
                    )}
                  >
                    <div className={cn(
                      "mt-0.5 p-1.5 rounded-lg transition-colors shrink-0",
                      isActive ? "bg-background shadow-sm" : "bg-transparent group-hover:bg-background group-hover:shadow-sm"
                    )}>
                      <Icon className={cn("w-4 h-4", isActive ? "text-primary" : "text-muted-foreground")} />
                    </div>
                    
                    {!isCollapsed && (
                      <div className="flex flex-col overflow-hidden whitespace-nowrap">
                        <span className={cn("font-medium text-[13px] tracking-tight", isActive ? "text-foreground" : "text-muted-foreground")}>
                          {stage.title}
                        </span>
                        <span className="text-[10px] opacity-70 mt-0.5 tracking-wide">{stage.description}</span>
                      </div>
                    )}

                    {/* Active Indicator Glow */}
                    {isActive && (
                      <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-8 bg-primary rounded-r-full" />
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
  const { isCollapsed } = useSidebar();

  return (
    <>
      {/* 
        Floating Antigravity Sidebar 
        We use calc(100vh - 2rem) to leave a 1rem margin top & bottom 
      */}
      <div 
        className={cn(
          "hidden lg:flex h-[calc(100vh-2rem)] fixed left-4 top-4 z-50 rounded-xl bg-card border border-border shadow-sm overflow-hidden transition-all duration-300",
          isCollapsed ? "w-20" : "w-64"
        )}
      >
        <SidebarContent isCollapsed={isCollapsed} />
      </div>
    </>
  );
}
