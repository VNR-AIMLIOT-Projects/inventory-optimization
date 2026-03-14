"""
RL Training Worker
==================
Standalone process that consumes training jobs from RabbitMQ,
runs the DQN training loop, and writes results to PostgreSQL.

Architecture:
  FastAPI  --(publish job)--> RabbitMQ --> Worker --(updates)--> PostgreSQL
                                              |
                                              +--(progress)--> RabbitMQ exchange --> FastAPI --> WebSocket

Each SKU = one independent job message in the queue.
"""

import os
import sys
import json
import time
import signal
import traceback
from datetime import datetime

import pika
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

# Add src/ to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from database import SessionLocal, engine, Base
from models import TrainingRun, EvaluationResult
import storage_service
from trainer import train_agent, evaluate_and_plot
from extracts_demand import load_and_process_data

# ─── Configuration ─────────────────────────────────────────
RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
JOB_QUEUE = "rl_training_jobs"
PROGRESS_EXCHANGE = "rl_training_progress"

# Graceful shutdown
_shutdown = False

def _handle_signal(sig, frame):
    global _shutdown
    print(f"[Worker] Received signal {sig}, shutting down gracefully...")
    _shutdown = True

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def get_rabbitmq_connection(max_retries=10, retry_delay=3):
    """Connect to RabbitMQ with retries."""
    params = pika.URLParameters(RABBITMQ_URL)
    params.heartbeat = 600
    params.blocked_connection_timeout = 300

    for attempt in range(1, max_retries + 1):
        try:
            conn = pika.BlockingConnection(params)
            print(f"[Worker] Connected to RabbitMQ (attempt {attempt})")
            return conn
        except pika.exceptions.AMQPConnectionError as e:
            if attempt == max_retries:
                raise
            print(f"[Worker] RabbitMQ not ready (attempt {attempt}/{max_retries}): {e}")
            time.sleep(retry_delay)


def publish_progress(channel, run_id: int, data: dict):
    """Publish training progress to the exchange so FastAPI can relay to WebSocket."""
    message = json.dumps({"run_id": run_id, **data})
    try:
        channel.basic_publish(
            exchange=PROGRESS_EXCHANGE,
            routing_key="",
            body=message,
            properties=pika.BasicProperties(content_type="application/json"),
        )
    except Exception as e:
        print(f"[Worker] Progress publish failed: {e}")


def update_run_status(run_id: int, status: str, **kwargs):
    """Update a TrainingRun row in the database."""
    db: Session = SessionLocal()
    try:
        run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if run:
            # Never resurrect cancelled runs back to active states.
            if run.status == "cancelled" and status in ("initiated", "in_progress"):
                return
            run.status = status
            for key, value in kwargs.items():
                if hasattr(run, key):
                    setattr(run, key, value)
            db.commit()
    except Exception as e:
        print(f"[Worker] DB update failed for run {run_id}: {e}")
        db.rollback()
    finally:
        db.close()


def process_job(channel, method, properties, body):
    """Process a single training job from the queue."""
    global _shutdown

    job = json.loads(body)
    run_id = job["run_id"]
    sku = job["sku"]
    episodes = job["episodes"]
    season_type = job.get("season_type", "custom")
    holding_cost = job.get("holding_cost", 5.0)
    stockout_penalty = job.get("stockout_penalty", 200.0)
    max_order = job.get("max_order")
    uploaded_filepath = job.get("uploaded_filepath")
    demand_params = job.get("demand_params")

    print(f"\n[Worker] ═══ Job received: run_id={run_id} sku={sku} episodes={episodes} ═══")

    # Respect cancellation requested before this queued job starts.
    pre_db = SessionLocal()
    try:
        pre_row = pre_db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if not pre_row:
            print(f"[Worker] Run {run_id} not found. Acking message.")
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return
        if pre_row.status == "cancelled":
            print(f"[Worker] Run {run_id} already cancelled before start. Skipping.")
            publish_progress(channel, run_id, {
                "type": "status",
                "sku": sku,
                "status": "stopped",
                "message": f"Training stopped for {sku} before start",
            })
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return
    finally:
        pre_db.close()

    # ── Mark as initiated ──
    update_run_status(run_id, "initiated", started_at=datetime.utcnow())
    publish_progress(channel, run_id, {
        "type": "status",
        "sku": sku,
        "status": "initiated",
        "message": f"Job initiated for {sku}",
    })

    try:
        # ── Prepare demand data ──
        custom_df = None
        if season_type == "custom" and uploaded_filepath and os.path.exists(uploaded_filepath):
            # Check if the file is already a pre-extracted per-SKU CSV
            raw_df = pd.read_csv(uploaded_filepath)
            raw_df.columns = [c.strip().lower() for c in raw_df.columns]

            if 'sku' not in raw_df.columns and 'demand' in raw_df.columns:
                # Already pre-processed (from multi-SKU endpoint)
                custom_df = raw_df
            else:
                # Raw upload — needs full extraction
                custom_df = load_and_process_data(uploaded_filepath, target_sku=sku)
                custom_df.columns = [c.lower() for c in custom_df.columns]

            if "day_of_week" not in custom_df.columns:
                custom_df["day_of_week"] = pd.to_datetime(custom_df["date"]).dt.dayofweek
            if "promo_flag" not in custom_df.columns:
                custom_df["promo_flag"] = 0

        # ── Mark as in_progress ──
        update_run_status(run_id, "in_progress")
        publish_progress(channel, run_id, {
            "type": "status",
            "sku": sku,
            "status": "in_progress",
            "message": f"Training {sku}...",
        })

        # ── Per-episode callback (throttled — publish every 5th episode) ──
        def on_episode(info: dict):
            if _shutdown:
                return False
            ep = info["episode"]
            total = info["total_episodes"]
            # Check DB for cancellation every episode to stop quickly.
            check_db = SessionLocal()
            try:
                run_row = check_db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
                if run_row and run_row.status == "cancelled":
                    print(f"[Worker] Run {run_id} ({sku}) cancelled via DB")
                    return False
            finally:
                check_db.close()
            # Publish every 5 episodes, plus the first and last
            if ep % 5 != 0 and ep != 1 and ep != total:
                return True
            publish_progress(channel, run_id, {
                "type": "episode",
                "sku": sku,
                "episode": info["episode"],
                "total_episodes": info["total_episodes"],
                "reward": float(info["reward"]),
                "best_reward": float(info["best_reward"]),
                "avg_reward_last_50": float(info["avg_reward_last_50"]),
                "epsilon": float(info["epsilon"]),
                "best_eval_reward": float(info.get("best_eval_reward", 0)),
            })
            return True

        # ── Train ──
        agent, rewards, used_max_order, used_action_step, used_h, used_s = train_agent(
            season_type=season_type,
            episodes=episodes,
            max_order=max_order,
            custom_df=custom_df,
            holding_cost=holding_cost,
            stockout_penalty=stockout_penalty,
            on_episode=on_episode,
        )

        # ── Check if cancelled mid-training ──
        check_db = SessionLocal()
        try:
            run_row = check_db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
            was_cancelled = run_row and run_row.status == "cancelled"
        finally:
            check_db.close()

        if was_cancelled:
            print(f"[Worker] ✗ Job cancelled: run_id={run_id} sku={sku}")
            publish_progress(channel, run_id, {
                "type": "status",
                "sku": sku,
                "status": "stopped",
                "message": f"Training stopped for {sku} at episode {len(rewards)}",
            })
            channel.basic_ack(delivery_tag=method.delivery_tag)
            return

        # ── Save model to disk ──
        model_path = storage_service.save_model(agent, sku, run_id)

        # ── Evaluate ──
        rl_df, oracle_df, rule_df = evaluate_and_plot(
            agent, season_type,
            max_order=used_max_order,
            action_step=used_action_step,
            custom_df=custom_df,
            holding_cost=used_h,
            stockout_penalty=used_s,
        )

        rl_reward = float(rl_df["reward"].sum())
        oracle_reward = float(oracle_df["reward"].sum())
        rule_reward = float(rule_df["reward"].sum())
        rl_vs_oracle = (rl_reward / oracle_reward * 100) if oracle_reward != 0 else None

        # ── Persist results ──
        db: Session = SessionLocal()
        try:
            run = db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
            if run:
                run.status = "success"
                run.best_reward = float(max(rewards)) if rewards else 0.0
                run.final_avg_reward = float(np.mean(rewards[-50:])) if rewards else 0.0
                run.rewards = [float(r) for r in rewards]
                run.model_path = model_path
                run.max_order = used_max_order
                run.action_step = used_action_step
                run.demand_params = demand_params
                run.completed_at = datetime.utcnow()
                db.commit()

                # Save evaluation
                eval_result = EvaluationResult(
                    training_run_id=run_id,
                    sku=sku,
                    rl_reward=rl_reward,
                    oracle_reward=oracle_reward,
                    rule_reward=rule_reward,
                    rl_vs_oracle_pct=rl_vs_oracle,
                    config={
                        "max_order": used_max_order,
                        "action_step": used_action_step,
                        "holding_cost": used_h,
                        "stockout_penalty": used_s,
                        "episodes": episodes,
                    },
                )
                db.add(eval_result)
                db.commit()
        except Exception as e:
            print(f"[Worker] DB persist failed: {e}")
            db.rollback()
        finally:
            db.close()

        publish_progress(channel, run_id, {
            "type": "status",
            "sku": sku,
            "status": "success",
            "best_reward": float(max(rewards)) if rewards else 0.0,
            "avg_reward_last_50": float(np.mean(rewards[-50:])) if rewards else 0.0,
            "rl_reward": rl_reward,
            "oracle_reward": oracle_reward,
            "rule_reward": rule_reward,
            "rl_vs_oracle_pct": rl_vs_oracle,
            "message": f"Training complete for {sku}. Best: {max(rewards):,.0f}",
        })

        print(f"[Worker] ✓ Job done: run_id={run_id} sku={sku} status=success")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Worker] ✗ Job failed: run_id={run_id} sku={sku}\n{tb}")
        update_run_status(run_id, "failure", completed_at=datetime.utcnow())
        publish_progress(channel, run_id, {
            "type": "status",
            "sku": sku,
            "status": "failure",
            "message": f"Training failed for {sku}: {e}",
        })

    # Acknowledge the message after processing (success or failure)
    channel.basic_ack(delivery_tag=method.delivery_tag)


def main():
    """Main worker loop — consume jobs from RabbitMQ."""
    print("[Worker] Starting RL Training Worker...")
    print(f"[Worker] RabbitMQ: {RABBITMQ_URL}")
    print(f"[Worker] Storage: {storage_service.STORAGE_DIR}")

    # Ensure DB tables exist (worker may start before API runs migrations)
    Base.metadata.create_all(bind=engine)

    connection = get_rabbitmq_connection()
    channel = connection.channel()

    # Declare the job queue (durable so jobs survive restarts)
    channel.queue_declare(queue=JOB_QUEUE, durable=True)

    # Declare the progress exchange (fanout so all listeners get updates)
    channel.exchange_declare(exchange=PROGRESS_EXCHANGE, exchange_type="fanout")

    # Fair dispatch — don't give more than 1 job at a time to this worker
    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(queue=JOB_QUEUE, on_message_callback=process_job)

    print(f"[Worker] Listening on queue '{JOB_QUEUE}'... (Ctrl+C to stop)")

    try:
        while not _shutdown:
            connection.process_data_events(time_limit=1)
    except KeyboardInterrupt:
        pass
    finally:
        print("[Worker] Shutting down...")
        try:
            channel.close()
            connection.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
