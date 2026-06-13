# Diagram 05 — Docker Deployment Architecture

**Scope**: Docker Compose services, networks, volumes, healthchecks, dependencies  
**Last Updated**: 2026-06-03  
**Source File**: [docker-compose.yml](../docker-compose.yml), [docker-compose.prod.yml](../docker-compose.prod.yml)

---

```mermaid
flowchart TB
    classDef service  fill:#1e3a5f,stroke:#4a90d9,color:#e8f4fd
    classDef infra    fill:#2d1b4e,stroke:#9c27b0,color:#f3e5f5
    classDef volume   fill:#1a3a2a,stroke:#4caf50,color:#e8f7ed
    classDef worker   fill:#3b1f0a,stroke:#ff8c00,color:#fff5e6
    classDef external fill:#2a1a1a,stroke:#ef5350,color:#fce4ec

    HOST(["Host Machine\nlocalhost"])

    subgraph DockerNetwork["Docker Compose Network (bridge)"]
        direction TB

        subgraph Infra["Infrastructure Layer"]
            PG["postgres:16-alpine\nPort: 5432\nHealthcheck: pg_isready\nVolume: pgdata"]:::infra
            RMQ["rabbitmq:3.13-management-alpine\nPort: 5672 (AMQP)\nPort: 15672 (Management UI)\nHealthcheck: rabbitmq-diagnostics ping"]:::infra
        end

        subgraph App["Application Layer"]
            BE["backend\nBuild: ./Backend-RL/Dockerfile\nPort: 8000\nFastAPI + Uvicorn\nVolume: backend_storage\nDepends: postgres ✓ rabbitmq ✓"]:::service
            FE["frontend\nBuild: ./Frontend/Dockerfile\nPort: 3000\nNode.js + Vite\nDepends: postgres ✓ rabbitmq ✓ backend ∼"]:::service
        end

        subgraph WorkerPool["Worker Pool (replicas: 8 default)"]
            W1["rl-worker replica 1\nBuild: ./Backend-RL/Dockerfile.worker\nOMP_NUM_THREADS=2\nMKL_NUM_THREADS=2\nTORCH_NUM_THREADS=2"]:::worker
            W2["rl-worker replica 2"]:::worker
            WN["rl-worker replica N\n(scale via WORKER_REPLICAS env)"]:::worker
        end

        subgraph Volumes["Named Volumes"]
            PGVOL["pgdata\nPostgreSQL data files\npersistent across restarts"]:::volume
            BSVOL["backend_storage\nuploads/ — CSV, Excel\nstorage/ — .pt models\n          — eval graphs\nShared: backend + workers"]:::volume
        end
    end

    subgraph External["External APIs"]
        GROQ["Groq API\nLlama-3.3-70B\nHTTPS"]:::external
        RESEND["Resend API\nTransactional email\nHTTPS"]:::external
    end

    HOST -->|":3000"| FE
    HOST -->|":8000"| BE
    HOST -->|":15672 (admin)"| RMQ

    FE -->|"REST + WS\nhttp://backend:8000"| BE
    BE -->|"AMQP\namqp://rabbitmq:5672"| RMQ
    W1 -->|"AMQP"| RMQ
    W2 -->|"AMQP"| RMQ
    WN -->|"AMQP"| RMQ

    PG -.->|"healthcheck gate"| BE
    PG -.->|"healthcheck gate"| FE
    PG -.->|"healthcheck gate"| W1
    RMQ -.->|"healthcheck gate"| BE
    RMQ -.->|"healthcheck gate"| FE
    RMQ -.->|"healthcheck gate"| W1

    BE -->|"postgresql://postgres:5432"| PG
    FE -->|"postgresql://postgres:5432"| PG
    W1 -->|"postgresql://postgres:5432"| PG

    BE --- BSVOL
    W1 --- BSVOL
    W2 --- BSVOL
    PG --- PGVOL

    FE -->|"LLM copilot calls"| GROQ
    FE -->|"email notifications"| RESEND
```

---

## Environment Variables

| Variable | Default | Used By |
|----------|---------|---------|
| `POSTGRES_USER` | `postgres` | postgres, backend, frontend, workers |
| `POSTGRES_PASSWORD` | `postgres` | postgres, backend, frontend, workers |
| `POSTGRES_DB` | `inventory` | postgres, backend, frontend, workers |
| `RABBITMQ_DEFAULT_USER` | `guest` | rabbitmq, backend, frontend, workers |
| `RABBITMQ_DEFAULT_PASS` | `guest` | rabbitmq, backend, frontend, workers |
| `WORKER_REPLICAS` | `8` | rl-worker deploy.replicas |
| `GROQ_API_KEY` | *(required)* | backend |
| `RESEND_API_KEY` | *(required)* | frontend |
| `BACKEND_PUBLIC_URL` | `http://localhost:8000` | frontend |

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-06-03 | Initial diagram — derived from docker-compose.yml | @sujaynimmagadda |
