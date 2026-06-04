# Spec A001 — System Overview

**ID**: SPEC-A001
**Status**: Done
**Type**: Architecture
**Author**: @sujaynimmagadda
**Created**: 2026-06-03
**Linked Diagram**: [diagrams/01-system-architecture.md](../../diagrams/01-system-architecture.md)

---

## Summary

This document describes the high-level architecture of the Replenix inventory optimization system. It is the canonical reference for system topology, service boundaries, and communication protocols.

---

## System Components

### 1. Frontend (React / Vite / TypeScript)
- 5 pipeline stages: Data Ingestion → Demand Shaping → RL Training → Evaluation → Deployment Sim
- Each stage has an integrated LLM Copilot powered by Groq (Llama-3.3-70B)
- Node.js Express server handles auth, session management, and proxies API calls to the FastAPI backend
- Port: 3000

### 2. FastAPI Backend (Python / Uvicorn)
- Handles all business logic: demand processing, training job dispatch, evaluation, deployment simulation
- Manages WebSocket connections for live training progress
- Port: 8000

### 3. RL Engine (Python modules)
- `demand.py` — Brownian motion demand generation
- `environment.py` — 15-dimensional state space InventoryEnvironment
- `dqn.py` — Double DQN with 512-512-256 architecture, Huber loss, Polyak target update
- `trainer.py` — Training loop with adaptive rewards, oracle baseline, greedy eval checkpoints

### 4. Worker Pool (Python processes via Docker replicas)
- Stateless workers that consume training jobs from RabbitMQ
- Default: 8 replicas (configurable via `WORKER_REPLICAS`)
- Publish per-episode progress back to RabbitMQ progress exchange

### 5. RabbitMQ
- `jobs` exchange (direct): training job dispatch
- `progress` exchange (fanout): episode-by-episode broadcast

### 6. PostgreSQL
- 3 tables: `uploaded_files`, `training_runs`, `evaluation_results`
- Source of truth for all persistent state

### 7. File Storage
- Docker named volume `backend_storage`
- `uploads/` — CSV/Excel files
- `storage/` — trained model `.pt` checkpoints + evaluation graphs

### 8. External Services
- Groq API (Llama-3.3-70B) — LLM inference for stage copilots
- Resend API — transactional email

---

## Communication Protocols

| From | To | Protocol |
|------|----|----------|
| Browser | Frontend server | HTTP/WS |
| Frontend server | FastAPI | HTTP REST (proxy) |
| Browser | FastAPI | WebSocket (/ws/training) |
| FastAPI | RabbitMQ | AMQP (pika) |
| Workers | RabbitMQ | AMQP (pika) |
| FastAPI/Workers | PostgreSQL | psycopg2 / SQLAlchemy |
| Frontend | Groq | HTTPS REST |
| Frontend | Resend | HTTPS REST |

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-03 | @sujaynimmagadda | Initial architecture spec |
