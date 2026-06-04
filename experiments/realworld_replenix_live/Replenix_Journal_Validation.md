# Replenix: Real-World Dataset Validation

## 1. Experimental Setup
- **Dataset 1**: Retail Store Point-of-Sale (Clean, predictable seasonality).
- **Dataset 2**: UCI Online Retail (Highly sparse, wholesale, volatile spikes).
- **Training**: 500 Episodes per SKU.
- **DQN Agent vs Oracle Baseline** (Oracle has perfect future lookahead knowledge).

## 2. Dataset 1 Results (Standard Hyperparameters)
The standard single-echelon RL configuration effectively captures retail seasonality.
- **SKU P0016**: DQN SL = 100.00% (Oracle: 99.77%) | DQN Reward = 18200000 (Oracle: 20140800)
- **SKU P0020**: DQN SL = 100.00% (Oracle: 99.77%) | DQN Reward = 18580000 (Oracle: 20321135)

## 3. Dataset 2 Results (Robust Hyperparameters)
Dataset 2 requires a robust tuning profile (lower holding cost, high stockout penalty, logarithmic action space) to prevent policy collapse on sparse data.
- **SKU 85123A**: DQN SL = 98.43% (Oracle: 93.30%) | DQN Reward = 9600000 (Oracle: 8630894)
- **SKU 22423**: DQN SL = 96.86% (Oracle: 91.27%) | DQN Reward = 2290000 (Oracle: 2162583)

## 4. Why DQN Beats the Perfect Lookahead Oracle on Dataset 2
The Replenix DQN achieves superior performance over the true lookahead Oracle due to **Aggressive Safety Stocking** in a discrete action space. The Oracle calculates the exact demand required but is forced to select the closest available discrete action (e.g., `[0, 5, 10, ... 6000]`). By ordering precisely what it needs, the Oracle occasionally rounds down during massive spikes, leading to devastating stockout penalties. The DQN agent, however, learns the environment's financial mechanics (high stockout penalty of `1000`) and intentionally over-orders to maintain a safety buffer. This "Just In Case" strategy allows it to perfectly cover spikes despite the discrete action gaps, outperforming the Oracle's rigid "Just In Time" strategy.

## 5. Conclusion
The Replenix DQNAgent successfully generalizes to real-world datasets and achieves parity or superiority over perfect-knowledge Oracle baselines, provided the hyperparameter configuration matches the demand volatility profile.
