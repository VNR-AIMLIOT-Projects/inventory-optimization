import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torch
import json
import argparse
from pathlib import Path
import time

HERE = Path(__file__).parent
# Assuming the script is in experiments/realworld_replenix_live
BACKEND_SRC = HERE / "Backend_src"
sys.path.insert(0, str(BACKEND_SRC))

try:
    from environment import InventoryEnvironment
    from dqn import DQNAgent
    import extracts_demand
except ImportError as e:
    print(f"Error importing Replenix modules: {e}")
    print("Make sure you have the Backend-RL modules accessible.")
    sys.exit(1)

def run_live_training(dataset_num=1, episodes=500):
    print("=" * 60)
    print(f"  REPLENIX MULTI-SKU LIVE TRAINING - DATASET {dataset_num}")
    print("=" * 60)
    
    data_dir = HERE / "data"
    
    if dataset_num == 1:
        file_path = data_dir / "retail_store_inventory.csv"
        print(f"Loading Dataset 1 (Retail Store): {file_path}")
        raw_df = pd.read_csv(file_path)
        raw_df['Date'] = pd.to_datetime(raw_df['Date'])
        raw_df.rename(columns={"Units Sold": "Demand", "Product ID": "sku"}, inplace=True)
        # Select 2 top SKUs for live demo to save time
        top_skus = raw_df.groupby('sku')['Demand'].sum().nlargest(2).index.tolist()
    else:
        file_path = data_dir / "online_retail.csv"
        print(f"Loading Dataset 2 (UCI Online): {file_path}")
        raw_df = pd.read_csv(file_path)
        top_skus = raw_df['StockCode'].value_counts().nlargest(2).index.tolist()

    print(f"Selected Top 2 SKUs for live training: {top_skus}")
    
    for sku in top_skus:
        print("\n" + "*" * 50)
        print(f"*** STARTING LIVE TRAINING FOR SKU: {sku} ***")
        print("*" * 50)
        
        if dataset_num == 1:
            sku_df = raw_df[raw_df['sku'] == sku].copy()
            sku_df = sku_df.groupby('Date')['Demand'].sum().reset_index()
        else:
            sku_df = raw_df[raw_df['StockCode'] == sku].copy()
            sku_df['Date'] = pd.to_datetime(sku_df['InvoiceDate']).dt.date
            sku_df = sku_df.groupby('Date')['Quantity'].sum().reset_index()
            sku_df.rename(columns={'Quantity': 'Demand'}, inplace=True)
            sku_df['Demand'] = sku_df['Demand'].clip(lower=0)

        sku_df['sku'] = sku
        sku_df['Date'] = pd.to_datetime(sku_df['Date'])
        full_idx = pd.date_range(start=sku_df['Date'].min(), end=sku_df['Date'].max(), freq='D')
        sku_df = sku_df.set_index('Date').reindex(full_idx, fill_value=0).reset_index()
        sku_df.rename(columns={'index': 'Date'}, inplace=True)
        sku_df['sku'] = sku
        
        temp_csv = data_dir / f"temp_live_sku_{sku}.csv"
        sku_df[['Date', 'sku', 'Demand']].to_csv(temp_csv, index=False)
        
        print(f"-> Extracting demand parameters for {sku}...")
        processed_df = extracts_demand.load_and_process_data(str(temp_csv), target_sku=None)
        processed_df.rename(columns={"Demand": "demand", "Date": "date"}, inplace=True)
        if 'day_of_week' not in processed_df.columns:
            processed_df['day_of_week'] = pd.to_datetime(processed_df['date']).dt.dayofweek
            
        env = InventoryEnvironment(processed_df)
        state_size = len(env.reset())
        action_size = env.action_size
        agent = DQNAgent(state_size, action_size, total_episodes=episodes)
        
        print(f"-> Environment Ready. State Size: {state_size}, Action Space: {action_size}")
        print(f"-> Beginning RL Training loop ({episodes} episodes)...")
        print("-" * 60)
        print(f"{'Episode':<10} | {'Total Reward':<15} | {'Epsilon':<10} | {'Status'}")
        print("-" * 60)
        
        start_time = time.time()
        
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
            
            # Live logging every 50 episodes
            if (ep + 1) % 50 == 0 or ep == 0:
                print(f"Ep {ep+1:<7} | {ep_r:<15.0f} | {agent.epsilon:<10.3f} | Training...")
                
        elapsed = time.time() - start_time
        print("-" * 60)
        print(f"-> Training Completed in {elapsed:.1f} seconds!")
        
        # Final Evaluation
        print("-> Running Final Evaluation (Greedy Policy)...")
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
        print(f"-> Final Evaluation Result:")
        print(f"   Service Level: {dqn_sl * 100:.2f}%")
        print(f"   Total Reward:  {dqn_r:.0f}")
        print("\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=int, default=1, choices=[1, 2], help="Dataset 1 (Retail) or 2 (UCI Wholesale)")
    parser.add_argument("--episodes", type=int, default=500, help="Number of training episodes")
    args = parser.parse_args()
    
    run_live_training(dataset_num=args.dataset, episodes=args.episodes)
