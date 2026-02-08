import numpy as np
import pandas as pd


def generate_demand(
   season_type="summer",
   start_date="2025-01-01",
   num_days=365,
   seed=42
):
   """
   Generates synthetic demand data.
   UPDATED: Summer now produces large numbers natively (approx x50 of original).
   """
   np.random.seed(seed)
   dates = pd.date_range(start=start_date, periods=num_days, freq="D")
  
   # --- CONFIGURATION BASED ON SEASON ---
   if season_type == "winter":
       # Winter: High magnitude (400-1500)
       off_season_base = 400
       seasonal_peak = 1000
       festival_peak = 1500
       baseline_start = 400
       baseline_sigma = 15.0
       baseline_min, baseline_max = 200, 600
      
       # Winter Blocks (Jan-Feb, Dec)
       season_periods = [(0, 59), (335, 364)]
       # Winter Festivals (Jan, May, Aug, Nov)
       base_festivals = [(15, 19), (120, 124), (220, 224), (300, 304)]
      
   else: # Summer
       # Summer: Scaled up to match Winter magnitudes (roughly x50 of original)
       off_season_base = 700      # Was 14
       seasonal_peak = 1250       # Was 25
       festival_peak = 2000       # Was 40
       baseline_start = 375       # Was 7.5
       baseline_sigma = 75.0      # Increased variance
       baseline_min, baseline_max = 0, 750
      
       # Summer Block (March-May)
       season_periods = [(59, 148)]
       # Summer Festivals (Jan, July, Sept, Nov)
       base_festivals = [(15, 19), (200, 204), (250, 254), (310, 314)]


   # Common params
   ramp_days = 14


   # --- 1. GENERATE BASELINE (Brownian Motion) ---
   baseline = np.zeros(num_days)
   current_val = baseline_start
   for i in range(num_days):
       step = np.random.normal(0, baseline_sigma)
       current_val = np.clip(current_val + step, baseline_min, baseline_max)
       baseline[i] = current_val


   # --- 2. APPLY SEASONALITY & FESTIVALS ---
   demand = []
   for day in range(num_days):
       val = baseline[day]
      
       # Check Seasonality
       in_season = False
       for s_start, s_end in season_periods:
           if s_start <= day <= s_end:
               val = seasonal_peak + np.random.randint(-int(seasonal_peak*0.05), int(seasonal_peak*0.05)+1)
               in_season = True
               break
          
           # Ramps
           if (s_start - ramp_days) <= day < s_start:
               days_into = day - (s_start - ramp_days)
               slope = (seasonal_peak - baseline[day]) / ramp_days
               val = baseline[day] + (slope * days_into)
           elif s_end < day <= (s_end + ramp_days):
               days_past = day - s_end
               slope = (seasonal_peak - baseline[day]) / ramp_days
               val = seasonal_peak - (slope * days_past)


       # Check Festivals (Overrides season)
       is_festival = any(s <= day <= e for s, e in base_festivals)
       if is_festival:
           # Add noise to festival peak
           val = festival_peak + np.random.randint(-int(festival_peak*0.05), int(festival_peak*0.05)+1)


       demand.append(max(0, int(val)))


   return pd.DataFrame({"Date": dates, "Demand": demand})


def prepare_env_data(df, season_type="summer"):
   """
   Prepares the dataframe for the RL environment.
   """
   df = df.copy()
   df["date"] = df["Date"]
   df["demand"] = df["Demand"]
   df["day_of_week"] = df["date"].dt.dayofweek
  
   # Select correct festival dates
   if season_type == "winter":
       festival_periods = [(15, 19), (120, 124), (220, 224), (300, 304)]
   else:
       festival_periods = [(15, 19), (200, 204), (250, 254), (310, 314)]
  
   # Apply "Professor's Fix" (7-day lookahead)
   df["promo_flag"] = 0
   for start, end in festival_periods:
       promo_start = max(0, start - 7)
       df.loc[(df.index >= promo_start) & (df.index <= end), "promo_flag"] = 1
      
   return df[["date", "demand", "day_of_week", "promo_flag"]]

