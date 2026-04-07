import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { useDemandUploads, useUploadDemand } from "@/hooks/use-demand";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { Upload, FileText, AlertCircle, Download, CheckCircle2 } from "lucide-react";
import { useState, useRef, useMemo } from "react";
import { useToast } from "@/hooks/use-toast";
import { format } from "date-fns";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useQueryClient } from "@tanstack/react-query";
import { api } from "@shared/routes";

export default function DataUpload() {
  const queryClient = useQueryClient();
  const { data: demandUploads } = useDemandUploads();
  const { mutate: upload, isPending } = useUploadDemand();
  const [file, setFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { toast } = useToast();
  const [selectedSku, setSelectedSku] = useState<string | null>(null);

  const skus = useMemo(() => {
    if (!demandUploads) return [];
    const allSkus = demandUploads.flatMap(u => (u.skus as string[]) || []);
    return [...new Set(allSkus)].sort();
  }, [demandUploads]);

  // DataUpload no longer stores raw data rows — data lives in files.
  // The chart below won't have per-row data; use the FastAPI backend for previews.
  const filteredData: any[] = [];

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/demand/upload', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.message || 'Upload failed');
      }

      const result = await response.json();
      const mappingInfo = result.columnsDetected 
        ? '\nColumns detected: ' + Object.entries(result.columnsDetected).map(([k,v]) => k + ' \u2190 "' + v + '"').join(', ')
        : '';
      toast({
        title: "Success",
        description: `Uploaded ${result.count} records successfully.` + mappingInfo,
      });
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      
      // Force refresh demand data after upload
      queryClient.invalidateQueries({ queryKey: [api.demand.list.path] });
    } catch (err: any) {
      toast({
        title: "Upload Error",
        description: err.message || "Failed to upload data",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-64 flex flex-col">
        <Header title="Data Upload" />
        
        <div className="px-6 pb-6 pt-2 space-y-4 animate-in fade-in duration-500">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            <Card className="col-span-1 border-border/50 shadow-lg h-fit">
              <CardHeader>
                <CardTitle>Historical Demand Import</CardTitle>
                <CardDescription>Upload any CSV with demand data — columns are auto-detected</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <Button 
                  variant="outline" 
                  className="w-full gap-2 border-dashed"
                  onClick={() => window.location.href = '/api/template'}
                >
                  <Download className="w-4 h-4" />
                  Download Sample Template
                </Button>

                <div 
                  className="border-2 border-dashed border-border rounded-xl p-8 flex flex-col items-center justify-center text-center cursor-pointer hover:bg-muted/30 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <Input 
                    ref={fileInputRef}
                    type="file" 
                    accept=".csv,.tsv,.txt" 
                    className="hidden" 
                    onChange={handleFileChange}
                  />
                  <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mb-3">
                    <Upload className="w-6 h-6 text-primary" />
                  </div>
                  {file ? (
                    <div className="flex items-center gap-2 text-primary font-medium">
                      <FileText className="w-4 h-4" />
                      {file.name}
                    </div>
                  ) : (
                    <>
                      <p className="font-medium text-sm">Select CSV file</p>
                      <p className="text-xs text-muted-foreground mt-1">Any format — we auto-detect columns</p>
                    </>
                  )}
                </div>

                <Button 
                  onClick={handleUpload} 
                  disabled={!file || isPending} 
                  className="w-full"
                >
                  {isPending ? "Processing..." : "Import & Analyze"}
                </Button>
              </CardContent>
            </Card>

            <Card className="col-span-2 border-border/50 shadow-lg min-h-[500px]">
              <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-7">
                <div className="space-y-1">
                  <CardTitle>SKU Analysis</CardTitle>
                  <CardDescription>
                    {skus.length > 0 
                      ? `Found ${skus.length} unique SKUs in historical data`
                      : "No data uploaded yet"}
                  </CardDescription>
                </div>
                {skus.length > 0 && (
                  <Select onValueChange={setSelectedSku} value={selectedSku || ""}>
                    <SelectTrigger className="w-[180px]">
                      <SelectValue placeholder="Select SKU" />
                    </SelectTrigger>
                    <SelectContent>
                      {skus.map(sku => (
                        <SelectItem key={sku} value={sku}>{sku}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                )}
              </CardHeader>
              <CardContent>
                {selectedSku ? (
                  <div className="h-[400px]">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={filteredData}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.2} />
                        <XAxis 
                          dataKey="date" 
                          stroke="#94a3b8" 
                          fontSize={12} 
                          tickLine={false} 
                          axisLine={false}
                          tickFormatter={(str) => format(new Date(str), 'MMM d')}
                        />
                        <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#0f172a', borderColor: '#1e293b' }}
                          itemStyle={{ color: '#e2e8f0' }}
                          labelFormatter={(str) => format(new Date(str), 'MMM d, yyyy')}
                        />
                        <Line 
                          type="monotone" 
                          dataKey="value" 
                          stroke="#8b5cf6" 
                          strokeWidth={3} 
                          dot={false} 
                          activeDot={{ r: 6 }} 
                          name="Historical Demand"
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="h-[400px] flex flex-col items-center justify-center text-muted-foreground bg-muted/20 rounded-xl border border-dashed border-border">
                    <CheckCircle2 className="w-10 h-10 mb-2 opacity-50" />
                    <p>{skus.length > 0 ? "Select an SKU to view demand plot" : "Please upload demand data to begin"}</p>
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
