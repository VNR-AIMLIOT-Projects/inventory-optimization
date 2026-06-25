import { useAuth } from "@/hooks/use-auth";
import { useLocation } from "wouter";
import { useEffect } from "react";
import { ArrowRight, Box } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/common/ThemeToggle";

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
    <div className="min-h-screen bg-background text-foreground flex flex-col font-sans selection:bg-primary/20">
      
      {/* Header */}
      <header className="relative z-10 p-6 flex items-center justify-between border-b border-border bg-background">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center">
            <Box className="w-5 h-5 text-primary" />
          </div>
          <span className="font-bold tracking-wider text-xl text-foreground">REPLENIX</span>
        </div>
        <nav className="flex items-center gap-4">
          <ThemeToggle />
          <Button 
            variant="ghost" 
            className="text-muted-foreground hover:text-foreground font-medium"
            onClick={() => setLocation("/auth")}
          >
            Sign In
          </Button>
        </nav>
      </header>

      {/* Main Content */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8 max-w-screen-xl mx-auto w-full text-center mt-12 mb-24 animate-in fade-in duration-700">
        
        <h1 className="text-5xl md:text-7xl font-light tracking-tight mb-6 text-foreground">
          Smart inventory decisions, <br className="hidden md:block" />
          <span className="font-bold">powered by reinforcement learning.</span>
        </h1>
        
        <p className="max-w-2xl text-lg md:text-xl text-muted-foreground mb-10 font-light leading-relaxed">
          Replenix removes the guesswork from supply chain management. By predicting demand spikes and adjusting stock levels automatically, you avoid stockouts and reduce wasted capital.
        </p>

        <div className="flex flex-col sm:flex-row gap-6 items-center mb-16">
          <Button 
            size="lg"
            onClick={() => setLocation("/auth")}
            className="group px-8 text-base font-bold tracking-wide h-12"
          >
            Get Started
            <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Button>
        </div>

        {/* Product Screenshot */}
        <div className="w-full max-w-5xl mx-auto relative mb-24 group">
          <div className="absolute -inset-1 bg-gradient-to-r from-primary/30 to-blue-500/30 rounded-2xl blur-2xl opacity-50 group-hover:opacity-75 transition-opacity duration-500" />
          <div className="relative rounded-xl border border-border/50 bg-card overflow-hidden shadow-2xl">
            <div className="h-8 bg-muted/30 border-b border-border flex items-center px-4 gap-2">
              <div className="w-3 h-3 rounded-full bg-destructive/50" />
              <div className="w-3 h-3 rounded-full bg-amber-500/50" />
              <div className="w-3 h-3 rounded-full bg-success/50" />
            </div>
            <img 
              src="/dashboard-preview.png" 
              alt="Replenix Deployment Dashboard" 
              className="w-full h-auto object-cover"
            />
          </div>
        </div>

        {/* Credibility Points */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full max-w-4xl mx-auto mb-24 text-center">
          <div>
            <h3 className="font-semibold text-foreground text-lg mb-2">Built with PyTorch</h3>
            <p className="text-muted-foreground text-sm font-light">State-of-the-art Deep Q-Network agents powering your inventory decisions.</p>
          </div>
          <div>
            <h3 className="font-semibold text-foreground text-lg mb-2">Multi-SKU Parallel Training</h3>
            <p className="text-muted-foreground text-sm font-light">Train independent RL agents for hundreds of SKUs simultaneously.</p>
          </div>
          <div>
            <h3 className="font-semibold text-foreground text-lg mb-2">Human-in-the-loop</h3>
            <p className="text-muted-foreground text-sm font-light">Maintain ultimate control with manual overrides on AI-suggested orders.</p>
          </div>
        </div>

        {/* Pipeline Walkthrough */}
        <div className="w-full text-left mb-16">
          <h2 className="text-3xl font-semibold text-center mb-12">The Replenix Pipeline</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-5xl mx-auto">
            <PipelineCard 
              step="1"
              title="Upload Data"
              desc="Import your historical sales, lead times, and holding costs."
            />
            <PipelineCard 
              step="2"
              title="Modify Demand"
              desc="Adjust baselines or simulate seasonal spikes for robustness."
            />
            <PipelineCard 
              step="3"
              title="Preview Data"
              desc="Review the synthetic demand scenarios before training."
            />
            <PipelineCard 
              step="4"
              title="Train Model"
              desc="Watch the RL agent learn optimal policies via live WebSockets."
            />
            <PipelineCard 
              step="5"
              title="Evaluate"
              desc="Compare the RL agent against an Oracle and traditional rule-based methods."
            />
            <PipelineCard 
              step="6"
              title="Deploy"
              desc="Run live daily simulations with KPI tracking and ledger history."
            />
          </div>
        </div>
      </main>
    </div>
  );
}

function PipelineCard({ step, title, desc }: { step: string, title: string, desc: string }) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-card p-6 text-left transition-all duration-300 hover:border-primary/50 hover:shadow-md">
      <div className="flex items-center gap-4 mb-4">
        <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-sm">
          {step}
        </div>
        <h3 className="text-foreground text-base font-semibold tracking-wide">{title}</h3>
      </div>
      <p className="text-muted-foreground text-sm font-light leading-relaxed">{desc}</p>
    </div>
  );
}


