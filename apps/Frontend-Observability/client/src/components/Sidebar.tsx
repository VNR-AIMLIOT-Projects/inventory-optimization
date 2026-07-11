import { Link, useLocation } from "wouter";
import { LayoutDashboard, Activity, BarChart3, Box, LogOut, Settings } from "lucide-react";
import { useAuth } from "@/lib/auth";

export default function Sidebar() {
  const [location] = useLocation();
  const { logout, user } = useAuth();

  const links = [
    { href: "/", label: "Overview", icon: LayoutDashboard },
    { href: "/traces", label: "AI Traces", icon: Activity },
    { href: "/metrics", label: "Metrics", icon: BarChart3 },
    { href: "/kubernetes", label: "Kubernetes", icon: Box },
    { href: "/settings", label: "Settings", icon: Settings },
  ];

  return (
    <div className="w-64 flex flex-col h-screen border-r border-border bg-sidebar px-4 py-6 text-sidebar-foreground z-10 transition-colors">
      <div className="flex items-center gap-2 mb-8 px-2">
        <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center text-primary-foreground font-bold">
          R
        </div>
        <span className="text-xl font-bold tracking-tight">Replenix</span>
      </div>

      <nav className="flex flex-col gap-2 flex-1">
        {links.map((link) => {
          const active = location === link.href || (link.href !== "/" && location.startsWith(link.href));
          return (
            <Link key={link.href} href={link.href}>
              <a className={`flex items-center gap-3 px-3 py-2 rounded-md transition-colors ${active ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium" : "text-muted-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-foreground"}`}>
                <link.icon className="w-5 h-5" />
                {link.label}
              </a>
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-border pt-4 px-2">
        <div className="flex items-center justify-between">
          <div className="flex flex-col">
            <span className="text-sm font-medium">{user?.username}</span>
            <span className="text-xs text-muted-foreground">Admin</span>
          </div>
          <button onClick={() => logout()} className="p-2 text-muted-foreground hover:text-foreground rounded-md transition-colors" title="Logout">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function SidebarLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-auto bg-background/50">
        {children}
      </main>
    </div>
  );
}
