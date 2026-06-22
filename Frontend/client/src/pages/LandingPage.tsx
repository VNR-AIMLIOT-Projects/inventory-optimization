import { useAuth } from "@/hooks/use-auth";
import { useLocation } from "wouter";
import { useEffect } from "react";
import { ArrowRight, TrendingDown, TrendingUp, Package } from "lucide-react";
import { ThemeToggle } from "@/components/common/ThemeToggle";

/* ---------- Tiny inline chart for the hero ---------- */
function HeroChart() {
  const pts = [42, 58, 45, 70, 52, 80, 62, 88, 68, 95, 75, 100];
  const w = 280, h = 96;
  const max = Math.max(...pts);
  const toX = (i: number) => (i / (pts.length - 1)) * w;
  const toY = (v: number) => h - (v / max) * h * 0.9 - 4;
  const path = pts.map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i)} ${toY(v)}`).join(" ");
  const area = [
    ...pts.map((v, i) => `${i === 0 ? "M" : "L"} ${toX(i)} ${toY(v)}`),
    `L ${w} ${h}`, `L 0 ${h}`, "Z",
  ].join(" ");

  return (
    <svg viewBox={`0 0 ${w} ${h}`} fill="none" className="w-full h-full" aria-hidden>
      <defs>
        <linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%"   stopColor="hsl(27,82%,52%)" stopOpacity="0.25" />
          <stop offset="100%" stopColor="hsl(27,82%,52%)" stopOpacity="0"    />
        </linearGradient>
      </defs>
      <path d={area} fill="url(#chartFill)" />
      <path d={path} stroke="hsl(27,82%,52%)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      {pts.map((v, i) => i === pts.length - 1 && (
        <circle key={i} cx={toX(i)} cy={toY(v)} r="4" fill="hsl(27,82%,52%)" stroke="white" strokeWidth="2" />
      ))}
    </svg>
  );
}

/* ---------- Stat pill ---------- */
function StatPill({ value, label, trend }: { value: string; label: string; trend: "up" | "down" }) {
  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-card border border-border rounded-xl shadow-amber">
      <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${trend === "up" ? "bg-success/10 text-success" : "bg-primary/10 text-primary"}`}>
        {trend === "up" ? <TrendingUp className="w-3.5 h-3.5" /> : <TrendingDown className="w-3.5 h-3.5" />}
      </div>
      <div>
        <p className="font-display font-bold text-foreground text-base leading-none tabular">{value}</p>
        <p className="text-muted-foreground text-xs mt-0.5 leading-none">{label}</p>
      </div>
    </div>
  );
}

/* ---------- Feature row item (zig-zag) ---------- */
function FeatureBlock({
  number, title, desc, stat, statLabel, flipped,
}: {
  number: string; title: string; desc: string;
  stat: string; statLabel: string; flipped?: boolean;
}) {
  return (
    <div className={`grid md:grid-cols-2 gap-12 md:gap-20 items-center ${flipped ? "md:[&>*:first-child]:order-2" : ""}`}>
      {/* Text */}
      <div>
        <span className="font-display font-bold text-primary text-5xl md:text-6xl select-none">{number}</span>
        <h3 className="font-display font-bold text-2xl md:text-3xl text-foreground mt-2 mb-4">{title}</h3>
        <p className="text-muted-foreground leading-relaxed text-[15px]">{desc}</p>
      </div>
      {/* Visual */}
      <div className="relative p-8 bg-card rounded-2xl border border-border shadow-amber flex flex-col gap-4 overflow-hidden">
        <div className="absolute top-0 right-0 w-40 h-40 bg-primary/5 rounded-full blur-2xl translate-x-16 -translate-y-16 pointer-events-none" />
        <div className="h-24 relative z-10">
          <HeroChart />
        </div>
        <div className="border-t border-border/50 pt-4 flex items-end justify-between z-10 relative">
          <div>
            <p className="font-display font-bold text-2xl text-foreground tabular">{stat}</p>
            <p className="text-muted-foreground text-xs mt-1">{statLabel}</p>
          </div>
          <span className="text-xs font-medium text-success bg-success/10 px-2 py-1 rounded-full">Live</span>
        </div>
      </div>
    </div>
  );
}

/* ============================================================ */
export default function LandingPage() {
  const { user, isLoading } = useAuth();
  const [, setLocation] = useLocation();

  useEffect(() => {
    if (!isLoading && user) setLocation("/home");
  }, [user, isLoading, setLocation]);

  if (isLoading) return null;

  return (
    <div className="min-h-dvh bg-background text-foreground flex flex-col font-sans selection:bg-primary/20">
      {/* Skip link */}
      <a href="#main-content" className="skip-to-content">Skip to content</a>

      {/* ── HEADER ── */}
      <header className="sticky top-0 z-40 px-6 py-4 flex items-center justify-between border-b border-border/60 glass">
        <a href="/" className="flex items-center gap-2.5" aria-label="Replenix home">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center shadow-inner-top">
            <Package className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-display font-bold text-lg text-foreground tracking-tight">Replenix</span>
        </a>
        <nav className="flex items-center gap-3" aria-label="Main navigation">
          <ThemeToggle />
          <button
            onClick={() => setLocation("/auth")}
            className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors duration-200 px-3 py-1.5"
          >
            Sign in
          </button>
          <button
            id="cta-header"
            onClick={() => setLocation("/auth")}
            className="group inline-flex items-center gap-2 bg-primary text-primary-foreground text-sm font-semibold px-4 py-2 rounded-xl transition-all duration-200 hover:brightness-105 active:scale-[0.97] shadow-amber"
          >
            Get started
            <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform duration-200" />
          </button>
        </nav>
      </header>

      {/* ── MAIN ── */}
      <main id="main-content" className="flex-1">

        {/* Hero */}
        <section className="relative overflow-hidden px-6 pt-20 pb-24 md:pt-28 md:pb-32 max-w-container mx-auto">
          {/* Ambient glow */}
          <div aria-hidden className="pointer-events-none absolute inset-0">
            <div className="absolute top-0 left-1/4 w-96 h-96 bg-primary/8 rounded-full blur-[120px]" />
            <div className="absolute bottom-0 right-1/4 w-72 h-72 bg-primary/5 rounded-full blur-[100px]" />
          </div>

          <div className="relative z-10 grid md:grid-cols-2 gap-12 md:gap-8 items-center">
            {/* Left — copy */}
            <div className="animate-fade-in-up">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-primary/10 border border-primary/20 rounded-full mb-6">
                <span className="w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
                <span className="text-xs font-semibold text-primary">Reinforcement learning, production-ready</span>
              </div>
              <h1 className="font-display font-extrabold text-5xl md:text-6xl lg:text-7xl text-foreground leading-[1.08] mb-6">
                Inventory that<br />
                <span className="text-primary">thinks ahead.</span>
              </h1>
              <p className="text-muted-foreground text-lg leading-relaxed mb-8 max-w-prose">
                Replenix trains a DQN agent on your sales history and deploys it live — so your reorder points adjust themselves before a stockout happens, not after.
              </p>
              <div className="flex flex-wrap items-center gap-4">
                <button
                  id="cta-hero-primary"
                  onClick={() => setLocation("/auth")}
                  className="group inline-flex items-center gap-2.5 bg-primary text-primary-foreground font-semibold px-6 py-3.5 rounded-xl text-[15px] transition-all duration-200 hover:brightness-105 active:scale-[0.97] shadow-amber-lg"
                >
                  Start for free
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform duration-200" />
                </button>
                <button
                  onClick={() => setLocation("/auth")}
                  className="text-[15px] font-medium text-muted-foreground hover:text-foreground transition-colors underline underline-offset-4 decoration-border hover:decoration-foreground"
                >
                  Sign in to existing account
                </button>
              </div>
            </div>

            {/* Right — live stats widget */}
            <div className="animate-fade-in-up delay-150 flex flex-col gap-4">
              <div className="relative bg-card border border-border rounded-2xl p-6 shadow-amber-lg overflow-hidden">
                <div aria-hidden className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-2xl translate-x-10 -translate-y-10 pointer-events-none" />
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-4">Forecast accuracy — last 30 days</p>
                <div className="h-28 mb-4">
                  <HeroChart />
                </div>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-display font-bold text-3xl text-foreground tabular">94.7%</p>
                    <p className="text-muted-foreground text-sm mt-1">mean absolute accuracy</p>
                  </div>
                  <div className="text-right">
                    <span className="inline-flex items-center gap-1 text-sm font-medium text-success bg-success/10 px-3 py-1.5 rounded-full">
                      <TrendingUp className="w-3.5 h-3.5" /> +6.2 pts
                    </span>
                  </div>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <StatPill value="$2.3M" label="capital freed from overstock" trend="down" />
                <StatPill value="3 min"  label="average reorder cycle time" trend="up"  />
              </div>
            </div>
          </div>
        </section>

        {/* How it works */}
        <section className="px-6 py-20 md:py-28 border-t border-border/50" aria-labelledby="how-it-works">
          <div className="max-w-container mx-auto">
            <div className="mb-16 md:mb-20">
              <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">How it works</p>
              <h2 id="how-it-works" className="font-display font-bold text-4xl md:text-5xl text-foreground">
                From raw data to live decisions
              </h2>
            </div>
            <div className="flex flex-col gap-20 md:gap-28">
              <FeatureBlock
                number="01"
                title="Connect your data"
                desc="Upload historical sales and inventory CSVs. Replenix parses, validates, and stages the data — no ETL pipeline to maintain."
                stat="47.2%"
                statLabel="fewer manual data corrections"
              />
              <FeatureBlock
                number="02"
                title="Train a DQN agent"
                desc="A Deep Q-Network explores your inventory environment and learns the optimal reorder policy for each SKU — without you writing a single rule."
                stat="∼8 min"
                statLabel="average training time per SKU"
                flipped
              />
              <FeatureBlock
                number="03"
                title="Deploy and watch it run"
                desc="The trained policy plugs directly into your live environment. Reorder thresholds update automatically as demand shifts."
                stat="99.1%"
                statLabel="uptime across simulated deployments"
              />
            </div>
          </div>
        </section>

        {/* CTA banner */}
        <section className="px-6 py-20 md:py-24 border-t border-border/50">
          <div className="max-w-container mx-auto">
            <div className="relative bg-primary/8 border border-primary/20 rounded-3xl px-8 py-14 md:py-20 text-center overflow-hidden">
              <div aria-hidden className="absolute inset-0 pointer-events-none">
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-96 h-40 bg-primary/10 rounded-full blur-3xl" />
              </div>
              <div className="relative z-10">
                <h2 className="font-display font-extrabold text-4xl md:text-5xl text-foreground mb-4">
                  Ready to stop guessing?
                </h2>
                <p className="text-muted-foreground text-lg mb-8 max-w-xl mx-auto">
                  Create an account and run your first RL training session in under 15 minutes.
                </p>
                <button
                  id="cta-bottom"
                  onClick={() => setLocation("/auth")}
                  className="group inline-flex items-center gap-2.5 bg-primary text-primary-foreground font-semibold px-8 py-4 rounded-xl text-[15px] transition-all duration-200 hover:brightness-105 active:scale-[0.97] shadow-amber-lg"
                >
                  Get started — it's free
                  <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform duration-200" />
                </button>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* ── FOOTER ── */}
      <footer className="border-t border-border/60 px-6 py-8">
        <div className="max-w-container mx-auto flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-primary flex items-center justify-center">
              <Package className="w-3 h-3 text-primary-foreground" />
            </div>
            <span className="font-display font-bold text-sm text-foreground">Replenix</span>
          </div>
          <p className="text-xs text-muted-foreground">
            © {new Date().getFullYear()} Replenix. All rights reserved.
          </p>
          <nav className="flex items-center gap-4 text-xs text-muted-foreground" aria-label="Footer">
            <a href="#" className="hover:text-foreground transition-colors">Privacy policy</a>
            <a href="#" className="hover:text-foreground transition-colors">Terms of service</a>
            <ThemeToggle />
          </nav>
        </div>
      </footer>
    </div>
  );
}
