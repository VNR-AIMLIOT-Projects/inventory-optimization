# import pandas as pd
# import numpy as np
# import matplotlib.pyplot as plt

# def load_and_process_data(filepath, target_sku=None):
#     """
#     Robust Data Loader for Real-World CSV/Excel.
#     Handles 'DD-MM-YYYY' dates and extracts Season/Spike flags.
#     """
#     print(f"\nLoading from: {filepath}")
    
#     # 1. Load Data
#     if filepath.endswith('.csv'):
#         df = pd.read_csv(filepath)
#     else:
#         df = pd.read_excel(filepath)

#     # 2. Clean Column Names
#     df.columns = [c.strip().lower() for c in df.columns]
    
#     # 3. Detect Date Column
#     date_col = None
#     possible_dates = ['date', 'timestamp', 'day', 'tx_date']
#     for col in df.columns:
#         if col in possible_dates:
#             date_col = col
#             break
#     if not date_col: date_col = df.columns[0]

#     # 4. Parse Dates (Crucial: Handle DD-MM-YYYY)
#     df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
#     df = df.dropna(subset=[date_col]).sort_values(date_col)

#     # 5. Handle Formats (Long vs Wide)
#     if 'sku' in df.columns and 'demand' in df.columns:
#         # User uploaded the template (Long format)
#         if target_sku:
#             target_sku = target_sku.strip()
#             # Filter first, then extract
#             # Normalize SKU column for matching
#             df['sku'] = df['sku'].astype(str).str.strip()
            
#             # Check if SKU exists (case insensitive)
#             sku_match = df[df['sku'].str.lower() == target_sku.lower()]
#             if sku_match.empty:
#                 raise ValueError(f" SKU '{target_sku}' not found in file.")
            
#             clean_df = pd.DataFrame({
#                 'Date': sku_match[date_col],
#                 'Demand': pd.to_numeric(sku_match['demand'], errors='coerce').fillna(0)
#             })
#         else:
#             # Auto-select top SKU
#             top_sku = df['sku'].value_counts().idxmax()
#             print(f"No SKU specified. Auto-selecting: '{top_sku}'")
#             sku_match = df[df['sku'] == top_sku]
#             clean_df = pd.DataFrame({
#                 'Date': sku_match[date_col],
#                 'Demand': pd.to_numeric(sku_match['demand'], errors='coerce').fillna(0)
#             })
#             target_sku = top_sku
            
#     else:
#         # Wide Format logic (Date, SKU1, SKU2...)
#         available_skus = [c for c in df.columns if c != date_col]
#         if not target_sku:
#             target_sku = df[available_skus].sum().idxmax()
#             print(f"No SKU specified. Auto-selecting: '{target_sku}'")
        
#         clean_df = pd.DataFrame({
#             'Date': df[date_col],
#             'Demand': pd.to_numeric(df[target_sku.lower()], errors='coerce').fillna(0)
#         })

#     # 6. Final Cleanup & Filling Gaps
#     clean_df['Demand'] = clean_df['Demand'].clip(lower=0).astype(int)
#     clean_df = clean_df.set_index('Date')
#     full_idx = pd.date_range(start=clean_df.index.min(), end=clean_df.index.max(), freq='D')
#     clean_df = clean_df.reindex(full_idx, fill_value=0).reset_index()
#     clean_df.rename(columns={'index': 'Date'}, inplace=True)

#     # 7. FEATURE EXTRACTION (Season/Spike)
#     # Season = 30-day moving avg > 75th percentile
#     rolling_avg = clean_df['Demand'].rolling(window=30, min_periods=1, center=True).mean()
#     season_thresh = clean_df['Demand'].quantile(0.75)
#     clean_df['is_season'] = (rolling_avg > season_thresh).astype(int)

#     # Spike = Daily > 95th percentile
#     spike_thresh = clean_df['Demand'].quantile(0.95)
#     clean_df['is_spike'] = (clean_df['Demand'] > spike_thresh).astype(int)

#     # RL Lookahead Flags (7 days prior)
#     indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=7)
#     clean_df['promo_flag'] = clean_df['is_spike'].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)
#     clean_df['season_flag'] = clean_df['is_season'].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)
    
#     # Basic Time Feats
#     clean_df['day_of_week'] = clean_df['Date'].dt.dayofweek
#     clean_df['month'] = clean_df['Date'].dt.month

#     print(f" Successfully extracted data for: {target_sku}")
#     return clean_df

# def plot_demand_preview(df, filename="demand_preview.png"):
#     plt.figure(figsize=(15, 6))
#     plt.plot(df['Date'], df['Demand'], label='Demand', color='blue')
#     plt.fill_between(df['Date'], 0, df['season_flag']*df['Demand'].max(), color='orange', alpha=0.2, label='Season Active')
#     plt.scatter(df[df['is_spike']==1]['Date'], df[df['is_spike']==1]['Demand'], color='red', label='Spikes')
#     plt.title("Demand Preview (with Detected Seasons/Spikes)")
#     plt.legend()
#     plt.grid(True, alpha=0.3)
#     plt.savefig(filename)
#     print(f"Saved preview graph to: {filename}")
#     plt.close()

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def detect_demand_parameters(df):
    """
    Analyze a demand DataFrame and extract/estimate the same parameters
    that demand.py uses for synthetic generation.
    
    Returns a dict with:
        - baseline_start, baseline_min, baseline_max, baseline_sigma
        - seasonal_peak, season_periods
        - festival_peak, base_festivals
        - ramp_days (estimated)
    """
    demand = df["Demand"].values
    dates = df["Date"]
    num_days = len(demand)

    # --- 1. BASELINE DETECTION ---
    # Baseline = demand outside of seasons and festivals
    # Use median as robust baseline estimate
    sorted_demand = np.sort(demand)
    # Baseline is the middle 50% of demand values (IQR region)
    q25 = np.percentile(demand, 25)
    q75 = np.percentile(demand, 75)
    baseline_mask = (demand >= q25) & (demand <= q75)
    baseline_values = demand[baseline_mask] if baseline_mask.any() else demand

    baseline_start = int(np.median(baseline_values))
    baseline_min = int(np.percentile(demand, 5))
    baseline_max = int(np.percentile(demand, 75))
    baseline_sigma = round(float(np.std(baseline_values)), 1)

    # --- 2. SEASONAL PEAK & PERIOD DETECTION ---
    # Use 30-day rolling average to find sustained high-demand periods
    rolling_avg = pd.Series(demand).rolling(window=30, center=True, min_periods=15).mean()
    
    # Seasonal threshold: demand consistently above 75th percentile
    seasonal_threshold = np.percentile(demand, 75)
    is_seasonal = (rolling_avg > seasonal_threshold).fillna(False).values

    # Extract contiguous seasonal blocks
    season_periods = []
    in_season = False
    s_start = 0
    for i in range(num_days):
        if is_seasonal[i] and not in_season:
            s_start = i
            in_season = True
        elif not is_seasonal[i] and in_season:
            if (i - s_start) >= 14:  # At least 2 weeks to count as a season
                season_periods.append((s_start, i - 1))
            in_season = False
    if in_season and (num_days - s_start) >= 14:
        season_periods.append((s_start, num_days - 1))

    # Seasonal peak = average demand during seasonal periods
    if season_periods:
        season_values = []
        for s, e in season_periods:
            season_values.extend(demand[s:e+1])
        seasonal_peak = int(np.mean(season_values))
    else:
        seasonal_peak = int(np.percentile(demand, 85))

    # --- 3. FESTIVAL PEAK & FESTIVAL DETECTION ---
    # Festivals = short sharp spikes (1-7 days) above 90th percentile
    spike_threshold = np.percentile(demand, 90)
    is_spike = demand > spike_threshold

    # Group consecutive spike days into festival blocks
    base_festivals = []
    in_spike = False
    f_start = 0
    for i in range(num_days):
        if is_spike[i] and not in_spike:
            f_start = i
            in_spike = True
        elif not is_spike[i] and in_spike:
            if (i - f_start) <= 10:  # Festivals are short (<=10 days)
                base_festivals.append((f_start, i - 1))
            # If longer than 10 days, it's a season not a festival (skip)
            in_spike = False
    if in_spike and (num_days - f_start) <= 10:
        base_festivals.append((f_start, num_days - 1))

    # Festival peak = average demand during festival periods
    if base_festivals:
        festival_values = []
        for s, e in base_festivals:
            festival_values.extend(demand[s:e+1])
        festival_peak = int(np.mean(festival_values))
    else:
        festival_peak = int(np.percentile(demand, 95))

    # --- 4. RAMP DETECTION ---
    # Estimate ramp days by looking at how quickly demand rises before seasons
    ramp_days = 14  # default
    if season_periods:
        ramp_estimates = []
        for s_start, s_end in season_periods:
            if s_start >= 7:
                pre_season = demand[max(0, s_start - 30):s_start]
                if len(pre_season) >= 7:
                    # Find where demand starts rising (crosses baseline mean)
                    baseline_mean = np.mean(baseline_values)
                    rising = np.where(pre_season > baseline_mean * 1.1)[0]
                    if len(rising) > 0:
                        ramp_estimates.append(len(pre_season) - rising[0])
        if ramp_estimates:
            ramp_days = int(np.median(ramp_estimates))
            ramp_days = max(7, min(30, ramp_days))  # Clamp between 7-30

    # --- 5. DETERMINE SEASON TYPE ---
    # Check which months have the highest demand
    monthly_avg = df.groupby(df["Date"].dt.month)["Demand"].mean()
    peak_months = monthly_avg.nlargest(3).index.tolist()
    
    # Summer-half: Mar–Sep (3–9), Winter-half: Oct–Feb (10,11,12,1,2)
    summer_months = {3, 4, 5, 6, 7, 8, 9}
    winter_months = {10, 11, 12, 1, 2}
    
    summer_score = len(set(peak_months) & summer_months)
    winter_score = len(set(peak_months) & winter_months)
    
    if summer_score > winter_score:
        detected_season_type = "summer"
    elif winter_score > summer_score:
        detected_season_type = "winter"
    else:
        # Tie-break: use weighted center of peak months
        # Months 4-8 lean summer, months 10-2 lean winter
        avg_month = np.mean(peak_months)
        detected_season_type = "summer" if 3 <= avg_month <= 9 else "winter"

    # --- BUILD RESULT ---
    # Convert season_periods and festivals to date strings for UI display
    season_periods_dates = []
    for s, e in season_periods:
        s_date = str(dates.iloc[s].date()) if s < len(dates) else None
        e_date = str(dates.iloc[e].date()) if e < len(dates) else None
        if s_date and e_date:
            season_periods_dates.append({"start": s_date, "end": e_date, "start_day": int(s), "end_day": int(e)})

    festival_periods_dates = []
    for s, e in base_festivals:
        s_date = str(dates.iloc[s].date()) if s < len(dates) else None
        e_date = str(dates.iloc[e].date()) if e < len(dates) else None
        if s_date and e_date:
            festival_periods_dates.append({"start": s_date, "end": e_date, "start_day": int(s), "end_day": int(e)})

    return {
        "detected_season_type": detected_season_type,
        "baseline": {
            "start": baseline_start,
            "min": baseline_min,
            "max": baseline_max,
            "sigma": baseline_sigma,
        },
        "seasonal": {
            "peak": seasonal_peak,
            "periods": season_periods_dates,
            "num_seasons": len(season_periods),
        },
        "festival": {
            "peak": festival_peak,
            "periods": festival_periods_dates,
            "num_festivals": len(base_festivals),
        },
        "ramp_days": ramp_days,
        "num_days": num_days,
    }


def regenerate_demand_from_params(original_df, params, seed=42):
    """
    Regenerate a demand time series from modified parameters.

    Uses the same Brownian-motion approach as demand.py so the curve
    looks realistic while honouring the user-supplied baseline, seasonal,
    festival and ramp settings.

    Parameters
    ----------
    original_df : pd.DataFrame
        The originally uploaded DataFrame (used for date range and shape).
    params : dict
        The parameter dict (same schema as detect_demand_parameters output).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        New DataFrame with columns Date, Demand, plus derived feature columns.
    """
    dates = original_df["Date"].values
    num_days = params.get("num_days", len(dates))
    # Extend or truncate dates to match requested num_days
    if num_days > len(dates):
        last_date = pd.to_datetime(dates[-1])
        extra = pd.date_range(
            start=last_date + pd.Timedelta(days=1),
            periods=num_days - len(dates),
            freq="D",
        )
        dates = np.concatenate([dates, extra.values])
    else:
        dates = dates[:num_days]

    # --- Unpack parameters ---
    bl = params["baseline"]
    baseline_start = bl["start"]
    baseline_sigma = bl["sigma"]
    baseline_min = bl["min"]
    baseline_max = bl["max"]

    seasonal_peak = params["seasonal"]["peak"]
    season_periods = []  # list of (start_day, end_day)
    for p in params["seasonal"].get("periods", []):
        season_periods.append((int(p["start_day"]), int(p["end_day"])))

    festival_peak = params["festival"]["peak"]
    festival_periods = []
    for p in params["festival"].get("periods", []):
        festival_periods.append((int(p["start_day"]), int(p["end_day"])))

    ramp_days = params.get("ramp_days", 14)

    np.random.seed(seed)  # reproducible with seed

    # --- 1. BASELINE (Brownian Motion) ---
    baseline = np.zeros(num_days)
    current_val = float(baseline_start)
    for i in range(num_days):
        step = np.random.normal(0, baseline_sigma)
        current_val = np.clip(current_val + step, baseline_min, baseline_max)
        baseline[i] = current_val

    signal = baseline.copy()

    # --- 2. SEASONAL BLOCKS with ramp-up / ramp-down ---
    season_sigma = seasonal_peak * 0.05 if seasonal_peak > 0 else 1.0
    season_low = seasonal_peak * 0.75
    season_high = seasonal_peak * 1.25

    for s_start, s_end in season_periods:
        s_start = min(s_start, num_days - 1)
        s_end = min(s_end, num_days - 1)

        # Ramp-up
        ramp_up_start = max(0, s_start - ramp_days)
        for i, day in enumerate(range(ramp_up_start, s_start)):
            frac = i / max(ramp_days, 1)
            target = baseline[day] + frac * (seasonal_peak - baseline[day])
            prev = signal[day - 1] if day > 0 else baseline[day]
            drift = 0.3 * (target - prev)
            noise = np.random.normal(0, season_sigma * 0.5)
            signal[day] = np.clip(prev + drift + noise, baseline_min, season_high)

        # Season block
        current = float(seasonal_peak)
        for day in range(s_start, min(s_end + 1, num_days)):
            current = np.clip(current + np.random.normal(0, season_sigma), season_low, season_high)
            signal[day] = current

        # Ramp-down
        ramp_down_end = min(num_days - 1, s_end + ramp_days)
        for i, day in enumerate(range(s_end + 1, ramp_down_end + 1)):
            frac = (i + 1) / max(ramp_days, 1)
            target = seasonal_peak - frac * (seasonal_peak - baseline[day])
            prev = signal[day - 1]
            drift = 0.3 * (target - prev)
            noise = np.random.normal(0, season_sigma * 0.5)
            signal[day] = np.clip(prev + drift + noise, baseline_min, season_high)

    # --- 3. FESTIVAL SPIKES ---
    festival_sigma = festival_peak * 0.03 if festival_peak > 0 else 1.0
    festival_low = festival_peak * 0.85
    festival_high = festival_peak * 1.15

    for f_start, f_end in festival_periods:
        current = float(festival_peak)
        for day in range(f_start, min(f_end + 1, num_days)):
            current = np.clip(current + np.random.normal(0, festival_sigma), festival_low, festival_high)
            signal[day] = current

    # --- 4. BUILD DATAFRAME ---
    demand_values = [max(0, int(v)) for v in signal]

    result = pd.DataFrame({
        "Date": dates,
        "Demand": demand_values,
    })
    result = result.sort_values("Date").reset_index(drop=True)

    # Derived features
    result["day_of_week"] = pd.to_datetime(result["Date"]).dt.dayofweek
    result["month"] = pd.to_datetime(result["Date"]).dt.month

    thresh = result["Demand"].quantile(0.90) if result["Demand"].max() > 0 else 0
    result["is_spike"] = (result["Demand"] > thresh).astype(int)

    rolling = result["Demand"].rolling(30, center=True, min_periods=15).mean()
    season_thresh = result["Demand"].median() * 1.3
    result["is_season"] = (rolling > season_thresh).fillna(0).astype(int)

    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=7)
    result["promo_flag"] = result["is_spike"].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)
    result["season_flag"] = result["is_season"].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)

    return result


def load_and_process_data(filepath, target_sku=None):
    """
    Robust Data Loader for Real-World CSV/Excel.
    Handles 'DD-MM-YYYY' dates and extracts Season/Spike flags.
    """
    print(f"\nLoading from: {filepath}")
    
    # 1. Load Data
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    # 2. Clean Column Names
    df.columns = [c.strip().lower() for c in df.columns]
    
    # 3. Detect Date Column
    date_col = None
    possible_dates = ['date', 'timestamp', 'day', 'tx_date']
    for col in df.columns:
        if col in possible_dates:
            date_col = col
            break
    if not date_col:
        date_col = df.columns[0]

    # 4. Parse Dates (Crucial: Handle DD-MM-YYYY)
    df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[date_col]).sort_values(date_col)

    # 5. Handle Formats (Long vs Wide)
    if 'sku' in df.columns:
        # Long format: Date | SKU | Demand
        if target_sku is None:
            target_sku = df['sku'].astype(str).str.strip().unique()[0]
            print(f"No SKU specified. Auto-selecting: '{target_sku}'")
        
        df = df[df['sku'].astype(str).str.strip() == target_sku].copy()
        if df.empty:
            raise ValueError(f"SKU '{target_sku}' not found.")
        
        demand_col = None
        for c in ['demand', 'qty', 'quantity', 'sales', 'units']:
            if c in df.columns:
                demand_col = c
                break
        if not demand_col:
            raise ValueError("Could not find demand column.")
    else:
        # Wide format: Date | SKU1 | SKU2 ...
        if target_sku is None:
            target_sku = [c for c in df.columns if c != date_col][0]
            print(f"No SKU specified. Auto-selecting: '{target_sku}'")
        
        if target_sku.lower() not in df.columns:
            raise ValueError(f"SKU '{target_sku}' not found in columns.")
        demand_col = target_sku.lower()

    print(f" Successfully extracted data for: {target_sku}")

    # 6. Build standardized output DataFrame
    result = pd.DataFrame({
        "Date": df[date_col].values,
        "Demand": df[demand_col].astype(int).values,
    })
    result = result.sort_values("Date").reset_index(drop=True)

    # 7. Add derived features
    result["day_of_week"] = result["Date"].dt.dayofweek
    result["month"] = result["Date"].dt.month

    # 8. Spike detection (above 90th percentile)
    thresh = result["Demand"].quantile(0.90)
    result["is_spike"] = (result["Demand"] > thresh).astype(int)

    # 9. Season detection (30-day rolling avg above median * 1.3)
    rolling = result["Demand"].rolling(30, center=True, min_periods=15).mean()
    season_thresh = result["Demand"].median() * 1.3
    result["is_season"] = (rolling > season_thresh).fillna(0).astype(int)

    # 10. Promo flag (7-day forward lookahead for spikes)
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=7)
    result["promo_flag"] = result["is_spike"].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)

    # 11. Season flag (7-day forward lookahead)
    result["season_flag"] = result["is_season"].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)

    # 12. Detect and store parameters
    result.attrs["detected_params"] = detect_demand_parameters(result)

    return result


def plot_demand_preview(df, filename="demand_preview.png"):
    """Plot demand with detected seasons, spikes, and parameter annotations."""
    params = df.attrs.get("detected_params", None)
    
    fig, axes = plt.subplots(2, 1, figsize=(16, 10), gridspec_kw={"height_ratios": [3, 1]})

    # --- Top: Demand curve with annotations ---
    ax = axes[0]
    ax.plot(df["Date"], df["Demand"], color="steelblue", linewidth=1, label="Daily Demand")

    # Highlight seasons
    if "is_season" in df.columns:
        season_mask = df["is_season"] == 1
        ax.fill_between(df["Date"], 0, df["Demand"].max() * 1.1,
                        where=season_mask, color="orange", alpha=0.1, label="Detected Season")

    # Mark spikes
    if "is_spike" in df.columns:
        spikes = df[df["is_spike"] == 1]
        ax.scatter(spikes["Date"], spikes["Demand"], color="red", s=25, zorder=5, label="Spikes (>90th pct)")

    # Add parameter annotations if available
    if params:
        baseline = params["baseline"]
        ax.axhline(baseline["start"], color="green", linestyle="--", linewidth=1, 
                    label=f"Baseline ≈ {baseline['start']}")
        ax.axhline(params["seasonal"]["peak"], color="orange", linestyle="--", linewidth=1,
                    label=f"Season Peak ≈ {params['seasonal']['peak']}")
        ax.axhline(params["festival"]["peak"], color="red", linestyle="--", linewidth=1,
                    label=f"Festival Peak ≈ {params['festival']['peak']}")

        # Annotate festival periods
        for fest in params["festival"]["periods"]:
            ax.axvspan(pd.to_datetime(fest["start"]), pd.to_datetime(fest["end"]),
                       color="red", alpha=0.15)

    avg = np.mean(df["Demand"])
    ax.axhline(avg, color="gray", linestyle=":", linewidth=1, label=f"Mean = {avg:.0f}")
    
    title = "Demand Analysis — Detected Parameters"
    if params:
        title += f" | Season: {params['detected_season_type'].upper()}"
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.set_ylabel("Demand (units)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)

    # --- Bottom: Parameter summary table ---
    ax2 = axes[1]
    ax2.axis("off")
    
    if params:
        table_data = [
            ["Detected Season Type", params["detected_season_type"].upper()],
            ["Baseline (start / min / max)", f"{baseline['start']} / {baseline['min']} / {baseline['max']}"],
            ["Baseline Sigma", f"{baseline['sigma']}"],
            ["Seasonal Peak", f"{params['seasonal']['peak']}"],
            ["# Season Periods", f"{params['seasonal']['num_seasons']}"],
            ["Festival Peak", f"{params['festival']['peak']}"],
            ["# Festivals Detected", f"{params['festival']['num_festivals']}"],
            ["Ramp Days", f"{params['ramp_days']}"],
            ["Total Days", f"{params['num_days']}"],
        ]
        
        table = ax2.table(cellText=table_data, colLabels=["Parameter", "Value"],
                          loc="center", cellLoc="left")
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.4)
        
        # Style header
        for j in range(2):
            table[0, j].set_facecolor("#4472C4")
            table[0, j].set_text_props(color="white", fontweight="bold")
    else:
        ax2.text(0.5, 0.5, "No parameters detected", ha="center", va="center", fontsize=12)

    fig.tight_layout()
    fig.savefig(filename, dpi=150, bbox_inches="tight")
    print(f"  Saved: {filename}")
    plt.close(fig)


def list_all_skus(filepath):
    """
    Return a list of all SKU identifiers found in the uploaded file.
    Supports both long format (Date, SKU, Demand) and wide format (Date, SKU1, SKU2...).
    """
    if filepath.endswith('.csv'):
        df = pd.read_csv(filepath)
    else:
        df = pd.read_excel(filepath)

    df.columns = [c.strip().lower() for c in df.columns]

    if 'sku' in df.columns:
        skus = sorted(df['sku'].astype(str).str.strip().unique().tolist())
    else:
        date_col = None
        for col in ['date', 'timestamp', 'day', 'tx_date']:
            if col in df.columns:
                date_col = col
                break
        if not date_col:
            date_col = df.columns[0]
        skus = [c for c in df.columns if c != date_col]

    return skus


def load_all_skus_data(filepath):
    """
    Load and process demand data for ALL SKUs in the file.
    Returns a dict: {sku_name: processed_DataFrame}
    """
    skus = list_all_skus(filepath)
    sku_data = {}
    for sku in skus:
        try:
            df = load_and_process_data(filepath, target_sku=sku)
            sku_data[sku] = df
        except Exception as e:
            print(f"  Warning: Failed to load SKU '{sku}': {e}")
    return sku_data