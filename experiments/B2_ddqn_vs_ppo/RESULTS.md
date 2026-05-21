# Experiment B2 — Results (Algorithm Ablation: Joint DDQN vs PPO)

**Branch:** `experiments/multi-echelon-research`
**Episodes:** 500
**Env:** A1 (2-echelon, seasonal, b_R=500)

---

## 1. Final Evaluation Metrics (Test Demand)

Both agents were trained for 500 episodes and evaluated greedily on a separate test set. 

| Metric | Joint DDQN | Joint PPO |
|--------|:----------:|:---------:|
| **Total Cost** | **10,594,003** | 112,000,555 |
| **Service Level** | 99.35% | **100.0%** (naive) |
| **Bullwhip Ratio** | **1.549** | 1.776 |
| **Order Std (Warehouse)** | **654.42** | 700.74 |
| **Convergence Ep (90% SL)** | **350** | 0 (naive buffer) |

---

## 2. Key Findings

### ✅ Joint DDQN Learns Efficient Buffering
The Dueling Double-DQN agent achieves an optimal balance, securing **>99% Service Level** at a total system cost of ~10.6M. The agent successfully explores the 121-action space and converges (reaches sustained 90%+ SL) around episode 350.

### ⚠️ PPO Collapses into Naive Policy
The Proximal Policy Optimization (PPO) agent fails to learn an efficient policy. It achieves a 100% service level immediately (Convergence Ep = 0) because it collapses into a naive, max-order policy that floods the system with inventory. This results in a holding cost explosion (total cost **~112M**, over 10x worse than DDQN). 

**Root Causes for PPO failure in this environment:**
1. **Discrete Action Space:** PPO typically excels in continuous action spaces. The discrete, multi-dimensional combinatorial action space (11 x 11) is difficult for the stochastic actor to explore efficiently without collapsing its entropy prematurely.
2. **Delayed Rewards:** The multi-echelon delay between placing an upstream warehouse order and satisfying downstream retail demand confounds PPO's advantage estimation, whereas DDQN's value-based off-policy replay buffer stabilizes learning.

---

## 3. Config Used

```json
{
  "ddqn_gamma": 0.98,
  "ddqn_tau": 0.005,
  "ddqn_lr": 1e-4,
  "ddqn_batch_size": 256,
  "ppo_lr": 3e-4,
  "ppo_gamma": 0.99,
  "ppo_gae_lambda": 0.95,
  "ppo_clip": 0.2
}
```

---

## 4. Plots Available

| Plot | Description |
|------|-------------|
| `plots/training_curves_comparison.png` | DDQN vs PPO episode reward convergence |
| `plots/eval_metric_comparison.png` | Head-to-head bar chart (SL, BW, Order Std) |
| `plots/convergence_comparison.png` | Episode progression to 90% SL target |
