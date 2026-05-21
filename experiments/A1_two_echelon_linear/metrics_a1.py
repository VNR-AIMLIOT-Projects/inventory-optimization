"""
Metric Computation — Experiment A1
====================================
All experiment metrics are computed here from the info_log list
returned by TwoEchelonEnv.step() calls.
"""

import numpy as np
import json
from pathlib import Path


# ──────────────────────────────────────────────────────────────────────────────

def compute_all_metrics(info_log: list, env=None) -> dict:
    """
    Compute all evaluation metrics from a completed episode's info log.

    Parameters
    ----------
    info_log : list[dict]  — per-step dicts returned by env.step()
    env      : TwoEchelonEnv  — optional; used for bullwhip_ratio if provided

    Returns
    -------
    dict of metric_name → value
    """
    demands     = np.array([d["demand"]     for d in info_log], dtype=float)
    inv_W       = np.array([d["inv_W"]      for d in info_log], dtype=float)
    inv_R       = np.array([d["inv_R"]      for d in info_log], dtype=float)
    backlog_R   = np.array([d["backlog_R"]  for d in info_log], dtype=float)
    a_W         = np.array([d["a_W"]        for d in info_log], dtype=float)
    a_R         = np.array([d["a_R"]        for d in info_log], dtype=float)
    holding_W   = np.array([d["holding_W"]  for d in info_log], dtype=float)
    holding_R   = np.array([d["holding_R"]  for d in info_log], dtype=float)
    backorder_R = np.array([d["backorder_R"]for d in info_log], dtype=float)
    order_cW    = np.array([d["order_cost_W"]for d in info_log], dtype=float)
    order_cR    = np.array([d["order_cost_R"]for d in info_log], dtype=float)
    rewards     = np.array([d["reward"]     for d in info_log], dtype=float)

    total_demand  = demands.sum()
    total_backlog = backlog_R.sum()

    # Service level
    service_level = 1.0 - (total_backlog / total_demand) if total_demand > 0 else 1.0

    # Bullwhip ratio
    var_demand = np.var(demands)
    var_w_orders = np.var(a_W)
    bullwhip = float(var_w_orders / var_demand) if var_demand > 1e-9 else float("nan")

    # Cost breakdown
    total_cost    = -(rewards.sum())   # cost = -reward
    holding_cost  = holding_W.sum() + holding_R.sum()
    backorder_cost= backorder_R.sum()
    ordering_cost = order_cW.sum() + order_cR.sum()

    # Inventory stats
    avg_inv_W    = inv_W.mean()
    avg_inv_R    = inv_R.mean()
    avg_inv_total= (inv_W + inv_R).mean()

    # Order frequency (how often orders are placed)
    order_freq_W = (a_W > 0).mean()
    order_freq_R = (a_R > 0).mean()

    # Fill rate: fraction of retailer order days where a_R > 0 was fully fulfilled
    # (proxy: days where no backlog was created)
    no_stockout_days = (backlog_R == 0).sum()
    fill_rate = float(no_stockout_days / len(backlog_R))

    return {
        # Primary
        "total_reward":        float(rewards.sum()),
        "total_cost":          float(total_cost),
        "service_level":       float(service_level),
        "bullwhip_ratio":      float(bullwhip),

        # Cost breakdown
        "holding_cost_W":      float(holding_W.sum()),
        "holding_cost_R":      float(holding_R.sum()),
        "backorder_cost":      float(backorder_cost),
        "ordering_cost_W":     float(order_cW.sum()),
        "ordering_cost_R":     float(order_cR.sum()),

        # Inventory averages
        "avg_inv_W":           float(avg_inv_W),
        "avg_inv_R":           float(avg_inv_R),
        "avg_inv_total":       float(avg_inv_total),

        # Operations
        "order_freq_W":        float(order_freq_W),
        "order_freq_R":        float(order_freq_R),
        "fill_rate":           float(fill_rate),
        "total_demand":        float(total_demand),
        "total_backlog":       float(total_backlog),
    }


def compute_relative_improvement(joint_metrics: dict,
                                  baseline_name: str,
                                  baseline_metrics: dict) -> dict:
    """
    Compute % improvement of Joint DDQN over a given baseline.

    Positive = Joint DDQN is better.
    """
    j_cost = joint_metrics["total_cost"]
    b_cost = baseline_metrics["total_cost"]

    cost_reduction_pct = (b_cost - j_cost) / abs(b_cost) * 100 if b_cost != 0 else 0.0

    j_bw = joint_metrics["bullwhip_ratio"]
    b_bw = baseline_metrics["bullwhip_ratio"]
    bw_reduction_pct = (b_bw - j_bw) / abs(b_bw) * 100 if (b_bw and b_bw > 1e-9) else 0.0

    return {
        "vs_baseline":          baseline_name,
        "cost_reduction_pct":   float(cost_reduction_pct),
        "bullwhip_reduction_pct": float(bw_reduction_pct),
        "service_level_delta":  float(joint_metrics["service_level"] -
                                      baseline_metrics["service_level"]),
    }


def save_summary(summary: dict, output_dir: str | Path) -> None:
    """Save the final results summary to JSON."""
    path = Path(output_dir) / "summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"  [OK] Summary saved -> {path}")


def append_episode_log(record: dict, output_dir: str | Path) -> None:
    """Append a single episode record to the JSONL training log."""
    path = Path(output_dir) / "experiment_log.jsonl"
    with open(path, "a") as f:
        f.write(json.dumps(record) + "\n")


def print_metrics_table(metrics: dict, label: str) -> None:
    """Pretty-print a metrics dict as a table."""
    w = 32
    print(f"\n  {'-'*50}")
    print(f"  {label:^50}")
    print(f"  {'-'*50}")
    for k, v in metrics.items():
        if isinstance(v, float):
            if "pct" in k or "level" in k or "freq" in k or "rate" in k:
                print(f"  {k:<{w}} {v:>10.2f}%")
            elif "ratio" in k:
                print(f"  {k:<{w}} {v:>10.4f}")
            else:
                print(f"  {k:<{w}} {v:>12,.1f}")
        else:
            print(f"  {k:<{w}} {str(v):>12}")
    print(f"  {'-'*50}")
