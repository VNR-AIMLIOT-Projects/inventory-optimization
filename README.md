# Inventory Optimization Project

A reinforcement learning–based inventory optimization system with a DQN agent, demand forecasting, and a human-in-the-loop simulation dashboard.

- **Frontend**: React + Express (TypeScript, Vite, Tailwind, Drizzle ORM)
- **Backend-RL**: FastAPI + PyTorch (DQN agent, SQLAlchemy, Alembic)
- **Database**: PostgreSQL 16

---

## Quick Start (Docker — recommended)

The easiest way to run the full project. Works on **macOS**, **Windows**, and **Linux**.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) installed and running

### Run

```bash
git clone https://github.com/your-user/inventory-optimization.git
cd inventory-optimization
docker compose up --build
```

That's it. This starts PostgreSQL, the backend, and the frontend — all wired together.

### Access

| Service       | URL                       |
|---------------|---------------------------|
| Frontend (UI) | http://localhost:3000      |
| Backend (API) | http://localhost:8000      |
| API Docs      | http://localhost:8000/docs |

### Stop

```bash
docker compose down          # Stop containers (data persists)
docker compose down -v       # Stop and delete all data
```

### Troubleshooting

- **Port 5432 already in use**: You have a local PostgreSQL running. Stop it first:
  - **macOS**: `brew services stop postgresql` (or `postgresql@14`, `@15`, `@16`)
  - **Windows**: Stop the PostgreSQL service from Services (`services.msc`) or `net stop postgresql-x64-16`
  - **Linux**: `sudo systemctl stop postgresql`
- **Port 3000 already in use**: Another app is using it. Either stop that app or change the frontend port in `docker-compose.yml`.

---

## Manual Setup (without Docker)

Use this if you want to run services individually for development.

### Prerequisites

- **Python 3.11+**
- **Node.js 22+**
- **PostgreSQL** running locally with a database named `inventory`

### Database

Create the database (if it doesn't exist):

```bash
psql -U postgres -c "CREATE DATABASE inventory;"
```

### Backend

```bash
cd Backend-RL
python -m venv venv
```

Activate the virtual environment:

- **macOS / Linux**:
  ```bash
  source venv/bin/activate
  ```
- **Windows** (Command Prompt):
  ```cmd
  venv\Scripts\activate
  ```
- **Windows** (PowerShell):
  ```powershell
  venv\Scripts\Activate.ps1
  ```

Install dependencies and start:

```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory   # macOS/Linux
# set DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory    # Windows CMD
# $env:DATABASE_URL="postgresql://postgres:postgres@localhost:5432/inventory" # Windows PowerShell
alembic upgrade head
cd src
uvicorn app:app --reload --port 8000
```

Backend runs at **http://localhost:8000** — API docs at **http://localhost:8000/docs**.

### Frontend

```bash
cd Frontend
```

Create a `.env` file:

```
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/inventory
PORT=3000
```

Then:

```bash
npm install
npm run db:push
npm run dev
```

Frontend runs at **http://localhost:3000**.

> **Note:** Both backend and frontend must be running simultaneously for the app to work.
