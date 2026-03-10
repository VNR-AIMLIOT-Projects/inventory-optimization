# Inventory Optimization — Docker Setup

One-command setup for the complete inventory optimization demo with:
- **PostgreSQL** database (local, persistent)
- **FastAPI Backend** (RL training, evaluation, demand processing)
- **React + Express Frontend** (UI, simulation, human-in-the-loop)

## Quick Start

```bash
# From the project root (inventory-optimization/)
docker compose up --build
```

This will:
1. Start a local PostgreSQL database
2. Run Alembic migrations for the backend (SQLAlchemy)
3. Push the Drizzle schema for the frontend
4. Start the FastAPI backend on **http://localhost:8000**
5. Start the React frontend on **http://localhost:3000**

> **Note:** The frontend uses port 3000 instead of 5000 because macOS reserves port 5000 for AirPlay Receiver.

## Access

| Service          | URL                         |
|------------------|-----------------------------|
| Frontend (UI)    | http://localhost:3000        |
| Backend (API)    | http://localhost:8000        |
| API Docs         | http://localhost:8000/docs   |
| PostgreSQL       | localhost:5432               |

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Browser    │────▶│  Frontend :3000   │────▶│              │
│              │     │  (React+Express)  │     │  PostgreSQL  │
│              │────▶│                   │     │   :5432      │
│              │     └──────────────────┘     │              │
│              │                              │              │
│              │     ┌──────────────────┐     │              │
│              │────▶│  Backend  :8000   │────▶│              │
│              │     │  (FastAPI+DQN)    │     └──────────────┘
│              │     │                   │
│              │◀───▶│  WebSocket /ws    │
└─────────────┘     └──────────────────┘
                           │
                    ┌──────┴──────┐
                    │  Local Disk  │
                    │  /storage/   │
                    │  - models/   │
                    │  - uploads/  │
                    │  - logs/     │
                    └─────────────┘
```

## Data Persistence

- **Database**: PostgreSQL stores training runs, evaluations, simulation history, demand data
- **File Storage**: Model weights (.pt), uploaded CSVs, evaluation graphs stored in Docker volume

## Stopping

```bash
docker compose down          # Stop containers (data persists)
docker compose down -v       # Stop and remove all data
```

## Local Development (without Docker)

If you prefer running services locally without Docker, ensure PostgreSQL is running locally and set the `DATABASE_URL` environment variable:

```bash
# Backend
cd Backend-RL
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory
pip install -r requirements.txt
alembic upgrade head
cd src && uvicorn app:app --reload --port 8000

# Frontend
cd Frontend
# Edit .env to set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory
npm install
npm run db:push
npm run dev
```
