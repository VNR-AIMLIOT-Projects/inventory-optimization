"""
SQLAlchemy ORM models for persisting training runs, evaluations, and uploaded files.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    filepath = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # csv / xlsx
    skus = Column(JSON, default=[])  # list of SKU names found
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    training_runs = relationship("TrainingRun", back_populates="uploaded_file")


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id = Column(Integer, primary_key=True, index=True)
    uploaded_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=True)
    sku = Column(String, nullable=False)
    season_type = Column(String, nullable=False)  # summer / winter / custom
    episodes = Column(Integer, nullable=False)
    holding_cost = Column(Float, default=5.0)
    stockout_penalty = Column(Float, default=200.0)
    gamma = Column(Float, default=0.98)
    learning_rate = Column(Float, default=1e-4)
    sweep_id = Column(String, nullable=True)
    max_order = Column(Integer, nullable=True)
    action_step = Column(Integer, nullable=True)
    best_reward = Column(Float, nullable=True)
    final_avg_reward = Column(Float, nullable=True)
    rewards = Column(JSON, default=[])  # list of per-episode rewards
    model_path = Column(String, nullable=True)  # path to saved .pt file
    log_path = Column(String, nullable=True)     # path to training log file
    demand_params = Column(JSON, nullable=True)  # detected/modified params snapshot
    status = Column(String, default="pending")   # pending → initiated → in_progress → success / failure
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    uploaded_file = relationship("UploadedFile", back_populates="training_runs")
    evaluation = relationship("EvaluationResult", back_populates="training_run", uselist=False)


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    training_run_id = Column(Integer, ForeignKey("training_runs.id"), nullable=False)
    sku = Column(String, nullable=False)
    rl_reward = Column(Float, nullable=False)
    oracle_reward = Column(Float, nullable=False)
    rule_reward = Column(Float, nullable=False)
    rl_vs_oracle_pct = Column(Float, nullable=True)
    config = Column(JSON, default={})
    eval_graph_path = Column(String, nullable=True)  # path to saved graph
    created_at = Column(DateTime, default=datetime.utcnow)

    training_run = relationship("TrainingRun", back_populates="evaluation")


class DeploymentSession(Base):
    __tablename__ = "deployment_sessions"

    id = Column(String, primary_key=True)  # UUID session ID
    run_id = Column(Integer, ForeignKey("training_runs.id"), nullable=False)
    sku = Column(String, nullable=False)
    start_day = Column(Integer, default=0)
    total_days = Column(Integer, nullable=False)
    overrides = Column(JSON, default={})  # {day_index: override_qty}
    initial_inventory = Column(Integer, nullable=False)
    max_order = Column(Integer, nullable=False)
    action_step = Column(Integer, nullable=False)
    holding_cost = Column(Float, default=5.0)
    stockout_penalty = Column(Float, default=200.0)
    final_rl_reward = Column(Float, nullable=True)
    final_human_reward = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
