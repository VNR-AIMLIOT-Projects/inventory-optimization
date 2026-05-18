"""
Experiment B2 — Algorithm Ablation: Joint DDQN vs PPO
=======================================================
Both agents trained on identical A1 (2-echelon) environment with seasonal demand.
Compares convergence speed, final service level, cost, and bullwhip ratio.

Usage:
    python3 run_experiment.py              # 500 eps each
    python3 run_experiment.py --smoke-test # 50 eps each
"""

import sys, json, time, argparse, copy, random
import numpy as np
import torch, torch.nn as nn, torch.optim as optim
import torch.distributions as dist
import pandas as pd
from collections import deque
from pathlib import Path

HERE   = Path(__file__).parent
SHARED = HERE.parent / "shared"
A1_DIR = HERE.parent / "A1_two_echelon_linear"
sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(A1_DIR))

from env_two_echelon import TwoEchelonEnv, generate_demand, prepare_env_data

RESULTS_DIR = HERE / "results"
PLOTS_DIR   = HERE / "plots"
RESULTS_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)

_device = torch.device(
    "mps"  if torch.backends.mps.is_available() else
    "cuda" if torch.cuda.is_available() else "cpu"
)
print(f"[B2] Device: {_device}")

CONFIG = {
    "season_type": "summer", "num_days": 365,
    "val_seed": 777, "test_seed": 999, "train_seed_base": 3000,
    "lead_time_W": 3, "lead_time_R": 1,
    "h_W": 2.0, "h_R": 5.0, "b_R": 500.0, "c_W": 2.0, "c_R": 2.0,
    "n_actions_W": 11, "n_actions_R": 11,
    # DDQN
    "ddqn_gamma": 0.98, "ddqn_tau": 0.005, "ddqn_lr": 1e-4,
    "ddqn_epsilon_start": 1.0, "ddqn_epsilon_min": 0.05,
    "ddqn_batch_size": 256, "ddqn_learn_every": 4, "ddqn_replay_capacity": 100_000,
    # PPO
    "ppo_lr": 3e-4, "ppo_gamma": 0.99, "ppo_gae_lambda": 0.95,
    "ppo_clip": 0.2, "ppo_entropy_coef": 0.01,
    "ppo_epochs": 4, "ppo_batch_size": 64,
}

# ── Shared env builder ────────────────────────────────────────────────────────

def make_env(df, cfg):
    return TwoEchelonEnv(df,
        lead_time_W=cfg["lead_time_W"], lead_time_R=cfg["lead_time_R"],
        h_W=cfg["h_W"], h_R=cfg["h_R"], b_R=cfg["b_R"],
        c_W=cfg["c_W"], c_R=cfg["c_R"],
        n_actions_W=cfg["n_actions_W"], n_actions_R=cfg["n_actions_R"])

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


class DDQNAgent:
    def __init__(self, ss, aa, cfg, episodes):
        self.aa = aa; self.gamma = cfg["ddqn_gamma"]; self.tau = cfg["ddqn_tau"]
        self.le = cfg["ddqn_learn_every"]; self.bs = cfg["ddqn_batch_size"]; self._step = 0
        self.eps = cfg["ddqn_epsilon_start"]; self.eps_min = cfg["ddqn_epsilon_min"]
        self.eps_decay = (self.eps_min/self.eps)**(1.0/max(episodes,1))
        self.policy = JointDQN(ss,aa).to(_device)
        self.target = JointDQN(ss,aa).to(_device)
        self.target.load_state_dict(self.policy.state_dict()); self.target.eval()
        self.opt = optim.Adam(self.policy.parameters(), lr=cfg["ddqn_lr"])
        self.buf = ReplayBuffer(cfg["ddqn_replay_capacity"])
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
        nn.utils.clip_grad_norm_(self.policy.parameters(),1.0); self.opt.step()
        for tp,pp in zip(self.target.parameters(),self.policy.parameters()):
            tp.data.copy_(self.tau*pp.data+(1-self.tau)*tp.data)

    def decay_epsilon(self): self.eps = max(self.eps_min, self.eps*self.eps_decay)
    def save_best(self, ev):
        if ev > self._best_eval: self._best_eval = ev; self._best = copy.deepcopy(self.policy.state_dict())
    def load_best(self):
        if self._best: self.policy.load_state_dict(self._best); self.target.load_state_dict(self._best)


# ── PPO ───────────────────────────────────────────────────────────────────────

class ActorCritic(nn.Module):
    """Shared MLP trunk with separate actor (softmax) and critic (scalar) heads."""
    def __init__(self, s, a):
        super().__init__()
        self.shared = nn.Sequential(
            nn.Linear(s,128), nn.ReLU(), nn.Linear(128,128), nn.ReLU())
        self.actor  = nn.Linear(128, a)
        self.critic = nn.Linear(128, 1)
    def forward(self, x):
        h = self.shared(x)
        return self.actor(h), self.critic(h)
    def get_action(self, state):
        logits, val = self.forward(state)
        probs  = torch.softmax(logits, dim=-1)
        m      = torch.distributions.Categorical(probs)
        action = m.sample()
        return action, m.log_prob(action), m.entropy(), val.squeeze(-1)


class PPOAgent:
    def __init__(self, ss, aa, cfg):
        self.gamma      = cfg["ppo_gamma"]
        self.gae_lambda = cfg["ppo_gae_lambda"]
        self.clip       = cfg["ppo_clip"]
        self.ent_coef   = cfg["ppo_entropy_coef"]
        self.epochs     = cfg["ppo_epochs"]
        self.bs         = cfg["ppo_batch_size"]
        self.net = ActorCritic(ss, aa).to(_device)
        self.opt = optim.Adam(self.net.parameters(), lr=cfg["ppo_lr"])
        self._best = None; self._best_eval = -np.inf

    def act(self, state):
        s = torch.FloatTensor(state).unsqueeze(0).to(_device)
        with torch.no_grad():
            action, log_prob, _, val = self.net.get_action(s)
        return action.item(), log_prob.item(), val.item()

    def update(self, rollout):
        """Standard PPO update on a full episode rollout."""
        states  = torch.FloatTensor(np.array(rollout["states"])).to(_device)
        actions = torch.LongTensor(rollout["actions"]).to(_device)
        old_lp  = torch.FloatTensor(rollout["log_probs"]).to(_device)
        returns = torch.FloatTensor(rollout["returns"]).to(_device)
        advs    = torch.FloatTensor(rollout["advantages"]).to(_device)
        advs    = (advs - advs.mean()) / (advs.std() + 1e-8)

        n = len(states)
        for _ in range(self.epochs):
            idx = torch.randperm(n)
            for start in range(0, n, self.bs):
                b = idx[start:start+self.bs]
                logits, vals = self.net(states[b])
                probs = torch.softmax(logits, dim=-1)
                m = torch.distributions.Categorical(probs)
                new_lp = m.log_prob(actions[b])
                entropy = m.entropy().mean()
                ratio  = (new_lp - old_lp[b]).exp()
                s1 = ratio * advs[b]
                s2 = ratio.clamp(1-self.clip, 1+self.clip) * advs[b]
                actor_loss  = -torch.min(s1, s2).mean()
                critic_loss = nn.MSELoss()(vals.squeeze(-1), returns[b])
                loss = actor_loss + 0.5*critic_loss - self.ent_coef*entropy
                self.opt.zero_grad(); loss.backward()
                nn.utils.clip_grad_norm_(self.net.parameters(), 0.5)
                self.opt.step()

    def save_best(self, ev):
        if ev > self._best_eval: self._best_eval = ev; self._best = copy.deepcopy(self.net.state_dict())
    def load_best(self):
        if self._best: self.net.load_state_dict(self._best)


def compute_gae(rewards, values, dones, gamma, gae_lambda):
    """Generalised Advantage Estimation."""
    n = len(rewards)
    advs = np.zeros(n, dtype=np.float32)
    gae = 0.0
    for t in reversed(range(n)):
        delta = rewards[t] + gamma * (values[t+1] if t+1 < n else 0.0) * (1-dones[t]) - values[t]
        gae = delta + gamma * gae_lambda * (1-dones[t]) * gae
        advs[t] = gae
    returns = advs + np.array(values[:n])
    return advs, returns


# ── Greedy eval ───────────────────────────────────────────────────────────────

def greedy_eval_ddqn(agent, env_data, cfg):
    env = make_env(env_data, cfg)
    state = env.reset(); saved = agent.eps; agent.eps = 0.0
    total_r, info_log, done = 0.0, [], False
    while not done:
        a = agent.act(state)
        ns, r, done, info = env.step(a)
        info_log.append(info); total_r += r
        state = ns if ns is not None else np.zeros(env.state_size)
    agent.eps = saved
    return total_r, info_log, env


def greedy_eval_ppo(agent, env_data, cfg):
    env = make_env(env_data, cfg)
    state = env.reset(); total_r, info_log, done = 0.0, [], False
    while not done:
        action, _, _ = agent.act(state)
        ns, r, done, info = env.step(action)
        info_log.append(info); total_r += r
        state = ns if ns is not None else np.zeros(env.state_size)
    return total_r, info_log, env


# ── Training ──────────────────────────────────────────────────────────────────

def train_ddqn(cfg, episodes, season):
    print(f"\n{'='*55}\n  B2: Training Joint DDQN | {episodes} eps\n{'='*55}")
    ref_df = prepare_env_data(generate_demand(season, seed=cfg["train_seed_base"]), season)
    ref_env = make_env(ref_df, cfg)
    ss = ref_env.state_size; aa = ref_env.action_size
    val_df = prepare_env_data(generate_demand(season, seed=cfg["val_seed"]), season)
    agent = DDQNAgent(ss, aa, cfg, episodes)
    rewards = []; t0 = time.time(); zeros = np.zeros(ss, dtype=np.float32)
    ep90 = None  # episode at which 90% SL first reached

    for ep in range(episodes):
        df = prepare_env_data(generate_demand(season, seed=cfg["train_seed_base"]+ep), season)
        env = make_env(df, cfg)
        state = env.reset(); ep_r = 0.0; done = False
        while not done:
            action = agent.act(state)
            ns, r, done, info = env.step(action)
            ns2 = ns if ns is not None else zeros
            agent.buf.push(state, action, r, ns2, float(done))
            agent.learn(); state = ns2; ep_r += r
        agent.decay_epsilon(); rewards.append(ep_r)

        if ep % 50 == 0 or ep == episodes-1:
            ev_r, ev_log, ev_env = greedy_eval_ddqn(agent, val_df, cfg)
            agent.save_best(ev_r)
            bw = ev_env.bullwhip_ratio(); svc = ev_env.service_level(ev_log)
            if ep90 is None and svc >= 0.90: ep90 = ep
            print(f"  Ep {ep:>4d} | DDQN | Eval={ev_r:>10,.0f} | "
                  f"ε={agent.eps:.3f} | BW={bw:.3f} | SL={svc:.3f} | {time.time()-t0:.0f}s")

    agent.load_best()
    return agent, rewards, ep90


def train_ppo(cfg, episodes, season):
    print(f"\n{'='*55}\n  B2: Training Joint PPO | {episodes} eps\n{'='*55}")
    ref_df = prepare_env_data(generate_demand(season, seed=cfg["train_seed_base"]), season)
    ref_env = make_env(ref_df, cfg)
    ss = ref_env.state_size; aa = ref_env.action_size
    val_df = prepare_env_data(generate_demand(season, seed=cfg["val_seed"]), season)
    agent = PPOAgent(ss, aa, cfg)
    rewards = []; t0 = time.time(); ep90 = None

    for ep in range(episodes):
        df = prepare_env_data(generate_demand(season, seed=cfg["train_seed_base"]+ep), season)
        env = make_env(df, cfg)
        state = env.reset(); done = False
        rollout = {"states":[],"actions":[],"log_probs":[],"rewards":[],"values":[],"dones":[]}

        while not done:
            action, log_prob, val = agent.act(state)
            ns, r, done, info = env.step(action)
            rollout["states"].append(state)
            rollout["actions"].append(action)
            rollout["log_probs"].append(log_prob)
            rollout["rewards"].append(r)
            rollout["values"].append(val)
            rollout["dones"].append(float(done))
            state = ns if ns is not None else np.zeros(ss)

        advs, returns = compute_gae(
            rollout["rewards"], rollout["values"], rollout["dones"],
            cfg["ppo_gamma"], cfg["ppo_gae_lambda"])
        rollout["advantages"] = advs; rollout["returns"] = returns
        agent.update(rollout)
        ep_r = sum(rollout["rewards"]); rewards.append(ep_r)

        if ep % 50 == 0 or ep == episodes-1:
            ev_r, ev_log, ev_env = greedy_eval_ppo(agent, val_df, cfg)
            agent.save_best(ev_r)
            bw = ev_env.bullwhip_ratio(); svc = ev_env.service_level(ev_log)
            if ep90 is None and svc >= 0.90: ep90 = ep
            print(f"  Ep {ep:>4d} |  PPO | Eval={ev_r:>10,.0f} | "
                  f"BW={bw:.3f} | SL={svc:.3f} | {time.time()-t0:.0f}s")

    agent.load_best()
    return agent, rewards, ep90


def compute_metrics(info_log, env):
    td = sum(d["demand"] for d in info_log)
    tb = sum(d["backlog_R"] for d in info_log)
    tc = sum(d["holding_W"]+d["holding_R"]+d["backorder_R"]+d["order_cost_W"]+d["order_cost_R"]
             for d in info_log)
    bw = env.bullwhip_ratio()
    ep_r = -tc
    return {
        "service_level":  round(1.0-tb/max(td,1),4),
        "total_cost":     round(float(tc),2),
        "episode_reward": round(float(ep_r),2),
        "bullwhip_ratio": round(float(bw),4) if not np.isnan(bw) else None,
        "order_std_W":    round(float(np.std([d["a_W"] for d in info_log])),2),
    }


def make_plots(ddqn_rewards, ppo_rewards, ddqn_m, ppo_m, ddqn_ep90, ppo_ep90):
    try:
        import matplotlib; matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("  [Plots] matplotlib not available."); return

    # 1. Training curves
    fig, ax = plt.subplots(figsize=(12,5))
    for rews, label, color in [(ddqn_rewards,"Joint DDQN","steelblue"),
                                (ppo_rewards, "Joint PPO",  "darkorange")]:
        sm = pd.Series(rews).rolling(20, min_periods=1).mean()
        ax.plot(sm, label=label, color=color)
    if ddqn_ep90: ax.axvline(ddqn_ep90, color="steelblue", ls=":", alpha=0.7)
    if ppo_ep90:  ax.axvline(ppo_ep90,  color="darkorange", ls=":", alpha=0.7)
    ax.set_xlabel("Episode"); ax.set_ylabel("Smoothed Reward (MA-20)")
    ax.set_title("B2 — Training Curves: Joint DDQN vs PPO"); ax.legend()
    plt.tight_layout(); plt.savefig(PLOTS_DIR/"training_curves_comparison.png", dpi=150)
    plt.close(); print("  ✓ Training curves saved")

    # 2. Metric comparison bar
    metrics_names = ["service_level","bullwhip_ratio","order_std_W"]
    labels_nice   = ["Service Level","Bullwhip Ratio","Warehouse Order Std"]
    fig, axes = plt.subplots(1,3,figsize=(14,5))
    for ax, mkey, mlabel in zip(axes, metrics_names, labels_nice):
        vals = [ddqn_m.get(mkey,0) or 0, ppo_m.get(mkey,0) or 0]
        bars = ax.bar(["DDQN","PPO"], vals, color=["steelblue","darkorange"])
        ax.set_title(mlabel)
        for bar, v in zip(bars, vals):
            ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()*1.01,
                    f"{v:.4f}", ha="center", fontsize=10)
    plt.suptitle("B2 — DDQN vs PPO Evaluation Metrics"); plt.tight_layout()
    plt.savefig(PLOTS_DIR/"eval_metric_comparison.png", dpi=150)
    plt.close(); print("  ✓ Metric comparison saved")

    # 3. Convergence comparison
    ddqn_sl = pd.Series(ddqn_rewards).rolling(20,min_periods=1).mean()
    ppo_sl  = pd.Series(ppo_rewards).rolling(20,min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(12,5))
    ax.plot(ddqn_sl, color="steelblue", label="DDQN (MA-20 reward)")
    ax.plot(ppo_sl,  color="darkorange", label="PPO (MA-20 reward)")
    if ddqn_ep90: ax.axvline(ddqn_ep90, color="steelblue", ls="--", label=f"DDQN 90% SL @ ep{ddqn_ep90}")
    if ppo_ep90:  ax.axvline(ppo_ep90,  color="darkorange", ls="--", label=f"PPO 90% SL @ ep{ppo_ep90}")
    ax.set_xlabel("Episode"); ax.set_ylabel("MA-20 Reward")
    ax.set_title("B2 — Convergence Comparison"); ax.legend()
    plt.tight_layout(); plt.savefig(PLOTS_DIR/"convergence_comparison.png", dpi=150)
    plt.close(); print("  ✓ Convergence comparison saved")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    episodes = 50 if args.smoke_test else args.episodes
    season   = CONFIG["season_type"]

    print(f"\n{'#'*55}")
    print(f"  EXPERIMENT B2 — Joint DDQN vs PPO Algorithm Ablation")
    print(f"  Episodes each : {episodes}")
    print(f"  Env: A1 (2-echelon, seasonal, b_R=500)")
    print(f"{'#'*55}")

    with open(RESULTS_DIR/"config.json","w") as f:
        json.dump({**CONFIG,"episodes":episodes}, f, indent=2)

    test_df = prepare_env_data(generate_demand(season, seed=CONFIG["test_seed"]), season)

    ddqn_agent, ddqn_rewards, ddqn_ep90 = train_ddqn(CONFIG, episodes, season)
    ppo_agent,  ppo_rewards,  ppo_ep90  = train_ppo(CONFIG,  episodes, season)

    # Evaluate both
    print("\n  Evaluating DDQN on test set...")
    _, ddqn_log, ddqn_env = greedy_eval_ddqn(ddqn_agent, test_df, CONFIG)
    ddqn_m = compute_metrics(ddqn_log, ddqn_env)

    print("  Evaluating PPO on test set...")
    _, ppo_log,  ppo_env  = greedy_eval_ppo(ppo_agent, test_df, CONFIG)
    ppo_m  = compute_metrics(ppo_log, ppo_env)

    print(f"\n{'='*55}")
    print(f"  B2 RESULTS SUMMARY")
    print(f"  {'Metric':25s} | {'DDQN':>10} | {'PPO':>10}")
    print(f"  {'-'*50}")
    for k in ["service_level","total_cost","bullwhip_ratio","order_std_W"]:
        print(f"  {k:25s} | {str(ddqn_m.get(k)):>10} | {str(ppo_m.get(k)):>10}")
    print(f"  {'Convergence ep (90% SL)':25s} | {str(ddqn_ep90):>10} | {str(ppo_ep90):>10}")
    print(f"{'='*55}")

    summary = {
        "experiment": "B2_ddqn_vs_ppo", "episodes": episodes,
        "ddqn": {**ddqn_m, "convergence_ep_90": ddqn_ep90},
        "ppo":  {**ppo_m,  "convergence_ep_90": ppo_ep90},
    }
    with open(RESULTS_DIR/"summary.json","w") as f: json.dump(summary, f, indent=2)
    with open(RESULTS_DIR/"experiment_log.jsonl","w") as f:
        f.write(json.dumps({"ddqn": summary["ddqn"]}) + "\n")
        f.write(json.dumps({"ppo":  summary["ppo"]})  + "\n")

    make_plots(ddqn_rewards, ppo_rewards, ddqn_m, ppo_m, ddqn_ep90, ppo_ep90)
    print(f"\n  ✅ Experiment B2 complete. Results → {RESULTS_DIR}/summary.json")


if __name__ == "__main__":
    main()
