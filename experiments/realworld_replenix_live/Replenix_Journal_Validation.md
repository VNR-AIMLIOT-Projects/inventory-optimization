# Replenix: Real-World Dataset Validation

## 1. Experimental Setup
- **Dataset 1**: Retail Store Point-of-Sale (Clean, predictable seasonality).
- **Dataset 2**: UCI Online Retail (Highly sparse, wholesale, volatile spikes).
- **Training**: 500 Episodes per SKU.
- **DQN Agent vs Oracle Baseline** (Oracle has perfect 5-day mean knowledge).

## 2. Dataset 1 Results (Standard Hyperparameters)
The standard single-echelon RL configuration effectively captures retail seasonality.
- **SKU P0016**: DQN SL = 100.00% (Oracle: 99.93%) | DQN Reward = 18195280 (Oracle: 17387605)
- **SKU P0020**: DQN SL = 100.00% (Oracle: 97.81%) | DQN Reward = 18582220 (Oracle: 17914485)

## 3. Dataset 2 Results (Robust Hyperparameters)
Dataset 2 requires a robust tuning profile (lower holding cost, high stockout penalty, logarithmic action space) to prevent policy collapse on sparse data.
- **SKU 85123A**: DQN SL = 98.43% (Oracle: 70.75%) | DQN Reward = 9599434 (Oracle: 1281182)
- **SKU 22423**: DQN SL = 96.86% (Oracle: 85.06%) | DQN Reward = 2286548 (Oracle: 1516422)

## 4. Conclusion
The Replenix DQNAgent successfully generalizes to real-world datasets and achieves parity or superiority over Oracle baselines, provided the hyperparameter configuration matches the demand volatility profile.
