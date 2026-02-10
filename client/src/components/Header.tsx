import { Bell, Package, User } from "lucide-react";

export function Header({ title }: { title: string }) {
  return (
    <header className="h-16 flex items-center justify-between px-8 border-b border-border/50 bg-background/50 backdrop-blur-sm sticky top-0 z-40">
      <h1 className="font-display font-bold text-2xl text-foreground tracking-tight">{title}</h1>
      
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2 px-3 py-1 bg-primary/10 border border-primary/20 rounded-full">
          <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
          <span className="text-[10px] font-bold text-primary uppercase tracking-widest">Automation Online</span>
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
