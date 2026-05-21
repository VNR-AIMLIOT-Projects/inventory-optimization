import sys
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import torch
from pathlib import Path
import json
import time

HERE = Path(__file__).parent
SHARED = HERE.parent / "shared"
A1_DIR = HERE.parent / "A1_two_echelon_linear"
BACKEND = HERE.parent.parent / "Backend-RL" / "src"

sys.path.insert(0, str(SHARED))
sys.path.insert(0, str(A1_DIR))
sys.path.insert(0, str(BACKEND))

import extracts_demand  # pyrefly: ignore
from env_two_echelon import TwoEchelonEnv

RESULTS_DIR = HERE / "results"
PLOTS_DIR = HERE / "plots"
RESULTS_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)

# 1. Load Real-World Dataset
df = pd.read_csv(HERE / "data/retail_store_inventory.csv")
df['Date'] = pd.to_datetime(df['Date'])
df.rename(columns={"Units Sold": "Demand", "Product ID": "sku"}, inplace=True)

# 2. Select Top SKU
top_sku = df.groupby('sku')['Demand'].sum().idxmax()
print(f"Top SKU selected: {top_sku}")
sku_df = df[df['sku'] == top_sku].copy()

# Group by Date and sum Demand to handle multiple sales on same day
sku_df = sku_df.groupby('Date')['Demand'].sum().reset_index()
sku_df['sku'] = top_sku

# Sort and complete dates
full_idx = pd.date_range(start=sku_df['Date'].min(), end=sku_df['Date'].max(), freq='D')  # pyrefly: ignore
sku_df = sku_df.set_index('Date').reindex(full_idx, fill_value=0).reset_index()
sku_df.rename(columns={'index': 'Date'}, inplace=True)
sku_df['sku'] = top_sku  # fill missing sku values after reindex
sku_df.rename(columns={'index': 'Date'}, inplace=True)

# Save to temporary csv to feed into extracts_demand
temp_csv = HERE / "data/temp_sku_demand.csv"
sku_df[['Date', 'sku', 'Demand']].to_csv(temp_csv, index=False)

# 3. Validate Demand Parameter Extraction
print("\n--- Validating Extracts Demand ---")
processed_df = extracts_demand.load_and_process_data(str(temp_csv), target_sku=None)
extracts_demand.plot_demand_preview(processed_df, filename=str(PLOTS_DIR / "realworld_demand_preview.png"))
params = processed_df.attrs.get("detected_params", {})
print("Extracted Parameters:")
print(json.dumps(params, indent=2))

# 4. Check if Seasonality & Peak Demand is correctly extracted
if params.get('seasonal', {}).get('num_seasons', 0) > 0:
    print("[OK] Seasonality correctly detected in the real-world dataset.")
else:
    print("[WARNING] No strong seasonality detected. The dataset might be mostly stationary.")

# 5. Run RL Baseline (Quick evaluation with a random/heuristic baseline for now)
processed_df.rename(columns={"Demand": "demand", "Date": "date"}, inplace=True)
CONFIG = {
    "lead_time_W": 3, "lead_time_R": 1,
    "h_W": 2.0, "h_R": 5.0, "b_R": 500.0, "c_W": 2.0, "c_R": 2.0,
    "n_actions_W": 11, "n_actions_R": 11,
}
env = TwoEchelonEnv(processed_df, **CONFIG)
state = env.reset()
done = False
total_reward = 0
info_log = []

# Simple heuristic policy: Order mean demand at R, Order mean demand + safety at W
mean_demand = processed_df['demand'].mean()

while not done:
    # A simple baseline agent (Not RL, just Oracle-like heuristic)
    action_W = min(CONFIG['n_actions_W'] - 1, int(mean_demand / 10))
    action_R = min(CONFIG['n_actions_R'] - 1, int(mean_demand / 10))
    action_idx = action_W * CONFIG['n_actions_R'] + action_R
    
    state, r, done, info = env.step(action_idx)
    total_reward += r
    info_log.append(info)

svc = env.service_level(info_log)
bw = env.bullwhip_ratio()

print("\n--- Baseline Oracle/Heuristic Performance ---")
print(f"Total Reward (Cost): {total_reward}")
print(f"Service Level: {svc:.2%}")
print(f"Bullwhip Ratio: {bw:.2f}")

with open(RESULTS_DIR / "validation_results.json", "w") as f:
    json.dump({
        "sku": top_sku,
        "extracted_params": params,
        "baseline_service_level": svc,
        "baseline_bullwhip": bw,
        "baseline_reward": total_reward
    }, f, indent=2)

print("\nReal-World Validation Script Completed Successfully!")
