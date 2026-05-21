# Experiment C1 — Results (Disruption Robustness)

**Branch:** `experiments/multi-echelon-research`
**Episodes:** 500
**Env:** A1 (2-echelon, seasonal) with stochastic supply disruption events.

---

## 1. Final Evaluation Metrics

Three conditions were tested to evaluate the robustness of the Joint DDQN agent against upstream supply disruptions. The "Naive" agent was trained on a clean environment but evaluated on one with disruptions. The "Aware" agent was explicitly trained on an environment featuring random disruption shocks.

| Condition | Overall Service Level | SL (Normal Periods) | SL (During Disruption) | Bullwhip Ratio | Disruption Days |
|-----------|:---------------------:|:-------------------:|:----------------------:|:--------------:|:---------------:|
| **Baseline (no disruption)** | **95.07%** | 95.07% | *N/A* | 1.462 | 0 |
| **Naive (no train disruption)**| 87.68% | 87.90% | 84.05% | 3.405 | 27 |
| **Aware (disruption-trained)** | **92.10%** | 91.46% | **96.63%** | **2.121** | 56 |

---

## 2. Key Findings

### ✅ "Aware" Agent Preemptively Mitigates Shocks
The Aware agent, having experienced supply disruptions during training, successfully learns to buffer inventory defensively. Despite experiencing double the disruption days (56 days) in its evaluation run compared to the Naive agent (27 days), it maintains an exceptional **96.63% Service Level during disruption events**. Its overall service level (92.10%) remains much closer to the clean baseline (95.07%).

### ⚠️ "Naive" Agent Vulnerability
The Naive agent crashes when exposed to supply shocks it hasn't seen during training. Its service level drops to **84.05%** during disruptions. Furthermore, its panic-ordering behavior upon recovery causes severe demand amplification, rocketing the Bullwhip Ratio up to **3.405** (vs. the Baseline's 1.462).

### 📊 Bullwhip Trade-off
The Aware agent manages to constrain the Bullwhip Ratio to **2.121**. While higher than the Baseline, it represents a massive stabilization improvement over the Naive agent's reactive panic ordering. 

---

## 3. Config Used

- Disruptions were modeled as low-probability, high-impact events shutting off warehouse inbound supply.
- The Aware agent learns solely through environmental interaction and reward feedback (stockout penalties), without needing an explicit "disruption forecast" input.

---

## 4. Plots Available

| Plot | Description |
|------|-------------|
| `plots/service_level_comparison.png` | Service levels across Normal vs Disrupted periods |
| `plots/bullwhip_disruption.png` | Bullwhip ratio spike visualization |
