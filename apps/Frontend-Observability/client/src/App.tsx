import { Switch, Route, Redirect } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/hooks/use-theme";
import { AuthProvider, useAuth } from "@/lib/auth";
import NotFound from "@/pages/not-found";
import ObservabilityDashboard from "@/features/observability/ObservabilityDashboard";
import MetricsDashboard from "@/pages/MetricsDashboard";
import KubernetesDashboard from "@/pages/KubernetesDashboard";
import Login from "@/pages/Login";
import { SidebarLayout } from "@/components/Sidebar";

function ProtectedRoute({ path, component: Component }: { path: string, component: React.ComponentType<any> }) {
  const { user, isLoading } = useAuth();
  
  if (isLoading) {
    return <div className="flex h-screen items-center justify-center">Loading...</div>;
  }
  
  if (!user) {
    return <Redirect to="/login" />;
  }
  
  return (
    <Route path={path}>
      <SidebarLayout>
        <Component />
      </SidebarLayout>
    </Route>
  );
}

function Router() {
  return (
    <Switch>
      <Route path="/login" component={Login} />
      <ProtectedRoute path="/" component={ObservabilityDashboard} />
      <ProtectedRoute path="/traces" component={ObservabilityDashboard} />
      <ProtectedRoute path="/metrics" component={MetricsDashboard} />
      <ProtectedRoute path="/kubernetes" component={KubernetesDashboard} />
      <Route>
        <SidebarLayout>
          <NotFound />
        </SidebarLayout>
      </Route>
    </Switch>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <Toaster />
          <AuthProvider>
            <Router />
          </AuthProvider>
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
