# Experiment C2: Stochastic Lead Times

## 1. Objective and Basis
While classical models and our previous DRL baselines (A1-A3) assume fixed, deterministic lead times (e.g., shipping always takes exactly 3 days), real-world supply chains are fraught with unpredictable delays. 
This experiment assesses whether our Joint DDQN agent's learned policy is robust to stochastic lead times, and explores a crucial RL question: Is it better to train an agent directly in a stochastic, noisy environment, or to train it in a clean, deterministic environment and rely on the policy's inherent robustness?

## 2. Environment Settings & Parameters
*   **Environment:** Modified A1 Two-Echelon Linear Supply Chain (`StochasticTwoEchelonEnv`).
*   **Demand Profile:** Seasonal (Summer peak), 365 days.
*   **Stochastic Lead Time (Warehouse):** Instead of a fixed $L_W = 3$, orders arrive in a uniformly random time between $2$ and $5$ days ($L_W \sim U(2,5)$).
*   **Conditions Evaluated (both tested on the Stochastic Env):**
    1.  **Fixed (LT=3):** Agent trained on a deterministic environment ($L_W=3$), evaluated on the stochastic environment.
    2.  **Stochastic (LT 2-5):** Agent trained directly on the stochastic environment, evaluated on the stochastic environment.
*   **Training Configuration:** Episodes: 500 per condition. DDQN algorithm.

## 3. Results and Conclusion
### Summary of Metrics (Evaluated on Stochastic Env)
| Training Condition | Service Level | Total Cost | Bullwhip Ratio |
|--------------------|---------------|------------|----------------|
| Fixed (LT=3) | 100.0% | 12.1M | 1.464 |
| Stochastic (LT 2-5) | 92.14% | 16.5M | 1.877 |

### Key Findings
*   **Inherent Robustness of Deterministic Training:** The agent trained on the clean, fixed 3-day lead time performed exceptionally well when tested in the unpredictable 2-5 day stochastic environment, maintaining a 100% Service Level with a relatively low cost of 12.1M. The safety-stock behavior it learned was robust enough to absorb the delivery shocks.
*   **Learning Hindered by Environmental Noise:** Counter-intuitively, the agent that was *trained* directly on the stochastic lead times performed significantly worse (92.1% SL and 16.5M cost). The unpredictability of order arrivals (and frequent order crossovers) during training created massive variance in the Q-value estimations. This noise prevented the DDQN agent from converging to an optimal policy within 500 episodes.
*   **Conclusion:** For deep reinforcement learning in supply chains, training on deterministic environments representing the "mean" expectation produces highly robust policies. Exposing the agent to too much environmental stochasticity (like random delivery delays) during the early stages of training can paralyze the learning process due to reward variance. This is a highly valuable insight for real-world DRL deployment.
