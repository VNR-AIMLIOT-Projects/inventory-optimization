# Experiment A4: Transfer Learning Across Seasons

## 1. Objective and Basis
The objective of this experiment is to evaluate **seasonal transfer learning** for the Joint DDQN inventory optimization model. We test whether a policy trained on one seasonal demand profile (Summer) can generalize directly or adapt efficiently via fine-tuning to a different seasonal profile (Winter). 

We aim to answer four key questions:
1. **Zero-shot generalization:** How well does a Summer-trained policy perform on Winter demand without any retraining?
2. **Transfer efficiency:** Does fine-tuning from Summer weights converge faster than training from scratch on Winter?
3. **Asymptotic convergence:** Does the fine-tuned model reach or exceed the long-run cold-start performance?
4. **Operational stability:** How do metrics like service level, total cost, and bullwhip ratio behave during adaptation?

## 2. Core Hypotheses
*   **H1 (Imperfect but Non-Trivial Zero-Shot Transfer):** The zero-shot Summer-trained policy will outperform naive behavior on Winter demand, but will have a noticeable performance gap compared to a Winter-converged model due to the seasonal distribution shift.
*   **H2 (Sample Efficiency Gain):** Fine-tuning the Summer policy on Winter demand will require significantly fewer training episodes (e.g., 50 episodes) to reach high service levels compared to training a cold-start Winter model from scratch.
*   **H3 (Structural Preservation):** The transferred model will retain essential supply chain control structures (such as inventory pipelines, lead-time buffering, and order coordination) from its pre-training, enabling rapid adaptation.
*   **H4 (Convergence Parallelism):** With long training budgets (e.g., 500 episodes), the cold-start model will eventually match or slightly exceed the fine-tuned model's performance, but the fine-tuned model will heavily dominate the early learning phase.

## 3. Environment & Parameter Settings
*   **Environment Base:** A1 Two-Echelon Linear Supply Chain (Supplier $\rightarrow$ Warehouse $\rightarrow$ Retailer $\rightarrow$ Customer).
*   **Lead Times:** Warehouse = 3 days, Retailer = 1 day.
*   **Cost Structure:**
    *   Warehouse holding cost ($h_W$): 2.0
    *   Retailer holding cost ($h_R$): 5.0
    *   Retailer backorder cost ($b_R$): 500.0
    *   Warehouse fixed ordering cost ($c_W$): 2.0
    *   Retailer fixed ordering cost ($c_R$): 2.0

## 4. Seasonal Demand Regimes
We define two distinct seasonal profiles generated via the synthetic demand generator:

| Metric | Summer (Source Task) | Winter (Target Task) |
|---|---|---|
| **Mean Daily Demand** | 714.9 | 577.0 |
| **Peak Daily Demand** | 2247 | 1685 |
| **Demand Volatility (Std Dev)** | 474.7 | 387.9 |
| **Peak Season Window** | Days 59–148 (Mid-year peak) | Days 0–59 & 335–364 (Winter peak) |
| **Festival Locations** | Days 15, 200, 250, 310 | Days 15, 120, 220, 300 |

## 5. Action Space Alignment
To facilitate clean weight transfer, the joint action semantics must be identical across both environments. We lock the action configuration to the Summer regime parameters:
*   **Max Order Quantity:** Calculated based on Summer demand statistics.
*   **Action Step Size:** Frozen for both Summer and Winter training.
This guarantees that action index $a \in [0, 120]$ represents the exact same physical order quantities in both Summer and Winter environments, allowing the neural network's advantage head to be transferred zero-shot.

## 6. Evaluation Conditions & Budgets
We evaluate five conditions:
1.  **Condition A (Summer Source):** Trained for 300 episodes on Summer demand.
2.  **Condition B (Winter Zero-Shot):** Summer policy evaluated directly on Winter demand with no retraining.
3.  **Condition C (Winter Fine-Tuned):** Initialized from Summer policy weights, fine-tuned on Winter demand for 50 episodes.
4.  **Condition D (Winter Cold-Start Matched):** Trained from scratch on Winter demand for 50 episodes.
5.  **Condition E (Winter Cold-Start Long):** Trained from scratch on Winter demand for 500 episodes (asymptotically converged target policy).

### Smoke Test Budgets
*   Summer source training: 30 episodes
*   Winter fine-tuning / cold-start matched: 10 episodes
*   Winter cold-start long: 50 episodes

## 7. Metrics
*   **Service Level (SL%):** Fraction of customer demand fulfilled without delay.
*   **Total Cost:** Sum of holding, backorder, and fixed ordering costs.
*   **Bullwhip Ratio:** Variance of warehouse orders divided by variance of retailer demand.
*   **Average Inventory:** Average daily inventory levels at the Warehouse ($I_W$) and Retailer ($I_R$).
*   **Zero-Shot Transfer Gap:** Metric delta between Condition B and Condition E.
*   **Fine-Tuning Gain:** Metric delta between Condition C and Condition D.
