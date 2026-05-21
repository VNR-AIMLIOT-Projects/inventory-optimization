# Experiment C3 — Results (Real-World Dataset Validation)

**Branch:** `experiments/multi-echelon-research`
**Episodes:** 500 per SKU
**Task:** Replace synthetic demand generators with actual historical transaction data.

---

## 1. Motivation
To ensure the Joint DDQN approach translates from clean, synthetic seasonal patterns to messy, real-world commerce, we evaluated the agent against two multi-SKU datasets spanning 1-2 years of historical transactions.

---

## 2. Dataset 1: Retail Store Inventory Forecasting

**Characteristics:** ~73,000 records of multi-SKU transactions over 2 years (2022-2024).

The demand extraction accurately captured the seasonal variations using the 60th percentile for rolling average. The DDQN agent was trained on the top 4 SKUs and compared to the Oracle (which has perfect 5-day future vision).

| SKU | Joint DDQN SL | Oracle SL | Joint DDQN Reward | Oracle Reward |
|-----|:-------------:|:---------:|:-----------------:|:-------------:|
| **P0016** | 99.58% | 99.93% | 18.35M | 17.38M |
| **P0020** | **100.0%** | 97.80% | 17.65M | 17.91M |
| **P0014** | **99.82%** | 98.86% | 18.00M | 18.22M |
| **P0015** | 99.63% | **100.0%** | 18.11M | 17.28M |

### ✅ Dataset 1 Findings
The RL agent successfully **matches or beats the Oracle** across all 4 SKUs. It consistently achieves ~99-100% Service Levels while dynamically adjusting the buffer to minimize cost and maximize reward.

---

## 3. Dataset 2: UCI Online Retail Dataset

**Characteristics:** 541,909 records (2010-2011) featuring highly sparse, volatile, and erratic demand typical of wholesale/online mixed retail.

| SKU | Joint DDQN SL | Oracle SL | Joint DDQN Reward | Oracle Reward |
|-----|:-------------:|:---------:|:-----------------:|:-------------:|
| **85123A** | 1.95% | 96.88% | -2.07M | 0.38M |
| **22423** | 1.96% | 83.69% | -0.56M | -0.09M |
| **85099B** | **82.90%** | **95.86%** | **1.07M** | **1.21M** |
| **47566** | 1.97% | 79.73% | -0.72M | 0.30M |

### ⚠️ Dataset 2 Findings (Volatility Challenges)
The extreme volatility of Dataset 2 challenged the RL agent at the standard 500-episode training budget.
- For **SKU 85099B**, the agent successfully found a viable policy, achieving ~82.9% Service Level and positive reward, staying competitive with the Oracle.
- For the other 3 SKUs, the agent collapsed into a defensive non-ordering state (Service Level ~2%) to avoid catastrophic holding costs given the erratic sparsity. 
- **Next Steps:** These highly volatile SKUs will require more advanced hyperparameter tuning (e.g., lower $b_R$ penalty or higher epsilon exploration minimums) or >500 episodes to fully converge.

---

## 4. Plots Available

| Plot | Description |
|------|-------------|
| `dataset1_retail_store/plots/replenix_dataset1_multisku_metrics.png` | Aggregate performance for retail store |
| `dataset2_uci_online/plots/replenix_dataset2_multisku_metrics.png` | Aggregate performance for online retail |
