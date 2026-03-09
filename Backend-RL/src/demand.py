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


   # --- 2. PRE-COMPUTE SEASON, RAMP, AND FESTIVAL SIGNALS ---
   # Start from baseline; overwrite season/ramp/festival zones in priority order.
   signal = baseline.copy()

   # Season block: Brownian walk anchored around seasonal_peak
   season_sigma = seasonal_peak * 0.05
   season_low   = seasonal_peak * 0.75
   season_high  = seasonal_peak * 1.25

   for s_start, s_end in season_periods:
       # Ramp-up: directed Brownian walk drifting from baseline toward seasonal_peak
       ramp_up_start = max(0, s_start - ramp_days)
       for i, day in enumerate(range(ramp_up_start, s_start)):
           frac   = i / ramp_days
           target = baseline[day] + frac * (seasonal_peak - baseline[day])
           prev   = signal[day - 1] if day > 0 else baseline[day]
           drift  = 0.3 * (target - prev)
           noise  = np.random.normal(0, season_sigma * 0.5)
           signal[day] = np.clip(prev + drift + noise, baseline_min, season_high)

       # Season block: unconstrained Brownian walk around seasonal_peak
       current = seasonal_peak
       for day in range(s_start, s_end + 1):
           current = np.clip(current + np.random.normal(0, season_sigma), season_low, season_high)
           signal[day] = current

       # Ramp-down: directed Brownian walk drifting from seasonal_peak back to baseline
       ramp_down_end = min(num_days - 1, s_end + ramp_days)
       for i, day in enumerate(range(s_end + 1, ramp_down_end + 1)):
           frac   = (i + 1) / ramp_days
           target = seasonal_peak - frac * (seasonal_peak - baseline[day])
           prev   = signal[day - 1]
           drift  = 0.3 * (target - prev)
           noise  = np.random.normal(0, season_sigma * 0.5)
           signal[day] = np.clip(prev + drift + noise, baseline_min, season_high)

   # Festival signals: Brownian walk clamped within ±15% of festival_peak
   # Written last so they override season/ramp zones.
   festival_sigma = festival_peak * 0.03
   festival_low   = festival_peak * 0.85
   festival_high  = festival_peak * 1.15

   for f_start, f_end in base_festivals:
       current = festival_peak
       for day in range(f_start, min(f_end + 1, num_days)):
           current = np.clip(current + np.random.normal(0, festival_sigma), festival_low, festival_high)
           signal[day] = current

   # --- 3. BUILD DEMAND ---
   demand = [max(0, int(v)) for v in signal]

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

