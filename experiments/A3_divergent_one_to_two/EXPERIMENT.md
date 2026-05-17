# Experiment A3 — Divergent Supply Chain (1 Warehouse → 2 Retailers)

**Branch:** `experiments/multi-echelon-research`  
**Status:** 🟡 In Progress  
**Depends on:** A1 (extends to divergent topology)

---

## 1. Topology

A3 tests a **divergent** (one-to-many) supply chain — one warehouse serving two
independent retailers with different demand profiles:

```
[Experiment A3]
                    ──[L_R=1d]──► Retailer 1 (Summer demand) ──► Customer 1
  Supplier(∞) ──[L_W=3d]──► Warehouse ─┤
                    ──[L_R=1d]──► Retailer 2 (Offset demand)  ──► Customer 2
                         ↑            ↑             ↑
                     WH order     R1 order       R2 order
                         └────────────┴─────────────┘
                                Joint DDQN Agent
                            (7 × 7 × 7 = 343 actions)
```

Key challenge: the warehouse has **finite stock** shared across two competing retailers.
When demand spikes at both retailers simultaneously, the agent must decide how to
prioritise allocation — a problem that doesn't exist in serial chains.

---

## 2. Research Hypothesis

> **H1 (Shared resource):** A joint DDQN agent outperforms two independent DDQN agents
> by explicitly coordinating warehouse allocation between the two retailers, reducing
> total system backorder cost.

> **H2 (Asymmetric demand):** The joint agent learns to prioritise the retailer with
> higher current backlog risk, demonstrating demand-aware allocation — something a
> static (s,S) policy cannot do.

> **H3 (Bullwhip divergence):** In a divergent topology, the bullwhip effect is less
> severe than serial chains because both retailers' demand partially cancels upstream,
> and the joint agent exploits this.

---

## 3. MDP Formulation

### 3.1 Demand Profiles

Retailer 1 and Retailer 2 use **different demand seeds** to simulate geographic or
demographic variation:

| Retailer | Seed offset | Effective pattern |
|----------|-------------|-------------------|
| R1 | base | Standard summer demand |
| R2 | base + 500 | Offset summer demand (different random walk) |

Both use the same `generate_demand("summer")` logic — same seasonality and festivals,
but different stochastic realisations. This creates realistic asynchronous demand.

### 3.2 State Space (13 dims)

```
s_t = [
    # Warehouse (2 dims)
    norm_inv_W,          log-normalized warehouse stock
    norm_pipeline_W,     in-transit from supplier

    # Retailer 1 (3 dims)
    norm_inv_R1,         log-normalized R1 stock
    norm_pipeline_R1,    in-transit from WH to R1
    norm_backlog_R1,     R1 customer backlog

    # Retailer 2 (3 dims)
    norm_inv_R2,         log-normalized R2 stock
    norm_pipeline_R2,    in-transit from WH to R2
    norm_backlog_R2,     R2 customer backlog

    # Demand context (5 dims)
    norm_demand_prev_R1, last period R1 demand
    norm_demand_prev_R2, last period R2 demand
    norm_demand_ma3_R1,  3-day MA R1
    day_sin, day_cos     cyclic weekday
]
```

**Total state dimension: 13**

### 3.3 Action Space

```
a_t = (a_W, a_R1, a_R2)   — 3-way Cartesian product
7 × 7 × 7 = 343 joint actions
```

`a_W` = warehouse replenishment order  
`a_R1` = R1's order to warehouse  
`a_R2` = R2's order to warehouse  

Warehouse fulfils R1 and R2 proportionally when stock is insufficient:
```
if inv_W >= a_R1 + a_R2:  # can fill both
    ship_R1 = a_R1; ship_R2 = a_R2
else:                      # proportional rationing
    total = a_R1 + a_R2
    ship_R1 = int(inv_W * a_R1 / total)
    ship_R2 = inv_W - ship_R1
```

### 3.4 Reward

$$R_t = -\bigl[ h_W I_W^+ + h_R(I_{R1}^+ + I_{R2}^+) + b_R(B_{R1} + B_{R2}) + c_W\mathbb{1}[a_W>0] + c_R(\mathbb{1}[a_{R1}>0] + \mathbb{1}[a_{R2}>0]) \bigr]$$

Cost parameters: h_W=2, h_R=5, b_R=500, c_W=2, c_R=2 (same tuned config as A2).

---

## 4. Baselines

| Baseline | Description |
|----------|-------------|
| **(s,S) Independent** | Each retailer orders independently; warehouse orders from sum of retailer orders |
| **Oracle (5-day)** | Knows 5 days ahead for both retailers |
| **Independent DDQN** | R1 agent and R2 agent trained separately; warehouse uses (s,S) |

---

## 5. Key Unique Challenge: Inventory Rationing

When warehouse stock is **insufficient** to fill both retailers, the rationing strategy
becomes critical. Under (s,S), both retailers simply get partial fills pro-rata.
The joint DDQN must learn:
1. When to prioritise R1 vs R2 (based on backlog state)
2. How much to order to avoid rationing situations entirely
3. That ordering less today (lower holding cost) may cause rationing tomorrow

This creates a qualitatively harder credit assignment problem than A1 or A2.

---

## 6. How to Run

```bash
cd experiments/A3_divergent_one_to_two
python3 run_experiment.py            # 500 episodes, all baselines (~25 min)
python3 run_experiment.py --smoke-test
```
