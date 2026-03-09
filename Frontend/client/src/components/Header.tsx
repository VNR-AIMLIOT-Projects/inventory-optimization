import { Bell, User } from "lucide-react";
import { useEffect, useState } from "react";
import { healthCheck } from "@/lib/api";

function getStatusBg(apiOnline: boolean | null) {
  if (apiOnline === true) return "bg-emerald-500/10 border-emerald-500/20";
  if (apiOnline === false) return "bg-red-500/10 border-red-500/20";
  return "bg-muted/50 border-border";
}

function getStatusDot(apiOnline: boolean | null) {
  if (apiOnline === true) return "bg-emerald-400 animate-pulse";
  if (apiOnline === false) return "bg-red-400";
  return "bg-muted-foreground animate-pulse";
}

function getStatusText(apiOnline: boolean | null) {
  if (apiOnline === true) return { text: "API Online", color: "text-emerald-400" };
  if (apiOnline === false) return { text: "API Offline", color: "text-red-400" };
  return { text: "Checking...", color: "text-muted-foreground" };
}

export function Header({ title }: Readonly<{ title: string }>) {
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

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

  return (
    <header className="h-16 flex items-center justify-between px-8 border-b border-border/50 bg-background/50 backdrop-blur-sm sticky top-0 z-40">
      <h1 className="font-display font-bold text-2xl text-foreground tracking-tight">{title}</h1>
      
      <div className="flex items-center gap-6">
        <div className={`flex items-center gap-2 px-3 py-1 border rounded-full ${getStatusBg(apiOnline)}`}>
          <div className={`w-2 h-2 rounded-full ${getStatusDot(apiOnline)}`} />
          <span className={`text-[10px] font-bold uppercase tracking-widest ${statusInfo.color}`}>
            {statusInfo.text}
          </span>
        </div>
        
        <button className="relative w-9 h-9 rounded-full bg-muted/50 border border-border flex items-center justify-center hover:bg-muted transition-colors">
          <Bell className="w-4 h-4 text-muted-foreground" />
          <span className="absolute top-2 right-2 w-1.5 h-1.5 rounded-full bg-red-500" />
        </button>
        
        <div className="flex items-center gap-3 pl-2 border-l border-border/50">
          <div className="text-right hidden sm:block">
            <p className="text-xs font-bold">Admin</p>
            <p className="text-[10px] text-muted-foreground">Warehouse Supervisor</p>
          </div>
          <div className="w-9 h-9 rounded-full bg-gradient-to-br from-primary/80 to-indigo-600 flex items-center justify-center border border-white/10">
            <User className="w-4 h-4 text-white" />
          </div>
        </div>
      </div>
    </header>
  );
}
