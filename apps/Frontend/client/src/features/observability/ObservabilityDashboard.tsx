import { useState, useEffect, useCallback } from "react";
import { useLocation } from "wouter";
import {
  Eye, AlertTriangle, Zap, ThumbsUp, ThumbsDown, RefreshCw,
  ChevronLeft, ChevronRight, Brain, Clock, Coins, TrendingDown,
  CheckCircle2, XCircle, ExternalLink, Filter
} from "lucide-react";
import { Sidebar } from "@/components/common/Sidebar";
import { Header } from "@/components/common/Header";
import { useSidebar } from "@/hooks/use-sidebar";
import { cn } from "@/lib/utils";
import { Card, CardContent } from "@/components/ui/card";
import {
  fetchObservabilityMetrics,
  fetchTraces,
  fetchBadAnswers,
  submitTraceFeedback,
  type AITrace,
  type ObservabilityMetrics,
  type PaginatedTraces,
} from "@/lib/api";

// ─── Metric Card ─────────────────────────────────────────────────────────────

function MetricCard({
  icon: Icon, label, value, sub, danger = false, loading = false
}: {
  icon: React.ElementType; label: string; value: string; sub?: string;
  danger?: boolean; loading?: boolean;
}) {
  return (
    <Card className="border-border/50 bg-card/60 backdrop-blur-sm">
      <CardContent className="p-5 flex items-start gap-4">
        <div className={cn(
          "p-2.5 rounded-xl border shrink-0",
          danger
            ? "bg-destructive/10 border-destructive/20 text-destructive"
            : "bg-primary/10 border-primary/20 text-primary"
        )}>
          <Icon className="w-4 h-4" />
        </div>
        <div>
          <p className="text-xs text-muted-foreground font-medium uppercase tracking-widest mb-1">{label}</p>
          {loading
            ? <div className="h-6 w-20 bg-muted animate-pulse rounded" />
            : <p className={cn("text-2xl font-bold tracking-tight", danger && "text-destructive")}>{value}</p>
          }
          {sub && <p className="text-xs text-muted-foreground mt-0.5">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Score Badge ──────────────────────────────────────────────────────────────

function ScoreBadge({ score, label }: { score: number | null; label: string }) {
  if (score === null) return <span className="text-xs text-muted-foreground">—</span>;
  const good = score >= 0.65;
  return (
    <span className={cn(
      "inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full border",
      good
        ? "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
        : "bg-destructive/10 border-destructive/20 text-destructive"
    )}>
      {good ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
      {label}: {score.toFixed(2)}
    </span>
  );
}

// ─── Trace Row ────────────────────────────────────────────────────────────────

function TraceRow({
  trace, onSelect, onFeedback
}: {
  trace: AITrace;
  onSelect: (t: AITrace) => void;
  onFeedback: (id: string, f: 1 | -1) => void;
}) {
  const ts = new Date(trace.created_at).toLocaleString();

  return (
    <div
      className={cn(
        "group grid grid-cols-[1fr_auto_auto_auto] gap-4 items-center px-5 py-3 border-b border-border/40",
        "hover:bg-muted/30 transition-colors cursor-pointer",
        trace.flagged_as_bad && "border-l-2 border-l-destructive"
      )}
      onClick={() => onSelect(trace)}
    >
      {/* Question */}
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground truncate">{trace.question}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{ts} · {trace.llm_model ?? "—"}</p>
      </div>

      {/* Scores */}
      <div className="flex flex-col gap-1 items-end">
        <ScoreBadge score={trace.scores.relevance} label="rel" />
        {trace.scores.hallucination_flag && (
          <span className="text-xs text-destructive font-medium flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> hallucination
          </span>
        )}
      </div>

      {/* Latency */}
      <div className="text-right">
        <p className="text-sm font-mono text-foreground">{trace.latency.total_ms ?? "—"}ms</p>
        <p className="text-xs text-muted-foreground">
          {((trace.tokens.in ?? 0) + (trace.tokens.out ?? 0))} tok
        </p>
      </div>

      {/* Feedback */}
      <div className="flex gap-1" onClick={e => e.stopPropagation()}>
        <button
          id={`feedback-up-${trace.trace_id}`}
          onClick={() => onFeedback(trace.trace_id, 1)}
          className={cn(
            "p-1.5 rounded-lg border transition-colors",
            trace.user_feedback === 1
              ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-400"
              : "border-border text-muted-foreground hover:text-emerald-400 hover:border-emerald-500/40"
          )}
        >
          <ThumbsUp className="w-3.5 h-3.5" />
        </button>
        <button
          id={`feedback-down-${trace.trace_id}`}
          onClick={() => onFeedback(trace.trace_id, -1)}
          className={cn(
            "p-1.5 rounded-lg border transition-colors",
            trace.user_feedback === -1
              ? "border-destructive/40 bg-destructive/10 text-destructive"
              : "border-border text-muted-foreground hover:text-destructive hover:border-destructive/40"
          )}
        >
          <ThumbsDown className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}

// ─── Trace Detail Panel ───────────────────────────────────────────────────────

function TraceDetailPanel({ trace, onClose }: { trace: AITrace; onClose: () => void }) {
  return (
    <div className="fixed inset-y-0 right-0 w-[480px] z-50 bg-card border-l border-border shadow-2xl flex flex-col animate-in slide-in-from-right duration-300">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-border/50 shrink-0">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-primary" />
          <span className="font-semibold text-sm">Trace Detail</span>
        </div>
        <button
          id="trace-detail-close"
          onClick={onClose}
          className="p-1.5 rounded-lg border border-border hover:bg-muted transition-colors"
        >
          ✕
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-6 text-sm">
        {/* Meta */}
        <div className="grid grid-cols-2 gap-3 text-xs">
          <div className="bg-muted/40 rounded-lg p-3">
            <p className="text-muted-foreground mb-1">Trace ID</p>
            <p className="font-mono text-foreground truncate">{trace.trace_id}</p>
          </div>
          <div className="bg-muted/40 rounded-lg p-3">
            <p className="text-muted-foreground mb-1">Timestamp</p>
            <p className="font-mono text-foreground">{new Date(trace.created_at).toLocaleString()}</p>
          </div>
          <div className="bg-muted/40 rounded-lg p-3">
            <p className="text-muted-foreground mb-1">Model</p>
            <p className="font-mono text-foreground">{trace.llm_model ?? "—"}</p>
          </div>
          <div className="bg-muted/40 rounded-lg p-3">
            <p className="text-muted-foreground mb-1">Prompt Version</p>
            <p className="font-mono text-foreground">{trace.prompt_version ?? "—"}</p>
          </div>
        </div>

        {/* Latency + Tokens */}
        <div className="bg-muted/30 rounded-xl p-4 space-y-2">
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-3">Performance</p>
          <div className="grid grid-cols-3 gap-3 text-center">
            {[
              { label: "Retrieval", val: trace.latency.retrieval_ms, unit: "ms" },
              { label: "LLM", val: trace.latency.llm_ms, unit: "ms" },
              { label: "Total", val: trace.latency.total_ms, unit: "ms" },
            ].map(({ label, val, unit }) => (
              <div key={label} className="bg-background/60 rounded-lg p-2">
                <p className="text-xs text-muted-foreground">{label}</p>
                <p className="font-bold text-foreground">{val ?? "—"}<span className="text-xs font-normal text-muted-foreground ml-0.5">{unit}</span></p>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-3 text-center mt-2">
            <div className="bg-background/60 rounded-lg p-2">
              <p className="text-xs text-muted-foreground">Tokens In</p>
              <p className="font-bold text-foreground">{trace.tokens.in ?? "—"}</p>
            </div>
            <div className="bg-background/60 rounded-lg p-2">
              <p className="text-xs text-muted-foreground">Tokens Out</p>
              <p className="font-bold text-foreground">{trace.tokens.out ?? "—"}</p>
            </div>
          </div>
        </div>

        {/* Question */}
        <div>
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-2">Question</p>
          <p className="text-foreground leading-relaxed bg-muted/30 rounded-xl p-4">{trace.question}</p>
        </div>

        {/* Retrieved Chunks */}
        <div>
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-2">
            Retrieved Chunks ({trace.retrieved_chunks.length})
          </p>
          <div className="space-y-2">
            {trace.retrieved_chunks.length === 0
              ? <p className="text-muted-foreground text-xs italic">No chunks retrieved</p>
              : trace.retrieved_chunks.map((c, i) => (
                <div key={i} className="bg-muted/30 rounded-xl p-3 border border-border/40">
                  <div className="flex items-center justify-between mb-1">
                    <p className="text-xs text-muted-foreground font-medium">{c.source ?? `chunk ${i + 1}`}</p>
                    <span className="text-xs font-mono text-primary">sim: {c.similarity?.toFixed(3) ?? "—"}</span>
                  </div>
                  <p className="text-xs text-foreground/80 leading-relaxed line-clamp-4">{c.text}</p>
                </div>
              ))
            }
          </div>
        </div>

        {/* Answer */}
        <div>
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-2">Answer</p>
          <div className={cn(
            "rounded-xl p-4 leading-relaxed text-sm",
            trace.flagged_as_bad
              ? "bg-destructive/5 border border-destructive/20 text-foreground"
              : "bg-muted/30"
          )}>
            {trace.answer ?? <span className="text-muted-foreground italic">No answer recorded</span>}
          </div>
        </div>

        {/* Eval Scores */}
        <div>
          <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest mb-3">Eval Scores</p>
          <div className="space-y-3">
            {[
              { label: "Answer Relevance", val: trace.scores.relevance, threshold: 0.65 },
              { label: "Groundedness", val: trace.scores.groundedness, threshold: 0.60 },
            ].map(({ label, val, threshold }) => (
              <div key={label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-muted-foreground">{label}</span>
                  <span className={cn(
                    "font-mono font-bold",
                    val === null ? "text-muted-foreground" : val >= threshold ? "text-emerald-400" : "text-destructive"
                  )}>
                    {val === null ? "pending..." : val.toFixed(3)}
                  </span>
                </div>
                <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all",
                      val === null ? "w-0" : val >= threshold ? "bg-emerald-500" : "bg-destructive"
                    )}
                    style={{ width: `${Math.round((val ?? 0) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
            <div className="flex items-center gap-2">
              <span className="text-xs text-muted-foreground">Hallucination</span>
              {trace.scores.hallucination_flag
                ? <span className="text-xs text-destructive flex items-center gap-1 font-medium"><AlertTriangle className="w-3 h-3" /> Flagged</span>
                : <span className="text-xs text-emerald-400 flex items-center gap-1 font-medium"><CheckCircle2 className="w-3 h-3" /> Clean</span>
              }
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

type ViewMode = "all" | "bad";

export default function ObservabilityDashboard() {
  const { isCollapsed } = useSidebar();
  const [, setLocation] = useLocation();

  const [metrics, setMetrics] = useState<ObservabilityMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState(true);

  const [viewMode, setViewMode] = useState<ViewMode>("all");
  const [data, setData] = useState<PaginatedTraces | null>(null);
  const [tracesLoading, setTracesLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [hours, setHours] = useState(24);

  const [selectedTrace, setSelectedTrace] = useState<AITrace | null>(null);
  const [localFeedback, setLocalFeedback] = useState<Record<string, 1 | -1>>({});

  // ── Load metrics ──
  const loadMetrics = useCallback(async () => {
    setMetricsLoading(true);
    try { setMetrics(await fetchObservabilityMetrics(hours)); }
    catch { /* ignore */ }
    finally { setMetricsLoading(false); }
  }, [hours]);

  // ── Load traces ──
  const loadTraces = useCallback(async () => {
    setTracesLoading(true);
    try {
      const result = viewMode === "bad"
        ? await fetchBadAnswers(page, 20, hours)
        : await fetchTraces(page, 20, { hours });
      setData(result);
    } catch { /* ignore */ }
    finally { setTracesLoading(false); }
  }, [viewMode, page, hours]);

  useEffect(() => { loadMetrics(); }, [loadMetrics]);
  useEffect(() => { setPage(1); }, [viewMode, hours]);
  useEffect(() => { loadTraces(); }, [loadTraces]);

  const handleFeedback = async (traceId: string, feedback: 1 | -1) => {
    setLocalFeedback(p => ({ ...p, [traceId]: feedback }));
    try { await submitTraceFeedback(traceId, feedback); }
    catch { /* ignore */ }
    setTimeout(loadTraces, 500);
  };

  const enrichedTrace = (t: AITrace): AITrace => ({
    ...t,
    user_feedback: localFeedback[t.trace_id] ?? t.user_feedback,
  });

  return (
    <div className="flex min-h-screen bg-background text-foreground font-sans">
      <Sidebar />

      {/* Trace detail overlay */}
      {selectedTrace && (
        <>
          <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm" onClick={() => setSelectedTrace(null)} />
          <TraceDetailPanel trace={selectedTrace} onClose={() => setSelectedTrace(null)} />
        </>
      )}

      <main className={cn("flex-1", isCollapsed ? "lg:ml-[112px]" : "lg:ml-[288px]", "flex flex-col")}>
        <Header title="AI Observability" />

        <div className="px-6 pb-16 pt-8 space-y-6 max-w-6xl mx-auto w-full animate-in fade-in duration-500">

          {/* Title */}
          <div className="border-l-2 border-primary/50 pl-6 py-2">
            <h1 className="text-3xl font-light tracking-tight mb-2">
              AI <span className="font-bold">Observability</span>
            </h1>
            <p className="text-muted-foreground text-sm font-light">
              Every chatbot request traced end-to-end. When the dashboard is green but the AI gives wrong answers — this is where you find out.
            </p>
          </div>

          {/* Controls row */}
          <div className="flex items-center gap-3 flex-wrap">
            {/* Window selector */}
            <div className="flex items-center gap-2 bg-muted/40 rounded-xl p-1">
              {[4, 24, 72, 168].map(h => (
                <button
                  key={h}
                  id={`window-${h}h`}
                  onClick={() => setHours(h)}
                  className={cn(
                    "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors",
                    hours === h ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {h < 24 ? `${h}h` : h < 168 ? `${h / 24}d` : "7d"}
                </button>
              ))}
            </div>

            {/* View toggle */}
            <div className="flex items-center gap-2 bg-muted/40 rounded-xl p-1">
              {(["all", "bad"] as ViewMode[]).map(mode => (
                <button
                  key={mode}
                  id={`view-${mode}`}
                  onClick={() => setViewMode(mode)}
                  className={cn(
                    "px-3 py-1.5 text-xs font-medium rounded-lg transition-colors flex items-center gap-1.5",
                    viewMode === mode ? "bg-primary text-primary-foreground shadow-sm" : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  {mode === "bad" && <AlertTriangle className="w-3 h-3" />}
                  {mode === "all" ? "All Traces" : "Bad Answers"}
                </button>
              ))}
            </div>

            <button
              id="refresh-traces"
              onClick={() => { loadMetrics(); loadTraces(); }}
              className="p-2 rounded-xl border border-border hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
          </div>

          {/* Metric cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              icon={Brain}
              label="Total Traces"
              value={metricsLoading ? "—" : String(metrics?.total_traces ?? 0)}
              sub={`last ${hours < 24 ? `${hours}h` : hours < 168 ? `${hours / 24}d` : "7d"}`}
              loading={metricsLoading}
            />
            <MetricCard
              icon={AlertTriangle}
              label="Bad Answer Rate"
              value={metricsLoading ? "—" : `${metrics?.bad_answers.rate_pct ?? 0}%`}
              sub={`${metrics?.bad_answers.count ?? 0} flagged`}
              danger={(metrics?.bad_answers.rate_pct ?? 0) > 15}
              loading={metricsLoading}
            />
            <MetricCard
              icon={Clock}
              label="Avg Latency"
              value={metricsLoading ? "—" : `${metrics?.avg_latency_ms ?? 0}ms`}
              loading={metricsLoading}
            />
            <MetricCard
              icon={TrendingDown}
              label="Hallucination Rate"
              value={metricsLoading ? "—" : `${metrics?.hallucination.rate_pct ?? 0}%`}
              sub={`${metrics?.hallucination.count ?? 0} traces`}
              danger={(metrics?.hallucination.rate_pct ?? 0) > 10}
              loading={metricsLoading}
            />
          </div>

          {/* Trace table */}
          <Card className="border-border/50 bg-card/60 backdrop-blur-sm overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[1fr_auto_auto_auto] gap-4 px-5 py-3 border-b border-border/50 bg-muted/20">
              <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest">Question</p>
              <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest text-right">Scores</p>
              <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest text-right">Latency</p>
              <p className="text-xs font-bold text-muted-foreground uppercase tracking-widest text-right">Feedback</p>
            </div>

            {tracesLoading
              ? Array.from({ length: 6 }).map((_, i) => (
                <div key={i} className="px-5 py-4 border-b border-border/30 flex gap-4 items-center">
                  <div className="flex-1 h-4 bg-muted animate-pulse rounded" />
                  <div className="w-24 h-4 bg-muted animate-pulse rounded" />
                  <div className="w-16 h-4 bg-muted animate-pulse rounded" />
                </div>
              ))
              : !data?.items.length
                ? (
                  <div className="py-16 text-center">
                    <Eye className="w-8 h-8 text-muted-foreground/40 mx-auto mb-3" />
                    <p className="text-muted-foreground text-sm">
                      {viewMode === "bad" ? "No bad answers flagged in this window 🎉" : "No traces yet in this window"}
                    </p>
                  </div>
                )
                : data.items.map(t => (
                  <TraceRow
                    key={t.trace_id}
                    trace={enrichedTrace(t)}
                    onSelect={setSelectedTrace}
                    onFeedback={handleFeedback}
                  />
                ))
            }

            {/* Pagination */}
            {data && data.pages > 1 && (
              <div className="flex items-center justify-between px-5 py-3 border-t border-border/40">
                <p className="text-xs text-muted-foreground">
                  {data.total} total · page {data.page} of {data.pages}
                </p>
                <div className="flex gap-2">
                  <button
                    id="traces-prev"
                    disabled={page === 1}
                    onClick={() => setPage(p => p - 1)}
                    className="p-1.5 rounded-lg border border-border disabled:opacity-40 hover:bg-muted transition-colors"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    id="traces-next"
                    disabled={page === data.pages}
                    onClick={() => setPage(p => p + 1)}
                    className="p-1.5 rounded-lg border border-border disabled:opacity-40 hover:bg-muted transition-colors"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}
          </Card>

        </div>
      </main>
    </div>
  );
}
