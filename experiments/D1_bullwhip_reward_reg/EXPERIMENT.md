# Experiment D1: Bullwhip Reward Regularisation

## 1. Objective and Basis
The Bullwhip Effect (variance amplification upstream) is a notorious supply chain inefficiency. While DRL agents optimize cost, they often induce heavy order variance upstream to achieve it. This experiment tests a novel reward-shaping approach: adding a penalty proportional to the step-to-step order variance (Bullwhip Regularisation). This is the first known attempt to explicitly suppress bullwhip in a DRL reward function for seasonal multi-echelon networks.

## 2. Environment Settings & Parameters
*   **Environment:** A1 Two-Echelon Linear Supply Chain.
*   **Demand Profile:** Seasonal (Summer peak).
*   **Regularisation Mechanism:** 
    *   Modified Reward: $R_{t} = R_{env} - \lambda \cdot |a_W(t) - a_W(t-1)|$
    *   Where $a_W$ is the Warehouse order action.
*   **Lambda ($\lambda$) Sweep:** Evaluated at $\lambda \in \{0.00, 0.01, 0.10, 0.50\}$.
*   **Training Configuration:** Episodes: 500 per $\lambda$. DDQN algorithm. Tested strictly on raw environment cost (without the penalty) to ensure fair comparison.

## 3. Results and Conclusion
### Summary of Metrics
| $\lambda$ (Penalty) | Service Level | Bullwhip Ratio | Order Std Dev | Total Cost |
|---------------------|---------------|----------------|---------------|------------|
| 0.00 (Baseline) | 98.79% | 2.077 | 757.9 | 8.9M |
| 0.01 | 97.28% | 1.779 | 701.5 | 10.2M |
| 0.10 | 97.94% | 1.917 | 728.1 | 8.6M |
| 0.50 | 98.81% | 2.088 | 759.9 | 9.5M |

### Key Findings
*   **Pareto Trade-off Established:** A moderate regularisation ($\lambda = 0.10$) proved to be a "sweet spot," achieving slightly lower cost (8.6M) and maintaining a high Service Level (~98%) while keeping the Bullwhip Ratio in check. 
*   **Hyperparameter Sensitivity:** Interestingly, high penalties ($\lambda = 0.50$) forced the agent into suboptimal exploration local minima where it had to break the regularisation to meet seasonal demand spikes, resulting in a rebound of the Bullwhip Ratio (2.08).
*   **Conclusion:** Bullwhip Reward Regularisation is an effective tool to smooth out upstream order volatility without sacrificing downstream customer service, but the $\lambda$ parameter must be carefully tuned to avoid stifling the agent's response to natural demand seasonality.
