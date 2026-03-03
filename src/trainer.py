import numpy as np
import pandas as pd
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


def _compute_adaptive_params(demand_series, max_order_override=None, action_step_override=None):
    """
    Compute max_order_qty and action_step scaled to the demand magnitude.
    
    Rules:
      - max_order = 5x average daily demand (rounded up to nearest action_step)
      - action_step = ~1/20th of max_order (min 1, rounded to a clean number)
    
    Returns (max_order_qty, action_step)
    """
    avg_demand = demand_series.mean()
    std_demand = demand_series.std()
    
    # Max order: enough to cover ~5 days of above-average demand
    raw_max = max(int((avg_demand + 2 * std_demand) * 5), int(avg_demand * 5))
    
    if action_step_override is not None:
        action_step = action_step_override
    else:
        # Pick a clean action_step that gives ~40 discrete actions
        action_step = max(1, int(round(raw_max / 40)))
        # Round action_step to a "clean" number
        if action_step >= 100:
            action_step = round(action_step / 50) * 50
        elif action_step >= 10:
            action_step = round(action_step / 10) * 10
        else:
            action_step = max(1, action_step)
    
    if max_order_override is not None:
        max_order = max_order_override
    else:
        max_order = int(np.ceil(raw_max / action_step)) * action_step
    
    return max_order, action_step


def run_perfect_human_oracle_fixed(env_data, window_size=5, max_order_qty=None, action_step=None, demand_scale=1.0):
    # Adaptive params
    scaled_demand = env_data['demand'] * demand_scale
    if max_order_qty is None or action_step is None:
        adapt_max, adapt_step = _compute_adaptive_params(scaled_demand)
        max_order_qty = max_order_qty or adapt_max
        action_step = action_step or adapt_step

    env = InventoryEnvironment(env_data, max_order_qty=max_order_qty, action_step=action_step, demand_scale=demand_scale)
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
        if action_qty > max_order_qty: action_qty = max_order_qty
        action_index = env.action_space.index(action_qty)
        
        _, reward, done, info = env.step(action_index)
        real_reward = reward / env.reward_scale_factor
        
        logs.append({**info, "reward": real_reward})
        total_reward += real_reward
        
        if done: break
        
    return total_reward, pd.DataFrame(logs)


def run_rule_baseline(env_data, max_order_qty=None, action_step=None, demand_scale=1.0):
    scaled_demand = env_data['demand'] * demand_scale
    if max_order_qty is None or action_step is None:
        adapt_max, adapt_step = _compute_adaptive_params(scaled_demand)
        max_order_qty = max_order_qty or adapt_max
        action_step = action_step or adapt_step

    env = InventoryEnvironment(env_data, max_order_qty=max_order_qty, action_step=action_step, demand_scale=demand_scale)
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
        if action_qty > max_order_qty: action_qty = max_order_qty
        action_index = env.action_space.index(action_qty)
        
        _, reward, done, info = env.step(action_index)
        real_reward = reward / env.reward_scale_factor
        
        logs.append({**info, "reward": real_reward})
        total_reward += real_reward
        if done: break
        
    return total_reward, pd.DataFrame(logs)


def train_agent(season_type, episodes=500, max_order=None, action_step=None, custom_df=None, decay_type="exponential"):
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

    dummy_env = InventoryEnvironment(dummy_data, max_order_qty=max_order, action_step=action_step, demand_scale=1.0)
    
    # DYNAMIC STATE SIZE DETECTION
    state_size = len(dummy_env.reset())
    
    agent = DQNAgent(state_size=state_size, action_size=dummy_env.action_size, total_episodes=episodes, decay_type=decay_type)
    rewards = []
    best_reward = -np.inf
    
    print(f"--- Training ({episodes} Episodes) | State Size: {state_size} | Actions: {dummy_env.action_size} | Decay: {decay_type} ---")
    
    for ep in range(episodes):
        if custom_df is not None:
            df = custom_df.copy()
        else:
            from demand import generate_demand, prepare_env_data
            df = prepare_env_data(generate_demand(season_type, seed=ep+1000), season_type)
        
        env = InventoryEnvironment(df, max_order_qty=max_order, action_step=action_step, demand_scale=1.0)
        state = env.reset()
        total_real_reward = 0
        done = False
        
        while not done:
            action = agent.act(state)
            next_state, scaled_r, done, _ = env.step(action)
            real_r = scaled_r / env.reward_scale_factor
            
            if next_state is None:
                next_state = np.zeros(state_size)
            
            agent.buffer.push(state, action, scaled_r, next_state, done)
            agent.learn()
            state = next_state
            total_real_reward += real_r
            
        agent.decay_epsilon(ep)
        if ep % agent.target_update_freq == 0:
            agent.update_target()
        
        rewards.append(total_real_reward)
        
        if total_real_reward > best_reward:
            best_reward = total_real_reward
        
        if ep % 50 == 0:
            avg_last_50 = np.mean(rewards[max(0, ep-49):ep+1])
            print(f"Ep {ep:>4d} | Reward: {total_real_reward:>10,.0f} | "
                  f"Avg50: {avg_last_50:>10,.0f} | Best: {best_reward:>10,.0f} | "
                  f"Eps: {agent.epsilon:.3f}")
    
    print(f"--- Training Complete | Final Best: {best_reward:,.0f} ---")
    return agent, rewards, max_order, action_step


def evaluate_and_plot(agent, season_type, max_order=None, action_step=None, custom_df=None, output_dir="."):
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
    
    env = InventoryEnvironment(data_eval, max_order_qty=max_order, action_step=action_step, demand_scale=1.0)
    state = env.reset()
    rl_logs = []
    done = False
    
    while not done:
        action = agent.act(state)
        next_state, r, done, info = env.step(action)
        real_r = r / env.reward_scale_factor
        rl_logs.append({**info, "reward": real_r})
        state = next_state
    
    rl_df = pd.DataFrame(rl_logs)
    rl_reward = rl_df['reward'].sum()
    
    # Run Baselines with same adaptive params
    oracle_reward, oracle_df = run_perfect_human_oracle_fixed(
        data_eval, window_size=5, max_order_qty=max_order, action_step=action_step, demand_scale=1.0
    )
    rule_reward, rule_df = run_rule_baseline(
        data_eval, max_order_qty=max_order, action_step=action_step, demand_scale=1.0
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