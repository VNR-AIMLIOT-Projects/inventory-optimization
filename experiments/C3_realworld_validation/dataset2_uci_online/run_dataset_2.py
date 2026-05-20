import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torch
import json
from pathlib import Path

HERE = Path(__file__).parent
BACKEND_SRC = HERE.parent.parent.parent / "Backend-RL" / "src"
sys.path.insert(0, str(BACKEND_SRC))

from environment import InventoryEnvironment
from dqn import DQNAgent
import extracts_demand

PLOTS_DIR = HERE / "plots"

print("Loading Dataset 2 (UCI Online Retail)...")
df = pd.read_csv(HERE / "data/online_retail.csv")

# Preprocess to get daily demand for top 4 SKUs
top_skus = df['StockCode'].value_counts().nlargest(4).index.tolist()
print(f"Selected Top 4 SKUs: {top_skus}")

episodes = 500
results = []

for sku in top_skus:
    print(f"\n======================================")
    print(f" Processing SKU: {sku}")
    print(f"======================================")
    
    sku_df = df[df['StockCode'] == sku].copy()
    sku_df['Date'] = pd.to_datetime(sku_df['InvoiceDate']).dt.date
    sku_df = sku_df.groupby('Date')['Quantity'].sum().reset_index()
    sku_df.rename(columns={'Quantity': 'Demand'}, inplace=True)
    sku_df['sku'] = sku
    
    # Reindex to fill missing days with 0
    sku_df['Date'] = pd.to_datetime(sku_df['Date'])
    full_idx = pd.date_range(start=sku_df['Date'].min(), end=sku_df['Date'].max(), freq='D')
    sku_df = sku_df.set_index('Date').reindex(full_idx, fill_value=0).reset_index()
    sku_df.rename(columns={'index': 'Date'}, inplace=True)
    sku_df['sku'] = sku
    
    # Handle negative quantities (returns)
    sku_df['Demand'] = sku_df['Demand'].clip(lower=0)
    
    temp_csv = HERE / f"data/temp_sku2_{sku}.csv"
    sku_df[['Date', 'sku', 'Demand']].to_csv(temp_csv, index=False)
    
    print(f"Extracting demand parameters for {sku}...")
    processed_df = extracts_demand.load_and_process_data(str(temp_csv), target_sku=None)
    processed_df.rename(columns={"Demand": "demand", "Date": "date"}, inplace=True)
    if 'day_of_week' not in processed_df.columns:
        processed_df['day_of_week'] = pd.to_datetime(processed_df['date']).dt.dayofweek
        
    env = InventoryEnvironment(processed_df)
    state_size = len(env.reset())
    action_size = env.action_size
    agent = DQNAgent(state_size, action_size, total_episodes=episodes)
    
    print(f"Training DQN for {episodes} episodes...")
    rewards = []
    for ep in range(episodes):
        state = env.reset()
        ep_r = 0.0
        done = False
        zeros = np.zeros(state_size, dtype=np.float32)
        while not done:
            action = agent.act(state)
            ns, r, done, info = env.step(action)
            ns2 = ns if ns is not None else zeros
            agent.buffer.push(state, action, r, ns2, float(done))
            agent.learn()
            state = ns2
            ep_r += r
        agent.decay_epsilon(ep)
        rewards.append(ep_r)
        
        if ep % 100 == 0 or ep == episodes - 1:
            ev_env = InventoryEnvironment(processed_df)
            ev_state = ev_env.reset()
            ev_done = False
            ev_r = 0.0
            while not ev_done:
                ev_action = agent.act(ev_state)
                ev_ns, r_, ev_done, info = ev_env.step(ev_action)
                ev_state = ev_ns
                ev_r += r_
            print(f"[DQN {sku}] Ep {ep} | Eval Reward: {ev_r:.0f}")

    # Oracle Baseline
    oracle_env = InventoryEnvironment(processed_df)
    mean_demand = processed_df['demand'].mean()
    oracle_state = oracle_env.reset()
    oracle_done = False
    oracle_r = 0
    oracle_log = []
    
    def get_nearest_action(target_qty, space):
        return min(range(len(space)), key=lambda i: abs(space[i] - target_qty))
        
    oracle_action_idx = get_nearest_action(mean_demand, oracle_env.action_space)
    while not oracle_done:
        oracle_ns, r_, oracle_done, info = oracle_env.step(oracle_action_idx)
        oracle_r += r_
        oracle_log.append(info)
        
    # Final DQN Eval
    ev_env = InventoryEnvironment(processed_df)
    ev_state = ev_env.reset()
    ev_done = False
    dqn_r = 0.0
    dqn_log = []
    while not ev_done:
        state_t = torch.from_numpy(np.asarray(ev_state, dtype=np.float32)).unsqueeze(0).to(agent.policy_net.net[0].weight.device)
        with torch.inference_mode():
            ev_action = torch.argmax(agent.policy_net(state_t)).item()
        ev_ns, r_, ev_done, info = ev_env.step(ev_action)
        ev_state = ev_ns
        dqn_r += r_
        dqn_log.append(info)
        
    dqn_sl = sum([d['units_sold'] for d in dqn_log]) / sum([d['demand'] for d in dqn_log]) if sum([d['demand'] for d in dqn_log]) > 0 else 1.0
    oracle_sl = sum([d['units_sold'] for d in oracle_log]) / sum([d['demand'] for d in oracle_log]) if sum([d['demand'] for d in oracle_log]) > 0 else 1.0
    
    results.append({
        'sku': sku,
        'dqn_sl': dqn_sl, 'oracle_sl': oracle_sl,
        'dqn_r': dqn_r, 'oracle_r': oracle_r
    })

# Plot Multi-SKU Metrics
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
x = np.arange(len(top_skus))
width = 0.35

# Convert SKUs to string in case they are numbers
sku_labels = [str(sku) for sku in top_skus]

dqn_sls = [res['dqn_sl'] for res in results]
oracle_sls = [res['oracle_sl'] for res in results]
dqn_rs = [res['dqn_r'] for res in results]
oracle_rs = [res['oracle_r'] for res in results]

axes[0].bar(x - width/2, dqn_sls, width, label='DQN', color='steelblue')
axes[0].bar(x + width/2, oracle_sls, width, label='Oracle', color='firebrick')
axes[0].set_xticks(x)
axes[0].set_xticklabels(sku_labels)
axes[0].set_title('Service Level across SKUs')
axes[0].legend()
axes[0].set_ylim(0, 1.1)

axes[1].bar(x - width/2, dqn_rs, width, label='DQN', color='steelblue')
axes[1].bar(x + width/2, oracle_rs, width, label='Oracle', color='firebrick')
axes[1].set_xticks(x)
axes[1].set_xticklabels(sku_labels)
axes[1].set_title('Total Reward across SKUs')
axes[1].legend()

plt.tight_layout()
plt.savefig(PLOTS_DIR / "replenix_dataset2_multisku_metrics.png", dpi=150)
plt.close()

with open(HERE / "results/dataset2_multisku_results.json", "w") as f:
    json.dump(results, f, indent=2)

print("\nAll SKUs processed! Results saved.")
