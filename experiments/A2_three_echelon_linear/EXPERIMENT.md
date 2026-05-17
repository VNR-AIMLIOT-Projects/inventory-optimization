# Experiment A2 — Three-Echelon Linear Supply Chain

**Branch:** `experiments/multi-echelon-research`  
**Status:** 🟡 In Progress  
**Depends on:** A1 (extends 2-echelon to 3-echelon)

---

## 1. What's New vs A1

A1 tested two echelons (Warehouse → Retailer). A2 adds a **Distribution Centre (DC)** in
the middle, creating a three-stage serial chain:

```
[Experiment A2]
  Supplier(∞) ──[L1=4d]──► Warehouse(E1) ──[L2=2d]──► DC(E2) ──[L3=1d]──► Retailer(E3) ──► Demand
                                 ↑                      ↑              ↑
                           warehouse order          DC order      retailer order
                                └──────────────────────┴──────────────┘
                                            Joint DDQN Agent
                                       (single agent, 7³=343 joint actions)
```

Key additions:
- **Third echelon** (DC) buffers between warehouse and retailer
- Action space grows to **7³ = 343** (7 levels per node × 3 nodes)
- State grows to **13 dims** covering all three nodes
- Longer total lead time (L1+L2+L3 = 7 days) → harder coordination

---

## 2. Research Hypothesis

> **H1 (Scale):** A joint DDQN agent can coordinate a 3-echelon system and still beat
> independent single-echelon baselines, showing the approach scales beyond 2-echelon.

> **H2 (Bullwhip cascade):** Adding a third echelon amplifies the bullwhip effect under
> (s,S) policy (cascade effect), while the joint DDQN suppresses it at all three levels.

> **H3 (Cost vs complexity):** The marginal cost reduction from A1→A2 is smaller than
> A1 baseline improvement, showing diminishing returns as topology complexity grows.

---

## 3. MDP Formulation

### 3.1 Topology

| Node | Symbol | Echelon | Lead Time | Supplier |
|------|--------|---------|-----------|---------|
| Warehouse | E1 | 1 (most upstream) | L1 = 4 days | Infinite supplier |
| Distribution Centre | E2 | 2 (middle) | L2 = 2 days | Warehouse stock |
| Retailer | E3 | 3 (downstream) | L3 = 1 day | DC stock |

### 3.2 State Space (13 dims)

```
s_t = [
    # Echelon 1 — Warehouse (3 dims)
    norm_inv_E1,         log-normalized warehouse on-hand stock
    norm_pipeline_E1,    in-transit from supplier to E1
    norm_backlog_E2,     unfilled DC orders at E1

    # Echelon 2 — Distribution Centre (3 dims)
    norm_inv_E2,         log-normalized DC on-hand stock
    norm_pipeline_E2,    in-transit from E1 to E2
    norm_backlog_E3,     unfilled retailer orders at E2

    # Echelon 3 — Retailer (3 dims)
    norm_inv_E3,         log-normalized retailer on-hand stock
    norm_pipeline_E3,    in-transit from E2 to E3
    norm_backlog_cust,   unmet customer demand

    # Shared context (4 dims)
    norm_demand_prev,
    norm_demand_ma3,
    day_sin, day_cos
]
```

**Total state dimension: 13**

### 3.3 Action Space

```
a_t = (a_E1, a_E2, a_E3)   — 3-way Cartesian product
7 × 7 × 7 = 343 joint actions
```

### 3.4 Reward

$$R_t = -\bigl[ h_1 I_{E1}^+ + h_2 I_{E2}^+ + h_3 I_{E3}^+ + b_3 B_{E3} + c_1\mathbb{1}[a_1>0] + c_2\mathbb{1}[a_2>0] + c_3\mathbb{1}[a_3>0] \bigr]$$

Holding costs decrease upstream (warehouse carries cheaper bulk), stockout only at E3.

### 3.5 Cost Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| h_E1 (holding, WH) | 1.0 | Bulk storage, cheapest |
| h_E2 (holding, DC) | 3.0 | Intermediate storage |
| h_E3 (holding, Retailer) | 5.0 | Premium retail shelf space |
| b_E3 (stockout penalty) | 500 | Same as A1-v2 (tuned) |
| c_E1, c_E2, c_E3 (order fixed) | 2.0 each | Tuned (was 10 in A1, caused under-ordering) |
| L1, L2, L3 | 4, 2, 1 | Realistic warehouse → DC → store |

---

## 4. Baselines

| Baseline | Description |
|----------|-------------|
| **(s,S) Independent** | Three independent (s,S) policies, one per node |
| **Oracle (7-day)** | Knows next 7 days demand (matches total lead time L1+L2+L3) |
| **Independent DDQN** | Three separate DDQN agents, no shared state |

---

## 5. Key Differences from A1

| Aspect | A1 (2-echelon) | A2 (3-echelon) |
|--------|---------------|---------------|
| Nodes | 2 | 3 |
| State dims | 10 | 13 |
| Action space | 11×11=121 | 7×7×7=343 |
| Total lead time | L_W+L_R = 4d | L1+L2+L3 = 7d |
| Tuned b_R | 100 | **500** |
| Tuned c_order | 10 | **2** |

---

## 6. How to Run

```bash
cd experiments/A2_three_echelon_linear
python3 run_experiment.py           # 500 episodes, all baselines (~25 min)
python3 run_experiment.py --smoke-test  # 50 episodes quick check
```
