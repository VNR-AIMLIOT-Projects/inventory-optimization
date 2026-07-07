# Diagram 08 — API Contracts (All Endpoints)

**Scope**: Complete REST + WebSocket endpoint reference for both FastAPI (Backend-RL) and Node.js (Frontend server)  
**Last Updated**: 2026-06-03  
**Source Files**: `Backend-RL/src/app.py`, `Backend-RL/src/schemas.py`, `Frontend/server/routes.ts`

---

## FastAPI Backend (port 8000)

```mermaid
flowchart TD
    classDef demand  fill:#1a3a2a,stroke:#4caf50,color:#e8f7ed
    classDef train   fill:#3b1f0a,stroke:#ff8c00,color:#fff5e6
    classDef eval    fill:#1e3a5f,stroke:#4a90d9,color:#e8f4fd
    classDef deploy  fill:#2d1b4e,stroke:#9c27b0,color:#f3e5f5
    classDef multi   fill:#1a1a3a,stroke:#5c6bc0,color:#e8eaf6
    classDef ws      fill:#2a1a1a,stroke:#ef5350,color:#fce4ec

    BE["FastAPI /api"]

    subgraph Demand["Demand API"]
        D1["POST /demand/upload\nBody: multipart/form-data file\nReturn: UploadResponse {dates, demand, detected_params, skus}"]:::demand
        D2["POST /demand/generate\nBody: {season_type, days, sku?}\nReturn: ModifyResponse {dates, demand}"]:::demand
        D3["POST /demand/modify/spike\nBody: {date, multiplier, width}\nReturn: ModifyResponse"]:::demand
        D4["POST /demand/modify/scale\nBody: {start_date, end_date, factor}\nReturn: ModifyResponse"]:::demand
        D5["POST /demand/reset\nReturn: ModifyResponse (original)"]:::demand
        D6["GET  /demand/params\nReturn: DetectedParams {mean, std, trend, seasonality}"]:::demand
    end

    subgraph Training["Training API"]
        T1["POST /train\nBody: TrainRequest {sku, episodes, holding_cost, stockout_penalty, ...}\nReturn: {run_id, status}"]:::train
        T2["GET  /train/status/{run_id}\nReturn: {episode, reward, epsilon, status, best_eval}"]:::train
        T3["WS   /ws/training\nMessages: EpisodeEvent | CompletedEvent | ErrorEvent\nAuto-reconnect supported"]:::ws
    end

    subgraph Evaluation["Evaluation API"]
        E1["POST /evaluate\nBody: {run_id, eval_episodes?}\nReturn: EvalResponse {rl_reward, oracle_reward, rule_reward, rl_vs_oracle_pct, graph_path}"]:::eval
        E2["GET  /evaluate/results/{run_id}\nReturn: EvalResponse (cached)"]:::eval
    end

    subgraph Deployment["Deployment API"]
        DP1["POST /deploy/step\nBody: {run_id, n_days?, use_override?}\nReturn: StepResponse {inventory, demand, rl_action, reward, health, day}"]:::deploy
        DP2["POST /deploy/override\nBody: {run_id, override_qty}\nReturn: {accepted: true}"]:::deploy
        DP3["GET  /deploy/status/{run_id}\nReturn: KPIResponse {total_reward, fill_rate, stockout_days, avg_inventory}"]:::deploy
    end

    subgraph MultiSKU["Multi-SKU API"]
        M1["POST /multi/train-all\nBody: {sku_list, episodes, ...shared hyperparams}\nReturn: [{sku, run_id}]"]:::multi
        M2["GET  /multi/status\nBody: {run_ids: []}\nReturn: [{sku, run_id, episode, reward, status}]"]:::multi
    end

    BE --> Demand
    BE --> Training
    BE --> Evaluation
    BE --> Deployment
    BE --> MultiSKU
```

---

## Node.js Frontend Server (port 3000)

```mermaid
flowchart TD
    classDef auth    fill:#1e3a5f,stroke:#4a90d9,color:#e8f4fd
    classDef proxy   fill:#1a3a2a,stroke:#4caf50,color:#e8f7ed
    classDef webhook fill:#3b1f0a,stroke:#ff8c00,color:#fff5e6

    FE["Node.js Express /api"]

    subgraph Auth["Auth Routes (Frontend/server/auth.ts)"]
        A1["POST /api/auth/register\nBody: {email, password, name}\nReturn: {user, session}"]:::auth
        A2["POST /api/auth/login\nBody: {email, password}\nReturn: {user, session}"]:::auth
        A3["POST /api/auth/logout\nReturn: {ok: true}"]:::auth
        A4["GET  /api/auth/me\nReturn: {user} or 401"]:::auth
    end

    subgraph Proxy["Backend Proxy Routes (Frontend/server/routes.ts)"]
        P1["ALL /api/demand/*\nProxy → FastAPI :8000/api/demand/*"]:::proxy
        P2["ALL /api/train/*\nProxy → FastAPI :8000/api/train/*"]:::proxy
        P3["ALL /api/evaluate/*\nProxy → FastAPI :8000/api/evaluate/*"]:::proxy
        P4["ALL /api/deploy/*\nProxy → FastAPI :8000/api/deploy/*"]:::proxy
        P5["ALL /api/multi/*\nProxy → FastAPI :8000/api/multi/*"]:::proxy
    end

    subgraph Webhooks["Webhook Routes (Frontend/server/webhook_routes.ts)"]
        W1["POST /api/webhooks/resend\nResend email delivery events"]:::webhook
    end

    FE --> Auth
    FE --> Proxy
    FE --> Webhooks
```

---

## WebSocket Event Schemas

### EpisodeEvent
```json
{ "type": "episode", "run_id": 42, "sku": "SKU-A",
  "episode": 237, "reward": 1842.5, "epsilon": 0.42, "best_eval": 2011.0 }
```

### CompletedEvent
```json
{ "type": "completed", "run_id": 42, "sku": "SKU-A",
  "best_reward": 2011.0, "model_path": "/app/storage/sku_a_run42.pt" }
```

### ErrorEvent
```json
{ "type": "error", "run_id": 42, "sku": "SKU-A", "message": "OOM during training" }
```

---

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2026-06-03 | Initial API contracts diagram — derived from app.py + schemas.py + routes.ts | @sujaynimmagadda |
