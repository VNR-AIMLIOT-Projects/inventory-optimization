# Replenix — Multi-Echelon Supply Chain Experiments

**Branch:** `experiments/multi-echelon-research`  
**Status:** ✅ All 9 experiments complete  
**Total training time:** ~62 min (Apple MPS) for core A/B set

This directory contains isolated, reproducible experiments evaluating **Joint DDQN**
(Reinforcement Learning) against classical baselines across multiple supply chain
topologies. All experiments are completely decoupled from the production Replenix
system on `dev`.

---

## Experiment Overview

| # | Folder | Topology | Status | Key Result |
|---|--------|----------|--------|------------|
| **A1** | `A1_two_echelon_linear/` | 2-Echelon Serial (WH→R) | ✅ Done | 97% SL, +32.8% cost vs (s,S) |
| **A2** | `A2_three_echelon_linear/` | 3-Echelon Serial (WH→DC→R) | ✅ Done | 96.6% SL, +35.7% cost vs (s,S) |
| **A3** | `A3_divergent_one_to_two/` | Divergent (WH→R1+R2) | ✅ Done | 90.3% SL, +23.7% cost vs (s,S) |
| **B1** | `B1_state_ablation/` | 2-Echelon (IS vs ES state) | ✅ Done | ES lowers Bullwhip 22.3% |
| **B2** | `B2_ddqn_vs_ppo/` | Algorithm Ablation | ✅ Done | DDQN >99% SL, PPO collapses |
| **C1** | `C1_disruption_robustness/` | Supply Disruption (Shock) | ✅ Done | Aware agent maintains 96.6% SL |
| **C2** | `C2_stochastic_lead_times/` | Stochastic LT (2-5d) | ✅ Done | Deterministic training transfers well |
| **C3** | `C3_realworld_validation/` | UCI/Retail Multi-SKU | ✅ Done | RL matches/beats Oracle on clean SKUs |
| **D1** | `D1_bullwhip_reward_reg/` | Reward Regularization | ✅ Done | λ=0.10 Pareto smooths bullwhip |

---

## Directory Structure

```
experiments/
│
├── README.md                          ← This file
├── run_all_experiments.py             ← Master sequential runner
├── run_summary.json                   ← Timing summary after full run
├── CONCLUSIONS.md                     ← Cross-experiment synthesis
│
├── shared/                            ← Reusable utilities (ALL experiments import from here)
│   ├── __init__.py
│   ├── demand.py                      ← Demand generation (mirrors Backend-RL/src/demand.py)
│   ├── dqn_agent.py                   ← Dueling Double-DQN agent
│   └── metrics.py                     ← Metrics, plots, logging
│
├── A1_two_echelon_linear/
│   ├── EXPERIMENT.md                  ← Design, MDP formulation, hypotheses
│   ├── RESULTS.md                     ← Full numerical results + interpretation
│   ├── env_two_echelon.py             ← 2-echelon environment
│   ├── baselines.py                   ← (s,S), Oracle, Independent DDQN
│   ├── run_experiment.py              ← Training + evaluation script
│   ├── results/
│   │   ├── config.json                ← Exact hyperparameters used
│   │   ├── summary.json               ← Machine-readable metric table
│   │   └── experiment_log.jsonl       ← Per-checkpoint training log
│   └── plots/
│       ├── training_curve.png
│       ├── inventory_trajectory.png
│       ├── bullwhip_comparison.png
│       └── cost_breakdown.png
│
├── A2_three_echelon_linear/
│   ├── EXPERIMENT.md                  ← Design doc
│   ├── RESULTS.md                     ← Results + interpretation
│   ├── env_three_echelon.py           ← 3-echelon environment
│   ├── run_experiment.py
│   ├── results/  ...
│   └── plots/   ...
│
├── A3_divergent_one_to_two/
│   ├── EXPERIMENT.md
│   ├── RESULTS.md
│   ├── env_divergent.py               ← Divergent 1→2 environment
│   ├── run_experiment.py
│   ├── results/  ...
│   └── plots/   ...
│
├── B1_state_ablation/
│   ├── EXPERIMENT.md
│   ├── RESULTS.md
│   ├── run_experiment.py              ← Trains IS and ES variants sequentially
│   ├── results/  ...
│   └── plots/   ...
│
├── B2_ddqn_vs_ppo/                    ← Algorithm Ablation (DDQN vs PPO)
├── C1_disruption_robustness/          ← Supply Disruption Testing
├── C2_stochastic_lead_times/          ← Stochastic Lead Time Testing
├── C3_realworld_validation/           ← Real-World Dataset Evaluation
└── D1_bullwhip_reward_reg/            ← Bullwhip Reward Regularization
```

---

## How to Run

### Full suite (all 4 experiments, 500 eps each):
```bash
cd experiments/
python3 run_all_experiments.py
```

### Single experiment:
```bash
python3 A1_two_echelon_linear/run_experiment.py --episodes 500
python3 A2_three_echelon_linear/run_experiment.py --episodes 500
python3 A3_divergent_one_to_two/run_experiment.py --episodes 500
python3 B1_state_ablation/run_experiment.py --episodes 500
```

### Smoke test (50 eps, ~8 min total):
```bash
python3 run_all_experiments.py --smoke-test
```

---

## Cross-Experiment Results At a Glance

| Experiment | Topology | SL — DDQN | SL — (s,S) | SL Δ | Cost Δ | Bullwhip DDQN | Bullwhip (s,S) |
|-----------|----------|:---------:|:---------:|:----:|:------:|:-------------:|:--------------:|
| **A1** | 2-Echelon | 97.0% | 85.4% | **+11.6 pp** | **+32.8%** | 2.138 | 1.054 |
| **A2** | 3-Echelon | 96.6% | 82.2% | **+14.4 pp** | **+35.7%** | 2.060 | 1.313 |
| **A3** | Divergent | 90.3% | 85.5% | **+4.8 pp** | **+23.7%** | 1.026 | 1.064 |
| **B1-IS** | 2-Ech (IS) | 95.5% | — | — | — | 2.325 | — |
| **B1-ES** | 2-Ech (ES) | 94.0% | — | — | — | **1.807** | — |
| **B2** | DDQN vs PPO | 99.3% | — | — | — | 1.549 | — |
| **C1** | Disruption | 92.1% | — | — | — | 2.121 | — |
| **C2** | Stochastic LT | 92.1% | — | — | — | 1.877 | — |
| **D1** | Reg (λ=0.1) | 97.9% | — | — | — | 1.917 | — |

---

## Branching Strategy

Each experiment is **committed and isolated on this branch**. The production `dev`
branch is never modified. To review results without running experiments:

```bash
git checkout experiments/multi-echelon-research
# All results are pre-computed in results/ and plots/ directories
```
