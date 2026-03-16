import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ThemeProvider } from "@/hooks/use-theme";
import NotFound from "@/pages/not-found";
import Stage1Data from "@/pages/Stage1Data";
import ModifyDemand from "@/pages/ModifyDemand";
import PreviewDemand from "@/pages/PreviewDemand";
import Stage2Training from "@/pages/Stage2Training";
import Stage3Deployment from "@/pages/Stage3Deployment";
import DeploymentDashboard from "@/pages/DeploymentDashboard";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Stage1Data} />
      <Route path="/modify" component={ModifyDemand} />
      <Route path="/preview" component={PreviewDemand} />
      <Route path="/train" component={Stage2Training} />
      <Route path="/evaluate" component={Stage3Deployment} />
      <Route path="/deploy" component={DeploymentDashboard} />
      <Route component={NotFound} />
    </Switch>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </QueryClientProvider>
    </ThemeProvider>
  );
}
