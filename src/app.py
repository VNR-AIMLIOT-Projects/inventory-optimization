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
import threading
import uuid
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend for server
import matplotlib.pyplot as plt

from fastapi import FastAPI, UploadFile, File, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# --- Add RL experiment modules to path ---
RL_DIR = os.path.join(os.path.dirname(__file__), "..", "experiments", "backend-implementation")
sys.path.insert(0, os.path.abspath(RL_DIR))

from schemas import (
    UploadResponse, SKUListResponse,
    SpikeRequest, ScaleRequest, DemandDataResponse, ModifyResponse,
    TrainRequest, TrainStatusResponse, TrainingStatus, EvalResultResponse,
    GraphResponse, SeasonType,
)
from extracts_demand import load_and_process_data, plot_demand_preview
from demand_modifier import DemandModifier
from demand import generate_demand, prepare_env_data
from trainer import train_agent, evaluate_and_plot

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
}

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


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


# ==========================================
# 1. DEMAND EXTRACTION ENDPOINTS
# ==========================================
@app.post("/api/demand/upload", response_model=UploadResponse, tags=["Demand Extraction"])
async def upload_demand_file(
    file: UploadFile = File(..., description="CSV or Excel file with demand data"),
    sku: str = Query(default=None, description="Target SKU to extract (auto-selects if omitted)"),
):
    """
    Upload a CSV/Excel demand file and extract time-series demand for a specific SKU.

    The file should follow the template format with columns: Date, SKU, Demand.
    Alternatively, wide-format (Date, SKU1, SKU2...) is also supported.
    """
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

    return UploadResponse(
        message=f"Successfully loaded demand data for SKU: {resolved_sku}",
        sku=resolved_sku,
        num_days=len(df),
        date_range={
            "start": str(df["Date"].iloc[0].date()),
            "end": str(df["Date"].iloc[-1].date()),
        },
        demand_stats=_demand_stats(df),
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
    Shows detected seasons and spikes overlaid on the demand curve.
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
    Ideal for embedding directly in a frontend <img> tag.
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
# 4. TRAINING ENDPOINTS
# ==========================================
def _run_training_thread(season_type: str, episodes: int, max_order, custom_df):
    """Background thread that runs agent training and updates _store."""
    try:
        _store["train_status"]["status"] = TrainingStatus.RUNNING
        _store["train_status"]["total_episodes"] = episodes
        _store["train_status"]["current_episode"] = 0
        _store["train_status"]["message"] = "Training in progress..."

        agent, rewards, used_max_order, used_action_step = train_agent(
            season_type,
            episodes=episodes,
            max_order=max_order,
            custom_df=custom_df,
        )

        _store["trained_agent"] = agent
        _store["train_rewards"] = rewards
        _store["train_max_order"] = used_max_order
        _store["train_action_step"] = used_action_step
        _store["train_status"].update({
            "status": TrainingStatus.COMPLETED,
            "current_episode": episodes,
            "best_reward": float(max(rewards)) if rewards else 0.0,
            "latest_reward": float(rewards[-1]) if rewards else 0.0,
            "avg_reward_last_50": float(np.mean(rewards[-50:])) if rewards else 0.0,
            "message": f"Training complete. Best reward: {max(rewards):,.0f}",
        })
    except Exception as e:
        _store["train_status"]["status"] = TrainingStatus.FAILED
        _store["train_status"]["message"] = f"Training failed: {e}"


@app.post("/api/train", response_model=TrainStatusResponse, tags=["Training"])
async def start_training(req: TrainRequest):
    """
    Start training the DQN agent on the current demand data.

    Training runs in a background thread. Poll GET /api/train/status for progress.
    If season_type is 'custom', the currently loaded (and possibly modified) demand data is used.
    For 'summer' or 'winter', synthetic data is generated automatically.
    """
    if _store["train_status"]["status"] == TrainingStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Training is already running. Wait for it to finish.")

    # Prepare custom data
    custom_df = None
    season = req.season_type.value

    if season == "custom":
        modifier = _get_modifier()
        custom_df = modifier.get_data().copy()
        # Standardise columns for the trainer
        custom_df.columns = [c.lower() for c in custom_df.columns]

    # Reset status
    _store["train_status"] = {
        "status": TrainingStatus.RUNNING,
        "current_episode": 0,
        "total_episodes": req.episodes,
        "best_reward": 0.0,
        "latest_reward": 0.0,
        "avg_reward_last_50": 0.0,
        "message": "Training started...",
    }

    thread = threading.Thread(
        target=_run_training_thread,
        args=(season, req.episodes, req.max_order, custom_df),
        daemon=True,
    )
    thread.start()

    return TrainStatusResponse(**_store["train_status"])


@app.get("/api/train/status", response_model=TrainStatusResponse, tags=["Training"])
async def get_training_status():
    """
    Poll the current training status including episode progress, rewards, etc.
    """
    return TrainStatusResponse(**_store["train_status"])


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

    # Get eval data
    modifier = _store.get("modifier")
    if modifier is not None:
        custom_df = modifier.get_data().copy()
        custom_df.columns = [c.lower() for c in custom_df.columns]
        season = "custom"
    else:
        custom_df = None
        season = "summer"

    try:
        rl_df, oracle_df, rule_df = evaluate_and_plot(
            agent, season, max_order=max_order, action_step=action_step, custom_df=custom_df
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
    return {
        "status": "ok",
        "data_loaded": _store["raw_df"] is not None,
        "agent_trained": _store["trained_agent"] is not None,
        "training_status": _store["train_status"]["status"],
    }
