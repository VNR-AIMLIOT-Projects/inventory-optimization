# Experiment B2 — Algorithm Ablation: Joint DDQN vs PPO

**Branch:** `experiments/multi-echelon-research`
**Status:** 🟡 Designed — Ready to Run
**Depends on:** A1-v2 (uses identical env, cost config, demand generator)

---

## 1. Motivation

All prior Replenix experiments (A1–B1) used **Joint Dueling Double-DQN** as the sole RL
algorithm. The literature (Gijsbrechts et al., 2022; Vanvuchelen et al., 2020) predominantly
uses **Proximal Policy Optimization (PPO)** or A3C, claiming superior performance in
complex multi-echelon settings. No paper in the literature has done a head-to-head
DDQN vs PPO comparison on **seasonal** multi-echelon demand.

**Research Question:** On a 2-echelon supply chain with seasonal demand, does PPO
outperform Joint DDQN in convergence speed, final service level, and cost?

---

## 2. Topology

Identical to A1-v2 (no change to environment):

```
[Experiment B2]
  Supplier(∞) ──[L_W=3d]──► Warehouse ──[L_R=1d]──► Retailer ──► Seasonal Demand
                                  ↑                       ↑
                        DDQN Agent (flat)          vs    PPO Agent (shared actor-critic)
                        (joint 11×11=121 actions)        (joint 121-dim output softmax)
```

Both agents see **identical**:
- Environment (A1 `TwoEchelonEnv`, b_R=500, c_W=2)
- Demand data (summer seasonal, seed=42)
- Training budget: **500 episodes**
- Evaluation: 50 independent episodes after training

---

## 3. Research Hypotheses

> **H1 (Convergence):** PPO converges faster than DDQN (fewer episodes to reach
> 90% service level), due to on-policy variance reduction with clipped surrogate objective.

> **H2 (Final Performance):** Both algorithms reach similar final service level (within ±3 pp),
> confirming that for this problem size (10-state, 121-action), algorithm choice is secondary
> to reward engineering.

> **H3 (Stability):** DDQN shows more variance across evaluation episodes due to
> off-policy instability, while PPO is more consistent (lower std dev of episode reward).

---

## 4. Algorithm Specifications

### 4.1 Joint DDQN (from `shared/dqn_agent.py`)
| Hyperparameter | Value |
|---------------|-------|
| Architecture | Dueling MLP: [128, 128] |
| Optimizer | Adam lr=1e-3 |
| Replay buffer | 50,000 transitions |
| Batch size | 256 |
| Target update (τ) | 0.01 (soft) |
| Epsilon decay | 1.0 → 0.05 over 300 eps |
| Reward normalizer | Welford online std |

### 4.2 PPO (custom implementation in `ppo_agent.py`)
| Hyperparameter | Value |
|---------------|-------|
| Architecture | Shared MLP [128,128] + separate actor/critic heads |
| Optimizer | Adam lr=3e-4 |
| Clip ratio (ε) | 0.2 |
| Entropy coefficient | 0.01 |
| GAE λ | 0.95 |
| Discount γ | 0.99 |
| Update epochs per rollout | 4 |
| Rollout length | 365 steps (1 episode) |
| Action space | Discrete softmax over 121 joint actions |

Both use **identical demand data and random seeds** for fair comparison.

---

## 5. MDP Formulation

Identical to A1-v2. See `experiments/A1_two_echelon_linear/EXPERIMENT.md`.

State: 10-dim | Actions: 121 joint | Reward: same cost function.

---

## 6. Metrics

| Metric | Description |
|--------|-------------|
| **Service Level** | 1 - (total_backlog / total_demand) over 50 eval episodes |
| **Avg Episode Cost** | Mean total cost per episode over eval |
| **Convergence Episode** | Episode at which rolling-100-ep SL first exceeds 90% |
| **Bullwhip Ratio** | Var(W orders) / Var(demand) over eval |
| **Reward Std Dev** | Std dev of episode reward over 50 eval episodes |

---

## 7. Expected Outputs

```
B2_ddqn_vs_ppo/
├── EXPERIMENT.md        ← This file
├── RESULTS.md           ← Written after run
├── ppo_agent.py         ← Custom PPO implementation
├── run_experiment.py    ← Trains both, evaluates, plots
├── results/
│   ├── config.json
│   ├── summary.json     ← Head-to-head metric table
│   └── experiment_log.jsonl
└── plots/
    ├── training_curves_comparison.png   ← DDQN vs PPO learning curves
    ├── eval_metric_comparison.png       ← Bar chart: SL, Cost, BW
    └── convergence_comparison.png       ← Episodes to 90% SL threshold
```

---

## 8. How to Run

```bash
cd experiments/B2_ddqn_vs_ppo
python3 run_experiment.py              # Full run, 500 eps each
python3 run_experiment.py --smoke-test # 50 eps each, ~5 min
```

---

## 9. Literature Gap Closed

No existing paper compares DDQN vs PPO on **seasonal multi-echelon demand** with
identical environments. This experiment directly fills the gap identified in the
literature survey (Section 5.2, Gap B2).

**Closest prior work:** Gijsbrechts et al. (2022) compare A3C vs heuristics (not vs DDQN).
Oroojlooyjadid et al. (2022) only use DQN. Neither uses seasonal demand.
