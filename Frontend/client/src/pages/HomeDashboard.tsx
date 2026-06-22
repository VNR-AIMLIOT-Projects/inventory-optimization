import { useLocation } from "wouter";
import {
  Upload, Wand2, Eye, Brain, BarChart3, Rocket, ArrowRight, CheckCircle2, Clock, CircleDot,
} from "lucide-react";
import { Sidebar } from "@/components/common/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { Header } from "@/components/common/Header";
import { useAuth } from "@/hooks/use-auth";

/* ---------- Pipeline step definition ---------- */
const STEPS = [
  {
    icon: Upload,
    label: "Upload",
    description: "Load raw sales and inventory CSV files",
    url: "/upload",
    status: "ready" as const,
  },
  {
    icon: Wand2,
    label: "Modify",
    description: "Apply demand shaping and scenario noise",
    url: "/modify",
    status: "ready" as const,
  },
  {
    icon: Eye,
    label: "Preview",
    description: "Visualize demand patterns and outliers",
    url: "/preview",
    status: "ready" as const,
  },
  {
    icon: Brain,
    label: "Train",
    description: "Run DQN agent training episodes",
    url: "/train",
    status: "ready" as const,
  },
  {
    icon: BarChart3,
    label: "Evaluate",
    description: "Compare RL vs rule-based vs oracle baselines",
    url: "/evaluate",
    status: "ready" as const,
  },
  {
    icon: Rocket,
    label: "Deploy",
    description: "Push the trained policy to the live environment",
    url: "/deploy",
    status: "ready" as const,
  },
];

/* ---------- Quick stat ---------- */
function QuickStat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="flex flex-col gap-0.5 p-5 bg-card border border-border rounded-2xl shadow-amber">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{label}</p>
      <p className="font-display font-bold text-2xl text-foreground tabular mt-1">{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

/* ---------- Step card ---------- */
function StepCard({
  step, index, isFirst, onClick,
}: {
  step: typeof STEPS[number];
  index: number;
  isFirst: boolean;
  onClick: () => void;
}) {
  const Icon = step.icon;
  const statusIcon =
    step.status === "done"    ? <CheckCircle2 className="w-3.5 h-3.5 text-success" /> :
    step.status === "active"  ? <CircleDot    className="w-3.5 h-3.5 text-primary animate-pulse" /> :
                                <Clock        className="w-3.5 h-3.5 text-muted-foreground" />;

  return (
    <button
      onClick={onClick}
      className={cn(
        "group relative flex flex-col gap-4 p-6 rounded-2xl border text-left transition-all duration-200",
        "hover:border-primary/40 hover:shadow-amber-lg hover:-translate-y-0.5 active:scale-[0.98]",
        "animate-fade-in-up",
        `delay-${index * 75}`,
        isFirst
          ? "bg-primary/6 border-primary/25"
          : "bg-card border-border shadow-amber",
      )}
      aria-label={`Go to ${step.label}`}
    >
      {/* Step number + status */}
      <div className="flex items-start justify-between">
        <div className={cn(
          "w-10 h-10 rounded-xl flex items-center justify-center transition-colors duration-200",
          isFirst ? "bg-primary/20 text-primary group-hover:bg-primary group-hover:text-primary-foreground"
                  : "bg-muted text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary",
        )}>
          <Icon className="w-4.5 h-4.5" />
        </div>
        <div className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
          {statusIcon}
          <span className="uppercase tracking-wide">Ready</span>
        </div>
      </div>

      {/* Content */}
      <div>
        <p className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest mb-1">
          Step {index + 1}
        </p>
        <h3 className="font-display font-semibold text-lg text-foreground">{step.label}</h3>
        <p className="text-sm text-muted-foreground mt-1 leading-relaxed">{step.description}</p>
      </div>

      {/* Arrow */}
      <div className="flex items-center gap-1.5 text-xs font-semibold text-primary opacity-0 group-hover:opacity-100 transition-opacity duration-200 -mt-1">
        Open <ArrowRight className="w-3 h-3 group-hover:translate-x-0.5 transition-transform" />
      </div>
    </button>
  );
}

/* ============================================================ */
export default function HomeDashboard() {
  const { isCollapsed } = useSidebar();
  const [, setLocation] = useLocation();
  const { user } = useAuth();

  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const firstName = user?.firstName || user?.username?.split("@")[0] || "there";

  return (
    <div className="flex min-h-dvh bg-background text-foreground font-sans selection:bg-primary/20">
      <Sidebar />

      <main
        className={cn(
          "flex-1 flex flex-col relative z-10 transition-all duration-300 ease-spring",
          isCollapsed ? "lg:ml-[5.5rem]" : "lg:ml-[17rem]",
        )}
      >
        <Header title="Control center" />

        <div className="px-6 pb-20 pt-8 max-w-container mx-auto w-full">

          {/* ── Greeting ── */}
          <div className="mb-10 animate-fade-in-up">
            <h1 className="font-display font-bold text-3xl md:text-4xl text-foreground">
              {greeting}, <span className="text-primary capitalize">{firstName}.</span>
            </h1>
            <p className="text-muted-foreground mt-2 text-[15px]">
              Your Reinforcement Learning pipeline is ready. Choose a step to begin.
            </p>
          </div>

          {/* ── Quick stats ── */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12 animate-fade-in-up delay-75">
            <QuickStat label="Pipeline steps"   value="6"      sub="Upload → Deploy" />
            <QuickStat label="SKUs available"   value="—"      sub="Upload data to start" />
            <QuickStat label="Last training"    value="—"      sub="No runs yet" />
            <QuickStat label="Active policy"    value="None"   sub="Not deployed" />
          </div>

          {/* ── Pipeline grid ── */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-semibold text-xl text-foreground">Pipeline steps</h2>
              <span className="text-xs text-muted-foreground">Run in sequence for best results</span>
            </div>

            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {STEPS.map((step, i) => (
                <StepCard
                  key={step.url}
                  step={step}
                  index={i}
                  isFirst={i === 0}
                  onClick={() => setLocation(step.url)}
                />
              ))}
            </div>
          </div>

          {/* ── CTA strip ── */}
          <div className="mt-10 p-6 bg-primary/6 border border-primary/20 rounded-2xl flex flex-col sm:flex-row items-start sm:items-center gap-4 sm:gap-6 animate-fade-in-up delay-450">
            <div className="flex-1">
              <h3 className="font-display font-semibold text-foreground">Ready to run the full pipeline?</h3>
              <p className="text-sm text-muted-foreground mt-1">Start with Step 1 and follow through to deploy your first RL policy.</p>
            </div>
            <button
              onClick={() => setLocation("/upload")}
              className="group shrink-0 inline-flex items-center gap-2.5 bg-primary text-primary-foreground font-semibold px-5 py-2.5 rounded-xl text-sm transition-all duration-200 hover:brightness-105 active:scale-[0.97] shadow-amber whitespace-nowrap"
            >
              Start from step 1
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
