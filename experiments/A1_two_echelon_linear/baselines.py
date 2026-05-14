"""
Baselines for Experiment A1
============================
Three baseline policies against which the Joint DDQN agent is compared:

  1. Independent DDQN  — Two separate Replenix-style DDQN agents, one per
                          node, with no shared state.
  2. (s, S) Policy     — Classical reorder-point / order-up-to heuristic
                          with analytically calibrated parameters.
  3. Oracle (5-day)    — Cheating agent that sees 5 days of future demand.

Each baseline exposes the same interface:
    run_baseline(env, ...) → (total_reward, info_log, extra_metrics)
"""

import sys, os
import numpy as np
import pandas as pd
from collections import deque

# Bring the experiment directory into path (for env_two_echelon imports)
sys.path.insert(0, os.path.dirname(__file__))
from env_two_echelon import TwoEchelonEnv, prepare_env_data, generate_demand

# DDQN re-used directly from the experiment's own copy
# (We adapt the single-echelon DQNAgent from Replenix by re-using its class
#  for the independent baseline — importing from the Backend-RL directory.)
REPLENIX_SRC = os.path.join(
    os.path.dirname(__file__), "..", "..", "Backend-RL", "src"
)


# ──────────────────────────────────────────────────────────────────────────────
# Baseline 1: (s, S) Policy
# ──────────────────────────────────────────────────────────────────────────────

def _ss_params(demand_series, lead_time, service_z=1.65):
    """
    Derive (s, S) parameters analytically.

    s = reorder point  = avg_demand * lead_time + z * σ * sqrt(lead_time)
    S = order-up-to   = s + avg_demand * review_cycle   (review_cycle=1 day)

    service_z = 1.65 → ~95% fill rate under Normal demand.
    """
    avg_d = float(demand_series.mean())
    std_d = float(demand_series.std())
    s = avg_d * lead_time + service_z * std_d * np.sqrt(lead_time)
    S = s + avg_d  # order-up-to is one cycle above reorder point
    return int(round(s)), int(round(S))


def run_ss_baseline(env: TwoEchelonEnv) -> tuple:
    """
    Two independent (s, S) policies — one for each echelon.

    Parameters are calibrated separately per node:
      - Warehouse uses L_W and faces retailer order demand.
      - Retailer  uses L_R and faces customer demand.

    Returns
    -------
    total_reward : float
    info_log     : list[dict]
    extra        : dict  — bullwhip_ratio, service_level
    """
    demand_series = env.data["demand"]

    # Calibrate per node
    s_W, S_W = _ss_params(demand_series, env.L_W)
    s_R, S_R = _ss_params(demand_series, env.L_R)

    state = env.reset()
    total_reward = 0.0
    info_log = []

    while True:
        # Retailer policy: order up to S_R if position drops below s_R
        pos_R = env.inv_R + sum(env.pipeline_R) - env.backlog_R
        a_R = max(0, S_R - pos_R) if pos_R < s_R else 0

        # Warehouse policy: order up to S_W if position drops below s_W
        pos_W = env.inv_W + sum(env.pipeline_W) - env.backlog_W
        a_W = max(0, S_W - pos_W) if pos_W < s_W else 0

        # Snap to nearest action grid
        a_W_qty = min(env.max_order_W,
                      round(a_W / env.action_step_W) * env.action_step_W)
        a_R_qty = min(env.max_order_R,
                      round(a_R / env.action_step_R) * env.action_step_R)

        action_index = env.encode_action(a_W_qty, a_R_qty)
        _, reward, done, info = env.step(action_index)

        info_log.append(info)
        total_reward += reward
        if done:
            break

    extra = {
        "bullwhip_ratio": env.bullwhip_ratio(),
        "service_level":  env.service_level(info_log),
        "s_W": s_W, "S_W": S_W,
        "s_R": s_R, "S_R": S_R,
    }
    return total_reward, info_log, extra


# ──────────────────────────────────────────────────────────────────────────────
# Baseline 2: Oracle (5-day lookahead)
# ──────────────────────────────────────────────────────────────────────────────

def run_oracle_baseline(env: TwoEchelonEnv, window: int = 5) -> tuple:
    """
    Oracle baseline: the agent knows future demand for `window` days.

    Strategy:
      - Retailer orders exactly the next `window`-day demand minus inventory
        position (capped at max_order_R).
      - Warehouse mirrors the retailer order (plus L_R buffer) to ensure
        retailer never waits.
    """
    demand_series = env.data["demand"].values
    n = len(demand_series)

    state = env.reset()
    total_reward = 0.0
    info_log = []

    while True:
        t = env.current_step
        if t >= n:
            break

        future_end    = min(t + window, n)
        future_demand = int(demand_series[t:future_end].sum())

        # Retailer: order what's needed over the window
        pos_R = env.inv_R + sum(env.pipeline_R) - env.backlog_R
        a_R   = max(0, future_demand - pos_R)

        # Warehouse: anticipate retailer order + lead-time demand
        pos_W = env.inv_W + sum(env.pipeline_W) - env.backlog_W
        a_W   = max(0, a_R + future_demand - pos_W)

        # Snap to grid
        a_W_qty = min(env.max_order_W,
                      round(a_W / env.action_step_W) * env.action_step_W)
        a_R_qty = min(env.max_order_R,
                      round(a_R / env.action_step_R) * env.action_step_R)

        action_index = env.encode_action(a_W_qty, a_R_qty)
        _, reward, done, info = env.step(action_index)

        info_log.append(info)
        total_reward += reward
        if done:
            break

    extra = {
        "bullwhip_ratio": env.bullwhip_ratio(),
        "service_level":  env.service_level(info_log),
        "window":         window,
    }
    return total_reward, info_log, extra


# ──────────────────────────────────────────────────────────────────────────────
# Baseline 3: Independent DDQN
# ──────────────────────────────────────────────────────────────────────────────
# Two single-echelon agents — each sees only its own node's state.
# We embed a minimal single-echelon DDQN directly to avoid coupling to
# the production Replenix Backend-RL code.

import torch
import torch.nn as nn
import torch.optim as optim
import random
import copy

_device = torch.device(
    "mps"  if torch.backends.mps.is_available() else
    "cuda" if torch.cuda.is_available()         else
    "cpu"
)


class _MiniDQN(nn.Module):
    """Minimal 3-layer DQN for single-echelon independent baseline."""
    def __init__(self, state_size, action_size):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_size, 128), nn.ReLU(),
            nn.Linear(128, 128),        nn.ReLU(),
            nn.Linear(128, action_size)
        )

    def forward(self, x):
        return self.net(x)


class _MiniReplayBuffer:
    def __init__(self, capacity=50000):
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

    def __len__(self): return len(self.buf)


class _MiniDDQNAgent:
    """Minimal Double-DQN agent for the independent baseline."""
    def __init__(self, state_size, action_size, episodes=300):
        self.action_size = action_size
        self.gamma   = 0.98
        self.epsilon = 1.0
        self.eps_min = 0.05
        self.eps_decay = (self.eps_min / 1.0) ** (1.0 / max(episodes, 1))
        self.tau     = 0.005
        self.learn_every = 4
        self._step   = 0
        self.batch_size = 128

        self.policy = _MiniDQN(state_size, action_size).to(_device)
        self.target = _MiniDQN(state_size, action_size).to(_device)
        self.target.load_state_dict(self.policy.state_dict())
        self.target.eval()

        self.opt = optim.Adam(self.policy.parameters(), lr=1e-4)
        self.buf = _MiniReplayBuffer()
        self._best = None

    def act(self, state):
        if random.random() < self.epsilon:
            return random.randint(0, self.action_size - 1)
        s = torch.FloatTensor(state).unsqueeze(0).to(_device)
        with torch.inference_mode():
            return self.policy(s).argmax().item()

    def learn(self):
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
        self.opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
        self.opt.step()
        for tp, pp in zip(self.target.parameters(), self.policy.parameters()):
            tp.data.copy_(self.tau * pp.data + (1 - self.tau) * tp.data)

    def decay(self):
        self.epsilon = max(self.eps_min, self.epsilon * self.eps_decay)

    def save_best(self):
        self._best = copy.deepcopy(self.policy.state_dict())

    def load_best(self):
        if self._best: self.policy.load_state_dict(self._best)


def _single_echelon_state_W(env: TwoEchelonEnv) -> np.ndarray:
    """Local 4-dim state for the warehouse agent (independent baseline)."""
    avg_d = env.data["demand"].mean()
    return np.array([
        np.log1p(env.inv_W) / np.log1p(env.max_inv_W),
        np.clip(sum(env.pipeline_W) / max(env.max_order_W, 1), 0, 2),
        np.clip(env.backlog_W / max(avg_d, 1), 0, 3),
        float(env.last_a_R / max(env.max_order_R, 1)),  # last retailer order seen
    ], dtype=np.float32)


def _single_echelon_state_R(env: TwoEchelonEnv, demand_t: int) -> np.ndarray:
    """Local 4-dim state for the retailer agent (independent baseline)."""
    avg_d = env.data["demand"].mean()
    return np.array([
        np.log1p(env.inv_R) / np.log1p(env.max_inv_R),
        np.clip(sum(env.pipeline_R) / max(env.max_order_R, 1), 0, 2),
        np.clip(env.backlog_R / max(avg_d, 1), 0, 3),
        np.clip(demand_t / max(env.max_order_R, 1), 0, 1),
    ], dtype=np.float32)


def run_independent_ddqn_baseline(
    env_data: pd.DataFrame,
    episodes: int = 300,
    season_type: str = "summer",
    test_seed: int = 999,
) -> tuple:
    """
    Train two independent single-echelon DDQN agents on the 2-echelon env.

    Each agent sees ONLY its own node's local state (4 dims each).
    They act independently — no shared information.

    Returns evaluation results on test_seed demand.
    """
    from env_two_echelon import compute_adaptive_params

    # Build a reference env to get grid params
    ref_env = TwoEchelonEnv(env_data)

    agent_W = _MiniDDQNAgent(state_size=4, action_size=ref_env.n_W, episodes=episodes)
    agent_R = _MiniDDQNAgent(state_size=4, action_size=ref_env.n_R, episodes=episodes)

    best_eval_W, best_eval_R = -np.inf, -np.inf

    print(f"\n  [Baseline: Independent DDQN] Training {episodes} episodes...")

    for ep in range(episodes):
        ep_env = TwoEchelonEnv(
            prepare_env_data(generate_demand(season_type, seed=ep + 1000),
                             season_type)
        )
        ep_env.reset()
        done = False

        # Read initial states from the env internals
        # (we build local states from env attributes)
        while not done:
            # Build local state for each node BEFORE the step
            current_demand = int(ep_env.data.iloc[ep_env.current_step]["demand"])
            sw = _single_echelon_state_W(ep_env)
            sr = _single_echelon_state_R(ep_env, current_demand)

            # Each agent picks its own action
            aw_idx = agent_W.act(sw)
            ar_idx = agent_R.act(sr)

            # Combine into joint action
            joint_idx = aw_idx * ref_env.n_R + ar_idx
            _, reward, done, info = ep_env.step(joint_idx)

            # Build next local states
            if not done:
                sw2 = _single_echelon_state_W(ep_env)
                sr2 = _single_echelon_state_R(ep_env, info["demand"])
            else:
                sw2 = np.zeros(4, dtype=np.float32)
                sr2 = np.zeros(4, dtype=np.float32)

            # Split reward heuristically:
            # Warehouse gets holding + order cost, retailer gets backorder + holding
            r_W = -(info["holding_W"] + info["order_cost_W"])
            r_R = -(info["holding_R"] + info["backorder_R"] + info["order_cost_R"])

            agent_W.buf.push(sw, aw_idx, r_W, sw2, float(done))
            agent_R.buf.push(sr, ar_idx, r_R, sr2, float(done))
            agent_W.learn()
            agent_R.learn()

        agent_W.decay()
        agent_R.decay()

    # ── Evaluation on test set ──
    print("  [Baseline: Independent DDQN] Evaluating on test demand...")
    test_df = prepare_env_data(generate_demand(season_type, seed=test_seed),
                               season_type)
    eval_env = TwoEchelonEnv(test_df)
    eval_env.reset()

    saved_W, saved_R = agent_W.epsilon, agent_R.epsilon
    agent_W.epsilon = 0.0
    agent_R.epsilon = 0.0

    total_reward = 0.0
    info_log = []
    done = False

    while not done:
        current_demand = int(eval_env.data.iloc[eval_env.current_step]["demand"])
        sw = _single_echelon_state_W(eval_env)
        sr = _single_echelon_state_R(eval_env, current_demand)
        aw_idx = agent_W.act(sw)
        ar_idx = agent_R.act(sr)
        joint_idx = aw_idx * ref_env.n_R + ar_idx
        _, reward, done, info = eval_env.step(joint_idx)
        info_log.append(info)
        total_reward += reward

    agent_W.epsilon = saved_W
    agent_R.epsilon = saved_R

    extra = {
        "bullwhip_ratio": eval_env.bullwhip_ratio(),
        "service_level":  eval_env.service_level(info_log),
    }
    return total_reward, info_log, extra
