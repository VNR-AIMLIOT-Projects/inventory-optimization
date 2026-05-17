"""
Shared Demand Generation — Replenix Multi-Echelon Experiments
=============================================================
Single source of truth for synthetic demand across ALL experiments.
Mirrors Backend-RL/src/demand.py exactly so results are comparable
to the production Replenix single-echelon system.
"""

import numpy as np
import pandas as pd


def generate_demand(season_type="summer", start_date="2025-01-01",
                    num_days=365, seed=42):
    """
    Synthetic demand with seasonal peaks and festival bursts.
    Consistent across A1, A2, A3, B1.
    """
    np.random.seed(seed)
    dates = pd.date_range(start=start_date, periods=num_days, freq="D")

    if season_type == "winter":
        off_season_base, seasonal_peak, festival_peak = 400, 1000, 1500
        baseline_start, baseline_sigma = 400, 15.0
        baseline_min, baseline_max = 200, 600
        season_periods = [(0, 59), (335, 364)]
        base_festivals = [(15, 19), (120, 124), (220, 224), (300, 304)]
    else:  # summer
        off_season_base, seasonal_peak, festival_peak = 700, 1250, 2000
        baseline_start, baseline_sigma = 375, 75.0
        baseline_min, baseline_max = 0, 750
        season_periods = [(59, 148)]
        base_festivals = [(15, 19), (200, 204), (250, 254), (310, 314)]

    ramp_days = 14

    baseline = np.zeros(num_days)
    curr = baseline_start
    for i in range(num_days):
        curr = np.clip(curr + np.random.normal(0, baseline_sigma),
                       baseline_min, baseline_max)
        baseline[i] = curr

    signal = baseline.copy()
    s_sigma = seasonal_peak * 0.05
    s_lo, s_hi = seasonal_peak * 0.75, seasonal_peak * 1.25

    for s_start, s_end in season_periods:
        for i, day in enumerate(range(max(0, s_start - ramp_days), s_start)):
            frac = i / ramp_days
            target = baseline[day] + frac * (seasonal_peak - baseline[day])
            prev = signal[day - 1] if day > 0 else baseline[day]
            signal[day] = np.clip(prev + 0.3 * (target - prev) +
                                  np.random.normal(0, s_sigma * 0.5),
                                  baseline_min, s_hi)
        curr = seasonal_peak
        for day in range(s_start, s_end + 1):
            curr = np.clip(curr + np.random.normal(0, s_sigma), s_lo, s_hi)
            signal[day] = curr
        for i, day in enumerate(range(s_end + 1,
                                      min(num_days - 1, s_end + ramp_days) + 1)):
            frac = (i + 1) / ramp_days
            target = seasonal_peak - frac * (seasonal_peak - baseline[day])
            prev = signal[day - 1]
            signal[day] = np.clip(prev + 0.3 * (target - prev) +
                                  np.random.normal(0, s_sigma * 0.5),
                                  baseline_min, s_hi)

    f_sigma = festival_peak * 0.03
    f_lo, f_hi = festival_peak * 0.85, festival_peak * 1.15
    for f_start, f_end in base_festivals:
        curr = festival_peak
        for day in range(f_start, min(f_end + 1, num_days)):
            curr = np.clip(curr + np.random.normal(0, f_sigma), f_lo, f_hi)
            signal[day] = curr

    demand = [max(0, int(v)) for v in signal]
    return pd.DataFrame({"Date": dates, "Demand": demand})


def prepare_env_data(df, season_type="summer"):
    """Adds day_of_week and promo_flag. Consistent with Replenix prepare_env_data."""
    df = df.copy()
    df["date"] = df["Date"]
    df["demand"] = df["Demand"]
    df["day_of_week"] = df["date"].dt.dayofweek

    festivals = ([(15, 19), (120, 124), (220, 224), (300, 304)]
                 if season_type == "winter"
                 else [(15, 19), (200, 204), (250, 254), (310, 314)])

    df["promo_flag"] = 0
    for start, end in festivals:
        promo_start = max(0, start - 7)
        df.loc[(df.index >= promo_start) & (df.index <= end), "promo_flag"] = 1

    return df[["date", "demand", "day_of_week", "promo_flag"]].reset_index(drop=True)


def compute_adaptive_params(demand_series, n_actions, lead_time):
    """Derive max_order and action_step from demand statistics."""
    max_d = int(demand_series.max())
    avg_d = float(demand_series.mean())
    raw_max = max(max_d, int(avg_d * (lead_time + 1)))
    action_step = max(1, int(raw_max / (n_actions - 1)))
    return raw_max, action_step
