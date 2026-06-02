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
    <div className="min-h-screen bg-[#0a0a0f] text-slate-100 overflow-hidden relative flex flex-col font-sans selection:bg-indigo-500/30">
      
      {/* Animated Background Gradients */}
      <div className="absolute top-[-10%] left-[-10%] w-[40%] h-[40%] rounded-full bg-indigo-600/20 blur-[120px] mix-blend-screen animate-pulse pointer-events-none" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] rounded-full bg-purple-600/10 blur-[150px] mix-blend-screen pointer-events-none" />
      <div className="absolute top-[40%] left-[60%] w-[30%] h-[30%] rounded-full bg-blue-500/10 blur-[100px] mix-blend-screen animate-pulse delay-1000 pointer-events-none" />
      
      {/* Subtle grid pattern */}
      <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:32px_32px] pointer-events-none [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)]" />

      {/* Header */}
      <header className="relative z-10 p-6 flex items-center justify-between bg-black/20 backdrop-blur-xl border-b border-white/5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 p-[1px] shadow-lg shadow-indigo-500/20">
            <div className="w-full h-full bg-[#0a0a0f]/80 rounded-xl flex items-center justify-center backdrop-blur-sm">
              <Box className="w-5 h-5 text-indigo-400" />
            </div>
          </div>
          <span className="font-bold tracking-wider text-xl text-white bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">REPLENIX</span>
        </div>
        <nav className="flex items-center gap-4">
          <ThemeToggle />
          <Button 
            variant="ghost" 
            className="text-slate-300 hover:text-white hover:bg-white/10 rounded-full h-10 px-6 text-sm font-medium tracking-wide transition-all border border-transparent hover:border-white/10"
            onClick={() => setLocation("/auth")}
          >
            Sign In
          </Button>
        </nav>
      </header>

      {/* Main Content */}
      <main className="relative z-10 flex-1 flex flex-col items-center justify-center px-4 sm:px-6 lg:px-8 max-w-6xl mx-auto w-full text-center mt-16 mb-24">
        
        {/* Badge */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-semibold uppercase tracking-widest mb-8 backdrop-blur-sm transform transition-transform hover:scale-105 cursor-default">
          <Zap className="w-3 h-3 text-indigo-400 fill-indigo-400/50" />
          The Future of Inventory
        </div>

        <h1 className="text-5xl md:text-7xl font-extrabold tracking-tight mb-8 text-white">
          Inventory optimization, <br className="hidden md:block" />
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-indigo-400 via-purple-400 to-blue-400 drop-shadow-sm">
            automated by AI.
          </span>
        </h1>
        
        <p className="max-w-2xl text-lg md:text-xl text-slate-400 mb-12 font-light leading-relaxed">
          Replenix removes the guesswork from supply chain management. By predicting demand spikes and adjusting stock levels automatically, you avoid stockouts and reduce wasted capital.
        </p>

        <div className="flex flex-col sm:flex-row gap-6 items-center">
          <button 
            onClick={() => setLocation("/auth")}
            className="group relative px-8 py-4 bg-white text-black font-semibold text-sm shadow-xl shadow-white/10 overflow-hidden transition-all hover:scale-105 active:scale-95 rounded-2xl flex items-center justify-center gap-2 w-full sm:w-auto"
          >
            <span>Start Managing</span>
            <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

        {/* Feature Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mt-32 w-full">
          <FeatureCard 
            icon={<BarChart3 className="w-6 h-6" />}
            title="Smart Forecasting"
            desc="Our AI learns your sales patterns to anticipate exactly what you need, exactly when you need it."
            color="indigo"
          />
          <FeatureCard 
            icon={<ShieldCheck className="w-6 h-6" />}
            title="Prevent Stockouts"
            desc="Automatically adjust reorder points to ensure your best-selling items never run dry."
            color="purple"
          />
          <FeatureCard 
            icon={<Box className="w-6 h-6" />}
            title="Reduce Excess"
            desc="Free up cash flow by keeping inventory lean without sacrificing customer satisfaction."
            color="blue"
          />
        </div>
      </main>
    </div>
  );
}

function FeatureCard({ icon, title, desc, color }: { icon: React.ReactNode, title: string, desc: string, color: 'indigo' | 'purple' | 'blue' }) {
  const colorMap = {
    indigo: "from-indigo-500/20 to-transparent border-indigo-500/10 text-indigo-400",
    purple: "from-purple-500/20 to-transparent border-purple-500/10 text-purple-400",
    blue: "from-blue-500/20 to-transparent border-blue-500/10 text-blue-400",
  };

  return (
    <div className="group relative overflow-hidden rounded-3xl border border-white/5 bg-[#12121a]/80 backdrop-blur-xl p-8 text-left transition-all duration-300 hover:bg-[#151520] hover:border-white/10 hover:-translate-y-1 hover:shadow-2xl hover:shadow-black/50">
      <div className={`absolute top-0 left-0 w-full h-32 bg-gradient-to-b opacity-0 group-hover:opacity-100 transition-opacity duration-500 ${colorMap[color].split(' ').slice(0,2).join(' ')} pointer-events-none`} />
      
      <div className={`mb-6 w-12 h-12 rounded-2xl bg-white/5 border flex items-center justify-center transition-transform duration-300 group-hover:scale-110 ${colorMap[color].split(' ').slice(2).join(' ')}`}>
        {icon}
      </div>
      <h3 className="text-white text-lg font-semibold mb-3 tracking-wide relative z-10">{title}</h3>
      <p className="text-sm text-slate-400 leading-relaxed font-light relative z-10 group-hover:text-slate-300 transition-colors">{desc}</p>
    </div>
  );
}
