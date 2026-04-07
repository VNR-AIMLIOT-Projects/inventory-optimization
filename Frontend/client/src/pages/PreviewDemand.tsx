import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ImageIcon, Loader2, TableIcon, BarChart3, Shuffle } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState, useEffect, useCallback } from "react";
import { useLocation } from "wouter";
import { getDemandPreviewBase64, getDemandData, listSkus, selectSku, getDemandPreviewVariationsBase64 } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import type { DemandDataResponse } from "@/lib/api";

export default function PreviewDemand() {
  const [, navigate] = useLocation();
  const { toast } = useToast();

  const [skus, setSkus] = useState<string[]>([]);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [switchingSku, setSwitchingSku] = useState(false);

  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [demandData, setDemandData] = useState<DemandDataResponse | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [variations, setVariations] = useState<string[]>([]);
  const [loadingVariations, setLoadingVariations] = useState(false);

  const fetchPreview = useCallback(async () => {
    setLoading(true);
    try {
      const data = await getDemandPreviewBase64();
      setPreviewSrc(`data:image/png;base64,${data.image_base64}`);
    } catch {
      setPreviewSrc(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchData = useCallback(async () => {
    setLoadingData(true);
    try {
      const data = await getDemandData();
      setDemandData(data);
    } catch {
      // no data
    } finally {
      setLoadingData(false);
    }
  }, []);

  const fetchVariations = useCallback(async () => {
    setLoadingVariations(true);
    try {
      const data = await getDemandPreviewVariationsBase64();
      setVariations(data.images_base64 || []);
    } catch {
      setVariations([]);
    } finally {
      setLoadingVariations(false);
    }
  }, []);

  useEffect(() => {
    fetchPreview();
    fetchData();
    fetchVariations();
    // Fetch SKU list on mount
    (async () => {
      try {
        const res = await listSkus();
        setSkus(res.skus);
      } catch {
        // No file uploaded
      }
    })();
  }, [fetchPreview, fetchData, fetchVariations]);

  const handleSkuSwitch = async (sku: string) => {
    if (sku === selectedSku) return;
    setSwitchingSku(true);
    setSelectedSku(sku);
    try {
      await selectSku(sku);
      await Promise.all([fetchPreview(), fetchData(), fetchVariations()]);
      toast({ title: "SKU Switched", description: `Now viewing preview for ${sku}` });
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setSwitchingSku(false);
    }
  };

  function renderGraphContent() {
    if (loading) {
      return (
        <div className="h-[500px] flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      );
    }
    if (previewSrc) {
      return <img src={previewSrc} alt="Demand Preview" className="w-full rounded-lg border border-border/50" />;
    }
    return (
      <div className="h-[500px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
        <ImageIcon className="w-10 h-10 mb-3 opacity-20" />
        <p className="text-sm">No demand data loaded</p>
      </div>
    );
  }

  function renderTableContent() {
    if (loadingData) {
      return (
        <div className="h-[400px] flex items-center justify-center">
          <Loader2 className="w-6 h-6 animate-spin text-primary" />
        </div>
      );
    }
    if (demandData?.dates && demandData.dates.length > 0) {
      return (
        <div className="max-h-[600px] overflow-auto rounded-lg border border-border/50">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-xs w-16">#</TableHead>
                <TableHead className="text-xs">Date</TableHead>
                <TableHead className="text-xs text-right">Demand</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {demandData.dates.slice(0, 100).map((date, i) => (
                <TableRow key={`${date}-${i}`}>
                  <TableCell className="text-xs text-muted-foreground">{i + 1}</TableCell>
                  <TableCell className="text-xs font-mono">{date}</TableCell>
                  <TableCell className="text-xs text-right font-mono font-medium">{demandData.demand[i]}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      );
    }
    return (
      <div className="h-[400px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
        <TableIcon className="w-10 h-10 mb-3 opacity-20" />
        <p className="text-sm">No data available</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 lg:ml-[320px] flex flex-col">
        <Header title="Preview Demand" />
        <div className="px-6 pb-6 pt-2 space-y-4 animate-in fade-in duration-500">

          <StageNav />

          {/* SKU Selector */}
          {skus.length > 1 && (
            <div className="flex gap-2 flex-wrap">
              {skus.map((sku) => (
                <Button
                  key={sku}
                  variant={selectedSku === sku ? "default" : "outline"}
                  size="sm"
                  onClick={() => handleSkuSwitch(sku)}
                  disabled={switchingSku}
                  className="gap-2"
                >
                  {switchingSku && selectedSku === sku && <Loader2 className="w-3 h-3 animate-spin" />}
                  {sku}
                </Button>
              ))}
            </div>
          )}

          <Tabs defaultValue="graph" className="space-y-6">
            <TabsList>
              <TabsTrigger value="graph" className="gap-2"><BarChart3 className="w-4 h-4" /> Graph View</TabsTrigger>
              <TabsTrigger value="table" className="gap-2"><TableIcon className="w-4 h-4" /> Data Table</TabsTrigger>
            </TabsList>

            {/* Current demand graph */}
            <TabsContent value="graph" className="space-y-8">
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Current Demand Graph</CardTitle>
                    <CardDescription>
                      {demandData ? `${demandData.num_days} data points` : "Loading..."}
                    </CardDescription>
                  </div>
                </CardHeader>
                <CardContent>
                  {renderGraphContent()}
                </CardContent>
              </Card>

              {/* Variations */}
              {variations.length > 0 && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 px-2">
                    <Shuffle className="w-5 h-5 text-primary" />
                    <div>
                      <h3 className="text-lg font-semibold">Brownian Motion Variations</h3>
                      <p className="text-sm text-muted-foreground">Different possible realities based on the current parameters and random noise.</p>
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {variations.map((b64, idx) => (
                      <Card key={idx} className="border-border/50 bg-card/50 overflow-hidden">
                        <img src={`data:image/png;base64,${b64}`} alt={`Variation ${idx + 1}`} className="w-full" />
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </TabsContent>



            {/* Data table */}
            <TabsContent value="table">
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <CardTitle>Demand Data Table</CardTitle>
                  <CardDescription>
                    {demandData ? `Showing ${Math.min(demandData.dates?.length ?? 0, 100)} of ${demandData.num_days} records` : "Loading..."}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {renderTableContent()}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
}
