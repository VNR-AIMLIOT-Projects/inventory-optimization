# Combined Architecture

Replenix relies on a tightly integrated but fully modular architecture. Below is the macroscopic view of how the Frontend, Backend APIs, RL Workers, RAG Pipeline, and Observability layers all interact.

## Macro System Architecture

```mermaid
graph TD
    %% Define Subgraphs
    subgraph Clients["Clients"]
        UI["Main Replenix UI (Port 3000)"]
        ObsUI["Observability Dashboard (Port 3001)"]
    end
    
    subgraph API["Backend API (FastAPI)"]
        Router["Zero-shot Agent Router"]
        Agents["Agent Executors (Upload, Modify, Train, etc.)"]
        Embedder["Embedding Service"]
        ObsTracer["Observability Tracer"]
        EvalTask["Async Evaluator Task"]
    end
    
    subgraph Data["Persistence & Brokers"]
        PG["PostgreSQL (App Data, ai_traces)"]
        PGVec["pgvector (RAG Chunks)"]
        Rabbit["RabbitMQ (Task Queue)"]
        Redis["Redis (Caching & Rate Limiting)"]
    end
    
    subgraph RL["RL Workers (Distributed)"]
        Worker1["RL Worker 1 (StableBaselines3)"]
        WorkerN["RL Worker N"]
    end

    %% Client Interactions
    UI -->|HTTP / REST| Router
    ObsUI -->|HTTP / REST| ObsTracer

    %% API Internal Flow
    Router -->|Determines Intent| Agents
    Agents <-->|Queries| Embedder
    Embedder <-->|Vector Search| PGVec
    Agents -->|Publishes Training Tasks| Rabbit
    Agents -->|Emits Trace| ObsTracer
    ObsTracer -->|Saves Trace| PG
    ObsTracer -->|Triggers Async Eval| EvalTask
    EvalTask -->|Updates Trace Scores| PG

    %% RL Worker Flow
    Rabbit -->|Consumes Tasks| Worker1
    Rabbit -->|Consumes Tasks| WorkerN
    Worker1 -->|Writes Model Checkpoints| PG
    WorkerN -->|Writes Model Checkpoints| PG
```

## System Tenets
1. **Asynchronous by Default**: Heavy tasks (RL training, Trace evaluation, Embedding generation) are strictly offloaded from the main API thread.
2. **Specialized Agents**: RAG is not a hammer. Specialized agents (like the Modify agent) can execute strict actions without forcing RAG vocabulary overlaps.
3. **Decoupled Dashboards**: Administrative and operational views (Observability, Grafana) are maintained as independent applications to keep the main user interface lightweight.
