import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Info, ShieldAlert, CheckCircle2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatDistanceToNow } from "date-fns";

export default function AlertsDashboard() {
  const { data: alerts, isLoading } = useQuery({
    queryKey: ["/api/metrics/alerts"],
    queryFn: async () => {
      const res = await fetch("/api/metrics/alerts");
      if (!res.ok) throw new Error("Failed to fetch alerts");
      return res.json();
    },
    refetchInterval: 10000 // auto-refresh every 10s
  });

  const getSeverityBadge = (severity: string) => {
    switch (severity.toLowerCase()) {
      case "critical":
        return <Badge variant="destructive" className="flex items-center gap-1"><ShieldAlert className="w-3 h-3"/> Critical</Badge>;
      case "warning":
        return <Badge variant="default" className="bg-amber-500 hover:bg-amber-600 flex items-center gap-1"><AlertTriangle className="w-3 h-3"/> Warning</Badge>;
      case "info":
        return <Badge variant="secondary" className="flex items-center gap-1"><Info className="w-3 h-3"/> Info</Badge>;
      default:
        return <Badge variant="outline">{severity}</Badge>;
    }
  };

  const getStatusBadge = (status: string) => {
    if (status.toLowerCase() === "firing" || status.toLowerCase() === "active") {
      return <Badge variant="destructive" className="bg-red-500">Firing</Badge>;
    }
    return <Badge variant="secondary" className="bg-green-500/20 text-green-500 hover:bg-green-500/30 border-green-500/20 flex items-center gap-1"><CheckCircle2 className="w-3 h-3"/> Resolved</Badge>;
  };

  const activeAlerts = alerts?.filter((a: any) => a.status === "firing" || a.status === "active") || [];
  const historicalAlerts = alerts?.filter((a: any) => a.status !== "firing" && a.status !== "active") || [];

  return (
    <div className="p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight">Alerts & Alarms</h1>
        <p className="text-muted-foreground mt-2">Monitor system health deviations and active alerts from Prometheus Alertmanager.</p>
      </div>

      <div className="grid gap-6">
        <Card className="border-red-900/50 bg-red-950/10">
          <CardHeader>
            <CardTitle className="text-red-500 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5" />
              Active Alerts ({activeAlerts.length})
            </CardTitle>
            <CardDescription>Alerts currently firing in the cluster.</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center p-4 text-muted-foreground animate-pulse">Loading alerts...</div>
            ) : activeAlerts.length === 0 ? (
              <div className="text-center p-8 text-green-500 border border-green-900/50 bg-green-950/20 rounded-lg flex flex-col items-center justify-center gap-2">
                <CheckCircle2 className="h-8 w-8" />
                <p className="font-medium">All systems green. No active alerts.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Alert Name</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Labels</TableHead>
                    <TableHead>Started</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {activeAlerts.map((alert: any) => (
                    <TableRow key={alert.id}>
                      <TableCell className="font-medium">{alert.name}</TableCell>
                      <TableCell>{getSeverityBadge(alert.severity)}</TableCell>
                      <TableCell>{getStatusBadge(alert.status)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {Object.entries(alert.labels || {}).map(([k, v]) => (
                            <Badge key={k} variant="outline" className="text-[10px] py-0">{k}: {String(v)}</Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {alert.startedAt ? formatDistanceToNow(new Date(alert.startedAt), { addSuffix: true }) : "Unknown"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Recent History</CardTitle>
            <CardDescription>Recently resolved alerts and notifications.</CardDescription>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="text-center p-4 text-muted-foreground animate-pulse">Loading history...</div>
            ) : historicalAlerts.length === 0 ? (
              <div className="text-center p-8 text-muted-foreground">No recent history available.</div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Alert Name</TableHead>
                    <TableHead>Severity</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Labels</TableHead>
                    <TableHead>Duration</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {historicalAlerts.map((alert: any) => (
                    <TableRow key={alert.id}>
                      <TableCell className="font-medium">{alert.name}</TableCell>
                      <TableCell>{getSeverityBadge(alert.severity)}</TableCell>
                      <TableCell>{getStatusBadge(alert.status)}</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1 max-w-xs">
                          {Object.entries(alert.labels || {}).map(([k, v]) => (
                            <Badge key={k} variant="outline" className="text-[10px] py-0">{k}: {String(v)}</Badge>
                          ))}
                        </div>
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {alert.startedAt && alert.resolvedAt ? 
                          formatDistanceToNow(new Date(alert.startedAt), { addSuffix: false }) : "Unknown"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
