import { Sidebar } from "@/components/Sidebar";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
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
import { TrendingUp, Zap, RotateCcw, Loader2, ArrowRight, ImageIcon } from "lucide-react";
import { useState, useEffect, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";
import { useLocation } from "wouter";
import { addSpike, scaleDemand, resetDemand, getDemandPreviewBase64, getComparisonImageUrl } from "@/lib/api";

export default function ModifyDemand() {
  const { toast } = useToast();
  const [, navigate] = useLocation();

  // Spike form
  const [spikeDate, setSpikeDate] = useState("");
  const [spikeUnits, setSpikeUnits] = useState(500);
  const [spiking, setSpiking] = useState(false);

  // Scale form
  const [scaleStartDate, setScaleStartDate] = useState("");
  const [scaleEndDate, setScaleEndDate] = useState("");
  const [scaleFactor, setScaleFactor] = useState([1.3]);
  const [scaling, setScaling] = useState(false);

  // Reset
  const [resetting, setResetting] = useState(false);

  // Preview
  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const [loadingPreview, setLoadingPreview] = useState(false);
  const [showComparison, setShowComparison] = useState(false);
  const [comparisonKey, setComparisonKey] = useState(0);

  const refreshPreview = useCallback(async () => {
    setLoadingPreview(true);
    try {
      const data = await getDemandPreviewBase64();
      setPreviewSrc(`data:image/png;base64,${data.image_base64}`);
    } catch {
      // no demand loaded
    } finally {
      setLoadingPreview(false);
    }
  }, []);

  useEffect(() => {
    refreshPreview();
  }, [refreshPreview]);

  const handleSpike = async () => {
    if (!spikeDate) {
      toast({ title: "Missing Date", description: "Please select a date for the spike", variant: "destructive" });
      return;
    }
    setSpiking(true);
    try {
      const result = await addSpike({ date: spikeDate, amount: spikeUnits });
      toast({ title: "Spike Added", description: result.message });
      await refreshPreview();
      setComparisonKey((k) => k + 1);
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setSpiking(false);
    }
  };

  const handleScale = async () => {
    if (!scaleStartDate || !scaleEndDate) {
      toast({ title: "Missing Dates", description: "Please select start and end dates", variant: "destructive" });
      return;
    }
    setScaling(true);
    try {
      const result = await scaleDemand({ start_date: scaleStartDate, end_date: scaleEndDate, factor: scaleFactor[0] });
      toast({ title: "Demand Scaled", description: result.message });
      await refreshPreview();
      setComparisonKey((k) => k + 1);
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setScaling(false);
    }
  };

  const handleReset = async () => {
    setResetting(true);
    try {
      await resetDemand();
      toast({ title: "Demand Reset", description: "Demand data restored to original values" });
      await refreshPreview();
      setShowComparison(false);
    } catch (err: any) {
      toast({ title: "Error", description: err.message, variant: "destructive" });
    } finally {
      setResetting(false);
    }
  };

  function renderPreviewContent() {
    if (loadingPreview) {
      return (
        <div className="h-[500px] flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      );
    }
    if (showComparison) {
      return (
        <div className="space-y-4">
          <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Original vs Modified</p>
          <img
            key={comparisonKey}
            src={getComparisonImageUrl()}
            alt="Comparison: Original vs Modified Demand"
            className="w-full rounded-lg border border-border/50"
            onError={(e) => {
              (e.target as HTMLImageElement).alt = "No modifications made yet — comparison unavailable";
            }}
          />
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
        <p className="text-xs text-muted-foreground/70 mt-1">Upload or generate data in Step 1 first</p>
      </div>
    );
  }

  const factorPercent = Math.round((scaleFactor[0] - 1) * 100);
  const factorLabel = factorPercent >= 0 ? `+${factorPercent}%` : `${factorPercent}%`;

  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Step 2: Modify Demand (Scenario Builder)" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Left column: Modifier forms */}
            <div className="col-span-1 space-y-6">
              {/* Add Spike */}
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className="bg-red-500/20 text-red-400 border-red-500/20">Spike</Badge>
                  </div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Zap className="w-4 h-4 text-red-400" /> Add Demand Spike
                  </CardTitle>
                  <CardDescription>Inject extra demand on a specific date</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="space-y-2">
                    <Label className="text-xs">Date</Label>
                    <Input type="date" value={spikeDate} onChange={(e) => setSpikeDate(e.target.value)} />
                  </div>
                  <div className="space-y-2">
                    <Label className="text-xs">Extra Units</Label>
                    <Input type="number" min={1} value={spikeUnits} onChange={(e) => setSpikeUnits(Number.parseInt(e.target.value) || 0)} />
                  </div>
                  <Button onClick={handleSpike} disabled={spiking} className="w-full gap-2">
                    {spiking ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
                    {spiking ? "Adding..." : "Add Spike"}
                  </Button>
                </CardContent>
              </Card>

              {/* Scale Demand */}
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader>
                  <div className="flex items-center gap-2 mb-1">
                    <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/20">Scale</Badge>
                  </div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <TrendingUp className="w-4 h-4 text-blue-400" /> Scale Demand Period
                  </CardTitle>
                  <CardDescription>Multiply demand over a date range</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <Label className="text-xs">Start Date</Label>
                      <Input type="date" value={scaleStartDate} onChange={(e) => setScaleStartDate(e.target.value)} />
                    </div>
                    <div className="space-y-2">
                      <Label className="text-xs">End Date</Label>
                      <Input type="date" value={scaleEndDate} onChange={(e) => setScaleEndDate(e.target.value)} />
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center">
                      <Label className="text-xs">Scale Factor</Label>
                      <span className="text-xs font-mono font-bold">
                        {scaleFactor[0].toFixed(2)}x{" "}
                        <span className={factorPercent >= 0 ? "text-emerald-400" : "text-red-400"}>({factorLabel})</span>
                      </span>
                    </div>
                    <Slider value={scaleFactor} onValueChange={setScaleFactor} min={0.1} max={3} step={0.05} />
                  </div>
                  <Button onClick={handleScale} disabled={scaling} className="w-full gap-2">
                    {scaling ? <Loader2 className="w-4 h-4 animate-spin" /> : <TrendingUp className="w-4 h-4" />}
                    {scaling ? "Scaling..." : "Apply Scale"}
                  </Button>
                </CardContent>
              </Card>

              {/* Reset + Navigate */}
              <div className="space-y-3">
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
                        This will undo all modifications (spikes, scaling) and restore the original uploaded/generated demand data.
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

                <Button onClick={() => navigate("/preview")} className="w-full gap-2">
                  Next: Preview Demand <ArrowRight className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Right: Graph Preview */}
            <Card className="col-span-1 lg:col-span-2 border-border/50 shadow-lg bg-card/50">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <ImageIcon className="w-5 h-5 text-primary" /> Demand Preview
                  </CardTitle>
                  <CardDescription>Live preview — refreshes after each modification</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={() => setShowComparison(!showComparison)}>
                    {showComparison ? "Show Current" : "Show Comparison"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={refreshPreview}>
                    <RotateCcw className="w-4 h-4" />
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                {renderPreviewContent()}
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  );
}
