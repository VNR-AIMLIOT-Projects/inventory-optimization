import { Button } from "@/components/ui/button";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useLocation } from "wouter";

const STAGES = [
    { url: "/", label: "Upload" },
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
        <div className="flex items-center justify-between glass p-2 rounded-2xl mb-2 backdrop-blur-3xl shadow-lg border-white/5 bg-background/20">
            {prev ? (
                <Button variant="outline" size="sm" className="gap-1.5 border-border/50 hover:bg-muted" onClick={() => navigate(prev.url)}>
                    <ChevronLeft className="w-4 h-4" /> {prev.label}
                </Button>
            ) : <div />}
            <div className="flex items-center gap-1.5">
                {STAGES.map((s, i) => (
                    <button
                        key={s.url}
                        onClick={() => navigate(s.url)}
                        className={`w-2 h-2 rounded-full transition-all ${i === currentIndex
                                ? "bg-primary w-5"
                                : "bg-muted-foreground/30 hover:bg-muted-foreground/50"
                            }`}
                        title={s.label}
                    />
                ))}
            </div>
            {next ? (
                <Button size="sm" className="gap-1.5" onClick={() => navigate(next.url)}>
                    {next.label} <ChevronRight className="w-4 h-4" />
                </Button>
            ) : <div />}
        </div>
    );
}
