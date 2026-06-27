# Replenix Developer Guide

Welcome to the Replenix Developer Guide. This document provides step-by-step instructions on setting up your local development environment ("Dev").

## Quick Start (Docker)

The fastest way to get the entire Replenix stack running locally is via Docker Compose.

```bash
# From the project root (inventory-optimization/)
cd setup
docker compose up --build -d
```

### What this does:
1. Starts a local **PostgreSQL** database.
2. Starts a local **RabbitMQ** broker.
3. Starts a local **Redis** cache.
4. Runs Alembic migrations for the backend (SQLAlchemy).
4. Starts the **FastAPI Backend** on http://localhost:8000.
5. Starts the **RL Worker Pool** (listens to RabbitMQ).
6. Starts the **React Frontend** on http://localhost:3000.

> **Note:** The frontend uses port 3000 instead of 5000 because macOS Monterey+ reserves port 5000 for AirPlay Receiver.

### Accessing Services

| Service          | URL                         |
|------------------|-----------------------------|
| Frontend (UI)    | http://localhost:3000        |
| Backend (API)    | http://localhost:8000        |
| API Docs         | http://localhost:8000/docs   |
| API Metrics      | http://localhost:8000/metrics|
| PostgreSQL       | localhost:5432               |
| RabbitMQ (Mgmt)  | http://localhost:15672       |
| Redis            | localhost:6379               |

---

## Inspecting the Cache (Redis)

To monitor cache hits, keys, and memory usage locally, you can use either the Command Line or a GUI.

### Via Command Line (redis-cli)
You can execute `redis-cli` directly inside the running Redis Docker container:
```bash
docker exec -it setup-redis-1 redis-cli
```
Useful commands inside `redis-cli`:
- `KEYS *` - List all cached keys.
- `INFO stats` - View cache hits and misses (`keyspace_hits` and `keyspace_misses`).
- `MONITOR` - Watch all commands processed by the server in real-time.

### Via GUI (RedisInsight)
For a visual dashboard of your cache:
1. Download and install [RedisInsight](https://redis.com/redis-enterprise/redis-insight/).
2. Click **Add Redis Database**.
3. Use the following connection details:
   - **Host:** `127.0.0.1` (or `localhost`)
   - **Port:** `6379`
   - **Name:** `Replenix Local Cache`
4. Once connected, you can browse keys, monitor memory usage, and view real-time cache hits/misses in the **Browser** and **Profiler** tabs.

---

## Local Architecture Mapping

When running locally, the architecture slightly differs from Kubernetes (Preprod/Prod) to prioritize development speed over security and horizontal scale:

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Browser    │────▶│  Frontend :3000   │────▶│              │
│              │     │  (React+Vite)     │     │  PostgreSQL  │
│              │────▶│                   │     │   :5432      │
│              │     └──────────────────┘     │              │
│              │                              │              │
│              │     ┌──────────────────┐     │              │
│              │────▶│  Backend  :8000   │────▶│              │
│              │     │  (FastAPI)        │     └──────────────┘
│              │     │                   │
│              │◀───▶│  WebSocket /ws    │     ┌──────────────┐
└─────────────┘     └─────────┬────────┘     │              │
                              │              │   RabbitMQ   │
                              ▼              │   :5672      │
                     ┌──────────────────┐    │              │
                     │  RL Worker Pool  │◀───│              │
                     │  (Python)        │    └──────────────┘
                     └──────────────────┘
```

## Data Persistence (Local)

- **Database**: PostgreSQL stores training runs, evaluations, simulation history, and demand data.
- **Message Queue**: RabbitMQ stores pending training jobs.
- **Cache**: Redis stores heavily requested API datasets and caches API responses.
- **File Storage**: Model weights (`.pt`), uploaded CSVs, and evaluation graphs are stored in local Docker volumes mapped to `/storage/`.

### Stopping the Environment

```bash
# From the setup directory
docker compose down

# Stop and WIPE ALL DATA (removes database and storage volumes)
docker compose down -v
```

---

## Bare-Metal Development (Without Docker)

If you need to use specific IDE debuggers or prefer running services natively, follow these steps. **You still need PostgreSQL and RabbitMQ running** (you can run just those two via Docker: `cd setup && docker compose up postgres rabbitmq -d`).

### 1. Environment Variables

Create a `.env` file in the `Backend-RL/` directory (or export these):

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
REDIS_URL=redis://localhost:6379/0
```

### 2. Run the Backend (FastAPI)

```bash
cd Backend-RL
pip install -r requirements-dev.txt

# Run database migrations
alembic upgrade head

# Start the server with hot-reload
cd src
uvicorn app:app --reload --port 8000
```

### 3. Run the RL Worker

In a separate terminal:

```bash
cd Backend-RL
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory
export RABBITMQ_URL=amqp://guest:guest@localhost:5672/
export REDIS_URL=redis://localhost:6379/0

# Start the worker
python src/worker.py
```

### 4. Run the Frontend (React)

In a separate terminal:

```bash
cd Frontend
npm install

# Start the Vite development server
npm run dev
```

---

## Coding Standards & Best Practices

1. **Database Migrations:** If you modify a SQLAlchemy model in `Backend-RL/src/models/`, you MUST generate a new Alembic migration:
   ```bash
   alembic revision --autogenerate -m "Add new column"
   alembic upgrade head
   ```

2. **Frontend Styling:** Use Tailwind CSS for all styling. Complex components should utilize Shadcn UI where applicable.

3. **RL Training Logs:** When testing the Deep Q-Network locally, you can monitor training progress and loss metrics directly in the backend console output, or view the generated graphs in the UI.
