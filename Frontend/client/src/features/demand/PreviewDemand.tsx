import { Sidebar } from "@/components/common/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { StageNav } from "@/components/common/StageNav";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ImageIcon, Loader2, TableIcon, BarChart3, Shuffle, Activity, CalendarDays, Zap, TrendingUp, CheckCircle2 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState, useEffect, useCallback } from "react";
import { useLocation } from "wouter";
import { getDemandData, listSkus, selectSku, getDemandPreviewVariationsBase64, getDetectedParams } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import type { DemandDataResponse, DetectedParams } from "@/lib/api";
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip as RechartsTooltip } from "recharts";

export default function PreviewDemand() {
  const { isCollapsed } = useSidebar();
  const [, navigate] = useLocation();
  const { toast } = useToast();

  const [skus, setSkus] = useState<string[]>([]);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [switchingSku, setSwitchingSku] = useState(false);

  const [demandData, setDemandData] = useState<DemandDataResponse | null>(null);
  const [params, setParams] = useState<DetectedParams | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  
  const [variations, setVariations] = useState<string[]>([]);
  const [loadingVariations, setLoadingVariations] = useState(false);

  const fetchData = useCallback(async () => {
    setLoadingData(true);
    try {
      const [dataRes, paramsRes] = await Promise.all([
        getDemandData(),
        getDetectedParams()
      ]);
      setDemandData(dataRes);
      setParams(paramsRes);
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
  }, [fetchData, fetchVariations]);

  const handleSkuSwitch = async (sku: string) => {
    if (sku === selectedSku) return;
    setSwitchingSku(true);
    setSelectedSku(sku);
    try {
      await selectSku(sku);
      await Promise.all([fetchData(), fetchVariations()]);
      toast({ title: "SKU Switched", description: `Now viewing preview for ${sku}` });
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setSwitchingSku(false);
    }
  };

  const handleProceed = () => {
    navigate("/train");
  };

  function renderGraphContent() {
    if (loadingData) {
      return (
        <div className="h-[400px] flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      );
    }
    if (demandData?.dates && demandData.dates.length > 0) {
      const chartData = demandData.dates.map((d, i) => ({ date: d, demand: demandData.demand[i] }));
      return (
        <div className="h-[400px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData}>
              <Line type="monotone" dataKey="demand" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} isAnimationActive={false} />
              <YAxis domain={['dataMin', 'dataMax']} hide />
              <RechartsTooltip 
                contentStyle={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))", borderRadius: "8px" }}
                labelStyle={{ color: "hsl(var(--muted-foreground))" }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      );
    }
    return (
      <div className="h-[400px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
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
      <main className={cn("flex-1", isCollapsed ? "lg:ml-[112px]" : "lg:ml-[288px]", "flex flex-col")}>
        <Header title="Finalize Demand" />
        <div className="px-5 py-4 space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-300 max-w-screen-xl mx-auto w-full">

          <StageNav />

          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-6 mt-4">
            <div>
              <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                Final Review
              </h2>
              <p className="text-muted-foreground mt-1">
                Please verify the final demand profile before proceeding to Reinforcement Learning.
              </p>
            </div>
            
            <Button size="lg" className="gap-2 shrink-0 shadow-lg shadow-primary/20" onClick={handleProceed}>
              Accept & Proceed to RL Setup
              <CheckCircle2 className="w-5 h-5" />
            </Button>
          </div>

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

          {/* Stats Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card className="border-border/50 bg-card/50 shadow-sm">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-3 bg-primary/10 rounded-lg text-primary">
                  <Activity className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Mean Demand</p>
                  <p className="text-2xl font-semibold font-mono mt-0.5">
                    {demandData?.stats?.mean ? Math.round(demandData.stats.mean) : "---"}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border/50 bg-card/50 shadow-sm">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-3 bg-amber-500/10 rounded-lg text-amber-500">
                  <Zap className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Max Peak</p>
                  <p className="text-2xl font-semibold font-mono mt-0.5">
                    {demandData?.stats?.max ? Math.round(demandData.stats.max) : "---"}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border/50 bg-card/50 shadow-sm">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-3 bg-emerald-500/10 rounded-lg text-emerald-500">
                  <TrendingUp className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Season Type</p>
                  <p className="text-lg font-semibold mt-1 capitalize">
                    {params?.detected_season_type || "---"}
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card className="border-border/50 bg-card/50 shadow-sm">
              <CardContent className="p-4 flex items-center gap-4">
                <div className="p-3 bg-blue-500/10 rounded-lg text-blue-500">
                  <CalendarDays className="w-5 h-5" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">Total Days</p>
                  <p className="text-2xl font-semibold font-mono mt-0.5">
                    {demandData?.num_days || "---"}
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>

          <Tabs defaultValue="graph" className="space-y-6">
            <TabsList>
              <TabsTrigger value="graph" className="gap-2"><BarChart3 className="w-4 h-4" /> Final Demand</TabsTrigger>
              <TabsTrigger value="table" className="gap-2"><TableIcon className="w-4 h-4" /> Data Table</TabsTrigger>
            </TabsList>

            {/* Current demand graph */}
            <TabsContent value="graph" className="space-y-8">
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader className="pb-2">
                  <CardTitle>Forecasted Profile</CardTitle>
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
                      <h3 className="text-lg font-semibold">Stochastic Realities</h3>
                      <p className="text-sm text-muted-foreground">The RL agent will train on thousands of variations like these, incorporating random noise.</p>
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
