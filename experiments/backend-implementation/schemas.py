"""
Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum


# ==========================================
# ENUMS
# ==========================================
class SeasonType(str, Enum):
    SUMMER = "summer"
    WINTER = "winter"
    CUSTOM = "custom"


class TrainingStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ==========================================
# DEMAND EXTRACTION
# ==========================================
class UploadResponse(BaseModel):
    message: str
    sku: str
    num_days: int
    date_range: dict  # {"start": ..., "end": ...}
    demand_stats: dict  # {"mean": ..., "max": ..., "min": ..., "std": ...}


class SKUListResponse(BaseModel):
    skus: List[str]
    total: int


# ==========================================
# DEMAND MODIFIER
# ==========================================
class SpikeRequest(BaseModel):
    date: str = Field(..., description="Date in YYYY-MM-DD format", examples=["2025-06-15"])
    amount: int = Field(..., description="Units to add on that date", ge=1)


class ScaleRequest(BaseModel):
    start_date: str = Field(..., description="Start date in YYYY-MM-DD format", examples=["2025-06-01"])
    end_date: str = Field(..., description="End date in YYYY-MM-DD format", examples=["2025-08-31"])
    factor: float = Field(..., description="Multiplier (e.g. 1.2 for +20%)", gt=0)


class DemandDataResponse(BaseModel):
    dates: List[str]
    demand: List[int]
    num_days: int
    stats: dict


class ModifyResponse(BaseModel):
    message: str
    data: DemandDataResponse


# ==========================================
# TRAINING
# ==========================================
class TrainRequest(BaseModel):
    episodes: int = Field(default=500, ge=10, le=5000, description="Number of training episodes")
    max_order: Optional[int] = Field(default=None, description="Max order qty (auto-computed if None)")
    season_type: SeasonType = Field(default=SeasonType.CUSTOM, description="Season type for synthetic data")


class TrainStatusResponse(BaseModel):
    status: TrainingStatus
    current_episode: int = 0
    total_episodes: int = 0
    best_reward: float = 0.0
    latest_reward: float = 0.0
    avg_reward_last_50: float = 0.0
    message: str = ""


class EvalResultResponse(BaseModel):
    rl_reward: float
    oracle_reward: float
    rule_reward: float
    rl_vs_oracle_pct: Optional[float] = None
    config: dict  # max_order, action_step
    message: str


# ==========================================
# GRAPH
# ==========================================
class GraphResponse(BaseModel):
    image_base64: str
    format: str = "png"
