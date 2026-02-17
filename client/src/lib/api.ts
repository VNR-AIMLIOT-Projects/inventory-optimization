// FastAPI Backend API Client
const BASE_URL = "http://localhost:8000";

// ─── Helper ───────────────────────────────────────────────
async function handleResponse<T = any>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || JSON.stringify(body);
    } catch {}
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

// ─── Types ────────────────────────────────────────────────
export interface UploadResponse {
  message: string;
  sku: string;
  num_days: number;
  date_range: { start: string; end: string };
  demand_stats: { mean: number; max: number; min: number; std: number };
}

export interface SkusResponse {
  skus: string[];
  total: number;
}

export interface GenerateRequest {
  season_type?: string;
  start_date?: string;
  num_days?: number;
  seed?: number;
}

export interface GenerateResponse {
  message: string;
  data: DemandDataResponse;
}

export interface DemandDataResponse {
  dates: string[];
  demand: number[];
  num_days: number;
  stats: { mean: number; max: number; min: number; std: number };
}

export interface SpikeRequest {
  date: string;
  amount: number;
}

export interface ModifyResponse {
  message: string;
  data: DemandDataResponse;
}

export interface ScaleRequest {
  start_date: string;
  end_date: string;
  factor: number;
}

export interface TrainRequest {
  episodes?: number;
  max_order?: number | null;
  season_type?: string;
}

export interface TrainResponse {
  status: string;
  message?: string;
}

export interface TrainStatus {
  status: "idle" | "running" | "completed" | "failed";
  current_episode: number;
  total_episodes: number;
  best_reward: number;
  latest_reward: number;
  avg_reward_last_50: number;
  message: string;
}

export interface EvaluateRequest {
  horizon_days?: number;
  initial_inventory?: number;
  service_level_target?: number;
}

export interface EvaluateResponse {
  rl_reward: number;
  oracle_reward: number;
  rule_reward: number;
  rl_vs_oracle_pct: number | null;
  config: Record<string, unknown>;
  message: string;
}

// ─── API Functions ────────────────────────────────────────

/** Health check */
export async function healthCheck(): Promise<{ status: string }> {
  const res = await fetch(`${BASE_URL}/api/health`);
  return handleResponse(res);
}

/** Upload demand CSV/Excel */
export async function uploadDemand(
  file: File,
  options?: {
    sku_column?: string;
    date_column?: string;
    demand_column?: string;
    sku_filter?: string;
    has_header?: string;
  }
): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  if (options?.sku_column) form.append("sku_column", options.sku_column);
  if (options?.date_column) form.append("date_column", options.date_column);
  if (options?.demand_column) form.append("demand_column", options.demand_column);
  if (options?.sku_filter) form.append("sku_filter", options.sku_filter);
  if (options?.has_header) form.append("has_header", options.has_header);

  const res = await fetch(`${BASE_URL}/api/demand/upload`, {
    method: "POST",
    body: form,
  });
  return handleResponse(res);
}

/** List SKUs in uploaded file */
export async function listSkus(): Promise<SkusResponse> {
  const res = await fetch(`${BASE_URL}/api/demand/skus`);
  return handleResponse(res);
}

/** Generate synthetic demand (query params, not JSON body) */
export async function generateDemand(params: GenerateRequest): Promise<GenerateResponse> {
  const qs = new URLSearchParams();
  if (params.season_type) qs.set("season_type", params.season_type);
  if (params.start_date) qs.set("start_date", params.start_date);
  if (params.num_days != null) qs.set("num_days", String(params.num_days));
  if (params.seed != null) qs.set("seed", String(params.seed));
  const res = await fetch(`${BASE_URL}/api/demand/generate?${qs.toString()}`, {
    method: "POST",
  });
  return handleResponse(res);
}

/** Get current demand data */
export async function getDemandData(): Promise<DemandDataResponse> {
  const res = await fetch(`${BASE_URL}/api/demand/data`);
  return handleResponse(res);
}

/** Add demand spike */
export async function addSpike(params: SpikeRequest): Promise<ModifyResponse> {
  const res = await fetch(`${BASE_URL}/api/demand/modify/spike`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse(res);
}

/** Scale demand over period */
export async function scaleDemand(params: ScaleRequest): Promise<ModifyResponse> {
  const res = await fetch(`${BASE_URL}/api/demand/modify/scale`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse(res);
}

/** Reset demand to original */
export async function resetDemand(): Promise<ModifyResponse> {
  const res = await fetch(`${BASE_URL}/api/demand/modify/reset`, {
    method: "POST",
  });
  return handleResponse(res);
}

/** Demand preview graph as base64 */
export async function getDemandPreviewBase64(): Promise<{ image_base64: string }> {
  const res = await fetch(`${BASE_URL}/api/demand/preview/base64`);
  return handleResponse(res);
}

/** Demand preview graph image URL (PNG) */
export function getDemandPreviewImageUrl(): string {
  return `${BASE_URL}/api/demand/preview/image?t=${Date.now()}`;
}

/** Original vs Modified comparison graph image URL */
export function getComparisonImageUrl(): string {
  return `${BASE_URL}/api/demand/preview/comparison?t=${Date.now()}`;
}

/** Start training */
export async function startTraining(params: TrainRequest = {}): Promise<TrainResponse> {
  const res = await fetch(`${BASE_URL}/api/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse(res);
}

/** Poll training status */
export async function getTrainingStatus(): Promise<TrainStatus> {
  const res = await fetch(`${BASE_URL}/api/train/status`);
  return handleResponse(res);
}

/** Training reward curve as base64 */
export async function getRewardCurveBase64(): Promise<{ image_base64: string }> {
  const res = await fetch(`${BASE_URL}/api/train/rewards?t=${Date.now()}`);
  return handleResponse(res);
}

/** Evaluate agent */
export async function evaluateAgent(params: EvaluateRequest = {}): Promise<EvaluateResponse> {
  const res = await fetch(`${BASE_URL}/api/evaluate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse(res);
}

/** Evaluation comparison graph as base64 */
export async function getEvaluationGraphBase64(): Promise<{ image_base64: string }> {
  const res = await fetch(`${BASE_URL}/api/evaluate/graph?t=${Date.now()}`);
  return handleResponse(res);
}
