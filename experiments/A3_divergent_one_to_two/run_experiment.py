"""
Experiment A3 Runner — Divergent 1→2 Joint DDQN
"""

import sys, os, argparse, json, time
import numpy as np
from pathlib import Path

HERE     = Path(__file__).parent
EXP_ROOT = HERE.parent
sys.path.insert(0, str(EXP_ROOT / "shared"))

from demand    import generate_demand, prepare_env_data
from dqn_agent import DDQNAgent, DEVICE
from metrics   import (compute_all_metrics, compute_relative_improvement,
                       ss_policy_params, save_summary, append_episode_log,
                       print_table, make_standard_plots)
from env_divergent import DivergentEnv

RESULTS = HERE / "results"
PLOTS   = HERE / "plots"
RESULTS.mkdir(exist_ok=True)
PLOTS.mkdir(exist_ok=True)

CFG = dict(
    season="summer", num_days=365,
    episodes=500, val_seed=777, test_seed=999, train_base=1000,
    r2_seed_offset=500,
    lead_time_W=3, lead_time_R=1,
    h_W=2.0, h_R=5.0, b_R=500., c_W=2., c_R=2.,
    n_actions=7,
    gamma=0.98, tau=0.005, lr=1e-4,
    batch_size=256, learn_every=4,
    eps_start=1.0, eps_min=0.05,
    capacity=100_000, hidden=256,
)


def make_env(df_r1, df_r2):
    return DivergentEnv(
        df_r1, df_r2,
        lead_time_W=CFG["lead_time_W"], lead_time_R=CFG["lead_time_R"],
        h_W=CFG["h_W"], h_R=CFG["h_R"], b_R=CFG["b_R"],
        c_W=CFG["c_W"], c_R=CFG["c_R"], n_actions=CFG["n_actions"],
    )


def greedy_eval(agent, df_r1, df_r2):
    env = make_env(df_r1, df_r2)
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


def run_ss_baseline(df_r1, df_r2):
    env = make_env(df_r1, df_r2)
    combined = df_r1["demand"] + df_r2["demand"]
    s_W, S_W = ss_policy_params(combined, env.L_W)
    s_R, S_R = ss_policy_params(df_r1["demand"], env.L_R)
    env.reset()
    total, info_log, done = 0.0, [], False
    while not done:
        pos_W = env.inv_W + sum(env.pipe_W)
        aW = max(0, S_W - pos_W) if pos_W < s_W else 0
        aW = min(env.max_W, round(aW / env.step_W) * env.step_W)

        pos_R1 = env.inv_R1 + sum(env.pipe_R1) - env.bl_R1
        aR1 = max(0, S_R - pos_R1) if pos_R1 < s_R else 0
        aR1 = min(env.max_R, round(aR1 / env.step_R) * env.step_R)

        pos_R2 = env.inv_R2 + sum(env.pipe_R2) - env.bl_R2
        aR2 = max(0, S_R - pos_R2) if pos_R2 < s_R else 0
        aR2 = min(env.max_R, round(aR2 / env.step_R) * env.step_R)

        idx = env.encode_action(aW, aR1, aR2)
        _, r, done, info = env.step(idx)
        info_log.append(info)
        total += r
    return total, info_log


def run_oracle_baseline(df_r1, df_r2, window=5):
    env = make_env(df_r1, df_r2)
    d1 = env.data_R1["demand"].values
    d2 = env.data_R2["demand"].values
    env.reset()
    total, info_log, done = 0.0, [], False
    while not done:
        t   = env.t
        end = min(t + window, len(d1))
        fd1 = int(d1[t:end].sum())
        fd2 = int(d2[t:end].sum())

        pos_W = env.inv_W + sum(env.pipe_W)
        aW = max(0, fd1 + fd2 - pos_W)
        aW = min(env.max_W, round(aW / env.step_W) * env.step_W)

        pos_R1 = env.inv_R1 + sum(env.pipe_R1)
        aR1 = max(0, fd1 - pos_R1)
        aR1 = min(env.max_R, round(aR1 / env.step_R) * env.step_R)

        pos_R2 = env.inv_R2 + sum(env.pipe_R2)
        aR2 = max(0, fd2 - pos_R2)
        aR2 = min(env.max_R, round(aR2 / env.step_R) * env.step_R)

        idx = env.encode_action(aW, aR1, aR2)
        _, r, done, info = env.step(idx)
        info_log.append(info)
        total += r
    return total, info_log


def train(episodes):
    print("\n" + "=" * 62)
    print("  Experiment A3: Divergent 1->2 Joint DDQN")
    print("  Episodes: {}  |  Device: {}".format(episodes, DEVICE))
    print("=" * 62)

    seed0 = CFG["train_base"]
    df_r1 = prepare_env_data(generate_demand(CFG["season"], seed=seed0))
    df_r2 = prepare_env_data(generate_demand(CFG["season"], seed=seed0 + CFG["r2_seed_offset"]))
    ref_env = make_env(df_r1, df_r2)

    agent = DDQNAgent(
        ref_env.state_size, ref_env.action_size, episodes=episodes,
        lr=CFG["lr"], gamma=CFG["gamma"], tau=CFG["tau"],
        batch_size=CFG["batch_size"], learn_every=CFG["learn_every"],
        eps_start=CFG["eps_start"], eps_min=CFG["eps_min"],
        capacity=CFG["capacity"], hidden=CFG["hidden"],
    )

    val_r1 = prepare_env_data(generate_demand(CFG["season"], seed=CFG["val_seed"]))
    val_r2 = prepare_env_data(generate_demand(CFG["season"],
                              seed=CFG["val_seed"] + CFG["r2_seed_offset"]))
    rewards = []
    t0 = time.time()

    for ep in range(episodes):
        ep_r1 = prepare_env_data(generate_demand(CFG["season"], seed=seed0 + ep))
        ep_r2 = prepare_env_data(generate_demand(CFG["season"],
                                  seed=seed0 + ep + CFG["r2_seed_offset"]))
        env   = make_env(ep_r1, ep_r2)
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
            ev_r, ev_log, ev_env = greedy_eval(agent, val_r1, val_r2)
            agent.save_best(ev_r)
            bw  = ev_env.bullwhip_ratio()
            svc = ev_env.service_level(ev_log)
            avg50 = np.mean(rewards[-50:])
            elapsed = time.time() - t0
            print("  Ep {:>4d}/{} | Train:{:>13,.0f} | Avg50:{:>13,.0f} | "
                  "Eval:{:>13,.0f} | eps={:.3f} | BW={:.3f} | Svc={:.3f} | {:.0f}s".format(
                      ep, episodes, ep_r, avg50, ev_r, agent.epsilon, bw, svc, elapsed))
            append_episode_log({
                "episode": ep, "train_reward": float(ep_r),
                "avg50": float(avg50), "eval_reward": float(ev_r),
                "epsilon": float(agent.epsilon),
                "bullwhip": float(bw) if not np.isnan(bw) else None,
                "service_level": float(svc),
            }, RESULTS)

    agent.load_best()
    return agent, rewards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--smoke-test", action="store_true")
    args = parser.parse_args()
    eps = 50 if args.smoke_test else args.episodes

    json.dump({**CFG, "episodes": eps}, open(RESULTS / "config.json", "w"), indent=2)
    agent, rewards = train(eps)

    test_r1 = prepare_env_data(generate_demand(CFG["season"], seed=CFG["test_seed"]))
    test_r2 = prepare_env_data(generate_demand(CFG["season"],
                               seed=CFG["test_seed"] + CFG["r2_seed_offset"]))

    print("\n  Evaluating Joint DDQN on test demand...")
    j_r, j_log, j_env = greedy_eval(agent, test_r1, test_r2)
    j_m = compute_all_metrics(j_log)
    print_table(j_m, "Joint DDQN -- A3 Divergent 1->2")

    summary = {"experiment": "A3_divergent_one_to_two", "episodes": eps,
               "joint_ddqn": j_m, "comparisons": []}

    if not args.smoke_test:
        print("\n  Running (s,S) baseline...")
        ss_r, ss_log = run_ss_baseline(test_r1, test_r2)
        ss_m = compute_all_metrics(ss_log)
        print_table(ss_m, "(s,S) Policy")
        summary["ss_policy"] = ss_m
        summary["comparisons"].append(compute_relative_improvement(j_m, "(s,S)", ss_m))

        print("\n  Running Oracle (5-day) baseline...")
        or_r, or_log = run_oracle_baseline(test_r1, test_r2)
        or_m = compute_all_metrics(or_log)
        print_table(or_m, "Oracle (5-day)")
        summary["oracle"] = or_m
        summary["comparisons"].append(compute_relative_improvement(j_m, "Oracle", or_m))

        for c in summary["comparisons"]:
            bw_str = "N/A" if not c["bullwhip_reduction_pct"] else "{:+.1f}%".format(c["bullwhip_reduction_pct"])
            print("  vs {:15s}: Cost D={:+.1f}%  Svc D={:+.4f}  BW D={}".format(
                c["vs_baseline"], c["cost_reduction_pct"], c["service_level_delta"], bw_str))

        make_standard_plots(rewards, j_log,
                            {"(s,S)": ss_log, "Oracle": or_log},
                            "A3 Divergent 1->2 Retailers", str(PLOTS))

    save_summary(summary, RESULTS)
    print("\n  A3 complete -> {}".format(RESULTS / "summary.json"))


if __name__ == "__main__":
    main()
