import { ChevronLeft, ChevronRight, Check } from "lucide-react";
import { useLocation } from "wouter";
import { cn } from "@/lib/utils";

const STAGES = [
  { url: "/upload",   label: "Upload",   short: "01" },
  { url: "/modify",   label: "Modify",   short: "02" },
  { url: "/preview",  label: "Preview",  short: "03" },
  { url: "/train",    label: "Train",    short: "04" },
  { url: "/evaluate", label: "Evaluate", short: "05" },
  { url: "/deploy",   label: "Deploy",   short: "06" },
];

export function StageNav() {
  const [location, navigate] = useLocation();
  const currentIndex = STAGES.findIndex((s) => s.url === location);
  const prev = currentIndex > 0 ? STAGES[currentIndex - 1] : null;
  const next = currentIndex < STAGES.length - 1 ? STAGES[currentIndex + 1] : null;

  return (
    <div className="flex items-center justify-between gap-4 px-4 py-3 bg-card border border-border rounded-2xl mb-4 shadow-amber">
      {/* Prev button */}
      <button
        onClick={() => prev && navigate(prev.url)}
        disabled={!prev}
        className={cn(
          "flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl transition-all duration-200",
          prev
            ? "text-muted-foreground hover:text-foreground hover:bg-muted/50"
            : "invisible",
        )}
      >
        <ChevronLeft className="w-3.5 h-3.5" />
        {prev?.label}
      </button>

      {/* Step dots */}
      <div className="flex items-center gap-1" role="list" aria-label="Pipeline steps">
        {STAGES.map((s, i) => {
          const isDone    = i < currentIndex;
          const isActive  = i === currentIndex;
          return (
            <button
              key={s.url}
              role="listitem"
              onClick={() => navigate(s.url)}
              title={s.label}
              className="flex items-center"
              aria-current={isActive ? "step" : undefined}
            >
              <div className={cn(
                "flex items-center justify-center transition-all duration-300",
                isActive
                  ? "w-20 h-7 rounded-full bg-primary text-primary-foreground gap-1.5 text-[11px] font-bold"
                  : isDone
                  ? "w-6 h-6 rounded-full bg-success/20 text-success"
                  : "w-6 h-6 rounded-full bg-muted text-muted-foreground hover:bg-muted/70 transition-colors",
              )}>
                {isDone
                  ? <Check className="w-3 h-3" />
                  : isActive
                  ? <><span className="text-[10px] opacity-70">{s.short}</span><span>{s.label}</span></>
                  : <span className="text-[10px]">{s.short}</span>
                }
              </div>
              {i < STAGES.length - 1 && (
                <div className={cn(
                  "w-3 h-px mx-0.5 transition-colors",
                  i < currentIndex ? "bg-success/40" : "bg-border",
                )} />
              )}
            </button>
          );
        })}
      </div>

      {/* Next button */}
      <button
        onClick={() => next && navigate(next.url)}
        disabled={!next}
        className={cn(
          "flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl transition-all duration-200",
          next
            ? "bg-primary text-primary-foreground hover:brightness-105 active:scale-[0.97] shadow-amber"
            : "invisible",
        )}
      >
        {next?.label}
        <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
