"""
Experiment A4 Runner — Transfer Learning Across Seasons
======================================================
Usage:
    # Full run:
    py run_experiment.py

    # Smoke test:
    py run_experiment.py --smoke-test
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

# ── Local imports ────────────────────────────────────────────────────────────
HERE = Path(__file__).parent
SHARED = HERE.parent / "shared"
A1_DIR = HERE.parent / "A1_two_echelon_linear"

sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(A1_DIR))

from env_two_echelon import TwoEchelonEnv, generate_demand, prepare_env_data
from metrics_a1 import (
    compute_all_metrics, compute_relative_improvement,
    save_summary, append_episode_log, print_metrics_table
)
from baselines import run_ss_baseline

RESULTS_DIR = HERE / "results"
PLOTS_DIR   = HERE / "plots"
RESULTS_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)

# Device Selection
_device = torch.device(
    "mps"  if torch.backends.mps.is_available() else
    "cuda" if torch.cuda.is_available()         else
    "cpu"
)
print(f"[A4] Device: {_device}")

# ── Joint DDQN Network (Matched with A1) ──────────────────────────────────────

class JointDQN(nn.Module):
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
    def __init__(self, capacity: int):
        self.buf = deque(maxlen=capacity)
        self._n, self._mean, self._m2 = 0, 0.0, 0.0

    def push(self, s, a, r, s2, done):
        self.buf.append((s, a, r, s2, done))
        self._n += 1
        d = r - self._mean
        self._mean += d / self._n
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
    def __init__(self, state_size: int, action_size: int,
                 lr=1e-4, gamma=0.98, tau=0.005, batch_size=256,
                 learn_every=4, replay_capacity=100_000,
                 epsilon_start=1.0, epsilon_min=0.05, episodes=300):
        self.action_size = action_size
        self.gamma       = gamma
        self.tau         = tau
        self.learn_every = learn_every
        self.batch_size  = batch_size
        self._step       = 0

        self.epsilon   = epsilon_start
        self.eps_min   = epsilon_min
        self.eps_decay = (self.eps_min / self.epsilon) ** (1.0 / max(episodes, 1))

        self.policy = JointDQN(state_size, action_size).to(_device)
        self.target = JointDQN(state_size, action_size).to(_device)
        self.target.load_state_dict(self.policy.state_dict())
        self.target.eval()

        self.opt = optim.Adam(self.policy.parameters(), lr=lr)
        from torch.optim.lr_scheduler import StepLR
        self.scheduler = StepLR(self.opt, step_size=max(1, 300 * 365 // self.learn_every), gamma=0.5)
        self.buf     = ReplayBuffer(replay_capacity)
        self._best   = None
        self._best_eval = -np.inf

    def act(self, state: np.ndarray) -> int:
        if random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        s = torch.FloatTensor(state).unsqueeze(0).to(_device)
        with torch.inference_mode():
            return self.policy(s).argmax().item()

    def learn(self) -> None:
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

        # Polyak target update
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
                max_order_W: int, max_order_R: int, season: str) -> tuple:
    env = TwoEchelonEnv(
        env_data,
        lead_time_W=3, lead_time_R=1,
        h_W=2.0, h_R=5.0, b_R=500.0,
        c_W=2.0, c_R=2.0,
        n_actions_W=11, n_actions_R=11,
        max_order_W=max_order_W, max_order_R=max_order_R
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


# ── Core Training Function ───────────────────────────────────────────────────

def train_agent(episodes: int, season: str, label: str,
                max_order_W: int | None = None, max_order_R: int | None = None,
                pre_trained_weights: dict | None = None, epsilon_start: float = 1.0) -> tuple:
    """
    Trains a Joint DDQN Agent on the specified season.
    If pre_trained_weights is provided, the model starts with those weights.
    """
    # 1. Determine action space bounds on Summer if not provided
    ref_df = prepare_env_data(generate_demand(season, seed=1000), season)
    ref_env = TwoEchelonEnv(
        ref_df,
        lead_time_W=3, lead_time_R=1,
        h_W=2.0, h_R=5.0, b_R=500.0,
        c_W=2.0, c_R=2.0,
        n_actions_W=11, n_actions_R=11,
        max_order_W=max_order_W, max_order_R=max_order_R
    )
    # Lock quantities
    actual_max_W = ref_env.max_order_W
    actual_max_R = ref_env.max_order_R

    state_size = ref_env.state_size   # 10
    action_size = ref_env.action_size # 121

    agent = JointDDQNAgent(
        state_size, action_size,
        lr=1e-4, gamma=0.98, tau=0.005, batch_size=256,
        learn_every=4, replay_capacity=100_000,
        epsilon_start=epsilon_start, epsilon_min=0.05, episodes=episodes
    )

    if pre_trained_weights is not None:
        print(f"  [{label}] Loading pre-trained source weights...")
        agent.policy.load_state_dict(copy.deepcopy(pre_trained_weights))
        agent.target.load_state_dict(copy.deepcopy(pre_trained_weights))

    val_df = prepare_env_data(generate_demand(season, seed=777), season)
    rewards_history = []
    val_rewards_history = []
    start_time = time.time()

    for ep in range(episodes):
        df = prepare_env_data(generate_demand(season, seed=1000 + ep), season)
        env = TwoEchelonEnv(
            df,
            lead_time_W=3, lead_time_R=1,
            h_W=2.0, h_R=5.0, b_R=500.0,
            c_W=2.0, c_R=2.0,
            n_actions_W=11, n_actions_R=11,
            max_order_W=actual_max_W, max_order_R=actual_max_R
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

        # Checkpoint validation reward
        eval_reward, eval_log, eval_env = greedy_eval(agent, val_df, actual_max_W, actual_max_R, season)
        agent.save_best(eval_reward)
        val_rewards_history.append(eval_reward)

        # Console print every 10% of training or 50 episodes
        print_interval = max(1, episodes // 10)
        if ep % print_interval == 0 or ep == episodes - 1:
            bw = eval_env.bullwhip_ratio()
            svc = eval_env.service_level(eval_log)
            print(f"    Ep {ep:>4d}/{episodes} | Train Reward: {ep_reward:>10,.0f} | Val Reward: {eval_reward:>10,.0f} | SL: {svc:.3f} | BW: {bw:.3f} | Epsilon: {agent.epsilon:.3f}")

    print(f"  [{label}] Training complete. Best validation reward: {agent._best_eval:,.0f}")
    agent.load_best()
    return agent, rewards_history, val_rewards_history, actual_max_W, actual_max_R


# ── Plotting ─────────────────────────────────────────────────────────────────

def generate_plots(val_curves: dict, test_logs: dict, test_envs: dict,
                   max_W: int, max_R: int):
    """Generates the publication-quality comparison charts for A4."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [Plots] matplotlib not available - skipping plots.")
        return

    # Set modern style elements
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Helvetica", "Arial"]

    # 1. Season Demand Profiles
    fig, ax = plt.subplots(figsize=(12, 4))
    sum_df = generate_demand("summer", seed=42)
    win_df = generate_demand("winter", seed=42)
    ax.plot(sum_df["Demand"], color="orange", alpha=0.8, label="Summer Demand", lw=1.5)
    ax.plot(win_df["Demand"], color="blue", alpha=0.7, label="Winter Demand", lw=1.5)
    ax.set_title("Demand Regimes Comparison (Summer vs Winter Profiles)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Day of Year")
    ax.set_ylabel("Quantity")
    ax.legend(frameon=True, facecolor="white", edgecolor="none")
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "season_profiles.png", dpi=150)
    plt.close()
    print(f"  [OK] Plot saved: plots/season_profiles.png")

    # 2. Adaptation Learning Curves (First 50 episodes comparison)
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Smooth curves
    def smooth(data, window=5):
        return pd.Series(data).rolling(window, min_periods=1).mean().values

    # Find the matching names
    ft_vals = val_curves["Winter_FineTuned"]
    cs_short_vals = val_curves["Winter_ColdStart_Short"]
    cs_long_vals = val_curves["Winter_ColdStart_Long"]

    ax.plot(smooth(ft_vals), color="seagreen", lw=2.5, label="Winter Fine-Tuned (pre-trained on Summer)")
    ax.plot(smooth(cs_short_vals), color="crimson", lw=2, label="Winter Cold-Start (Short, 50 eps)")
    ax.plot(smooth(cs_long_vals[:len(ft_vals)]), color="blue", ls="--", lw=1.5, label="Winter Cold-Start (Long, 500 eps - early phase)")
    
    ax.set_title("Winter Adaptation Learning Curves (Validation Reward)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Adaptation Episode")
    ax.set_ylabel("Smoothed Validation Reward")
    ax.legend(frameon=True)
    ax.grid(True, linestyle="--", alpha=0.5)
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "training_curves.png", dpi=150)
    plt.close()
    print(f"  [OK] Plot saved: plots/training_curves.png")

    # 3. Performance Bar Charts
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    
    conditions = ["Zero-Shot", "Fine-Tuned", "Cold-Start (Short)", "Cold-Start (Long)", "(s,S) Heuristic"]
    keys = ["Winter_ZeroShot", "Winter_FineTuned", "Winter_ColdStart_Short", "Winter_ColdStart_Long", "Winter_SS_Heuristic"]
    
    colors = ["orange", "seagreen", "crimson", "blue", "grey"]

    # Extract metrics
    sls = []
    costs = []
    bws = []
    
    for k in keys:
        log = test_logs[k]
        env = test_envs[k]
        m = compute_all_metrics(log, env)
        sls.append(m["service_level"] * 100)
        costs.append(m["total_cost"] / 1e6)  # In Millions
        bws.append(m["bullwhip_ratio"])

    # Service Level Bar
    axes[0].bar(conditions, sls, color=colors, edgecolor="black", alpha=0.85)
    axes[0].set_title("Service Level (%)", fontsize=11, fontweight="bold")
    axes[0].set_ylabel("%")
    axes[0].set_ylim(0, 105)
    axes[0].set_xticklabels(conditions, rotation=30, ha="right")
    for i, v in enumerate(sls):
        axes[0].text(i, v + 1, f"{v:.1f}%", ha="center", fontsize=9)
    axes[0].grid(True, axis="y", linestyle="--", alpha=0.5)

    # Cost Bar
    axes[1].bar(conditions, costs, color=colors, edgecolor="black", alpha=0.85)
    axes[1].set_title("Total Cost ($ Millions)", fontsize=11, fontweight="bold")
    axes[1].set_ylabel("$ Millions")
    axes[1].set_xticklabels(conditions, rotation=30, ha="right")
    for i, v in enumerate(costs):
        axes[1].text(i, v + (max(costs)*0.01), f"${v:.2f}M", ha="center", fontsize=9)
    axes[1].grid(True, axis="y", linestyle="--", alpha=0.5)

    # Bullwhip Bar
    axes[2].bar(conditions, bws, color=colors, edgecolor="black", alpha=0.85)
    axes[2].set_title("Bullwhip Ratio", fontsize=11, fontweight="bold")
    axes[2].set_ylabel("Ratio")
    axes[2].axhline(1.0, color="red", ls="--", lw=1.2, label="BW=1 (no amp)")
    axes[2].set_xticklabels(conditions, rotation=30, ha="right")
    for i, v in enumerate(bws):
        if not np.isnan(v):
            axes[2].text(i, v + (max(bws)*0.01), f"{v:.2f}", ha="center", fontsize=9)
    axes[2].grid(True, axis="y", linestyle="--", alpha=0.5)

    fig.suptitle("Experiment A4 Performance Comparison under Winter Target Regime", fontsize=14, fontweight="bold")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "performance_comparison.png", dpi=150)
    plt.close()
    print(f"  [OK] Plot saved: plots/performance_comparison.png")

    # 4. Trajectory Comparison (First 90 Days)
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    days = 90
    
    # Fine-Tuned vs Matched Scratch
    ft_log = test_logs["Winter_FineTuned"][:days]
    cs_log = test_logs["Winter_ColdStart_Short"][:days]

    ft_inv_W = [d["inv_W"] for d in ft_log]
    ft_inv_R = [d["inv_R"] for d in ft_log]
    cs_inv_W = [d["inv_W"] for d in cs_log]
    cs_inv_R = [d["inv_R"] for d in cs_log]
    demand   = [d["demand"] for d in ft_log]

    axes[0].plot(ft_inv_W, color="seagreen", lw=2, label="Fine-Tuned WH Inventory")
    axes[0].plot(cs_inv_W, color="crimson", ls="--", lw=1.5, label="Cold-Start WH Inventory")
    axes[0].set_ylabel("Warehouse Inventory")
    axes[0].grid(True, linestyle="--", alpha=0.5)
    axes[0].legend()

    axes[1].plot(ft_inv_R, color="seagreen", lw=2, label="Fine-Tuned Retailer Inventory")
    axes[1].plot(cs_inv_R, color="crimson", ls="--", lw=1.5, label="Cold-Start Retailer Inventory")
    axes[1].set_ylabel("Retailer Inventory")
    axes[1].grid(True, linestyle="--", alpha=0.5)
    axes[1].legend()

    axes[2].fill_between(range(days), demand, alpha=0.3, color="gray", label="Customer Demand")
    axes[2].set_ylabel("Demand")
    axes[2].set_xlabel("Day")
    axes[2].grid(True, linestyle="--", alpha=0.5)
    axes[2].legend()

    fig.suptitle("Inventory Trajectory Comparison (First 90 Days in Winter)", fontsize=13, fontweight="bold")
    plt.tight_layout()
    plt.savefig(PLOTS_DIR / "trajectory_comparison.png", dpi=150)
    plt.close()
    print(f"  [OK] Plot saved: plots/trajectory_comparison.png")


# ── Main Entry ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true", help="Quick run with reduced episodes")
    parser.add_argument("--episodes", type=int, default=500, help="For compatibility with master runner (ignored to keep seasonal transfer design)")
    args = parser.parse_args()

    # Define budgets
    if args.smoke_test:
        episodes_source = 30
        episodes_target = 10
        episodes_long   = 50
    else:
        episodes_source = 300
        episodes_target = 50
        episodes_long   = 500

    print(f"\n{'='*70}")
    print(f"  EXPERIMENT A4: Seasonal Transfer Learning (Summer -> Winter)")
    print(f"  Mode: {'SMOKE TEST' if args.smoke_test else 'FULL RUN'}")
    print(f"  Budgets: Source (Summer) = {episodes_source} eps | Target (Winter) = {episodes_target} / {episodes_long} eps")
    print(f"{'='*70}")

    # ── Condition A: Train Summer Source Policy ──
    print(f"\n[Condition A] Training Source Policy on Summer demand ({episodes_source} episodes)...")
    t0 = time.time()
    source_agent, train_rews_sum, val_rews_sum, max_W, max_R = train_agent(
        episodes=episodes_source,
        season="summer",
        label="Summer Source",
        epsilon_start=1.0
    )
    summer_time = time.time() - t0
    
    # Save checkpoint weights
    checkpoint_path = RESULTS_DIR / "source_summer_best.pth"
    torch.save(source_agent.policy.state_dict(), checkpoint_path)
    print(f"  Source agent weights saved -> {checkpoint_path}")

    # Load the best summer checkpoint
    summer_weights = torch.load(checkpoint_path, map_location=_device)

    # Prepare Winter Test Data
    winter_test_df = prepare_env_data(generate_demand("winter", seed=999), "winter")
    summer_test_df = prepare_env_data(generate_demand("summer", seed=999), "summer")

    # Reference Metrics Logs
    test_logs = {}
    test_envs = {}
    val_curves = {}

    # Evaluate Condition A on its native Summer test set
    print("\n  Evaluating Condition A (Summer Source) on Native Summer Test Demand...")
    sum_reward, sum_log, sum_env = greedy_eval(source_agent, summer_test_df, max_W, max_R, "summer")
    condition_a_metrics = compute_all_metrics(sum_log, sum_env)
    print_metrics_table(condition_a_metrics, "Condition A: Summer Source (on Summer)")
    test_logs["Summer_Source"] = sum_log
    test_envs["Summer_Source"] = sum_env

    # ── Condition B: Winter Zero-Shot Transfer ──
    print("\n[Condition B] Evaluating Zero-Shot Transfer on Winter test demand...")
    zero_shot_agent = JointDDQNAgent(10, 121)
    zero_shot_agent.policy.load_state_dict(copy.deepcopy(summer_weights))
    zero_shot_agent.epsilon = 0.0
    zs_reward, zs_log, zs_env = greedy_eval(zero_shot_agent, winter_test_df, max_W, max_R, "winter")
    condition_b_metrics = compute_all_metrics(zs_log, zs_env)
    print_metrics_table(condition_b_metrics, "Condition B: Winter Zero-Shot Transfer")
    test_logs["Winter_ZeroShot"] = zs_log
    test_envs["Winter_ZeroShot"] = zs_env
    val_curves["Winter_ZeroShot"] = [zs_reward] * episodes_target

    # ── Condition C: Winter Fine-Tuning ──
    print(f"\n[Condition C] Fine-Tuning Agent on Winter demand ({episodes_target} episodes)...")
    t0 = time.time()
    ft_agent, ft_train_rews, ft_val_rews, _, _ = train_agent(
        episodes=episodes_target,
        season="winter",
        label="Winter Fine-Tuning",
        max_order_W=max_W,
        max_order_R=max_R,
        pre_trained_weights=summer_weights,
        epsilon_start=0.5 # lower epsilon to preserve weights
    )
    ft_time = time.time() - t0
    ft_reward, ft_log, ft_env = greedy_eval(ft_agent, winter_test_df, max_W, max_R, "winter")
    condition_c_metrics = compute_all_metrics(ft_log, ft_env)
    print_metrics_table(condition_c_metrics, "Condition C: Winter Fine-Tuned (50 eps)")
    test_logs["Winter_FineTuned"] = ft_log
    test_envs["Winter_FineTuned"] = ft_env
    val_curves["Winter_FineTuned"] = ft_val_rews

    # ── Condition D: Winter Cold-Start (Matched Budget) ──
    print(f"\n[Condition D] Training Cold-Start Agent on Winter demand ({episodes_target} episodes)...")
    t0 = time.time()
    cs_agent, cs_train_rews, cs_val_rews, _, _ = train_agent(
        episodes=episodes_target,
        season="winter",
        label="Winter Cold-Start (Matched)",
        max_order_W=max_W,
        max_order_R=max_R,
        epsilon_start=1.0
    )
    cs_time = time.time() - t0
    cs_reward, cs_log, cs_env = greedy_eval(cs_agent, winter_test_df, max_W, max_R, "winter")
    condition_d_metrics = compute_all_metrics(cs_log, cs_env)
    print_metrics_table(condition_d_metrics, "Condition D: Winter Cold-Start Matched")
    test_logs["Winter_ColdStart_Short"] = cs_log
    test_envs["Winter_ColdStart_Short"] = cs_env
    val_curves["Winter_ColdStart_Short"] = cs_val_rews

    # ── Condition E: Winter Cold-Start (Long Budget) ──
    print(f"\n[Condition E] Training Asymptotic Cold-Start Agent on Winter demand ({episodes_long} episodes)...")
    t0 = time.time()
    long_agent, long_train_rews, long_val_rews, _, _ = train_agent(
        episodes=episodes_long,
        season="winter",
        label="Winter Cold-Start (Long)",
        max_order_W=max_W,
        max_order_R=max_R,
        epsilon_start=1.0
    )
    long_time = time.time() - t0
    long_reward, long_log, long_env = greedy_eval(long_agent, winter_test_df, max_W, max_R, "winter")
    condition_e_metrics = compute_all_metrics(long_log, long_env)
    print_metrics_table(condition_e_metrics, "Condition E: Winter Cold-Start Long")
    test_logs["Winter_ColdStart_Long"] = long_log
    test_envs["Winter_ColdStart_Long"] = long_env
    val_curves["Winter_ColdStart_Long"] = long_val_rews

    # ── (s,S) Heuristic Baseline on Winter ──
    print("\n[Baseline] Running (s,S) Policy Baseline on Winter target regime...")
    ss_env = TwoEchelonEnv(
        winter_test_df,
        lead_time_W=3, lead_time_R=1,
        h_W=2.0, h_R=5.0, b_R=500.0,
        c_W=2.0, c_R=2.0,
        n_actions_W=11, n_actions_R=11,
        max_order_W=max_W, max_order_R=max_R
    )
    ss_reward, ss_log, ss_extra = run_ss_baseline(ss_env)
    condition_ss_metrics = compute_all_metrics(ss_log)
    condition_ss_metrics.update(ss_extra)
    print_metrics_table(condition_ss_metrics, "Winter (s,S) Policy")
    test_logs["Winter_SS_Heuristic"] = ss_log
    test_envs["Winter_SS_Heuristic"] = ss_env

    # ── Save config ──
    with open(RESULTS_DIR / "config.json", "w") as f:
        json.dump({
            "smoke_test": args.smoke_test,
            "episodes_source": episodes_source,
            "episodes_target": episodes_target,
            "episodes_long": episodes_long,
            "max_order_W": int(max_W),
            "max_order_R": int(max_R),
            "device": str(_device)
        }, f, indent=2)

    # ── Compile Summary ──
    summary = {
        "experiment": "A4_seasonal_transfer",
        "smoke_test": args.smoke_test,
        "max_order_W": int(max_W),
        "max_order_R": int(max_R),
        "runtimes": {
            "summer_source_min": round(summer_time / 60, 2),
            "winter_fine_tune_min": round(ft_time / 60, 2),
            "winter_cold_start_short_min": round(cs_time / 60, 2),
            "winter_cold_start_long_min": round(long_time / 60, 2),
        },
        "results": {
            "Condition_A_Summer_Source": condition_a_metrics,
            "Condition_B_Winter_Zero_Shot": condition_b_metrics,
            "Condition_C_Winter_Fine_Tuned": condition_c_metrics,
            "Condition_D_Winter_Cold_Start_Matched": condition_d_metrics,
            "Condition_E_Winter_Cold_Start_Long": condition_e_metrics,
            "Winter_SS_Heuristic": condition_ss_metrics,
        },
        "transfer_metrics": {
            "zero_shot_service_level_gap": round(condition_b_metrics["service_level"] - condition_e_metrics["service_level"], 4),
            "zero_shot_cost_gap_pct": round((condition_b_metrics["total_cost"] - condition_e_metrics["total_cost"]) / condition_e_metrics["total_cost"] * 100, 2),
            "fine_tuning_service_level_gain": round(condition_c_metrics["service_level"] - condition_d_metrics["service_level"], 4),
            "fine_tuning_cost_gain_pct": round((condition_d_metrics["total_cost"] - condition_c_metrics["total_cost"]) / condition_d_metrics["total_cost"] * 100, 2),
        }
    }

    # Save summary
    with open(RESULTS_DIR / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  [OK] Summary saved -> {RESULTS_DIR}/summary.json")

    # Save logs
    with open(RESULTS_DIR / "experiment_log.jsonl", "w") as f:
        f.write(json.dumps(summary) + "\n")

    # ── Plots Generation ──
    print("\n  Generating plots...")
    generate_plots(val_curves, test_logs, test_envs, max_W, max_R)

    print(f"\n  [OK] Experiment A4 complete.")


if __name__ == "__main__":
    main()
