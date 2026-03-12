"""
RabbitMQ Publisher for FastAPI
==============================
Publishes training jobs to the RabbitMQ queue and listens for
progress updates from workers to relay to WebSocket clients.
"""

import os
import json
import threading

import pika

RABBITMQ_URL = os.environ.get("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
JOB_QUEUE = "rl_training_jobs"
PROGRESS_EXCHANGE = "rl_training_progress"


def _get_connection():
    """Create a new blocking connection to RabbitMQ."""
    params = pika.URLParameters(RABBITMQ_URL)
    params.heartbeat = 600
    params.blocked_connection_timeout = 300
    return pika.BlockingConnection(params)


def publish_training_job(job: dict):
    """
    Publish a training job to the RabbitMQ queue.

    job should contain:
      - run_id: int (DB primary key)
      - sku: str
      - episodes: int
      - season_type: str
      - holding_cost: float
      - stockout_penalty: float
      - max_order: int or None
      - uploaded_filepath: str or None
      - demand_params: dict or None
    """
    connection = _get_connection()
    channel = connection.channel()
    channel.queue_declare(queue=JOB_QUEUE, durable=True)

    body = json.dumps(job)
    channel.basic_publish(
        exchange="",
        routing_key=JOB_QUEUE,
        body=body,
        properties=pika.BasicProperties(
            delivery_mode=2,  # persistent
            content_type="application/json",
        ),
    )
    channel.close()
    connection.close()
    print(f"[RMQ] Published job: run_id={job['run_id']} sku={job['sku']}")


class ProgressListener:
    """
    Listens for training progress messages from the RabbitMQ exchange
    and calls a callback for each message. Runs in a background thread.
    """

    def __init__(self, on_message):
        """
        on_message: callable(dict) — called for every progress update from workers.
        """
        self._on_message = on_message
        self._thread = None
        self._stop = False
        self._connection = None

    def start(self):
        """Start listening in a daemon thread."""
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the listener to stop."""
        self._stop = True
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass

    def _run(self):
        """Background thread: connect to RabbitMQ and consume progress messages."""
        import time
        max_retries = 30
        for attempt in range(1, max_retries + 1):
            if self._stop:
                return
            try:
                self._connection = _get_connection()
                channel = self._connection.channel()
                channel.exchange_declare(exchange=PROGRESS_EXCHANGE, exchange_type="fanout")

                # Create an exclusive, auto-delete queue bound to the fanout exchange
                result = channel.queue_declare(queue="", exclusive=True)
                queue_name = result.method.queue
                channel.queue_bind(exchange=PROGRESS_EXCHANGE, queue=queue_name)

                print(f"[RMQ] Progress listener connected (attempt {attempt})")

                for method, properties, body in channel.consume(queue_name, inactivity_timeout=1):
                    if self._stop:
                        break
                    if body is None:
                        continue
                    try:
                        data = json.loads(body)
                        self._on_message(data)
                    except Exception as e:
                        print(f"[RMQ] Progress parse error: {e}")

                break  # Clean exit from consume loop

            except pika.exceptions.AMQPConnectionError as e:
                if attempt == max_retries:
                    print(f"[RMQ] Progress listener gave up after {max_retries} attempts: {e}")
                    return
                print(f"[RMQ] Progress listener retry {attempt}/{max_retries}: {e}")
                time.sleep(3)
            except Exception as e:
                print(f"[RMQ] Progress listener error: {e}")
                time.sleep(3)
