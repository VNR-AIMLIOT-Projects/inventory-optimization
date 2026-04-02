import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Upload, FileText, Sparkles, CheckCircle2, AlertCircle, Loader2, Table as TableIcon, Download, Search, History } from "lucide-react";
import { useState, useRef, useCallback, useEffect } from "react";
import { useToast } from "@/hooks/use-toast";
import { uploadDemand, listSkus, selectSku, generateDemand, getDemandData, getUploads } from "@/lib/api";
import type { DemandDataResponse, UploadSummary } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Label } from "@/components/ui/label";
import { useLocation } from "wouter";

export default function Stage1Data() {
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

  // Drag & drop
  const [dragOver, setDragOver] = useState(false);

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
        <div className="h-[400px] flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      );
    }
    if (demandData?.dates && demandData.dates.length > 0) {
      return (
        <div className="max-h-[500px] overflow-auto rounded-lg border border-border/50">
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
      );
    }
    return (
      <div className="h-[400px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
        <AlertCircle className="w-10 h-10 mb-3 opacity-20" />
        <p className="text-sm">Upload or generate data to preview</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 lg:ml-72 flex flex-col">
        <Header title="Upload Demand Data" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">
          <StageNav />

          {/* Success Banner */}
          {uploadSuccess && uploadInfo && (
            <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <div>
                <p className="text-sm font-semibold text-emerald-400">Data Loaded Successfully</p>
                <p className="text-xs text-muted-foreground">
                  {uploadInfo.num_days} days | SKU: {uploadInfo.sku} | {uploadInfo.start_date}{uploadInfo.end_date ? ` → ${uploadInfo.end_date}` : ""}
                  {uploadInfo.season_type && (
                    <span className={`ml-2 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${uploadInfo.season_type === "summer" ? "bg-amber-500/20 text-amber-400" : "bg-blue-500/20 text-blue-400"
                      }`}>
                      {uploadInfo.season_type === "summer" ? "☀" : "❄"} {uploadInfo.season_type}
                    </span>
                  )}
                </p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left: Upload / Generate */}
            <Card className="col-span-1 lg:col-span-2 border-border/50 shadow-lg bg-card/50">
              <CardHeader>

                <CardTitle>Load Demand Data</CardTitle>
                <CardDescription>Upload your own CSV/Excel file or generate synthetic data</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button variant="outline" className="w-full gap-2 border-dashed" onClick={downloadTemplate}>
                  <Download className="w-4 h-4" /> Download Template CSV
                </Button>

                <Tabs defaultValue="upload" className="space-y-6">
                  <TabsList className="grid w-full grid-cols-2">
                    <TabsTrigger value="upload" className="gap-2"><Upload className="w-4 h-4" /> Upload File</TabsTrigger>
                    <TabsTrigger value="generate" className="gap-2"><Sparkles className="w-4 h-4" /> Generate Synthetic</TabsTrigger>
                  </TabsList>

                  {/* Upload Tab */}
                  <TabsContent value="upload" className="space-y-6">
                    {/* biome-ignore lint: drag-drop zone needs div for drag events */}
                    <button
                      type="button"
                      className={`w-full border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 bg-transparent ${dragOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"
                        }`}
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
                          <FileText className="w-10 h-10 text-primary mb-3" />
                          <span className="text-sm font-semibold text-primary">{file.name}</span>
                          <span className="text-xs text-muted-foreground mt-1">
                            {(file.size / 1024).toFixed(1)} KB — Click to change
                          </span>
                        </>
                      ) : (
                        <>
                          <Upload className="w-10 h-10 text-muted-foreground/50 mb-3" />
                          <span className="text-sm font-medium text-muted-foreground">Drag & drop your CSV or Excel file here</span>
                          <span className="text-xs text-muted-foreground/70 mt-1">or click to browse</span>
                        </>
                      )}
                    </button>

                    <Button onClick={handleUpload} disabled={!file || uploading} className="w-full h-12 gap-2 font-bold">
                      {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                      {uploading ? "Analyzing..." : "Analyze"}
                    </Button>
                  </TabsContent>

                  {/* Generate Tab */}
                  <TabsContent value="generate" className="space-y-6">
                    <div className="grid grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label className="text-xs">Season Type</Label>
                        <Select value={seasonType} onValueChange={setSeasonType}>
                          <SelectTrigger><SelectValue /></SelectTrigger>
                          <SelectContent>
                            <SelectItem value="summer">Summer</SelectItem>
                            <SelectItem value="winter">Winter</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs">Start Date</Label>
                        <Input type="date" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs">Number of Days</Label>
                        <Input type="number" min={30} max={730} value={numDays} onChange={(e) => setNumDays(Number.parseInt(e.target.value) || 365)} />
                      </div>
                      <div className="space-y-2">
                        <Label className="text-xs">Random Seed</Label>
                        <Input type="number" value={seed} onChange={(e) => setSeed(Number.parseInt(e.target.value) || 42)} />
                      </div>
                    </div>
                    <Button onClick={handleGenerate} disabled={generating} className="w-full h-12 gap-2 font-bold">
                      {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                      {generating ? "Generating..." : "Generate Sample Data"}
                    </Button>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>

            {/* Right: Data Preview */}
            <Card className="col-span-1 border-border/50 shadow-lg bg-card/50">
              <CardHeader>
                <div className="flex items-center justify-between">
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
                </div>
                <CardDescription>
                  {demandData ? `${demandData.num_days} records` + (selectedSku ? ` · ${selectedSku}` : "") : "No data loaded yet"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {renderDataPreview()}
              </CardContent>
            </Card>
          </div>

          {/* Upload History */}
          {pastUploads.length > 0 && (
            <Card className="border-border/50 shadow-lg bg-card/50">
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
                          } catch (err: any) {
                            toast({ title: "Load Failed", description: friendlyError(err, "upload"), variant: "destructive" });
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
  );
}
