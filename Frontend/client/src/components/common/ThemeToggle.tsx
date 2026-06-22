import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/hooks/use-theme";
import { cn } from "@/lib/utils";

export function ThemeToggle({ className }: { className?: string }) {
  const { theme, toggleTheme } = useTheme();
  const isDark = theme === "dark";

  return (
    <button
      onClick={toggleTheme}
      className={cn(
        "relative w-8 h-8 rounded-xl flex items-center justify-center",
        "border border-border/60 bg-background/60 backdrop-blur-sm",
        "text-muted-foreground hover:text-foreground hover:bg-muted/50",
        "transition-all duration-200 active:scale-95",
        className,
      )}
      aria-label={`Switch to ${isDark ? "light" : "dark"} mode`}
    >
      <Sun  className={cn("w-3.5 h-3.5 absolute transition-all duration-300", isDark  ? "opacity-100 scale-100" : "opacity-0 scale-50")} />
      <Moon className={cn("w-3.5 h-3.5 absolute transition-all duration-300", !isDark ? "opacity-100 scale-100" : "opacity-0 scale-50")} />
    </button>
  );
}
