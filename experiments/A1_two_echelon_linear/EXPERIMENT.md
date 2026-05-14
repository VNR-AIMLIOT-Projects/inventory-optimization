# Experiment A1: Two-Echelon Linear Supply Chain — Joint DDQN

**Branch:** `experiment/A1-two-echelon-linear-ddqn`  
**Status:** 🟡 In Progress  
**Started:** 2026-05-14  
**Author:** Sujay Nimmagadda

---

## 1. Context & Motivation

### Where We Are (Replenix `dev`)

The current production Replenix system is a **single-echelon, multi-SKU** inventory optimizer:

```
[Replenix on dev]
  Supplier (infinite / assumed) ──► Retailer Node ──► Customer Demand
                                       ↑
                                    DDQN Agent
                                  (one per SKU)
```

Each SKU has its own independently trained DDQN agent that sees only *its own* inventory,
pipeline orders, and demand. There is **no supplier inventory modelling** — the upstream is
treated as always-available.

### What A1 Adds

A1 introduces a **Warehouse node** between the supplier and the retailer:

```
[Experiment A1]
  Supplier (infinite) ──► Warehouse Node ──► Retailer Node ──► Customer Demand
                               ↑                  ↑
                         warehouse order      retailer order
                               └──────────────────┘
                                   Joint DDQN Agent
                              (single agent, joint state)
```

Key differences:
- The **retailer** can only order from the warehouse (not the infinite supplier directly).
- The **warehouse** orders from the infinite supplier.
- A **single joint DDQN agent** decides both orders simultaneously.
- The **joint state** includes both nodes' inventories, pipelines, and backlogs.

---

## 2. Research Hypothesis

> **H1 (Primary):** A joint DDQN agent with a shared observation of the full 2-echelon
> system achieves lower total system cost than two independent single-echelon DDQN agents
> (one per node) that cannot observe each other's state.

> **H2 (Secondary):** The joint agent exhibits a measurably lower **Bullwhip Ratio**
> (variance of warehouse orders / variance of retailer demand), demonstrating that
> coordinated decision-making dampens demand amplification upstream.

---

## 3. MDP Formulation

### 3.1 Nodes

| Node | Symbol | Role | Supplier |
|------|--------|------|---------|
| Warehouse | W | Echelon 1 (upstream) | Infinite external supplier (L_W day lead time) |
| Retailer | R | Echelon 2 (downstream) | Warehouse stock only |

### 3.2 State Space

At each time step `t`, the agent observes a flat vector:

```
s_t = [
    # Warehouse node (3 dims)
    norm_inv_W,          # log-normalized on-hand inventory at W
    norm_pipeline_W,     # in-transit orders TO W (from supplier)
    norm_backlog_R,      # unfulfilled retailer demand (R's backlog, visible to W)

    # Retailer node (3 dims)
    norm_inv_R,          # log-normalized on-hand inventory at R
    norm_pipeline_R,     # in-transit orders FROM W TO R
    norm_demand_prev,    # last period's actual demand (normalized)

    # Shared context (4 dims)
    norm_demand_forecast,# 3-day rolling average demand (normalized)
    day_of_week_sin,     # cyclic encoding of weekday (sin component)
    day_of_week_cos,     # cyclic encoding of weekday (cos component)
    promo_flag           # 0/1 upcoming festival/promo window
]
```

**Total state dimension: 10**  
(vs. 14-dim in Replenix single-echelon — leaner because we encode weekday cyclically)

### 3.3 Action Space

The agent outputs a **joint discrete action**:
```
a_t = (a_W, a_R)   — a Cartesian product
```

| Variable | Range | Discretization |
|----------|-------|----------------|
| `a_W` (warehouse order qty) | [0, MAX_W] | N_W = 11 levels |
| `a_R` (retailer order qty)  | [0, MAX_R] | N_R = 11 levels |

Total joint actions: **11 × 11 = 121**

`MAX_W` and `MAX_R` are auto-computed from demand statistics (same `_compute_adaptive_params` logic as Replenix), but independently scaled per node.

### 3.4 Reward Function

$$R_t = -\left[ h_W \cdot I_W^+ + h_R \cdot I_R^+ + b_R \cdot B_R + c_W \cdot \mathbb{1}[a_W > 0] + c_R \cdot \mathbb{1}[a_R > 0] \right]$$

Where:
- `I_W+` = on-hand inventory at W (holding cost)
- `I_R+` = on-hand inventory at R (holding cost)
- `B_R`  = backlog at R (stockout penalty — only end customers are penalized)
- `c_W, c_R` = fixed order costs (applied if any order is placed)

**No stockout penalty at W** — warehouse backorders simply delay retailer replenishment.

### 3.5 Inventory Dynamics (per period)

**Warehouse (each step):**
```
1. Receive: I_W += pipeline_W.popleft()
2. Fulfill:  shipped_to_R = min(a_R_prev, I_W)   # retailer's requested qty
3. Backlog:  B_W += max(0, a_R_prev - I_W)        # if W can't fill R's order
4. Update:   I_W -= shipped_to_R
5. Order:    pipeline_W.append(a_W)
```

**Retailer (each step):**
```
1. Receive:  I_R += shipped_to_R  (from warehouse this period)
2. Fulfill:  units_sold = min(demand_t, I_R)
3. Backlog:  B_R = max(0, demand_t - I_R)
4. Update:   I_R -= units_sold
5. Order:    pipeline_R.append(a_R)   (requested, may be partially filled)
```

### 3.6 Lead Times

| Link | Lead Time (days) | Notes |
|------|-----------------|-------|
| Supplier → Warehouse | L_W = 3 | Fixed, deterministic |
| Warehouse → Retailer | L_R = 1 | Fixed, deterministic (next-day delivery) |

---

## 4. Baselines

Three baselines will be run on the **identical** synthetic demand stream:

| Baseline | Description |
|----------|-------------|
| **Independent DDQN** | Two separate single-echelon DDQN agents (Replenix-style), no shared state |
| **(s,S) Policy** | Classical reorder-point / order-up-to policy with analytically derived parameters |
| **Oracle (5-day lookahead)** | Cheating agent that knows future demand for 5 days (upper bound on performance) |

---

## 5. Evaluation Metrics

| Metric | Formula | Goal |
|--------|---------|------|
| **Total System Cost** (primary) | `sum(holding + backorder + order_fixed)` | Minimize |
| **Service Level** | `1 - (total_backlog / total_demand)` | Maximize (>95%) |
| **Bullwhip Ratio** | `Var(warehouse_orders) / Var(retailer_demand)` | Minimize (<1.5 ideal) |
| **Order Fill Rate** | `retailer_orders_filled / retailer_orders_placed` | Maximize |
| **Avg Inventory (W+R)** | Average total system stock | Minimize |
| **Training Convergence** | Episodes to reach stable eval reward | Faster = better |

---

## 6. Experimental Configuration

```python
# demand
SEASON_TYPE  = "summer"   # uses Replenix generate_demand() directly
NUM_DAYS     = 365        # one year per episode
TRAIN_SEED   = range(1000, 1500)  # 500 episodes × different seeds
VAL_SEED     = 777
TEST_SEED    = 999

# environment
L_W          = 3     # warehouse lead time
L_R          = 1     # retailer lead time
h_W          = 2     # warehouse holding cost (lower — it's a bulk warehouse)
h_R          = 5     # retailer holding cost (matches Replenix)
b_R          = 100   # retailer stockout penalty (matches Replenix)
c_W          = 10    # warehouse order fixed cost
c_R          = 10    # retailer order fixed cost

# agent
EPISODES     = 500
BATCH_SIZE   = 256
GAMMA        = 0.98
TAU          = 0.005
LR           = 1e-4
EPSILON_START= 1.0
EPSILON_MIN  = 0.05
DECAY_TYPE   = "exponential"
N_ACTIONS_W  = 11   # discrete levels for warehouse
N_ACTIONS_R  = 11   # discrete levels for retailer
```

---

## 7. File Structure

```
experiments/A1_two_echelon_linear/
├── EXPERIMENT.md              ← THIS FILE (design doc)
├── env_two_echelon.py         ← 2-echelon environment (NEW, isolated)
├── run_experiment.py          ← training + evaluation runner
├── baselines.py               ← (s,S), Oracle, Independent-DDQN baselines
├── metrics.py                 ← metric computation helpers
├── results/
│   ├── experiment_log.jsonl   ← per-episode metrics (written during run)
│   └── summary.json           ← final aggregated results
└── plots/
    ├── training_curve.png
    ├── inventory_trajectory.png
    ├── bullwhip_comparison.png
    └── cost_breakdown.png
```

> **⚠️ ISOLATION GUARANTEE:** No file in `experiments/` imports from or modifies
> `Backend-RL/src/`. The experiment copies/adapts only the algorithms it needs.
> The production Replenix system on `dev` is untouched.

---

## 8. Expected Results (Pre-Experiment Hypothesis)

Based on Geevers et al. (2024) and general RL supply chain literature:

| Agent | Expected Cost Reduction vs (s,S) |
|-------|----------------------------------|
| Independent DDQN | ~5–8% |
| **Joint DDQN (A1)** | **~10–16%** |
| Oracle | ~20–25% (upper bound) |

Expected Bullwhip Ratio:
- (s,S): 1.8–2.5 (high amplification)
- Independent DDQN: 1.5–2.0
- **Joint DDQN: 1.0–1.4** (coordinated, lower amplification)

---

## 9. How to Run

```bash
# From repo root, on experiment/A1-two-echelon-linear-ddqn branch:
cd experiments/A1_two_echelon_linear

# Install dependencies (uses existing Backend-RL requirements)
pip install torch numpy pandas matplotlib

# Run full experiment (500 episodes, all baselines, all plots)
python run_experiment.py

# Quick smoke test (50 episodes, no baselines)
python run_experiment.py --episodes 50 --smoke-test

# View summary results
cat results/summary.json
```

---

## 10. Next Experiments (Roadmap)

| Branch | Experiment | Depends On |
|--------|-----------|-----------|
| `experiment/A1-...` (this) | 2-echelon Joint DDQN | — |
| `experiment/A2-three-echelon` | 3-echelon + PPO comparison | A1 results |
| `experiment/A3-divergent` | 1 warehouse → 3 retailers, shared policy | A1 |
| `experiment/B1-ddqn-vs-ppo` | Algorithm ablation on same A1 env | A1 |
| `experiment/D1-xai-echelon` | SHAP on multi-echelon policy | A2/B1 |
