import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from environment import InventoryEnvironment
from dqn import DQNAgent
from demand import generate_demand, prepare_env_data


def run_perfect_human_oracle_fixed(env_data, window_size=9, max_order_qty=500, action_step=50, demand_scale=1.0):
   env = InventoryEnvironment(env_data, max_order_qty=max_order_qty, action_step=action_step, demand_scale=demand_scale)
   # FIX: Ensure demand series is integers for the calculation
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
      
       # The Oracle logic: Order exactly what is needed for the window
       # minus what we have on hand and what is already coming.
       needed = max(0, future_demand - env.inv_onhand - pipeline)
      
       # Cap at max_order_qty
       action_qty = min(max_order_qty, max(0, int(needed)))
      
       # Round to nearest step (e.g. 50, 100)
       action_qty = round(action_qty / action_step) * action_step
      
       # Safety check: Ensure valid index
       if action_qty > max_order_qty: action_qty = max_order_qty
       action_index = env.action_space.index(action_qty)
      
       _, reward, done, info = env.step(action_index)
      
       # FIX: The environment returns SCALED reward.
       # We must convert it back to REAL reward for fair comparison.
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
       action_index = env.action_space.index(action_qty)
      
       _, reward, done, info = env.step(action_index)
       logs.append({**info, "reward": reward})
       total_reward += reward
       if done: break
      
   return total_reward, pd.DataFrame(logs)


def train_agent(season_type, episodes=300, max_order=2000):
   # FIX: demand_scale is ALWAYS 1.0 because generate_demand() now produces large numbers for both.
   d_scale = 1.0
  
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
          
           # Recover real reward for display
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
   # FIX: demand_scale is 1.0 here too
   d_scale = 1.0
  
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
       # Scaled r comes out, convert to real
       real_r = r / env.reward_scale_factor
       rl_logs.append({**info, "reward": real_r})
       state = next_state
  
   rl_df = pd.DataFrame(rl_logs)
   rl_reward = rl_df['reward'].sum()
  
   # Run Baselines
   oracle_reward, oracle_df = run_perfect_human_oracle_fixed(data_eval, max_order_qty=max_order, action_step=50, demand_scale=d_scale)
   rule_reward, rule_df = run_rule_baseline(data_eval, max_order_qty=max_order, action_step=50, demand_scale=d_scale)
  
   print(f"\nResults ({season_type}):")
   print(f"RL: {rl_reward:,.0f}")
   print(f"Oracle: {oracle_reward:,.0f}")
   print(f"Rule: {rule_reward:,.0f}")
  
   # Plotting
   plt.figure(figsize=(12, 6))
   plt.plot(rl_df['date'], rl_df['inventory'], label='RL Inventory', color='blue')
   plt.plot(oracle_df['date'], oracle_df['inventory'], label='Oracle', color='green', linestyle='--')
   plt.fill_between(rl_df['date'], rl_df['demand'], color='gray', alpha=0.3, label='Demand')
   plt.title(f"Evaluation: {season_type.upper()} Season")
   plt.legend()
   plt.savefig(f"{season_type}_results.png")
   print(f"Saved plot to {season_type}_results.png")
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

