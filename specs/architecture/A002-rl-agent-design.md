# Spec A002 — RL Agent Design

**ID**: SPEC-A002
**Status**: Done
**Type**: Architecture
**Author**: @sujaynimmagadda
**Created**: 2026-06-03
**Linked Diagram**: [diagrams/02-rl-agent-dataflow.md](../../diagrams/02-rl-agent-dataflow.md)
**Source Files**: `Backend-RL/src/dqn.py`, `Backend-RL/src/environment.py`, `Backend-RL/src/trainer.py`

---

## Summary

Documents the design decisions for the DQN-based RL agent used for inventory replenishment optimization. This is the canonical reference for understanding state space, action space, reward function, and network architecture choices.

---

## State Space (15 dimensions)

| Index | Feature | Normalization |
|-------|---------|---------------|
| 0 | Current inventory level | log-normalized |
| 1 | Last period demand | normalized by max demand |
| 2 | Last order quantity | normalized by max order |
| 3 | Pipeline inventory (in-transit) | normalized |
| 4–10 | Day-of-week (7-hot encoding) | binary |
| 11 | Seasonal progress (0.0–1.0) | raw |
| 12 | Promotional flag | binary |
| 13 | Days since last order | normalized |
| 14 | Stockout indicator | binary |

---

## Action Space

Discrete action space. Each action index maps to an order quantity:
```
action_index * action_step = order_quantity
```
Example: `action_step=10`, `max_order=100` → 11 actions (0, 10, 20, ..., 100)

---

## Reward Function

```
R_t = p × sales_t - h × inventory_t - c_s × lost_sales_t - f × (1 if ordered)
```

| Symbol | Meaning | Default |
|--------|---------|---------|
| `p` | Revenue per unit sold | 10.0 |
| `h` | Holding cost per unit per day | configurable |
| `c_s` | Stockout penalty per lost unit | configurable |
| `f` | Fixed ordering cost | 5.0 |

Rewards are normalized at sample time using Welford's online algorithm (running mean/std over the replay buffer).

---

## Network Architecture

```
Input (15) → Linear(512) → ReLU → Linear(512) → ReLU → Linear(256) → ReLU → Linear(|actions|)
```

Two networks: `policy_net` (trained) and `target_net` (Polyak-updated).

---

## Training Algorithm: Double DQN

```
a* = argmax_a Q_policy(s', a)           # action selection from policy net
y  = r + γ × Q_target(s', a*)           # value estimation from target net
loss = HuberLoss(Q_policy(s, a), y)
```

Prevents overestimation bias vs. vanilla DQN.

---

## Key Hyperparameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Replay buffer capacity | 100,000 | Sufficient diversity without memory pressure |
| Batch size | 256 | Balance between gradient quality and speed |
| Learning rate | 1e-4 | Conservative for stable convergence |
| Gamma (discount) | 0.99 | Long-horizon inventory planning |
| Polyak tau | 0.005 | Slow target network update = stability |
| Epsilon start | 1.0 | Full exploration initially |
| Epsilon end | 0.05 | 5% exploration maintained permanently |
| Epsilon decay | Linear over 75% of training | Smooth transition |
| Learn frequency | Every 4 steps | Reduce variance from single-step updates |
| Eval frequency | Every 100 episodes | Checkpoint best model |
| Grad clip norm | 1.0 | Prevent exploding gradients |

---

## Change Log

| Date | Author | Change |
|------|--------|--------|
| 2026-06-03 | @sujaynimmagadda | Initial RL agent design spec |
