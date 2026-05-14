# Replenix Multi-Echelon Experiments

This directory contains **isolated research experiments** exploring multi-echelon supply chain
reinforcement learning. Each experiment lives in its **own Git branch** and **its own folder**
so production Replenix code on `dev` is never modified.

---

## Branch Convention

| Branch | Folder | Experiment |
|--------|--------|-----------|
| `experiment/A1-two-echelon-linear-ddqn` | `A1_two_echelon_linear/` | 2-echelon Linear, Joint DDQN |
| `experiment/A2-three-echelon` *(planned)* | `A2_three_echelon/` | 3-echelon, DDQN vs PPO |
| `experiment/A3-divergent` *(planned)* | `A3_divergent/` | 1 WH → 3 Retailers, Shared Policy |
| `experiment/B1-ddqn-vs-ppo` *(planned)* | `B1_ddqn_vs_ppo/` | Algorithm ablation |
| `experiment/D1-xai-echelon` *(planned)* | `D1_xai_echelon/` | SHAP on multi-echelon policy |

---

## Isolation Guarantee

> **No experiment file in this directory imports from or modifies `Backend-RL/src/`.**
>
> Each experiment is fully self-contained: it copies the algorithms it needs and uses the
> same synthetic demand generator logic, reimplemented locally.
>
> The production Replenix multi-SKU system on `dev` remains completely untouched.

---

## Quick Start (Experiment A1)

```bash
# Make sure you are on the correct branch
git checkout experiment/A1-two-echelon-linear-ddqn

# Install deps
pip install torch numpy pandas matplotlib

# Run full experiment (500 eps, all baselines, all plots, ~15 min)
cd experiments/A1_two_echelon_linear
python run_experiment.py

# Quick smoke test (50 eps, no baselines, ~2 min)
python run_experiment.py --smoke-test
```

---

## Reading Results

After a run, results appear in:

```
experiments/A1_two_echelon_linear/
  results/
    config.json          ← exact config used for this run
    experiment_log.jsonl ← per-evaluation-checkpoint metrics
    summary.json         ← final comparison table (Joint DDQN vs all baselines)
  plots/
    training_curve.png
    inventory_trajectory.png
    bullwhip_comparison.png
    cost_breakdown.png
```

The primary metric is **total_cost** (lower is better).
The key novel metric is **bullwhip_ratio** (lower = less demand amplification).
