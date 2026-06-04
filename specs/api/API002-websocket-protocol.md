# Spec API002 — WebSocket Protocol

**ID**: SPEC-API002
**Status**: Done
**Type**: API
**Author**: @sujaynimmagadda
**Created**: 2026-06-03
**Linked Diagram**: [diagrams/06-rabbitmq-message-flow.md](../../diagrams/06-rabbitmq-message-flow.md)
**Source Files**: `Backend-RL/src/app.py` (WSMgr), `Frontend/client/src/` (useTrainingWebSocket)

---

## Summary

Canonical reference for the WebSocket protocol used for real-time training progress delivery from the backend to the React frontend during Stage 3 RL Training.

---

## Connection

**Endpoint**: `ws://localhost:8000/ws/training` (dev) | `ws://$BACKEND_HOST/ws/training` (prod)

**Connect timing**: Client connects immediately after `POST /train` returns `run_id`

**Reconnection**: Client should implement exponential backoff reconnect (1s, 2s, 4s, max 30s)

---

## Server → Client Messages

All messages are JSON strings. The `type` field is the discriminator.

### `episode` — Per-episode training update
Sent after every training episode completes.

```json
{
  "type": "episode",
  "run_id": 42,
  "sku": "SKU-A",
  "episode": 237,
  "total_episodes": 500,
  "reward": 1842.5,
  "epsilon": 0.42,
  "best_eval": 2011.0
}
```

### `completed` — Training finished successfully
Sent once when a training run finishes all episodes.

```json
{
  "type": "completed",
  "run_id": 42,
  "sku": "SKU-A",
  "total_episodes": 500,
  "best_reward": 2011.0,
  "model_path": "/app/storage/sku_a_run42.pt"
}
```

### `error` — Training failed
Sent if a worker crashes or encounters an unrecoverable error.

```json
{
  "type": "error",
  "run_id": 42,
  "sku": "SKU-A",
  "episode": 237,
  "message": "CUDA out of memory"
}
```

### `heartbeat` — Keep-alive ping
Sent every 30 seconds to prevent connection timeout.

```json
{ "type": "heartbeat", "timestamp": "2024-03-15T10:30:00Z" }
```

---

## Client → Server Messages

Currently none — this is a unidirectional push channel. The client only listens.

---

## Frontend Handling

```typescript
// Pseudocode for useTrainingWebSocket hook
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case 'episode':    updateRewardChart(msg); updateEpsilonBar(msg); break;
    case 'completed':  setStatus('done'); showSuccessBanner(msg); break;
    case 'error':      setStatus('failed'); showErrorBanner(msg.message); break;
    case 'heartbeat':  // ignore, connection is alive
  }
};
```

---

## Multi-SKU Handling

When training multiple SKUs simultaneously, the same WebSocket connection receives events for all active runs. The frontend must filter by `run_id` to route events to the correct progress card:

```typescript
// Route to correct SKU card by run_id
const card = skuCards.find(c => c.runId === msg.run_id);
if (card) card.update(msg);
```

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-03 | @sujaynimmagadda | Initial WebSocket protocol spec |
