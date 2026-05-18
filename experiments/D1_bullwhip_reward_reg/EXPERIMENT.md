# Experiment D1 — Bullwhip Reward Regularisation

**Branch:** `experiments/multi-echelon-research`
**Status:** 🟡 Designed — Ready to Run
**Depends on:** A1-v2 (same env; modifies only reward function)

---

## 1. Motivation

In experiments A1–A3, the Joint DDQN consistently achieves **higher Bullwhip Ratio
than the (s,S) baseline** (A1: BW=2.138 vs (s,S) BW=1.054). The agent optimises cost
and service level, but places highly variable upstream orders as a side-effect.

In real supply chains, high bullwhip creates:
- Supplier capacity planning problems
- Excess production at manufacturer level
- Margin erosion from emergency orders

The literature (Lee et al., 1997) established bullwhip as a key supply chain KPI,
but no DRL paper has directly penalised bullwhip in the reward function.

**Research Question:** Can adding a bullwhip penalty term λ·BW to the reward reduce
upstream order variance without sacrificing service level?

---

## 2. Topology

Identical to A1-v2 (2-echelon, Warehouse → Retailer):

```
[Experiment D1]
  Supplier(∞) ──[L_W=3d]──► Warehouse ──[L_R=1d]──► Retailer ──► Seasonal Demand

  Reward = Standard Cost + λ × Bullwhip Penalty Term
  Three variants: λ ∈ {0.01, 0.1, 0.5}
  Plus control: λ = 0 (identical to A1-v2)
```

---

## 3. Research Hypotheses

> **H1 (Bullwhip reduction):** Higher λ directly reduces Bullwhip Ratio, with
> λ=0.5 achieving BW closer to 1.0 than λ=0 (our A1 result of 2.138).

> **H2 (Service level trade-off):** Higher λ causes service level degradation because
> the agent learns to order less variably but undershoots peak-demand periods.

> **H3 (Sweet spot):** λ=0.1 provides the best balance: BW below 1.5 with
> service level above 93%, outperforming both (s,S) and λ=0 on cost efficiency.

> **H4 (Cost neutrality):** The total cost difference between λ=0 and λ=0.1 is
> less than 5%, meaning bullwhip reduction is nearly "free" at low λ.

---

## 4. Reward Formulation

### 4.1 Standard Reward (λ=0, baseline = A1-v2)
```
R_t = -(h_W·I_W + h_R·I_R + b_R·B_R + c_W·1[a_W>0] + c_R·1[a_R>0])
```

### 4.2 Bullwhip-Regularised Reward
```
R_t = -(h_W·I_W + h_R·I_R + b_R·B_R + c_W·1[a_W>0] + c_R·1[a_R>0])
      - λ · |a_W(t) - a_W(t-1)|   ← order smoothness penalty
```

The bullwhip penalty is **order-change magnitude** (|Δa_W|) rather than the
variance-ratio (which is only computable at episode end). This provides:
- Step-level gradient signal for the agent
- Directly penalises sudden order spikes
- Mathematically equivalent to L1 regularisation on order changes

### 4.3 Lambda Sweep
| Run | λ | Description |
|-----|---|-------------|
| D1-λ0 | 0.00 | Control (= A1-v2, no regularisation) |
| D1-λ1 | 0.01 | Weak smoothing |
| D1-λ2 | 0.10 | Moderate smoothing |
| D1-λ3 | 0.50 | Strong smoothing |

---

## 5. Cost Parameters

Identical to A1-v2: h_W=2, h_R=5, b_R=500, c_W=2, c_R=10, L_W=3, L_R=1.

The λ penalty is added ON TOP of existing costs — it does not replace them.

---

## 6. Metrics

| Metric | Why it Matters |
|--------|---------------|
| **Bullwhip Ratio** | Primary outcome: does regularisation work? |
| **Service Level** | Trade-off check: do we lose SL for BW gains? |
| **Avg Order Std Dev** | More interpretable than BW ratio for practitioners |
| **Total Episode Cost** | Check λ does not inflate nominal cost |
| **Convergence Episode** | Does regularisation slow or speed learning? |

### 6.1 Pareto Analysis
We plot **BW Ratio vs Service Level** as a 2D scatter across all λ values.
The ideal agent sits in the bottom-right corner (low BW, high SL).

---

## 7. Expected Outputs

```
D1_bullwhip_reward_reg/
├── EXPERIMENT.md
├── RESULTS.md
├── run_experiment.py       ← Trains 4 variants (λ=0,0.01,0.1,0.5)
├── results/
│   ├── config.json
│   ├── summary.json        ← λ vs [SL, BW, Cost, Conv. ep.]
│   └── experiment_log.jsonl
└── plots/
    ├── training_curves_all_lambda.png  ← 4 learning curves overlaid
    ├── bw_vs_sl_pareto.png             ← 2D Pareto scatter
    ├── order_variance_comparison.png   ← Warehouse order std dev vs λ
    └── cost_comparison.png             ← Total cost vs λ (bar chart)
```

---

## 8. How to Run

```bash
cd experiments/D1_bullwhip_reward_reg
python3 run_experiment.py              # Full run, 500 eps per lambda
python3 run_experiment.py --smoke-test # 50 eps per lambda (~12 min)
```

---

## 9. Literature Gap Closed

No DRL inventory paper penalises bullwhip explicitly in the reward function.
Lee et al. (1997) show BW is a first-class KPI; Gijsbrechts et al. (2022) only
report BW post-hoc; neither attempts to control it via reward shaping.

This experiment is the **first empirical test of bullwhip reward regularisation**
in a seasonal multi-echelon DRL system. The λ-sweep provides the foundation
for choosing the right regularisation level for any real production deployment.
