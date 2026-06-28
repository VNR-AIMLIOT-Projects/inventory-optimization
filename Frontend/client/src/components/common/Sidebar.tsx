import { Link, useLocation } from "wouter";
import { cn } from "@/lib/utils";
import { useSidebar } from "@/hooks/use-sidebar";
import { useAuth } from "@/hooks/use-auth";
import {
  Upload, Wand2, Eye, Brain, BarChart3, Rocket,
  Package, LogOut, User, ChevronRight,
} from "lucide-react";

const NAV_ITEMS = [
  { id: 1, label: "Upload",   url: "/upload",   icon: Upload,    sub: "Load demand data"      },
  { id: 2, label: "Modify",   url: "/modify",   icon: Wand2,     sub: "Scenario builder"      },
  { id: 3, label: "Preview",  url: "/preview",  icon: Eye,       sub: "Visualize demand"      },
  { id: 4, label: "Train",    url: "/train",    icon: Brain,     sub: "DQN agent training"    },
  { id: 5, label: "Evaluate", url: "/evaluate", icon: BarChart3, sub: "Compare results"       },
  { id: 6, label: "Deploy",   url: "/deploy",   icon: Rocket,    sub: "Live environment"      },
];

/* ---------- Nav link ---------- */
function NavLink({
  item,
  isActive,
  isCollapsed,
}: {
  item: typeof NAV_ITEMS[number];
  isActive: boolean;
  isCollapsed: boolean;
}) {
  const Icon = item.icon;
  return (
    <Link href={item.url}>
      <div
        title={isCollapsed ? item.label : undefined}
        className={cn(
          "relative flex items-center gap-3 rounded-xl transition-all duration-200 cursor-pointer group select-none",
          isCollapsed ? "justify-center w-10 h-10 mx-auto" : "px-3 py-2.5",
          isActive
            ? "bg-primary/12 text-foreground"
            : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
        )}
      >
        {/* Active left bar */}
        {isActive && !isCollapsed && (
          <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-primary" />
        )}

        {/* Icon */}
        <div className={cn(
          "shrink-0 w-7 h-7 flex items-center justify-center rounded-lg transition-colors duration-200",
          isActive
            ? "bg-primary/18 text-primary"
            : "bg-transparent group-hover:bg-muted text-muted-foreground group-hover:text-foreground",
        )}>
          <Icon className="w-3.5 h-3.5" />
        </div>

        {/* Labels */}
        {!isCollapsed && (
          <div className="flex-1 min-w-0 overflow-hidden">
            <p className={cn("text-[13px] font-medium leading-tight truncate", isActive ? "text-foreground" : "")}>
              {item.label}
            </p>
            <p className="text-[10px] text-muted-foreground truncate mt-0.5 leading-tight">{item.sub}</p>
          </div>
        )}

        {/* Step number badge (collapsed) */}
        {isCollapsed && isActive && (
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-primary" />
        )}
      </div>
    </Link>
  );
}

/* ---------- Sidebar content ---------- */
export function SidebarContent({ isCollapsed = false }: { isCollapsed?: boolean }) {
  const [location] = useLocation();
  const { user, logoutMutation } = useAuth();
  const displayName = user?.firstName || user?.username?.split("@")[0] || "User";
  const initial     = displayName[0]?.toUpperCase() ?? "U";

  return (
    <div className="flex flex-col h-full">
      {/* ── Branding ── */}
      <div className={cn("shrink-0 border-b border-border/50", isCollapsed ? "p-3 flex justify-center" : "p-5")}>
        <Link href="/home">
          <div className="flex items-center gap-3 cursor-pointer group">
            <div className="w-8 h-8 rounded-xl bg-primary flex items-center justify-center shrink-0 transition-transform duration-200 group-hover:scale-105 group-active:scale-95 shadow-inner-top">
              <Package className="w-4 h-4 text-primary-foreground" />
            </div>
            {!isCollapsed && (
              <div>
                <p className="font-display font-bold text-[15px] text-foreground leading-tight">Replenix</p>
                <p className="text-[9px] font-semibold text-muted-foreground uppercase tracking-widest leading-tight">
                  Inventory Intelligence
                </p>
              </div>
            )}
          </div>
        </Link>
      </div>

      {/* ── Navigation ── */}
      <nav
        className={cn("flex-1 overflow-y-auto overflow-x-hidden py-4", isCollapsed ? "px-2" : "px-3")}
        aria-label="Pipeline navigation"
      >
        {!isCollapsed && (
          <p className="text-[9px] font-bold text-muted-foreground uppercase tracking-[0.18em] px-3 mb-3">
            Workflow
          </p>
        )}
        <div className="flex flex-col gap-0.5">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.url}
              item={item}
              isActive={location === item.url}
              isCollapsed={isCollapsed}
            />
          ))}
        </div>
      </nav>

      {/* ── User strip ── */}
      <div className={cn("shrink-0 border-t border-border/50 p-3", isCollapsed ? "flex flex-col items-center gap-2" : "")}>
        {!isCollapsed ? (
          <div className="flex items-center gap-3 p-2 rounded-xl hover:bg-muted/50 transition-colors group cursor-default">
            {/* Avatar */}
            <div className="w-8 h-8 rounded-lg bg-primary/15 border border-primary/20 flex items-center justify-center shrink-0">
              <span className="font-display font-bold text-xs text-primary">{initial}</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-[13px] font-semibold text-foreground truncate capitalize">{displayName}</p>
              <p className="text-[10px] text-muted-foreground truncate">{user?.username || ""}</p>
            </div>
            {/* Actions */}
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <Link href="/profile">
                <button
                  title="Profile"
                  className="w-6 h-6 rounded-md flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                >
                  <User className="w-3.5 h-3.5" />
                </button>
              </Link>
              <button
                title="Sign out"
                onClick={() => logoutMutation.mutate()}
                disabled={logoutMutation.isPending}
                className="w-6 h-6 rounded-md flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        ) : (
          <>
            <Link href="/profile">
              <button
                title="Profile"
                className="w-8 h-8 rounded-lg bg-primary/15 border border-primary/20 flex items-center justify-center text-primary hover:bg-primary/25 transition-colors"
              >
                <span className="font-display font-bold text-xs">{initial}</span>
              </button>
            </Link>
            <button
              title="Sign out"
              onClick={() => logoutMutation.mutate()}
              disabled={logoutMutation.isPending}
              className="w-8 h-8 rounded-lg flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" />
            </button>
          </>
        )}
      </div>
    </div>
  );
}

/* ---------- Floating sidebar wrapper ---------- */
export function Sidebar() {
  const { isCollapsed } = useSidebar();

  return (
    <div
      className={cn(
        "hidden lg:flex h-[calc(100dvh-2rem)] fixed left-4 top-4 z-50",
        "rounded-2xl glass shadow-amber-lg overflow-hidden",
        "transition-all duration-300 ease-spring",
        isCollapsed ? "w-[4.5rem]" : "w-[16.5rem]",
      )}
    >
      <SidebarContent isCollapsed={isCollapsed} />
    </div>
  );
}
