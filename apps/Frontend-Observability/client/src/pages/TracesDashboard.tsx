import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity, Clock, Search, Database, Bot, Cpu } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { formatDistanceToNow, format } from "date-fns";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function TracesDashboard() {
  const [page, setPage] = useState(1);
  const [selectedTrace, setSelectedTrace] = useState<any | null>(null);
  
  const { data, isLoading } = useQuery({
    queryKey: ["/api_rl/observability/traces", page],
    queryFn: async () => {
      const res = await fetch(`/api_rl/observability/traces?page=${page}&page_size=20&hours=24`);
      if (!res.ok) throw new Error("Failed to fetch traces");
      return res.json();
    },
    refetchInterval: 15000 // refresh every 15s
  });

  const traces = data?.items || [];

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">AI Traces</h1>
          <p className="text-muted-foreground mt-2">Monitor RL agent and LLM request latency and details.</p>
        </div>
        <div className="flex items-center gap-2 w-72">
          <Search className="h-4 w-4 text-muted-foreground" />
          <Input placeholder="Search traces by ID or content..." className="h-9" />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Recent Traces (Last 24 Hours)
          </CardTitle>
          <CardDescription>
            Showing {traces.length} of {data?.total || 0} traces.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <div className="text-center p-8 text-muted-foreground animate-pulse">Loading traces...</div>
          ) : traces.length === 0 ? (
            <div className="text-center p-8 text-muted-foreground">No traces found in the last 24 hours.</div>
          ) : (
            <div className="border rounded-md overflow-hidden">
              <Table>
                <TableHeader className="bg-muted/50">
                  <TableRow>
                    <TableHead>Trace ID</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Question / Context</TableHead>
                    <TableHead>Latency</TableHead>
                    <TableHead>Tokens</TableHead>
                    <TableHead>Time</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {traces.map((trace: any) => (
                    <TableRow 
                      key={trace.trace_id} 
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => setSelectedTrace(trace)}
                    >
                      <TableCell className="font-mono text-xs max-w-[120px] truncate">
                        {trace.trace_id}
                      </TableCell>
                      <TableCell>
                        <Badge variant="outline" className="bg-zinc-900">
                          {trace.llm_model || "unknown"}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-[200px] truncate">
                        {trace.question}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 text-sm">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          <span className={trace.latency?.total_ms > 2000 ? "text-amber-500 font-medium" : ""}>
                            {trace.latency?.total_ms || 0}ms
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">
                        {trace.tokens?.total || 0}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {trace.created_at ? formatDistanceToNow(new Date(trace.created_at), { addSuffix: true }) : "Unknown"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={!!selectedTrace} onOpenChange={(open) => !open && setSelectedTrace(null)}>
        <DialogContent className="max-w-3xl h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              Trace Details
              <Badge variant="outline" className="font-mono ml-2 text-xs">{selectedTrace?.trace_id}</Badge>
            </DialogTitle>
            <DialogDescription>
              {selectedTrace?.created_at && format(new Date(selectedTrace.created_at), "PPpp")}
            </DialogDescription>
          </DialogHeader>
          
          <ScrollArea className="flex-1 mt-4 pr-4">
            <div className="grid gap-6 pb-6">
              <div className="grid grid-cols-3 gap-4">
                <Card>
                  <CardHeader className="py-3 px-4 flex flex-row items-center justify-between bg-muted/30">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <Cpu className="h-4 w-4 text-blue-500" /> Model
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="py-3 px-4 text-sm font-medium">
                    {selectedTrace?.llm_model}
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="py-3 px-4 flex flex-row items-center justify-between bg-muted/30">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <Clock className="h-4 w-4 text-amber-500" /> Total Latency
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="py-3 px-4 text-sm font-medium">
                    {selectedTrace?.latency?.total_ms}ms
                  </CardContent>
                </Card>
                <Card>
                  <CardHeader className="py-3 px-4 flex flex-row items-center justify-between bg-muted/30">
                    <CardTitle className="text-sm font-medium flex items-center gap-2">
                      <Database className="h-4 w-4 text-green-500" /> Tokens Used
                    </CardTitle>
                  </CardHeader>
                  <CardContent className="py-3 px-4 text-sm font-medium">
                    {selectedTrace?.tokens?.total} (In: {selectedTrace?.tokens?.in}, Out: {selectedTrace?.tokens?.out})
                  </CardContent>
                </Card>
              </div>

              <div>
                <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <Bot className="h-4 w-4" /> Input Question
                </h3>
                <div className="bg-zinc-950 border border-border/50 rounded-md p-4 text-sm font-mono text-zinc-300">
                  {selectedTrace?.question}
                </div>
              </div>

              <div>
                <h3 className="text-sm font-medium mb-2 flex items-center gap-2">
                  <Bot className="h-4 w-4 text-primary" /> Output Answer
                </h3>
                <div className="bg-zinc-950 border border-border/50 rounded-md p-4 text-sm font-mono text-zinc-300 whitespace-pre-wrap">
                  {selectedTrace?.answer}
                </div>
              </div>

              <div className="border-t pt-4">
                <h3 className="text-sm font-medium mb-4">Execution Breakdown</h3>
                <div className="space-y-3">
                  <div className="relative">
                    <div className="flex justify-between text-xs mb-1">
                      <span>Retrieval</span>
                      <span>{selectedTrace?.latency?.retrieval_ms}ms</span>
                    </div>
                    <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-blue-500" 
                        style={{ width: `${(selectedTrace?.latency?.retrieval_ms / selectedTrace?.latency?.total_ms) * 100}%` }}
                      />
                    </div>
                  </div>
                  <div className="relative">
                    <div className="flex justify-between text-xs mb-1">
                      <span>LLM Generation</span>
                      <span>{selectedTrace?.latency?.llm_ms}ms</span>
                    </div>
                    <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-purple-500" 
                        style={{ width: `${(selectedTrace?.latency?.llm_ms / selectedTrace?.latency?.total_ms) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </ScrollArea>
        </DialogContent>
      </Dialog>
    </div>
  );
}
