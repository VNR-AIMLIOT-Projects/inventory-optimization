import { Bell, User, Terminal, LogOut, Settings, ChevronDown, Activity, Server, ShieldAlert, Menu } from "lucide-react";
import { Link } from "wouter";
import { useEffect, useState } from "react";
import { io } from "socket.io-client";
import { healthCheck } from "@/lib/api";
import { ThemeToggle } from "@/components/ThemeToggle";
import { useAuth } from "@/hooks/use-auth";
import { useSidebar } from "@/hooks/use-sidebar";
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

interface Notification {
  type: string;
  sku?: string;
  quantity_deducted?: number;
  timestamp?: string;
  status?: string;
  message?: string;
}

export function Header({ title }: Readonly<{ title: React.ReactNode }>) {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [hasUnread, setHasUnread] = useState(false);
  const { user, logoutMutation } = useAuth();
  const { toggleSidebar } = useSidebar();

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

    const socket = io();
    socket.on("notification", (data: Notification) => {
      setNotifications((prev) => [data, ...prev].slice(0, 10));
      setHasUnread(true);
    });

    return () => {
      clearInterval(interval);
      socket.disconnect();
    };
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
        
        {/* Desktop Sidebar Toggle */}
        <Button onClick={toggleSidebar} variant="ghost" size="icon" className="hidden lg:flex h-9 w-9 text-muted-foreground hover:text-foreground">
          <Menu className="w-5 h-5" />
        </Button>

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

        <Popover onOpenChange={(open) => { if (open) setHasUnread(false); }}>
          <PopoverTrigger asChild>
            <Button variant="outline" size="icon" className="relative rounded-xl border-border/50 bg-background/50 h-9 w-9 hover:bg-muted">
              <Bell className="w-4 h-4 text-foreground" />
              {hasUnread && (
                <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              )}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-80 p-0 rounded-2xl glass font-mono translate-y-2 shadow-2xl overflow-hidden" align="end">
            <div className="border-b border-border/50 p-3 bg-muted/40 font-bold uppercase text-xs flex items-center gap-2 text-foreground/80">
              <Terminal className="w-4 h-4 text-primary" />
              SYSTEM.LOG
            </div>
            <div className="flex flex-col text-xs bg-background/40 max-h-[300px] overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-6 text-center text-muted-foreground flex items-center justify-center">
                  <span className="text-[10px] tracking-widest uppercase">System nominal. No events.</span>
                </div>
              ) : (
                notifications.map((notif, idx) => (
                  <div key={idx} className="p-3 border-b border-border/20 hover:bg-muted/30 transition-colors cursor-default flex gap-3">
                    <div className={`mt-0.5 p-1 rounded-md border shrink-0 ${notif.type === 'inventory_update' ? 'bg-primary/10 border-primary/20' : 'bg-amber-500/10 border-amber-500/20'}`}>
                      {notif.type === 'inventory_update' ? (
                         <Activity className="w-3.5 h-3.5 text-primary" />
                      ) : (
                         <ShieldAlert className="w-3.5 h-3.5 text-amber-500" />
                      )}
                    </div>
                    <div>
                      <p className="font-bold text-foreground">{notif.type.toUpperCase()}</p>
                      <p className="text-muted-foreground mt-1 text-[10px] leading-relaxed">
                        {notif.type === 'inventory_update' 
                          ? `ERP sale recorded. Deducted ${notif.quantity_deducted} units for SKU ${notif.sku}.` 
                          : notif.message || "System event occurred."}
                      </p>
                      <p className="text-[9px] text-primary mt-2 font-bold tracking-wider">
                        {notif.timestamp ? new Date(notif.timestamp).toLocaleTimeString() : "JUST NOW"}
                      </p>
                    </div>
                  </div>
                ))
              )}
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
            <Link href="/profile">
              <DropdownMenuItem className="cursor-pointer text-xs focus:bg-muted/50 rounded-xl m-1 transition-colors">
                <User className="mr-2 h-3.5 w-3.5" />
                <span>My Profile</span>
              </DropdownMenuItem>
            </Link>
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
