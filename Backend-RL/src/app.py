"""
Inventory Optimization - REST API
===================================
FastAPI application exposing endpoints for:
  1. Demand Extraction   - Upload CSV/Excel, parse demand for a SKU
  2. Demand Modification - Add spikes, scale periods, reset
  3. Graph Preview       - Visualize demand before training
  4. Training Agent      - Train DQN agent on configured demand
  5. Evaluation          - Evaluate trained agent vs baselines

Run:  uvicorn app:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

import io
import os
import sys
import base64
import uuid
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server
import matplotlib.pyplot as plt

import asyncio
import json
from datetime import datetime

from fastapi import FastAPI, UploadFile, File, Query, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

# --- Import local src/ modules FIRST (before path manipulation) ---
from schemas import (
    UploadResponse, SKUListResponse,
    SpikeRequest, ScaleRequest, DemandDataResponse, ModifyResponse,
    TrainRequest, TrainStatusResponse, TrainingStatus, EvalResultResponse,
    GraphResponse, GraphVariationsResponse, SeasonType, DetectedParamsResponse, UpdateParamsRequest,
    SkuTrainStatus, MultiSkuTrainStatusResponse, SkuEvalResult, MultiSkuEvalResponse,
)
from extracts_demand import load_and_process_data, plot_demand_preview, detect_demand_parameters, regenerate_demand_from_params, list_all_skus, load_all_skus_data
from demand_modifier import DemandModifier
from database import get_db, SessionLocal
from models import UploadedFile, TrainingRun, EvaluationResult
import storage_service
from queue_service import publish_training_job, ProgressListener

# --- Add RL experiment modules to path (for demand.py, trainer.py, etc.) ---
RL_DIR = os.path.join(os.path.dirname(__file__), "..", "experiments", "backend-implementation")
sys.path.insert(0, os.path.abspath(RL_DIR))

from demand import generate_demand, prepare_env_data
from trainer import train_agent, evaluate_and_plot, train_and_evaluate_single_sku, train_all_skus_parallel

# ==========================================
# APP INITIALISATION
# ==========================================
app = FastAPI(
    title="Inventory Optimization API",
    description="REST endpoints for DQN-based inventory optimization: "
                "upload demand data, modify scenarios, preview graphs, and train the RL agent.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==========================================
# IN-MEMORY SESSION STORE
# ==========================================
# For simplicity, we keep a single global session.
# In production, use Redis / DB keyed by user/session ID.
_store = {
    "raw_df": None,          # DataFrame after upload & extraction
    "modifier": None,        # DemandModifier instance
    "sku": None,             # Currently selected SKU
    "trained_agent": None,   # Trained DQNAgent
    "train_rewards": [],     # Reward history from training
    "train_max_order": None,
    "train_action_step": None,
    "train_holding_cost": 5,
    "train_stockout_penalty": 200,
    "train_status": {
        "status": TrainingStatus.IDLE,
        "current_episode": 0,
        "total_episodes": 0,
        "best_reward": 0.0,
        "latest_reward": 0.0,
        "avg_reward_last_50": 0.0,
        "message": "",
    },
    "eval_results": None,    # Latest evaluation results dict
    "uploaded_filepath": None,
    "detected_params": None,   # Auto-detected demand parameters
    "modified_params": None,   # User-modified parameters (overrides detected)
    "training_stop_requested": False,
    "train_started_at": None,
    "uploaded_file_id": None,        # DB ID of uploaded file
    "current_run_id": None,          # DB ID of current training run
    # Per-SKU persistent state (survives SKU switching)
    "per_sku_detected_params": {},   # {sku: detected_params dict}
    "per_sku_modified_params": {},   # {sku: modified_params dict}
    "per_sku_raw_dfs": {},           # {sku: raw DataFrame}
    "per_sku_modifiers": {},         # {sku: DemandModifier instance}
    # Multi-SKU state
    "multi_sku_status": {},          # {sku_name: SkuTrainStatus dict}
    "multi_sku_overall": TrainingStatus.IDLE,
    "multi_sku_agents": {},          # {sku_name: agent}
    "multi_sku_rewards": {},         # {sku_name: [rewards]}
    "multi_sku_configs": {},         # {sku_name: {max_order, action_step, ...}}
    "multi_sku_eval_results": {},    # {sku_name: {rl_df, oracle_df, rule_df}}
    "multi_sku_stop_requested": False,
}

UPLOAD_DIR = storage_service.UPLOADS_DIR


# ==========================================
# WEBSOCKET CONNECTION MANAGER
# ==========================================
class TrainingWSManager:
    """Manages WebSocket connections for live training updates."""
    def __init__(self):
        self.connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._broadcast_count = 0

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        # Capture the running event loop so background threads can schedule sends
        self._loop = asyncio.get_running_loop()
        print(f"[WS] Client connected. Total connections: {len(self.connections)}")
        # Send greeting so the client can confirm the connection works
        try:
            await ws.send_json({"type": "connected", "message": "WebSocket connected"})
        except Exception:
            pass

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)
        print(f"[WS] Client disconnected. Total connections: {len(self.connections)}")

    def broadcast_from_thread(self, data: dict):
        """Thread-safe broadcast — schedules coroutine on the event loop."""
        if not self.connections or self._loop is None:
            return
        self._broadcast_count += 1
        if self._broadcast_count <= 3 or self._broadcast_count % 100 == 0:
            print(f"[WS] Broadcasting #{self._broadcast_count} to {len(self.connections)} client(s): type={data.get('type')}, sku={data.get('sku', 'N/A')}")
        asyncio.run_coroutine_threadsafe(self._broadcast(data), self._loop)

    async def _broadcast(self, data: dict):
        dead: list[WebSocket] = []
        for ws in self.connections:
            try:
                await ws.send_json(data)
            except Exception as e:
                print(f"[WS] send_json failed: {e}")
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


ws_manager = TrainingWSManager()


# ==========================================
# RabbitMQ PROGRESS LISTENER → WS RELAY
# ==========================================
def _on_worker_progress(msg: dict):
    """Called by ProgressListener when the RL worker publishes a progress message.
    Relays to WebSocket clients and updates in-memory status dicts."""
    msg_type = msg.get("type")
    sku = msg.get("sku", "unknown")

    if msg_type == "episode":
        # Update single-SKU in-memory status
        if _store.get("current_run_id") == msg.get("run_id"):
            _store["train_status"].update({
                "status": TrainingStatus.RUNNING,
                "current_episode": msg.get("episode", 0),
                "total_episodes": msg.get("total_episodes", 0),
                "best_reward": msg.get("best_reward", 0.0),
                "latest_reward": msg.get("reward", 0.0),
                "avg_reward_last_50": msg.get("avg_reward_last_50", 0.0),
            })
        # Update multi-SKU in-memory status
        if sku in _store.get("multi_sku_status", {}):
            _store["multi_sku_status"][sku].update({
                "status": TrainingStatus.RUNNING,
                "current_episode": msg.get("episode", 0),
                "total_episodes": msg.get("total_episodes", 0),
                "best_reward": msg.get("best_reward", 0.0),
                "latest_reward": msg.get("reward", 0.0),
                "avg_reward_last_50": msg.get("avg_reward_last_50", 0.0),
            })

    elif msg_type == "status":
        status_str = msg.get("status", "")
        run_id = msg.get("run_id")
        if _store.get("current_run_id") == run_id:
            if status_str in ("completed", "success"):
                _store["train_status"]["status"] = TrainingStatus.COMPLETED
                _store["train_status"]["message"] = msg.get("message", "Training complete.")
            elif status_str in ("failed", "failure"):
                _store["train_status"]["status"] = TrainingStatus.FAILED
                _store["train_status"]["message"] = msg.get("message", "Training failed.")
            elif status_str in ("stopped", "cancelled"):
                _store["train_status"]["status"] = TrainingStatus.STOPPED
                _store["train_status"]["message"] = msg.get("message", "Training stopped.")
        # Multi-SKU
        if sku in _store.get("multi_sku_status", {}):
            if status_str in ("completed", "success"):
                _store["multi_sku_status"][sku]["status"] = TrainingStatus.COMPLETED
                _store["multi_sku_status"][sku]["message"] = msg.get("message", "Completed.")
                # Populate rewards from DB for this SKU
                try:
                    run_id_for_sku = _store.get("multi_sku_run_ids", {}).get(sku)
                    if run_id_for_sku:
                        db = SessionLocal()
                        run_row = db.query(TrainingRun).filter(TrainingRun.id == run_id_for_sku).first()
                        if run_row and run_row.rewards:
                            _store["multi_sku_rewards"][sku] = run_row.rewards
                        db.close()
                except Exception as e:
                    print(f"[Progress] Could not load rewards for {sku}: {e}")
                # Populate eval results from the progress message
                if msg.get("rl_reward") is not None:
                    _store["multi_sku_eval_results"][sku] = {
                        "rl_reward": msg.get("rl_reward", 0.0),
                        "oracle_reward": msg.get("oracle_reward", 0.0),
                        "rule_reward": msg.get("rule_reward", 0.0),
                        "rl_vs_oracle_pct": msg.get("rl_vs_oracle_pct"),
                    }
            elif status_str in ("failed", "failure"):
                _store["multi_sku_status"][sku]["status"] = TrainingStatus.FAILED
                _store["multi_sku_status"][sku]["message"] = msg.get("message", "Failed.")
            elif status_str in ("cancelled", "stopped"):
                _store["multi_sku_status"][sku]["status"] = TrainingStatus.STOPPED
                _store["multi_sku_status"][sku]["message"] = msg.get("message", "Stopped.")
            # Check if all SKUs are done
            all_done = all(
                s["status"] in (TrainingStatus.COMPLETED, TrainingStatus.FAILED, TrainingStatus.STOPPED)
                for s in _store["multi_sku_status"].values()
            )
            if all_done and _store["multi_sku_overall"] == TrainingStatus.RUNNING:
                statuses = [s["status"] for s in _store["multi_sku_status"].values()]
                if any(st == TrainingStatus.FAILED for st in statuses):
                    _store["multi_sku_overall"] = TrainingStatus.FAILED
                elif any(st == TrainingStatus.STOPPED for st in statuses):
                    _store["multi_sku_overall"] = TrainingStatus.STOPPED
                else:
                    _store["multi_sku_overall"] = TrainingStatus.COMPLETED

    # Forward to WebSocket clients
    ws_manager.broadcast_from_thread(msg)


def _start_progress_listener():
    """Start the RabbitMQ progress listener in a daemon thread."""
    rabbitmq_url = os.environ.get("RABBITMQ_URL")
    if not rabbitmq_url:
        print("[ProgressListener] RABBITMQ_URL not set — skipping listener (local dev mode).")
        return
    try:
        listener = ProgressListener(_on_worker_progress)
        listener.start()
        print("[ProgressListener] Started — relaying worker progress to WebSocket clients.")
    except Exception as e:
        print(f"[ProgressListener] Failed to start: {e}")


# Start listener when the module loads (FastAPI startup)
_start_progress_listener()


# ==========================================
# HELPER FUNCTIONS
# ==========================================
def _demand_stats(df: pd.DataFrame) -> dict:
    """Return summary stats for the Demand column."""
    col = "Demand" if "Demand" in df.columns else "demand"
    return {
        "mean": round(float(df[col].mean()), 2),
        "max": int(df[col].max()),
        "min": int(df[col].min()),
        "std": round(float(df[col].std()), 2),
    }


def _demand_data_response(df: pd.DataFrame) -> DemandDataResponse:
    """Build a DemandDataResponse from a DataFrame."""
    date_col = "Date" if "Date" in df.columns else "date"
    demand_col = "Demand" if "Demand" in df.columns else "demand"
    return DemandDataResponse(
        dates=[str(d.date()) if hasattr(d, "date") else str(d) for d in df[date_col]],
        demand=df[demand_col].astype(int).tolist(),
        num_days=len(df),
        stats=_demand_stats(df),
    )


def _fig_to_base64(fig) -> str:
    """Convert a matplotlib Figure to a base64-encoded PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


def _get_modifier() -> DemandModifier:
    """Return the current DemandModifier or raise 400."""
    if _store["modifier"] is None:
        raise HTTPException(status_code=400, detail="No demand data loaded. Upload a file first via POST /api/demand/upload.")
    return _store["modifier"]


# ------------------------------------------------------------------
# Period auto-generation helpers (for num_seasons / num_festivals)
# ------------------------------------------------------------------
def _get_occupied_days(periods: list) -> set:
    """Return set of day indices covered by a list of period dicts."""
    occupied = set()
    for p in periods:
        for d in range(int(p["start_day"]), int(p["end_day"]) + 1):
            occupied.add(d)
    return occupied


def _find_gaps(occupied: set, num_days: int) -> list:
    """Find contiguous free day ranges as (start, end) tuples."""
    gaps = []
    gap_start = None
    for d in range(num_days):
        if d not in occupied:
            if gap_start is None:
                gap_start = d
        else:
            if gap_start is not None:
                gaps.append((gap_start, d - 1))
                gap_start = None
    if gap_start is not None:
        gaps.append((gap_start, num_days - 1))
    return gaps


def _generate_new_periods(count: int, duration: int, num_days: int,
                          occupied: set, dates) -> list:
    """Place *count* new periods of *duration* days in the largest available gaps."""
    new_periods = []
    for _ in range(count):
        gaps = _find_gaps(occupied, num_days)
        if not gaps:
            break
        gaps.sort(key=lambda g: g[1] - g[0], reverse=True)
        gap_s, gap_e = gaps[0]
        actual_dur = min(duration, gap_e - gap_s + 1)
        center = (gap_s + gap_e) // 2
        ps = max(0, center - actual_dur // 2)
        pe = min(num_days - 1, ps + actual_dur - 1)

        s_date = str(pd.to_datetime(dates.iloc[min(ps, len(dates) - 1)]).date()) if ps < len(dates) else "auto"
        e_date = str(pd.to_datetime(dates.iloc[min(pe, len(dates) - 1)]).date()) if pe < len(dates) else "auto"

        new_periods.append({
            "start": s_date,
            "end": e_date,
            "start_day": int(ps),
            "end_day": int(pe),
        })
        for d in range(ps, pe + 1):
            occupied.add(d)
    return new_periods


def _reconcile_periods(params: dict, original_df):
    """
    Ensure num_seasons matches len(seasonal.periods) and
    num_festivals matches len(festival.periods) by auto-generating
    or trimming period ranges.
    """
    dates = original_df["Date"]
    num_days = params.get("num_days", len(dates))

    # --- Seasonal ---
    seasonal = params["seasonal"]
    target_s = seasonal.get("num_seasons", len(seasonal.get("periods", [])))
    current_s = seasonal.get("periods", [])

    if target_s > len(current_s):
        needed = target_s - len(current_s)
        occupied = _get_occupied_days(current_s)
        season_dur = min(60, max(14, num_days // (3 * max(target_s, 1))))
        new = _generate_new_periods(needed, season_dur, num_days, occupied, dates)
        seasonal["periods"] = current_s + new
    elif target_s < len(current_s):
        seasonal["periods"] = current_s[:target_s]
    seasonal["num_seasons"] = len(seasonal["periods"])

    # --- Festival ---
    festival = params["festival"]
    target_f = festival.get("num_festivals", len(festival.get("periods", [])))
    current_f = festival.get("periods", [])

    if target_f > len(current_f):
        needed = target_f - len(current_f)
        # Exclude both existing festival AND seasonal ranges
        occupied = _get_occupied_days(current_f + seasonal.get("periods", []))
        new = _generate_new_periods(needed, 5, num_days, occupied, dates)
        festival["periods"] = current_f + new
    elif target_f < len(current_f):
        festival["periods"] = current_f[:target_f]
    festival["num_festivals"] = len(festival["periods"])


def _apply_param_adjustments(df: pd.DataFrame) -> pd.DataFrame:
    """
    If the user has modified demand parameters, adjust the demand data proportionally.
    
    Scaling logic:
    - Seasonal periods: scale demand by (modified_peak / detected_peak)
    - Festival periods: scale demand by (modified_festival_peak / detected_festival_peak)
    - Baseline: shift demand by (modified_baseline - detected_baseline)
    """
    detected = _store.get("detected_params")
    modified = _store.get("modified_params")
    
    if detected is None or modified is None:
        return df
    
    result = df.copy()
    demand_col = "Demand" if "Demand" in result.columns else "demand"
    date_col = "Date" if "Date" in result.columns else "date"
    
    # 1. Baseline shift — apply to ALL days
    detected_baseline = detected["baseline"]["start"]
    modified_baseline = modified["baseline"]["start"]
    if detected_baseline != modified_baseline and detected_baseline > 0:
        baseline_ratio = modified_baseline / detected_baseline
        # Apply gentle shift: only affect the baseline portion
        result[demand_col] = (result[demand_col] * baseline_ratio).astype(int)
    
    # 2. Seasonal peak scaling — apply only to seasonal periods
    detected_seasonal = detected["seasonal"]["peak"]
    modified_seasonal = modified["seasonal"]["peak"]
    if detected_seasonal != modified_seasonal and detected_seasonal > 0:
        season_ratio = modified_seasonal / detected_seasonal
        for period in detected["seasonal"].get("periods", []):
            start = pd.to_datetime(period["start"])
            end = pd.to_datetime(period["end"])
            mask = (result[date_col] >= start) & (result[date_col] <= end)
            if mask.any():
                result.loc[mask, demand_col] = (result.loc[mask, demand_col] * season_ratio).astype(int)
    
    # 3. Festival peak scaling — apply only to festival periods
    detected_festival = detected["festival"]["peak"]
    modified_festival = modified["festival"]["peak"]
    if detected_festival != modified_festival and detected_festival > 0:
        festival_ratio = modified_festival / detected_festival
        for period in detected["festival"].get("periods", []):
            start = pd.to_datetime(period["start"])
            end = pd.to_datetime(period["end"])
            mask = (result[date_col] >= start) & (result[date_col] <= end)
            if mask.any():
                result.loc[mask, demand_col] = (result.loc[mask, demand_col] * festival_ratio).astype(int)
    
    # Ensure no negative demand
    result[demand_col] = result[demand_col].clip(lower=0)
    
    return result


# ==========================================
# 1. DEMAND EXTRACTION ENDPOINTS
# ==========================================
# @app.post("/api/demand/upload", response_model=UploadResponse, tags=["Demand Extraction"])
# async def upload_demand_file(
#     file: UploadFile = File(..., description="CSV or Excel file with demand data"),
#     sku: str = Query(default=None, description="Target SKU to extract (auto-selects if omitted)"),
# ):
#     """
#     Upload a CSV/Excel demand file and extract time-series demand for a specific SKU.

#     The file should follow the template format with columns: Date, SKU, Demand.
#     Alternatively, wide-format (Date, SKU1, SKU2...) is also supported.
#     """
#     # Validate extension
#     ext = os.path.splitext(file.filename)[1].lower()
#     if ext not in (".csv", ".xlsx", ".xls"):
#         raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Use .csv or .xlsx")

#     # Save temp file
#     filepath = os.path.join(UPLOAD_DIR, file.filename)
#     content = await file.read()
#     with open(filepath, "wb") as f:
#         f.write(content)

#     # Process
#     try:
#         df = load_and_process_data(filepath, target_sku=sku)
#     except ValueError as e:
#         raise HTTPException(status_code=400, detail=str(e))
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error processing file: {e}")

#     resolved_sku = sku or "auto-selected"
#     _store["raw_df"] = df
#     _store["modifier"] = DemandModifier(df)
#     _store["sku"] = resolved_sku
#     _store["uploaded_filepath"] = filepath

#     return UploadResponse(
#         message=f"Successfully loaded demand data for SKU: {resolved_sku}",
#         sku=resolved_sku,
#         num_days=len(df),
#         date_range={
#             "start": str(df["Date"].iloc[0].date()),
#             "end": str(df["Date"].iloc[-1].date()),
#         },
#         demand_stats=_demand_stats(df),
#     )


@app.post("/api/demand/upload", response_model=UploadResponse, tags=["Demand Extraction"])
async def upload_demand_file(
    file: UploadFile = File(..., description="CSV or Excel file with demand data"),
    sku: str = Query(default=None, description="Target SKU to extract (auto-selects if omitted)"),
):
    # Validate extension
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".csv", ".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail=f"Unsupported file type '{ext}'. Use .csv or .xlsx")

    # Save temp file
    filepath = os.path.join(UPLOAD_DIR, file.filename)
    content = await file.read()
    with open(filepath, "wb") as f:
        f.write(content)

    # Process
    try:
        df = load_and_process_data(filepath, target_sku=sku)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {e}")

    resolved_sku = sku or "auto-selected"
    _store["raw_df"] = df
    _store["modifier"] = DemandModifier(df)
    _store["sku"] = resolved_sku
    _store["uploaded_filepath"] = filepath
    # Call detect_demand_parameters directly (df.attrs can get lost during DataFrame operations)
    _store["detected_params"] = detect_demand_parameters(df)
    _store["modified_params"] = None  # Reset user modifications on new upload

    # Persist upload metadata to DB
    try:
        db = SessionLocal()
        # Detect all SKUs for the DB record
        all_skus = []
        try:
            if filepath.endswith(".csv"):
                raw = pd.read_csv(filepath)
            else:
                raw = pd.read_excel(filepath)
            raw.columns = [c.strip().lower() for c in raw.columns]
            if "sku" in raw.columns:
                all_skus = sorted(raw["sku"].astype(str).str.strip().unique().tolist())
        except Exception:
            all_skus = [resolved_sku]

        db_file = UploadedFile(
            filename=file.filename,
            filepath=filepath,
            file_type=ext.lstrip("."),
            skus=all_skus,
        )
        db.add(db_file)
        db.commit()
        _store["uploaded_file_id"] = db_file.id
        db.close()
    except Exception as e:
        print(f"[DB] Warning: Could not persist upload metadata: {e}")

    return UploadResponse(
        message=f"Successfully loaded demand data for SKU: {resolved_sku}",
        sku=resolved_sku,
        num_days=len(df),
        date_range={
            "start": str(df["Date"].iloc[0].date()),
            "end": str(df["Date"].iloc[-1].date()),
        },
        demand_stats=_demand_stats(df),
        detected_params=_store["detected_params"],
    )

@app.get("/api/demand/skus", response_model=SKUListResponse, tags=["Demand Extraction"])
async def list_skus_in_file():
    """
    List all SKUs found in the last uploaded file.
    """
    filepath = _store.get("uploaded_filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=400, detail="No file uploaded yet.")

    try:
        if filepath.endswith(".csv"):
            raw = pd.read_csv(filepath)
        else:
            raw = pd.read_excel(filepath)
        raw.columns = [c.strip().lower() for c in raw.columns]

        if "sku" in raw.columns:
            skus = sorted(raw["sku"].astype(str).str.strip().unique().tolist())
        else:
            date_col = None
            for c in ["date", "timestamp", "day", "tx_date"]:
                if c in raw.columns:
                    date_col = c
                    break
            if not date_col:
                date_col = raw.columns[0]
            skus = [c for c in raw.columns if c != date_col]

        return SKUListResponse(skus=skus, total=len(skus))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/demand/select-sku", response_model=UploadResponse, tags=["Demand Extraction"])
async def select_sku(sku: str = Query(..., description="SKU to select from the uploaded file")):
    """
    Re-process the already-uploaded file with a different SKU filter.
    Saves current SKU's state and restores saved state for the target SKU.
    """
    filepath = _store.get("uploaded_filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=400, detail="No file uploaded yet.")

    # --- Save current SKU's state before switching ---
    prev_sku = _store.get("sku")
    if prev_sku and prev_sku != sku:
        _store["per_sku_detected_params"][prev_sku] = _store.get("detected_params")
        _store["per_sku_modified_params"][prev_sku] = _store.get("modified_params")
        _store["per_sku_raw_dfs"][prev_sku] = _store.get("raw_df")
        _store["per_sku_modifiers"][prev_sku] = _store.get("modifier")

    # --- Check if we have saved state for the target SKU ---
    if sku in _store["per_sku_raw_dfs"]:
        # Restore previously saved state
        _store["raw_df"] = _store["per_sku_raw_dfs"][sku]
        _store["modifier"] = _store["per_sku_modifiers"][sku]
        _store["sku"] = sku
        _store["detected_params"] = _store["per_sku_detected_params"].get(sku)
        _store["modified_params"] = _store["per_sku_modified_params"].get(sku)

        df = _store["raw_df"]
    else:
        # First time selecting this SKU — process from file
        try:
            df = load_and_process_data(filepath, target_sku=sku)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing file: {e}")

        _store["raw_df"] = df
        _store["modifier"] = DemandModifier(df)
        _store["sku"] = sku
        _store["detected_params"] = detect_demand_parameters(df)
        _store["modified_params"] = None

    # Return the current (possibly restored) detected params
    current_params = _store.get("modified_params") or _store.get("detected_params")

    return UploadResponse(
        message=f"Successfully loaded demand data for SKU: {sku}",
        sku=sku,
        num_days=len(df),
        date_range={
            "start": str(df["Date"].iloc[0].date()),
            "end": str(df["Date"].iloc[-1].date()),
        },
        demand_stats=_demand_stats(df),
        detected_params=current_params,
    )


@app.post("/api/demand/generate", response_model=ModifyResponse, tags=["Demand Extraction"])
async def generate_synthetic_demand(
    season_type: SeasonType = Query(default=SeasonType.SUMMER, description="Season type"),
    num_days: int = Query(default=365, ge=30, le=730, description="Number of days to generate"),
):
    """
    Generate synthetic demand data instead of uploading a file.
    Useful for testing with summer/winter patterns.
    """
    raw = generate_demand(season_type.value, num_days=num_days)
    df = prepare_env_data(raw, season_type.value)

    # Standardise column names to match what DemandModifier expects
    df_for_modifier = raw.copy()
    _store["raw_df"] = df_for_modifier
    _store["modifier"] = DemandModifier(df_for_modifier)
    _store["sku"] = f"synthetic-{season_type.value}"

    return ModifyResponse(
        message=f"Generated {num_days}-day {season_type.value} demand data.",
        data=_demand_data_response(df_for_modifier),
    )


# ==========================================
# 2. DEMAND MODIFIER ENDPOINTS
# ==========================================
@app.get("/api/demand/data", response_model=DemandDataResponse, tags=["Demand Modifier"])
async def get_current_demand():
    """
    Get the current (possibly modified) demand data.
    Reflects both demand modifications (spikes/scaling) and parameter adjustments.
    """
    modifier = _get_modifier()
    df = modifier.get_data()
    return _demand_data_response(df)


@app.post("/api/demand/modify/spike", response_model=ModifyResponse, tags=["Demand Modifier"])
async def add_demand_spike(req: SpikeRequest):
    """
    Add a demand spike (large order) on a specific date.

    Example: Add 500 extra units on 2025-06-15.
    """
    modifier = _get_modifier()
    modifier.add_spike(req.date, req.amount)
    df = modifier.get_data()
    return ModifyResponse(
        message=f"Added spike of {req.amount} units on {req.date}.",
        data=_demand_data_response(df),
    )


@app.post("/api/demand/modify/scale", response_model=ModifyResponse, tags=["Demand Modifier"])
async def scale_demand_period(req: ScaleRequest):
    """
    Multiply demand by a factor over a date range.

    Example: Scale by 1.2 (20% increase) from June to August.
    """
    modifier = _get_modifier()
    modifier.scale_period(req.start_date, req.end_date, req.factor)
    df = modifier.get_data()
    return ModifyResponse(
        message=f"Scaled demand by {req.factor}x from {req.start_date} to {req.end_date}.",
        data=_demand_data_response(df),
    )


@app.post("/api/demand/modify/reset", response_model=ModifyResponse, tags=["Demand Modifier"])
async def reset_demand():
    """
    Reset demand data back to the original uploaded/generated data.
    """
    modifier = _get_modifier()
    modifier.reset()
    df = modifier.get_data()
    return ModifyResponse(
        message="Demand data reset to original.",
        data=_demand_data_response(df),
    )


# ==========================================
# 3. GRAPH / VISUALIZATION ENDPOINTS
# ==========================================
@app.get("/api/demand/preview/image", tags=["Visualization"])
async def preview_demand_graph_image():
    """
    Returns the demand preview graph as a PNG image (direct download/display).
    Reflects parameter adjustments if user has modified them.
    """
    modifier = _get_modifier()
    df = modifier.get_data()

    fig, ax = plt.subplots(figsize=(15, 6))
    ax.plot(df["Date"], df["Demand"], label="Demand", color="blue", linewidth=1)

    if "season_flag" in df.columns:
        ax.fill_between(
            df["Date"], 0,
            df["season_flag"] * df["Demand"].max(),
            color="orange", alpha=0.15, label="Season Active",
        )

    if "is_spike" in df.columns:
        spikes = df[df["is_spike"] == 1]
        ax.scatter(spikes["Date"], spikes["Demand"], color="red", zorder=5, label="Spikes", s=30)

    sku_label = _store.get("sku", "")
    ax.set_title(f"Demand Preview – {sku_label} (with Detected Seasons/Spikes)")
    ax.set_xlabel("Date")
    ax.set_ylabel("Demand (units)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    plt.close(fig)

    return StreamingResponse(buf, media_type="image/png", headers={
        "Content-Disposition": f"inline; filename=demand_preview.png"
    })


@app.get("/api/demand/preview/base64", response_model=GraphResponse, tags=["Visualization"])
async def preview_demand_graph_base64():
    """
    Returns the demand preview graph as a base64-encoded PNG string.
    Reflects parameter adjustments if user has modified them.
    """
    modifier = _get_modifier()
    df = modifier.get_data()

    fig, ax = plt.subplots(figsize=(15, 6))
    ax.plot(df["Date"], df["Demand"], label="Demand", color="blue", linewidth=1)

    if "season_flag" in df.columns:
        ax.fill_between(
            df["Date"], 0,
            df["season_flag"] * df["Demand"].max(),
            color="orange", alpha=0.15, label="Season Active",
        )
    if "is_spike" in df.columns:
        spikes = df[df["is_spike"] == 1]
        ax.scatter(spikes["Date"], spikes["Demand"], color="red", zorder=5, label="Spikes", s=30)

    sku_label = _store.get("sku", "")
    ax.set_title(f"Demand Preview – {sku_label}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Demand (units)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    return GraphResponse(image_base64=_fig_to_base64(fig))


@app.get("/api/demand/preview/variations/base64", response_model=GraphVariationsResponse, tags=["Visualization"])
async def preview_demand_variations_base64():
    """
    Returns 4 variations of the demand graph using the current parameters.
    Handy for Stage 3 to show how random Brownian motion creates different 
    possible realities from the same parameters.
    """
    original_df = _store.get("raw_df")
    sku_label = _store.get("sku", "")
    
    # If no data loaded, just return empty
    if original_df is None:
        return GraphVariationsResponse(images_base64=[])

    # Get the current parameters (prefer user-modified over auto-detected)
    current_params = _store.get("modified_params") or _store.get("detected_params")
    if not current_params:
        return GraphVariationsResponse(images_base64=[])

    # Seeds to generate different variations
    seeds = [123, 456, 789, 999]
    images = []

    for idx, seed in enumerate(seeds):
        # Regenerate demand data using the seed
        df_var = regenerate_demand_from_params(original_df, current_params, seed=seed)

        fig, ax = plt.subplots(figsize=(10, 4))
        ax.plot(df_var["Date"], df_var["Demand"], label=f"Variation {idx+1}", color="blue", linewidth=1.2)

        if "season_flag" in df_var.columns:
            ax.fill_between(
                df_var["Date"], 0,
                df_var["season_flag"] * df_var["Demand"].max(),
                color="orange", alpha=0.15, label="Season Active",
            )
        if "is_spike" in df_var.columns:
            spikes = df_var[df_var["is_spike"] == 1]
            ax.scatter(spikes["Date"], spikes["Demand"], color="red", zorder=5, label="Spikes", s=20)

        ax.set_title(f"{sku_label} - Brownian Variation {idx+1}", fontsize=10)
        ax.set_ylabel("Demand", fontsize=9)
        ax.legend(loc="upper right", fontsize=8)
        ax.grid(True, alpha=0.3)
        fig.tight_layout()

        images.append(_fig_to_base64(fig))
        plt.close(fig)

    return GraphVariationsResponse(images_base64=images)


@app.get("/api/demand/preview/comparison", response_model=GraphResponse, tags=["Visualization"])
async def preview_original_vs_modified():
    """
    Returns a comparison graph showing original vs modified demand as base64 PNG.
    Useful to visualise the impact of spikes/scaling before training.
    """
    modifier = _get_modifier()
    original = modifier.original_df
    modified = modifier.get_data()

    fig, ax = plt.subplots(figsize=(15, 6))
    ax.plot(original["Date"], original["Demand"], label="Original", color="gray", alpha=0.6, linewidth=1)
    ax.plot(modified["Date"], modified["Demand"], label="Modified", color="blue", linewidth=1.5)

    ax.fill_between(
        modified["Date"],
        original["Demand"], modified["Demand"],
        where=(modified["Demand"] > original["Demand"]),
        color="green", alpha=0.2, label="Increase",
    )
    ax.fill_between(
        modified["Date"],
        original["Demand"], modified["Demand"],
        where=(modified["Demand"] < original["Demand"]),
        color="red", alpha=0.2, label="Decrease",
    )

    ax.set_title(f"Original vs Modified Demand – {_store.get('sku', '')}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Demand (units)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    return GraphResponse(image_base64=_fig_to_base64(fig))


# ==========================================
# 4. TRAINING ENDPOINTS (RabbitMQ-backed)
# ==========================================


@app.post("/api/train", response_model=TrainStatusResponse, tags=["Training"])
async def start_training(req: TrainRequest, db: Session = Depends(get_db)):
    """
    Start training the DQN agent.

    Creates a training_run row in PostgreSQL (status='pending'),
    then publishes the job to RabbitMQ. The RL worker picks it up
    and updates status: pending → initiated → in_progress → success/failure.
    """
    # Prepare demand data path & params for the worker
    custom_df = None
    season = req.season_type.value
    uploaded_filepath = _store.get("uploaded_filepath")
    demand_params = _store.get("modified_params") or _store.get("detected_params")

    if season == "custom" and not uploaded_filepath:
        raise HTTPException(status_code=400, detail="No data uploaded. Upload a file first or use 'summer'/'winter' season type.")

    # Apply param adjustments locally if needed (to save the adjusted data for the worker)
    if season == "custom" and _store.get("modifier"):
        modifier = _get_modifier()
        custom_df = modifier.get_data().copy()
        custom_df = _apply_param_adjustments(custom_df)
        # Save adjusted data to a temp file the worker can read
        adjusted_path = os.path.join(storage_service.UPLOADS_DIR, f"adjusted_{_store.get('sku', 'unknown')}_{int(datetime.utcnow().timestamp())}.csv")
        custom_df.to_csv(adjusted_path, index=False)
        uploaded_filepath = adjusted_path

    sku = _store.get("sku", "unknown")

    # Create DB row with status='pending'
    run = TrainingRun(
        uploaded_file_id=_store.get("uploaded_file_id"),
        sku=sku,
        season_type=season,
        episodes=req.episodes,
        holding_cost=req.holding_cost,
        stockout_penalty=req.stockout_penalty,
        max_order=req.max_order,
        demand_params=demand_params,
        status="pending",
        created_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Publish job to RabbitMQ
    publish_training_job({
        "run_id": run.id,
        "sku": sku,
        "episodes": req.episodes,
        "season_type": season,
        "holding_cost": req.holding_cost,
        "stockout_penalty": req.stockout_penalty,
        "max_order": req.max_order,
        "uploaded_filepath": uploaded_filepath,
        "demand_params": demand_params,
    })

    _store["current_run_id"] = run.id
    _store["train_status"] = {
        "status": TrainingStatus.RUNNING,
        "current_episode": 0,
        "total_episodes": req.episodes,
        "best_reward": 0.0,
        "latest_reward": 0.0,
        "avg_reward_last_50": 0.0,
        "message": f"Job queued (run #{run.id}). Worker will pick it up shortly.",
    }

    return TrainStatusResponse(**_store["train_status"])


@app.get("/api/train/status", response_model=TrainStatusResponse, tags=["Training"])
async def get_training_status(db: Session = Depends(get_db)):
    """
    Poll the current training status including episode progress, rewards, etc.
    Reads from the in-memory cache (updated by ProgressListener) and
    falls back to the DB for persistent state.
    """
    run_id = _store.get("current_run_id")
    if run_id:
        run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if run and run.status in ("success", "failure", "cancelled"):
            # Reconcile in-memory status with DB truth
            if run.status == "success":
                _store["train_status"]["status"] = TrainingStatus.COMPLETED
                _store["train_status"]["message"] = f"Training complete (run #{run.id})."
            elif run.status == "failure":
                _store["train_status"]["status"] = TrainingStatus.FAILED
                _store["train_status"]["message"] = f"Training failed (run #{run.id})."
            elif run.status == "cancelled":
                _store["train_status"]["status"] = TrainingStatus.STOPPED
                _store["train_status"]["message"] = f"Training stopped (run #{run.id})."
    return TrainStatusResponse(**_store["train_status"])


@app.post("/api/train/stop", tags=["Training"])
async def stop_training(db: Session = Depends(get_db)):
    """
    Request early stopping of the currently running training.
    The training loop will stop after the current episode finishes.
    """
    if _store["train_status"]["status"] != TrainingStatus.RUNNING:
        raise HTTPException(status_code=409, detail="No training is currently running.")

    run_id = _store.get("current_run_id")
    if run_id:
        run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if run and run.status in ("pending", "initiated", "in_progress"):
            run.status = "cancelled"
            db.commit()

    _store["training_stop_requested"] = True
    _store["train_status"]["status"] = TrainingStatus.STOPPED
    _store["train_status"]["message"] = "Stop requested. Waiting for worker acknowledgement."
    return {"message": "Stop requested. Training will stop after the current episode."}


@app.get("/api/train/rewards", response_model=GraphResponse, tags=["Training"])
async def get_training_reward_curve():
    """
    Returns the training reward curve as a base64-encoded PNG.
    Available after training completes.
    """
    rewards = _store.get("train_rewards", [])
    if not rewards:
        raise HTTPException(status_code=400, detail="No training data available. Train the agent first.")

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(rewards, alpha=0.4, color="blue", label="Episode Reward")

    # Rolling average
    window = min(50, len(rewards))
    if len(rewards) >= window:
        rolling = pd.Series(rewards).rolling(window).mean()
        ax.plot(rolling, color="red", linewidth=2, label=f"Rolling Avg ({window} ep)")

    ax.set_title("Training Reward Curve")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Total Reward")
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    return GraphResponse(image_base64=_fig_to_base64(fig))


# ==========================================
# 5. EVALUATION ENDPOINTS
# ==========================================
@app.post("/api/evaluate", response_model=EvalResultResponse, tags=["Evaluation"])
async def evaluate_agent():
    """
    Evaluate the trained RL agent against the Oracle and Rule-Based baselines.

    Must be called after training is complete. Uses the same demand data and
    action-space configuration that was used for training.
    """
    if _store["trained_agent"] is None:
        raise HTTPException(status_code=400, detail="No trained agent. Train the agent first via POST /api/train.")

    agent = _store["trained_agent"]
    max_order = _store["train_max_order"]
    action_step = _store["train_action_step"]
    holding_cost = _store.get("train_holding_cost", 5)
    stockout_penalty = _store.get("train_stockout_penalty", 200)

    # Get eval data
    modifier = _store.get("modifier")
    if modifier is not None:
        custom_df = modifier.get_data().copy()
        custom_df.columns = [c.lower() for c in custom_df.columns]
        # Ensure required RL columns exist
        if "day_of_week" not in custom_df.columns:
            custom_df["day_of_week"] = pd.to_datetime(custom_df["date"]).dt.dayofweek
        if "promo_flag" not in custom_df.columns:
            custom_df["promo_flag"] = 0
        season = "custom"
    else:
        custom_df = None
        season = "summer"

    try:
        rl_df, oracle_df, rule_df = evaluate_and_plot(
            agent, season, max_order=max_order, action_step=action_step, custom_df=custom_df,
            holding_cost=holding_cost, stockout_penalty=stockout_penalty,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")

    rl_reward = float(rl_df["reward"].sum())
    oracle_reward = float(oracle_df["reward"].sum())
    rule_reward = float(rule_df["reward"].sum())
    rl_vs_oracle = (rl_reward / oracle_reward * 100) if oracle_reward != 0 else None

    _store["eval_results"] = {
        "rl_df": rl_df,
        "oracle_df": oracle_df,
        "rule_df": rule_df,
    }

    # Persist evaluation results to DB
    run_id = _store.get("current_run_id")
    if run_id:
        try:
            db = SessionLocal()
            eval_result = EvaluationResult(
                training_run_id=run_id,
                sku=_store.get("sku", "unknown"),
                rl_reward=round(rl_reward, 2),
                oracle_reward=round(oracle_reward, 2),
                rule_reward=round(rule_reward, 2),
                rl_vs_oracle_pct=round(rl_vs_oracle, 2) if rl_vs_oracle else None,
                config={"max_order": max_order, "action_step": action_step},
            )
            db.add(eval_result)
            db.commit()
            db.close()
        except Exception as e:
            print(f"[DB] Warning: Could not persist evaluation results: {e}")

    return EvalResultResponse(
        rl_reward=round(rl_reward, 2),
        oracle_reward=round(oracle_reward, 2),
        rule_reward=round(rule_reward, 2),
        rl_vs_oracle_pct=round(rl_vs_oracle, 2) if rl_vs_oracle else None,
        config={"max_order": max_order, "action_step": action_step},
        message=f"RL Agent achieves {rl_vs_oracle:.1f}% of Oracle performance." if rl_vs_oracle else "Evaluation complete.",
    )


@app.get("/api/evaluate/graph", response_model=GraphResponse, tags=["Evaluation"])
async def get_evaluation_graph():
    """
    Returns the evaluation comparison graph (RL vs Oracle vs Rule) as base64 PNG.
    Shows inventory levels and order quantities side by side.
    """
    if _store.get("eval_results") is None:
        raise HTTPException(status_code=400, detail="No evaluation results. Run POST /api/evaluate first.")

    rl_df = _store["eval_results"]["rl_df"]
    oracle_df = _store["eval_results"]["oracle_df"]
    rule_df = _store["eval_results"]["rule_df"]

    min_len = min(len(rl_df), len(oracle_df), len(rule_df))
    dates = rl_df["date"].iloc[:min_len]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

    # Inventory levels
    ax1.plot(dates, rl_df["inventory"].iloc[:min_len], "b-", label="RL Agent", linewidth=1.2)
    ax1.plot(dates, oracle_df["inventory"].iloc[:min_len], "g--", label="Oracle", linewidth=1)
    ax1.plot(dates, rule_df["inventory"].iloc[:min_len], "r:", label="Rule-Based", linewidth=1)
    ax1.fill_between(dates, rl_df["demand"].iloc[:min_len], alpha=0.2, color="gray", label="Demand")
    ax1.set_title("Inventory Level Comparison")
    ax1.set_ylabel("Units")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Order quantities
    ax2.step(dates, rl_df["action_order_qty"].iloc[:min_len], "b-", where="post", label="RL Order", linewidth=1.2)
    ax2.step(dates, oracle_df["action_order_qty"].iloc[:min_len], "g--", where="post", label="Oracle Order", linewidth=1)
    ax2.step(dates, rule_df["action_order_qty"].iloc[:min_len], "r:", where="post", label="Rule Order", linewidth=1)
    ax2.fill_between(dates, rl_df["demand"].iloc[:min_len], alpha=0.2, color="gray", label="Demand")
    ax2.set_title("Order Quantity Comparison")
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Units Ordered")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    return GraphResponse(image_base64=_fig_to_base64(fig))


# ==========================================
# HEALTH CHECK
# ==========================================
@app.get("/api/health", tags=["System"])
async def health_check():
    """Basic health-check endpoint."""
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(db.bind.dialect.do_ping if hasattr(db.bind.dialect, 'do_ping') else None)
        db_ok = True
        db.close()
    except Exception:
        try:
            from sqlalchemy import text
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db_ok = True
            db.close()
        except Exception:
            pass
    return {
        "status": "ok",
        "database": "connected" if db_ok else "unavailable",
        "data_loaded": _store["raw_df"] is not None,
        "agent_trained": _store["trained_agent"] is not None,
        "training_status": _store["train_status"]["status"],
    }

@app.get("/api/demand/parameters", response_model=DetectedParamsResponse, tags=["Demand Extraction"])
async def get_detected_parameters():
    """
    Returns the current demand parameters (detected or user-modified).
    If the user has modified params via PUT, those overrides are reflected.
    """
    params = _store.get("modified_params") or _store.get("detected_params")
    if params is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet. Upload a file first.")
    return params


@app.put("/api/demand/parameters", response_model=DetectedParamsResponse, tags=["Demand Extraction"])
async def update_detected_parameters(req: UpdateParamsRequest):
    """
    Modify the detected demand parameters from the UI.
    Accepts the same nested structure as the GET response.
    Only the fields you send will be updated; others stay as detected.
    After saving, the demand time series is regenerated so subsequent
    GET calls to /preview and /data reflect the changes immediately.
    """
    import copy

    base_params = _store.get("modified_params") or _store.get("detected_params")
    if base_params is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet. Upload a file first.")

    updated = copy.deepcopy(base_params)

    # --- Top-level scalar overrides ---
    if req.detected_season_type is not None:
        updated["detected_season_type"] = req.detected_season_type
    if req.ramp_days is not None:
        updated["ramp_days"] = req.ramp_days
    if req.num_days is not None:
        updated["num_days"] = req.num_days

    # --- Baseline overrides ---
    if req.baseline is not None:
        b = req.baseline
        if b.start is not None:
            updated["baseline"]["start"] = b.start
        if b.min is not None:
            updated["baseline"]["min"] = b.min
        if b.max is not None:
            updated["baseline"]["max"] = b.max
        if b.sigma is not None:
            updated["baseline"]["sigma"] = b.sigma

    # --- Seasonal overrides ---
    if req.seasonal is not None:
        s = req.seasonal
        if s.peak is not None:
            updated["seasonal"]["peak"] = s.peak
        # periods=None  → don't touch existing periods
        # periods=[...]  → replace with explicit list
        if s.periods is not None:
            updated["seasonal"]["periods"] = [p.model_dump() for p in s.periods]
            updated["seasonal"]["num_seasons"] = len(s.periods)
        # num_seasons may differ from len(periods) — reconciliation below will fix
        if s.num_seasons is not None:
            updated["seasonal"]["num_seasons"] = s.num_seasons

    # --- Festival overrides ---
    if req.festival is not None:
        f = req.festival
        if f.peak is not None:
            updated["festival"]["peak"] = f.peak
        if f.periods is not None:
            updated["festival"]["periods"] = [p.model_dump() for p in f.periods]
            updated["festival"]["num_festivals"] = len(f.periods)
        if f.num_festivals is not None:
            updated["festival"]["num_festivals"] = f.num_festivals

    # --- Reconcile num_seasons / num_festivals vs actual period lists ---
    original_df = _store.get("raw_df")
    if original_df is not None:
        _reconcile_periods(updated, original_df)

    updated["is_modified"] = True
    _store["modified_params"] = updated

    # --- Persist to per-SKU storage ---
    current_sku = _store.get("sku")
    if current_sku:
        _store["per_sku_modified_params"][current_sku] = updated

    # --- Regenerate the demand time series from the updated parameters ---
    if original_df is not None:
        regenerated_df = regenerate_demand_from_params(original_df, updated)
        _store["modifier"] = DemandModifier(regenerated_df)
        # Also persist updated modifier
        if current_sku:
            _store["per_sku_modifiers"][current_sku] = _store["modifier"]

    return updated


@app.post("/api/demand/parameters/reset", response_model=DetectedParamsResponse, tags=["Demand Extraction"])
async def reset_parameters():
    """
    Reset parameters back to the auto-detected values (discard user modifications).
    """
    params = _store.get("detected_params")
    if params is None:
        raise HTTPException(status_code=400, detail="No data uploaded yet. Upload a file first.")
    _store["modified_params"] = None

    # --- Clear per-SKU entry ---
    current_sku = _store.get("sku")
    if current_sku and current_sku in _store["per_sku_modified_params"]:
        del _store["per_sku_modified_params"][current_sku]

    # Restore the original demand data in the modifier
    original_df = _store.get("raw_df")
    if original_df is not None:
        _store["modifier"] = DemandModifier(original_df)
        if current_sku:
            _store["per_sku_modifiers"][current_sku] = _store["modifier"]

    return params


# ==========================================
# 7. WEBSOCKET ENDPOINT — LIVE TRAINING
# ==========================================
@app.websocket("/ws/train")
async def ws_training(ws: WebSocket):
    """
    WebSocket endpoint for live training updates.
    Clients connect here before/during training to receive per-episode JSON messages.
    Message types:
      - {"type": "episode", "episode": N, "reward": ..., ...}
      - {"type": "status", "status": "completed"|"failed", ...}
    """
    await ws_manager.connect(ws)
    try:
        # Keep the connection alive; the training thread pushes data.
        while True:
            # We don't expect client messages, but await to detect disconnects
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)


# ==========================================
# 8. MULTI-SKU TRAINING & EVALUATION (RabbitMQ-backed)
# ==========================================


@app.post("/api/train/multi", response_model=MultiSkuTrainStatusResponse, tags=["Multi-SKU Training"])
async def start_multi_sku_training(req: TrainRequest, db: Session = Depends(get_db)):
    """
    Start training DQN agents for ALL SKUs in the uploaded file.
    Each SKU gets its own TrainingRun row + RabbitMQ job.
    """
    if _store["multi_sku_overall"] == TrainingStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Multi-SKU training is already running.")

    # DB truth: prevent starting a new batch while any run is still active.
    active_runs = db.query(TrainingRun).filter(
        TrainingRun.status.in_(["pending", "initiated", "in_progress"])
    ).all()
    if active_runs:
        sku_statuses = {}
        for run in active_runs:
            sku_statuses[run.sku] = {
                "sku": run.sku,
                "status": TrainingStatus.RUNNING,
                "current_episode": 0,
                "total_episodes": run.episodes or 0,
                "best_reward": run.best_reward or 0.0,
                "latest_reward": 0.0,
                "avg_reward_last_50": run.final_avg_reward or 0.0,
                "message": f"Run #{run.id} already in progress",
            }
        _store["multi_sku_status"] = sku_statuses
        _store["multi_sku_overall"] = TrainingStatus.RUNNING
        _store["multi_sku_run_ids"] = {run.sku: run.id for run in active_runs}
        raise HTTPException(status_code=409, detail="A multi-SKU training batch is already active. Please wait or stop it first.")

    filepath = _store.get("uploaded_filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=400, detail="No file uploaded yet. Upload a file first.")

    # Load all SKUs
    sku_data_dict = load_all_skus_data(filepath)
    if not sku_data_dict:
        raise HTTPException(status_code=400, detail="No SKUs found in the uploaded file.")

    # Reset state
    _store["multi_sku_stop_requested"] = False
    _store["multi_sku_overall"] = TrainingStatus.RUNNING
    _store["multi_sku_agents"] = {}
    _store["multi_sku_rewards"] = {}
    _store["multi_sku_configs"] = {}
    _store["multi_sku_eval_results"] = {}
    _store["multi_sku_run_ids"] = {}

    sku_statuses = {}
    for sku_name, df in sku_data_dict.items():
        # Standardize columns
        df_copy = df.copy()
        df_copy.columns = [c.lower() for c in df_copy.columns]
        if "day_of_week" not in df_copy.columns:
            df_copy["day_of_week"] = pd.to_datetime(df_copy["date"]).dt.dayofweek
        if "promo_flag" not in df_copy.columns:
            df_copy["promo_flag"] = 0

        # Save per-SKU data to a temp file for the worker
        sku_filepath = os.path.join(
            storage_service.UPLOADS_DIR,
            f"multi_{sku_name}_{int(datetime.utcnow().timestamp())}.csv",
        )
        df_copy.to_csv(sku_filepath, index=False)

        # Get per-SKU demand params if available
        demand_params = _store.get("per_sku_modified_params", {}).get(sku_name) or \
                        _store.get("per_sku_detected_params", {}).get(sku_name)

        # Create DB row
        run = TrainingRun(
            uploaded_file_id=_store.get("uploaded_file_id"),
            sku=sku_name,
            season_type="custom",
            episodes=req.episodes,
            holding_cost=req.holding_cost,
            stockout_penalty=req.stockout_penalty,
            demand_params=demand_params,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        _store["multi_sku_run_ids"][sku_name] = run.id

        # Publish to RabbitMQ
        publish_training_job({
            "run_id": run.id,
            "sku": sku_name,
            "episodes": req.episodes,
            "season_type": "custom",
            "holding_cost": req.holding_cost,
            "stockout_penalty": req.stockout_penalty,
            "max_order": req.max_order,
            "uploaded_filepath": sku_filepath,
            "demand_params": demand_params,
        })

        sku_statuses[sku_name] = {
            "sku": sku_name,
            "status": TrainingStatus.RUNNING,
            "current_episode": 0,
            "total_episodes": req.episodes,
            "best_reward": 0,
            "latest_reward": 0,
            "avg_reward_last_50": 0,
            "message": f"Job queued (run #{run.id})...",
        }

    _store["multi_sku_status"] = sku_statuses

    return MultiSkuTrainStatusResponse(
        overall_status=TrainingStatus.RUNNING,
        skus={k: SkuTrainStatus(**v) for k, v in sku_statuses.items()},
        message=f"Training queued for {len(sku_data_dict)} SKUs: {list(sku_data_dict.keys())}",
    )


@app.get("/api/train/multi/status", response_model=MultiSkuTrainStatusResponse, tags=["Multi-SKU Training"])
async def get_multi_sku_training_status():
    """Poll the training status of all SKUs.
    Falls back to DB if in-memory state is empty (e.g. after page reload)."""
    # If _store has live status, use it
    if _store["multi_sku_status"]:
        return MultiSkuTrainStatusResponse(
            overall_status=_store["multi_sku_overall"],
            skus={k: SkuTrainStatus(**v) for k, v in _store["multi_sku_status"].items()},
            message="",
        )

    # DB fallback: check for any recent active runs
    db = SessionLocal()
    try:
        active_runs = db.query(TrainingRun).filter(
            TrainingRun.status.in_(["pending", "initiated", "in_progress"])
        ).all()
        if active_runs:
            # Reconstruct status from DB
            sku_statuses = {}
            for run in active_runs:
                sku_statuses[run.sku] = {
                    "sku": run.sku,
                    "status": TrainingStatus.RUNNING,
                    "current_episode": 0,
                    "total_episodes": run.episodes or 0,
                    "best_reward": run.best_reward or 0.0,
                    "latest_reward": 0.0,
                    "avg_reward_last_50": run.final_avg_reward or 0.0,
                    "message": f"Resuming {run.sku} (run #{run.id})...",
                }
            _store["multi_sku_status"] = sku_statuses
            _store["multi_sku_overall"] = TrainingStatus.RUNNING
            # Also restore run_ids mapping
            _store["multi_sku_run_ids"] = {run.sku: run.id for run in active_runs}
            return MultiSkuTrainStatusResponse(
                overall_status=TrainingStatus.RUNNING,
                skus={k: SkuTrainStatus(**v) for k, v in sku_statuses.items()},
                message="Reconnected to in-progress training.",
            )
    finally:
        db.close()

    return MultiSkuTrainStatusResponse(
        overall_status=_store["multi_sku_overall"],
        skus={},
        message="",
    )


@app.post("/api/train/multi/stop", tags=["Multi-SKU Training"])
async def stop_multi_sku_training(db: Session = Depends(get_db)):
    """Request early stopping of multi-SKU training.
    Marks all active training runs as 'cancelled' in the DB so workers stop."""
    active = db.query(TrainingRun).filter(
        TrainingRun.status.in_(["pending", "initiated", "in_progress"])
    ).all()
    if not active:
        raise HTTPException(status_code=409, detail="No multi-SKU training is currently running.")

    _store["multi_sku_stop_requested"] = True
    _store["multi_sku_overall"] = TrainingStatus.STOPPED

    # Mark all active runs as cancelled in the DB so workers see it.
    cancelled_count = 0
    for run in active:
        run.status = "cancelled"
        cancelled_count += 1
        # Keep UI state coherent immediately; worker updates will refine this later.
        if run.sku in _store.get("multi_sku_status", {}):
            _store["multi_sku_status"][run.sku]["status"] = TrainingStatus.STOPPED
            _store["multi_sku_status"][run.sku]["message"] = "Stop requested. Waiting for worker acknowledgement."
    db.commit()

    return {"message": f"Stop requested. {cancelled_count} run(s) marked as cancelled."}


@app.get("/api/train/multi/rewards", tags=["Multi-SKU Training"])
async def get_multi_sku_rewards():
    """Return per-SKU reward arrays for live charting.
    Falls back to DB if in-memory rewards are empty."""
    if _store["multi_sku_rewards"]:
        return {
            sku: rewards
            for sku, rewards in _store["multi_sku_rewards"].items()
        }

    # DB fallback: load rewards from the most recent batch of training runs
    db = SessionLocal()
    try:
        # Get the latest uploaded_file_id to scope the query
        file_id = _store.get("uploaded_file_id")
        if file_id:
            runs = db.query(TrainingRun).filter(
                TrainingRun.uploaded_file_id == file_id,
                TrainingRun.rewards.isnot(None),
                TrainingRun.status == "success",
            ).all()
        else:
            # Fallback: get the latest successful runs
            runs = db.query(TrainingRun).filter(
                TrainingRun.rewards.isnot(None),
                TrainingRun.status == "success",
            ).order_by(TrainingRun.created_at.desc()).limit(20).all()

        result = {}
        for run in runs:
            if run.rewards:
                result[run.sku] = run.rewards
                # Also populate _store for future calls
                _store["multi_sku_rewards"][run.sku] = run.rewards
        return result
    finally:
        db.close()


@app.post("/api/evaluate/multi", response_model=MultiSkuEvalResponse, tags=["Multi-SKU Evaluation"])
async def evaluate_multi_sku():
    """
    Return evaluation results for all trained SKUs.
    First checks in-memory store, then falls back to PostgreSQL.
    """
    eval_results = _store.get("multi_sku_eval_results", {})

    # DB fallback: if _store is empty, load from PostgreSQL
    if not eval_results:
        db = SessionLocal()
        try:
            file_id = _store.get("uploaded_file_id")
            if file_id:
                runs = db.query(TrainingRun).filter(
                    TrainingRun.uploaded_file_id == file_id,
                    TrainingRun.status == "success",
                ).all()
            else:
                # Get the latest batch of successful runs
                runs = db.query(TrainingRun).filter(
                    TrainingRun.status == "success",
                ).order_by(TrainingRun.created_at.desc()).limit(20).all()

            for run in runs:
                if run.evaluation:
                    eval_results[run.sku] = {
                        "rl_reward": run.evaluation.rl_reward,
                        "oracle_reward": run.evaluation.oracle_reward,
                        "rule_reward": run.evaluation.rule_reward,
                        "rl_vs_oracle_pct": run.evaluation.rl_vs_oracle_pct,
                    }
                    # Also populate configs from DB
                    _store["multi_sku_configs"][run.sku] = run.evaluation.config or {}
            # Cache for future calls
            _store["multi_sku_eval_results"] = eval_results
        finally:
            db.close()

    if not eval_results:
        raise HTTPException(status_code=400, detail="No multi-SKU training results. Run POST /api/train/multi first.")

    skus = {}
    for sku_name, r in eval_results.items():
        config = _store["multi_sku_configs"].get(sku_name, {})
        rl_vs_oracle = r.get("rl_vs_oracle_pct")
        skus[sku_name] = SkuEvalResult(
            sku=sku_name,
            rl_reward=round(r["rl_reward"], 2),
            oracle_reward=round(r["oracle_reward"], 2),
            rule_reward=round(r["rule_reward"], 2),
            rl_vs_oracle_pct=round(rl_vs_oracle, 2) if rl_vs_oracle else None,
            config=config,
            message=f"RL achieves {rl_vs_oracle:.1f}% of Oracle" if rl_vs_oracle else "Evaluated",
        )

    return MultiSkuEvalResponse(
        skus=skus,
        message=f"Evaluation results for {len(skus)} SKUs.",
    )


@app.get("/api/evaluate/multi/graph/{sku_name}", response_model=GraphResponse, tags=["Multi-SKU Evaluation"])
async def get_multi_sku_eval_graph(sku_name: str):
    """Return evaluation comparison graph for a specific SKU.
    If DataFrames are in _store, uses them directly.
    Otherwise, re-runs evaluation from the saved model on disk."""
    eval_results = _store.get("multi_sku_eval_results", {})

    rl_df = None
    oracle_df = None
    rule_df = None

    # Try in-memory first
    if sku_name in eval_results and "rl_df" in eval_results[sku_name]:
        r = eval_results[sku_name]
        rl_df = r["rl_df"]
        oracle_df = r["oracle_df"]
        rule_df = r["rule_df"]

    # DB fallback: re-run evaluation from saved model
    if rl_df is None:
        db = SessionLocal()
        try:
            run = db.query(TrainingRun).filter(
                TrainingRun.sku == sku_name,
                TrainingRun.status == "success",
                TrainingRun.model_path.isnot(None),
            ).order_by(TrainingRun.created_at.desc()).first()

            if not run:
                raise HTTPException(status_code=404, detail=f"No successful training run found for SKU '{sku_name}'.")
            if not run.model_path or not os.path.exists(run.model_path):
                raise HTTPException(status_code=404, detail=f"Model file not found for SKU '{sku_name}'.")

            # Load model + re-evaluate
            from dqn import DQNAgent
            max_order = run.max_order or 100
            action_step = run.action_step or 10
            n_actions = (max_order // action_step) + 1
            state_size = 15

            agent = DQNAgent(state_size=state_size, action_size=n_actions)
            weights = storage_service.load_model_weights(run.model_path)
            agent.policy_net.load_state_dict(weights)
            agent.target_net.load_state_dict(weights)

            # Get demand data for this SKU
            filepath = _store.get("uploaded_filepath")
            if filepath and os.path.exists(filepath):
                custom_df = load_and_process_data(filepath, target_sku=sku_name)
                custom_df.columns = [c.lower() for c in custom_df.columns]
                if "day_of_week" not in custom_df.columns:
                    custom_df["day_of_week"] = pd.to_datetime(custom_df["date"]).dt.dayofweek
                if "promo_flag" not in custom_df.columns:
                    custom_df["promo_flag"] = 0
            else:
                raise HTTPException(status_code=400, detail="Upload file not found. Please re-upload.")

            rl_df, oracle_df, rule_df = evaluate_and_plot(
                agent, "custom",
                max_order=max_order,
                action_step=action_step,
                custom_df=custom_df,
                holding_cost=run.holding_cost or 5,
                stockout_penalty=run.stockout_penalty or 200,
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Graph generation failed: {e}")
        finally:
            db.close()

    min_len = min(len(rl_df), len(oracle_df), len(rule_df))
    dates = rl_df["date"].iloc[:min_len]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))

    ax1.plot(dates, rl_df["inventory"].iloc[:min_len], "b-", label="RL Agent", linewidth=1.2)
    ax1.plot(dates, oracle_df["inventory"].iloc[:min_len], "g--", label="Oracle", linewidth=1)
    ax1.plot(dates, rule_df["inventory"].iloc[:min_len], "r:", label="Rule-Based", linewidth=1)
    ax1.fill_between(dates, rl_df["demand"].iloc[:min_len], alpha=0.2, color="gray", label="Demand")
    ax1.set_title(f"Inventory Level Comparison — {sku_name}")
    ax1.set_ylabel("Units")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    ax2.step(dates, rl_df["action_order_qty"].iloc[:min_len], "b-", where="post", label="RL Order", linewidth=1.2)
    ax2.step(dates, oracle_df["action_order_qty"].iloc[:min_len], "g--", where="post", label="Oracle Order", linewidth=1)
    ax2.step(dates, rule_df["action_order_qty"].iloc[:min_len], "r:", where="post", label="Rule Order", linewidth=1)
    ax2.fill_between(dates, rl_df["demand"].iloc[:min_len], alpha=0.2, color="gray", label="Demand")
    ax2.set_title(f"Order Quantity Comparison — {sku_name}")
    ax2.set_xlabel("Date")
    ax2.set_ylabel("Units Ordered")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    return GraphResponse(image_base64=_fig_to_base64(fig))


# ==========================================
# 9. TRAINING HISTORY ENDPOINTS
# ==========================================

@app.get("/api/runs", tags=["History"])
async def list_training_runs(db: Session = Depends(get_db)):
    """List all past training runs with their evaluation results."""
    runs = db.query(TrainingRun).order_by(TrainingRun.created_at.desc()).all()
    results = []
    for run in runs:
        entry = {
            "id": run.id,
            "sku": run.sku,
            "season_type": run.season_type,
            "episodes": run.episodes,
            "holding_cost": run.holding_cost,
            "stockout_penalty": run.stockout_penalty,
            "best_reward": run.best_reward,
            "final_avg_reward": run.final_avg_reward,
            "status": run.status,
            "model_path": run.model_path,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "created_at": run.created_at.isoformat() if run.created_at else None,
        }
        if run.evaluation:
            entry["evaluation"] = {
                "rl_reward": run.evaluation.rl_reward,
                "oracle_reward": run.evaluation.oracle_reward,
                "rule_reward": run.evaluation.rule_reward,
                "rl_vs_oracle_pct": run.evaluation.rl_vs_oracle_pct,
            }
        results.append(entry)
    return results


@app.get("/api/runs/{run_id}", tags=["History"])
async def get_training_run(run_id: int, db: Session = Depends(get_db)):
    """Get details of a specific training run, including rewards curve."""
    run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found.")
    return {
        "id": run.id,
        "sku": run.sku,
        "season_type": run.season_type,
        "episodes": run.episodes,
        "holding_cost": run.holding_cost,
        "stockout_penalty": run.stockout_penalty,
        "max_order": run.max_order,
        "action_step": run.action_step,
        "best_reward": run.best_reward,
        "final_avg_reward": run.final_avg_reward,
        "rewards": run.rewards,
        "demand_params": run.demand_params,
        "status": run.status,
        "model_path": run.model_path,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "evaluation": {
            "rl_reward": run.evaluation.rl_reward,
            "oracle_reward": run.evaluation.oracle_reward,
            "rule_reward": run.evaluation.rule_reward,
            "rl_vs_oracle_pct": run.evaluation.rl_vs_oracle_pct,
            "config": run.evaluation.config,
        } if run.evaluation else None,
    }


@app.post("/api/runs/{run_id}/load", tags=["History"])
async def load_training_run(run_id: int, db: Session = Depends(get_db)):
    """Load a previously trained model back into memory for evaluation."""
    run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Training run not found.")
    if not run.model_path or not os.path.exists(run.model_path):
        raise HTTPException(status_code=400, detail="Model file not found on disk.")

    from dqn import DQNAgent

    # Reconstruct agent with same action space
    max_order = run.max_order or 100
    action_step = run.action_step or 10
    
    weights = storage_service.load_model_weights(run.model_path)

    # Dynamically determine state_size and action_size from the saved model weights
    # First layer is nn.Linear(state_size, 256), so net.0.weight shape is [256, state_size]
    state_size = weights["net.0.weight"].shape[1] if "net.0.weight" in weights else 15
    # Last layer is nn.Linear(128, action_size), so net.6.weight shape is [action_size, 128]
    n_actions = weights["net.6.weight"].shape[0] if "net.6.weight" in weights else ((max_order // action_step) + 1)

    agent = DQNAgent(state_size=state_size, action_size=n_actions)
    agent.policy_net.load_state_dict(weights)
    agent.target_net.load_state_dict(weights)

    _store["trained_agent"] = agent
    _store["train_rewards"] = run.rewards or []
    _store["train_max_order"] = run.max_order
    _store["train_action_step"] = run.action_step
    _store["train_holding_cost"] = run.holding_cost
    _store["train_stockout_penalty"] = run.stockout_penalty
    _store["current_run_id"] = run.id
    _store["train_status"] = {
        "status": TrainingStatus.COMPLETED,
        "current_episode": run.episodes,
        "total_episodes": run.episodes,
        "best_reward": run.best_reward or 0.0,
        "latest_reward": float(run.rewards[-1]) if run.rewards else 0.0,
        "avg_reward_last_50": run.final_avg_reward or 0.0,
        "message": f"Loaded model from run #{run.id}",
    }

    return {"message": f"Loaded model from training run #{run.id} ({run.sku})", "run_id": run.id}


@app.get("/api/uploads", tags=["History"])
async def list_uploads(db: Session = Depends(get_db)):
    """List all uploaded files."""
    files = db.query(UploadedFile).order_by(UploadedFile.uploaded_at.desc()).all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "file_type": f.file_type,
            "skus": f.skus,
            "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
        }
        for f in files
    ]