import sys
import pandas as pd
import matplotlib.pyplot as plt
from trainer import train_agent, evaluate_and_plot
from demand import generate_demand


# ==========================================
# CONFIGURATION
# ==========================================
# Change this variable to "summer" or "winter" to switch modes
SEASON = "winter"


# Training parameters
EPISODES = 1000
MAX_ORDER = 2000


# ==========================================
# HELPER: DEMAND PLOTTING
# ==========================================
def plot_demand_preview(season_type):
   """
   Generates a plot of the demand curve before training starts
   so you can verify the data looks correct.
   """
   print(f"\n📊 Generating demand profile for {season_type.upper()}...")
  
   # Generate a sample year
   # NOTE: generated_demand now produces large numbers (0-2000 range)
   # for BOTH seasons natively. No extra scaling needed here.
   df = generate_demand(season_type, seed=42)
  
   plt.figure(figsize=(15, 6))
   plt.plot(df['Date'], df['Demand'], 'b-', linewidth=2, label='Daily Demand')
   plt.fill_between(df['Date'], df['Demand'], alpha=0.3, color='blue')
  
   # Highlight Seasons
   if season_type == 'winter':
       # Winter: Jan-Feb and Dec
       plt.axvspan(df['Date'].iloc[0], df['Date'].iloc[59], color='cyan', alpha=0.2, label='Winter Season')
       plt.axvspan(df['Date'].iloc[335], df['Date'].iloc[-1], color='cyan', alpha=0.2)
   else:
       # Summer: March-June
       plt.axvspan(df['Date'].iloc[59], df['Date'].iloc[148], color='orange', alpha=0.2, label='Summer Season')


   plt.title(f"{season_type.upper()} Demand Pattern", fontsize=14, fontweight='bold')
   plt.xlabel('Date', fontsize=12)
   plt.ylabel('Daily Demand', fontsize=12)
   plt.legend(loc='upper right')
   plt.grid(True, alpha=0.3)
   plt.tight_layout()
  
   filename = f"{season_type}_demand_profile.png"
   plt.savefig(filename)
   print(f"✅ Saved demand plot to {filename}")
   plt.close()


# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
   # 1. Plot the Demand Data First
   plot_demand_preview(SEASON)
  
   # 2. Start Training
   print(f"\n🚀 Starting training for {SEASON.upper()} ({EPISODES} episodes)...")
   agent, rewards = train_agent(SEASON, episodes=EPISODES, max_order=MAX_ORDER)
  
   # 3. Evaluate & Plot Results
   print(f"\n📈 Evaluating agent performance...")
   evaluate_and_plot(agent, SEASON, max_order=MAX_ORDER)
   print("\n✅ Done! Check the .png files for results.")


if __name__ == "__main__":
   main()

