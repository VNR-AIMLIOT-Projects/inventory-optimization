import { Bell, User, LogOut, ChevronDown, Wifi, WifiOff, Loader, Menu } from "lucide-react";
import { Link } from "wouter";
import { useEffect, useState } from "react";
import { io } from "socket.io-client";
import { healthCheck } from "@/lib/api";
import { ThemeToggle } from "@/components/common/ThemeToggle";
import { useAuth } from "@/hooks/use-auth";
import { useSidebar } from "@/hooks/use-sidebar";
import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
import { SidebarContent } from "@/components/common/Sidebar";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Popover, PopoverContent, PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface Notification {
  type: string;
  sku?: string;
  quantity_deducted?: number;
  timestamp?: string;
  status?: string;
  message?: string;
}

/* ---------- API status badge ---------- */
function StatusBadge({ status }: { status: boolean | null }) {
  if (status === null) return (
    <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground">
      <Loader className="w-3 h-3 animate-spin" /> Connecting
    </span>
  );
  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 text-[10px] font-semibold",
      status ? "text-success" : "text-destructive",
    )}>
      {status
        ? <><span className="w-1.5 h-1.5 rounded-full bg-success inline-block animate-pulse" />Live</>
        : <><WifiOff className="w-3 h-3" />Offline</>
      }
    </span>
  );
}

/* ============================================================ */
export function Header({ title }: Readonly<{ title: React.ReactNode }>) {
  const [apiOnline, setApiOnline]       = useState<boolean | null>(null);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [hasUnread, setHasUnread]       = useState(false);
  const { user, logoutMutation }        = useAuth();
  const { toggleSidebar }               = useSidebar();

  useEffect(() => {
    const check = async () => {
      try   { await healthCheck(); setApiOnline(true);  }
      catch { setApiOnline(false); }
    };
    check();
    const interval = setInterval(check, 15_000);

    const socket = io({ transports: ["websocket"] });
    socket.on("notification", (data: Notification) => {
      setNotifications((prev) => [data, ...prev].slice(0, 10));
      setHasUnread(true);
    });

    return () => { clearInterval(interval); socket.disconnect(); };
  }, []);

  const displayName = user?.firstName
    ? `${user.firstName}${user.lastName ? " " + user.lastName : ""}`
    : user?.username?.split("@")[0] ?? "Guest";
  const initial = displayName[0]?.toUpperCase() ?? "?";

  return (
    <header className="h-14 flex items-center justify-between px-4 mb-2 glass rounded-2xl mx-4 mt-4 shrink-0 shadow-amber">
      {/* Left: menu + title */}
      <div className="flex items-center gap-2.5">
        {/* Mobile sheet */}
        <Sheet>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden h-8 w-8 text-muted-foreground hover:text-foreground rounded-lg">
              <Menu className="w-4 h-4" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-[16.5rem] p-0 border-r border-border bg-card flex flex-col glass">
            <SidebarContent />
          </SheetContent>
        </Sheet>

        {/* Desktop sidebar toggle */}
        <button
          onClick={toggleSidebar}
          className="hidden lg:flex h-8 w-8 items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors duration-200"
          aria-label="Toggle sidebar"
        >
          <Menu className="w-4 h-4" />
        </button>

        {/* Title + status */}
        <div className="flex items-center gap-2.5">
          <h1 className="font-display font-semibold text-[15px] text-foreground">{title}</h1>
          <div className="hidden sm:block h-3 w-px bg-border/60" />
          <StatusBadge status={apiOnline} />
        </div>
      </div>

      {/* Right: actions */}
      <div className="flex items-center gap-2">
        <ThemeToggle />

        {/* Notifications */}
        <Popover onOpenChange={(open) => { if (open) setHasUnread(false); }}>
          <PopoverTrigger asChild>
            <button
              className="relative h-8 w-8 flex items-center justify-center rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors duration-200"
              aria-label="Notifications"
            >
              <Bell className="w-4 h-4" />
              {hasUnread && (
                <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full bg-primary animate-pulse" />
              )}
            </button>
          </PopoverTrigger>
          <PopoverContent
            className="w-80 p-0 rounded-2xl glass shadow-amber-lg overflow-hidden"
            align="end"
            sideOffset={8}
          >
            <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
              <p className="text-sm font-semibold text-foreground">Notifications</p>
              {hasUnread && (
                <span className="text-[10px] font-semibold text-primary bg-primary/10 px-2 py-0.5 rounded-full">New</span>
              )}
            </div>
            <div className="max-h-72 overflow-y-auto divide-y divide-border/30">
              {notifications.length === 0 ? (
                <div className="px-4 py-8 text-center">
                  <Bell className="w-6 h-6 text-muted-foreground/40 mx-auto mb-2" />
                  <p className="text-sm text-muted-foreground">No notifications yet</p>
                  <p className="text-xs text-muted-foreground/60 mt-1">Events will appear here as your pipeline runs.</p>
                </div>
              ) : (
                notifications.map((n, i) => (
                  <div key={i} className="px-4 py-3 hover:bg-muted/30 transition-colors">
                    <div className="flex items-start gap-3">
                      <div className={cn(
                        "w-6 h-6 rounded-lg flex items-center justify-center shrink-0 mt-0.5",
                        n.type === "inventory_update"
                          ? "bg-primary/10 text-primary"
                          : "bg-amber-500/10 text-amber-500",
                      )}>
                        <Bell className="w-3 h-3" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-foreground capitalize">
                          {n.type.replace(/_/g, " ")}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
                          {n.type === "inventory_update"
                            ? `Sale recorded — ${n.quantity_deducted} units deducted for SKU ${n.sku}.`
                            : n.message ?? "System event occurred."}
                        </p>
                        <p className="text-[10px] text-muted-foreground/60 mt-1 font-mono">
                          {n.timestamp ? new Date(n.timestamp).toLocaleTimeString() : "Just now"}
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </PopoverContent>
        </Popover>

        {/* User menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button className="flex items-center gap-2 h-8 pl-1.5 pr-2.5 rounded-xl border border-border/50 bg-background/50 hover:bg-muted/50 transition-colors duration-200 group">
              <div className="w-5.5 h-5.5 w-6 h-6 rounded-lg bg-primary/15 border border-primary/20 flex items-center justify-center shrink-0 group-hover:bg-primary group-hover:border-primary transition-colors">
                <span className="font-display font-bold text-[10px] text-primary group-hover:text-primary-foreground transition-colors">
                  {initial}
                </span>
              </div>
              <span className="text-xs font-medium text-foreground hidden sm:block capitalize">{displayName}</span>
              <ChevronDown className="w-3 h-3 text-muted-foreground" />
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-48 rounded-xl glass shadow-amber-lg p-1 mt-2 overflow-hidden">
            <div className="px-3 py-2">
              <p className="text-xs font-semibold text-foreground capitalize">{displayName}</p>
              <p className="text-[10px] text-muted-foreground truncate">{user?.username ?? ""}</p>
            </div>
            <DropdownMenuSeparator className="bg-border/40 my-1" />
            <Link href="/profile">
              <DropdownMenuItem className="cursor-pointer text-xs rounded-lg m-0.5 gap-2.5 hover:bg-muted/60 focus:bg-muted/60 transition-colors">
                <User className="w-3.5 h-3.5 text-muted-foreground" />
                <span>Profile</span>
              </DropdownMenuItem>
            </Link>
            <DropdownMenuSeparator className="bg-border/40 my-1" />
            <DropdownMenuItem
              className="cursor-pointer text-xs text-destructive rounded-lg m-0.5 gap-2.5 focus:bg-destructive/10 focus:text-destructive hover:bg-destructive/10 transition-colors"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>{logoutMutation.isPending ? "Signing out…" : "Sign out"}</span>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
