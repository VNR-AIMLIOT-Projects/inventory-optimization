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

def run_perfect_human_oracle_fixed(env_data, window_size=5, max_order_qty=2000, action_step=50, demand_scale=1.0):
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

def run_rule_baseline(env_data, max_order_qty, action_step, demand_scale=1.0):
    env = InventoryEnvironment(env_data, max_order_qty=max_order_qty, action_step=action_step, demand_scale=demand_scale)
    scaled_demand = env_data['demand'] * demand_scale
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

def train_agent(season_type, episodes=300, max_order=2000, custom_df=None):
    # Setup dummy env to get dimensions
    if custom_df is not None:
        dummy_data = custom_df.copy()
    else:
        # Fallback to synthetic
        from demand import generate_demand, prepare_env_data
        dummy_data = prepare_env_data(generate_demand(season_type, num_days=10), season_type)

    dummy_env = InventoryEnvironment(dummy_data, max_order_qty=max_order, demand_scale=1.0)
    
    # DYNAMIC STATE SIZE DETECTION
    # This ensures we handle 13 features (synthetic) or 14 features (custom with 'month') automatically
    state_size = len(dummy_env.reset())
    
    agent = DQNAgent(state_size=state_size, action_size=dummy_env.action_size)
    rewards = []
    
    print(f"--- Training ({episodes} Episodes) | State Size: {state_size} ---")
    
    for ep in range(episodes):
        if custom_df is not None:
            # Use User Data
            df = custom_df.copy()
        else:
            # Use Synthetic Data
            from demand import generate_demand, prepare_env_data
            df = prepare_env_data(generate_demand(season_type, seed=ep+1000), season_type)
        
        env = InventoryEnvironment(df, max_order_qty=max_order, demand_scale=1.0)
        state = env.reset()
        total_real_reward = 0
        done = False
        
        while not done:
            action = agent.act(state)
            next_state, scaled_r, done, _ = env.step(action)
            real_r = scaled_r / env.reward_scale_factor
            
            # Handle Next State None
            if next_state is None: next_state = np.zeros(state_size)
            
            agent.buffer.push(state, action, scaled_r, next_state, done)
            agent.learn()
            state = next_state
            total_real_reward += real_r
            
        agent.epsilon = max(agent.eps_min, agent.epsilon * agent.eps_decay)
        if ep % 10 == 0: agent.update_target()
        
        rewards.append(total_real_reward)
        if ep % 50 == 0:
            print(f"Ep {ep} | Reward: {total_real_reward:,.0f} | Eps: {agent.epsilon:.2f}")
            
    return agent, rewards

def evaluate_and_plot(agent, season_type, max_order=2000, custom_df=None):
    if custom_df is not None:
        data_eval = custom_df.copy()
    else:
        from demand import generate_demand, prepare_env_data
        data_eval = prepare_env_data(generate_demand(season_type, seed=999), season_type)
    
    env = InventoryEnvironment(data_eval, max_order_qty=max_order, demand_scale=1.0)
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
    
    # Run Baselines (window_size=5 for Lean Oracle)
    oracle_reward, oracle_df = run_perfect_human_oracle_fixed(data_eval, window_size=5, max_order_qty=max_order, action_step=50, demand_scale=1.0)
    rule_reward, rule_df = run_rule_baseline(data_eval, max_order_qty=max_order, action_step=50, demand_scale=1.0)
    
    print(f"\nResults ({season_type}):")
    print(f"RL: {rl_reward:,.0f}")
    print(f"Oracle: {oracle_reward:,.0f}")
    print(f"Rule: {rule_reward:,.0f}")
    
    # Plotting
    plot_comparison(rl_df, oracle_df, rule_df, f"Evaluation: {season_type.upper()}", f"{season_type}_results.png")