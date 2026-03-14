// FastAPI Backend API Client
const BASE_URL = "http://localhost:8000";

// ─── Helper ───────────────────────────────────────────────
async function handleResponse<T = any>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || body.message || JSON.stringify(body);
    } catch { }
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
  detected_params?: DetectedParams | null;
}

// ─── Detected Parameters ──────────────────────────────────
export interface PeriodRange {
  start: string;
  end: string;
  start_day: number;
  end_day: number;
}

export interface BaselineParams {
  start: number;
  min: number;
  max: number;
  sigma: number;
}

export interface SeasonalParams {
  peak: number;
  periods: PeriodRange[];
  num_seasons: number;
}

export interface FestivalParams {
  peak: number;
  periods: PeriodRange[];
  num_festivals: number;
}

export interface DetectedParams {
  detected_season_type: string;
  baseline: BaselineParams;
  seasonal: SeasonalParams;
  festival: FestivalParams;
  ramp_days: number;
  num_days: number;
  is_modified?: boolean;
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
  holding_cost?: number;
  stockout_penalty?: number;
}

export interface TrainResponse {
  status: string;
  message?: string;
}

export interface TrainStatus {
  status: "idle" | "running" | "completed" | "failed" | "stopped";
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

/** Select a SKU from the already-uploaded file (backend re-processes) */
export async function selectSku(sku: string): Promise<UploadResponse> {
  const res = await fetch(`${BASE_URL}/api/demand/select-sku?sku=${encodeURIComponent(sku)}`, {
    method: "POST",
  });
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

export interface GraphVariationsResponse {
  images_base64: string[];
  format: string;
}

/** Get 4 random variations of the demand graph */
export async function getDemandPreviewVariationsBase64(): Promise<GraphVariationsResponse> {
  const res = await fetch(`${BASE_URL}/api/demand/preview/variations/base64`);
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

/** Stop training */
export async function stopTraining(): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/api/train/stop`, { method: "POST" });
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

// ─── Detected Parameters ──────────────────────────────────

/** Get detected (or user-modified) demand parameters */
export async function getDetectedParams(): Promise<DetectedParams> {
  const res = await fetch(`${BASE_URL}/api/demand/parameters`);
  return handleResponse(res);
}

/** Update detected params (partial merge) */
export async function updateDetectedParams(params: Partial<DetectedParams>): Promise<DetectedParams> {
  const res = await fetch(`${BASE_URL}/api/demand/parameters`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse(res);
}

/** Reset params to auto-detected values */
export async function resetDetectedParams(): Promise<{ message: string; params: DetectedParams }> {
  const res = await fetch(`${BASE_URL}/api/demand/parameters/reset`, {
    method: "POST",
  });
  return handleResponse(res);
}

// ─── Multi-SKU Types ──────────────────────────────────────

export interface SkuTrainStatus {
  sku: string;
  status: "idle" | "running" | "completed" | "failed" | "stopped";
  current_episode: number;
  total_episodes: number;
  best_reward: number;
  latest_reward: number;
  avg_reward_last_50: number;
  message: string;
}

export interface MultiSkuTrainStatusResponse {
  overall_status: "idle" | "running" | "completed" | "failed" | "stopped";
  skus: Record<string, SkuTrainStatus>;
  message: string;
}

export interface SkuEvalResult {
  sku: string;
  rl_reward: number;
  oracle_reward: number;
  rule_reward: number;
  rl_vs_oracle_pct: number | null;
  config: Record<string, unknown>;
  message: string;
}

export interface MultiSkuEvalResponse {
  skus: Record<string, SkuEvalResult>;
  message: string;
}

// ─── Multi-SKU API Functions ──────────────────────────────

/** Start multi-SKU parallel training */
export async function startMultiSkuTraining(params: TrainRequest = {}): Promise<MultiSkuTrainStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/train/multi`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  return handleResponse(res);
}

/** Poll multi-SKU training status */
export async function getMultiSkuTrainingStatus(): Promise<MultiSkuTrainStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/train/multi/status`);
  return handleResponse(res);
}

/** Stop multi-SKU training */
export async function stopMultiSkuTraining(): Promise<{ message: string }> {
  const res = await fetch(`${BASE_URL}/api/train/multi/stop`, { method: "POST" });
  return handleResponse(res);
}

/** Get per-SKU reward arrays */
export async function getMultiSkuRewards(): Promise<Record<string, number[]>> {
  const res = await fetch(`${BASE_URL}/api/train/multi/rewards`);
  return handleResponse(res);
}

/** Evaluate all trained SKUs */
export async function evaluateMultiSku(): Promise<MultiSkuEvalResponse> {
  const res = await fetch(`${BASE_URL}/api/evaluate/multi`, { method: "POST" });
  return handleResponse(res);
}

/** Get evaluation graph for a specific SKU */
export async function getMultiSkuEvalGraph(skuName: string): Promise<{ image_base64: string }> {
  const res = await fetch(`${BASE_URL}/api/evaluate/multi/graph/${encodeURIComponent(skuName)}?t=${Date.now()}`);
  return handleResponse(res);
}

// ─── History Types ────────────────────────────────────────

export interface EvaluationSummary {
  rl_reward: number;
  oracle_reward: number;
  rule_reward: number;
  rl_vs_oracle_pct: number | null;
}

export interface EvaluationDetail extends EvaluationSummary {
  config?: Record<string, unknown>;
}

export interface TrainingRunSummary {
  id: number;
  sku: string;
  season_type: string;
  episodes: number;
  holding_cost: number;
  stockout_penalty: number;
  best_reward: number | null;
  final_avg_reward: number | null;
  status: string;
  model_path: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string | null;
  evaluation?: EvaluationSummary;
}

export interface TrainingRunDetail extends TrainingRunSummary {
  max_order: number | null;
  action_step: number | null;
  rewards: number[] | null;
  demand_params: Record<string, unknown> | null;
  evaluation?: EvaluationDetail;
}

export interface LoadedTrainingRun extends TrainingRunDetail {
  is_loaded: true;
}

export interface UploadSummary {
  id: number;
  filename: string;
  filepath: string;
  file_type: string;
  skus: string[];
  uploaded_at: string;
}

// ─── History API Functions ────────────────────────────────

/** List all past training runs */
export async function getTrainingRuns(): Promise<TrainingRunSummary[]> {
  const res = await fetch(`${BASE_URL}/api/runs`);
  return handleResponse(res);
}

/** Get a single training run by ID */
export async function getTrainingRun(runId: number): Promise<TrainingRunDetail> {
  const res = await fetch(`${BASE_URL}/api/runs/${runId}`);
  return handleResponse(res);
}

/** Get the currently loaded historical run, if any */
export async function getCurrentLoadedRun(): Promise<LoadedTrainingRun | null> {
  const res = await fetch(`${BASE_URL}/api/runs/current-loaded`);
  if (res.status === 404) return null;
  return handleResponse(res);
}

/** Load a past training run's model into memory */
export async function loadTrainingRun(runId: number): Promise<{ message: string; run_id: number }> {
  const res = await fetch(`${BASE_URL}/api/runs/${runId}/load`, { method: "POST" });
  return handleResponse(res);
}

/** List all past file uploads */
export async function getUploads(): Promise<UploadSummary[]> {
  const res = await fetch(`${BASE_URL}/api/uploads`);
  return handleResponse(res);
}
