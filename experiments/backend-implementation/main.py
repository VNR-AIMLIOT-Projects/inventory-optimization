import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from extracts_demand import load_and_process_data, plot_demand_preview
from demand_modifier import DemandModifier
from demand import generate_demand, prepare_env_data
from trainer import train_agent, evaluate_and_plot

# ==========================================
# CONFIGURATION — Edit these variables
# ==========================================
MODE = "summer"         # Options: "custom", "summer", "winter"
EPISODES = 3000         # Number of training episodes
DECAY_TYPE = "exponential"  # Options: "exponential", "linear"
FILE_PATH = "Inventory Data Template.xlsx - Sample Data.csv"
TARGET_SKU = "SKU_001"
MAX_ORDER = None        # Set to an int (e.g. 2000) or None for auto-compute
ACTION_SIZE = 20        # Fixed number of discrete actions

# Experiment name — results saved to results/<EXPERIMENT_NAME>/
EXPERIMENT_NAME = f"{EPISODES}_{DECAY_TYPE}"   # e.g. "3000_exponential"
OUTPUT_DIR = os.path.join("results", EXPERIMENT_NAME)


# ==========================================
# PLOTTING HELPERS
# ==========================================
def plot_demand_overview(dates, demand, title, filename):
    """Plot the raw demand time-series with basic stats."""
    fig, axes = plt.subplots(2, 1, figsize=(15, 10), gridspec_kw={"height_ratios": [3, 1]})

    # --- Top: Demand curve ---
    ax = axes[0]
    ax.plot(dates, demand, color="steelblue", linewidth=1, label="Daily Demand")
    avg = np.mean(demand)
    ax.axhline(avg, color="orange", linestyle="--", linewidth=1, label=f"Mean = {avg:.0f}")
    ax.fill_between(dates, demand, alpha=0.15, color="steelblue")
    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_ylabel("Demand (units)")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # --- Bottom: Distribution histogram ---
    ax2 = axes[1]
    ax2.hist(demand, bins=40, color="steelblue", edgecolor="white", alpha=0.8)
    ax2.axvline(avg, color="orange", linestyle="--", linewidth=1)
    ax2.set_xlabel("Demand (units)")
    ax2.set_ylabel("Frequency")
    ax2.set_title("Demand Distribution")
    ax2.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    print(f"  Saved: {filename}")
    plt.close(fig)


def plot_reward_curve(rewards, filename):
    """Plot training reward curve with rolling average and annotations."""
    fig, ax = plt.subplots(figsize=(14, 6))

    episodes = range(len(rewards))
    ax.plot(episodes, rewards, alpha=0.3, color="blue", linewidth=0.8, label="Episode Reward")

    # Rolling average (window=50)
    window = min(50, len(rewards))
    if len(rewards) >= window:
        rolling = pd.Series(rewards).rolling(window).mean()
        ax.plot(episodes, rolling, color="red", linewidth=2, label=f"Rolling Avg ({window} ep)")

    # Mark best episode
    best_idx = int(np.argmax(rewards))
    best_val = rewards[best_idx]
    ax.scatter([best_idx], [best_val], color="green", s=100, zorder=5, marker="*")
    ax.annotate(f"Best: {best_val:,.0f}\n(Ep {best_idx})",
                xy=(best_idx, best_val), xytext=(best_idx + len(rewards)*0.05, best_val),
                fontsize=9, color="green",
                arrowprops=dict(arrowstyle="->", color="green", lw=1))

    ax.set_title("Training Reward Curve", fontsize=14, fontweight="bold")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Total Reward")
    ax.legend(loc="lower right")
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    print(f"  Saved: {filename}")
    plt.close(fig)


def plot_epsilon_schedule(episodes, decay_type, eps_min, filename):
    """Plot the epsilon decay schedule so you can verify it visually before training."""
    eps = 1.0
    eps_min_val = eps_min

    if decay_type == "exponential":
        decay_rate = (eps_min_val / eps) ** (1.0 / episodes)
        schedule = []
        e = 1.0
        for _ in range(episodes):
            schedule.append(e)
            e = max(eps_min_val, e * decay_rate)
    else:  # linear
        step = (1.0 - eps_min_val) / (0.75 * episodes)
        schedule = []
        e = 1.0
        for i in range(episodes):
            schedule.append(e)
            if i < 0.75 * episodes:
                e = max(eps_min_val, e - step)

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(schedule, color="purple", linewidth=1.5)
    ax.axhline(eps_min_val, color="red", linestyle="--", linewidth=1, label=f"eps_min = {eps_min_val}")
    ax.axvline(int(0.75 * episodes), color="gray", linestyle=":", linewidth=1, label="75% of training")
    ax.set_title(f"Epsilon Decay Schedule — {decay_type.upper()} ({episodes} episodes)", fontweight="bold")
    ax.set_xlabel("Episode")
    ax.set_ylabel("Epsilon (exploration rate)")
    ax.set_ylim(0, 1.05)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(filename, dpi=150)
    print(f"  Saved: {filename}")
    plt.close(fig)
    print(f"  Epsilon at ep 0:                       {schedule[0]:.4f}")
    print(f"  Epsilon at ep {int(0.75*episodes):>5} (75%):          {schedule[int(0.75*episodes)-1]:.4f}")
    print(f"  Epsilon at ep {episodes-1:>5} (end):          {schedule[-1]:.4f}")


def plot_eval_detailed(rl_df, oracle_df, rule_df, title, filename):
    """Detailed 4-panel evaluation: inventory, orders, cumulative reward, stockouts."""
    min_len = min(len(rl_df), len(oracle_df), len(rule_df))
    dates = rl_df["date"].iloc[:min_len]

    fig, axes = plt.subplots(4, 1, figsize=(16, 18), sharex=True)

    # --- Panel 1: Inventory Levels ---
    ax = axes[0]
    ax.plot(dates, rl_df["inventory"].iloc[:min_len], "b-", label="RL Agent", linewidth=1.2)
    ax.plot(dates, oracle_df["inventory"].iloc[:min_len], "g--", label="Oracle", linewidth=1)
    ax.plot(dates, rule_df["inventory"].iloc[:min_len], "r:", label="Rule-Based", linewidth=1)
    ax.fill_between(dates, rl_df["demand"].iloc[:min_len], alpha=0.15, color="gray", label="Demand")
    ax.set_title(f"{title} — Inventory Levels", fontweight="bold")
    ax.set_ylabel("Units")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # --- Panel 2: Order Quantities ---
    ax = axes[1]
    ax.step(dates, rl_df["action_order_qty"].iloc[:min_len], "b-", where="post", label="RL Order", linewidth=1)
    ax.step(dates, oracle_df["action_order_qty"].iloc[:min_len], "g--", where="post", label="Oracle Order", linewidth=1)
    ax.step(dates, rule_df["action_order_qty"].iloc[:min_len], "r:", where="post", label="Rule Order", linewidth=1)
    ax.fill_between(dates, rl_df["demand"].iloc[:min_len], alpha=0.15, color="gray", label="Demand")
    ax.set_title("Order Quantities", fontweight="bold")
    ax.set_ylabel("Units Ordered")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # --- Panel 3: Cumulative Reward ---
    ax = axes[2]
    rl_cum = rl_df["reward"].iloc[:min_len].cumsum()
    oracle_cum = oracle_df["reward"].iloc[:min_len].cumsum()
    rule_cum = rule_df["reward"].iloc[:min_len].cumsum()
    ax.plot(dates, rl_cum, "b-", label=f"RL (Total: {rl_cum.iloc[-1]:,.0f})", linewidth=1.5)
    ax.plot(dates, oracle_cum, "g--", label=f"Oracle (Total: {oracle_cum.iloc[-1]:,.0f})", linewidth=1.2)
    ax.plot(dates, rule_cum, "r:", label=f"Rule (Total: {rule_cum.iloc[-1]:,.0f})", linewidth=1.2)
    ax.set_title("Cumulative Reward Over Time", fontweight="bold")
    ax.set_ylabel("Cumulative Reward")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)

    # --- Panel 4: Daily Reward (RL vs Oracle gap) ---
    ax = axes[3]
    rl_daily = rl_df["reward"].iloc[:min_len].values
    oracle_daily = oracle_df["reward"].iloc[:min_len].values
    gap = rl_daily - oracle_daily
    ax.bar(dates, gap, color=["green" if g >= 0 else "red" for g in gap], alpha=0.6, width=1.0)
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_title("Daily Reward Gap (RL − Oracle)  |  Green = RL wins", fontweight="bold")
    ax.set_ylabel("Reward Difference")
    ax.set_xlabel("Date")
    ax.grid(True, alpha=0.3)

    fig.suptitle(title, fontsize=16, fontweight="bold", y=1.01)
    fig.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"  Saved: {filename}")
    plt.close(fig)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ==========================================
    # 1. PREPARE DEMAND DATA
    # ==========================================
    if MODE == "custom":
        print(f"\n{'='*60}")
        print(f"  STEP 1: Loading Custom Demand Data")
        print(f"{'='*60}")
        print(f"  File: {FILE_PATH}  |  SKU: {TARGET_SKU}")
        try:
            raw_df = load_and_process_data(FILE_PATH, TARGET_SKU)
        except Exception as e:
            print(f"Error loading file: {e}")
            print("  Make sure the file exists and the SKU is correct.")
            return

        # Plot the raw uploaded demand (uses extracts_demand's plotter)
        plot_demand_preview(raw_df, os.path.join(OUTPUT_DIR, "1_custom_demand_preview.png"))

        # Standardize columns for the environment (expects lowercase 'demand')
        raw_df.columns = map(str.lower, raw_df.columns)
        final_df = raw_df.copy()

        # Also plot with our detailed plotter
        plot_demand_overview(
            final_df["date"], final_df["demand"],
            f"Custom Demand — {TARGET_SKU}  ({len(final_df)} days)",
            os.path.join(OUTPUT_DIR, "1_demand_overview.png"),
        )

    else:
        # Synthetic demand (summer/winter)
        print(f"\n{'='*60}")
        print(f"  STEP 1: Generating Synthetic {MODE.upper()} Demand")
        print(f"{'='*60}")
        raw = generate_demand(MODE, num_days=365)
        final_df = prepare_env_data(raw, MODE)

        # Plot synthetic demand overview
        plot_demand_overview(
            final_df["date"], final_df["demand"],
            f"Synthetic {MODE.upper()} Demand (365 days)",
            os.path.join(OUTPUT_DIR, f"1_demand_{MODE}_overview.png"),
        )

    max_demand = final_df['demand'].max()
    auto_max_order = MAX_ORDER or int(0.5 * max_demand)
    auto_action_step = int(auto_max_order / ACTION_SIZE)
    print(f"  Auto-configured MAX_ORDER: {auto_max_order}")


    print(f"\n  Demand Stats: mean={final_df['demand'].mean():.0f}  "
          f"max={final_df['demand'].max()}  min={final_df['demand'].min()}  "
          f"std={final_df['demand'].std():.0f}")

    # ==========================================
    # 2. TRAIN RL AGENT
    # ==========================================
    print(f"\n{'='*60}")
    print(f"  STEP 2: Training RL Agent ({EPISODES} episodes, {DECAY_TYPE} decay)")
    print(f"{'='*60}")

    # Plot and verify epsilon schedule before training starts
    print(f"\n  Epsilon Schedule Preview:")
    plot_epsilon_schedule(
        EPISODES, DECAY_TYPE, eps_min=0.05,
        filename=os.path.join(OUTPUT_DIR, "0_epsilon_schedule.png"),
    )

    agent, rewards, used_max_order, used_action_step = train_agent(
        MODE,
        episodes=EPISODES,
        max_order=auto_max_order,
        action_step=auto_action_step,
        custom_df=final_df if MODE == "custom" else None,
        decay_type=DECAY_TYPE,
    )

    # Plot training reward curve
    plot_reward_curve(rewards, os.path.join(OUTPUT_DIR, "2_training_reward_curve.png"))

    # Print training summary
    print(f"\n  Training Summary:")
    print(f"    Best Reward:  {max(rewards):>12,.0f}  (Episode {np.argmax(rewards)})")
    print(f"    Final Reward: {rewards[-1]:>12,.0f}")
    print(f"    Avg Last 50:  {np.mean(rewards[-50:]):>12,.0f}")
    print(f"    Max Order:    {used_max_order}")
    print(f"    Action Step:  {used_action_step}")

    # ==========================================
    # 3. EVALUATE
    # ==========================================
    print(f"\n{'='*60}")
    print(f"  STEP 3: Evaluating Agent vs Baselines")
    print(f"{'='*60}")
    rl_df, oracle_df, rule_df = evaluate_and_plot(
        agent, MODE,
        max_order=used_max_order,
        action_step=used_action_step,
        custom_df=final_df if MODE == "custom" else None,
        output_dir=OUTPUT_DIR,
    )

    # Detailed 4-panel evaluation graph
    plot_eval_detailed(
        rl_df, oracle_df, rule_df,
        f"Evaluation: {MODE.upper()} — RL vs Oracle vs Rule",
        os.path.join(OUTPUT_DIR, "3_evaluation_detailed.png"),
    )

    # ==========================================
    # SUMMARY
    # ==========================================
    print(f"\n{'='*60}")
    print(f"  ALL DONE — Experiment: {EXPERIMENT_NAME}")
    print(f"  Graphs saved to {OUTPUT_DIR}/")
    print(f"{'='*60}")
    print(f"  1_demand_*_overview.png    — Input demand visualization")
    print(f"  2_training_reward_curve.png — Reward progression over {EPISODES} episodes")
    print(f"  3_evaluation_detailed.png  — RL vs Oracle vs Rule (4-panel)")
    print(f"  {MODE}_results.png         — Evaluation comparison (from trainer)")


if __name__ == "__main__":
    main()
