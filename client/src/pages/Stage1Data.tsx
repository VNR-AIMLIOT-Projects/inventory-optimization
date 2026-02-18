import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Upload, FileText, Sparkles, CheckCircle2, AlertCircle, Loader2, Table as TableIcon } from "lucide-react";
import { useState, useRef, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { uploadDemand, listSkus, generateDemand, getDemandData } from "@/lib/api";
import type { DemandDataResponse } from "@/lib/api";
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
  const [uploadInfo, setUploadInfo] = useState<{ num_days: number; sku: string; start_date: string; end_date: string } | null>(null);

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

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadDemand(file, {
        sku_filter: selectedSku || undefined,
      });
      setUploadSuccess(true);
      setUploadInfo({ num_days: result.num_days, sku: result.sku, start_date: result.date_range.start, end_date: result.date_range.end });
      toast({ title: "Upload Successful", description: `${result.num_days} days loaded for ${result.sku} (${result.date_range.start} → ${result.date_range.end})` });
      await fetchSkus();
      await fetchDemandData();
    } catch (err: any) {
      toast({ title: "Upload Failed", description: err.message, variant: "destructive" });
    } finally {
      setUploading(false);
    }
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const result = await generateDemand({ season_type: seasonType, start_date: startDate, num_days: numDays, seed });
      setUploadSuccess(true);
      setUploadInfo({ num_days: result.data.num_days, sku: "Synthetic", start_date: startDate, end_date: "" });
      toast({ title: "Data Generated", description: `${result.data.num_days} days of ${seasonType} demand generated` });
      await fetchDemandData();
    } catch (err: any) {
      toast({ title: "Generation Failed", description: err.message, variant: "destructive" });
    } finally {
      setGenerating(false);
    }
  };

  const handleSkuSelect = async (sku: string) => {
    setSelectedSku(sku);
    if (!file) return;
    setUploading(true);
    try {
      const result = await uploadDemand(file, {
        sku_filter: sku,
      });
      setUploadInfo({ num_days: result.num_days, sku: result.sku, start_date: result.date_range.start, end_date: result.date_range.end });
      toast({ title: "SKU Selected", description: `Loaded ${result.num_days} days for ${result.sku}` });
      await fetchDemandData();
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setUploading(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && (droppedFile.name.endsWith(".csv") || droppedFile.name.endsWith(".xlsx") || droppedFile.name.endsWith(".xls"))) {
      setFile(droppedFile);
    } else {
      toast({ title: "Invalid File", description: "Please drop a CSV or Excel file", variant: "destructive" });
    }
  }, [toast]);

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
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Step 1: Upload Demand Data" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">

          {/* Success Banner */}
          {uploadSuccess && uploadInfo && (
            <div className="flex items-center gap-3 p-4 bg-emerald-500/10 border border-emerald-500/20 rounded-xl">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <div>
                <p className="text-sm font-semibold text-emerald-400">Data Loaded Successfully</p>
                <p className="text-xs text-muted-foreground">
                  {uploadInfo.num_days} days | SKU: {uploadInfo.sku} | {uploadInfo.start_date}{uploadInfo.end_date ? ` → ${uploadInfo.end_date}` : ""}
                </p>
              </div>
              <Button variant="outline" size="sm" className="ml-auto" onClick={() => navigate("/modify")}>
                Next: Modify Demand →
              </Button>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left: Upload / Generate */}
            <Card className="col-span-1 lg:col-span-2 border-border/50 shadow-lg bg-card/50">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <Badge className="bg-primary/20 text-primary border-primary/20">Step 1</Badge>
                </div>
                <CardTitle>Load Demand Data</CardTitle>
                <CardDescription>Upload your own CSV/Excel file or generate synthetic data</CardDescription>
              </CardHeader>
              <CardContent>
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
                      className={`w-full border-2 border-dashed rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all duration-200 bg-transparent ${
                        dragOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/50 hover:bg-muted/30"
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

                    {/* SKU Selection — visible after upload */}
                    {skus.length > 0 && (
                      <div className="space-y-2 p-4 bg-muted/30 rounded-xl border border-border/50">
                        <Label className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Select SKU</Label>
                        <Select value={selectedSku} onValueChange={handleSkuSelect}>
                          <SelectTrigger><SelectValue placeholder="Choose a SKU" /></SelectTrigger>
                          <SelectContent>
                            {skus.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      </div>
                    )}

                    <Button onClick={handleUpload} disabled={!file || uploading} className="w-full h-12 gap-2 font-bold">
                      {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                      {uploading ? "Uploading..." : "Upload & Analyze"}
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
                <CardTitle className="flex items-center gap-2 text-base">
                  <TableIcon className="w-4 h-4 text-primary" />
                  Data Preview
                </CardTitle>
                <CardDescription>
                  {demandData ? `${demandData.num_days} records loaded` : "No data loaded yet"}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {renderDataPreview()}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
