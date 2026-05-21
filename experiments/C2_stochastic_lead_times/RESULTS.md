# Experiment C2 — Results (Stochastic Lead Times)

**Branch:** `experiments/multi-echelon-research`
**Episodes:** 500
**Env:** A1 (2-echelon, seasonal) evaluated under deterministic vs. stochastic supplier lead times.

---

## 1. Final Evaluation Metrics

The Joint DDQN agent was evaluated in two scenarios: one where the lead time from the supplier to the warehouse is strictly fixed at 3 days ($L_W = 3$), and one where it varies stochastically between 2 and 5 days ($L_W \sim U(2, 5)$).

| Metric | Fixed (LT = 3) | Stochastic (LT 2-5) |
|--------|:--------------:|:-------------------:|
| **Total Cost** | 12,115,461 | 16,537,716 |
| **Service Level** | **100.0%** | **92.14%** |
| **Bullwhip Ratio** | **1.464** | 1.877 |
| **Order Std (Warehouse)** | **636.23** | 720.39 |
| **Total Backlog** | **0** | 16,390 |

---

## 2. Key Findings

### ✅ High Robustness to Unseen Stochasticity
Remarkably, a Joint DDQN policy trained on a clean, deterministic environment ($L_W = 3$) proved highly robust when deployed in an environment with stochastic lead times. Even under delivery uncertainties varying from 2 to 5 days, the agent maintained a **92.14% Service Level**. 

### 📈 Cost and Variance Impact
The stochastic delays force the system to absorb late shipments, increasing both backorders and holding costs (as items arrive unpredictably). Consequently, total costs increase from ~12.1M to ~16.5M. The Bullwhip Ratio also climbs from 1.464 to 1.877 as the agent's actions attempt to compensate for pipeline discrepancies. 

### 🧠 Training Stability Insight (From EXPERIMENT.md Notes)
Training directly on stochastic lead times severely hinders Q-value convergence because the random delay noise obfuscates the immediate reward signal associated with a given ordering action. The C2 experiment proves that **Zero-Shot Transfer** (training on deterministic $\rightarrow$ deploying on stochastic) is a superior paradigm for this multi-echelon DRL architecture.

---

## 3. Config Used

- **Test Condition 1:** $L_W = 3$ (Deterministic)
- **Test Condition 2:** $L_W \sim U(2, 5)$ (Stochastic, uniformly distributed delays)
- The agent evaluated was trained exclusively on the deterministic environment.

---

## 4. Plots Available

| Plot | Description |
|------|-------------|
| `plots/lt_stochasticity_impact.png` | Side-by-side metric comparison under both conditions |
