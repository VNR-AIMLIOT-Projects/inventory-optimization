import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/hooks/use-theme";
import NotFound from "@/pages/not-found";
import Stage1Data from "@/features/demand/Stage1Data";
import ModifyDemand from "@/features/demand/ModifyDemand";
import PreviewDemand from "@/features/demand/PreviewDemand";
import Stage2Training from "@/features/training/Stage2Training";
import Stage3Deployment from "@/features/deployment/Stage3Deployment";
import DeploymentDashboard from "@/features/deployment/DeploymentDashboard";
import AuthPage from "@/features/auth/AuthPage";
import LandingPage from "@/pages/LandingPage";
import HomeDashboard from "@/pages/HomeDashboard";
import ProfilePage from "@/features/auth/ProfilePage";
import { AuthProvider, useAuth } from "./hooks/use-auth";
import { Loader2 } from "lucide-react";

function ProtectedRoute({ path, component: Component }: { path: string, component: any }) {
  return (
    <Route path={path}>
      {() => {
        const { user, isLoading } = useAuth();
        if (isLoading) {
          return (
            <div className="flex items-center justify-center min-h-dvh">
              <Loader2 className="w-8 h-8 animate-spin text-border" />
            </div>
          );
        }
        if (!user) {
          return <AuthPage />;
        }
        return <Component />;
      }}
    </Route>
  );
}

function Router() {
  return (
    <Switch>
      <Route path="/" component={LandingPage} />
      <Route path="/auth" component={AuthPage} />
      <ProtectedRoute path="/home" component={HomeDashboard} />
      <ProtectedRoute path="/profile" component={ProfilePage} />
      <ProtectedRoute path="/upload" component={Stage1Data} />
      <ProtectedRoute path="/modify" component={ModifyDemand} />
      <ProtectedRoute path="/preview" component={PreviewDemand} />
      <ProtectedRoute path="/train" component={Stage2Training} />
      <ProtectedRoute path="/evaluate" component={Stage3Deployment} />
      <ProtectedRoute path="/deploy" component={DeploymentDashboard} />
      <Route component={NotFound} />
    </Switch>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <TooltipProvider>
            <Toaster />
            <Router />
          </TooltipProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
