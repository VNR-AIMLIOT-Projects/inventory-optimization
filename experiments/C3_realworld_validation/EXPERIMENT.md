# Experiment C3: Real-World Dataset Validation

## Objective
Validate the Replenix demand simulation, parameter extraction, and RL agents on real-world multi-SKU datasets that span at least 1-2 years of historical demand. Compare the RL agent's performance against the Oracle baseline on these datasets to prove the robustness of the system for actual production workloads. 

## Motivation
To support journal publication of the Replenix study, it is critical to move beyond purely synthetic demand data and validate the models on 2-3 real-world datasets. This experiment serves as the first parallel research track towards that goal, utilizing the UCI Online Retail II dataset (which contains multi-SKU transactional data over a 2-year period).

## Tasks
1. **Dataset Acquisition & Preprocessing**: 
   - Download the UCI Online Retail II dataset.
   - Aggregate transactional data into daily sales demand per SKU.
   - Select top performing SKUs with at least 1-2 years of dense historical data.
2. **Demand Extraction Validation**: 
   - Run the dataset through `extracts_demand.py`.
   - Verify whether seasonality and peak demand are correctly detected. 
   - If extraction fails to capture the true distribution, refine the detection algorithms.
3. **RL Training & Oracle Comparison**: 
   - Train the Joint DDQN/PPO agent on the real-world demand profile.
   - Run the Oracle baseline.
   - Compare performance metrics (Cost, Service Level, Fill Rate) against the Oracle to quantify the optimality gap.

## Results & Logs

### Dataset 1: Retail Store Inventory Forecasting
- **Dataset Acquired:** Downloaded a 1.5MB Retail Store Inventory Forecasting Dataset with ~73,000 records of multi-SKU transactions over 2 years (2022-2024).
- **Validation Scope:** Validated across the Top 4 SKUs (`P0016`, `P0020`, `P0014`, `P0015`) for 500 episodes each (731 days per episode).
- **Demand Parameter Extraction:** The extraction logic was updated to use the 60th percentile for the rolling average to accurately capture seasonal variations. After the change, it successfully detected multiple seasons and festival peaks.
- **Baseline Evaluation:** The Replenix `DQNAgent` successfully matched or slightly outperformed the Oracle baseline across all 4 SKUs, consistently achieving ~99-100% Service Levels while dynamically adjusting the buffer to minimize cost and maximize reward (~18M per SKU).
- **Artifacts:** See `experiments/C3_realworld_validation/dataset1_retail_store/plots/replenix_dataset1_multisku_metrics.png` for aggregated comparisons.

### Dataset 2: UCI Online Retail Dataset
- **Dataset Acquired:** Downloaded the massive UCI Online Retail dataset (541,909 records, multi-SKU, 2010-2011).
- **Validation Scope:** Validated across the Top 4 SKUs (`85123A`, `22423`, `85099B`, `47566`) for 500 episodes each (374 days per episode).
- **Demand Parameter Extraction:** Aggregated transactional data into daily demands. The parameter extraction accurately handled the sparse and highly volatile demand distribution.
- **Baseline Evaluation:** Trained the `DQNAgent` on highly noisy real-world data. While it learned the optimal policy for some SKUs (e.g., `85099B` matched Oracle at ~82% SL and >1M reward), the extreme volatility of other SKUs means they require more advanced tuning or >500 episodes to fully converge against the deterministic Oracle.
- **Artifacts:** See `experiments/C3_realworld_validation/dataset2_uci_online/plots/replenix_dataset2_multisku_metrics.png` for aggregated comparisons.
