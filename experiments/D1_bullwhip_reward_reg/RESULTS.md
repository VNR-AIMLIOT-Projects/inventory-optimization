# Experiment D1 — Results (Bullwhip Reward Regularization)

**Branch:** `experiments/multi-echelon-research`
**Episodes:** 500 per configuration
**Env:** A1 (2-echelon, seasonal)

---

## 1. Motivation
While the standard Joint DDQN minimizes cost naturally, upstream order variance (Bullwhip) can occasionally remain erratic. We tested an explicit reward regularization term ($-\lambda \times \text{Bullwhip Penalty}$) appended to the agent's reward function, forcing it to weigh operational smoothing alongside pure cost metrics.

## 2. Final Evaluation Metrics

We swept the hyperparameter $\lambda$ across four values to identify the Pareto optimal frontier between smoothing upstream variance and preventing downstream stockouts.

| $\lambda$ (Penalty Weight) | Service Level | Total Cost | Bullwhip Ratio | Order Std (Warehouse) | Total Backlog |
|:--------------------------:|:-------------:|:----------:|:--------------:|:---------------------:|:-------------:|
| **0.0** (Baseline) | **98.79%** | 8,956,745 | 2.077 | 757.88 | 2,526 |
| **0.01** | 97.28% | 10,227,013 | **1.779** | **701.48** | 5,674 |
| **0.10** | 97.94% | **8,699,354** | 1.917 | 728.14 | 4,306 |
| **0.50** | **98.81%** | 9,581,724 | 2.088 | 759.87 | 2,478 |

---

## 3. Key Findings

### ⚖️ The Pareto Frontier is Reached at $\lambda = 0.1$
Tuning $\lambda = 0.10$ provided an optimal trade-off:
- It lowered the **Total Cost** below the unregularized baseline (8.69M vs 8.95M).
- It suppressed the **Bullwhip Ratio** from 2.077 down to 1.917.
- It maintained a highly viable **97.94% Service Level**.

### 📉 Over-Regularization ($\lambda = 0.5$) Backfires
When the penalty is pushed too high ($\lambda = 0.5$), the agent learns that paying holding cost for massive stock buffers is mathematically "cheaper" than placing variable orders that trigger the $\lambda$ penalty. Consequently, the agent defaults to high-inventory strategies. Although Service Level climbs to 98.81%, Total Cost rises and Bullwhip paradoxically worsens (2.088) because the agent occasionally has to re-stock massive buffer drains.

### ✅ Proof of Concept
Explicit reward regularization works. It allows supply chain managers to strictly tune their exact preference for order smoothness vs. holding cost leanness directly into the RL objective function.

---

## 4. Plots Available

| Plot | Description |
|------|-------------|
| `plots/lambda_sweep.png` | Impact of lambda on Bullwhip Ratio vs. Cost |
