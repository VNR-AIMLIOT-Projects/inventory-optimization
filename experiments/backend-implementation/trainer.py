import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from environment import InventoryEnvironment
from dqn import DQNAgent

# CHANGED: window_size reduced from 9 to 5 for leaner inventory
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
        
        # Lookahead window (Now only 5 days)
        future_end = min(t + window_size, n)
        future_demand = demand_series[t:future_end].sum()
        pipeline = sum(env.order_pipeline)
        
        needed = max(0, future_demand - env.inv_onhand - pipeline)
        
        # Cap at max_order_qty
        action_qty = min(max_order_qty, max(0, int(needed)))
        action_qty = round(action_qty / action_step) * action_step
        
        # Ensure valid action index
        if action_qty > max_order_qty: action_qty = max_order_qty
        action_index = env.action_space.index(action_qty)
        
        _, reward, done, info = env.step(action_index)
        
        # Convert back to REAL reward
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
    
    # Standard Rule: Reorder Point = 3 days of avg demand
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
        
        # Convert back to REAL reward
        real_reward = reward / env.reward_scale_factor
        
        logs.append({**info, "reward": real_reward})
        total_reward += real_reward
        if done: break
        
    return total_reward, pd.DataFrame(logs)

def train_agent(season_type, episodes=300, max_order=2000):
    d_scale = 1.0 
    
    # Dummy env for dimensions
    from demand import prepare_env_data, generate_demand # Import here to avoid circular imports
    dummy_data = prepare_env_data(generate_demand(season_type, num_days=10), season_type)
    dummy_env = InventoryEnvironment(dummy_data, max_order_qty=max_order, demand_scale=d_scale)
    
    agent = DQNAgent(state_size=13, action_size=dummy_env.action_size)
    rewards = []
    
    print(f"--- Training on {season_type.upper()} Season (Scale={d_scale}) ---")
    
    for ep in range(episodes):
        df = generate_demand(season_type, seed=ep+1000) 
        env = InventoryEnvironment(prepare_env_data(df, season_type), max_order_qty=max_order, demand_scale=d_scale)
        
        state = env.reset()
        total_real_reward = 0
        done = False
        
        while not done:
            action = agent.act(state)
            next_state, scaled_r, done, _ = env.step(action)
            
            # Recover real reward for logging
            real_r = scaled_r / env.reward_scale_factor
            
            if next_state is None: next_state = np.zeros(13)
            
            agent.buffer.push(state, action, scaled_r, next_state, done)
            agent.learn()
            state = next_state
            
            total_real_reward += real_r
            
        agent.epsilon = max(agent.eps_min, agent.epsilon * agent.eps_decay)
        if ep % 10 == 0: agent.update_target()
        
        rewards.append(total_real_reward)
        if ep % 20 == 0:
            print(f"Ep {ep} | Reward: {total_real_reward:,.0f} | Eps: {agent.epsilon:.2f}")
            
    return agent, rewards

def evaluate_and_plot(agent, season_type, max_order=2000):
    d_scale = 1.0 
    from demand import prepare_env_data, generate_demand
    
    df_eval = generate_demand(season_type, seed=999)
    data_eval = prepare_env_data(df_eval, season_type)
    
    # Run Agent
    env = InventoryEnvironment(data_eval, max_order_qty=max_order, demand_scale=d_scale)
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
    
    # Run Baselines with updated window_size=5
    oracle_reward, oracle_df = run_perfect_human_oracle_fixed(data_eval, window_size=5, max_order_qty=max_order, action_step=50, demand_scale=d_scale)
    rule_reward, rule_df = run_rule_baseline(data_eval, max_order_qty=max_order, action_step=50, demand_scale=d_scale)
    
    print(f"\nResults ({season_type}):")
    print(f"RL: {rl_reward:,.0f}")
    print(f"Oracle: {oracle_reward:,.0f}")
    print(f"Rule: {rule_reward:,.0f}")
    
    # Plotting
    plot_comparison(rl_df, oracle_df, rule_df, f"Evaluation: {season_type.upper()} Season", f"{season_type}_results.png")

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

def plot_demand_data(df, season_type, filename):
    plt.figure(figsize=(15, 6))
    plt.plot(df['Date'], df['Demand'], 'b-', linewidth=2, label='Daily Demand')
    plt.fill_between(df['Date'], df['Demand'], alpha=0.3, color='blue')
    
    if season_type == 'winter':
        plt.axvspan(df['Date'].iloc[0], df['Date'].iloc[59], color='cyan', alpha=0.2, label='Winter Season')
        plt.axvspan(df['Date'].iloc[335], df['Date'].iloc[-1], color='cyan', alpha=0.2)
    else:
        plt.axvspan(df['Date'].iloc[59], df['Date'].iloc[148], color='orange', alpha=0.2, label='Summer Season')

    plt.title(f"{season_type.upper()} Demand Pattern", fontsize=14, fontweight='bold')
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Daily Demand', fontsize=12)
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename)
    print(f"✅ Saved demand plot to {filename}")
    plt.close()