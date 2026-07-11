import { useState, useEffect } from "react";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { useAuth } from "@/lib/auth";
import { useTheme } from "@/hooks/use-theme";
import { Moon, Sun, User, Database, LogOut } from "lucide-react";
import { setEnvironment as setGlobalEnv } from "@/lib/api";

export default function SettingsDashboard() {
  const { user, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  
  const [defaultEnv, setDefaultEnv] = useState<"prod" | "preprod">(() => {
    return (localStorage.getItem("replenix_env") as "prod" | "preprod") || "prod";
  });

  const handleEnvChange = (env: "prod" | "preprod") => {
    setDefaultEnv(env);
    setGlobalEnv(env);
  };

  return (
    <div className="flex flex-col h-full bg-background text-foreground overflow-y-auto">
      <Header title="Settings" />
      
      <div className="p-8 max-w-4xl mx-auto w-full space-y-8 animate-in fade-in duration-500">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Preferences</h1>
          <p className="text-muted-foreground mt-2">Manage your account settings and preferences.</p>
        </div>

        <div className="grid gap-6">
          {/* Profile Card */}
          <Card className="border-border bg-card">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2">
                <User className="w-5 h-5 text-primary" />
                Profile
              </CardTitle>
              <CardDescription>Your account details.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <p className="text-muted-foreground font-medium mb-1">Username</p>
                  <p className="font-semibold">{user?.username || "—"}</p>
                </div>
                <div>
                  <p className="text-muted-foreground font-medium mb-1">User ID</p>
                  <p className="font-semibold">{user?.id || "—"}</p>
                </div>
                {user?.firstName && (
                  <div>
                    <p className="text-muted-foreground font-medium mb-1">First Name</p>
                    <p className="font-semibold">{user.firstName}</p>
                  </div>
                )}
                {user?.lastName && (
                  <div>
                    <p className="text-muted-foreground font-medium mb-1">Last Name</p>
                    <p className="font-semibold">{user.lastName}</p>
                  </div>
                )}
              </div>
              <div className="pt-4 border-t border-border mt-4">
                <button
                  onClick={logout}
                  className="flex items-center gap-2 px-4 py-2 bg-destructive/10 text-destructive hover:bg-destructive hover:text-destructive-foreground rounded-md transition-colors text-sm font-medium"
                >
                  <LogOut className="w-4 h-4" />
                  Sign Out
                </button>
              </div>
            </CardContent>
          </Card>

          {/* Appearance Card */}
          <Card className="border-border bg-card">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2">
                {theme === "dark" ? <Moon className="w-5 h-5 text-primary" /> : <Sun className="w-5 h-5 text-primary" />}
                Appearance
              </CardTitle>
              <CardDescription>Customize the look and feel of the dashboard.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium">Theme</p>
                  <p className="text-sm text-muted-foreground">Toggle between light and dark mode.</p>
                </div>
                <button
                  onClick={toggleTheme}
                  className="px-4 py-2 rounded-md border border-border hover:bg-muted transition-colors font-medium text-sm flex items-center gap-2"
                >
                  {theme === "dark" ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
                  Switch to {theme === "dark" ? "Light" : "Dark"} Mode
                </button>
              </div>
            </CardContent>
          </Card>

          {/* Environment Card */}
          <Card className="border-border bg-card">
            <CardHeader className="pb-4">
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5 text-primary" />
                Default Environment
              </CardTitle>
              <CardDescription>Choose which cluster environment to default to on load.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex gap-4">
                <button
                  onClick={() => handleEnvChange("prod")}
                  className={`flex-1 p-4 rounded-xl border text-center transition-colors ${
                    defaultEnv === "prod" 
                      ? "bg-primary/10 border-primary text-primary" 
                      : "bg-muted/30 border-border hover:bg-muted/50 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <p className="font-bold">Production</p>
                  <p className="text-xs mt-1 opacity-80">replenix-prod</p>
                </button>
                <button
                  onClick={() => handleEnvChange("preprod")}
                  className={`flex-1 p-4 rounded-xl border text-center transition-colors ${
                    defaultEnv === "preprod" 
                      ? "bg-primary/10 border-primary text-primary" 
                      : "bg-muted/30 border-border hover:bg-muted/50 text-muted-foreground hover:text-foreground"
                  }`}
                >
                  <p className="font-bold">Pre-Production</p>
                  <p className="text-xs mt-1 opacity-80">replenix-preprod</p>
                </button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
