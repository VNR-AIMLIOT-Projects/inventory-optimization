import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useDemandData } from "@/hooks/use-demand";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, AreaChart, Area } from "recharts";
import { Upload, FileText, Download, CheckCircle2, Sliders, Calendar, AlertCircle } from "lucide-react";
import { useState, useRef, useMemo } from "react";
import { useToast } from "@/hooks/use-toast";
import { format } from "date-fns";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@shared/routes";
import { Slider } from "@/components/ui/slider";
import { Badge } from "@/components/ui/badge";

export default function Stage1Data() {
  const queryClient = useQueryClient();
  const { data: demandData } = useDemandData();
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [noise, setNoise] = useState([10]);
  const [windowSize, setWindowSize] = useState([7]);

  const skus = useMemo(() => {
    if (!demandData) return [];
    return Array.from(new Set(demandData.map(d => d.sku))).sort();
  }, [demandData]);

  const filteredData = useMemo(() => {
    if (!demandData || !selectedSku) return [];
    return demandData
      .filter(d => d.sku === selectedSku)
      .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  }, [demandData, selectedSku]);

  const syntheticData = useMemo(() => {
    if (filteredData.length === 0) return [];
    // Generate simple synthetic curve based on mean and some seasonality
    const mean = filteredData.reduce((acc, curr) => acc + curr.value, 0) / filteredData.length;
    return filteredData.map((d, i) => ({
      ...d,
      synthetic: Math.round(mean + Math.sin(i/10) * 10 + (Math.random() - 0.5) * noise[0])
    }));
  }, [filteredData, noise]);

  const handleUpload = async () => {
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const response = await fetch('/api/demand/upload', { method: 'POST', body: formData });
      if (!response.ok) throw new Error((await response.json()).message || 'Upload failed');
      const result = await response.json();
      toast({ title: "Success", description: `Detected ${result.count} records.` });
      queryClient.invalidateQueries({ queryKey: [api.demand.list.path] });
      setFile(null);
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Stage 1: Pre-Processing" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">
          
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Step 1 & 2: Import */}
            <Card className="col-span-1 border-border/50 shadow-lg h-fit bg-card/50">
              <CardHeader>
                <div className="flex items-center gap-2 mb-2">
                  <Badge className="bg-primary/20 text-primary border-primary/20">Step 1 & 2</Badge>
                </div>
                <CardTitle>Data Import</CardTitle>
                <CardDescription>Download template and upload 1 year of demand</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <Button variant="outline" className="w-full gap-2" onClick={() => window.location.href = '/api/template'}>
                  <Download className="w-4 h-4" /> Download Excel Template
                </Button>
                <div className="border-2 border-dashed border-border rounded-xl p-6 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-muted/30 transition-colors" onClick={() => fileInputRef.current?.click()}>
                  <Input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={(e) => e.target.files && setFile(e.target.files[0])} />
                  <Upload className="w-8 h-8 text-primary mb-2" />
                  {file ? <span className="text-sm font-medium text-primary">{file.name}</span> : <span className="text-xs text-muted-foreground">Drop demand CSV here</span>}
                </div>
                <Button onClick={handleUpload} disabled={!file} className="w-full">Upload & Analyze</Button>
              </CardContent>
            </Card>

            {/* Step 3 & 4: SKU Analysis */}
            <Card className="col-span-2 border-border/50 shadow-lg bg-card/50">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge className="bg-primary/20 text-primary border-primary/20">Step 3 & 4</Badge>
                  </div>
                  <CardTitle>SKU Selection & Fitting</CardTitle>
                  <CardDescription>{skus.length} SKUs detected in database</CardDescription>
                </div>
                {skus.length > 0 && (
                  <Select onValueChange={setSelectedSku} value={selectedSku || ""}>
                    <SelectTrigger className="w-[200px]"><SelectValue placeholder="Select SKU" /></SelectTrigger>
                    <SelectContent>{skus.map(s => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                  </Select>
                )}
              </CardHeader>
              <CardContent>
                {selectedSku ? (
                  <div className="space-y-6">
                    <div className="h-[300px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={syntheticData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                          <XAxis dataKey="date" hide />
                          <YAxis stroke="#94a3b8" fontSize={10} />
                          <Tooltip contentStyle={{ backgroundColor: '#0f172a' }} />
                          <Legend />
                          <Line type="monotone" dataKey="value" stroke="#8b5cf6" strokeWidth={2} dot={false} name="Actual Data" />
                          <Line type="monotone" dataKey="synthetic" stroke="#10b981" strokeDasharray="5 5" strokeWidth={2} dot={false} name="Fitted Estimate" />
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                    
                    {/* Step 5: Parameters */}
                    <div className="grid grid-cols-2 gap-8 p-4 bg-muted/30 rounded-xl border border-border/50">
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                            <Sliders className="w-3 h-3" /> Demand Noise
                          </label>
                          <span className="text-xs font-mono">{noise[0]}%</span>
                        </div>
                        <Slider value={noise} onValueChange={setNoise} max={50} step={1} />
                      </div>
                      <div className="space-y-4">
                        <div className="flex justify-between items-center">
                          <label className="text-xs font-bold uppercase tracking-wider text-muted-foreground flex items-center gap-2">
                            <Calendar className="w-3 h-3" /> Smoothing Window
                          </label>
                          <span className="text-xs font-mono">{windowSize[0]} days</span>
                        </div>
                        <Slider value={windowSize} onValueChange={setWindowSize} max={30} min={1} step={1} />
                      </div>
                    </div>
                    <div className="flex justify-end">
                      <Button className="gap-2 bg-emerald-600 hover:bg-emerald-700">
                        <CheckCircle2 className="w-4 h-4" /> Validate Fitted Model
                      </Button>
                    </div>
                  </div>
                ) : (
                  <div className="h-[400px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
                    <AlertCircle className="w-10 h-10 mb-2 opacity-20" />
                    <p className="text-sm">Select an SKU to visualize demand patterns</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
