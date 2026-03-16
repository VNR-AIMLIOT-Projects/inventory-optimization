#!/usr/bin/env python3
"""
autoresearch_eval.py — Standalone training + evaluation script for autoresearch.

This is the equivalent of `uv run train.py` in Karpathy's autoresearch.
Run it to train a DQN agent and evaluate it against baselines.

Usage:
    python autoresearch_eval.py                    # 100 episodes (default, ~2 min)
    python autoresearch_eval.py --episodes 200     # 200 episodes (~4 min)
    python autoresearch_eval.py --season summer    # change season type

The script prints a structured summary at the end that can be parsed by grep.
"""

import sys
import time
import argparse
import numpy as np

from demand import generate_demand, prepare_env_data
from trainer import train_agent, _greedy_eval, run_perfect_human_oracle_fixed, run_rule_baseline
from environment import InventoryEnvironment
from trainer import _compute_adaptive_params


def main():
    parser = argparse.ArgumentParser(description="Autoresearch: RL Inventory Optimization Experiment")
    parser.add_argument("--episodes", type=int, default=100,
                        help="Number of training episodes (default: 100)")
    parser.add_argument("--season", type=str, default="summer",
                        choices=["summer", "winter"],
                        help="Season type for demand generation (default: summer)")
    parser.add_argument("--eval-seed", type=int, default=999,
                        help="Seed for evaluation demand (default: 999)")
    parser.add_argument("--decay", type=str, default="exponential",
                        choices=["exponential", "linear"],
                        help="Epsilon decay type (default: exponential)")
    args = parser.parse_args()

    print(f"=== Autoresearch Experiment ===")
    print(f"Episodes: {args.episodes} | Season: {args.season} | Decay: {args.decay}")
    print(f"Eval seed: {args.eval_seed}")
    print()

    # ---- Train ----
    t0 = time.time()

    agent, rewards, max_order, action_step, holding_cost, stockout_penalty = train_agent(
        season_type=args.season,
        episodes=args.episodes,
        decay_type=args.decay,
    )

    training_seconds = time.time() - t0

    # ---- Evaluate on fixed validation demand ----
    eval_data = prepare_env_data(generate_demand(args.season, seed=args.eval_seed), args.season)

    # Greedy evaluation (epsilon = 0)
    eval_env = InventoryEnvironment(
        eval_data, max_order_qty=max_order, action_step=action_step,
        demand_scale=1.0, holding_cost=holding_cost, stockout_penalty=stockout_penalty
    )
    eval_reward = _greedy_eval(agent, eval_data, max_order, action_step,
                                holding_cost=holding_cost, stockout_penalty=stockout_penalty,
                                _env=eval_env)

    # Oracle baseline
    oracle_reward, _ = run_perfect_human_oracle_fixed(
        eval_data, window_size=5, max_order_qty=max_order, action_step=action_step,
        demand_scale=1.0, holding_cost=holding_cost, stockout_penalty=stockout_penalty
    )

    # Rule baseline
    rule_reward, _ = run_rule_baseline(
        eval_data, max_order_qty=max_order, action_step=action_step,
        demand_scale=1.0, holding_cost=holding_cost, stockout_penalty=stockout_penalty
    )

    # Compute metrics
    rl_vs_oracle_pct = (eval_reward / oracle_reward * 100) if oracle_reward != 0 else 0.0
    best_train_reward = float(max(rewards)) if rewards else 0.0

    # ---- Print structured summary ----
    print()
    print("---")
    print(f"eval_reward:        {eval_reward:.2f}")
    print(f"oracle_reward:      {oracle_reward:.2f}")
    print(f"rule_reward:        {rule_reward:.2f}")
    print(f"rl_vs_oracle_pct:   {rl_vs_oracle_pct:.1f}")
    print(f"training_seconds:   {training_seconds:.1f}")
    print(f"episodes:           {args.episodes}")
    print(f"best_train_reward:  {best_train_reward:.2f}")
    print("---")

    # Return non-zero exit code if training produced no improvement
    if eval_reward <= 0:
        print("\nWARNING: eval_reward <= 0, something may be wrong.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
