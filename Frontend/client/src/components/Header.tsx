import { Bell, User, Terminal, LogOut, Settings, ChevronDown, Activity, Server, ShieldAlert, Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { healthCheck } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/hooks/use-auth";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SidebarContent } from "@/components/Sidebar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";

function getStatusBg(apiOnline: boolean | null) {
  if (apiOnline === true) return "bg-primary/10 border-primary/20";
  if (apiOnline === false) return "bg-destructive/10 border-destructive/20";
  return "bg-muted/50 border-border";
}

function getStatusDot(apiOnline: boolean | null) {
  if (apiOnline === true) return "bg-primary animate-pulse";
  if (apiOnline === false) return "bg-destructive";
  return "bg-muted-foreground animate-pulse";
}

function getStatusText(apiOnline: boolean | null) {
  if (apiOnline === true) return { text: "SYS.ONLINE", color: "text-primary" };
  if (apiOnline === false) return { text: "SYS.OFFLINE", color: "text-destructive" };
  return { text: "BOOTING...", color: "text-muted-foreground" };
}

export function Header({ title }: Readonly<{ title: React.ReactNode }>) {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const { user, logoutMutation } = useAuth();

  useEffect(() => {
    const check = async () => {
      try {
        await healthCheck();
        setApiOnline(true);
      } catch {
        setApiOnline(false);
      }
    };
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  const statusInfo = getStatusText(apiOnline);
  const usernameInitial = user?.username?.[0]?.toUpperCase() ?? "?";
  const displayName = user?.username?.toUpperCase() ?? "GUEST";

  return (
    <header className="h-16 flex items-center justify-between px-6 mb-2 glass rounded-3xl mx-4 mt-4 shrink-0 shadow-lg shadow-background/5">
      <div className="flex items-center gap-3 md:gap-4">
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden h-9 w-9 text-muted-foreground hover:text-foreground">
              <Menu className="w-5 h-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-72 p-0 border-r border-border bg-card flex flex-col glass">
            <SidebarContent />
          </SheetContent>
        </Sheet>
        
        {/* Aesthetic Title Area */}
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded-md bg-muted/50 hidden border border-border sm:flex items-center justify-center">
            <Server className="w-3.5 h-3.5 text-muted-foreground" />
          </div>
          <h1 className="font-display font-semibold text-[15px] text-foreground tracking-tight max-w-[150px] sm:max-w-none">{title}</h1>
        </div>
      </div>
      
      <div className="flex items-center gap-3">

        <ThemeToggle />

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="icon" className="relative rounded-xl border-border/50 bg-background/50 h-9 w-9 hover:bg-muted">
              <Bell className="w-4 h-4 text-foreground" />
              <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-0 rounded-2xl glass font-mono translate-y-2 shadow-2xl overflow-hidden" align="end">
            <div className="border-b border-border/50 p-3 bg-muted/40 font-bold uppercase text-xs flex items-center gap-2 text-foreground/80">
              <Terminal className="w-4 h-4 text-primary" />
              SYSTEM.LOG
            </div>
            <div className="flex flex-col text-xs bg-background/40">
              <div className="p-3 border-b border-border/20 hover:bg-muted/30 transition-colors cursor-default flex gap-3">
                <div className="mt-0.5 p-1 rounded-md bg-primary/10 border border-primary/20 shrink-0">
                   <Activity className="w-3.5 h-3.5 text-primary" />
                </div>
                <div>
                  <p className="font-bold text-foreground">RL_WORKER_POOL</p>
                  <p className="text-muted-foreground mt-1 text-[10px] leading-relaxed">MPS Hardware acceleration enabled. 8 replicas active.</p>
                  <p className="text-[9px] text-primary mt-2 font-bold tracking-wider">JUST NOW</p>
                </div>
              </div>
              <div className="p-3 hover:bg-muted/30 transition-colors cursor-default flex gap-3">
                <div className="mt-0.5 p-1 rounded-md bg-amber-500/10 border border-amber-500/20 shrink-0">
                  <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
                </div>
                <div>
                  <p className="font-bold text-foreground">TRAINING_EVAL</p>
                  <p className="text-muted-foreground mt-1 text-[10px] leading-relaxed">Greedy eval throttled to 100 intervals to conserve CPU cycles.</p>
                  <p className="text-[9px] text-muted-foreground mt-2 tracking-wider">2m AGO</p>
                </div>
              </div>
            </div>
          </PopoverContent>
        </Popover>
        
        <div className="w-px h-6 bg-border/50 mx-1 hidden sm:block" />

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="rounded-xl border-border/50 bg-background/50 hover:bg-muted flex items-center gap-2 pl-2 pr-3 h-9 transition-colors group">
              <div className="w-6 h-6 rounded-md bg-primary/10 text-primary border border-primary/30 flex items-center justify-center text-xs font-bold group-hover:bg-primary group-hover:text-primary-foreground transition-colors">
                {usernameInitial}
              </div>
              <span className="text-xs font-medium tracking-wide hidden sm:block">{displayName}</span>
              <ChevronDown className="w-3 h-3 text-muted-foreground ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 rounded-2xl glass font-mono mt-2 shadow-2xl p-1 overflow-hidden">
            <DropdownMenuLabel className="font-bold uppercase tracking-widest text-[10px] text-muted-foreground px-2 py-1.5">Access Level: root</DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-border/30 my-1" />
            <DropdownMenuItem
              className="cursor-pointer text-xs uppercase text-destructive focus:bg-destructive/10 focus:text-destructive rounded-xl m-1 transition-colors"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
            >
              <LogOut className="mr-2 h-3.5 w-3.5" />
              <span>{logoutMutation.isPending ? "Disconnecting..." : "Disconnect"}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

      </div>
    </header>
  );
}
