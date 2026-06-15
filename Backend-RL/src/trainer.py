# import numpy as np
# import pandas as pd
# import matplotlib.pyplot as plt
# from environment import InventoryEnvironment
# from dqn import DQNAgent

# # Helper to plot comparisons
# def plot_comparison(rl_df, oracle_df, rule_df, title, filename):
#     fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
#     min_len = min(len(rl_df), len(oracle_df), len(rule_df))
#     dates = rl_df['date'].iloc[:min_len]

#     # Inventory
#     ax1.plot(dates, rl_df['inventory'].iloc[:min_len], 'b-', label='RL Inventory')
#     ax1.plot(dates, oracle_df['inventory'].iloc[:min_len], 'g--', label='Oracle')
#     ax1.fill_between(dates, rl_df['demand'].iloc[:min_len], alpha=0.3, color='gray', label='Demand')
#     ax1.set_title(f"{title} - Inventory Level")
#     ax1.legend()

#     # Actions
#     ax2.step(dates, rl_df['action_order_qty'].iloc[:min_len], 'b-', where='post', label='RL Order')
#     ax2.step(dates, oracle_df['action_order_qty'].iloc[:min_len], 'g--', where='post', label='Oracle Order')
#     ax2.fill_between(dates, rl_df['demand'].iloc[:min_len], alpha=0.3, color='gray', label='Demand')
#     ax2.set_title(f"{title} - Order Quantity")
#     ax2.legend()
    
#     plt.tight_layout()
#     plt.savefig(filename)
#     print(f"Saved plot: {filename}")
#     plt.close()


# def _compute_adaptive_params(demand_series, max_order_override=None, action_step_override=None, lead_time=2):
#     """
#     Compute max_order_qty and action_step scaled to the demand magnitude.
    
#     max_order must be large enough that the agent CAN meet demand:
#       - At minimum: avg_demand * (lead_time + 1) so one order covers the gap
#       - Also at least peak daily demand so spikes can be handled
#     action_step ≈ max_order / 20  (~20 discrete actions)
    
#     Returns (max_order_qty, action_step)
#     """
#     ACTION_SIZE = 20
    
#     max_demand = int(demand_series.max())
#     avg_demand = float(demand_series.mean())
#     # Ensure the agent can order enough to cover lead-time worth of demand
#     raw_max = max(int(max_demand), int(avg_demand * (lead_time + 1)))
    
#     if action_step_override is not None:
#         action_step = action_step_override
#     else:
#         action_step = max(1, int(raw_max / ACTION_SIZE))
    
#     if max_order_override is not None:
#         max_order = max_order_override
#     else:
#         max_order = raw_max
    
#     return max_order, action_step


# def run_perfect_human_oracle_fixed(env_data, window_size=5, max_order_qty=None, action_step=None, demand_scale=1.0,
#                                     holding_cost=5, stockout_penalty=200):
#     # Adaptive params
#     scaled_demand = env_data['demand'] * demand_scale
#     if max_order_qty is None or action_step is None:
#         adapt_max, adapt_step = _compute_adaptive_params(scaled_demand)
#         max_order_qty = max_order_qty or adapt_max
#         action_step = action_step or adapt_step

#     env = InventoryEnvironment(env_data, max_order_qty=max_order_qty, action_step=action_step, demand_scale=demand_scale,
#                                holding_cost=holding_cost, stockout_penalty=stockout_penalty)
#     demand_series = (env_data['demand'].values * demand_scale).astype(int)
#     n = len(demand_series)
    
#     state = env.reset()
#     total_reward = 0
#     logs = []
    
#     while True:
#         t = env.current_step
#         if t >= n: break
        
#         future_end = min(t + window_size, n)
#         future_demand = demand_series[t:future_end].sum()
#         pipeline = sum(env.order_pipeline)
        
#         needed = max(0, future_demand - env.inv_onhand - pipeline)
        
#         action_qty = min(max_order_qty, max(0, int(needed)))
#         action_qty = round(action_qty / action_step) * action_step
#         if action_qty > max_order_qty:
#             action_qty = (max_order_qty // action_step) * action_step
#         action_index = env.action_space.index(action_qty)
        
#         _, reward, done, info = env.step(action_index)
        
#         logs.append({**info, "reward": reward})
#         total_reward += reward
        
#         if done: break
        
#     return total_reward, pd.DataFrame(logs)


# def run_rule_baseline(env_data, max_order_qty=None, action_step=None, demand_scale=1.0,
#                       holding_cost=5, stockout_penalty=200):
#     scaled_demand = env_data['demand'] * demand_scale
#     if max_order_qty is None or action_step is None:
#         adapt_max, adapt_step = _compute_adaptive_params(scaled_demand)
#         max_order_qty = max_order_qty or adapt_max
#         action_step = action_step or adapt_step

#     env = InventoryEnvironment(env_data, max_order_qty=max_order_qty, action_step=action_step, demand_scale=demand_scale,
#                                holding_cost=holding_cost, stockout_penalty=stockout_penalty)
#     avg_d = scaled_demand.mean()
#     std_d = scaled_demand.std()
    
#     reorder_point = int(avg_d * 3)
#     target_stock = int(reorder_point + avg_d + 1.5 * std_d)
    
#     state = env.reset()
#     total_reward = 0
#     logs = []
    
#     while True:
#         total_stock = env.inv_onhand + sum(env.order_pipeline)
#         if total_stock < reorder_point:
#             needed = target_stock - total_stock
#             action_qty = min(max_order_qty, max(0, int(needed)))
#         else:
#             action_qty = 0
            
#         action_qty = round(action_qty / action_step) * action_step
#         if action_qty > max_order_qty:
#             action_qty = (max_order_qty // action_step) * action_step
#         action_index = env.action_space.index(action_qty)
        
#         _, reward, done, info = env.step(action_index)
        
#         logs.append({**info, "reward": reward})
#         total_reward += reward
#         if done: break
        
#     return total_reward, pd.DataFrame(logs)


# def _greedy_eval(agent, eval_df, max_order, action_step, holding_cost=5, stockout_penalty=200):
#     """Run one greedy episode (epsilon=0) on fixed data. Returns total reward."""
#     env = InventoryEnvironment(eval_df, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
#                                holding_cost=holding_cost, stockout_penalty=stockout_penalty)
#     state = env.reset()
#     total = 0
#     saved_eps = agent.epsilon
#     agent.epsilon = 0.0
#     done = False
#     while not done:
#         action = agent.act(state)
#         next_state, r, done, _ = env.step(action)
#         total += r
#         state = next_state
#     agent.epsilon = saved_eps
#     return total


# def train_agent(season_type, episodes=500, max_order=None, action_step=None, custom_df=None, decay_type="exponential",
#                 holding_cost=5, stockout_penalty=200, on_episode=None):
#     """
#     Train the RL agent with demand-adaptive action space.
    
#     If max_order / action_step are None, they are automatically computed
#     from the demand data so the agent's action space matches the demand scale.
#     """
#     # --- Prepare data & compute adaptive params ---
#     if custom_df is not None:
#         dummy_data = custom_df.copy()
#     else:
#         from demand import generate_demand, prepare_env_data
#         dummy_data = prepare_env_data(generate_demand(season_type, num_days=365), season_type)

#     # Compute adaptive action space if not provided
#     if max_order is None or action_step is None:
#         adapt_max, adapt_step = _compute_adaptive_params(dummy_data['demand'])
#         max_order = max_order or adapt_max
#         action_step = action_step or adapt_step
#         print(f"[Adaptive Config] avg_demand={dummy_data['demand'].mean():.1f} | max_order={max_order} | action_step={action_step}")

#     dummy_env = InventoryEnvironment(dummy_data, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
#                                       holding_cost=holding_cost, stockout_penalty=stockout_penalty)
    
#     # DYNAMIC STATE SIZE DETECTION
#     state_size = len(dummy_env.reset())
    
#     agent = DQNAgent(state_size=state_size, action_size=dummy_env.action_size, total_episodes=episodes, decay_type=decay_type)
#     rewards = []
#     best_eval_reward = -np.inf
    
#     # Fixed validation demand for evaluation-based checkpointing
#     # (different seed from eval set so we're not overfitting to the test)
#     if custom_df is not None:
#         val_df = custom_df.copy()
#     else:
#         from demand import generate_demand, prepare_env_data
#         val_df = prepare_env_data(generate_demand(season_type, seed=777), season_type)
    
#     print(f"--- Training ({episodes} Episodes) | State Size: {state_size} | Actions: {dummy_env.action_size} | Decay: {decay_type} ---")
    
#     for ep in range(episodes):
#         if custom_df is not None:
#             df = custom_df.copy()
#         else:
#             from demand import generate_demand, prepare_env_data
#             df = prepare_env_data(generate_demand(season_type, seed=ep+1000), season_type)
        
#         env = InventoryEnvironment(df, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
#                                     holding_cost=holding_cost, stockout_penalty=stockout_penalty)
#         state = env.reset()
#         total_real_reward = 0
#         done = False
        
#         while not done:
#             action = agent.act(state)
#             next_state, r, done, _ = env.step(action)
            
#             if next_state is None:
#                 next_state = np.zeros(state_size)
            
#             agent.buffer.push(state, action, r, next_state, done)
#             agent.learn()
#             state = next_state
#             total_real_reward += r
            
#         agent.decay_epsilon(ep)
#         # Soft target updates happen inside agent.learn() every step
        
#         rewards.append(total_real_reward)
        
#         # Greedy evaluation every 10 episodes for honest checkpointing
#         # (training reward includes exploration noise — this doesn't)
#         if ep % 10 == 0 or ep == episodes - 1:
#             eval_reward = _greedy_eval(agent, val_df, max_order, action_step,
#                                        holding_cost=holding_cost, stockout_penalty=stockout_penalty)
#             if eval_reward > best_eval_reward:
#                 best_eval_reward = eval_reward
#                 agent.save_best()
        
#         if ep % 50 == 0:
#             avg_last_50 = np.mean(rewards[max(0, ep-49):ep+1])
#             print(f"Ep {ep:>4d} | Reward: {total_real_reward:>10,.0f} | "
#                   f"Avg50: {avg_last_50:>10,.0f} | EvalBest: {best_eval_reward:>10,.0f} | "
#                   f"Eps: {agent.epsilon:.3f}")

#         # Invoke per-episode callback (used by WebSocket broadcast)
#         # If callback returns False, stop training early.
#         if on_episode is not None:
#             avg_last_50 = float(np.mean(rewards[max(0, ep-49):ep+1]))
#             should_continue = on_episode({
#                 "episode": ep + 1,
#                 "total_episodes": episodes,
#                 "reward": float(total_real_reward),
#                 "best_reward": float(max(rewards)),
#                 "avg_reward_last_50": avg_last_50,
#                 "epsilon": float(agent.epsilon),
#                 "best_eval_reward": float(best_eval_reward),
#             })
#             if should_continue is False:
#                 print(f"--- Training stopped at episode {ep + 1} by caller ---")
#                 break
    
#     print(f"--- Training Complete | Best Eval: {best_eval_reward:,.0f} ---")
#     agent.load_best()  # Restore best policy for evaluation
#     print(f"  (Restored best model checkpoint for evaluation)")
#     return agent, rewards, max_order, action_step, holding_cost, stockout_penalty


# def evaluate_and_plot(agent, season_type, max_order=None, action_step=None, custom_df=None, output_dir=".",
#                       holding_cost=5, stockout_penalty=200):
#     if custom_df is not None:
#         data_eval = custom_df.copy()
#     else:
#         from demand import generate_demand, prepare_env_data
#         data_eval = prepare_env_data(generate_demand(season_type, seed=999), season_type)
    
#     # Use same adaptive params
#     if max_order is None or action_step is None:
#         adapt_max, adapt_step = _compute_adaptive_params(data_eval['demand'])
#         max_order = max_order or adapt_max
#         action_step = action_step or adapt_step
    
#     env = InventoryEnvironment(data_eval, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
#                                holding_cost=holding_cost, stockout_penalty=stockout_penalty)
#     state = env.reset()
#     rl_logs = []
#     done = False

#     # Greedy evaluation — no random actions
#     saved_epsilon = agent.epsilon
#     agent.epsilon = 0.0
    
#     while not done:
#         action = agent.act(state)
#         next_state, r, done, info = env.step(action)
#         rl_logs.append({**info, "reward": r})
#         state = next_state
    
#     agent.epsilon = saved_epsilon  # Restore epsilon after evaluation
    
#     rl_df = pd.DataFrame(rl_logs)
#     rl_reward = rl_df['reward'].sum()
    
#     # Run Baselines with same adaptive params
#     oracle_reward, oracle_df = run_perfect_human_oracle_fixed(
#         data_eval, window_size=5, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
#         holding_cost=holding_cost, stockout_penalty=stockout_penalty
#     )
#     rule_reward, rule_df = run_rule_baseline(
#         data_eval, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
#         holding_cost=holding_cost, stockout_penalty=stockout_penalty
#     )
    
#     print(f"\nResults ({season_type}) [max_order={max_order}, step={action_step}]:")
#     print(f"  RL Agent : {rl_reward:>12,.0f}")
#     print(f"  Oracle   : {oracle_reward:>12,.0f}")
#     print(f"  Rule     : {rule_reward:>12,.0f}")
    
#     # Relative performance
#     if oracle_reward != 0:
#         rl_vs_oracle = (rl_reward / oracle_reward) * 100
#         print(f"  RL/Oracle: {rl_vs_oracle:.1f}%")
    
#     import os
#     plot_comparison(rl_df, oracle_df, rule_df, f"Evaluation: {season_type.upper()}",
#                    os.path.join(output_dir, f"{season_type}_results.png"))
    
#     return rl_df, oracle_df, rule_df

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from environment import InventoryEnvironment
from dqn import DQNAgent

# Helper to plot comparisons
def plot_comparison(rl_df, oracle_df, rule_df, title, filename):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(15, 10))
    min_len = min(len(rl_df), len(oracle_df), len(rule_df))
    dates = rl_df['date'].iloc[:min_len]

    # Inventory
    ax1.plot(dates, rl_df['inventory'].iloc[:min_len], 'b-', label='RL Inventory')
    ax1.plot(dates, oracle_df['inventory'].iloc[:min_len], 'g--', label='Oracle')
    ax1.fill_between(dates, rl_df['demand'].iloc[:min_len], alpha=0.3, color='gray', label='Demand')
    ax1.set_title(f"{title} - Inventory Level")
    ax1.legend()

    # Actions
    ax2.step(dates, rl_df['action_order_qty'].iloc[:min_len], 'b-', where='post', label='RL Order')
    ax2.step(dates, oracle_df['action_order_qty'].iloc[:min_len], 'g--', where='post', label='Oracle Order')
    ax2.fill_between(dates, rl_df['demand'].iloc[:min_len], alpha=0.3, color='gray', label='Demand')
    ax2.set_title(f"{title} - Order Quantity")
    ax2.legend()
    
    plt.tight_layout()
    plt.savefig(filename)
    print(f"Saved plot: {filename}")
    plt.close()


def _compute_adaptive_params(demand_series, max_order_override=None, action_step_override=None, lead_time=2):
    """
    Compute max_order_qty and action_step scaled to the demand magnitude.
    
    max_order must be large enough that the agent CAN meet demand:
      - At minimum: avg_demand * (lead_time + 1) so one order covers the gap
      - Also at least peak daily demand so spikes can be handled
    action_step ≈ max_order / 20  (~20 discrete actions)
    
    Returns (max_order_qty, action_step)
    """
    ACTION_SIZE = 20
    
    max_demand = int(demand_series.max())
    avg_demand = float(demand_series.mean())
    # Ensure the agent can order enough to cover lead-time worth of demand
    raw_max = max(int(max_demand), int(avg_demand * (lead_time + 1)))
    
    if action_step_override is not None:
        action_step = action_step_override
    else:
        action_step = max(1, int(raw_max / ACTION_SIZE))
    
    if max_order_override is not None:
        max_order = max_order_override
    else:
        max_order = raw_max
    
    return max_order, action_step


def run_perfect_human_oracle_fixed(env_data, window_size=5, max_order_qty=None, action_step=None, demand_scale=1.0,
                                    holding_cost=5, stockout_penalty=200):
    # Adaptive params
    scaled_demand = env_data['demand'] * demand_scale
    if max_order_qty is None or action_step is None:
        adapt_max, adapt_step = _compute_adaptive_params(scaled_demand)
        max_order_qty = max_order_qty or adapt_max
        action_step = action_step or adapt_step

    env = InventoryEnvironment(env_data, max_order_qty=max_order_qty, action_step=action_step, demand_scale=demand_scale,
                               holding_cost=holding_cost, stockout_penalty=stockout_penalty)
    demand_series = (env_data['demand'].values * demand_scale).astype(int)
    n = len(demand_series)
    
    state = env.reset()
    total_reward = 0
    logs = []
    
    while True:
        t = env.current_step
        if t >= n: break
        
        future_end = min(t + window_size, n)
        future_demand = demand_series[t:future_end].sum()
        pipeline = sum(env.order_pipeline)
        
        needed = max(0, future_demand - env.inv_onhand - pipeline)
        
        action_qty = min(max_order_qty, max(0, int(needed)))
        action_qty = round(action_qty / action_step) * action_step
        if action_qty > max_order_qty:
            action_qty = (max_order_qty // action_step) * action_step
        action_index = env.action_space.index(action_qty)
        
        _, reward, done, info = env.step(action_index)
        
        logs.append({**info, "reward": reward})
        total_reward += reward
        
        if done: break
        
    return total_reward, pd.DataFrame(logs)


def run_rule_baseline(env_data, max_order_qty=None, action_step=None, demand_scale=1.0,
                      holding_cost=5, stockout_penalty=200):
    scaled_demand = env_data['demand'] * demand_scale
    if max_order_qty is None or action_step is None:
        adapt_max, adapt_step = _compute_adaptive_params(scaled_demand)
        max_order_qty = max_order_qty or adapt_max
        action_step = action_step or adapt_step

    env = InventoryEnvironment(env_data, max_order_qty=max_order_qty, action_step=action_step, demand_scale=demand_scale,
                               holding_cost=holding_cost, stockout_penalty=stockout_penalty)
    avg_d = scaled_demand.mean()
    std_d = scaled_demand.std()
    
    reorder_point = int(avg_d * 3)
    target_stock = int(reorder_point + avg_d + 1.5 * std_d)
    
    state = env.reset()
    total_reward = 0
    logs = []
    
    while True:
        total_stock = env.inv_onhand + sum(env.order_pipeline)
        if total_stock < reorder_point:
            needed = target_stock - total_stock
            action_qty = min(max_order_qty, max(0, int(needed)))
        else:
            action_qty = 0
            
        action_qty = round(action_qty / action_step) * action_step
        if action_qty > max_order_qty:
            action_qty = (max_order_qty // action_step) * action_step
        action_index = env.action_space.index(action_qty)
        
        _, reward, done, info = env.step(action_index)
        
        logs.append({**info, "reward": reward})
        total_reward += reward
        if done: break
        
    return total_reward, pd.DataFrame(logs)


def _greedy_eval(agent, eval_df, max_order, action_step, holding_cost=5, stockout_penalty=200, _env=None):
    """Run one greedy episode (epsilon=0) on fixed data. Returns total reward."""
    if _env is None:
        _env = InventoryEnvironment(eval_df, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
                                   holding_cost=holding_cost, stockout_penalty=stockout_penalty)
    state = _env.reset()
    total = 0
    saved_eps = agent.epsilon
    agent.epsilon = 0.0
    done = False
    while not done:
        action = agent.act(state)
        next_state, r, done, _ = _env.step(action)
        total += r
        state = next_state
    agent.epsilon = saved_eps
    return total


def train_agent(season_type, episodes=500, max_order=None, action_step=None, custom_df=None, decay_type="exponential",
                holding_cost=5, stockout_penalty=200, gamma=0.98, learning_rate=1e-4, on_episode=None):
    """
    Train the RL agent with demand-adaptive action space.
    
    If max_order / action_step are None, they are automatically computed
    from the demand data so the agent's action space matches the demand scale.
    """
    # --- Prepare data & compute adaptive params ---
    if custom_df is not None:
        dummy_data = custom_df.copy()
    else:
        from demand import generate_demand, prepare_env_data
        dummy_data = prepare_env_data(generate_demand(season_type, num_days=365), season_type)

    # Compute adaptive action space if not provided
    if max_order is None or action_step is None:
        adapt_max, adapt_step = _compute_adaptive_params(dummy_data['demand'])
        max_order = max_order or adapt_max
        action_step = action_step or adapt_step
        print(f"[Adaptive Config] avg_demand={dummy_data['demand'].mean():.1f} | max_order={max_order} | action_step={action_step}")

    dummy_env = InventoryEnvironment(dummy_data, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
                                      holding_cost=holding_cost, stockout_penalty=stockout_penalty)
    
    # DYNAMIC STATE SIZE DETECTION
    state_size = len(dummy_env.reset())
    
    agent = DQNAgent(state_size=state_size, action_size=dummy_env.action_size, total_episodes=episodes, decay_type=decay_type, gamma=gamma, learning_rate=learning_rate)
    rewards = []
    best_eval_reward = -np.inf
    
    # Fixed validation demand for evaluation-based checkpointing
    # (different seed from eval set so we're not overfitting to the test)
    if custom_df is not None:
        val_df = custom_df
    else:
        from demand import generate_demand, prepare_env_data
        val_df = prepare_env_data(generate_demand(season_type, seed=777), season_type)
    
    # Pre-build reusable environments to avoid re-allocation every episode
    eval_env = InventoryEnvironment(val_df, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
                                    holding_cost=holding_cost, stockout_penalty=stockout_penalty)
    if custom_df is not None:
        # For custom data, reuse a single env (data never changes)
        train_env = dummy_env
    else:
        train_env = None  # rebuilt per episode for generated demand
    
    print(f"--- Training ({episodes} Episodes) | State Size: {state_size} | Actions: {dummy_env.action_size} | Decay: {decay_type} ---")
    
    for ep in range(episodes):
        if train_env is not None:
            env = train_env
        else:
            from demand import generate_demand, prepare_env_data
            df = prepare_env_data(generate_demand(season_type, seed=ep+1000), season_type)
            env = InventoryEnvironment(df, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
                                        holding_cost=holding_cost, stockout_penalty=stockout_penalty)
        state = env.reset()
        total_real_reward = 0
        done = False
        
        while not done:
            action = agent.act(state)
            next_state, r, done, _ = env.step(action)
            
            if next_state is None:
                next_state = np.zeros(state_size)
            
            agent.buffer.push(state, action, r, next_state, done)
            agent.learn()
            state = next_state
            total_real_reward += r
            
        agent.decay_epsilon(ep)
        # Soft target updates happen inside agent.learn() every step
        
        rewards.append(total_real_reward)
        
        # Greedy evaluation every 100 episodes for honest checkpointing
        # (training reward includes exploration noise — this doesn't)
        if ep % 100 == 0 or ep == episodes - 1:
            eval_reward = _greedy_eval(agent, val_df, max_order, action_step,
                                       holding_cost=holding_cost, stockout_penalty=stockout_penalty,
                                       _env=eval_env)
            if eval_reward > best_eval_reward:
                best_eval_reward = eval_reward
                agent.save_best()
        
        if ep % 50 == 0:
            avg_last_50 = np.mean(rewards[max(0, ep-49):ep+1])
            print(f"Ep {ep:>4d} | Reward: {total_real_reward:>10,.0f} | "
                  f"Avg50: {avg_last_50:>10,.0f} | EvalBest: {best_eval_reward:>10,.0f} | "
                  f"Eps: {agent.epsilon:.3f}")

        # Invoke per-episode callback (used by WebSocket broadcast)
        # If callback returns False, stop training early.
        if on_episode is not None:
            avg_last_50 = float(np.mean(rewards[max(0, ep-49):ep+1]))
            should_continue = on_episode({
                "episode": ep + 1,
                "total_episodes": episodes,
                "reward": float(total_real_reward),
                "best_reward": float(max(rewards)),
                "avg_reward_last_50": avg_last_50,
                "epsilon": float(agent.epsilon),
                "best_eval_reward": float(best_eval_reward),
            })
            if should_continue is False:
                print(f"--- Training stopped at episode {ep + 1} by caller ---")
                break
    
    print(f"--- Training Complete | Best Eval: {best_eval_reward:,.0f} ---")
    agent.load_best()  # Restore best policy for evaluation
    print(f"  (Restored best model checkpoint for evaluation)")
    return agent, rewards, max_order, action_step, holding_cost, stockout_penalty


def evaluate_and_plot(agent, season_type, max_order=None, action_step=None, custom_df=None, output_dir=".",
                      holding_cost=5, stockout_penalty=200):
    if custom_df is not None:
        data_eval = custom_df.copy()
    else:
        from demand import generate_demand, prepare_env_data
        data_eval = prepare_env_data(generate_demand(season_type, seed=999), season_type)
    
    # Use same adaptive params
    if max_order is None or action_step is None:
        adapt_max, adapt_step = _compute_adaptive_params(data_eval['demand'])
        max_order = max_order or adapt_max
        action_step = action_step or adapt_step
    
    env = InventoryEnvironment(data_eval, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
                               holding_cost=holding_cost, stockout_penalty=stockout_penalty)
    state = env.reset()
    rl_logs = []
    done = False

    # Greedy evaluation — no random actions
    saved_epsilon = agent.epsilon
    agent.epsilon = 0.0
    
    while not done:
        action = agent.act(state)
        next_state, r, done, info = env.step(action)
        rl_logs.append({**info, "reward": r})
        state = next_state
    
    agent.epsilon = saved_epsilon  # Restore epsilon after evaluation
    
    rl_df = pd.DataFrame(rl_logs)
    rl_reward = rl_df['reward'].sum()
    
    # Run Baselines with same adaptive params
    oracle_reward, oracle_df = run_perfect_human_oracle_fixed(
        data_eval, window_size=5, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
        holding_cost=holding_cost, stockout_penalty=stockout_penalty
    )
    rule_reward, rule_df = run_rule_baseline(
        data_eval, max_order_qty=max_order, action_step=action_step, demand_scale=1.0,
        holding_cost=holding_cost, stockout_penalty=stockout_penalty
    )
    
    print(f"\nResults ({season_type}) [max_order={max_order}, step={action_step}]:")
    print(f"  RL Agent : {rl_reward:>12,.0f}")
    print(f"  Oracle   : {oracle_reward:>12,.0f}")
    print(f"  Rule     : {rule_reward:>12,.0f}")
    
    # Relative performance
    if oracle_reward != 0:
        rl_vs_oracle = (rl_reward / oracle_reward) * 100
        print(f"  RL/Oracle: {rl_vs_oracle:.1f}%")
    
    import os
    plot_comparison(rl_df, oracle_df, rule_df, f"Evaluation: {season_type.upper()}",
                   os.path.join(output_dir, f"{season_type}_results.png"))
    
    return rl_df, oracle_df, rule_df


# ==========================================
# MULTI-SKU PARALLEL TRAINING
# ==========================================

def train_and_evaluate_single_sku(sku_name, env_df, episodes=500, decay_type="exponential",
                                   holding_cost=5, stockout_penalty=200, gamma=0.98, learning_rate=1e-4, output_dir=".",
                                   on_episode=None):
    """
    Full train + evaluate pipeline for a single SKU.
    Returns a dict with all results for this SKU.
    """
    import os
    sku_dir = os.path.join(output_dir, sku_name)
    os.makedirs(sku_dir, exist_ok=True)

    print(f"\n{'='*60}")
    print(f"  [{sku_name}] Starting training ({episodes} episodes)")
    print(f"{'='*60}")

    # Wrap the on_episode callback to tag with SKU name
    def _sku_on_episode(info):
        if on_episode is not None:
            info_with_sku = {**info, "sku": sku_name}
            return on_episode(info_with_sku)
        return True

    agent, rewards, used_max_order, used_action_step, used_h, used_s = train_agent(
        season_type="custom",
        episodes=episodes,
        custom_df=env_df,
        decay_type=decay_type,
        holding_cost=holding_cost,
        stockout_penalty=stockout_penalty,
        gamma=gamma,
        learning_rate=learning_rate,
        on_episode=_sku_on_episode,
    )

    print(f"  [{sku_name}] Training complete. Best reward: {max(rewards):,.0f}")

    # Evaluate
    rl_df, oracle_df, rule_df = evaluate_and_plot(
        agent, "custom",
        max_order=used_max_order,
        action_step=used_action_step,
        custom_df=env_df,
        output_dir=sku_dir,
        holding_cost=used_h,
        stockout_penalty=used_s,
    )

    rl_reward = float(rl_df["reward"].sum())
    oracle_reward = float(oracle_df["reward"].sum())
    rule_reward = float(rule_df["reward"].sum())
    rl_vs_oracle = (rl_reward / oracle_reward * 100) if oracle_reward != 0 else None

    return {
        "sku": sku_name,
        "agent": agent,
        "rewards": rewards,
        "max_order": used_max_order,
        "action_step": used_action_step,
        "holding_cost": used_h,
        "stockout_penalty": used_s,
        "rl_df": rl_df,
        "oracle_df": oracle_df,
        "rule_df": rule_df,
        "rl_reward": rl_reward,
        "oracle_reward": oracle_reward,
        "rule_reward": rule_reward,
        "rl_vs_oracle_pct": rl_vs_oracle,
        "output_dir": sku_dir,
    }


def train_all_skus_parallel(sku_data_dict, episodes=500, decay_type="exponential",
                             holding_cost=5, stockout_penalty=200, gamma=0.98, learning_rate=1e-4, output_dir=".",
                             max_workers=None, on_episode=None):
    """
    Train and evaluate all SKUs in parallel using ThreadPoolExecutor.

    Parameters
    ----------
    sku_data_dict : dict
        {sku_name: DataFrame} — each DataFrame is the processed env data for that SKU.
    episodes : int
        Number of training episodes per SKU.
    max_workers : int or None
        Max parallel threads. Defaults to number of SKUs.
    on_episode : callable or None
        Per-episode callback. Receives dict with extra "sku" key.

    Returns
    -------
    dict : {sku_name: result_dict} — results for each SKU.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import os

    os.makedirs(output_dir, exist_ok=True)
    num_skus = len(sku_data_dict)
    if max_workers is None:
        max_workers = num_skus

    print(f"\n{'#'*60}")
    print(f"  MULTI-SKU PARALLEL TRAINING")
    print(f"  SKUs: {list(sku_data_dict.keys())}  |  Workers: {max_workers}")
    print(f"  Episodes: {episodes}  |  Decay: {decay_type}")
    print(f"{'#'*60}")

    results = {}
    futures = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        for sku_name, env_df in sku_data_dict.items():
            future = executor.submit(
                train_and_evaluate_single_sku,
                sku_name=sku_name,
                env_df=env_df,
                episodes=episodes,
                decay_type=decay_type,
                holding_cost=holding_cost,
                stockout_penalty=stockout_penalty,
                gamma=gamma,
                learning_rate=learning_rate,
                output_dir=output_dir,
                on_episode=on_episode,
            )
            futures[future] = sku_name

        for future in as_completed(futures):
            sku_name = futures[future]
            try:
                result = future.result()
                results[sku_name] = result
                print(f"\n  [DONE] {sku_name}: RL={result['rl_reward']:,.0f} | "
                      f"Oracle={result['oracle_reward']:,.0f} | "
                      f"RL/Oracle={result['rl_vs_oracle_pct']:.1f}%")
            except Exception as e:
                print(f"\n  [FAIL] {sku_name}: {e}")
                results[sku_name] = {"sku": sku_name, "error": str(e)}

    # Print summary
    print(f"\n{'#'*60}")
    print(f"  MULTI-SKU TRAINING SUMMARY")
    print(f"{'#'*60}")
    print(f"  {'SKU':<15} {'RL Reward':>12} {'Oracle':>12} {'Rule':>12} {'RL/Oracle':>10}")
    print(f"  {'-'*61}")
    for sku_name in sorted(results.keys()):
        r = results[sku_name]
        if "error" in r:
            print(f"  {sku_name:<15} {'FAILED':>12}")
        else:
            print(f"  {r['sku']:<15} {r['rl_reward']:>12,.0f} {r['oracle_reward']:>12,.0f} "
                  f"{r['rule_reward']:>12,.0f} {r['rl_vs_oracle_pct']:>9.1f}%")

    return results