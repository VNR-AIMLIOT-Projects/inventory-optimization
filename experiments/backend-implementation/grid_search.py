"""
Grid Search over reward hyperparameters for inventory RL agent.

Experiments with different combinations of:
  - holding_cost   (penalty per unit of inventory per day)
  - stockout_penalty (penalty per unit of lost sales)

For each combo, trains a fresh agent and evaluates vs Oracle & Rule baselines.
Saves a summary CSV + comparison plots.

Usage:
    python grid_search.py
"""

import os
import itertools
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from datetime import datetime

from demand import generate_demand, prepare_env_data
from trainer import train_agent, evaluate_and_plot, _compute_adaptive_params

# ============================================================
# GRID SEARCH CONFIGURATION
# ============================================================

MODE = "summer"
EPISODES = 1000              # Episodes per experiment (same as main.py)
DECAY_TYPE = "exponential"
ACTION_SIZE = 20

# --- Hyperparameter grid ---
# Vary holding cost and stockout penalty to find the sweet spot
HOLDING_COSTS     = [5, 15, 30, 50]
STOCKOUT_PENALTIES = [100, 200, 400, 800]

# Output directory
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_DIR = os.path.join("results", f"grid_search_{TIMESTAMP}")


# ============================================================
# MAIN
# ============================================================

def run_grid_search():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Generate demand once — all experiments use the same demand
    raw = generate_demand(MODE, num_days=365)
    final_df = prepare_env_data(raw, MODE)

    max_demand = final_df['demand'].max()
    auto_max_order = int(0.5 * max_demand)
    auto_action_step = int(auto_max_order / ACTION_SIZE)

    print(f"{'='*70}")
    print(f"  GRID SEARCH — {len(HOLDING_COSTS) * len(STOCKOUT_PENALTIES)} experiments")
    print(f"  Demand: {MODE} | Episodes: {EPISODES} | Decay: {DECAY_TYPE}")
    print(f"  holding_costs:      {HOLDING_COSTS}")
    print(f"  stockout_penalties:  {STOCKOUT_PENALTIES}")
    print(f"  Output: {OUTPUT_DIR}")
    print(f"{'='*70}\n")

    results = []

    for i, (h_cost, s_penalty) in enumerate(itertools.product(HOLDING_COSTS, STOCKOUT_PENALTIES)):
        exp_name = f"h{h_cost}_s{s_penalty}"
        exp_dir = os.path.join(OUTPUT_DIR, exp_name)
        os.makedirs(exp_dir, exist_ok=True)

        print(f"\n{'='*60}")
        print(f"  Experiment {i+1}/{len(HOLDING_COSTS)*len(STOCKOUT_PENALTIES)}: "
              f"holding_cost={h_cost}, stockout_penalty={s_penalty}")
        print(f"  Ratio (stockout/holding): {s_penalty/h_cost:.1f}x")
        print(f"{'='*60}")

        # Train
        agent, rewards, used_max_order, used_action_step, _, _ = train_agent(
            MODE,
            episodes=EPISODES,
            max_order=auto_max_order,
            action_step=auto_action_step,
            custom_df=final_df,
            decay_type=DECAY_TYPE,
            holding_cost=h_cost,
            stockout_penalty=s_penalty,
        )

        # Evaluate
        rl_df, oracle_df, rule_df = evaluate_and_plot(
            agent, MODE,
            max_order=used_max_order,
            action_step=used_action_step,
            custom_df=final_df,
            output_dir=exp_dir,
            holding_cost=h_cost,
            stockout_penalty=s_penalty,
        )

        rl_reward = rl_df['reward'].sum()
        oracle_reward = oracle_df['reward'].sum()
        rule_reward = rule_df['reward'].sum()
        rl_vs_oracle = (rl_reward / oracle_reward * 100) if oracle_reward != 0 else 0

        # Inventory stats from RL evaluation
        avg_inv = rl_df['inventory'].mean()
        max_inv = rl_df['inventory'].max()
        avg_demand = rl_df['demand'].mean()
        days_of_supply = avg_inv / avg_demand if avg_demand > 0 else 0

        result = {
            "holding_cost": h_cost,
            "stockout_penalty": s_penalty,
            "ratio_s_over_h": round(s_penalty / h_cost, 1),
            "rl_reward": rl_reward,
            "oracle_reward": oracle_reward,
            "rule_reward": rule_reward,
            "rl_vs_oracle_pct": round(rl_vs_oracle, 1),
            "rl_avg_inventory": round(avg_inv, 0),
            "rl_max_inventory": max_inv,
            "rl_days_of_supply": round(days_of_supply, 1),
            "best_train_reward": max(rewards),
            "final_train_reward": rewards[-1],
            "avg_last_50": round(np.mean(rewards[-50:]), 0),
        }
        results.append(result)

        print(f"\n  >> Result: RL={rl_reward:,.0f} | Oracle={oracle_reward:,.0f} | "
              f"RL/Oracle={rl_vs_oracle:.1f}% | Avg Inv={avg_inv:.0f} | "
              f"Days Supply={days_of_supply:.1f}")

    # ============================================================
    # Save summary
    # ============================================================
    results_df = pd.DataFrame(results)
    csv_path = os.path.join(OUTPUT_DIR, "grid_search_results.csv")
    results_df.to_csv(csv_path, index=False)
    print(f"\n{'='*70}")
    print(f"  GRID SEARCH COMPLETE — Results saved to {csv_path}")
    print(f"{'='*70}")
    print(results_df.to_string(index=False))

    # ============================================================
    # Summary Heatmaps
    # ============================================================
    _plot_heatmaps(results_df, OUTPUT_DIR)

    # Best configuration
    best = results_df.loc[results_df['rl_vs_oracle_pct'].idxmax()]
    print(f"\n  BEST CONFIG (by RL/Oracle %):")
    print(f"    holding_cost     = {best['holding_cost']}")
    print(f"    stockout_penalty = {best['stockout_penalty']}")
    print(f"    RL/Oracle        = {best['rl_vs_oracle_pct']}%")
    print(f"    Avg Inventory    = {best['rl_avg_inventory']}")
    print(f"    Days of Supply   = {best['rl_days_of_supply']}")

    # Best by lowest days of supply (least overstocking) among those with decent RL/Oracle
    decent = results_df[results_df['rl_vs_oracle_pct'] > 10]
    if len(decent) > 0:
        leanest = decent.loc[decent['rl_days_of_supply'].idxmin()]
        print(f"\n  LEANEST CONFIG (lowest overstock, RL/Oracle > 10%):")
        print(f"    holding_cost     = {leanest['holding_cost']}")
        print(f"    stockout_penalty = {leanest['stockout_penalty']}")
        print(f"    RL/Oracle        = {leanest['rl_vs_oracle_pct']}%")
        print(f"    Avg Inventory    = {leanest['rl_avg_inventory']}")
        print(f"    Days of Supply   = {leanest['rl_days_of_supply']}")


def _plot_heatmaps(results_df, output_dir):
    """Generate heatmap plots for key metrics across the grid."""
    metrics = [
        ("rl_vs_oracle_pct", "RL / Oracle (%)", "RdYlGn"),
        ("rl_days_of_supply", "Avg Days of Supply", "RdYlGn_r"),   # lower is better → reversed
        ("rl_avg_inventory", "Avg RL Inventory", "RdYlGn_r"),
    ]

    for metric, title, cmap in metrics:
        pivot = results_df.pivot_table(
            index="holding_cost",
            columns="stockout_penalty",
            values=metric,
        )

        fig, ax = plt.subplots(figsize=(8, 6))
        im = ax.imshow(pivot.values, cmap=cmap, aspect="auto")

        # Labels
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index)
        ax.set_xlabel("Stockout Penalty")
        ax.set_ylabel("Holding Cost")
        ax.set_title(f"Grid Search: {title}", fontweight="bold")

        # Annotate cells
        for (j, k), val in np.ndenumerate(pivot.values):
            ax.text(k, j, f"{val:.1f}", ha="center", va="center",
                    fontsize=10, fontweight="bold",
                    color="white" if abs(val - pivot.values.mean()) > pivot.values.std() else "black")

        fig.colorbar(im, ax=ax)
        fig.tight_layout()
        safe_metric = metric.replace("/", "_")
        fig.savefig(os.path.join(output_dir, f"heatmap_{safe_metric}.png"), dpi=150)
        plt.close(fig)

    print(f"  Saved heatmaps to {output_dir}/")


if __name__ == "__main__":
    run_grid_search()
