"""
Experiment A1 Runner — Two-Echelon Linear Joint DDQN
=====================================================
Usage
-----
    # Full run (500 episodes, all baselines, all plots):
    python run_experiment.py

    # Quick smoke test (50 episodes, no baselines):
    python run_experiment.py --episodes 50 --smoke-test

    # Resume logging (won't overwrite existing results):
    python run_experiment.py --episodes 500

Outputs
-------
    results/experiment_log.jsonl   — per-episode metrics
    results/summary.json           — final aggregated comparison table
    plots/training_curve.png
    plots/inventory_trajectory.png
    plots/bullwhip_comparison.png
    plots/cost_breakdown.png
"""

import sys, os, argparse, json, time
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
import copy
import random
from collections import deque
from pathlib import Path
from typing import Any

# ── Local imports ────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from env_two_echelon import (
    TwoEchelonEnv, generate_demand, prepare_env_data
)
from metrics_a1 import (
    compute_all_metrics, compute_relative_improvement,
    save_summary, append_episode_log, print_metrics_table
)

RESULTS_DIR = HERE / "results"
PLOTS_DIR   = HERE / "plots"
RESULTS_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)

# ── Experiment Config ────────────────────────────────────────────────────────
CONFIG = {
    "season_type":   "summer",
    "num_days":      365,
    "train_episodes":500,
    "val_seed":      777,
    "test_seed":     999,
    "train_seed_base": 1000,
    # Environment — v2 tuned config (fixes service-level underperformance from run 1)
    "lead_time_W":   3,
    "lead_time_R":   1,
    "h_W":           2.0,
    "h_R":           5.0,
    "b_R":           500.0,   # raised: 100→500 to enforce service level
    "c_W":           2.0,    # lowered: 10→2 to encourage warehouse ordering
    "c_R":           2.0,    # lowered: 10→2
    "n_actions_W":   11,
    "n_actions_R":   11,
    # Agent
    "gamma":         0.98,
    "tau":           0.005,
    "lr":            1e-4,
    "epsilon_start": 1.0,
    "epsilon_min":   0.05,
    "decay_type":    "exponential",
    "batch_size":    256,
    "learn_every":   4,
    "replay_capacity": 100_000,
}

# Device
_device = torch.device(
    "mps"  if torch.backends.mps.is_available() else
    "cuda" if torch.cuda.is_available()         else
    "cpu"
)
print(f"[A1] Device: {_device}")


# ── Joint DDQN Network ───────────────────────────────────────────────────────

class JointDQN(nn.Module):
    """
    DDQN for the joint 2-echelon action space.
    Input:  10-dim state vector
    Output: (n_W × n_R) Q-values (one per joint action)
    """
    def __init__(self, state_size: int, action_size: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_size, 256), nn.ReLU(),
            nn.Linear(256, 256),        nn.ReLU(),
            nn.Linear(256, 128),        nn.ReLU(),
            nn.Linear(128, action_size)
        )

    def forward(self, x):
        return self.net(x)


class ReplayBuffer:
    """Experience replay with running Welford reward normalization."""
    def __init__(self, capacity: int):
        self.buf = deque(maxlen=capacity)
        self._n, self._mean, self._m2 = 0, 0.0, 0.0

    def push(self, s, a, r, s2, done):
        self.buf.append((s, a, r, s2, done))
        self._n += 1
        d = r - self._mean; self._mean += d / self._n
        self._m2 += d * (r - self._mean)

    @property
    def std(self):
        return max(np.sqrt(self._m2 / max(self._n, 1)), 1e-6)

    def sample(self, bs):
        batch = random.sample(self.buf, bs)
        s, a, r, s2, d = zip(*batch)
        r_norm = (np.array(r, np.float32) - self._mean) / self.std
        return (
            torch.FloatTensor(np.array(s)).to(_device),
            torch.LongTensor(a).to(_device),
            torch.FloatTensor(r_norm).to(_device),
            torch.FloatTensor(np.array(s2)).to(_device),
            torch.FloatTensor(d).to(_device),
        )

    def __len__(self):
        return len(self.buf)


class JointDDQNAgent:
    """
    Double-DQN agent for the joint 2-echelon action space.
    Identical algorithmic structure to Replenix's DQNAgent (dqn.py):
      - Soft Polyak target updates
      - Welford reward normalization in replay buffer
      - Exponential epsilon decay
      - Huber loss + gradient clipping
    """
    def __init__(self, state_size: int, action_size: int,
                 cfg: dict = CONFIG):
        self.action_size = action_size
        self.gamma       = cfg["gamma"]
        self.tau         = cfg["tau"]
        self.learn_every = cfg["learn_every"]
        self.batch_size  = cfg["batch_size"]
        self._step       = 0

        episodes = cfg["train_episodes"]
        self.epsilon   = cfg["epsilon_start"]
        self.eps_min   = cfg["epsilon_min"]
        self.eps_decay = (self.eps_min / self.epsilon) ** (1.0 / max(episodes, 1))

        self.policy = JointDQN(state_size, action_size).to(_device)
        self.target = JointDQN(state_size, action_size).to(_device)
        self.target.load_state_dict(self.policy.state_dict())
        self.target.eval()

        self.opt = optim.Adam(self.policy.parameters(), lr=cfg["lr"])
        from torch.optim.lr_scheduler import StepLR
        steps_per_ep = cfg["num_days"]
        self.scheduler = StepLR(
            self.opt,
            step_size=max(1, 300 * steps_per_ep // self.learn_every),
            gamma=0.5
        )
        self.buf     = ReplayBuffer(cfg["replay_capacity"])
        self._best   = None
        self._best_eval = -np.inf

    def act(self, state: np.ndarray) -> int:
        """Epsilon-greedy action selection."""
        if random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        s = torch.FloatTensor(state).unsqueeze(0).to(_device)
        with torch.inference_mode():
            return self.policy(s).argmax().item()

    def learn(self) -> None:
        """Double-DQN update step (runs every learn_every steps)."""
        self._step += 1
        if self._step % self.learn_every or len(self.buf) < self.batch_size:
            return

        s, a, r, s2, d = self.buf.sample(self.batch_size)

        q = self.policy(s).gather(1, a.unsqueeze(1)).squeeze()
        with torch.no_grad():
            best_a = self.policy(s2).argmax(1, keepdim=True)
            q_next = self.target(s2).gather(1, best_a).squeeze()
            target = r + self.gamma * q_next * (1 - d)

        loss = nn.SmoothL1Loss()(q, target)
        self.opt.zero_grad()
        loss.backward()
        nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
        self.opt.step()
        self.scheduler.step()

        # Soft Polyak target update
        for tp, pp in zip(self.target.parameters(), self.policy.parameters()):
            tp.data.copy_(self.tau * pp.data + (1 - self.tau) * tp.data)

    def decay_epsilon(self):
        self.epsilon = max(self.eps_min, self.epsilon * self.eps_decay)

    def save_best(self, eval_reward: float):
        if eval_reward > self._best_eval:
            self._best_eval = eval_reward
            self._best = copy.deepcopy(self.policy.state_dict())

    def load_best(self):
        if self._best:
            self.policy.load_state_dict(self._best)
            self.target.load_state_dict(self._best)


# ── Greedy Evaluation ────────────────────────────────────────────────────────

def greedy_eval(agent: JointDDQNAgent, env_data: pd.DataFrame,
                cfg: dict) -> tuple:
    """Run one epsilon=0 episode. Returns (total_reward, info_log)."""
    env = TwoEchelonEnv(
        env_data,
        lead_time_W=cfg["lead_time_W"], lead_time_R=cfg["lead_time_R"],
        h_W=cfg["h_W"], h_R=cfg["h_R"], b_R=cfg["b_R"],
        c_W=cfg["c_W"], c_R=cfg["c_R"],
        n_actions_W=cfg["n_actions_W"], n_actions_R=cfg["n_actions_R"],
    )
    state = env.reset()
    saved_eps = agent.epsilon
    agent.epsilon = 0.0
    total_reward, info_log, done = 0.0, [], False

    while not done:
        action = agent.act(state)
        next_state, reward, done, info = env.step(action)
        info_log.append(info)
        total_reward += reward
        state = next_state if next_state is not None else np.zeros(env.state_size)

    agent.epsilon = saved_eps
    return total_reward, info_log, env


# ── Main Training Loop ───────────────────────────────────────────────────────

def train(cfg: dict[str, Any], episodes: int) -> tuple[JointDDQNAgent, list[float]]:
    """
    Train the Joint DDQN agent.

    Each episode uses a fresh demand stream (different seed) to prevent
    overfitting to one specific demand pattern.
    """
    season = cfg["season_type"]

    # Build reference env (to detect state/action sizes)
    ref_df  = prepare_env_data(
        generate_demand(season, seed=cfg["train_seed_base"]), season)
    ref_env = TwoEchelonEnv(
        ref_df,
        lead_time_W=cfg["lead_time_W"], lead_time_R=cfg["lead_time_R"],
        h_W=cfg["h_W"], h_R=cfg["h_R"], b_R=cfg["b_R"],
        c_W=cfg["c_W"], c_R=cfg["c_R"],
        n_actions_W=cfg["n_actions_W"], n_actions_R=cfg["n_actions_R"],
    )
    state_size  = ref_env.state_size         # 10
    action_size = ref_env.action_size        # 121

    print(f"\n{'='*60}")
    print(f"  Experiment A1: Joint DDQN — Two-Echelon Linear")
    print(f"{'='*60}")
    print(f"  State dims   : {state_size}")
    print(f"  Action dims  : {action_size}  ({cfg['n_actions_W']}×{cfg['n_actions_R']})")
    print(f"  Episodes     : {episodes}")
    print(f"  Device       : {_device}")
    print(f"  Max order W  : {ref_env.max_order_W}")
    print(f"  Max order R  : {ref_env.max_order_R}")
    print(f"{'='*60}\n")

    agent = JointDDQNAgent(state_size, action_size, cfg)

    # Validation data (fixed for honest checkpointing)
    val_df = prepare_env_data(
        generate_demand(season, seed=cfg["val_seed"]), season)

    rewards_history = []
    start_time = time.time()

    for ep in range(episodes):
        # Fresh demand per episode
        df = prepare_env_data(
            generate_demand(season, seed=cfg["train_seed_base"] + ep), season)
        env = TwoEchelonEnv(
            df,
            lead_time_W=cfg["lead_time_W"], lead_time_R=cfg["lead_time_R"],
            h_W=cfg["h_W"], h_R=cfg["h_R"], b_R=cfg["b_R"],
            c_W=cfg["c_W"], c_R=cfg["c_R"],
            n_actions_W=cfg["n_actions_W"], n_actions_R=cfg["n_actions_R"],
        )
        state = env.reset()
        ep_reward, done = 0.0, False
        zeros = np.zeros(state_size, dtype=np.float32)

        while not done:
            action = agent.act(state)
            next_state, reward, done, info = env.step(action)
            ns = next_state if next_state is not None else zeros
            agent.buf.push(state, action, reward, ns, float(done))
            agent.learn()
            state = ns
            ep_reward += reward

        agent.decay_epsilon()
        rewards_history.append(ep_reward)

        # Greedy eval checkpoint every 50 episodes
        if ep % 50 == 0 or ep == episodes - 1:
            eval_reward, eval_log, eval_env = greedy_eval(agent, val_df, cfg)
            agent.save_best(eval_reward)
            bw  = eval_env.bullwhip_ratio()
            svc = eval_env.service_level(eval_log)

            avg50 = np.mean(rewards_history[-50:])
            elapsed = time.time() - start_time
            print(
                f"  Ep {ep:>4d}/{episodes} | "
                f"Train: {ep_reward:>12,.0f} | "
                f"Avg50: {avg50:>12,.0f} | "
                f"Eval: {eval_reward:>12,.0f} | "
                f"eps={agent.epsilon:.3f} | "
                f"BW={bw:.3f} | "
                f"SvcLv={svc:.3f} | "
                f"{elapsed:.0f}s"
            )

            # Append to log
            append_episode_log({
                "episode":       ep,
                "train_reward":  float(ep_reward),
                "avg50":         float(avg50),
                "eval_reward":   float(eval_reward),
                "epsilon":       float(agent.epsilon),
                "bullwhip":      float(bw) if not np.isnan(bw) else None,
                "service_level": float(svc),
                "elapsed_s":     float(elapsed),
            }, RESULTS_DIR)

    print(f"\n  Training complete. Best eval: {agent._best_eval:,.0f}")
    agent.load_best()
    return agent, rewards_history


# ── Plotting ─────────────────────────────────────────────────────────────────

def make_plots(rewards_history, joint_log, ss_log, oracle_log, cfg):
    """Generate all experiment plots and save to plots/ directory."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [Plots] matplotlib not available — skipping plots.")
        return

    # 1. Training curve
    fig, ax = plt.subplots(figsize=(12, 5))
    window = 20
    smoothed = pd.Series(rewards_history).rolling(window, min_periods=1).mean()
    ax.plot(rewards_history, alpha=0.3, color="steelblue", label="Episode reward")
    ax.plot(smoothed, color="steelblue", lw=2, label=f"MA-{window}")
    ax.set_xlabel("Episode"); ax.set_ylabel("Total Reward")
    ax.set_title("Experiment A1 — Joint DDQN Training Curve (2-Echelon)")
    ax.legend(); plt.tight_layout()
    plt.savefig(PLOTS_DIR / "training_curve.png", dpi=150)
    plt.close()
    print(f"  [OK] Training curve -> {PLOTS_DIR / 'training_curve.png'}")

    # 2. Inventory trajectory (first 90 days)
    days = min(90, len(joint_log))
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    inv_W_joint = [d["inv_W"] for d in joint_log[:days]]
    inv_R_joint = [d["inv_R"] for d in joint_log[:days]]
    demand_j    = [d["demand"] for d in joint_log[:days]]

    inv_W_ss    = [d["inv_W"] for d in ss_log[:days]]
    inv_R_ss    = [d["inv_R"] for d in ss_log[:days]]

    axes[0].plot(inv_W_joint, label="Joint DDQN", color="steelblue")
    axes[0].plot(inv_W_ss,    label="(s,S)",      color="darkorange", ls="--")
    axes[0].set_ylabel("Warehouse Inventory"); axes[0].legend()

    axes[1].plot(inv_R_joint, label="Joint DDQN", color="steelblue")
    axes[1].plot(inv_R_ss,    label="(s,S)",      color="darkorange", ls="--")
    axes[1].set_ylabel("Retailer Inventory"); axes[1].legend()

    axes[2].fill_between(range(days), demand_j, alpha=0.4,
                          color="gray", label="Customer Demand")
    axes[2].set_ylabel("Demand"); axes[2].set_xlabel("Day")
    axes[2].legend()

    fig.suptitle("Experiment A1 — Inventory Trajectory (First 90 Days)")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "inventory_trajectory.png", dpi=150)
    plt.close()
    print(f"  [OK] Inventory trajectory -> {PLOTS_DIR / 'inventory_trajectory.png'}")

    # 3. Bullwhip comparison
    def order_variance_ratio(log):
        orders = np.array([d["a_W"] for d in log], dtype=float)
        demand = np.array([d["demand"] for d in log], dtype=float)
        vd = np.var(demand)
        return np.var(orders) / vd if vd > 1e-9 else float("nan")

    bw_j = order_variance_ratio(joint_log)
    bw_s = order_variance_ratio(ss_log)
    bw_o = order_variance_ratio(oracle_log) if oracle_log else None

    labels  = ["Joint DDQN", "(s,S)", "Oracle"]
    values  = [bw_j, bw_s, bw_o if bw_o else 0]
    colors  = ["steelblue", "darkorange", "seagreen"]
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(labels, values, color=colors, edgecolor="black", linewidth=0.8)
    ax.axhline(1.0, color="red", ls="--", lw=1.2, label="BW=1 (no amplification)")
    ax.set_ylabel("Bullwhip Ratio")
    ax.set_title("Experiment A1 — Bullwhip Ratio Comparison")
    ax.legend()
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{v:.3f}", ha="center", va="bottom", fontsize=10)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "bullwhip_comparison.png", dpi=150)
    plt.close()
    print(f"  [OK] Bullwhip comparison -> {PLOTS_DIR / 'bullwhip_comparison.png'}")

    # 4. Cost breakdown stacked bar
    def cost_vec(log):
        hW = sum(d["holding_W"]   for d in log)
        hR = sum(d["holding_R"]   for d in log)
        bo = sum(d["backorder_R"] for d in log)
        oc = sum(d["order_cost_W"] + d["order_cost_R"] for d in log)
        return hW, hR, bo, oc

    j = cost_vec(joint_log)
    s = cost_vec(ss_log)
    o = cost_vec(oracle_log) if oracle_log else (0,0,0,0)

    cats  = ["Hold W", "Hold R", "Backorder", "Order Fixed"]
    x     = np.arange(3)
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 6))
    bottoms_j = np.zeros(3)
    for i, cat in enumerate(cats):
        vals = [j[i], s[i], o[i]]
        ax.bar(["Joint DDQN", "(s,S)", "Oracle"], vals, bottom=bottoms_j,
               label=cat, alpha=0.85)
        bottoms_j += np.array(vals)

    ax.set_ylabel("Total Cost")
    ax.set_title("Experiment A1 — Cost Breakdown by Policy")
    ax.legend()
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "cost_breakdown.png", dpi=150)
    plt.close()
    print(f"  [OK] Cost breakdown -> {PLOTS_DIR / 'cost_breakdown.png'}")


# ── Entry Point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Experiment A1: Joint DDQN 2-Echelon")
    parser.add_argument("--episodes",   type=int, default=500,
                        help="Number of training episodes (default: 500)")
    parser.add_argument("--smoke-test", action="store_true",
                        help="Quick 50-episode run without baselines")
    parser.add_argument("--no-baselines", action="store_true",
                        help="Skip baseline runs")
    args = parser.parse_args()

    cfg: dict[str, Any] = {**CONFIG}
    episodes = args.episodes if not args.smoke_test else 50

    print(f"\n{'#'*60}")
    print(f"  EXPERIMENT A1 - Two-Echelon Linear Joint DDQN")
    print(f"  Smoke test: {args.smoke_test}")
    print(f"  Episodes:   {episodes}")
    print(f"{'#'*60}")

    # ── Save config ──────────────────────────────────────────────────────────
    cfg_path = RESULTS_DIR / "config.json"
    with open(cfg_path, "w") as f:
        json.dump({**cfg, "episodes": episodes, "smoke_test": args.smoke_test}, f, indent=2)
    print(f"  Config saved -> {cfg_path}")

    # ── Train Joint DDQN ─────────────────────────────────────────────────────
    agent, rewards_history = train(cfg, episodes)

    # ── Evaluate on test set ─────────────────────────────────────────────────
    season = cfg["season_type"]
    test_df = prepare_env_data(
        generate_demand(season, seed=cfg["test_seed"]), season)

    print("\n  Evaluating Joint DDQN on test demand (seed=999)...")
    joint_reward, joint_log, joint_env = greedy_eval(agent, test_df, cfg)
    joint_metrics = compute_all_metrics(joint_log, joint_env)
    print_metrics_table(joint_metrics, "Joint DDQN (A1)")

    summary = {
        "experiment": "A1_two_echelon_linear",
        "episodes":   episodes,
        "joint_ddqn": joint_metrics,
        "comparisons": [],
    }

    # ── Run Baselines ────────────────────────────────────────────────────────
    if not args.smoke_test and not args.no_baselines:

        # 1. (s,S) baseline
        print("\n  Running (s,S) baseline...")
        ss_env = TwoEchelonEnv(
            test_df,
            lead_time_W=cfg["lead_time_W"], lead_time_R=cfg["lead_time_R"],
            h_W=cfg["h_W"], h_R=cfg["h_R"], b_R=cfg["b_R"],
            c_W=cfg["c_W"], c_R=cfg["c_R"],
        )
        from baselines import run_ss_baseline
        ss_reward, ss_log, ss_extra = run_ss_baseline(ss_env)
        ss_metrics = compute_all_metrics(ss_log)
        ss_metrics.update(ss_extra)
        print_metrics_table(ss_metrics, "(s,S) Policy")

        vs_ss = compute_relative_improvement(joint_metrics, "(s,S)", ss_metrics)
        summary["ss_policy"]  = ss_metrics
        summary["comparisons"].append(vs_ss)

        # 2. Oracle baseline
        print("\n  Running Oracle (5-day lookahead) baseline...")
        oracle_env = TwoEchelonEnv(
            test_df,
            lead_time_W=cfg["lead_time_W"], lead_time_R=cfg["lead_time_R"],
            h_W=cfg["h_W"], h_R=cfg["h_R"], b_R=cfg["b_R"],
            c_W=cfg["c_W"], c_R=cfg["c_R"],
        )
        from baselines import run_oracle_baseline
        oracle_reward, oracle_log, oracle_extra = run_oracle_baseline(oracle_env)
        oracle_metrics = compute_all_metrics(oracle_log)
        oracle_metrics.update(oracle_extra)
        print_metrics_table(oracle_metrics, "Oracle (5-day)")

        vs_oracle = compute_relative_improvement(joint_metrics, "Oracle", oracle_metrics)
        summary["oracle"]     = oracle_metrics
        summary["comparisons"].append(vs_oracle)

        # 3. Independent DDQN baseline
        print("\n  Running Independent DDQN baseline...")
        from baselines import run_independent_ddqn_baseline
        ind_reward, ind_log, ind_extra = run_independent_ddqn_baseline(
            test_df, episodes=min(episodes, 200), season_type=season,
            test_seed=cfg["test_seed"]
        )
        ind_metrics = compute_all_metrics(ind_log)
        ind_metrics.update(ind_extra)
        print_metrics_table(ind_metrics, "Independent DDQN (Replenix-style)")

        vs_ind = compute_relative_improvement(joint_metrics, "Indep. DDQN", ind_metrics)
        summary["independent_ddqn"] = ind_metrics
        summary["comparisons"].append(vs_ind)

        # ── Print Comparison Table ────────────────────────────────────────
        print(f"\n{'='*60}")
        print(f"  FINAL RESULTS - Experiment A1")
        print(f"{'='*60}")
        for comp in summary["comparisons"]:
            print(f"\n  vs {comp['vs_baseline']}:")
            print(f"    Cost reduction  : {comp['cost_reduction_pct']:+.1f}%")
            print(f"    Bullwhip reduc. : {comp['bullwhip_reduction_pct']:+.1f}%")
            print(f"    Service Δ       : {comp['service_level_delta']:+.4f}")
        print(f"{'='*60}")

        # Make plots with baselines
        make_plots(rewards_history, joint_log, ss_log, oracle_log, cfg)

    else:
        # Smoke test — plots without baselines
        make_plots(rewards_history, joint_log, joint_log, [], cfg)

    # ── Save final summary ────────────────────────────────────────────────
    save_summary(summary, RESULTS_DIR)
    print(f"\n  [OK] Experiment A1 complete.")
    print(f"  Results -> {RESULTS_DIR}/summary.json")
    print(f"  Plots   -> {PLOTS_DIR}/")


if __name__ == "__main__":
    main()
