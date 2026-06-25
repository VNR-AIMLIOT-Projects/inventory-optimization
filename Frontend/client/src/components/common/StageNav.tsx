import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight, Check } from "lucide-react";
import { useLocation } from "wouter";

const STAGES = [
    { url: "/upload", label: "Upload" },
    { url: "/modify", label: "Modify" },
    { url: "/preview", label: "Preview" },
    { url: "/train", label: "Train" },
    { url: "/evaluate", label: "Evaluate" },
    { url: "/deploy", label: "Deploy" },
];

export function StageNav() {
    const [location, navigate] = useLocation();

    const currentIndex = STAGES.findIndex((s) => s.url === location);
    const prev = currentIndex > 0 ? STAGES[currentIndex - 1] : null;
    const next = currentIndex < STAGES.length - 1 ? STAGES[currentIndex + 1] : null;

    return (
        <div className="flex items-center justify-between p-2 rounded-xl mb-4 border border-border bg-card shadow-sm">
            {prev ? (
                <Button variant="outline" size="sm" className="gap-1.5" onClick={() => navigate(prev.url)}>
                    <ChevronLeft className="w-4 h-4" /> {prev.label}
                </Button>
            ) : <div className="w-[88px]" />}
            
            <div className="hidden md:flex items-center">
                {STAGES.map((s, i) => {
                    const isCompleted = i < currentIndex;
                    const isCurrent = i === currentIndex;
                    return (
                        <div key={s.url} className="flex items-center">
                            <button
                                onClick={() => navigate(s.url)}
                                className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                                    isCurrent ? "bg-primary text-primary-foreground" : 
                                    isCompleted ? "text-foreground hover:bg-muted" : "text-muted-foreground hover:bg-muted/50"
                                }`}
                            >
                                <span className={`flex items-center justify-center w-5 h-5 rounded-full text-xs ${
                                    isCurrent ? "bg-primary-foreground/20" : 
                                    isCompleted ? "bg-primary/10 text-primary" : "bg-muted"
                                }`}>
                                    {isCompleted ? <Check className="w-3 h-3" /> : i + 1}
                                </span>
                                {s.label}
                            </button>
                            {i < STAGES.length - 1 && (
                                <div className={`w-4 h-px mx-1 ${isCompleted ? "bg-primary/50" : "bg-border"}`} />
                            )}
                        </div>
                    );
                })}
            </div>

            {next ? (
                <Button size="sm" className="gap-1.5" onClick={() => navigate(next.url)}>
                    {next.label} <ChevronRight className="w-4 h-4" />
                </Button>
            ) : <div className="w-[88px]" />}
        </div>
    );
}
