import { useAuth } from "@/hooks/use-auth";
import { useLocation } from "wouter";
import { useEffect } from "react";
import { ArrowRight, Activity, Database, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";

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
    <div className="min-h-screen bg-black text-white selection:bg-white/20 overflow-hidden relative flex flex-col font-sans">
      {/* Ethereal Background Elements */}
      <div className="absolute top-[-20%] left-[-10%] w-[50%] h-[50%] rounded-full bg-blue-900/10 blur-[120px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full bg-indigo-900/10 blur-[120px] pointer-events-none" />
      
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-[size:24px_24px] pointer-events-none [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]" />

      {/* Header */}
      <header className="relative z-10 p-6 flex items-center justify-between border-b border-white/5">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-white text-black flex items-center justify-center font-bold font-mono text-xl tracking-tighter">
            Rx
          </div>
          <span className="font-semibold tracking-wide text-lg text-white">REPLENIX</span>
        </div>
        <nav>
          <Button 
            variant="ghost" 
            className="text-white/70 hover:text-white hover:bg-white/10 rounded-none h-9 px-4 text-xs font-mono uppercase tracking-wider transition-colors"
            onClick={() => setLocation("/auth")}
          >
            Log In
          </Button>
        </nav>
      </header>

      {/* Main Content: Central Pillar Layout */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full text-center mt-12 mb-24">
        
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-white/10 bg-white/5 backdrop-blur-md mb-8">
          <span className="w-2 h-2 rounded-full bg-blue-500 animate-pulse" />
          <span className="text-xs font-mono text-white/70 tracking-uppercase">System Online / Beta Phase</span>
        </div>

        <h1 className="text-5xl md:text-7xl font-bold tracking-tight mb-6 bg-clip-text text-transparent bg-gradient-to-b from-white to-white/50">
          Intelligent Inventory <br className="hidden md:block" /> Optimization Pipeline
        </h1>
        
        <p className="max-w-2xl text-lg text-white/50 mb-10 font-light leading-relaxed">
          Replenix utilizes Reinforcement Learning and predictive data modeling to precisely align your supply with volatile demand. Ethereal efficiency meets utilitarian precision.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 items-center">
          <button 
            onClick={() => setLocation("/auth")}
            className="group relative px-8 py-4 bg-white text-black font-medium text-sm uppercase tracking-widest overflow-hidden transition-all hover:pr-12"
          >
            <span className="relative z-10 flex items-center gap-2">
              Initialize System
              <ArrowRight className="w-4 h-4 opacity-0 -ml-4 group-hover:opacity-100 group-hover:ml-0 transition-all duration-300" />
            </span>
            <div className="absolute inset-0 bg-gray-200 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-out" />
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
    <div className="relative group overflow-hidden border border-white/5 bg-white/[0.02] backdrop-blur-sm p-6 text-left transition-colors hover:bg-white/[0.04]">
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
      <div className="mb-4 text-blue-400 group-hover:text-blue-300 transition-colors">
        {icon}
      </div>
      <h3 className="text-white font-medium mb-2 tracking-wide">{title}</h3>
      <p className="text-sm text-white/40 leading-relaxed font-light">{desc}</p>
    </div>
  );
}
