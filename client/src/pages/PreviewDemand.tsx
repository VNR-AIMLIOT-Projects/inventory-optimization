import { Sidebar } from "@/components/Sidebar";
import { StageNav } from "@/components/StageNav";
import { Header } from "@/components/Header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ImageIcon, Loader2, ArrowRight, RotateCcw, TableIcon, BarChart3 } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useState, useEffect, useCallback } from "react";
import { useLocation } from "wouter";
import { getDemandPreviewBase64, getComparisonImageUrl, getDemandData } from "@/lib/api";
import type { DemandDataResponse } from "@/lib/api";

export default function PreviewDemand() {
  const [, navigate] = useLocation();

  const [previewSrc, setPreviewSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [demandData, setDemandData] = useState<DemandDataResponse | null>(null);
  const [loadingData, setLoadingData] = useState(false);
  const [comparisonKey, setComparisonKey] = useState(0);

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

  useEffect(() => {
    fetchPreview();
    fetchData();
  }, [fetchPreview, fetchData]);

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
      <main className="flex-1 ml-72 flex flex-col">
        <Header title="Preview Demand" />
        <div className="p-8 space-y-8 animate-in fade-in duration-500">

          <StageNav />

          <Tabs defaultValue="graph" className="space-y-6">
            <TabsList>
              <TabsTrigger value="graph" className="gap-2"><BarChart3 className="w-4 h-4" /> Graph View</TabsTrigger>
              <TabsTrigger value="comparison" className="gap-2"><ImageIcon className="w-4 h-4" /> Comparison</TabsTrigger>
              <TabsTrigger value="table" className="gap-2"><TableIcon className="w-4 h-4" /> Data Table</TabsTrigger>
            </TabsList>

            {/* Current demand graph */}
            <TabsContent value="graph">
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Current Demand Graph</CardTitle>
                    <CardDescription>
                      {demandData ? `${demandData.num_days} data points` : "Loading..."}
                    </CardDescription>
                  </div>
                  <Button variant="ghost" size="sm" onClick={fetchPreview}>
                    <RotateCcw className="w-4 h-4" />
                  </Button>
                </CardHeader>
                <CardContent>
                  {renderGraphContent()}
                </CardContent>
              </Card>
            </TabsContent>

            {/* Comparison graph */}
            <TabsContent value="comparison">
              <Card className="border-border/50 shadow-lg bg-card/50">
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Original vs Modified</CardTitle>
                    <CardDescription>Compare original uploaded data with your modifications</CardDescription>
                  </div>
                  <Button variant="ghost" size="sm" onClick={() => setComparisonKey((k) => k + 1)}>
                    <RotateCcw className="w-4 h-4" />
                  </Button>
                </CardHeader>
                <CardContent>
                  <img
                    key={comparisonKey}
                    src={getComparisonImageUrl()}
                    alt="Original vs Modified Demand"
                    className="w-full rounded-lg border border-border/50"
                    onError={(e) => {
                      (e.target as HTMLImageElement).style.display = "none";
                      (e.target as HTMLImageElement).parentElement!.innerHTML = `
                        <div class="h-[500px] flex flex-col items-center justify-center text-muted-foreground border-2 border-dashed border-border rounded-xl">
                          <p class="text-sm">No modifications made yet</p>
                          <p class="text-xs mt-1 opacity-70">Modify demand in Step 2 to see comparison</p>
                        </div>
                      `;
                    }}
                  />
                </CardContent>
              </Card>
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
