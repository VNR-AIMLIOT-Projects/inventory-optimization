"""
Experiment B1 Runner — State Representation Ablation
=====================================================
Compares Installation Stock (IS) vs Echelon Stock (ES) state on A1 env.
Usage: python3 run_experiment.py  |  python3 run_experiment.py --smoke-test
"""

import sys, os, argparse, json, time
import numpy as np
from pathlib import Path

HERE     = Path(__file__).parent
EXP_ROOT = HERE.parent
# Insert A1 first (lower priority), then shared on top (higher priority)
# so shared/metrics.py wins over A1's minimal metrics.py
sys.path.insert(0, str(EXP_ROOT / "A1_two_echelon_linear"))
sys.path.insert(0, str(EXP_ROOT / "shared"))

from demand    import generate_demand, prepare_env_data
from dqn_agent import DDQNAgent, DEVICE
from metrics   import (compute_all_metrics, compute_relative_improvement,
                       save_summary, append_episode_log, print_table,
                       make_standard_plots)
from env_two_echelon import TwoEchelonEnv

RESULTS = HERE / "results"
PLOTS   = HERE / "plots"
RESULTS.mkdir(exist_ok=True); PLOTS.mkdir(exist_ok=True)

CFG = dict(
    season="summer", episodes=500, val_seed=777, test_seed=999, train_base=1000,
    lead_time_W=3, lead_time_R=1,
    h_W=2.0, h_R=5.0, b_R=500., c_W=2., c_R=2.,
    n_actions_W=11, n_actions_R=11,
    gamma=0.98, tau=0.005, lr=1e-4,
    batch_size=256, learn_every=4, eps_start=1.0, eps_min=0.05,
    capacity=100_000, hidden=256,
)


# ── State builders ────────────────────────────────────────────────────────────

def get_is_state(env: TwoEchelonEnv) -> np.ndarray:
    """Installation Stock state — each node sees only its own inventory (A1 original)."""
    return env._get_state()   # uses the built-in state from A1 env


def get_es_state(env: TwoEchelonEnv) -> np.ndarray:
    """
    Echelon Stock state.
    Warehouse sees: inv_W + pipeline_W→R + inv_R  (total downstream coverage)
    Retailer sees: inv_R  (same as IS)
    Same 10-dim structure, but norm_inv_W and norm_pipeline_W are replaced
    by the echelon-stock aggregate.
    """
    if env.current_step >= len(env.data):
        return None
    row = env.data.iloc[env.current_step]
    avg_d = env.data["demand"].mean()

    # Echelon stock at E1 = own inv + pipeline_R (stock heading to R) + inv_R
    echelon_W = env.inv_W + sum(env.pipeline_R) + env.inv_R
    norm_echelon_W = np.log1p(echelon_W) / np.log1p(env.max_inv_W + env.max_inv_R)

    norm_pipeline_W = np.clip(sum(env.pipeline_W) / max(env.max_order_W, 1), 0, 2)
    norm_backlog_R  = np.clip(env.backlog_R / max(avg_d, 1), 0, 3)
    norm_inv_R      = np.log1p(env.inv_R) / np.log1p(env.max_inv_R)
    norm_pipeline_R = np.clip(sum(env.pipeline_R) / max(env.max_order_R, 1), 0, 2)
    norm_demand_prev = np.clip(env.last_demand / max(env.max_order_R, 1), 0, 1)
    from collections import deque
    ma3 = np.mean(list(env._demand_history))
    norm_demand_ma3 = np.clip(ma3 / max(env.max_order_R, 1), 0, 1)
    dow = int(row["day_of_week"])
    day_sin = np.sin(2 * np.pi * dow / 7)
    day_cos = np.cos(2 * np.pi * dow / 7)
    promo   = float(row["promo_flag"])

    return np.array([
        norm_echelon_W, norm_pipeline_W, norm_backlog_R,
        norm_inv_R, norm_pipeline_R, norm_demand_prev,
        norm_demand_ma3, day_sin, day_cos, promo,
    ], dtype=np.float32)


# ── Training helper ───────────────────────────────────────────────────────────

def make_env(df):
    return TwoEchelonEnv(
        df,
        lead_time_W=CFG["lead_time_W"], lead_time_R=CFG["lead_time_R"],
        h_W=CFG["h_W"], h_R=CFG["h_R"], b_R=CFG["b_R"],
        c_W=CFG["c_W"], c_R=CFG["c_R"],
        n_actions_W=CFG["n_actions_W"], n_actions_R=CFG["n_actions_R"],
    )


def greedy_eval(agent, df, state_fn):
    env = make_env(df)
    env.reset()
    state = state_fn(env)
    saved, agent.epsilon = agent.epsilon, 0.0
    total, info_log, done = 0.0, [], False
    zeros = np.zeros(env.state_size, dtype=np.float32)
    while not done:
        ns, r, done, info = env.step(agent.greedy_act(state))
        info_log.append(info); total += r
        state = state_fn(env) if ns is not None else zeros
    agent.epsilon = saved
    return total, info_log, env


def train_variant(label, state_fn, episodes, log_suffix):
    print("\n" + "="*62)
    print("  B1 Variant: {}".format(label))
    print("  Episodes: {}  |  Device: {}".format(episodes, DEVICE))
    print("="*62)

    ref_df  = prepare_env_data(generate_demand(CFG["season"], seed=CFG["train_base"]))
    ref_env = make_env(ref_df)
    agent   = DDQNAgent(
        ref_env.state_size, ref_env.action_size, episodes=episodes,
        lr=CFG["lr"], gamma=CFG["gamma"], tau=CFG["tau"],
        batch_size=CFG["batch_size"], learn_every=CFG["learn_every"],
        eps_start=CFG["eps_start"], eps_min=CFG["eps_min"],
        capacity=CFG["capacity"], hidden=CFG["hidden"],
    )
    val_df  = prepare_env_data(generate_demand(CFG["season"], seed=CFG["val_seed"]))
    rewards = []
    t0 = time.time()

    for ep in range(episodes):
        df    = prepare_env_data(generate_demand(CFG["season"], seed=CFG["train_base"] + ep))
        env   = make_env(df)
        env.reset()
        state = state_fn(env)
        ep_r, done = 0.0, False
        zeros = np.zeros(env.state_size, dtype=np.float32)
        while not done:
            a = agent.act(state)
            ns, r, done, info = env.step(a)
            ns_raw = state_fn(env) if ns is not None else zeros
            agent.step(state, a, r, ns_raw, done)
            state = ns_raw; ep_r += r
        agent.decay_epsilon()
        rewards.append(ep_r)

        if ep % 50 == 0 or ep == episodes - 1:
            ev_r, ev_log, ev_env = greedy_eval(agent, val_df, state_fn)
            agent.save_best(ev_r)
            bw   = ev_env.bullwhip_ratio()
            svc  = ev_env.service_level(ev_log)
            avg50 = np.mean(rewards[-50:])
            elapsed = time.time() - t0
            print("  [{}] Ep {:>4d}/{} | Train:{:>13,.0f} | "
                  "Eval:{:>13,.0f} | eps={:.3f} | BW={:.3f} | Svc={:.3f} | {:.0f}s".format(
                      label, ep, episodes, ep_r, ev_r, agent.epsilon, bw, svc, elapsed))
            append_episode_log({"episode": ep, "variant": label,
                                 "train_reward": float(ep_r), "avg50": float(avg50),
                                 "eval_reward": float(ev_r), "epsilon": float(agent.epsilon),
                                 "bullwhip": float(bw) if not np.isnan(bw) else None,
                                 "service_level": float(svc)}, RESULTS)

    agent.load_best()
    return agent, rewards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    eps = 50 if args.smoke_test else args.episodes

    json.dump({**CFG, "episodes": eps}, open(RESULTS / "config.json", "w"), indent=2)

    test_df = prepare_env_data(generate_demand(CFG["season"], seed=CFG["test_seed"]))

    # ── Train IS variant ─────────────────────────────────────────────────────
    agent_is, rewards_is = train_variant("IS (Installation Stock)", get_is_state, eps, "is")
    _, is_log, is_env = greedy_eval(agent_is, test_df, get_is_state)
    is_m = compute_all_metrics(is_log)
    print_table(is_m, "IS — Installation Stock")

    # ── Train ES variant ─────────────────────────────────────────────────────
    agent_es, rewards_es = train_variant("ES (Echelon Stock)", get_es_state, eps, "es")
    _, es_log, es_env = greedy_eval(agent_es, test_df, get_es_state)
    es_m = compute_all_metrics(es_log)
    print_table(es_m, "ES — Echelon Stock")

    # ── Compare ──────────────────────────────────────────────────────────────
    comp = compute_relative_improvement(es_m, "IS (baseline)", is_m)
    summary = {
        "experiment": "B1_state_ablation", "episodes": eps,
        "installation_stock": is_m,
        "echelon_stock": es_m,
        "es_vs_is": comp,
    }

    bw_str = "N/A" if not comp["bullwhip_reduction_pct"] else "{:+.1f}%".format(comp["bullwhip_reduction_pct"])
    print("\n" + "="*62 + "  B1 HEAD-TO-HEAD  " + "="*62)
    print("  ES vs IS  --  Cost D={:+.1f}%  BW D={}  Svc D={:+.4f}".format(
        comp["cost_reduction_pct"], bw_str, comp["service_level_delta"]))

    if not args.smoke_test:
        # Side-by-side training curve plot
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import pandas as pd

            fig, axes = plt.subplots(1, 2, figsize=(14, 5), sharey=True)
            for ax, rewards, lbl, col in [
                (axes[0], rewards_is, "IS (Installation Stock)", "steelblue"),
                (axes[1], rewards_es, "ES (Echelon Stock)", "seagreen"),
            ]:
                sm = pd.Series(rewards).rolling(20, min_periods=1).mean()
                ax.plot(rewards, alpha=0.2, color=col)
                ax.plot(sm, color=col, lw=2)
                ax.set_title(lbl); ax.set_xlabel("Episode"); ax.set_ylabel("Total Reward")
            fig.suptitle("B1 State Ablation - IS vs ES Training Curves")
            plt.tight_layout()
            plt.savefig(PLOTS / "training_curves_comparison.png", dpi=150)
            plt.close()
            print("  [OK] training_curves_comparison.png")

            # Head-to-head bar chart for key metrics
            metrics_to_plot = ["total_cost", "service_level", "bullwhip_ratio", "fill_rate"]
            fig, axes = plt.subplots(1, 4, figsize=(16, 5))
            for ax, m in zip(axes, metrics_to_plot):
                vals = [is_m[m], es_m[m]]
                bars = ax.bar(["IS", "ES"], vals, color=["steelblue", "seagreen"],
                              edgecolor="black", lw=0.8)
                ax.set_title(m.replace("_", " ").title())
                for bar, v in zip(bars, vals):
                    ax.text(bar.get_x() + bar.get_width()/2,
                            bar.get_height() * 1.01, f"{v:.3f}",
                            ha="center", va="bottom", fontsize=9)
            fig.suptitle("B1 State Ablation - IS vs ES Key Metrics")
            plt.tight_layout()
            plt.savefig(PLOTS / "metric_comparison.png", dpi=150)
            plt.close()
            print("  [OK] metric_comparison.png")
        except ImportError:
            pass

    save_summary(summary, RESULTS)
    print(f"\n  [OK] B1 complete -> {RESULTS}/summary.json")


if __name__ == "__main__":
    main()
