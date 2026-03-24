import { Bell, User, Terminal, LogOut, Settings, ChevronDown, Activity, Server, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { healthCheck } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/hooks/use-auth";
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

export function Header({ title }: Readonly<{ title: string }>) {
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
    <header className="h-16 flex items-center justify-between px-6 border-b border-border/50 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-40 font-mono">
      <div className="flex items-center gap-4">
        <Server className="w-5 h-5 text-muted-foreground" />
        <h1 className="font-bold text-lg text-foreground tracking-widest uppercase">{title}</h1>
      </div>
      
      <div className="flex items-center gap-4">
        <div className={`flex items-center gap-2 px-3 py-1 border rounded-none ${getStatusBg(apiOnline)}`}>
          <div className={`w-2 h-2 rounded-none ${getStatusDot(apiOnline)}`} />
          <span className={`text-[10px] font-bold uppercase tracking-widest ${statusInfo.color}`}>
            {statusInfo.text}
          </span>
        </div>
        
        <div className="border-r border-border h-6 mx-2 hidden sm:block" />
        
        <ThemeToggle />

        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="icon" className="relative rounded-none border-border h-9 w-9">
              <Bell className="w-4 h-4 text-foreground" />
              <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-none bg-primary animate-pulse" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-0 rounded-none border-border font-mono translate-y-2 translate-x-4 shadow-[4px_4px_0_0_rgba(0,0,0,1)] dark:shadow-[4px_4px_0_0_rgba(255,255,255,0.1)]" align="end">
            <div className="border-b border-border p-3 bg-muted/30 font-bold uppercase text-xs flex items-center gap-2">
              <Terminal className="w-4 h-4" />
              SYSTEM.LOG
            </div>
            <div className="flex flex-col text-xs">
              <div className="p-3 border-b border-border/50 hover:bg-muted/50 cursor-default flex gap-3">
                <Activity className="w-4 h-4 text-primary mt-0.5" />
                <div>
                  <p className="font-bold text-foreground">RL_WORKER_POOL</p>
                  <p className="text-muted-foreground mt-1 text-[10px]">MPS Hardware acceleration enabled. 8 replicas active.</p>
                  <p className="text-[10px] text-muted-foreground mt-2 opacity-70">JUST NOW</p>
                </div>
              </div>
              <div className="p-3 border-b border-border/50 hover:bg-muted/50 cursor-default flex gap-3">
                <ShieldAlert className="w-4 h-4 text-amber-500 mt-0.5" />
                <div>
                  <p className="font-bold text-foreground">TRAINING_EVAL</p>
                  <p className="text-muted-foreground mt-1 text-[10px]">Greedy eval throttled to 100 intervals to conserve CPU cycles.</p>
                  <p className="text-[10px] text-muted-foreground mt-2 opacity-70">2m AGO</p>
                </div>
              </div>
            </div>
          </PopoverContent>
        </Popover>
        
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" className="rounded-none border-border flex items-center gap-2 pl-2 pr-3 h-9">
              <div className="w-6 h-6 bg-primary/20 text-primary border border-primary/50 flex items-center justify-center text-xs font-bold">
                {usernameInitial}
              </div>
              <span className="text-xs font-bold uppercase tracking-widest hidden sm:block">{displayName}</span>
              <ChevronDown className="w-3 h-3 text-muted-foreground ml-1" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 rounded-none border-border font-mono mt-2 shadow-[4px_4px_0_0_rgba(0,0,0,1)] dark:shadow-[4px_4px_0_0_rgba(255,255,255,0.1)]">
            <DropdownMenuLabel className="font-bold uppercase tracking-widest text-xs">Access Level: root</DropdownMenuLabel>
            <DropdownMenuSeparator className="bg-border" />
            <DropdownMenuItem className="cursor-pointer text-xs uppercase focus:bg-primary/20 focus:text-primary rounded-none">
              <Settings className="mr-2 h-4 w-4" />
              <span>Preferences</span>
            </DropdownMenuItem>
            <DropdownMenuItem className="cursor-pointer text-xs uppercase focus:bg-primary/20 focus:text-primary rounded-none">
              <Terminal className="mr-2 h-4 w-4" />
              <span>Shell Access</span>
            </DropdownMenuItem>
            <DropdownMenuSeparator className="bg-border" />
            <DropdownMenuItem
              className="cursor-pointer text-xs uppercase text-destructive focus:bg-destructive/10 focus:text-destructive rounded-none"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
            >
              <LogOut className="mr-2 h-4 w-4" />
              <span>{logoutMutation.isPending ? "Disconnecting..." : "Disconnect"}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>

      </div>
    </header>
  );
}
