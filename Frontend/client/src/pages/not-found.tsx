import { useLocation } from "wouter";
import { Package, ArrowLeft, AlertCircle } from "lucide-react";

export default function NotFound() {
  const [, setLocation] = useLocation();

  return (
    <div className="min-h-dvh flex items-center justify-center bg-background px-6">
      {/* Ambient glow */}
      <div aria-hidden className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[400px] bg-primary/6 rounded-full blur-[120px]" />
      </div>

      <div className="relative z-10 text-center max-w-md mx-auto animate-fade-in-up">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2 mb-12">
          <div className="w-8 h-8 rounded-xl bg-primary flex items-center justify-center">
            <Package className="w-4 h-4 text-primary-foreground" />
          </div>
          <span className="font-display font-bold text-lg text-foreground">Replenix</span>
        </div>

        {/* 404 display */}
        <div className="relative mb-8">
          <p className="font-display font-extrabold text-[9rem] md:text-[11rem] leading-none text-primary/10 select-none">
            404
          </p>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-16 h-16 rounded-2xl bg-card border border-border shadow-amber flex items-center justify-center">
              <AlertCircle className="w-7 h-7 text-muted-foreground" />
            </div>
          </div>
        </div>

        <h1 className="font-display font-bold text-2xl md:text-3xl text-foreground mb-3">
          Page not found
        </h1>
        <p className="text-muted-foreground text-[15px] leading-relaxed mb-8">
          The page you're looking for doesn't exist or has been moved. Let's get you back on track.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
          <button
            onClick={() => setLocation("/home")}
            className="group inline-flex items-center gap-2 bg-primary text-primary-foreground font-semibold px-5 py-2.5 rounded-xl text-sm transition-all duration-200 hover:brightness-105 active:scale-[0.97] shadow-amber"
          >
            <ArrowLeft className="w-4 h-4 group-hover:-translate-x-0.5 transition-transform" />
            Back to dashboard
          </button>
          <button
            onClick={() => setLocation("/")}
            className="inline-flex items-center gap-2 text-sm font-medium text-muted-foreground hover:text-foreground transition-colors px-4 py-2.5"
          >
            Go to home
          </button>
        </div>
      </div>
    </div>
  );
}
