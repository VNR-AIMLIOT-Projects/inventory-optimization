"""
Experiment A2 Runner — Three-Echelon Linear Joint DDQN
=======================================================
Usage:
    python3 run_experiment.py              # 500 episodes, all baselines
    python3 run_experiment.py --smoke-test # 50 episodes, quick check
"""

import sys, os, argparse, json, time
import numpy as np
import pandas as pd
from pathlib import Path
from collections import deque

HERE     = Path(__file__).parent
EXP_ROOT = HERE.parent
sys.path.insert(0, str(EXP_ROOT / "shared"))

from demand      import generate_demand, prepare_env_data
from dqn_agent   import DDQNAgent, DEVICE
from metrics     import (compute_all_metrics, compute_relative_improvement,
                         ss_policy_params, save_summary, append_episode_log,
                         print_table, make_standard_plots)
from env_three_echelon import ThreeEchelonEnv

RESULTS = HERE / "results"
PLOTS   = HERE / "plots"
RESULTS.mkdir(exist_ok=True)
PLOTS.mkdir(exist_ok=True)

# ── Config ────────────────────────────────────────────────────────────────────
CFG = dict(
    season="summer", num_days=365,
    episodes=500, val_seed=777, test_seed=999, train_base=1000,
    lead_time_1=4, lead_time_2=2, lead_time_3=1,
    h_E1=1.0, h_E2=3.0, h_E3=5.0,
    b_E3=500., c_E1=2., c_E2=2., c_E3=2.,
    n_actions=7,
    gamma=0.98, tau=0.005, lr=1e-4,
    batch_size=256, learn_every=4,
    eps_start=1.0, eps_min=0.05,
    capacity=100_000, hidden=256,
)


def make_env(df):
    return ThreeEchelonEnv(
        df,
        lead_time_1=CFG["lead_time_1"], lead_time_2=CFG["lead_time_2"],
        lead_time_3=CFG["lead_time_3"],
        h_E1=CFG["h_E1"], h_E2=CFG["h_E2"], h_E3=CFG["h_E3"],
        b_E3=CFG["b_E3"], c_E1=CFG["c_E1"], c_E2=CFG["c_E2"], c_E3=CFG["c_E3"],
        n_actions=CFG["n_actions"],
    )


def greedy_eval(agent, df):
    env = make_env(df)
    state = env.reset()
    saved, agent.epsilon = agent.epsilon, 0.0
    total, info_log, done = 0.0, [], False
    zeros = np.zeros(env.state_size, dtype=np.float32)
    while not done:
        s2, r, done, info = env.step(agent.greedy_act(state))
        info_log.append(info)
        total += r
        state = s2 if s2 is not None else zeros
    agent.epsilon = saved
    return total, info_log, env


def run_ss_baseline(test_df):
    env = make_env(test_df)
    demand_series = env.data["demand"]
    params = [ss_policy_params(demand_series, L) for L in env.L]
    state = env.reset()
    total, info_log, done = 0.0, [], False
    while not done:
        orders = []
        inventories = [env.inv[i] + sum(env.pipes[i]) for i in range(3)]
        for i in range(3):
            s_i, S_i = params[i]
            pos = inventories[i] - env.bl[i]
            a = max(0, S_i - pos) if pos < s_i else 0
            a = min(env.max_orders[i], round(a / env.act_steps[i]) * env.act_steps[i])
            orders.append(a)
        idx = env.encode_action(*orders)
        _, r, done, info = env.step(idx)
        info_log.append(info); total += r
    return total, info_log


def run_oracle_baseline(test_df, window=7):
    env = make_env(test_df)
    demands = env.data["demand"].values
    state = env.reset()
    total, info_log, done = 0.0, [], False
    while not done:
        t = env.t
        fd = int(demands[t:min(t + window, len(demands))].sum())
        orders = []
        for i in range(3):
            pos = env.inv[i] + sum(env.pipes[i]) - env.bl[i]
            a = max(0, fd - pos)
            a = min(env.max_orders[i], round(a / env.act_steps[i]) * env.act_steps[i])
            orders.append(a)
        idx = env.encode_action(*orders)
        _, r, done, info = env.step(idx)
        info_log.append(info); total += r
    return total, info_log


def train(episodes, smoke=False):
    print(f"\n{'='*62}")
    print(f"  Experiment A2: Three-Echelon Linear Joint DDQN")
    print(f"  Episodes: {episodes}  |  Device: {DEVICE}")
    print(f"{'='*62}")

    ref_df  = prepare_env_data(generate_demand(CFG["season"], seed=CFG["train_base"]))
    ref_env = make_env(ref_df)
    agent   = DDQNAgent(
        ref_env.state_size, ref_env.action_size, episodes=episodes,
        lr=CFG["lr"], gamma=CFG["gamma"], tau=CFG["tau"],
        batch_size=CFG["batch_size"], learn_every=CFG["learn_every"],
        eps_start=CFG["eps_start"], eps_min=CFG["eps_min"],
        capacity=CFG["capacity"], hidden=CFG["hidden"],
    )
    val_df   = prepare_env_data(generate_demand(CFG["season"], seed=CFG["val_seed"]))
    rewards  = []
    t0 = time.time()

    for ep in range(episodes):
        df    = prepare_env_data(generate_demand(CFG["season"], seed=CFG["train_base"] + ep))
        env   = make_env(df)
        state = env.reset()
        ep_r, done = 0.0, False
        zeros = np.zeros(env.state_size, dtype=np.float32)
        while not done:
            a = agent.act(state)
            ns, r, done, _ = env.step(a)
            ns_ = ns if ns is not None else zeros
            agent.step(state, a, r, ns_, done)
            state = ns_
            ep_r += r
        agent.decay_epsilon()
        rewards.append(ep_r)

        if ep % 50 == 0 or ep == episodes - 1:
            ev_r, ev_log, ev_env = greedy_eval(agent, val_df)
            agent.save_best(ev_r)
            bw  = ev_env.bullwhip_ratio()
            svc = ev_env.service_level(ev_log)
            avg50 = np.mean(rewards[-50:])
            print(f"  Ep {ep:>4d}/{episodes} | Train:{ep_r:>13,.0f} | Avg50:{avg50:>13,.0f} | "
                  f"Eval:{ev_r:>13,.0f} | ε={agent.epsilon:.3f} | BW={bw:.3f} | Svc={svc:.3f} | {time.time()-t0:.0f}s")
            append_episode_log({"episode": ep, "train_reward": float(ep_r),
                                 "avg50": float(avg50), "eval_reward": float(ev_r),
                                 "epsilon": float(agent.epsilon),
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

    agent, rewards = train(eps, args.smoke_test)

    test_df = prepare_env_data(generate_demand(CFG["season"], seed=CFG["test_seed"]))
    print("\n  Evaluating Joint DDQN on test demand...")
    j_r, j_log, j_env = greedy_eval(agent, test_df)
    j_m = compute_all_metrics(j_log)
    print_table(j_m, "Joint DDQN — A2 Three-Echelon")

    summary = {"experiment": "A2_three_echelon_linear", "episodes": eps,
               "joint_ddqn": j_m, "comparisons": []}

    if not args.smoke_test:
        print("\n  Running (s,S) baseline...")
        ss_r, ss_log = run_ss_baseline(test_df)
        ss_m = compute_all_metrics(ss_log)
        print_table(ss_m, "(s,S) Policy")
        summary["ss_policy"] = ss_m
        summary["comparisons"].append(compute_relative_improvement(j_m, "(s,S)", ss_m))

        print("\n  Running Oracle (7-day) baseline...")
        or_r, or_log = run_oracle_baseline(test_df, window=7)
        or_m = compute_all_metrics(or_log)
        print_table(or_m, "Oracle (7-day)")
        summary["oracle"] = or_m
        summary["comparisons"].append(compute_relative_improvement(j_m, "Oracle", or_m))

        print(f"\n{'='*62}  FINAL RESULTS — A2  {'='*62}")
        for c in summary["comparisons"]:
            print(f"  vs {c['vs_baseline']:15s}:  Cost Δ={c['cost_reduction_pct']:+.1f}%  "
                  f"BW Δ={str(round(c['bullwhip_reduction_pct'],1))+'%' if c['bullwhip_reduction_pct'] else 'N/A':>8}  "
                  f"Svc Δ={c['service_level_delta']:+.4f}")

        baselines = {"(s,S)": ss_log, "Oracle": or_log}
        make_standard_plots(rewards, j_log, baselines, "A2 Three-Echelon Linear", str(PLOTS))

    save_summary(summary, RESULTS)
    print(f"\n  ✅ A2 complete → {RESULTS}/summary.json")


if __name__ == "__main__":
    main()
