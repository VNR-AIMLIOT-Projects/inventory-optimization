# Spec A003 — Data Model

**ID**: SPEC-A003
**Status**: Done
**Type**: Architecture
**Author**: @sujaynimmagadda
**Created**: 2026-06-03
**Linked Diagram**: [diagrams/03-database-schema.md](../../diagrams/03-database-schema.md)
**Source Files**: `Backend-RL/src/models.py`, `Backend-RL/alembic/`

---

## Summary

Canonical reference for the PostgreSQL database schema. Documents table purposes, column semantics, JSON field schemas, and relationship constraints.

---

## Tables

### `uploaded_files`
Stores metadata about CSV/Excel files uploaded by users.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | SERIAL | PK | |
| `filename` | TEXT | NOT NULL | Original file name |
| `filepath` | TEXT | NOT NULL | Path on disk in `uploads/` |
| `file_type` | TEXT | NOT NULL | `"csv"` or `"xlsx"` |
| `skus` | JSONB | NOT NULL | `["SKU-A", "SKU-B"]` — list of detected SKU names |
| `uploaded_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

---

### `training_runs`
One row per SKU training job.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | SERIAL | PK | |
| `uploaded_file_id` | INT | FK → uploaded_files.id | |
| `sku` | TEXT | NOT NULL | |
| `season_type` | TEXT | NOT NULL | `"summer"`, `"winter"`, or `"custom"` |
| `episodes` | INT | NOT NULL | |
| `holding_cost` | FLOAT | NOT NULL | |
| `stockout_penalty` | FLOAT | NOT NULL | |
| `max_order` | INT | NOT NULL | |
| `action_step` | INT | NOT NULL | |
| `best_reward` | FLOAT | NULLABLE | Set when first checkpoint saved |
| `final_avg_reward` | FLOAT | NULLABLE | Average of last 50 episodes |
| `rewards` | JSONB | NULLABLE | `[1200.5, 1380.2, ...]` — per-episode list |
| `model_path` | TEXT | NULLABLE | `/app/storage/sku_a_run42.pt` |
| `log_path` | TEXT | NULLABLE | Path to training log file |
| `demand_params` | JSONB | NULLABLE | Snapshot of detected params at training time |
| `status` | TEXT | NOT NULL | `"pending"` \| `"running"` \| `"success"` \| `"failed"` |
| `started_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |
| `completed_at` | TIMESTAMPTZ | NULLABLE | Set when status → success or failed |

**`demand_params` JSON schema:**
```json
{
  "mean": 50.0,
  "std": 12.0,
  "trend": 0.01,
  "seasonality_amplitude": 0.3,
  "promo_probability": 0.05
}
```

---

### `evaluation_results`
One row per training run evaluation.

| Column | Type | Constraints | Notes |
|--------|------|-------------|-------|
| `id` | SERIAL | PK | |
| `training_run_id` | INT | FK → training_runs.id, UNIQUE | One evaluation per run |
| `sku` | TEXT | NOT NULL | Denormalized for query convenience |
| `rl_reward` | FLOAT | NOT NULL | Greedy RL episode total reward |
| `oracle_reward` | FLOAT | NOT NULL | Oracle (W=5 lookahead) total reward |
| `rule_reward` | FLOAT | NOT NULL | Rule-based s,S policy total reward |
| `rl_vs_oracle_pct` | FLOAT | NOT NULL | `(rl_reward / oracle_reward) * 100` |
| `config` | JSONB | NULLABLE | Eval configuration snapshot |
| `eval_graph_path` | TEXT | NULLABLE | Path to matplotlib comparison graph |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | |

---

## Relationships

```
uploaded_files (1) ──< training_runs (many)   [one file, many SKU runs]
training_runs  (1) ──| evaluation_results (0..1)  [one run, at most one eval]
```

---

## Design Decisions

1. **`rewards` as JSONB array** (not a separate table) — keeps read patterns simple; the full reward history is always fetched together for chart rendering
2. **`demand_params` snapshot** — stored at training time so evaluation is reproducible even if demand is later edited by the user
3. **`rl_vs_oracle_pct` denormalized** — pre-computed to avoid float division on every read
4. **`status` as TEXT** (not enum) — Alembic migrations for enum changes in PostgreSQL are painful; TEXT with application-level validation is simpler

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-03 | @sujaynimmagadda | Initial data model spec |
