# Spec F001 — Multi-SKU Parallel Training

**ID**: SPEC-F001
**Status**: Approved
**Type**: Feature
**Author**: @sujaynimmagadda
**Created**: 2026-06-03
**Updated**: 2026-06-03
**Linked Diagram**: [diagrams/06-rabbitmq-message-flow.md](../../diagrams/06-rabbitmq-message-flow.md)
**Linked Issue**: —

---

## Summary

Allow users to train RL models for multiple SKUs simultaneously using the existing RabbitMQ worker pool. Each SKU gets its own training job, reported progress independently, and the UI shows a per-SKU progress grid in Stage 3.

---

## Context & Motivation

Currently, the "Train" button in Stage 3 trains one SKU at a time. When a file with multiple SKUs is uploaded, users must train each sequentially — causing significant wait time and friction for multi-product warehouses.

---

## Scope

### In Scope
- [ ] `POST /api/multi/train-all` — publish one RabbitMQ job per SKU from a shared hyperparameter config
- [ ] `GET /api/multi/status` — return per-SKU training progress as a list
- [ ] Frontend Stage 3: multi-SKU progress grid (one card per SKU with episode, reward, epsilon, status)
- [ ] DB: one `training_runs` row created per SKU at job submission time

### Out of Scope
- [ ] Cross-SKU model sharing or transfer learning
- [ ] Priority queue ordering between SKUs
- [ ] Per-SKU hyperparameter overrides (all SKUs share the same config in this spec)
- [ ] Cancelling individual SKU jobs once started

---

## Behavioral Specification

**Scenario 1: Happy Path — 3 SKUs**
- **Given** a file with SKUs `["SKU-A", "SKU-B", "SKU-C"]` has been uploaded
- **When** the user configures hyperparameters and clicks "Train All"
- **Then** 3 RabbitMQ messages are published to the `jobs` exchange
- **And** 3 rows are created in `training_runs` with `status=pending`
- **And** the UI shows 3 progress cards, each updating independently via WebSocket

**Scenario 2: Single worker available**
- **Given** only 1 worker replica is running
- **When** 3 SKU jobs are published
- **Then** jobs queue and are processed sequentially (FIFO)
- **And** the UI correctly shows 2 cards as `pending` and 1 as `running`

**Scenario 3: Worker crash mid-training**
- **Given** Worker 1 is training SKU-A and crashes
- **When** the crash occurs
- **Then** the RabbitMQ job for SKU-A is requeued (nack + requeue=true)
- **And** another worker picks up SKU-A and resumes from episode 0
- **And** SKU-B and SKU-C training is unaffected

**Scenario 4: Empty SKU list**
- **Given** the request body has `sku_list: []`
- **When** `POST /api/multi/train-all` is called
- **Then** HTTP 400 is returned with `{"detail": "sku_list cannot be empty"}`

---

## API Contract

### `POST /api/multi/train-all`

**Request:**
```json
{
  "sku_list": ["SKU-A", "SKU-B", "SKU-C"],
  "episodes": 500,
  "holding_cost": 0.5,
  "stockout_penalty": 5.0,
  "max_order": 100,
  "action_step": 10,
  "uploaded_file_id": 7
}
```

**Response (200 OK):**
```json
[
  { "sku": "SKU-A", "run_id": 42 },
  { "sku": "SKU-B", "run_id": 43 },
  { "sku": "SKU-C", "run_id": 44 }
]
```

**Error Responses:**

| Status | Condition | Body |
|--------|-----------|------|
| 400 | `sku_list` is empty | `{"detail": "sku_list cannot be empty"}` |
| 404 | `uploaded_file_id` not found | `{"detail": "uploaded file not found"}` |

---

### `GET /api/multi/status`

**Query params:** `?run_ids=42,43,44`

**Response (200 OK):**
```json
[
  { "sku": "SKU-A", "run_id": 42, "episode": 237, "reward": 1842.5, "epsilon": 0.42, "status": "running" },
  { "sku": "SKU-B", "run_id": 43, "episode": 0,   "reward": null,   "epsilon": null, "status": "pending" },
  { "sku": "SKU-C", "run_id": 44, "episode": 500,  "reward": 2011.0, "epsilon": 0.05, "status": "completed" }
]
```

---

## Data Model Changes

No schema changes required. Each SKU training job creates one row in the existing `training_runs` table:

```sql
-- No migrations needed — existing schema supports this:
-- training_runs.sku → one row per SKU
-- training_runs.status → pending | running | success | failed
```

---

## Acceptance Criteria

- [ ] **AC1**: Clicking "Train All" with 3 SKUs creates exactly 3 `training_runs` rows with `status=pending`
- [ ] **AC2**: 3 RabbitMQ messages are published to the `jobs` exchange within 2 seconds
- [ ] **AC3**: Each SKU's WebSocket progress updates independently (SKU-A ep 300 doesn't affect SKU-B ep 150)
- [ ] **AC4**: If one worker crashes, only that SKU's job restarts — others continue uninterrupted
- [ ] **AC5**: `GET /api/multi/status?run_ids=42,43,44` returns a list of 3 objects
- [ ] **AC6**: Empty `sku_list` returns HTTP 400
- [ ] **AC7**: Frontend Stage 3 shows one progress card per SKU with live episode/reward/status

---

## Test Cases

| # | Scenario | Input | Expected | Type |
|---|----------|-------|----------|------|
| T1 | 3 SKUs, all workers available | sku_list: [A,B,C] | 3 run_ids returned, 3 DB rows | Integration |
| T2 | Empty sku_list | sku_list: [] | HTTP 400 | Unit |
| T3 | Invalid file ID | uploaded_file_id: 9999 | HTTP 404 | Unit |
| T4 | Status poll — mixed states | run_ids: 42,43,44 | List of 3 with correct statuses | Integration |
| T5 | WebSocket isolation | 2 SKUs training | Each card updates from its own run_id only | E2E |

---

## Implementation Notes

Files to touch:
- `Backend-RL/src/app.py` — add `/multi/train-all` and `/multi/status` routes
- `Backend-RL/src/schemas.py` — add `MultiTrainRequest`, `MultiTrainResponse`, `MultiStatusResponse`
- `Backend-RL/src/queue_service.py` — add `publish_multi_jobs()` helper
- `Frontend/client/src/pages/Stage3Page.tsx` — add multi-SKU progress grid component
- `Frontend/server/routes.ts` — proxy `/api/multi/*` to backend

---

## Verification Checklist

- [ ] All 7 acceptance criteria pass
- [ ] Stage 1–5 single-SKU flow still works (no regression)
- [ ] `diagrams/06-rabbitmq-message-flow.md` updated with multi-job publish path
- [ ] PR description includes: `Implements SPEC-F001`

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-03 | @sujaynimmagadda | Initial spec — example for spec-driven workflow |
