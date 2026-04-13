import { useAuth } from "@/hooks/use-auth";
import { useLocation } from "wouter";
import { useEffect } from "react";
import { ArrowRight, Activity, Database, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function LandingPage() {
  const { user, isLoading } = useAuth();
  const [, setLocation] = useLocation();

  useEffect(() => {
    if (!isLoading && user) {
      setLocation("/home");
    }
  }, [user, isLoading, setLocation]);

  if (isLoading) return null;

  return (
    <div className="min-h-screen bg-background text-foreground selection:bg-primary/20 overflow-hidden relative flex flex-col font-sans">
      {/* Ethereal Background Elements */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-primary/5 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-blue-500/5 blur-[120px] pointer-events-none" />
      
      <div className="absolute inset-0 bg-[linear-gradient(to_right,hsl(var(--muted-foreground))_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--muted-foreground))_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none opacity-[0.05] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]" />

      {/* Header */}
      <header className="relative z-10 p-6 flex items-center justify-between border-b border-border/50 bg-background/50 backdrop-blur-md">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-md bg-muted/50 border border-border flex items-center justify-center font-bold font-mono text-xl tracking-tighter">
            Rx
          </div>
          <span className="font-semibold tracking-wide text-lg text-foreground">REPLENIX</span>
        </div>
        <nav className="flex items-center gap-4">
          <ThemeToggle />
          <Button 
            variant="ghost" 
            className="text-muted-foreground hover:text-foreground hover:bg-muted rounded-none h-9 px-4 text-xs font-mono uppercase tracking-wider transition-colors border border-transparent hover:border-border"
            onClick={() => setLocation("/auth")}
          >
            Log In
          </Button>
        </nav>
      </header>

      {/* Main Content: Central Pillar Layout */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full text-center mt-12 mb-24">
        
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border bg-card/30 backdrop-blur-md shadow-sm mb-8">
          <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="text-xs font-mono text-muted-foreground tracking-uppercase">System Online / Beta Phase</span>
        </div>

        <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-b from-foreground to-foreground/50">
          Intelligent Inventory <br className="hidden md:block" /> Optimization Pipeline
        </h1>
        
        <p className="max-w-2xl text-lg text-muted-foreground mb-10 font-light leading-relaxed">
          Replenix utilizes Reinforcement Learning and predictive data modeling to precisely align your supply with volatile demand. Ethereal efficiency meets utilitarian precision.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 items-center">
          <button 
            onClick={() => setLocation("/auth")}
            className="group relative px-8 py-4 bg-primary text-primary-foreground font-medium text-sm shadow-lg shadow-primary/20 uppercase tracking-widest overflow-hidden transition-all hover:pr-12 rounded-xl"
          >
            <span className="relative z-10 flex items-center gap-2">
              Initialize System
              <ArrowRight className="w-4 h-4 opacity-0 -ml-4 group-hover:opacity-100 group-hover:ml-0 transition-all duration-300" />
            </span>
            <div className="absolute inset-0 bg-primary/80 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out" />
          </button>
        </div>

        {/* Feature Trays - Glassmorphic styling */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-24 w-full">
          <FeatureCard 
            icon={<Database className="w-5 h-5" />}
            title="Data Integration"
            desc="Seamless unification of historical sales and inventory states."
          />
          <FeatureCard 
            icon={<Cpu className="w-5 h-5" />}
            title="DQN Training"
            desc="Continuous learning models adjusting reorder points dynamically."
          />
          <FeatureCard 
            icon={<Activity className="w-5 h-5" />}
            title="Real-time Evaluation"
            desc="Immediate visualization of policy outcomes and reward metrics."
          />
        </div>
      </main>
    </div>
  );
}

function FeatureCard({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) {
  return (
    <div className="relative group overflow-hidden rounded-xl border border-border bg-card/30 backdrop-blur-md p-6 text-left shadow-sm transition-all hover:bg-card/50 hover:shadow-md hover:border-border/80">
      <div className="mb-4 text-primary opacity-80 group-hover:opacity-100 transition-opacity">
        {icon}
      </div>
      <h3 className="text-foreground font-medium mb-2 tracking-wide">{title}</h3>
      <p className="text-sm text-muted-foreground leading-relaxed font-light">{desc}</p>
    </div>
  );
}
