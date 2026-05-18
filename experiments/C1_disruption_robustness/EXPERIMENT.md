# Experiment C1: Disruption Robustness (Supply Shock)

## 1. Objective and Basis
Real-world supply chains are vulnerable to sudden shocks (e.g., factory shutdowns, transport strikes). Current DRL literature mostly assumes stable supply links. This experiment investigates whether an agent can learn preemptive and reactive resilience when trained in an environment subjected to stochastic supply disruptions, closing the literature gap regarding disruption handling under seasonal multi-echelon demand.

## 2. Environment Settings & Parameters
*   **Environment:** A2 Three-Echelon Linear Supply Chain (Supplier → Warehouse → DC → Retailer).
*   **Demand Profile:** Seasonal (Summer peak), 365 days.
*   **Lead Times:** L1 = 4, L2 = 2, L3 = 1.
*   **Disruption Parameters:** 
    *   Probability of shock (`p_shock`): 0.03 per day.
    *   Disruption length: Uniformly random between 1 and 7 days.
    *   Effect: Upstream supply to the Warehouse is completely cut off (forced 0 order reception).
*   **Conditions Evaluated:**
    1.  **Baseline:** Trained and evaluated with no disruptions.
    2.  **Naive:** Trained with no disruptions, but evaluated *with* disruptions.
    3.  **Aware:** Trained *with* disruptions and provided an augmented state space (2 extra dims: `disruption_active` flag, `disruption_remaining_norm`).
*   **Training Configuration:** Episodes: 500 per condition. DDQN algorithm.

## 3. Results and Conclusion
### Summary of Metrics
| Condition | Overall SL | Normal SL | Disruption SL | Cost |
|-----------|------------|-----------|---------------|------|
| Baseline (No shock) | 95.07% | 95.07% | N/A | Lowest |
| Naive (Untrained for shock) | 87.68% | 87.90% | 84.05% | High |
| Aware (Trained for shock) | 92.10% | 91.46% | 96.63% | Optimal balanced |

### Key Findings
*   **Catastrophic Drop in Naive Agent:** The Naive agent, when faced with unexpected supply shocks, saw its Service Level crash to 84.0% during the disruption windows, leading to severe stockouts.
*   **Learned Resilience:** The Aware agent, by observing the disruption state, successfully learned dynamic safety-stock behaviours. During actual disruption events, it maintained an incredible **96.63% Service Level**, heavily outperforming the Naive agent.
*   **Conclusion:** DRL agents can proactively handle supply shocks if the disruption state is observable. The agent learns to secure inventory at downstream nodes (DC and Retailer) the moment a disruption is detected upstream.
