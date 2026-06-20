# Replenix Backend & RL Worker

This directory houses the core logic for the Replenix platform, comprising two tightly-coupled but independently scalable components:
1. **FastAPI Web Server:** Handles REST API requests, websocket connections, and orchestrates jobs.
2. **Reinforcement Learning (RL) Worker:** An asynchronous Python process that consumes training jobs from RabbitMQ and runs PyTorch DQN models.

## 1. Local Development Setup

We recommend using Docker Compose for local development (see the main `docs/developer_guide.md`). If you prefer running it natively:

### Virtual Environment Setup

```bash
# Create and activate
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements-dev.txt
```

### Environment Variables
Create a `.env` file in this directory (or rely on local defaults):
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
```

## 2. Running the Services

### Start the FastAPI Server
The backend requires the database to be migrated first.
```bash
alembic upgrade head
cd src
uvicorn app:app --reload --port 8000
```
- **API Docs:** http://localhost:8000/docs
- **Metrics Endpoint:** http://localhost:8000/metrics

### Start the RL Worker
In a separate terminal (with the `.venv` activated):
```bash
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory
export RABBITMQ_URL=amqp://guest:guest@localhost:5672/
python src/worker.py
```

## 3. Architecture & Observability

- **Database (PostgreSQL):** Accessed via SQLAlchemy async ORM. Migrations are managed by Alembic (`alembic/` directory).
- **Message Broker (RabbitMQ):** Task queues are managed via `aio-pika`. The API pushes jobs to `training_queue`, and the worker consumes them.
- **Monitoring (Prometheus):** The FastAPI app uses `prometheus-fastapi-instrumentator` to automatically expose RED (Rate, Errors, Duration) metrics at `/metrics`.

## 4. Coding Standards
- **Migrations:** Always run `alembic revision --autogenerate -m "Message"` when changing models in `src/models/`.
- **Typing:** Use strict Pydantic models for all request/response validation in `src/schemas/`.
- **Docstrings:** All API routes and core functions must be documented using Google-style docstrings.