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
Parallelism: jobs are dispatched to a ThreadPoolExecutor so multiple SKUs
train simultaneously instead of one-at-a-time.
"""

import os
import sys
import json
import time
import signal
import traceback
import threading
from concurrent.futures import ThreadPoolExecutor
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
ERP_QUEUE = "erp_ingestion"
PROGRESS_EXCHANGE = "rl_training_progress"
UI_UPDATE_EXCHANGE = "ui_updates"

# Maximum number of SKUs to train in parallel — tune to your CPU/RAM budget.
# Defaults to number of logical CPUs (capped at 8 to avoid OOM on small VMs).
_default_workers = min(os.cpu_count() or 4, 8)
MAX_PARALLEL_SKUS = int(os.environ.get("MAX_PARALLEL_SKUS", _default_workers))

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


def _make_progress_channel():
    """Open a fresh pika connection+channel for use inside a worker thread.

    pika's BlockingConnection is NOT thread-safe, so each thread must own
    its own connection rather than sharing the main consumer channel.
    Returns (connection, channel) or (None, None) on failure.
    """
    try:
        params = pika.URLParameters(RABBITMQ_URL)
        params.heartbeat = 600
        params.blocked_connection_timeout = 300
        conn = pika.BlockingConnection(params)
        ch = conn.channel()
        ch.exchange_declare(exchange=PROGRESS_EXCHANGE, exchange_type="fanout")
        return conn, ch
    except Exception as e:
        print(f"[Worker] Could not open progress channel: {e}")
        return None, None


def publish_progress(channel, run_id: int, data: dict):
    """Publish training progress to the exchange so FastAPI can relay to WebSocket.

    `channel` may be a main-thread channel (for ERP webhooks) or a
    per-thread channel opened by _make_progress_channel().
    """
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


def _run_training_job(job: dict, delivery_tag, ack_callback):
    """Execute one training job inside a worker thread.

    Opens its own pika connection for progress publishing so it does not
    share state with the main consumer channel (pika is not thread-safe).
    Calls ack_callback(delivery_tag) on the main thread via a thread-safe
    mechanism once done.
    """
    global _shutdown

    run_id = job["run_id"]
    sku = job["sku"]
    episodes = job["episodes"]
    season_type = job.get("season_type", "custom")
    holding_cost = job.get("holding_cost", 5.0)
    stockout_penalty = job.get("stockout_penalty", 200.0)
    max_order = job.get("max_order")
    uploaded_filepath = job.get("uploaded_filepath")
    demand_params = job.get("demand_params")

    print(f"\n[Worker] ═══ [Thread] Job started: run_id={run_id} sku={sku} episodes={episodes} ═══")

    # Open a dedicated pika channel for this thread
    prog_conn, prog_ch = _make_progress_channel()

    def _publish(data: dict):
        if prog_ch is not None:
            try:
                publish_progress(prog_ch, run_id, data)
            except Exception:
                pass  # Non-fatal — progress update lost, training continues

    # Respect cancellation requested before this queued job starts.
    pre_db = SessionLocal()
    try:
        pre_row = pre_db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
        if not pre_row:
            print(f"[Worker] Run {run_id} not found. Acking message.")
            ack_callback(delivery_tag)
            return
        if pre_row.status == "cancelled":
            print(f"[Worker] Run {run_id} already cancelled before start. Skipping.")
            _publish({
                "type": "status",
                "sku": sku,
                "status": "stopped",
                "message": f"Training stopped for {sku} before start",
            })
            ack_callback(delivery_tag)
            return
    finally:
        pre_db.close()

    # ── Mark as initiated ──
    update_run_status(run_id, "initiated", started_at=datetime.utcnow())
    _publish({
        "type": "status",
        "sku": sku,
        "status": "initiated",
        "message": f"Job initiated for {sku}",
    })

    try:
        # ── Prepare demand data ──
        custom_df = None
        if season_type == "custom" and uploaded_filepath and os.path.exists(uploaded_filepath):
            raw_df = pd.read_csv(uploaded_filepath)
            raw_df.columns = [c.strip().lower() for c in raw_df.columns]

            if 'sku' not in raw_df.columns and 'demand' in raw_df.columns:
                custom_df = raw_df
            else:
                custom_df = load_and_process_data(uploaded_filepath, target_sku=sku)
                custom_df.columns = [c.lower() for c in custom_df.columns]

            if "day_of_week" not in custom_df.columns:
                custom_df["day_of_week"] = pd.to_datetime(custom_df["date"]).dt.dayofweek
            if "promo_flag" not in custom_df.columns:
                custom_df["promo_flag"] = 0

        # ── Mark as in_progress ──
        update_run_status(run_id, "in_progress")
        _publish({
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
            check_db = SessionLocal()
            try:
                run_row = check_db.query(TrainingRun).filter(TrainingRun.id == run_id).first()
                if run_row and run_row.status == "cancelled":
                    print(f"[Worker] Run {run_id} ({sku}) cancelled via DB")
                    return False
            finally:
                check_db.close()
            if ep % 5 != 0 and ep != 1 and ep != total:
                return True
            _publish({
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
            _publish({
                "type": "status",
                "sku": sku,
                "status": "stopped",
                "message": f"Training stopped for {sku} at episode {len(rewards)}",
            })
            ack_callback(delivery_tag)
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

        _publish({
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
        try:
            import requests
            # Trigger Node.js backend to send completion email via the webhook endpoint to bypass CSRF
            payload = {
                "sku": sku,
                "episodes": episodes,
                "best_reward": float(max(rewards)) if rewards else 0.0,
                "avg_reward_last_50": float(np.mean(rewards[-50:])) if rewards else 0.0,
                "rl_reward": rl_reward,
                "oracle_reward": oracle_reward,
                "rule_reward": rule_reward,
                "rl_vs_oracle_pct": rl_vs_oracle,
                "run_id": run_id
            }
            requests.post("http://frontend:3000/api/webhooks/notify/training-complete", json=payload, timeout=5)
            print("[Worker] ✓ Triggered email notification")
        except Exception as e:
            print(f"[Worker] Warning: Failed to trigger email notification: {e}")

    except Exception as e:
        tb = traceback.format_exc()
        print(f"[Worker] ✗ Job failed: run_id={run_id} sku={sku}\n{tb}")
        update_run_status(run_id, "failure", completed_at=datetime.utcnow())
        _publish({
            "type": "status",
            "sku": sku,
            "status": "failure",
            "message": f"Training failed for {sku}: {e}",
        })

    finally:
        # Ack the RabbitMQ message (via thread-safe callback) and close progress channel
        ack_callback(delivery_tag)
        if prog_conn is not None:
            try:
                prog_conn.close()
            except Exception:
                pass


def process_job(channel, method, properties, body):
    """RabbitMQ callback — immediately acks and dispatches training to the thread pool.

    This keeps the main event loop unblocked so the next message can be
    fetched from the queue right away, enabling true parallel multi-SKU training.
    """
    global _job_executor, _ack_lock

    job = json.loads(body)
    delivery_tag = method.delivery_tag

    # Thread-safe ack: pika channel operations must happen on the thread that
    # owns the connection. We queue the ack back onto the connection's I/O loop
    # using add_callback_threadsafe.
    connection = channel.connection

    def ack_on_main_thread(tag):
        try:
            connection.add_callback_threadsafe(
                lambda: channel.basic_ack(delivery_tag=tag)
            )
        except Exception as e:
            print(f"[Worker] Ack failed for tag {tag}: {e}")

    print(f"[Worker] Dispatching job to thread pool: run_id={job.get('run_id')} sku={job.get('sku')}")
    _job_executor.submit(_run_training_job, job, delivery_tag, ack_on_main_thread)


def process_erp_webhook(channel, method, properties, body):
    """Process a single live ERP event webhook from Node.js."""
    try:
        event = json.loads(body)
        print(f"\n[Worker/ERP] ⚡ Live webhook received: {event}")
        
        sku = event.get("sku", "UNKNOWN")
        quantity_sold = event.get("quantity", 0)
        
        # In a real environment, you'd step the RL engine or record the sale in Postgres.
        # e.g., session = SessionLocal(); record_sale(sku, quantity_sold)
        
        # Broadcast via AMQP to the UI_UPDATE_EXCHANGE so Node.js can proxy it to WebSockets
        update_message = json.dumps({
            "type": "inventory_update",
            "sku": sku,
            "quantity_deducted": quantity_sold,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        channel.basic_publish(
            exchange=UI_UPDATE_EXCHANGE,
            routing_key="",
            body=update_message,
            properties=pika.BasicProperties(content_type="application/json"),
        )
        print(f"[Worker/ERP] ✓ Processed & Broadcasted update for {sku}")

    except Exception as e:
        print(f"[Worker/ERP] ✗ Failed to process ERP event: {e}")

    channel.basic_ack(delivery_tag=method.delivery_tag)


# ── Module-level thread pool (initialised in main) ────────────────────────
_job_executor: ThreadPoolExecutor | None = None
_ack_lock = threading.Lock()


def main():
    """Main worker loop — consume jobs from RabbitMQ in parallel."""
    global _job_executor

    print("[Worker] Starting RL Training Worker (parallel mode)...")
    print(f"[Worker] RabbitMQ:         {RABBITMQ_URL}")
    print(f"[Worker] Storage:          {storage_service.STORAGE_DIR}")
    print(f"[Worker] Max parallel SKUs: {MAX_PARALLEL_SKUS}")

    # Ensure DB tables exist (worker may start before API runs migrations)
    Base.metadata.create_all(bind=engine)

    # Create the thread pool that will run training jobs concurrently
    _job_executor = ThreadPoolExecutor(
        max_workers=MAX_PARALLEL_SKUS,
        thread_name_prefix="sku-trainer",
    )

    connection = get_rabbitmq_connection()
    channel = connection.channel()

    # Declare the job queue (durable so jobs survive restarts)
    channel.queue_declare(queue=JOB_QUEUE, durable=True)
    channel.queue_declare(queue=ERP_QUEUE, durable=True)

    # Declare the progress exchange (fanout so all listeners get updates)
    channel.exchange_declare(exchange=PROGRESS_EXCHANGE, exchange_type="fanout")
    channel.exchange_declare(exchange=UI_UPDATE_EXCHANGE, exchange_type="fanout")

    # Allow up to MAX_PARALLEL_SKUS unacknowledged messages to be in-flight
    # at once so the thread pool always has work to do without the queue
    # blocking behind a single long-running job.
    channel.basic_qos(prefetch_count=MAX_PARALLEL_SKUS)

    channel.basic_consume(queue=JOB_QUEUE, on_message_callback=process_job)
    channel.basic_consume(queue=ERP_QUEUE, on_message_callback=process_erp_webhook)

    print(f"[Worker] Listening on '{JOB_QUEUE}' and '{ERP_QUEUE}' "
          f"(prefetch={MAX_PARALLEL_SKUS}, workers={MAX_PARALLEL_SKUS})... (Ctrl+C to stop)")

    try:
        while not _shutdown:
            connection.process_data_events(time_limit=1)
    except KeyboardInterrupt:
        pass
    finally:
        print("[Worker] Shutting down — waiting for in-progress jobs to finish...")
        if _job_executor:
            _job_executor.shutdown(wait=True)
        try:
            channel.close()
            connection.close()
        except Exception:
            pass
        print("[Worker] Shutdown complete.")


if __name__ == "__main__":
    main()
