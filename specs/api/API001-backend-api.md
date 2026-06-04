# Spec API001 — Backend REST API Contracts

**ID**: SPEC-API001
**Status**: Done
**Type**: API
**Author**: @sujaynimmagadda
**Created**: 2026-06-03
**Linked Diagram**: [diagrams/08-api-contracts.md](../../diagrams/08-api-contracts.md)
**Source Files**: `Backend-RL/src/app.py`, `Backend-RL/src/schemas.py`

---

## Summary

Canonical reference for all FastAPI backend REST endpoints. This spec is the source of truth for request/response schemas, status codes, and error conditions. Any change to an endpoint must update this spec first.

---

## Global Conventions

- **Base URL**: `http://localhost:8000/api` (dev) | `$BACKEND_PUBLIC_URL/api` (prod)
- **Content-Type**: `application/json` for all JSON bodies
- **Error format**: `{ "detail": "human-readable message" }` (FastAPI default)
- **Auth**: None on backend (auth is handled by the Node.js frontend server)

---

## Demand API

### `POST /demand/upload`
Upload a CSV or Excel file and detect SKUs + demand parameters.

**Request:** `multipart/form-data`
- `file`: CSV or XLSX file

**Response 200:**
```json
{
  "file_id": 7,
  "filename": "warehouse_q1.csv",
  "skus": ["SKU-A", "SKU-B"],
  "dates": ["2024-01-01", "2024-01-02", "..."],
  "demand": [45.0, 52.0, "..."],
  "detected_params": {
    "mean": 48.5, "std": 11.2, "trend": 0.008,
    "seasonality_amplitude": 0.25, "promo_probability": 0.04
  }
}
```
**Errors:** `400` if file type not CSV/XLSX | `422` if file is malformed

---

### `POST /demand/generate`
Generate synthetic demand for the selected SKU.

**Request:**
```json
{ "season_type": "summer", "days": 180, "sku": "SKU-A" }
```

**Response 200:**
```json
{ "dates": ["2024-01-01", "..."], "demand": [45.0, "..."] }
```
**Errors:** `400` if `season_type` not in `["summer", "winter", "custom"]`

---

### `POST /demand/modify/spike`
Add a demand spike on a specific date.

**Request:**
```json
{ "date": "2024-03-15", "multiplier": 3.0, "width": 3 }
```

**Response 200:** Same as `/demand/generate` — updated full demand series.

---

### `POST /demand/modify/scale`
Scale demand in a date range by a factor.

**Request:**
```json
{ "start_date": "2024-02-01", "end_date": "2024-02-28", "factor": 1.5 }
```

**Response 200:** Updated full demand series.

---

### `POST /demand/reset`
Reset demand to the originally uploaded or generated series.

**Response 200:** Original demand series.

---

### `GET /demand/params`
Get the currently detected demand parameters for the active session.

**Response 200:**
```json
{ "mean": 48.5, "std": 11.2, "trend": 0.008, "seasonality_amplitude": 0.25, "promo_probability": 0.04 }
```

---

## Training API

### `POST /train`
Publish a single-SKU training job to RabbitMQ.

**Request:**
```json
{
  "sku": "SKU-A",
  "uploaded_file_id": 7,
  "episodes": 500,
  "holding_cost": 0.5,
  "stockout_penalty": 5.0,
  "max_order": 100,
  "action_step": 10
}
```

**Response 200:**
```json
{ "run_id": 42, "status": "initiated" }
```
**Errors:** `404` if `uploaded_file_id` not found

---

### `GET /train/status/{run_id}`
Poll current training progress for a run.

**Response 200:**
```json
{
  "run_id": 42, "sku": "SKU-A",
  "episode": 237, "reward": 1842.5, "epsilon": 0.42,
  "best_eval": 2011.0, "status": "running"
}
```
**Errors:** `404` if `run_id` not found

---

## Multi-SKU API

### `POST /multi/train-all`
See **SPEC-F001** for full contract.

### `GET /multi/status`
See **SPEC-F001** for full contract.

---

## Evaluation API

### `POST /evaluate`
Run RL vs Oracle vs Rule-based evaluation for a completed training run.

**Request:**
```json
{ "run_id": 42, "eval_episodes": 1 }
```

**Response 200:**
```json
{
  "eval_id": 11,
  "sku": "SKU-A",
  "rl_reward": 2011.0,
  "oracle_reward": 2350.0,
  "rule_reward": 1650.0,
  "rl_vs_oracle_pct": 85.6,
  "eval_graph_path": "/app/storage/eval_run42.png"
}
```
**Errors:** `404` if `run_id` not found | `400` if training not yet completed

---

### `GET /evaluate/results/{run_id}`
Retrieve cached evaluation results without re-running.

**Response 200:** Same schema as `POST /evaluate`.
**Errors:** `404` if no evaluation exists for this run

---

## Deployment API

### `POST /deploy/step`
Advance the deployment simulation by N days.

**Request:**
```json
{ "run_id": 42, "n_days": 1, "use_override": false }
```

**Response 200:**
```json
{
  "day": 15,
  "inventory": 87,
  "demand": 52,
  "rl_action": 20,
  "reward": 412.5,
  "health": "good",
  "cumulative_reward": 5820.0
}
```

---

### `POST /deploy/override`
Set a manual override order quantity for the next step.

**Request:**
```json
{ "run_id": 42, "override_qty": 50 }
```

**Response 200:** `{ "accepted": true }`

---

### `GET /deploy/status/{run_id}`
Get KPI dashboard data for a deployment simulation.

**Response 200:**
```json
{
  "run_id": 42,
  "total_reward": 5820.0,
  "fill_rate": 0.94,
  "stockout_days": 3,
  "avg_inventory": 82.5,
  "current_day": 15
}
```

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-03 | @sujaynimmagadda | Initial API contracts spec |
