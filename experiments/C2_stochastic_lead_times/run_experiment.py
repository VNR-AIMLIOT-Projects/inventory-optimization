"""
Experiment C2 — Stochastic Lead Times
================================================
Trains Joint DDQN on A1 (2-echelon) env with stochastic lead times.
Evaluates the robustness of an agent trained on Fixed Lead Time vs 
an agent trained natively on Stochastic Lead Time.

Usage:
    python3 run_experiment.py              # 500 eps per condition
    python3 run_experiment.py --smoke-test # 50 eps per condition
"""

import sys, json, time, argparse, copy, random
import numpy as np
import torch, torch.nn as nn, torch.optim as optim
import pandas as pd
from collections import deque
from pathlib import Path

HERE   = Path(__file__).parent
SHARED = HERE.parent / "shared"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(HERE))

from env_stochastic_lt import StochasticTwoEchelonEnv, generate_demand, prepare_env_data

RESULTS_DIR = HERE / "results"
PLOTS_DIR   = HERE / "plots"
RESULTS_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)

_device = torch.device(
    "mps"  if torch.backends.mps.is_available() else
    "cuda" if torch.cuda.is_available() else "cpu"
)
print(f"[C2] Device: {_device}")

CONFIG = {
    "season_type": "summer", "num_days": 365,
    "val_seed": 777, "test_seed": 999, "train_seed_base": 1000,
    "lead_time_W_min": 2, "lead_time_W_max": 5, "lead_time_R": 1,
    "h_W": 2.0, "h_R": 5.0, "b_R": 500.0, "c_W": 2.0, "c_R": 2.0,
    "n_actions_W": 11, "n_actions_R": 11,
    "gamma": 0.98, "tau": 0.005, "lr": 1e-4,
    "epsilon_start": 1.0, "epsilon_min": 0.05,
    "batch_size": 256, "learn_every": 4, "replay_capacity": 100_000,
}
CONDITIONS = ["Fixed (LT=3)", "Stochastic (LT 2-5)"]


class JointDQN(nn.Module):
    def __init__(self, s, a):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(s, 256), nn.ReLU(), nn.Linear(256, 256), nn.ReLU(),
            nn.Linear(256, 128), nn.ReLU(), nn.Linear(128, a))
    def forward(self, x): return self.net(x)


class ReplayBuffer:
    def __init__(self, cap):
        self.buf = deque(maxlen=cap)
        self._n = self._mean = self._m2 = 0.0
    def push(self, s, a, r, s2, d):
        self.buf.append((s, a, r, s2, d))
        self._n += 1
        delta = r - self._mean; self._mean += delta / self._n
        self._m2 += delta * (r - self._mean)
    @property
    def std(self): return max(np.sqrt(self._m2 / max(self._n, 1)), 1e-6)
    def sample(self, bs):
        batch = random.sample(self.buf, bs)
        s, a, r, s2, d = zip(*batch)
        r_n = (np.array(r, np.float32) - self._mean) / self.std
        return (torch.FloatTensor(np.array(s)).to(_device),
                torch.LongTensor(a).to(_device),
                torch.FloatTensor(r_n).to(_device),
                torch.FloatTensor(np.array(s2)).to(_device),
                torch.FloatTensor(d).to(_device))
    def __len__(self): return len(self.buf)


class Agent:
    def __init__(self, ss, aa, cfg, episodes):
        self.aa = aa; self.gamma = cfg["gamma"]; self.tau = cfg["tau"]
        self.le = cfg["learn_every"]; self.bs = cfg["batch_size"]; self._step = 0
        self.eps = cfg["epsilon_start"]; self.eps_min = cfg["epsilon_min"]
        self.eps_decay = (self.eps_min / self.eps) ** (1.0 / max(episodes, 1))
        self.policy = JointDQN(ss, aa).to(_device)
        self.target = JointDQN(ss, aa).to(_device)
        self.target.load_state_dict(self.policy.state_dict()); self.target.eval()
        self.opt = optim.Adam(self.policy.parameters(), lr=cfg["lr"])
        self.buf = ReplayBuffer(cfg["replay_capacity"])
        self._best = None; self._best_eval = -np.inf

    def act(self, state):
        if random.random() < self.eps:
            return random.randint(0, self.aa - 1)
        s = torch.FloatTensor(state).unsqueeze(0).to(_device)
        with torch.inference_mode(): return self.policy(s).argmax().item()

    def learn(self):
        self._step += 1
        if self._step % self.le or len(self.buf) < self.bs: return
        s, a, r, s2, d = self.buf.sample(self.bs)
        q = self.policy(s).gather(1, a.unsqueeze(1)).squeeze()
        with torch.no_grad():
            ba = self.policy(s2).argmax(1, keepdim=True)
            qn = self.target(s2).gather(1, ba).squeeze()
            tgt = r + self.gamma * qn * (1 - d)
        loss = nn.SmoothL1Loss()(q, tgt)
        self.opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(self.policy.parameters(), 1.0)
        self.opt.step()
        for tp, pp in zip(self.target.parameters(), self.policy.parameters()):
            tp.data.copy_(self.tau * pp.data + (1 - self.tau) * tp.data)

    def decay_epsilon(self): self.eps = max(self.eps_min, self.eps * self.eps_decay)
    def save_best(self, ev):
        if ev > self._best_eval: self._best_eval = ev; self._best = copy.deepcopy(self.policy.state_dict())
    def load_best(self):
        if self._best: self.policy.load_state_dict(self._best); self.target.load_state_dict(self._best)


def make_env(df, cfg, condition="Stochastic (LT 2-5)"):
    if condition == "Fixed (LT=3)":
        lt_min = 3
        lt_max = 3
    else:
        lt_min = cfg["lead_time_W_min"]
        lt_max = cfg["lead_time_W_max"]

    return StochasticTwoEchelonEnv(df,
        lead_time_W_min=lt_min, lead_time_W_max=lt_max, lead_time_R=cfg["lead_time_R"],
        h_W=cfg["h_W"], h_R=cfg["h_R"], b_R=cfg["b_R"],
        c_W=cfg["c_W"], c_R=cfg["c_R"],
        n_actions_W=cfg["n_actions_W"], n_actions_R=cfg["n_actions_R"])


def greedy_eval(agent, env_data, cfg, condition="Stochastic (LT 2-5)"):
    env = make_env(env_data, cfg, condition)
    state = env.reset()
    saved_eps = agent.eps; agent.eps = 0.0
    total_r, info_log, done = 0.0, [], False
    while not done:
        a = agent.act(state)
        ns, r, done, info = env.step(a)
        info_log.append(info); total_r += r
        state = ns if ns is not None else np.zeros(env.state_size)
    agent.eps = saved_eps
    return total_r, info_log, env


def train_condition(cond, cfg, episodes, season):
    print(f"\n{'='*55}\n  Condition: {cond} | {episodes} episodes\n{'='*55}")
    ref_df  = prepare_env_data(generate_demand(season, seed=cfg["train_seed_base"]), season)
    ref_env = make_env(ref_df, cfg, cond)
    ss = ref_env.state_size; aa = ref_env.action_size
    val_df = prepare_env_data(generate_demand(season, seed=cfg["val_seed"]), season)
    agent = Agent(ss, aa, cfg, episodes)
    rewards = []; t0 = time.time()
    zeros = np.zeros(ss, dtype=np.float32)

    for ep in range(episodes):
        df = prepare_env_data(generate_demand(season, seed=cfg["train_seed_base"] + ep), season)
        env = make_env(df, cfg, cond)
        state = env.reset(); ep_r = 0.0; done = False

        while not done:
            action = agent.act(state)
            ns, r, done, info = env.step(action)
            ns2 = ns if ns is not None else zeros
            agent.buf.push(state, action, r, ns2, float(done))
            agent.learn(); state = ns2; ep_r += r

        agent.decay_epsilon(); rewards.append(ep_r)

        if ep % 50 == 0 or ep == episodes - 1:
            # We evaluate on the SAME condition as training during the run to save best weights
            ev_r, ev_log, ev_env = greedy_eval(agent, val_df, cfg, cond)
            agent.save_best(ev_r)
            bw = ev_env.bullwhip_ratio(); svc = ev_env.service_level(ev_log)
            print(f"  Ep {ep:>4d} | {cond[:10]}... | Eval={ev_r:>10,.0f} | "
                  f"eps={agent.eps:.3f} | BW={bw:.3f} | SL={svc:.3f} | {time.time()-t0:.0f}s")

    agent.load_best()
    return agent, rewards


def compute_metrics(info_log, env):
    td = sum(d["demand"] for d in info_log)
    tb = sum(d["backlog_R"] for d in info_log)
    tc = sum(-(d["holding_W"]+d["holding_R"]+d["backorder_R"]+d["order_cost_W"]+d["order_cost_R"]) for d in info_log)
    bw = env.bullwhip_ratio()
    os = float(np.std([d["a_W"] for d in info_log]))
    return {
        "service_level":  round(1.0 - tb/max(td,1), 4),
        "total_cost":     round(float(-tc), 2),
        "bullwhip_ratio": round(float(bw), 4) if not np.isnan(bw) else None,
        "order_std_W":    round(os, 2),
        "total_demand":   int(td), "total_backlog": int(tb),
    }


def make_plots(all_results, rewards_by_cond):
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [Plots] matplotlib not available."); return

    conds  = [r["condition"] for r in all_results]
    svc    = [r["metrics"]["service_level"] for r in all_results]
    bw     = [r["metrics"]["bullwhip_ratio"] or 0 for r in all_results]
    costs  = [r["metrics"]["total_cost"] for r in all_results]
    colors = ["steelblue", "darkorange"]

    # 1. Training curves
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, (cond, rews) in enumerate(zip(conds, rewards_by_cond)):
        sm = pd.Series(rews).rolling(20, min_periods=1).mean()
        ax.plot(sm, label=f"Train Cond={cond}", color=colors[i])
    ax.set_xlabel("Episode"); ax.set_ylabel("Smoothed Reward (MA-20)")
    ax.set_title("C2 - Training Curves")
    ax.legend()
    plt.tight_layout(); plt.savefig(PLOTS_DIR/"training_curves.png", dpi=150)
    plt.close(); print(f"  [OK] Training curves saved")

    # 2. Performance Comparison Bar Charts
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    
    # Cost
    axes[0].bar(conds, costs, color=colors)
    axes[0].set_ylabel("Total Episode Cost")
    axes[0].set_title("C2 - Cost on Stochastic Eval Env")
    for bar, v in zip(axes[0].patches, costs):
        axes[0].text(bar.get_x()+bar.get_width()/2, bar.get_height()+max(costs)*0.01,
                f"{v:,.0f}", ha="center", fontsize=9)
    
    # Service Level
    axes[1].bar(conds, svc, color=colors)
    axes[1].set_ylabel("Service Level")
    axes[1].set_title("C2 - Service Level on Stochastic Eval Env")
    axes[1].set_ylim(0, 1.05)
    for bar, v in zip(axes[1].patches, svc):
        axes[1].text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.02,
                f"{v:.4f}", ha="center", fontsize=9)

    plt.tight_layout(); plt.savefig(PLOTS_DIR/"performance_comparison.png", dpi=150)
    plt.close(); print(f"  [OK] Performance comparison saved")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    episodes = 50 if args.smoke_test else args.episodes
    season   = CONFIG["season_type"]

    print(f"\n{'#'*55}")
    print(f"\n  EXPERIMENT C2 - Stochastic Lead Times")
    print(f"  Conditions : {CONDITIONS}")
    print(f"  Episodes/cond: {episodes}")
    print(f"{'#'*55}")

    with open(RESULTS_DIR/"config.json","w") as f:
        json.dump({**CONFIG, "episodes": episodes, "conditions": CONDITIONS}, f, indent=2)

    test_df = prepare_env_data(generate_demand(season, seed=CONFIG["test_seed"]), season)

    all_results = []; rewards_by_cond = []
    for cond in CONDITIONS:
        agent, rewards = train_condition(cond, CONFIG, episodes, season)
        rewards_by_cond.append(rewards)
        
        # KEY TEST: Evaluate BOTH agents on the Stochastic environment
        print(f"\n  Evaluating {cond} agent on STOCHASTIC test set...")
        _, info_log, ev_env = greedy_eval(agent, test_df, CONFIG, condition="Stochastic (LT 2-5)")
        metrics = compute_metrics(info_log, ev_env)
        all_results.append({"condition": cond, "metrics": metrics})
        print(f"  {cond} | SL={metrics['service_level']:.4f} | "
              f"BW={metrics['bullwhip_ratio']} | Cost={metrics['total_cost']:,.0f}")

    print(f"\n{'='*55}")
    print(f"  C2 RESULTS SUMMARY (Tested on Stochastic Env)")
    print(f"  {'Condition':>20} | {'SL':>7} | {'BW':>8} | {'Cost':>12}")
    print(f"  {'-'*55}")
    for r in all_results:
        m = r["metrics"]
        print(f"  {r['condition']:>20} | {m['service_level']:>7.4f} | "
              f"{str(m['bullwhip_ratio']):>8} | {m['total_cost']:>12,.0f}")
    print(f"{'='*55}")

    summary = {"experiment": "C2_stochastic_lead_times", "episodes": episodes,
               "conditions": CONDITIONS, "results": all_results}
    with open(RESULTS_DIR/"summary.json","w") as f: json.dump(summary, f, indent=2)

    make_plots(all_results, rewards_by_cond)
    print(f"\n  [OK] Experiment C2 complete. Results -> {RESULTS_DIR}/summary.json")


if __name__ == "__main__":
    main()
