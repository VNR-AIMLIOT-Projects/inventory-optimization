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
    date_range: dict
    demand_stats: dict
    detected_params: dict | None = None


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
# DETECTED PARAMETERS
# ==========================================
class BaselineParams(BaseModel):
    start: int = Field(..., description="Baseline demand center")
    min: int = Field(..., description="Minimum baseline demand")
    max: int = Field(..., description="Maximum baseline demand")
    sigma: float = Field(..., description="Baseline std deviation")


class PeriodRange(BaseModel):
    start: str = Field(..., description="Period start date (YYYY-MM-DD)")
    end: str = Field(..., description="Period end date (YYYY-MM-DD)")
    start_day: int = Field(..., description="Start day index")
    end_day: int = Field(..., description="End day index")


class SeasonalParams(BaseModel):
    peak: int = Field(..., description="Average demand during seasonal periods")
    periods: List[PeriodRange] = Field(default_factory=list)
    num_seasons: int = Field(default=0)


class FestivalParams(BaseModel):
    peak: int = Field(..., description="Average demand during festival spikes")
    periods: List[PeriodRange] = Field(default_factory=list)
    num_festivals: int = Field(default=0)


class DetectedParamsResponse(BaseModel):
    detected_season_type: str
    baseline: BaselineParams
    seasonal: SeasonalParams
    festival: FestivalParams
    ramp_days: int = Field(default=14, description="Days for demand ramp-up before season")
    num_days: int
    is_modified: bool = Field(default=False, description="Whether user has modified these params")


class UpdateParamsRequest(BaseModel):
    """Request body for modifying detected parameters from the UI.
    Accepts the same nested structure as DetectedParamsResponse.
    All fields are optional — only send what you want to change."""
    detected_season_type: Optional[str] = Field(default=None, description="Override season type: summer/winter/unknown")
    baseline: Optional[BaselineParams] = Field(default=None, description="Baseline parameters")
    seasonal: Optional[SeasonalParams] = Field(default=None, description="Seasonal parameters")
    festival: Optional[FestivalParams] = Field(default=None, description="Festival parameters")
    ramp_days: Optional[int] = Field(default=None, ge=1, le=60, description="Ramp-up days before season")
    num_days: Optional[int] = Field(default=None, description="Total number of days")
    is_modified: Optional[bool] = Field(default=None, description="Ignored on input, always set to true on save")


# ==========================================
# GRAPH
# ==========================================
class GraphResponse(BaseModel):
    image_base64: str
    format: str = "png"
