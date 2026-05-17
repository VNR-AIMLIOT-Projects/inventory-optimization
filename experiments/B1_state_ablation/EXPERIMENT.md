# Experiment B1 — State Representation Ablation

**Branch:** `experiments/multi-echelon-research`  
**Status:** 🟡 In Progress  
**Depends on:** A1 (uses the same 2-echelon environment)

---

## 1. Motivation

A1 showed that a joint DDQN agent achieves a very low bullwhip ratio but suffered from
low service level due to warehouse under-stocking. A natural question is:

> **Does the agent under-stock because it doesn't have enough information about the
> supply chain's downstream state?**

B1 directly tests this by comparing two different **state representations** on the
*identical* A1 environment (2-echelon, same demand, same costs):

---

## 2. The Two State Representations

### Variant 1: Installation Stock (IS) State
*What A1 used.* Each node observes only its own on-hand inventory.

```
State = [inv_W, pipeline_W, inv_R, pipeline_R, backlog_R,
         demand_prev, demand_ma3, day_sin, day_cos, promo]
```
→ **10 dims**. The warehouse doesn't know how much stock the retailer currently has.

### Variant 2: Echelon Stock (ES) State
Each node's state includes **total system stock downstream of it**.

Echelon stock concept:
```
Echelon_stock_W = inv_W + pipeline_W_to_R + inv_R   (WH "owns" all downstream)
Echelon_stock_R = inv_R                              (Retailer owns only its own)
```

```
State = [norm_echelon_W, norm_pipeline_W, norm_echelon_R, norm_pipeline_R,
         norm_backlog_R, norm_demand_prev, norm_demand_ma3,
         day_sin, day_cos, promo]
```
→ **10 dims** (same size, but richer semantics — WH sees total downstream coverage).

---

## 3. Research Hypothesis

> **H1:** Echelon Stock (ES) state achieves higher service level than Installation
> Stock (IS) state because the warehouse can observe total downstream coverage and
> order more proactively.

> **H2:** ES and IS achieve similar bullwhip ratio, since the ordering smoothness is
> determined by the joint policy structure, not the state representation alone.

> **H3:** ES converges faster (fewer episodes to reach stable service level) because
> the state is more informative about the global supply chain position.

---

## 4. Why This Matters for the Research Paper

Echelon stock vs installation stock is a **classical debate** in multi-echelon
inventory theory (Clark & Scarf 1960, Chen 1998). Our RL experiment provides an
empirical data point: which representation leads to better RL policy learning?

If ES wins on service level (H1 confirmed), this suggests RL agents benefit from the
same global information that analytical optimal policies require — a connection between
classical theory and modern RL.

---

## 5. Experiment Design

| Aspect | IS Variant | ES Variant |
|--------|-----------|-----------|
| Environment | A1 TwoEchelonEnv | A1 TwoEchelonEnv |
| State type | Installation stock | Echelon stock |
| State dims | 10 | 10 |
| Episodes | 500 | 500 |
| All other params | Identical (b_R=500, c_W=2, c_R=2) | Identical |
| Seeds | Same train/val/test seeds | Same |

Both variants use the **tuned A1 config** (b_R=500, c_W=2 — the fixes identified
from the A1 post-mortem).

---

## 6. How to Run

```bash
cd experiments/B1_state_ablation
python3 run_experiment.py          # 2× 500 episodes (~35 min)
python3 run_experiment.py --smoke-test
```

Outputs include separate metrics files for IS and ES, plus a head-to-head
comparison plot.
