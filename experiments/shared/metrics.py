"""
Shared Metrics — Replenix Multi-Echelon Experiments
====================================================
Consistent metric computation across A1, A2, A3, B1.
All functions accept the standardised info_log (list of per-step dicts).
"""

import numpy as np
import json
from pathlib import Path


def compute_all_metrics(info_log: list) -> dict:
    """
    Compute all evaluation metrics from a completed episode's info_log.

    Expected keys per dict (minimum):
      demand, a_W (or a_E1), inv_R (deepest node), backlog_R,
      holding_W, holding_R, backorder_R, order_cost_W, order_cost_R,
      reward, units_sold

    Returns a flat dict of floats.
    """
    demands      = np.array([d["demand"]      for d in info_log], dtype=float)
    rewards      = np.array([d["reward"]      for d in info_log], dtype=float)
    backlog_R    = np.array([d["backlog_R"]   for d in info_log], dtype=float)
    holding_all  = np.array([d.get("holding_total", d.get("holding_W", 0) + d.get("holding_R", 0))
                              for d in info_log], dtype=float)
    backorder_R  = np.array([d["backorder_R"] for d in info_log], dtype=float)
    ordering_all = np.array([d.get("order_cost_total",
                                   d.get("order_cost_W", 0) + d.get("order_cost_R", 0))
                              for d in info_log], dtype=float)

    # Upstream orders (for bullwhip — use the MOST upstream order quantity)
    a_up = np.array([d.get("a_E1", d.get("a_W", 0)) for d in info_log], dtype=float)

    total_demand  = float(demands.sum())
    total_backlog = float(backlog_R.sum())
    service_level = 1.0 - total_backlog / total_demand if total_demand > 0 else 1.0

    var_demand    = float(np.var(demands))
    var_upstream  = float(np.var(a_up))
    bullwhip      = (var_upstream / var_demand) if var_demand > 1e-9 else float("nan")

    fill_rate     = float((backlog_R == 0).mean())
    total_cost    = float(-rewards.sum())

    return {
        "total_reward":     float(rewards.sum()),
        "total_cost":       total_cost,
        "service_level":    float(service_level),
        "bullwhip_ratio":   float(bullwhip),
        "holding_cost":     float(holding_all.sum()),
        "backorder_cost":   float(backorder_R.sum()),
        "ordering_cost":    float(ordering_all.sum()),
        "fill_rate":        float(fill_rate),
        "total_demand":     total_demand,
        "total_backlog":    total_backlog,
    }


def compute_relative_improvement(agent_m: dict, baseline_name: str,
                                  baseline_m: dict) -> dict:
    """% improvement of agent over baseline. Positive = agent wins."""
    bc = baseline_m["total_cost"]
    ac = agent_m["total_cost"]
    cost_pct = (bc - ac) / abs(bc) * 100 if bc != 0 else 0.0

    bb = baseline_m.get("bullwhip_ratio", float("nan"))
    ab = agent_m.get("bullwhip_ratio", float("nan"))
    if bb and not np.isnan(bb) and bb > 1e-9:
        bw_pct = (bb - ab) / abs(bb) * 100
    else:
        bw_pct = float("nan")

    return {
        "vs_baseline":           baseline_name,
        "cost_reduction_pct":    float(cost_pct),
        "bullwhip_reduction_pct": float(bw_pct) if not np.isnan(bw_pct) else None,
        "service_level_delta":   float(agent_m["service_level"] -
                                        baseline_m["service_level"]),
    }


def ss_policy_params(demand_series, lead_time, z=1.65):
    """Derive (s, S) reorder point and order-up-to level."""
    avg_d = float(demand_series.mean())
    std_d = float(demand_series.std())
    s = avg_d * lead_time + z * std_d * np.sqrt(lead_time)
    S = s + avg_d
    return int(round(s)), int(round(S))


def save_summary(summary: dict, results_dir: str):
    path = Path(results_dir) / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  ✓ Summary → {path}")


def append_episode_log(record: dict, results_dir: str):
    path = Path(results_dir) / "experiment_log.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def print_table(metrics: dict, label: str, width: int = 32):
    print(f"\n  {'─'*52}")
    print(f"  {label:^52}")
    print(f"  {'─'*52}")
    for k, v in metrics.items():
        if isinstance(v, float):
            if any(x in k for x in ["pct", "level", "freq", "rate"]):
                print(f"  {k:<{width}} {v * 100:>10.2f}%")
            elif "ratio" in k:
                print(f"  {k:<{width}} {v:>10.4f}")
            else:
                print(f"  {k:<{width}} {v:>14,.1f}")
        else:
            print(f"  {k:<{width}} {str(v):>14}")
    print(f"  {'─'*52}")


def make_standard_plots(
    rewards_history: list,
    agent_info_log: list,
    baselines: dict,           # {label: info_log}
    experiment_name: str,
    plots_dir: str,
):
    """
    Generate the 4 standard plots for any experiment:
      1. training_curve.png
      2. inventory_trajectory.png  (first 90 days)
      3. bullwhip_comparison.png
      4. cost_breakdown.png
    """
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import pandas as pd
    except ImportError:
        print("  [Plots] matplotlib not available — skipping.")
        return

    pd_  = Path(plots_dir)
    pd_.mkdir(parents=True, exist_ok=True)

    # ── 1. Training curve ─────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(12, 5))
    w = 20
    smoothed = pd.Series(rewards_history).rolling(w, min_periods=1).mean()
    ax.plot(rewards_history, alpha=0.2, color="steelblue")
    ax.plot(smoothed, color="steelblue", lw=2, label=f"MA-{w}")
    ax.set_xlabel("Episode"); ax.set_ylabel("Total Episode Reward")
    ax.set_title(f"{experiment_name} — Training Curve")
    ax.legend(); plt.tight_layout()
    plt.savefig(pd_ / "training_curve.png", dpi=150); plt.close()
    print(f"  ✓ training_curve.png")

    # ── 2. Inventory trajectory ───────────────────────────────────────
    days = min(90, len(agent_info_log))
    n_axes = 2 + len(baselines)
    fig, axes = plt.subplots(3, 1, figsize=(14, 9), sharex=True)

    # Deepest node inventory
    inv_agent = [d.get("inv_R", d.get("inv_E3", 0)) for d in agent_info_log[:days]]
    demand_a  = [d["demand"] for d in agent_info_log[:days]]

    colors_b = ["darkorange", "seagreen", "crimson"]
    axes[0].plot(inv_agent, color="steelblue", label="Joint DDQN")
    for i, (lbl, log) in enumerate(baselines.items()):
        inv_b = [d.get("inv_R", d.get("inv_E3", 0)) for d in log[:days]]
        axes[0].plot(inv_b, ls="--", color=colors_b[i % len(colors_b)], label=lbl)
    axes[0].set_ylabel("Retailer Inventory"); axes[0].legend(fontsize=8)

    # Upstream inventory
    inv_up_agent = [d.get("inv_W", d.get("inv_E1", 0)) for d in agent_info_log[:days]]
    axes[1].plot(inv_up_agent, color="steelblue", label="Joint DDQN")
    for i, (lbl, log) in enumerate(baselines.items()):
        inv_b = [d.get("inv_W", d.get("inv_E1", 0)) for d in log[:days]]
        axes[1].plot(inv_b, ls="--", color=colors_b[i % len(colors_b)], label=lbl)
    axes[1].set_ylabel("Upstream Inventory"); axes[1].legend(fontsize=8)

    axes[2].fill_between(range(days), demand_a, alpha=0.4, color="gray", label="Demand")
    axes[2].set_ylabel("Demand"); axes[2].set_xlabel("Day"); axes[2].legend(fontsize=8)

    fig.suptitle(f"{experiment_name} — Inventory Trajectory (First 90 Days)")
    plt.tight_layout()
    plt.savefig(pd_ / "inventory_trajectory.png", dpi=150); plt.close()
    print(f"  ✓ inventory_trajectory.png")

    # ── 3. Bullwhip comparison ────────────────────────────────────────
    def bw(log):
        a_up = np.array([d.get("a_E1", d.get("a_W", 0)) for d in log], float)
        dem  = np.array([d["demand"] for d in log], float)
        vd = np.var(dem)
        return float(np.var(a_up) / vd) if vd > 1e-9 else float("nan")

    all_labels = ["Joint DDQN"] + list(baselines.keys())
    all_logs   = [agent_info_log] + list(baselines.values())
    all_bw     = [bw(lg) for lg in all_logs]
    colors_all = ["steelblue", "darkorange", "seagreen", "crimson"]

    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(all_labels, all_bw,
                  color=colors_all[:len(all_labels)], edgecolor="black", lw=0.8)
    ax.axhline(1.0, color="red", ls="--", lw=1.2, label="BW=1 (no amplification)")
    ax.set_ylabel("Bullwhip Ratio"); ax.legend()
    ax.set_title(f"{experiment_name} — Bullwhip Ratio")
    for bar, v in zip(bars, all_bw):
        if not np.isnan(v):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.02,
                    f"{v:.3f}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    plt.savefig(pd_ / "bullwhip_comparison.png", dpi=150); plt.close()
    print(f"  ✓ bullwhip_comparison.png")

    # ── 4. Cost breakdown ─────────────────────────────────────────────
    def costs(log):
        h  = sum(d.get("holding_total",
                        d.get("holding_W", 0) + d.get("holding_R", 0))
                 for d in log)
        bo = sum(d["backorder_R"] for d in log)
        oc = sum(d.get("order_cost_total",
                        d.get("order_cost_W", 0) + d.get("order_cost_R", 0))
                 for d in log)
        return h, bo, oc

    fig, ax = plt.subplots(figsize=(10, 6))
    cats   = ["Holding", "Backorder", "Order Fixed"]
    bottom = np.zeros(len(all_labels))
    palette = ["#4C72B0", "#DD8452", "#55A868"]
    for ci, cat in enumerate(cats):
        vals = [costs(lg)[ci] for lg in all_logs]
        ax.bar(all_labels, vals, bottom=bottom, label=cat,
               color=palette[ci], alpha=0.88)
        bottom += np.array(vals, float)
    ax.set_ylabel("Total Cost"); ax.legend()
    ax.set_title(f"{experiment_name} — Cost Breakdown")
    plt.tight_layout()
    plt.savefig(pd_ / "cost_breakdown.png", dpi=150); plt.close()
    print(f"  ✓ cost_breakdown.png")
