import { useLocation } from "wouter";
import { ArrowRight, Database, Settings2, Cpu, Activity, Rocket } from "lucide-react";
import { Sidebar } from "@/components/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { Header } from "@/components/Header";
import { Card, CardContent } from "@/components/ui/card";

const PIPELINE_STEPS = [
  {
    icon: Database,
    title: "1. Data Integration",
    desc: "Upload and validate raw sales and inventory logs.",
  },
  {
    icon: Settings2,
    title: "2. Demand Shaping",
    desc: "Optionally apply stochastic noise or AI manipulation to test resilience.",
  },
  {
    icon: Cpu,
    title: "3. DQN Training",
    desc: "Agents explore environments to learn optimal reorder thresholds.",
  },
  {
    icon: Activity,
    title: "4. Policy Evaluation",
    desc: "Simulate exact rewards, lost sales, and holding costs against baselines.",
  },
  {
    icon: Rocket,
    title: "5. Production Deployment",
    desc: "Deploy the trained policy to the live environment.",
  }
];

export default function HomeDashboard() {
  const { isCollapsed } = useSidebar();
  const [, setLocation] = useLocation();

  return (
    <div className="flex min-h-screen bg-background text-foreground font-sans selection:bg-primary/20">
      
      <Sidebar />

      <main className={cn("flex-1", isCollapsed ? "lg:ml-[112px]" : "lg:ml-[288px]", "flex flex-col relative z-10")}>
        <Header title="Control Center" />

        <div className="px-6 pb-16 pt-8 space-y-4 animate-in fade-in duration-500 max-w-5xl mx-auto w-full">
          <div className="mb-12 border-l-2 border-primary/50 pl-6 py-2">
            <h1 className="text-4xl font-light tracking-tight mb-4 text-foreground">
              System <span className="font-bold">Architecture</span>
            </h1>
            <p className="text-muted-foreground text-lg max-w-2xl font-light leading-relaxed">
              Welcome to the Replenix Control Center. Follow the sequential pipeline to train, evaluate, and deploy Reinforcement Learning models tailored to your inventory dynamics.
            </p>
          </div>

          {/* Pipeline Visualization */}
          <div className="relative">
            {/* Vertical connecting line */}
            <div className="absolute left-6 top-10 bottom-10 w-px bg-gradient-to-b from-primary/50 via-border to-transparent hidden md:block" />

            <div className="flex flex-col gap-6">
              {PIPELINE_STEPS.map((step, idx) => (
                <div key={idx} className="relative flex flex-col md:flex-row gap-6 md:gap-12 md:items-center group">
                  {/* Node marker */}
                  <div className="hidden md:flex relative z-10 w-12 h-12 bg-card border border-border rounded-xl items-center justify-center shadow-sm group-hover:border-primary/50 group-hover:shadow-[0_0_15px_rgba(var(--primary),0.2)] transition-all shrink-0">
                    <step.icon className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>

                  {/* Card */}
                  <Card className="flex-1 border-border/50 shadow-sm bg-card/50 backdrop-blur-sm group-hover:bg-card group-hover:border-border group-hover:shadow-md transition-all">
                    <CardContent className="p-6">
                      <div className="flex items-center gap-4 mb-3 md:hidden">
                        <step.icon className="w-5 h-5 text-primary" />
                        <h3 className="text-xl font-medium tracking-wide text-foreground">{step.title}</h3>
                      </div>
                      <h3 className="hidden md:block text-xl font-medium tracking-wide mb-2 text-foreground/90 group-hover:text-foreground transition-colors">{step.title}</h3>
                      <p className="text-muted-foreground font-light leading-relaxed">{step.desc}</p>
                    </CardContent>
                  </Card>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-16 border-t border-border/50 pt-12 flex justify-center">
            <button 
              onClick={() => setLocation("/upload")}
              className="group relative inline-flex items-center gap-4 bg-primary text-primary-foreground px-10 py-5 text-sm font-bold tracking-widest uppercase overflow-hidden rounded-xl shadow-lg shadow-primary/20 hover:shadow-primary/40 transition-shadow"
            >
              <div className="absolute inset-x-0 bottom-0 h-full bg-black/10 scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-300" />
              <span className="relative z-10">Commence Pipeline</span>
              <ArrowRight className="w-5 h-5 relative z-10 group-hover:translate-x-1 transition-transform" />
            </button>
          </div>

        </div>
      </main>
    </div>
  );
}
