# Diagram 03 — Database Schema (ERD)

**Scope**: PostgreSQL schema — all tables, columns, relationships  
**Last Updated**: 2026-06-03  
**Related Spec**: [specs/architecture/data-model.md](../specs/architecture/data-model.md)  
**Source Files**: `Backend-RL/src/models.py`, `Backend-RL/alembic/`, `Frontend/shared/`

---

```mermaid
erDiagram
    UPLOADED_FILES {
        int      id           PK
        string   filename
        string   filepath
        string   file_type    "csv or xlsx"
        json     skus         "list of SKU name strings"
        datetime uploaded_at
    }

    TRAINING_RUNS {
        int      id              PK
        int      uploaded_file_id FK
        string   sku
        string   season_type     "summer | winter | custom"
        int      episodes
        float    holding_cost
        float    stockout_penalty
        int      max_order
        int      action_step
        float    best_reward
        float    final_avg_reward
        json     rewards          "list of per-episode reward floats"
        string   model_path       "path to .pt checkpoint file"
        string   log_path
        json     demand_params    "detected params snapshot at training time"
        string   status           "pending | running | success | failed"
        datetime started_at
        datetime completed_at
    }

    EVALUATION_RESULTS {
        int      id               PK
        int      training_run_id  FK
        string   sku
        float    rl_reward
        float    oracle_reward
        float    rule_reward
        float    rl_vs_oracle_pct
        json     config
        string   eval_graph_path
        datetime created_at
    }

    UPLOADED_FILES    ||--o{ TRAINING_RUNS      : "has many (one file, many SKU runs)"
    TRAINING_RUNS     ||--o|  EVALUATION_RESULTS : "produces one evaluation result"
```

---

## Notes

- `training_runs.rewards` stores raw per-episode reward history as JSON array — used for reward chart on frontend
- `training_runs.demand_params` is a snapshot of demand params at training time, so evaluation is reproducible even if demand is later changed
- `training_runs.model_path` points to a `.pt` file in the shared `backend_storage` Docker volume
- `evaluation_results.eval_graph_path` stores the file path of the saved matplotlib comparison graph

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-06-03 | Initial ERD — ported from replenix_architecture.md | @sujaynimmagadda |
