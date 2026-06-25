import { Sidebar } from "@/components/common/Sidebar";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { StageNav } from "@/components/common/StageNav";
import { Header } from "@/components/common/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  RotateCcw, Loader2, ImageIcon, ChevronDown, Sliders, Sun, Snowflake,
  Sparkles, CalendarDays, Save, Info, HelpCircle,
} from "lucide-react";
import { useState, useEffect, useCallback, useRef } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import {
  resetDemand, getDemandData, getComparisonImageUrl,
  getDetectedParams, updateDetectedParams, resetDetectedParams,
  listSkus, selectSku,
} from "@/lib/api";
import type { DetectedParams, DemandDataResponse } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { PageCopilot } from "@/features/copilot/PageCopilot";
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip as RechartsTooltip } from "recharts";

/** Reusable inline tooltip info icon */
function InfoTip({ text }: { text: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Info className="w-3 h-3 text-muted-foreground/50 hover:text-muted-foreground cursor-help shrink-0" />
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-[200px] text-xs">
        {text}
      </TooltipContent>
    </Tooltip>
  );
}

export default function ModifyDemand() {
  const { isCollapsed } = useSidebar();
  const { toast } = useToast();
  const [, navigate] = useLocation();

  // Reset
  const [resetting, setResetting] = useState(false);

  // SKU selection
  const [skus, setSkus] = useState<string[]>([]);
  const [selectedSku, setSelectedSku] = useState<string | null>(null);
  const [switchingSku, setSwitchingSku] = useState(false);
  const [modifiedSkus, setModifiedSkus] = useState<Set<string>>(new Set());

  // Preview
  const [demandData, setDemandData] = useState<DemandDataResponse | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [comparisonKey, setComparisonKey] = useState(0);

  // Detected params
  const [params, setParams] = useState<DetectedParams | null>(null);
  const [lastSavedParamsStr, setLastSavedParamsStr] = useState<string>("");
  const [loadingParams, setLoadingParams] = useState(false);
  const [savingParams, setSavingParams] = useState(false);
  const [trendsOpen, setTrendsOpen] = useState(true);
  const [noiseOpen, setNoiseOpen] = useState(true);
  const [anomaliesOpen, setAnomaliesOpen] = useState(true);

  // Explainer
  const [showExplainer, setShowExplainer] = useState(false);

  const refreshPreview = useCallback(async () => {
    setLoadingPreview(true);
    try {
      const data = await getDemandData();
      setDemandData(data);
    } catch {
      // no demand loaded
    } finally {
      setLoadingPreview(false);
    }
  }, []);

  const fetchParams = useCallback(async () => {
    setLoadingParams(true);
    try {
      const p = await getDetectedParams();
      setParams(p);
      setLastSavedParamsStr(JSON.stringify(p));
    } catch {
      // no params yet
    } finally {
      setLoadingParams(false);
    }
  }, []);

  useEffect(() => {
    refreshPreview();
    fetchParams();
    (async () => {
      try {
        const res = await listSkus();
        setSkus(res.skus);
      } catch {
        // No file uploaded yet
      }
    })();
  }, [refreshPreview, fetchParams]);

  const handleSkuSwitch = async (sku: string) => {
    if (sku === selectedSku) return;
    setSwitchingSku(true);
    setSelectedSku(sku);
    try {
      await selectSku(sku);
      await Promise.all([refreshPreview(), fetchParams()]);
      toast({ title: "SKU Switched", description: `Now viewing parameters for ${sku}` });
    } catch (err: any) {
      toast({ title: "SKU Switch Failed", description: friendlyError(err, "sku"), variant: "destructive" });
    } finally {
      setSwitchingSku(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await resetDemand();
      toast({ title: "Demand Reset", description: "Demand data restored to original values." });
      await refreshPreview();
    } catch (err: any) {
      toast({ title: "Reset Failed", description: friendlyError(err, "general"), variant: "destructive" });
    } finally {
      setResetting(false);
    }
  };

  const updateField = <K extends keyof DetectedParams>(key: K, value: DetectedParams[K]) => {
    if (!params) return;
    setParams({ ...params, [key]: value });
  };

  const updateBaseline = (field: string, value: number) => {
    if (!params) return;
    setParams({ ...params, baseline: { ...params.baseline, [field]: value } });
  };

  const updateSeasonal = (field: string, value: number) => {
    if (!params) return;
    setParams({ ...params, seasonal: { ...params.seasonal, [field]: value } });
  };

  const updateFestival = (field: string, value: number) => {
    if (!params) return;
    setParams({ ...params, festival: { ...params.festival, [field]: value } });
  };

  const handleSaveParams = async (currentParams: DetectedParams) => {
    setSavingParams(true);
    try {
      const updated = await updateDetectedParams({
        detected_season_type: currentParams.detected_season_type,
        baseline: currentParams.baseline,
        seasonal: currentParams.seasonal,
        festival: currentParams.festival,
        ramp_days: currentParams.ramp_days,
      });
      setParams(updated);
      setLastSavedParamsStr(JSON.stringify(updated));
      toast({ title: "Parameters Auto-Saved", description: "Graph updated with new values." });
      if (selectedSku) setModifiedSkus((prev) => new Set(prev).add(selectedSku));
      await refreshPreview();
      setComparisonKey((k) => k + 1);
    } catch (err: any) {
      toast({ title: "Save Failed", description: friendlyError(err, "params"), variant: "destructive" });
    } finally {
      setSavingParams(false);
    }
  };

  useEffect(() => {
    if (!params) return;
    const currentStr = JSON.stringify(params);
    if (currentStr === lastSavedParamsStr) return;

    const timer = setTimeout(() => {
      handleSaveParams(params);
    }, 800);
    return () => clearTimeout(timer);
  }, [params, lastSavedParamsStr]);

  const handleResetParams = async () => {
    try {
      const result = await resetDetectedParams();
      setParams(result.params);
      setLastSavedParamsStr(JSON.stringify(result.params));
      toast({ title: "Parameters Reset", description: result.message });
      await refreshPreview();
      setComparisonKey((k) => k + 1);
    } catch (err: any) {
      toast({ title: "Reset Failed", description: friendlyError(err, "params"), variant: "destructive" });
    }
  };


  // Chatbot refresh callback
  const handleChatbotRefresh = useCallback(async () => {
    await Promise.all([refreshPreview(), fetchParams()]);
    if (selectedSku) setModifiedSkus(prev => new Set(prev).add(selectedSku));
  }, [refreshPreview, fetchParams, selectedSku]);

  // ── Preview rendering ─────────────────────────────────────
  function renderPreviewContent() {
    if (loadingPreview) {
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
        <p className="text-xs text-muted-foreground/70 mt-1">Upload or generate data first</p>
      </div>
    );
  }

  const seasonIcon = params?.detected_season_type === "summer"
    ? <Sun className="w-3.5 h-3.5" />
    : params?.detected_season_type === "winter"
      ? <Snowflake className="w-3.5 h-3.5" />
      : <Sparkles className="w-3.5 h-3.5" />;

  const seasonColor = params?.detected_season_type === "summer"
    ? "bg-amber-500/20 text-amber-400 border-amber-500/20"
    : params?.detected_season_type === "winter"
      ? "bg-blue-500/20 text-blue-400 border-blue-500/20"
      : "bg-purple-500/20 text-purple-400 border-purple-500/20";

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <main className={cn("flex-1", isCollapsed ? "lg:ml-[112px]" : "lg:ml-[288px]", "flex flex-col h-screen overflow-hidden")}>
          <Header title="Modify Demand Parameters" />
          <div className="flex-1 px-5 py-4 space-y-5 overflow-y-auto max-w-screen-xl mx-auto w-full">
            <StageNav />

            {/* ── Summary ── */}
            {params && (
              <div className="mb-6">
                <h2 className="text-2xl font-semibold tracking-tight text-foreground">
                  Working with {params.num_days} days of {params.detected_season_type || "unknown"} data
                  {selectedSku && ` for SKU ${selectedSku}`}
                </h2>
                <p className="text-muted-foreground mt-1">
                  Adjust parameters below to simulate different scenarios. Changes save automatically.
                </p>
              </div>
            )}

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
                    className="gap-2 relative"
                  >
                    {switchingSku && selectedSku === sku && <Loader2 className="w-3 h-3 animate-spin" />}
                    {sku}
                    {modifiedSkus.has(sku) && (
                      <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-amber-400" />
                    )}
                  </Button>
                ))}
              </div>
            )}

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* ── Left column ── */}
              <div className="col-span-1 space-y-4">

                {/* DEMAND SETTINGS PANEL */}
                <Card className="border-border/50 shadow-lg bg-card/50">
                  <CardHeader className="pb-3">
                    <div className="flex items-center justify-between">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Sliders className="w-4 h-4 text-primary" /> Demand Settings
                        <InfoTip text="Parameters auto-extracted from your data. Edit them to customize the demand profile." />
                      </CardTitle>
                      {params && (
                        <div className="flex items-center gap-1.5">
                          {params.is_modified && (
                            <Badge variant="outline" className="text-[9px] bg-amber-500/10 text-amber-400 border-amber-500/20">Modified</Badge>
                          )}
                          <Badge className={`${seasonColor} text-[10px] gap-1`}>
                            {seasonIcon}
                            {(params.detected_season_type || "unknown").toUpperCase()}
                          </Badge>
                        </div>
                      )}
                    </div>
                  </CardHeader>

                  <CardContent className="space-y-3">
                    {loadingParams ? (
                      <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-5 h-5 animate-spin text-primary" />
                      </div>
                    ) : !params ? (
                      <div className="text-center py-8 text-muted-foreground">
                        <Sliders className="w-8 h-8 mx-auto mb-2 opacity-20" />
                        <p className="text-xs">Upload demand data first</p>
                      </div>
                    ) : (
                      <>
                        {/* Trends */}
                        <Collapsible open={trendsOpen} onOpenChange={setTrendsOpen}>
                          <CollapsibleTrigger asChild>
                            <button className="flex items-center justify-between w-full py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors border border-transparent hover:border-border/30">
                              <div className="text-left">
                                <span className="text-xs font-bold uppercase tracking-wider text-emerald-400">Trends</span>
                                <p className="text-[10px] text-muted-foreground/70 mt-0.5">Base demand and seasonal patterns</p>
                              </div>
                              <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${trendsOpen ? "rotate-180" : ""}`} />
                            </button>
                          </CollapsibleTrigger>
                          <CollapsibleContent className="pt-2 space-y-2 px-1">
                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  Base Demand <InfoTip text="Central baseline demand" />
                                </Label>
                                <Input type="number" className="h-8 text-xs font-mono" value={params.baseline.start} onChange={(e) => updateBaseline("start", Number(e.target.value))} />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  Season Peak <InfoTip text="Average demand during high-season periods" />
                                </Label>
                                <Input type="number" className="h-8 text-xs font-mono" value={params.seasonal.peak} onChange={(e) => updateSeasonal("peak", Number(e.target.value))} />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  Season Count <InfoTip text="# of seasonal periods detected" />
                                </Label>
                                <Input type="number" className="h-8 text-xs font-mono" value={params.seasonal.num_seasons} onChange={(e) => updateSeasonal("num_seasons", Number(e.target.value))} />
                              </div>
                            </div>
                          </CollapsibleContent>
                        </Collapsible>

                        {/* Noise */}
                        <Collapsible open={noiseOpen} onOpenChange={setNoiseOpen}>
                          <CollapsibleTrigger asChild>
                            <button className="flex items-center justify-between w-full py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors border border-transparent hover:border-border/30">
                              <div className="text-left">
                                <span className="text-xs font-bold uppercase tracking-wider text-amber-400">Noise</span>
                                <p className="text-[10px] text-muted-foreground/70 mt-0.5">Volatility and day-to-day fluctuations</p>
                              </div>
                              <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${noiseOpen ? "rotate-180" : ""}`} />
                            </button>
                          </CollapsibleTrigger>
                          <CollapsibleContent className="pt-2 space-y-2 px-1">
                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  Volatility (Sigma) <InfoTip text="Standard deviation of daily fluctuation" />
                                </Label>
                                <Input type="number" step="0.1" className="h-8 text-xs font-mono" value={params.baseline.sigma} onChange={(e) => updateBaseline("sigma", Number(e.target.value))} />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  Min Floor <InfoTip text="Absolute lowest typical demand" />
                                </Label>
                                <Input type="number" className="h-8 text-xs font-mono" value={params.baseline.min} onChange={(e) => updateBaseline("min", Number(e.target.value))} />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  Max Ceiling <InfoTip text="Absolute highest typical demand (non-peak)" />
                                </Label>
                                <Input type="number" className="h-8 text-xs font-mono" value={params.baseline.max} onChange={(e) => updateBaseline("max", Number(e.target.value))} />
                              </div>
                            </div>
                          </CollapsibleContent>
                        </Collapsible>

                        {/* Anomalies */}
                        <Collapsible open={anomaliesOpen} onOpenChange={setAnomaliesOpen}>
                          <CollapsibleTrigger asChild>
                            <button className="flex items-center justify-between w-full py-2 px-3 rounded-lg hover:bg-muted/50 transition-colors border border-transparent hover:border-border/30">
                              <div className="text-left">
                                <span className="text-xs font-bold uppercase tracking-wider text-red-400">Anomalies</span>
                                <p className="text-[10px] text-muted-foreground/70 mt-0.5">Spikes and rare outlier events</p>
                              </div>
                              <ChevronDown className={`w-3.5 h-3.5 text-muted-foreground transition-transform duration-200 ${anomaliesOpen ? "rotate-180" : ""}`} />
                            </button>
                          </CollapsibleTrigger>
                          <CollapsibleContent className="pt-2 space-y-2 px-1">
                            <div className="grid grid-cols-2 gap-2">
                              <div className="space-y-1">
                                <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  Spike Magnitude <InfoTip text="Average demand during sudden spikes" />
                                </Label>
                                <Input type="number" className="h-8 text-xs font-mono" value={params.festival.peak} onChange={(e) => updateFestival("peak", Number(e.target.value))} />
                              </div>
                              <div className="space-y-1">
                                <Label className="text-[10px] text-muted-foreground flex items-center gap-1">
                                  Spike Frequency <InfoTip text="# of short demand spikes detected" />
                                </Label>
                                <Input type="number" className="h-8 text-xs font-mono" value={params.festival.num_festivals} onChange={(e) => updateFestival("num_festivals", Number(e.target.value))} />
                              </div>
                            </div>
                          </CollapsibleContent>
                        </Collapsible>

                        <div className="pt-3 border-t border-border/30">
                          {savingParams && (
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <Loader2 className="w-3 h-3 animate-spin" /> Saving changes...
                            </div>
                          )}
                        </div>
                      </>
                    )}
                  </CardContent>
                </Card>

                {/* Reset + Navigate */}
                <AlertDialog>
                  <AlertDialogTrigger asChild>
                    <Button variant="outline" className="w-full gap-2 border-red-500/30 text-red-400 hover:bg-red-500/10">
                      <RotateCcw className="w-4 h-4" /> Reset to Original
                    </Button>
                  </AlertDialogTrigger>
                  <AlertDialogContent>
                    <AlertDialogHeader>
                      <AlertDialogTitle>Reset Demand Data?</AlertDialogTitle>
                      <AlertDialogDescription>
                        This will undo all modifications and restore the original uploaded/generated demand data. This cannot be undone.
                      </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                      <AlertDialogCancel>Cancel</AlertDialogCancel>
                      <AlertDialogAction onClick={handleReset} disabled={resetting}>
                        {resetting ? "Resetting..." : "Yes, Reset"}
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>

              {/* ── Right: Graph Preview ── */}
              <Card className="col-span-1 lg:col-span-2 border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <ImageIcon className="w-5 h-5 text-primary" /> Demand Preview
                      </CardTitle>
                      <CardDescription className="mt-1">Live preview — refreshes after saving parameters or using the AI assistant</CardDescription>
                    </div>
                    <Button variant="ghost" size="sm" onClick={refreshPreview}>
                      <RotateCcw className="w-4 h-4" />
                    </Button>
                  </div>

                  {/* Mini Summary Stats */}
                  {params && (
                    <div className="flex gap-3 mt-3 flex-wrap">
                      {[
                        { label: "Avg", value: params.baseline.start, color: "text-emerald-400" },
                        { label: "Peak", value: params.seasonal.peak, color: "text-amber-400" },
                        { label: "Seasons", value: params.seasonal.num_seasons, color: "text-amber-400" },
                        { label: "Festivals", value: params.festival.num_festivals, color: "text-red-400" },
                      ].map((stat) => (
                        <div key={stat.label} className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/40 border border-border/30">
                          <span className="text-[10px] text-muted-foreground">{stat.label}</span>
                          <span className={`text-xs font-bold font-mono ${stat.color}`}>{stat.value}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardHeader>
                <CardContent>
                  {renderPreviewContent()}
                </CardContent>
              </Card>
            </div>
          </div>
        </main>
      </div>
      <PageCopilot
        page="modify"
        title="Demand Assistant"
        subtitle={params ? "● Ready · Data loaded" : "○ Waiting for data"}
        disabled={!params}
        disabledPlaceholder="Upload demand data first..."
        quickActions={[
          "Set avg demand to 200 units",
          "Add a spike of 500 units on 2025-06-15",
          "Scale demand up by 20%",
          "Reset to original data",
        ]}
        pageContext={params ? { params } : {}}
        onRefresh={handleChatbotRefresh}
      />
    </TooltipProvider>
  );
}
