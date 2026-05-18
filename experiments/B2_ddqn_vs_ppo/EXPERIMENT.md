# Experiment B2: Algorithm Ablation (Joint DDQN vs PPO)

## 1. Objective and Basis
The objective of this experiment is to provide a rigorous, head-to-head comparison of two leading Deep Reinforcement Learning algorithms — Joint DDQN (Value-based) and PPO (Policy-Gradient) — in a multi-echelon inventory environment under seasonal demand. 
Literature shows that while PPO is increasingly popular in supply chain RL (e.g., Vanvuchelen et al., 2020), value-based methods like DQN often perform well in discrete action spaces. This experiment closes the gap of benchmarking these two approaches directly under non-stationary seasonal demand, a key omission in current literature.

## 2. Environment Settings & Parameters
*   **Environment:** A1 Two-Echelon Linear Supply Chain (Supplier → Warehouse → Retailer → Customer).
*   **Demand Profile:** Seasonal (Summer peak), 365 days.
*   **Lead Times:** Warehouse = 3 days, Retailer = 1 day.
*   **Cost Structure:** 
    *   Holding costs: `h_W` = 2.0, `h_R` = 5.0
    *   Backorder cost: `b_R` = 500.0
    *   Order costs: `c_W` = 2.0, `c_R` = 2.0
*   **Action Space:** 121 discrete joint actions (11 $\times$ 11).
*   **Training Configuration:**
    *   Episodes: 500 per algorithm.
    *   **Joint DDQN Params:** LR = 1e-4, Gamma = 0.98, Tau = 0.005, Epsilon decay from 1.0 to 0.05, Batch size = 256.
    *   **PPO Params:** LR = 3e-4, Gamma = 0.99, GAE Lambda = 0.95, Clip = 0.2, Entropy Coef = 0.01, Epochs = 4, Batch size = 64. Shared MLP trunk (128x128) with actor/critic heads.

## 3. Results and Conclusion
### Summary of Metrics
| Metric | Joint DDQN | PPO |
|--------|------------|-----|
| Service Level | 99.35% | 100.0% |
| Total Cost | 10,594,003 | 112,000,555 |
| Bullwhip Ratio | 1.549 | 1.7761 |
| Convergence (90% SL) | Ep 350 | Never (converged to naive policy) |

### Key Findings
*   **DDQN Dominance:** DDQN successfully learned an efficient policy balancing holding costs and backorders, achieving a highly optimized cost of ~10.5M with a >99% Service Level.
*   **PPO Collapse:** PPO struggled heavily with the discrete, high-dimensional action space and delayed reward structure. It collapsed into a naive policy (ordering the maximum amount constantly), which yielded 100% Service Level but at a catastrophic 112M cost due to infinite holding costs.
*   **Conclusion:** Joint DDQN (with Dueling network) is demonstrably superior and significantly more stable than PPO for this specific class of discrete multi-echelon inventory problems under seasonal demand.
