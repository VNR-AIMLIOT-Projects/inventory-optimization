import type { TrainingRunDetail } from "@/lib/api";

const LOADED_RUNS_KEY = "inventory-optimization.loaded-runs";
const ACTIVE_RUN_ID_KEY = "inventory-optimization.active-loaded-run-id";

function hasStorage() {
  return globalThis.window?.localStorage !== undefined;
}

export function getLoadedHistoricalRuns(): TrainingRunDetail[] {
  if (!hasStorage()) return [];
  try {
    const raw = globalThis.window.localStorage.getItem(LOADED_RUNS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveLoadedHistoricalRuns(runs: TrainingRunDetail[]) {
  if (!hasStorage()) return;
  globalThis.window.localStorage.setItem(LOADED_RUNS_KEY, JSON.stringify(runs));
}

export function getActiveLoadedHistoricalRunId(): number | null {
  if (!hasStorage()) return null;
  const raw = globalThis.window.localStorage.getItem(ACTIVE_RUN_ID_KEY);
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

export function setActiveLoadedHistoricalRunId(runId: number | null) {
  if (!hasStorage()) return;
  if (runId == null) {
    globalThis.window.localStorage.removeItem(ACTIVE_RUN_ID_KEY);
    return;
  }
  globalThis.window.localStorage.setItem(ACTIVE_RUN_ID_KEY, String(runId));
}

export function upsertLoadedHistoricalRun(run: TrainingRunDetail): TrainingRunDetail[] {
  const existing = getLoadedHistoricalRuns();
  const next = [...existing.filter((entry) => entry.id !== run.id && entry.sku !== run.sku), run];
  saveLoadedHistoricalRuns(next);
  setActiveLoadedHistoricalRunId(run.id);
  return next;
}

export function removeLoadedHistoricalRun(runId: number): TrainingRunDetail[] {
  const existing = getLoadedHistoricalRuns();
  const next = existing.filter((entry) => entry.id !== runId);
  saveLoadedHistoricalRuns(next);
  const activeId = getActiveLoadedHistoricalRunId();
  if (activeId === runId) {
    setActiveLoadedHistoricalRunId(next.length > 0 ? next.at(-1)?.id ?? null : null);
  }
  return next;
}