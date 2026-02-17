import sys
import pandas as pd
from extracts_demand import load_and_process_data, plot_demand_preview
from demand_modifier import DemandModifier
from trainer import train_agent, evaluate_and_plot

# ==========================================
# CONFIGURATION
# ==========================================
MODE = "CUSTOM" # Options: "CUSTOM", "SUMMER", "WINTER"
FILE_PATH = "Inventory Data Template.xlsx - Sample Data.csv" 
TARGET_SKU = "SKU_001" 

# Training Config
EPISODES = 500  # More episodes for custom data
MAX_ORDER = 2000

def interactive_scenario_builder(df):
    """
    Command Line Interface for modifying the demand data.
    """
    modifier = DemandModifier(df)
    
    while True:
        print("\n" + "="*50)
        print(f"  SCENARIO BUILDER: {TARGET_SKU}")
        print("="*50)
        print("1. [SPIKE]  Add a large order on a specific day")
        print("2. [SCALE]  Multiply demand for a season (e.g. +20%)")
        print("3. [RESET]  Revert to original data")
        print("4. [VIEW]   Generate preview graph")
        print("5. [TRAIN]   Lock in data & Start RL Training")
        print("0. [EXIT]   Quit")
        
        choice = input("\nEnter choice: ")
        
        if choice == '1':
            date = input("   Enter Date (YYYY-MM-DD): ")
            try:
                amt = int(input("   Enter Amount to Add: "))
                modifier.add_spike(date, amt)
            except ValueError:
                print("    Invalid amount.")
            
        elif choice == '2':
            start = input("   Start Date (YYYY-MM-DD): ")
            end = input("   End Date (YYYY-MM-DD): ")
            try:
                factor = float(input("   Multiplier (e.g. 1.2): "))
                modifier.scale_period(start, end, factor)
            except ValueError:
                print("    Invalid multiplier.")
            
        elif choice == '3':
            modifier.reset()
            
        elif choice == '4':
            curr_df = modifier.get_data()
            plot_demand_preview(curr_df, "scenario_preview.png")
            
        elif choice == '5':
            print("\n Scenario Locked. Preparing Environment...")
            return modifier.get_data()
            
        elif choice == '0':
            sys.exit()
            
        else:
            print(" Invalid choice.")

def main():
    if MODE == "CUSTOM":
        # 1. Load Data
        print(f"Loading {FILE_PATH}...")
        try:
            raw_df = load_and_process_data(FILE_PATH, TARGET_SKU)
        except Exception as e:
            print(f" Error loading file: {e}")
            print("   Make sure the file exists and the SKU is correct.")
            return

        # 2. Interactive Modification
        final_df = interactive_scenario_builder(raw_df)
        
        # --- CRITICAL FIX: LOWERCASE COLUMNS ---
        # The Loader uses 'Demand', but Environment expects 'demand'.
        # We standardize here before training.
        final_df.columns = map(str.lower, final_df.columns)
        # ---------------------------------------
        
        # 3. Configure RL based on Data
        max_demand = final_df['demand'].max() # Now using lowercase 'demand'
        
        # Set max order to 2x peak demand (safety buffer), minimum 2000
        auto_max_order = max(2000, int(max_demand * 2))
        print(f"\nAuto-Configured MAX_ORDER: {auto_max_order}")
        
        # 4. Train
        print(f"\nStarting RL Training on Custom Scenario ({EPISODES} episodes)...")
        agent, rewards, used_max_order, used_action_step = train_agent("custom", episodes=EPISODES, max_order=auto_max_order, custom_df=final_df)
        
        # 5. Evaluate
        print("\nEvaluating Performance...")
        evaluate_and_plot(agent, "custom", max_order=used_max_order, action_step=used_action_step, custom_df=final_df)

    else:
        # Fallback to Synthetic (Summer/Winter)
        print(f"\nStarting Synthetic Training for {MODE}...")
        agent, rewards, used_max_order, used_action_step = train_agent(MODE.lower(), episodes=EPISODES, max_order=MAX_ORDER)
        evaluate_and_plot(agent, MODE.lower(), max_order=used_max_order, action_step=used_action_step)

    print("\n Process Complete. Check the .png files.")

if __name__ == "__main__":
    main()