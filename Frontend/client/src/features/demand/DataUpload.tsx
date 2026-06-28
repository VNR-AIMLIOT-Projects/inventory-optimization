import { Sidebar } from "@/components/common/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { Header } from "@/components/common/Header";
import { useDemandUploads } from "@/hooks/use-demand";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { Upload, FileText, Download, CheckCircle2, Loader2 } from "lucide-react";
import { useState, useRef, useMemo } from "react";
import { useToast } from "@/hooks/use-toast";
import { format } from "date-fns";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@shared/routes";

export default function DataUpload() {
  const { isCollapsed } = useSidebar();
  const queryClient = useQueryClient();
  const { data: demandUploads } = useDemandUploads();
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isPending, setIsPending] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  const skus = useMemo(() => {
    if (!demandUploads) return [];
    const allSkus = demandUploads.flatMap((u: any) => (u.skus as string[]) || []);
    return Array.from(new Set(allSkus)).sort();
  }, [demandUploads]);

  const filteredData: any[] = [];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) setFile(e.target.files[0]);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  };

  const handleUpload = async () => {
    if (!file) return;
    setIsPending(true);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const response = await fetch("/api/demand/upload", { method: "POST", body: formData });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || "Upload failed");
      }
      const result = await response.json();
      toast({ title: "Data imported", description: `${result.count} records processed successfully.` });
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      queryClient.invalidateQueries({ queryKey: [api.demand.list.path] });
    } catch (err: any) {
      toast({ title: "Import failed", description: err.message || "Failed to upload data", variant: "destructive" });
    } finally {
      setIsPending(false);
    }
  };

  return (
    <div className="flex min-h-dvh bg-background">
      <Sidebar />
      <main className={cn(
        "flex-1 flex flex-col transition-all duration-300 ease-spring",
        isCollapsed ? "lg:ml-[5.5rem]" : "lg:ml-[17rem]",
      )}>
        <Header title="Step 1 — Upload data" />

        <div className="px-6 pb-10 pt-6 max-w-container mx-auto w-full">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

            {/* ── Upload panel ── */}
            <div className="lg:col-span-1 space-y-4 animate-fade-in-up">
              {/* Download template */}
              <button
                onClick={() => (window.location.href = "/api/template")}
                className="w-full flex items-center gap-3 px-4 py-3 bg-card border border-dashed border-border rounded-2xl text-sm text-muted-foreground hover:border-primary/40 hover:text-foreground hover:bg-muted/30 transition-all duration-200 group"
              >
                <Download className="w-4 h-4 shrink-0 group-hover:text-primary transition-colors" />
                <span className="font-medium">Download sample CSV template</span>
              </button>

              {/* Drop zone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={cn(
                  "relative border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200",
                  isDragging
                    ? "border-primary/60 bg-primary/5"
                    : file
                    ? "border-success/40 bg-success/5"
                    : "border-border hover:border-primary/40 hover:bg-muted/20",
                )}
              >
                <Input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.tsv,.txt"
                  className="hidden"
                  onChange={handleFileChange}
                />
                <div className={cn(
                  "w-12 h-12 rounded-xl flex items-center justify-center mb-4 transition-colors",
                  file ? "bg-success/15 text-success" : "bg-primary/10 text-primary",
                )}>
                  {file ? <CheckCircle2 className="w-6 h-6" /> : <Upload className="w-6 h-6" />}
                </div>
                {file ? (
                  <div className="flex items-center gap-2 text-success font-medium text-sm">
                    <FileText className="w-4 h-4" />
                    <span className="truncate max-w-[180px]">{file.name}</span>
                  </div>
                ) : (
                  <>
                    <p className="font-semibold text-sm text-foreground">Drop CSV here</p>
                    <p className="text-xs text-muted-foreground mt-1">or click to browse · any column format</p>
                  </>
                )}
              </div>

              {/* Upload button */}
              <button
                onClick={handleUpload}
                disabled={!file || isPending}
                className={cn(
                  "w-full flex items-center justify-center gap-2.5 h-11 rounded-xl font-semibold text-sm transition-all duration-200",
                  file && !isPending
                    ? "bg-primary text-primary-foreground hover:brightness-105 active:scale-[0.97] shadow-amber"
                    : "bg-muted text-muted-foreground cursor-not-allowed",
                )}
              >
                {isPending && <Loader2 className="w-4 h-4 animate-spin" />}
                {isPending ? "Processing…" : "Import and analyze"}
              </button>

              {/* Uploaded files list */}
              {demandUploads && demandUploads.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider px-1">
                    Uploaded datasets
                  </p>
                  {demandUploads.map((upload: any, i: number) => (
                    <div key={upload.id} className={cn("flex items-center gap-3 p-3 bg-card border border-border rounded-xl animate-fade-in-up", `delay-${i * 75}`)}>
                      <div className="w-7 h-7 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                        <FileText className="w-3.5 h-3.5 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-medium text-foreground truncate">{upload.filename}</p>
                        <p className="text-[10px] text-muted-foreground tabular">
                          {(upload.skus as string[])?.length ?? 0} SKUs
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* ── Analysis panel ── */}
            <div className="lg:col-span-2 animate-fade-in-up delay-150">
              <Card className="border-border shadow-amber min-h-[500px] rounded-2xl">
                <CardHeader className="flex flex-row items-start justify-between gap-4 pb-6">
                  <div>
                    <CardTitle className="font-display font-semibold text-lg">SKU analysis</CardTitle>
                    <CardDescription className="mt-1">
                      {skus.length > 0
                        ? `${skus.length} unique SKUs found in your data`
                        : "No data yet — upload a CSV to get started"}
                    </CardDescription>
                  </div>
                  {skus.length > 0 && (
                    <Select onValueChange={setSelectedSku} value={selectedSku || ""}>
                      <SelectTrigger className="w-44 h-9 rounded-xl border-border bg-background text-sm shrink-0">
                        <SelectValue placeholder="Select SKU" />
                      </SelectTrigger>
                      <SelectContent className="rounded-xl">
                        {skus.map((sku: string) => (
                          <SelectItem key={sku} value={sku}>{sku}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                </CardHeader>
                <CardContent>
                  {selectedSku ? (
                    <div className="h-80">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={filteredData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" opacity={0.5} />
                          <XAxis
                            dataKey="date"
                            stroke="hsl(var(--muted-foreground))"
                            fontSize={11}
                            tickLine={false}
                            axisLine={false}
                            tickFormatter={(str) => format(new Date(str), "MMM d")}
                          />
                          <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
                          <Tooltip
                            contentStyle={{
                              background: "hsl(var(--card))",
                              border: "1px solid hsl(var(--border))",
                              borderRadius: "0.75rem",
                            }}
                            itemStyle={{ color: "hsl(var(--foreground))" }}
                            labelFormatter={(str) => format(new Date(str), "MMM d, yyyy")}
                          />
                          <Line
                            type="monotone"
                            dataKey="value"
                            stroke="hsl(var(--primary))"
                            strokeWidth={2.5}
                            dot={false}
                            activeDot={{ r: 5, fill: "hsl(var(--primary))" }}
                            name="Historical demand"
                          />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <div className="h-80 flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-border bg-muted/20">
                      <div className="w-12 h-12 rounded-xl bg-muted flex items-center justify-center mb-4">
                        <CheckCircle2 className="w-5 h-5 text-muted-foreground/50" />
                      </div>
                      <p className="text-sm font-medium text-muted-foreground">
                        {skus.length > 0 ? "Select an SKU above to view the demand plot" : "Upload a CSV to see your demand data"}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
