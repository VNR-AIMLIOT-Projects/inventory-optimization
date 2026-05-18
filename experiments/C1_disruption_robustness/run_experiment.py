"""
Experiment C1 — Disruption Robustness
======================================
Extends A2 (3-echelon) environment with supply disruption injection.
Tests: Baseline | Naive (no disruption training) | Aware (disruption-trained).

Disruption: p_shock per day triggers zero-supply period for D_len ~ Uniform(1,7) days.
State extended by 2 dims: [disruption_active, disruption_remaining_norm]

Usage:
    python3 run_experiment.py              # 500 episodes per condition
    python3 run_experiment.py --smoke-test # 50 episodes
"""

import sys, json, time, argparse, copy, random
import numpy as np
import torch, torch.nn as nn, torch.optim as optim
import pandas as pd
from collections import deque
from pathlib import Path

HERE   = Path(__file__).parent
SHARED = HERE.parent / "shared"
A2_DIR = HERE.parent / "A2_three_echelon_linear"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(A2_DIR))

from env_three_echelon import ThreeEchelonEnv, generate_demand, prepare_env_data

RESULTS_DIR = HERE / "results"
PLOTS_DIR   = HERE / "plots"
RESULTS_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)

_device = torch.device(
    "mps"  if torch.backends.mps.is_available() else
    "cuda" if torch.cuda.is_available() else "cpu"
)
print(f"[C1] Device: {_device}")

CONFIG = {
    "season_type": "summer", "num_days": 365,
    "val_seed": 777, "test_seed": 999, "train_seed_base": 2000,
    "lead_time_1": 4, "lead_time_2": 2, "lead_time_3": 1,
    "h_E1": 1.0, "h_E2": 3.0, "h_E3": 5.0,
    "b_E3": 500.0, "c_E1": 2.0, "c_E2": 2.0, "c_E3": 2.0,
    "n_actions": 7,
    "gamma": 0.98, "tau": 0.005, "lr": 1e-4,
    "epsilon_start": 1.0, "epsilon_min": 0.05,
    "batch_size": 256, "learn_every": 4, "replay_capacity": 100_000,
    # Disruption params (moderate setting)
    "p_shock": 0.03,
    "max_disruption_len": 7,
}


# ── Disruption wrapper for ThreeEchelonEnv ───────────────────────────────────

class DisruptionEnv:
    """
    Wraps ThreeEchelonEnv and injects zero-supply disruption events on the
    supplier → E1 (warehouse) link.

    State extension: appends 2 dims to the base 13-dim state:
      [13] disruption_active        (0 or 1)
      [14] disruption_remaining_norm (remaining_days / max_disruption_len)
    """
    BASE_STATE_SIZE = 13

    def __init__(self, base_env: ThreeEchelonEnv,
                 p_shock: float = 0.03, max_d_len: int = 7,
                 awareness: bool = True):
        self.env      = base_env
        self.p_shock  = p_shock
        self.max_d    = max_d_len
        self.aware    = awareness   # if False: no disruption dims in state
        self._active  = False
        self._remain  = 0
        # Disruption log for analysis
        self.disruption_log = []

    @property
    def state_size(self):
        return self.BASE_STATE_SIZE + (2 if self.aware else 0)

    @property
    def action_size(self):
        return self.env.action_size

    def reset(self):
        self._active = False; self._remain = 0
        self.disruption_log = []
        base_state = self.env.reset()
        return self._augment(base_state)

    def _augment(self, base_state):
        if not self.aware:
            return base_state
        d_active = float(self._active)
        d_remain = self._remain / self.max_d
        return np.concatenate([base_state, [d_active, d_remain]]).astype(np.float32)

    def step(self, action_index):
        # Disruption state machine
        if self._active:
            self._remain -= 1
            if self._remain <= 0:
                self._active = False
                self._remain = 0
        else:
            if random.random() < self.p_shock:
                self._active = True
                self._remain = random.randint(1, self.max_d)

        # If disrupted: zero out the warehouse replenishment
        # We do this by zeroing E1 order index while keeping E2/E3
        if self._active:
            n7 = self.env.n_act
            a_E2_idx = (action_index % (n7 * n7)) // n7
            a_E3_idx = action_index % n7
            # Force E1 order to 0 (first level = 0)
            action_index = 0 * (n7 * n7) + a_E2_idx * n7 + a_E3_idx

        next_state, reward, done, info = self.env.step(action_index)
        info["disruption_active"]  = self._active
        info["disruption_remain"]  = self._remain
        self.disruption_log.append({
            "step": self.env.t,
            "active": self._active, "remain": self._remain
        })

        if next_state is not None:
            next_state = self._augment(next_state)
        return next_state, reward, done, info

    def bullwhip_ratio(self): return self.env.bullwhip_ratio()
    def service_level(self, info_log): return self.env.service_level(info_log)


# ── DDQN ─────────────────────────────────────────────────────────────────────

class JointDQN(nn.Module):
    def __init__(self, s, a):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(s,256), nn.ReLU(), nn.Linear(256,256), nn.ReLU(),
            nn.Linear(256,128), nn.ReLU(), nn.Linear(128,a))
    def forward(self, x): return self.net(x)


class ReplayBuffer:
    def __init__(self, cap):
        self.buf = deque(maxlen=cap)
        self._n = self._mean = self._m2 = 0.0
    def push(self, s, a, r, s2, d):
        self.buf.append((s, a, r, s2, d))
        self._n += 1; delta = r - self._mean
        self._mean += delta / self._n; self._m2 += delta*(r-self._mean)
    @property
    def std(self): return max(np.sqrt(self._m2/max(self._n,1)),1e-6)
    def sample(self, bs):
        batch = random.sample(self.buf, bs)
        s,a,r,s2,d = zip(*batch)
        rn = (np.array(r,np.float32)-self._mean)/self.std
        return (torch.FloatTensor(np.array(s)).to(_device),
                torch.LongTensor(a).to(_device),
                torch.FloatTensor(rn).to(_device),
                torch.FloatTensor(np.array(s2)).to(_device),
                torch.FloatTensor(d).to(_device))
    def __len__(self): return len(self.buf)


class Agent:
    def __init__(self, ss, aa, cfg, episodes):
        self.aa = aa; self.gamma = cfg["gamma"]; self.tau = cfg["tau"]
        self.le = cfg["learn_every"]; self.bs = cfg["batch_size"]; self._step = 0
        self.eps = cfg["epsilon_start"]; self.eps_min = cfg["epsilon_min"]
        self.eps_decay = (self.eps_min/self.eps)**(1.0/max(episodes,1))
        self.policy = JointDQN(ss,aa).to(_device)
        self.target = JointDQN(ss,aa).to(_device)
        self.target.load_state_dict(self.policy.state_dict()); self.target.eval()
        self.opt = optim.Adam(self.policy.parameters(), lr=cfg["lr"])
        self.buf = ReplayBuffer(cfg["replay_capacity"])
        self._best = None; self._best_eval = -np.inf

    def act(self, state):
        if random.random() < self.eps: return random.randint(0,self.aa-1)
        s = torch.FloatTensor(state).unsqueeze(0).to(_device)
        with torch.inference_mode(): return self.policy(s).argmax().item()

    def learn(self):
        self._step += 1
        if self._step % self.le or len(self.buf) < self.bs: return
        s,a,r,s2,d = self.buf.sample(self.bs)
        q = self.policy(s).gather(1,a.unsqueeze(1)).squeeze()
        with torch.no_grad():
            ba = self.policy(s2).argmax(1,keepdim=True)
            qn = self.target(s2).gather(1,ba).squeeze()
            tgt = r + self.gamma*qn*(1-d)
        loss = nn.SmoothL1Loss()(q,tgt)
        self.opt.zero_grad(); loss.backward()
        nn.utils.clip_grad_norm_(self.policy.parameters(),1.0)
        self.opt.step()
        for tp,pp in zip(self.target.parameters(),self.policy.parameters()):
            tp.data.copy_(self.tau*pp.data+(1-self.tau)*tp.data)

    def decay_epsilon(self): self.eps = max(self.eps_min, self.eps*self.eps_decay)
    def save_best(self, ev):
        if ev > self._best_eval: self._best_eval = ev; self._best = copy.deepcopy(self.policy.state_dict())
    def load_best(self):
        if self._best: self.policy.load_state_dict(self._best); self.target.load_state_dict(self._best)


def make_base_env(df, cfg):
    return ThreeEchelonEnv(df,
        lead_time_1=cfg["lead_time_1"], lead_time_2=cfg["lead_time_2"],
        lead_time_3=cfg["lead_time_3"],
        h_E1=cfg["h_E1"], h_E2=cfg["h_E2"], h_E3=cfg["h_E3"],
        b_E3=cfg["b_E3"], c_E1=cfg["c_E1"], c_E2=cfg["c_E2"], c_E3=cfg["c_E3"],
        n_actions=cfg["n_actions"])


def greedy_eval(agent, env_data, cfg, aware=True):
    base = make_base_env(env_data, cfg)
    env  = DisruptionEnv(base, p_shock=cfg["p_shock"],
                         max_d_len=cfg["max_disruption_len"], awareness=aware)
    state = env.reset(); saved = agent.eps; agent.eps = 0.0
    total_r, info_log, done = 0.0, [], False
    ss = env.state_size
    while not done:
        a = agent.act(state)
        ns, r, done, info = env.step(a)
        info_log.append(info); total_r += r
        state = ns if ns is not None else np.zeros(ss)
    agent.eps = saved
    return total_r, info_log, env


def train_condition(condition_name, use_disruption_in_train, awareness, cfg, episodes, season):
    print(f"\n{'='*55}\n  C1: {condition_name} | episodes={episodes}\n{'='*55}")
    ref_df = prepare_env_data(generate_demand(season, seed=cfg["train_seed_base"]), season)
    base   = make_base_env(ref_df, cfg)
    ref_env = DisruptionEnv(base, p_shock=cfg["p_shock"] if use_disruption_in_train else 0.0,
                            max_d_len=cfg["max_disruption_len"], awareness=awareness)
    ss = ref_env.state_size; aa = ref_env.action_size
    val_df = prepare_env_data(generate_demand(season, seed=cfg["val_seed"]), season)
    agent = Agent(ss, aa, cfg, episodes)
    rewards = []; t0 = time.time(); zeros = np.zeros(ss, dtype=np.float32)

    for ep in range(episodes):
        df = prepare_env_data(generate_demand(season, seed=cfg["train_seed_base"]+ep), season)
        base_env = make_base_env(df, cfg)
        env = DisruptionEnv(base_env,
                            p_shock=cfg["p_shock"] if use_disruption_in_train else 0.0,
                            max_d_len=cfg["max_disruption_len"], awareness=awareness)
        state = env.reset(); ep_r = 0.0; done = False
        while not done:
            action = agent.act(state)
            ns, r, done, info = env.step(action)
            ns2 = ns if ns is not None else zeros
            agent.buf.push(state, action, r, ns2, float(done))
            agent.learn(); state = ns2; ep_r += r
        agent.decay_epsilon(); rewards.append(ep_r)

        if ep % 50 == 0 or ep == episodes-1:
            ev_r, ev_log, ev_env = greedy_eval(agent, val_df, cfg, aware=awareness)
            agent.save_best(ev_r)
            bw = ev_env.bullwhip_ratio(); svc = ev_env.service_level(ev_log)
            print(f"  Ep {ep:>4d} | {condition_name[:12]:12s} | Eval={ev_r:>10,.0f} | "
                  f"ε={agent.eps:.3f} | BW={bw:.3f} | SL={svc:.3f} | {time.time()-t0:.0f}s")

    agent.load_best()
    return agent, rewards


def compute_metrics_c1(info_log, env):
    td = sum(d["demand"] for d in info_log)
    tb = sum(d["backlog_E3"] if "backlog_E3" in d else d.get("backlog_R",0) for d in info_log)
    tc = sum(d.get("holding_E1",0)+d.get("holding_E2",0)+d.get("holding_E3",0)
             +d.get("backorder_E3",0)+d.get("order_cost_E1",0)+d.get("order_cost_E2",0)
             +d.get("order_cost_E3",0) for d in info_log)
    disrupt_days = sum(1 for d in info_log if d.get("disruption_active", False))
    disrupt_sl_log = [d for d in info_log if d.get("disruption_active", False)]
    normal_log     = [d for d in info_log if not d.get("disruption_active", False)]
    disrupt_sl = (1.0 - sum(d.get("backlog_E3", d.get("backlog_R",0)) for d in disrupt_sl_log)
                  / max(sum(d["demand"] for d in disrupt_sl_log), 1)) if disrupt_sl_log else None
    normal_sl  = (1.0 - sum(d.get("backlog_E3", d.get("backlog_R",0)) for d in normal_log)
                  / max(sum(d["demand"] for d in normal_log), 1)) if normal_log else None
    bw = env.bullwhip_ratio()
    return {
        "service_level":         round(1.0 - tb/max(td,1), 4),
        "service_level_normal":  round(normal_sl, 4) if normal_sl is not None else None,
        "service_level_disruption": round(disrupt_sl, 4) if disrupt_sl is not None else None,
        "total_cost":            round(float(tc), 2),
        "bullwhip_ratio":        round(float(bw),4) if not np.isnan(bw) else None,
        "disruption_days":       disrupt_days,
        "total_demand":          int(td),
    }


def make_plots(all_results, rewards_by_cond):
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [Plots] matplotlib not available."); return

    conds  = [r["condition"] for r in all_results]
    svc    = [r["metrics"]["service_level"] for r in all_results]
    svc_d  = [r["metrics"]["service_level_disruption"] or 0 for r in all_results]
    svc_n  = [r["metrics"]["service_level_normal"] or 0 for r in all_results]
    bw     = [r["metrics"]["bullwhip_ratio"] or 0 for r in all_results]
    colors = ["steelblue","darkorange","seagreen","crimson"][:len(conds)]

    # 1. Training curves
    fig, ax = plt.subplots(figsize=(12,5))
    for i, (cond, rews) in enumerate(zip(conds, rewards_by_cond)):
        sm = pd.Series(rews).rolling(20, min_periods=1).mean()
        ax.plot(sm, label=cond, color=colors[i])
    ax.set_xlabel("Episode"); ax.set_ylabel("Smoothed Reward (MA-20)")
    ax.set_title("C1 — Training Curves by Condition"); ax.legend()
    plt.tight_layout(); plt.savefig(PLOTS_DIR/"training_curves.png", dpi=150)
    plt.close(); print("  ✓ Training curves saved")

    # 2. SL by window (normal vs disruption)
    x = np.arange(len(conds)); width = 0.3
    fig, ax = plt.subplots(figsize=(10,6))
    ax.bar(x-width, svc_n, width, label="Normal days", color="steelblue")
    ax.bar(x,       svc_d, width, label="Disruption days", color="crimson")
    ax.bar(x+width, svc,   width, label="Overall SL", color="seagreen", alpha=0.7)
    ax.set_xticks(x); ax.set_xticklabels(conds, rotation=15)
    ax.set_ylabel("Service Level"); ax.set_title("C1 — Service Level by Disruption Window")
    ax.legend(); ax.set_ylim(0,1.05); plt.tight_layout()
    plt.savefig(PLOTS_DIR/"service_level_by_window.png", dpi=150)
    plt.close(); print("  ✓ SL by window saved")

    # 3. Severity comparison bar
    fig, ax = plt.subplots(figsize=(9,5))
    bars = ax.bar(conds, svc, color=colors)
    ax.set_ylabel("Overall Service Level"); ax.set_title("C1 — Service Level by Condition")
    for bar, v in zip(bars, svc):
        ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+0.005, f"{v:.4f}", ha="center", fontsize=10)
    ax.set_ylim(0, 1.05); plt.tight_layout()
    plt.savefig(PLOTS_DIR/"severity_comparison.png", dpi=150)
    plt.close(); print("  ✓ Severity comparison saved")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    episodes = 50 if args.smoke_test else args.episodes
    season   = CONFIG["season_type"]

    print(f"\n{'#'*55}")
    print(f"  EXPERIMENT C1 — Disruption Robustness")
    print(f"  p_shock={CONFIG['p_shock']} | max_D={CONFIG['max_disruption_len']} days")
    print(f"  Episodes/condition: {episodes}")
    print(f"{'#'*55}")

    with open(RESULTS_DIR/"config.json","w") as f:
        json.dump({**CONFIG,"episodes":episodes}, f, indent=2)

    test_df = prepare_env_data(generate_demand(season, seed=CONFIG["test_seed"]), season)

    # Conditions: (name, disrupt_in_train, awareness)
    conditions = [
        ("Baseline (no disruption)", False, False),
        ("Naive (no train disruption)", False, False),
        ("Aware (disruption-trained)", True,  True),
    ]

    all_results = []; rewards_by_cond = []

    for cond_name, disrupt_train, aware in conditions:
        agent, rewards = train_condition(
            cond_name, disrupt_train, aware, CONFIG, episodes, season)
        rewards_by_cond.append(rewards)

        # Eval: Baseline tested without disruption; others tested WITH disruption
        use_disruption_at_test = (cond_name != "Baseline (no disruption)")
        if use_disruption_at_test:
            _, info_log, ev_env = greedy_eval(agent, test_df, CONFIG, aware=aware)
        else:
            # No disruption eval for baseline
            base_env = make_base_env(test_df, CONFIG)
            env = DisruptionEnv(base_env, p_shock=0.0, max_d_len=1, awareness=False)
            state = env.reset(); saved = agent.eps; agent.eps = 0.0
            info_log = []; done = False
            while not done:
                a = agent.act(state)
                ns, r, done, info = env.step(a)
                info_log.append(info)
                state = ns if ns is not None else np.zeros(env.state_size)
            agent.eps = saved; ev_env = env

        metrics = compute_metrics_c1(info_log, ev_env)
        all_results.append({"condition": cond_name, "metrics": metrics})
        print(f"\n  {cond_name}:")
        print(f"    SL Overall={metrics['service_level']:.4f} | "
              f"SL Normal={metrics['service_level_normal']} | "
              f"SL Disruption={metrics['service_level_disruption']}")
        print(f"    Cost={metrics['total_cost']:,.0f} | BW={metrics['bullwhip_ratio']} | "
              f"Disruption days={metrics['disruption_days']}")

    print(f"\n{'='*55}")
    print(f"  C1 RESULTS SUMMARY")
    print(f"  {'Condition':35s} | {'SL':7s} | {'SL_D':7s} | {'SL_N':7s}")
    print(f"  {'-'*60}")
    for r in all_results:
        m = r["metrics"]
        print(f"  {r['condition']:35s} | {m['service_level']:7.4f} | "
              f"{str(m['service_level_disruption']):7s} | {str(m['service_level_normal']):7s}")
    print(f"{'='*55}")

    summary = {"experiment": "C1_disruption_robustness", "episodes": episodes, "results": all_results}
    with open(RESULTS_DIR/"summary.json","w") as f: json.dump(summary, f, indent=2)
    with open(RESULTS_DIR/"experiment_log.jsonl","w") as f:
        for r in all_results: f.write(json.dumps(r)+"\n")

    make_plots(all_results, rewards_by_cond)
    print(f"\n  ✅ Experiment C1 complete. Results → {RESULTS_DIR}/summary.json")


if __name__ == "__main__":
    main()
