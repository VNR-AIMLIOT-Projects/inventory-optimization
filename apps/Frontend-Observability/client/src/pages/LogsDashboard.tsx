import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Terminal, RefreshCw, Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function LogsDashboard() {
  const [env, setEnv] = useState<string>("replenix-prod");
  const [selectedPod, setSelectedPod] = useState<string>("");
  const [filter, setFilter] = useState<string>("");

  const { data: pods, isLoading: loadingPods } = useQuery({
    queryKey: ["/api/k8s/pods", env],
    queryFn: async () => {
      const res = await fetch(`/api/k8s/pods?env=${env}`);
      if (!res.ok) throw new Error("Failed to fetch pods");
      return res.json();
    }
  });

  const { data: logs, isLoading: loadingLogs, refetch: refetchLogs } = useQuery({
    queryKey: ["/api/k8s/logs", env, selectedPod],
    queryFn: async () => {
      if (!selectedPod) return "";
      const res = await fetch(`/api/k8s/logs?env=${env}&pod=${selectedPod}`);
      if (!res.ok) throw new Error("Failed to fetch logs");
      return res.text();
    },
    enabled: !!selectedPod,
    refetchInterval: 5000 // auto-refresh every 5s
  });

  const filteredLogs = logs
    ? logs
        .split("\n")
        .filter((line: string) => line.toLowerCase().includes(filter.toLowerCase()))
        .join("\n")
    : "";

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Logs Viewer</h1>
          <p className="text-muted-foreground mt-2">View real-time logs from Kubernetes pods.</p>
        </div>
        <div className="flex items-center gap-4">
          <Select value={env} onValueChange={(val) => { setEnv(val); setSelectedPod(""); }}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="Select Environment" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="replenix-prod">Production</SelectItem>
              <SelectItem value="replenix-preprod">Pre-Production</SelectItem>
            </SelectContent>
          </Select>

          <Select value={selectedPod} onValueChange={setSelectedPod} disabled={loadingPods}>
            <SelectTrigger className="w-[250px]">
              <SelectValue placeholder={loadingPods ? "Loading..." : "Select Pod"} />
            </SelectTrigger>
            <SelectContent>
              {pods?.map((pod: any) => (
                <SelectItem key={pod.name} value={pod.name}>{pod.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Button variant="outline" size="icon" onClick={() => refetchLogs()} disabled={!selectedPod || loadingLogs}>
            <RefreshCw className={`h-4 w-4 ${loadingLogs ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      <Card className="border-border/50 h-[calc(100vh-200px)] flex flex-col">
        <CardHeader className="py-3 px-4 border-b border-border/50 flex flex-row items-center justify-between">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Terminal className="h-4 w-4" />
            Terminal Output
          </CardTitle>
          <div className="flex items-center gap-2 relative w-64">
            <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input 
              placeholder="Filter logs..." 
              value={filter} 
              onChange={(e) => setFilter(e.target.value)} 
              className="pl-8 h-9 text-sm"
            />
          </div>
        </CardHeader>
        <CardContent className="p-0 flex-1 overflow-hidden bg-zinc-950">
          {!selectedPod ? (
            <div className="h-full flex items-center justify-center text-zinc-500 font-mono text-sm">
              Please select a pod to view logs.
            </div>
          ) : (
            <pre className="h-full w-full p-4 overflow-auto text-green-400 font-mono text-xs leading-relaxed whitespace-pre-wrap break-words">
              {filteredLogs || (loadingLogs ? "Loading logs..." : "No logs found.")}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
