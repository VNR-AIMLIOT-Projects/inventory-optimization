import sys
import pandas as pd
import numpy as np
from pathlib import Path

HERE = Path(__file__).parent
BACKEND_SRC = HERE.parent / "experiments" / "realworld_replenix_live" / "Backend_src"
sys.path.insert(0, str(BACKEND_SRC))

from environment import InventoryEnvironment
import extracts_demand

class RobustInventoryEnvironment(InventoryEnvironment):
    def __init__(self, historical_data, **kwargs):
        super().__init__(historical_data, **kwargs)
        self.action_space = [0, 5, 10, 20, 50, 100, 200, 350, 500, 750, 1000, 1500, 2500, 4000, 6000]
        self.action_size = len(self.action_space)

def run_oracle(env, processed_df):
    oracle_state = env.reset()
    oracle_done = False
    oracle_r = 0
    oracle_log = []
    
    def get_nearest_action(target_qty, space):
        return min(range(len(space)), key=lambda i: abs(space[i] - target_qty))
        
    demands = processed_df['demand'].values
    n = len(demands)
    
    while not oracle_done:
        t = env.current_step
        target_t = t + env.lead_time
        future_demand = demands[target_t] if target_t < n else 0
        
        current_inv = env.inv_onhand
        pipeline_sum = sum(env.order_pipeline)
        expected_demand_before_target = sum(demands[t:target_t])
        
        expected_inv_at_target = current_inv + pipeline_sum - expected_demand_before_target
        ideal_order = max(0, future_demand - expected_inv_at_target)
        
        oracle_action_idx = get_nearest_action(ideal_order, env.action_space)
        ns, r, oracle_done, info = env.step(oracle_action_idx)
        oracle_r += r
        oracle_log.append(info)
        
    total_sold = sum([d['units_sold'] for d in oracle_log])
    total_demand = sum([d['demand'] for d in oracle_log])
    sl = total_sold / total_demand if total_demand > 0 else 1.0
    return sl, oracle_r

print("="*50)
print("TRUE LOOKAHEAD ORACLE EVALUATION")
print("="*50)

print("\n--- Dataset 1 (Retail Store) ---")
d1_skus = ['P0016', 'P0020']
for sku in d1_skus:
    temp_csv = HERE.parent / f"experiments/realworld_replenix_live/data/temp_d1_{sku}.csv"
    processed_df = extracts_demand.load_and_process_data(str(temp_csv), target_sku=None)
    processed_df.rename(columns={"Demand": "demand", "Date": "date"}, inplace=True)
    env = InventoryEnvironment(processed_df)
    sl, r = run_oracle(env, processed_df)
    print(f"SKU {sku} | True Oracle SL: {sl*100:.2f}% | True Oracle Reward: {r:.0f}")

print("\n--- Dataset 2 (UCI Robust) ---")
d2_skus = ['85123A', '22423']
for sku in d2_skus:
    temp_csv = HERE.parent / f"experiments/realworld_replenix_live/data/temp_d2_{sku}.csv"
    processed_df = extracts_demand.load_and_process_data(str(temp_csv), target_sku=None)
    processed_df.rename(columns={"Demand": "demand", "Date": "date"}, inplace=True)
    env_kwargs = {"holding_cost": 0.5, "stockout_penalty": 1000, "price": 500}
    env = RobustInventoryEnvironment(processed_df, **env_kwargs)
    sl, r = run_oracle(env, processed_df)
    print(f"SKU {sku} | True Oracle SL: {sl*100:.2f}% | True Oracle Reward: {r:.0f}")
