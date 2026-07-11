import { useState, useEffect, useRef } from "react";
import { Terminal, RefreshCw, Power, AlertCircle, CheckCircle2, CircleDashed, Box, Search, Pause, Play, Filter } from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import { Card } from "@/components/ui/card";

export default function KubernetesDashboard() {
  const [env, setEnv] = useState<"replenix-prod" | "replenix-preprod">("replenix-prod");
  const [pods, setPods] = useState<any[]>([]);
  const [selectedPod, setSelectedPod] = useState<any>(null);
  const [logs, setLogs] = useState<string>("");
  const [loadingPods, setLoadingPods] = useState(true);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [restarting, setRestarting] = useState(false);
  
  // New state for filtering and polling
  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("All");
  const [autoRefresh, setAutoRefresh] = useState(true);

  const { toast } = useToast();
  const logsEndRef = useRef<HTMLDivElement>(null);

  const fetchPods = async (environment: string) => {
    setLoadingPods(true);
    try {
      const res = await fetch(`/api/k8s/pods?env=${environment}`);
      if (!res.ok) throw new Error("Failed to fetch pods");
      const data = await res.json();
      setPods(data);
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setLoadingPods(false);
    }
  };

  const fetchLogs = async (environment: string, podName: string) => {
    setLoadingLogs(true);
    try {
      const res = await fetch(`/api/k8s/logs?env=${environment}&pod=${podName}`);
      if (!res.ok) throw new Error("Failed to fetch logs");
      const data = await res.text();
      setLogs(data);
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
      setLogs("");
    } finally {
      setLoadingLogs(false);
    }
  };

  useEffect(() => {
    fetchPods(env);
    setSelectedPod(null);
    setLogs("");
  }, [env]);

  useEffect(() => {
    if (selectedPod) {
      fetchLogs(env, selectedPod.name);
      if (!autoRefresh) return;
      const interval = setInterval(() => {
        fetchLogs(env, selectedPod.name);
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [selectedPod, env, autoRefresh]);

  useEffect(() => {
    if (logsEndRef.current && autoRefresh) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoRefresh]);

  const handleRestart = async () => {
    if (!selectedPod || !confirm(`Are you sure you want to restart pod ${selectedPod.name}?`)) return;
    setRestarting(true);
    try {
      const res = await fetch(`/api/k8s/pods?env=${env}&pod=${selectedPod.name}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Failed to restart pod");
      toast({ title: "Pod Restarted", description: "The ReplicaSet will recreate it shortly." });
      setSelectedPod(null);
      setTimeout(() => fetchPods(env), 2000);
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setRestarting(false);
    }
  };

  const getStatusIcon = (phase: string) => {
    switch (phase) {
      case "Running": return <CheckCircle2 className="w-4 h-4 text-emerald-500" />;
      case "Pending": return <CircleDashed className="w-4 h-4 text-amber-500" />;
      case "Failed":
      case "CrashLoopBackOff": return <AlertCircle className="w-4 h-4 text-red-500" />;
      default: return <CircleDashed className="w-4 h-4 text-muted-foreground" />;
    }
  };

  const filteredPods = pods.filter(pod => {
    if (searchQuery && !pod.name.toLowerCase().includes(searchQuery.toLowerCase())) return false;
    if (statusFilter !== "All") {
      if (statusFilter === "Running" && pod.status !== "Running") return false;
      if (statusFilter === "Failed/CrashLoop" && pod.status !== "Failed" && pod.status !== "CrashLoopBackOff") return false;
    }
    return true;
  });

  return (
    <div className="flex h-full">
      {/* Left Pane: Pod List */}
      <div className="w-1/3 max-w-sm border-r border-border bg-card flex flex-col">
        <div className="p-4 border-b border-border flex items-center justify-between bg-muted/30">
          <h2 className="font-semibold tracking-tight">Pods</h2>
          <select 
            value={env} 
            onChange={(e) => setEnv(e.target.value as any)}
            className="text-sm bg-background border border-input rounded-md px-2 py-1 outline-none focus:ring-1 focus:ring-primary"
          >
            <option value="replenix-prod">Production</option>
            <option value="replenix-preprod">Pre-Production</option>
          </select>
        </div>
        
        <div className="p-3 border-b border-border space-y-2 bg-card">
          <div className="relative">
            <Search className="absolute left-2.5 top-2 h-4 w-4 text-muted-foreground" />
            <input
              type="text"
              placeholder="Search pods..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-sm bg-background border border-input rounded-md outline-none focus:ring-1 focus:ring-primary"
            />
          </div>
          <div className="flex gap-2 text-xs">
            {["All", "Running", "Failed/CrashLoop"].map(status => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-2 py-1 rounded-md transition-colors ${
                  statusFilter === status 
                    ? "bg-primary text-primary-foreground font-medium" 
                    : "bg-muted hover:bg-muted/80 text-muted-foreground"
                }`}
              >
                {status}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-auto p-2 space-y-1">
          {loadingPods ? (
            <div className="p-4 text-center text-sm text-muted-foreground">Loading pods...</div>
          ) : filteredPods.length === 0 ? (
            <div className="p-4 text-center text-sm text-muted-foreground">No pods found matching filters.</div>
          ) : (
            filteredPods.map((pod) => (
              <button
                key={pod.name}
                onClick={() => setSelectedPod(pod)}
                className={`w-full text-left p-3 rounded-md transition-colors flex flex-col gap-1 border ${
                  selectedPod?.name === pod.name 
                    ? "bg-primary/10 border-primary/20" 
                    : "border-transparent hover:bg-muted/50"
                }`}
              >
                <div className="flex items-center gap-2">
                  {getStatusIcon(pod.status)}
                  <span className="font-medium text-sm truncate" title={pod.name}>{pod.name}</span>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground pl-6">
                  <span>{pod.status}</span>
                  <span className={pod.restarts > 0 ? "text-amber-500 font-medium" : ""}>Restarts: {pod.restarts}</span>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right Pane: Details & Logs */}
      <div className="flex-1 flex flex-col bg-background">
        {selectedPod ? (
          <>
            <div className="p-6 border-b border-border bg-card flex items-start justify-between shrink-0">
              <div>
                <h2 className="text-xl font-bold tracking-tight mb-1">{selectedPod.name}</h2>
                <div className="flex gap-4 text-sm text-muted-foreground">
                  <span>Node: {selectedPod.nodeIP || "Pending"}</span>
                  <span>Pod IP: {selectedPod.podIP || "Pending"}</span>
                  <span>Started: {new Date(selectedPod.startTime).toLocaleString()}</span>
                </div>
              </div>
              <button
                onClick={handleRestart}
                disabled={restarting}
                className="flex items-center gap-2 px-4 py-2 bg-destructive/10 text-destructive hover:bg-destructive hover:text-destructive-foreground rounded-md transition-colors text-sm font-medium disabled:opacity-50"
              >
                <Power className="w-4 h-4" />
                {restarting ? "Restarting..." : "Restart Pod"}
              </button>
            </div>
            
            <div className="flex-1 p-6 flex flex-col min-h-0">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <Terminal className="w-4 h-4" /> Live Logs
                  {loadingLogs && <RefreshCw className="w-3 h-3 animate-spin ml-2" />}
                </div>
                <button
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className={`flex items-center gap-1.5 px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                    autoRefresh 
                      ? "bg-primary/10 text-primary hover:bg-primary/20" 
                      : "bg-muted text-muted-foreground hover:bg-muted/80"
                  }`}
                >
                  {autoRefresh ? <Pause className="w-3 h-3" /> : <Play className="w-3 h-3" />}
                  {autoRefresh ? "Pause Logs" : "Resume Logs"}
                </button>
              </div>
              <Card className="flex-1 bg-[#1e1e1e] border-border overflow-hidden flex flex-col relative font-mono text-xs shadow-inner">
                <div className="flex-1 overflow-auto p-4 text-[#d4d4d4]">
                  {logs ? (
                    <pre className="whitespace-pre-wrap break-words">{logs}</pre>
                  ) : (
                    <span className="text-muted-foreground italic">No logs available...</span>
                  )}
                  <div ref={logsEndRef} />
                </div>
              </Card>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-muted-foreground flex-col gap-4">
            <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
              <Box className="w-8 h-8 opacity-50" />
            </div>
            <p>Select a pod to view details and logs.</p>
          </div>
        )}
      </div>
    </div>
  );
}
