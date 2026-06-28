import { useState } from "react";
import { useAuth } from "@/hooks/use-auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, Package, Eye, EyeOff, ArrowRight } from "lucide-react";
import { useLocation } from "wouter";
import { ThemeToggle } from "@/components/common/ThemeToggle";

/* ---------- Animated inventory trend for the left panel ---------- */
function PanelVisual() {
  const bars = [35, 62, 48, 78, 54, 91, 67, 83, 72, 96, 80, 100];
  const maxVal = Math.max(...bars);
  return (
    <div className="w-full" aria-hidden>
      {/* Mini bar chart */}
      <div className="flex items-end gap-1.5 h-28">
        {bars.map((v, i) => (
          <div key={i} className="flex-1 rounded-sm bg-primary/25 relative overflow-hidden">
            <div
              className="absolute bottom-0 left-0 right-0 rounded-sm bg-primary transition-all duration-700"
              style={{ height: `${(v / maxVal) * 100}%`, animationDelay: `${i * 60}ms` }}
            />
          </div>
        ))}
      </div>
      {/* Labels */}
      <div className="flex items-center justify-between mt-2 text-[10px] text-muted-foreground">
        <span>Jan</span><span>Mar</span><span>Jun</span><span>Sep</span><span>Dec</span>
      </div>

      {/* Stat row */}
      <div className="grid grid-cols-3 gap-3 mt-6">
        {[
          { label: "SKUs tracked", value: "1,284" },
          { label: "Avg accuracy",  value: "94.7%" },
          { label: "Reorders today",value: "38" },
        ].map(({ label, value }) => (
          <div key={label} className="bg-muted/40 border border-border/50 rounded-xl p-3">
            <p className="font-display font-bold text-foreground text-lg tabular">{value}</p>
            <p className="text-muted-foreground text-[10px] mt-0.5 leading-tight">{label}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ============================================================ */
export default function AuthPage() {
  const { loginMutation, registerMutation, user } = useAuth();
  const [, navigate] = useLocation();
  const [mode, setMode]         = useState<"login" | "register">("login");
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName]   = useState("");
  const [showPw, setShowPw]       = useState(false);

  if (user) { navigate("/home"); return null; }

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    loginMutation.mutate({ username: email, password });
  };

  const handleRegister = (e: React.FormEvent) => {
    e.preventDefault();
    registerMutation.mutate({ username: email, password, firstName, lastName });
  };

  const isLogin     = mode === "login";
  const isPending   = loginMutation.isPending || registerMutation.isPending;
  const error       = loginMutation.error || registerMutation.error;

  return (
    <div className="min-h-dvh flex text-foreground bg-background selection:bg-primary/20 relative">
      {/* Theme toggle top-right */}
      <div className="absolute top-5 right-5 z-50">
        <ThemeToggle />
      </div>

      {/* ── LEFT PANEL — brand + visual ── */}
      <aside
        className="hidden lg:flex flex-col justify-between w-[42%] xl:w-[45%] p-12 xl:p-16 relative overflow-hidden border-r border-border/50 bg-card noise"
        aria-hidden="true"
      >
        {/* Glow blobs */}
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute top-[-15%] left-[-10%] w-80 h-80 bg-primary/8 rounded-full blur-[100px]" />
          <div className="absolute bottom-[-10%] right-[-10%] w-64 h-64 bg-primary/5 rounded-full blur-[80px]" />
        </div>

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shadow-inner-top">
            <Package className="w-4.5 h-4.5 text-primary-foreground" />
          </div>
          <span className="font-display font-bold text-xl text-foreground">Replenix</span>
        </div>

        {/* Main copy */}
        <div className="relative z-10 space-y-6">
          <div>
            <p className="text-xs font-semibold text-primary uppercase tracking-wider mb-3">Inventory intelligence</p>
            <h1 className="font-display font-extrabold text-4xl xl:text-5xl text-foreground leading-[1.08]">
              Let the model handle the reorders.
            </h1>
            <p className="text-muted-foreground mt-4 text-[15px] leading-relaxed max-w-md">
              Upload your data, train a DQN agent, and deploy it to production — all in one workflow.
            </p>
          </div>
          <PanelVisual />
        </div>

        {/* Bottom quote */}
        <div className="relative z-10 border-t border-border/40 pt-6">
          <p className="text-sm text-muted-foreground italic leading-relaxed">
            "Replenix cut our overstock by 38% in the first month — without touching our existing ERP."
          </p>
          <p className="text-xs font-semibold text-foreground mt-2">Priya S., Supply Chain Lead</p>
        </div>
      </aside>

      {/* ── RIGHT PANEL — form ── */}
      <main className="flex-1 flex flex-col justify-center px-6 sm:px-12 py-16 relative z-10">
        <div className="mx-auto w-full max-w-form">

          {/* Mobile logo */}
          <div className="flex items-center gap-2.5 mb-10 lg:hidden">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
              <Package className="w-4 h-4 text-primary-foreground" />
            </div>
            <span className="font-display font-bold text-lg text-foreground">Replenix</span>
          </div>

          {/* Heading */}
          <div className="mb-8">
            <h2 className="font-display font-bold text-3xl text-foreground">
              {isLogin ? "Welcome back" : "Create your account"}
            </h2>
            <p className="text-muted-foreground text-sm mt-2">
              {isLogin ? "Sign in to access your pipeline." : "Free to start — no credit card required."}
            </p>
          </div>

          {/* Mode toggle */}
          <div className="flex items-center p-1 bg-muted rounded-xl mb-8">
            {(["login", "register"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`flex-1 py-2 text-sm font-semibold rounded-lg transition-all duration-200 ${
                  mode === m
                    ? "bg-background text-foreground shadow-amber"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {m === "login" ? "Sign in" : "Register"}
              </button>
            ))}
          </div>

          {/* Error banner */}
          {error && (
            <div role="alert" className="mb-5 px-4 py-3 bg-destructive/10 border border-destructive/30 rounded-xl text-destructive text-sm font-medium">
              {error.message || "Authentication failed. Please check your credentials."}
            </div>
          )}

          {/* ── LOGIN FORM ── */}
          {isLogin && (
            <form onSubmit={handleLogin} className="space-y-5 animate-fade-in-up">
              <div className="space-y-1.5">
                <Label htmlFor="login-email" className="text-sm font-medium text-foreground">Email</Label>
                <Input
                  id="login-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-11 bg-background border-border focus:border-primary transition-colors"
                  placeholder="you@company.com"
                />
              </div>
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label htmlFor="login-password" className="text-sm font-medium text-foreground">Password</Label>
                  <button type="button" className="text-xs text-muted-foreground hover:text-foreground transition-colors">Forgot password?</button>
                </div>
                <div className="relative">
                  <Input
                    id="login-password"
                    type={showPw ? "text" : "password"}
                    required
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-11 bg-background border-border focus:border-primary transition-colors pr-10"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label={showPw ? "Hide password" : "Show password"}
                  >
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <Button
                type="submit"
                disabled={isPending}
                className="w-full h-11 font-semibold text-[15px] bg-primary text-primary-foreground hover:brightness-105 active:scale-[0.98] transition-all duration-200 shadow-amber group"
              >
                {isPending ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : null}
                Continue
                {!isPending && <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />}
              </Button>
            </form>
          )}

          {/* ── REGISTER FORM ── */}
          {!isLogin && (
            <form onSubmit={handleRegister} className="space-y-5 animate-fade-in-up">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <Label htmlFor="reg-first" className="text-sm font-medium text-foreground">First name</Label>
                  <Input
                    id="reg-first"
                    required
                    autoComplete="given-name"
                    value={firstName}
                    onChange={(e) => setFirstName(e.target.value)}
                    className="h-11 bg-background border-border focus:border-primary transition-colors"
                    placeholder="Alex"
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="reg-last" className="text-sm font-medium text-foreground">Last name</Label>
                  <Input
                    id="reg-last"
                    required
                    autoComplete="family-name"
                    value={lastName}
                    onChange={(e) => setLastName(e.target.value)}
                    className="h-11 bg-background border-border focus:border-primary transition-colors"
                    placeholder="Rivera"
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reg-email" className="text-sm font-medium text-foreground">Work email</Label>
                <Input
                  id="reg-email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-11 bg-background border-border focus:border-primary transition-colors"
                  placeholder="alex@company.com"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="reg-password" className="text-sm font-medium text-foreground">Password</Label>
                <div className="relative">
                  <Input
                    id="reg-password"
                    type={showPw ? "text" : "password"}
                    required
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-11 bg-background border-border focus:border-primary transition-colors pr-10"
                    placeholder="At least 8 characters"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(!showPw)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                    aria-label={showPw ? "Hide password" : "Show password"}
                  >
                    {showPw ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>
              <Button
                type="submit"
                disabled={isPending}
                className="w-full h-11 font-semibold text-[15px] bg-primary text-primary-foreground hover:brightness-105 active:scale-[0.98] transition-all duration-200 shadow-amber group"
              >
                {isPending ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
                Create account
                {!isPending && <ArrowRight className="w-4 h-4 ml-2 group-hover:translate-x-0.5 transition-transform" />}
              </Button>
              <p className="text-xs text-muted-foreground text-center">
                By creating an account, you agree to our{" "}
                <a href="#" className="underline underline-offset-2 hover:text-foreground transition-colors">Terms</a>
                {" "}and{" "}
                <a href="#" className="underline underline-offset-2 hover:text-foreground transition-colors">Privacy policy</a>.
              </p>
            </form>
          )}
        </div>
      </main>
    </div>
  );
}
