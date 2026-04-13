import { useLocation } from "wouter";
import { ArrowRight, Database, Settings2, Cpu, Activity, Rocket } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";

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
  const [, setLocation] = useLocation();
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-black text-white font-sans selection:bg-white/20">
      
      {/* Background Ambience */}
      <div className="fixed inset-0 pointer-events-none z-0">
        <div className="absolute top-[20%] left-[20%] w-[40%] h-[40%] rounded-full bg-blue-900/5 blur-[100px]" />
        <div className="absolute top-[60%] right-[20%] w-[30%] h-[30%] rounded-full bg-purple-900/5 blur-[100px]" />
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff05_1px,transparent_1px),linear-gradient(to_bottom,#ffffff05_1px,transparent_1px)] bg-[size:32px_32px] [mask-image:radial-gradient(ellipse_80%_60%_at_50%_40%,#000_80%,transparent_100%)]" />
      </div>

      <header className="relative z-10 p-6 border-b border-white/5 flex items-center justify-between bg-black/50 backdrop-blur-md sticky top-0">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-white text-black flex items-center justify-center font-bold font-mono text-xl tracking-tighter">
            Rx
          </div>
          <span className="font-semibold tracking-wide text-lg">DASHBOARD</span>
        </div>
        <div className="flex items-center gap-4 text-sm font-mono text-white/50">
          <span>OPERATOR: {user?.username}</span>
          <span className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
        </div>
      </header>

      <main className="relative z-10 max-w-5xl mx-auto px-6 py-16">
        
        <div className="mb-16 border-l-2 border-blue-500/50 pl-6 py-2">
          <h1 className="text-4xl font-light tracking-tight mb-4">
            System <span className="font-bold">Architecture</span>
          </h1>
          <p className="text-white/50 text-lg max-w-2xl font-light leading-relaxed">
            Welcome to the Replenix Control Center. Follow the sequential pipeline to train, evaluate, and deploy Reinforcement Learning models tailored to your inventory dynamics.
          </p>
        </div>

        {/* Pipeline Visualization */}
        <div className="relative">
          {/* Vertical connecting line */}
          <div className="absolute left-6 top-10 bottom-10 w-px bg-gradient-to-b from-blue-500/50 via-white/10 to-transparent hidden md:block" />

          <div className="flex flex-col gap-8">
            {PIPELINE_STEPS.map((step, idx) => (
              <div key={idx} className="relative flex flex-col md:flex-row gap-6 md:gap-12 md:items-center group">
                {/* Node marker */}
                <div className="hidden md:flex relative z-10 w-12 h-12 bg-black border border-white/10 rounded-none items-center justify-center shadow-[0_0_15px_rgba(255,255,255,0.05)] group-hover:border-blue-400 group-hover:shadow-[0_0_20px_rgba(59,130,246,0.3)] transition-all shrink-0">
                  <step.icon className="w-5 h-5 text-white/70 group-hover:text-blue-400" />
                </div>

                {/* Card */}
                <div className="flex-1 bg-white/[0.02] border border-white/5 p-6 backdrop-blur-sm group-hover:bg-white/[0.04] group-hover:border-white/10 transition-colors">
                  <div className="flex items-center gap-4 mb-3 md:hidden">
                    <step.icon className="w-5 h-5 text-blue-400" />
                    <h3 className="text-xl font-medium tracking-wide">{step.title}</h3>
                  </div>
                  <h3 className="hidden md:block text-xl font-medium tracking-wide mb-2 text-white/90 group-hover:text-white transition-colors">{step.title}</h3>
                  <p className="text-white/50 font-light leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-24 border-t border-white/5 pt-12 flex justify-center">
          <button 
            onClick={() => setLocation("/upload")}
            className="group relative inline-flex items-center gap-4 bg-white text-black px-10 py-5 text-sm font-bold tracking-widest uppercase overflow-hidden"
          >
            <div className="absolute inset-x-0 bottom-0 h-1 bg-blue-500 scale-x-0 group-hover:scale-x-100 origin-left transition-transform duration-300" />
            <span className="relative z-10">Commence Pipeline</span>
            <ArrowRight className="w-5 h-5 relative z-10 group-hover:translate-x-1 transition-transform" />
          </button>
        </div>

      </main>
    </div>
  );
}
