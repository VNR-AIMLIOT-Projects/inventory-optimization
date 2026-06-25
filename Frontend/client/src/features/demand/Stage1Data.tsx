import { Sidebar } from "@/components/common/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { StageNav } from "@/components/common/StageNav";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Upload, FileText, Sparkles, CheckCircle2, AlertCircle, Loader2, Table as TableIcon, Download, Search, History, ChevronDown, ChevronUp } from "lucide-react";
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";
import { useState, useRef, useCallback, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { uploadDemand, listSkus, selectSku, generateDemand, getDemandData, getUploads } from "@/lib/api";
import type { DemandDataResponse, UploadSummary } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { useLocation } from "wouter";
import { PageCopilot } from "@/features/copilot/PageCopilot";

export default function Stage1Data() {
  const { isCollapsed } = useSidebar();
  const { toast } = useToast();
  const [, navigate] = useLocation();
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload state
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [uploadInfo, setUploadInfo] = useState<{ num_days: number; sku: string; start_date: string; end_date: string; season_type?: string } | null>(null);

  // SKU state
  const [skus, setSkus] = useState<string[]>([]);
  const [selectedSku, setSelectedSku] = useState("");

  // Generate state
  const [seasonType, setSeasonType] = useState("summer");
  const [startDate, setStartDate] = useState("2025-01-01");
  const [numDays, setNumDays] = useState(365);
  const [seed, setSeed] = useState(42);
  const [generating, setGenerating] = useState(false);

  // Data preview
  const [demandData, setDemandData] = useState<DemandDataResponse | null>(null);
  const [loadingData, setLoadingData] = useState(false);

  // Upload history
  const [pastUploads, setPastUploads] = useState<UploadSummary[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Data Preview Expandable
  const [showTable, setShowTable] = useState(false);

  // Drag & drop
  const [dragOver, setDragOver] = useState(false);

  const hasData = demandData?.dates && demandData.dates.length > 0;

  const fetchDemandData = useCallback(async () => {
    setLoadingData(true);
    try {
      const data = await getDemandData();
      setDemandData(data);
    } catch {
      // Silently ignore if no data yet
    } finally {
      setLoadingData(false);
    }
  }, []);

  const fetchSkus = useCallback(async () => {
    try {
      const res = await listSkus();
      setSkus(res.skus);
    } catch {
      // No file uploaded yet
    }
  }, []);

  // Restore state when navigating back to this page
  useEffect(() => {
    (async () => {
      try {
        const [skuRes, dataRes, uploadsRes] = await Promise.allSettled([
          listSkus(),
          getDemandData(),
          getUploads(),
        ]);
        if (skuRes.status === "fulfilled") setSkus(skuRes.value.skus);
        if (dataRes.status === "fulfilled") {
          setDemandData(dataRes.value);
          setUploadSuccess(true);
          setUploadInfo({
            num_days: dataRes.value.num_days,
            sku: "",
            start_date: dataRes.value.dates?.[0] || "",
            end_date: dataRes.value.dates?.[dataRes.value.dates.length - 1] || "",
          });
        }
        if (uploadsRes.status === "fulfilled") setPastUploads(uploadsRes.value);
      } catch {
        // No data uploaded yet — that's fine
      }
    })();
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadDemand(file, {});
      setUploadSuccess(true);
      setUploadInfo({
        num_days: result.num_days,
        sku: result.sku,
        start_date: result.date_range.start,
        end_date: result.date_range.end,
        season_type: result.detected_params?.detected_season_type,
      });
      toast({ title: "Analysis Complete", description: `${result.num_days} days loaded for ${result.sku} (${result.date_range.start} → ${result.date_range.end})` });
      await fetchSkus();
      await fetchDemandData();
      // Refresh upload history
      try { setPastUploads(await getUploads()); } catch { }
    } catch (err: any) {
      toast({ title: "Analysis Failed", description: friendlyError(err, "upload"), variant: "destructive" });
    } finally {
      setUploading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await generateDemand({ season_type: seasonType, start_date: startDate, num_days: numDays, seed });
      setUploadSuccess(true);
      setUploadInfo({ num_days: result.data.num_days, sku: `synthetic-${seasonType}`, start_date: startDate, end_date: "" });
      toast({ title: "Data Generated", description: `${result.data.num_days} days of Demand generated. Multi-SKUs available.` });
      await fetchSkus();
      await fetchDemandData();
      try { setPastUploads(await getUploads()); } catch { }
    } catch (err: any) {
      toast({ title: "Generation Failed", description: friendlyError(err, "generate"), variant: "destructive" });
    } finally {
      setGenerating(false);
    }
  };

  const handleSkuSelect = async (sku: string) => {
    setSelectedSku(sku);
    setLoadingData(true);
    try {
      const result = await selectSku(sku);
      setUploadInfo({
        num_days: result.num_days,
        sku: result.sku,
        start_date: result.date_range.start,
        end_date: result.date_range.end,
        season_type: result.detected_params?.detected_season_type,
      });
      toast({ title: "SKU Selected", description: `Loaded ${result.num_days} days for ${result.sku}` });
      await fetchDemandData();
    } catch (err: any) {
      toast({ title: "SKU Selection Failed", description: friendlyError(err, "sku"), variant: "destructive" });
    } finally {
      setLoadingData(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.name.endsWith(".csv") || droppedFile.name.endsWith(".xlsx") || droppedFile.name.endsWith(".xls"))) {
      setFile(droppedFile);
    } else {
      toast({
        title: "Unsupported File Type",
        description: "Only CSV (.csv) and Excel (.xlsx, .xls) files are supported. Please convert your file before uploading.",
        variant: "destructive",
      });
    }
  }, [toast]);

  const downloadTemplate = () => {
    const csv = "Date,SKU,Demand\n";
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "inventory_data_template.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  function renderDataPreview() {
    if (loadingData) {
      return (
        <div className="h-[200px] flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      );
    }
    if (hasData && demandData) {
      const chartData = demandData.dates.map((d, i) => ({ date: d, demand: demandData.demand[i] }));
      
      return (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-4">
            <Card className="flex-1 bg-muted/30 border-border/50">
              <CardContent className="p-4 flex flex-col justify-center h-full space-y-1">
                <p className="text-sm font-medium">Dataset Summary</p>
                <p className="text-xs text-muted-foreground">
                  {demandData.num_days} days · {skus.length} SKU{skus.length !== 1 ? 's' : ''}
                </p>
                <p className="text-xs text-muted-foreground">
                  {demandData.dates[0]} to {demandData.dates[demandData.dates.length - 1]}
                </p>
                {uploadInfo?.season_type && (
                  <Badge variant="outline" className="w-fit mt-1 text-[10px]">
                    Pattern: {uploadInfo.season_type}
                  </Badge>
                )}
              </CardContent>
            </Card>
            <Card className="flex-1 bg-muted/30 border-border/50 h-[100px] flex items-center justify-center overflow-hidden p-2">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <Line type="monotone" dataKey="demand" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} isAnimationActive={false} />
                  <YAxis domain={['dataMin', 'dataMax']} hide />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          </div>

          <Button 
            variant="outline" 
            className="w-full justify-between" 
            onClick={() => setShowTable(!showTable)}
          >
            <span>View Full Data Table</span>
            {showTable ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </Button>

          {showTable && (
            <div className="max-h-[300px] overflow-auto rounded-lg border border-border/50 animate-in slide-in-from-top-2">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="text-xs">Date</TableHead>
                    <TableHead className="text-xs text-right">Demand</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {demandData.dates.slice(0, 50).map((date, i) => (
                    <TableRow key={`${date}-${i}`}>
                      <TableCell className="text-xs font-mono">{date}</TableCell>
                      <TableCell className="text-xs text-right font-mono">{demandData.demand[i]}</TableCell>
                    </TableRow>
                  ))}
                  {demandData.dates.length > 50 && (
                    <TableRow>
                      <TableCell colSpan={2} className="text-xs text-center text-muted-foreground py-3">
                        ... and {demandData.dates.length - 50} more rows
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </div>
      );
    }
    return null;
  }

  function renderUploadZone(isCompact: boolean) {
    return (
      <div className="space-y-4">
        {/* biome-ignore lint: drag-drop zone needs div for drag events */}
        <button
          type="button"
          className={`w-full border-2 border-dashed rounded-xl flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 bg-transparent ${dragOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"} ${isCompact ? "p-6" : "p-12"}`}
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={handleDrop}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,.xlsx,.xls"
            className="hidden"
            onChange={(e) => e.target.files && setFile(e.target.files[0])}
          />
          {file ? (
            <>
              <FileText className={`${isCompact ? "w-6 h-6 mb-2" : "w-12 h-12 mb-4"} text-primary`} />
              <span className={`${isCompact ? "text-sm" : "text-lg"} font-semibold text-primary`}>{file.name}</span>
              <span className="text-xs text-muted-foreground mt-1">
                {(file.size / 1024).toFixed(1)} KB — Click to change
              </span>
            </>
          ) : (
            <>
              <Upload className={`${isCompact ? "w-6 h-6 mb-2" : "w-12 h-12 mb-4"} text-muted-foreground/50`} />
              <span className={`${isCompact ? "text-sm" : "text-lg"} font-medium text-foreground`}>Drag & drop your CSV or Excel file</span>
              <span className="text-xs text-muted-foreground mt-2">or click to browse</span>
            </>
          )}
        </button>

        {file && (
          <Button onClick={handleUpload} disabled={uploading} className="w-full h-12 gap-2 font-bold">
            {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            {uploading ? "Analyzing..." : "Analyze File"}
          </Button>
        )}

        {!isCompact && !file && (
          <div className="flex flex-col items-center gap-3 pt-4 border-t border-border/50">
            <button 
              onClick={handleGenerate} 
              disabled={generating} 
              className="text-sm text-primary hover:text-primary/80 transition-colors flex items-center gap-2"
            >
              {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              Generate sample data instead
            </button>
            <button 
              onClick={downloadTemplate} 
              className="text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              Download template CSV
            </button>
          </div>
        )}
      </div>
    );
  }

  return (
    <>
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className={cn("flex-1", isCollapsed ? "lg:ml-[112px]" : "lg:ml-[288px]", "flex flex-col")}>
          <Header title="Upload Demand Data" />
          <div className="px-5 py-4 space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-300 max-w-screen-xl mx-auto w-full">
            <StageNav />

            {/* Success Banner */}
            {uploadSuccess && uploadInfo && (
              <div className="flex items-center justify-between p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <div>
                    <p className="text-sm font-semibold text-emerald-400">Data Loaded Successfully</p>
                    <p className="text-xs text-muted-foreground">Ready for analysis</p>
                  </div>
                </div>
                <Button variant="default" size="sm" onClick={() => navigate("/modify")}>Continue to Configuration</Button>
              </div>
            )}

            {!hasData ? (
              // Phase 1: No data uploaded yet
              <div className="max-w-2xl mx-auto mt-12 w-full">
                <Card className="border-border/50 shadow-sm">
                  <CardHeader className="text-center pb-2">
                    <CardTitle className="text-2xl font-medium">Load Demand Data</CardTitle>
                    <CardDescription>Upload your historical inventory data to begin analysis</CardDescription>
                  </CardHeader>
                  <CardContent className="pt-4">
                    {renderUploadZone(false)}
                  </CardContent>
                </Card>
                
                {pastUploads.length > 0 && (
                  <div className="mt-8 text-center">
                    <Button 
                      variant="ghost" 
                      onClick={() => setShowHistory(!showHistory)}
                      className="text-sm text-muted-foreground"
                    >
                      <History className="w-4 h-4 mr-2" />
                      View previously uploaded files
                    </Button>
                  </div>
                )}
              </div>
            ) : (
              // Phase 2: Data has been uploaded
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <div className="lg:col-span-1 space-y-6">
                  <Card className="border-border/50 shadow-sm bg-card">
                    <CardHeader className="pb-3">
                      <CardTitle className="text-base">Upload New File</CardTitle>
                    </CardHeader>
                    <CardContent>
                      {renderUploadZone(true)}
                    </CardContent>
                  </Card>
                </div>

                <div className="lg:col-span-2 space-y-6">
                  <Card className="border-border/50 shadow-sm bg-card">
                    <CardHeader className="pb-3 flex flex-row items-center justify-between">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <TableIcon className="w-4 h-4 text-primary" />
                        Data Preview
                      </CardTitle>
                      {skus.length > 1 && (
                        <Select value={selectedSku} onValueChange={handleSkuSelect}>
                          <SelectTrigger className="w-[140px] h-8 text-xs">
                            <SelectValue placeholder="All SKUs" />
                          </SelectTrigger>
                          <SelectContent>
                            {skus.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      )}
                    </CardHeader>
                    <CardContent>
                      {renderDataPreview()}
                    </CardContent>
                  </Card>
                </div>
              </div>
            )}

            {/* Upload History (Collapsible) */}
            {(showHistory || hasData) && pastUploads.length > 0 && (
              <Card className="border-border/50 shadow-sm bg-card mt-8 animate-in fade-in">
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-base">
                    <History className="w-4 h-4 text-primary" /> Previous Uploads
                  </CardTitle>
                  <CardDescription>Re-use previously uploaded datasets</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    {pastUploads.slice(0, 3).map((upload) => (
                      <button
                        key={upload.id}
                        onClick={async () => {
                          // Re-upload by selecting the first SKU from this file
                          // The backend already has the file path stored
                          if (upload.skus.length > 0) {
                            try {
                              const result = await selectSku(upload.skus[0]);
                              setUploadSuccess(true);
                              setUploadInfo({
                                num_days: result.num_days,
                                sku: result.sku,
                                start_date: result.date_range.start,
                                end_date: result.date_range.end,
                                season_type: result.detected_params?.detected_season_type,
                              });
                              setSkus(upload.skus);
                              await fetchDemandData();
                              toast({ title: "Dataset Loaded", description: `Loaded ${upload.filename}` });
                            } catch (err: unknown) {
                              toast({ title: "Load Failed", description: friendlyError(err as Error, "upload"), variant: "destructive" });
                            }
                          }
                        }}
                        className="flex items-start gap-3 p-3 rounded-lg border border-border/50 bg-muted/20 hover:bg-muted/40 transition-colors text-left"
                      >
                        <FileText className="w-5 h-5 text-primary shrink-0 mt-0.5" />
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{upload.filename}</p>
                          <div className="flex items-center gap-2 mt-1">
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0">{upload.file_type}</Badge>
                            <span className="text-[10px] text-muted-foreground">{upload.skus.length} SKU{upload.skus.length !== 1 ? "s" : ""}</span>
                            <span className="text-[10px] text-muted-foreground">{new Date(upload.uploaded_at).toLocaleDateString()}</span>
                          </div>
                          {upload.skus.length > 0 && (
                            <p className="text-[10px] text-muted-foreground mt-1 truncate">
                              {upload.skus.join(", ")}
                            </p>
                          )}
                        </div>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </main>
      </div>
      <PageCopilot
        page="stage1"
        title="Data Assistant"
        subtitle={demandData ? "● Ready · Data loaded" : "○ No data loaded yet"}
        quickActions={[
          "Generate 365 days of summer demand",
          "Generate 180 days of winter demand",
          "What file format should I upload?",
          "I'm done — take me to the next step",
        ]}
        pageContext={{
          has_file: skus.length > 0,
          skus,
          current_sku: selectedSku || null,
          has_data: !!demandData,
          num_days: demandData?.num_days ?? null,
          date_range: demandData?.dates?.length
            ? `${demandData.dates[0]} to ${demandData.dates[demandData.dates.length - 1]}`
            : null,
        }}
        onAction={async (action) => {
          const a = action as Record<string, unknown>;
          if (a.action === "generate_demand") {
            setGenerating(true);
            try {
              await generateDemand({
                season_type: (a.season_type as string) ?? seasonType,
                start_date: (a.start_date as string) ?? startDate,
                num_days: (a.num_days as number) ?? numDays,
                seed: (a.seed as number) ?? seed,
              });
              await fetchDemandData();
              toast({ title: "Demand Generated", description: `${a.num_days} days of ${a.season_type} demand created.` });
            } catch (err: unknown) {
              toast({ title: "Generation Failed", description: String(err), variant: "destructive" });
            } finally {
              setGenerating(false);
            }
          } else if (a.action === "select_sku") {
            try {
              await selectSku(a.sku as string);
              setSelectedSku(a.sku as string);
              await fetchDemandData();
            } catch (err: unknown) {
              toast({ title: "SKU Select Failed", description: String(err), variant: "destructive" });
            }
          } else if (a.action === "navigate_to_modify") {
            navigate("/modify");
          }
        }}
        onRefresh={fetchDemandData}
      />
    </>
  );
}
