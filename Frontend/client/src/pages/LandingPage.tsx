import { useAuth } from "@/hooks/use-auth";
import { useLocation } from "wouter";
import { useEffect } from "react";
import { ArrowRight, BarChart3, Box, ShieldCheck, Zap } from "lucide-react";
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
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto w-full text-center mt-16 mb-24 animate-in fade-in duration-700">
        
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-secondary text-secondary-foreground text-xs font-semibold uppercase tracking-widest mb-8 border border-border">
          <Zap className="w-3 h-3 text-primary" />
          The Future of Inventory
        </div>

        <h1 className="text-5xl md:text-7xl font-light tracking-tight mb-8 text-foreground">
          Inventory optimization, <br className="hidden md:block" />
          <span className="font-bold">automated by AI.</span>
        </h1>
        
        <p className="max-w-2xl text-lg md:text-xl text-muted-foreground mb-12 font-light leading-relaxed">
          Replenix removes the guesswork from supply chain management. By predicting demand spikes and adjusting stock levels automatically, you avoid stockouts and reduce wasted capital.
        </p>

        <div className="flex flex-col sm:flex-row gap-6 items-center">
          <Button 
            size="lg"
            onClick={() => setLocation("/auth")}
            className="group px-8 text-base font-bold tracking-wide uppercase h-14"
          >
            Start Managing
            <ArrowRight className="ml-2 w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </Button>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-32 w-full">
          <FeatureCard 
            icon={<BarChart3 className="w-6 h-6" />}
            title="Smart Forecasting"
            desc="Our AI learns your sales patterns to anticipate exactly what you need, exactly when you need it."
          />
          <FeatureCard 
            icon={<ShieldCheck className="w-6 h-6" />}
            title="Prevent Stockouts"
            desc="Automatically adjust reorder points to ensure your best-selling items never run dry."
          />
          <FeatureCard 
            icon={<Box className="w-6 h-6" />}
            title="Reduce Excess"
            desc="Free up cash flow by keeping inventory lean without sacrificing customer satisfaction."
          />
        </div>
      </main>
    </div>
  );
}

function FeatureCard({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) {
  return (
    <div className="group relative overflow-hidden rounded-xl border border-border bg-card p-8 text-left transition-all duration-300 hover:border-primary/50 hover:shadow-md">
      <div className="mb-6 w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary transition-transform duration-300 group-hover:scale-110">
        {icon}
      </div>
      <h3 className="text-foreground text-lg font-medium tracking-wide mb-3">{title}</h3>
      <p className="text-muted-foreground font-light leading-relaxed">{desc}</p>
    </div>
  );
}
