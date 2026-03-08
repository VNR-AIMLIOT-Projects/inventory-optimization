import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

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
    if not date_col: date_col = df.columns[0]

    # 4. Parse Dates (Crucial: Handle DD-MM-YYYY)
    df[date_col] = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    df = df.dropna(subset=[date_col]).sort_values(date_col)

    # 5. Handle Formats (Long vs Wide)
    if 'sku' in df.columns and 'demand' in df.columns:
        # User uploaded the template (Long format)
        if target_sku:
            target_sku = target_sku.strip()
            # Filter first, then extract
            # Normalize SKU column for matching
            df['sku'] = df['sku'].astype(str).str.strip()
            
            # Check if SKU exists (case insensitive)
            sku_match = df[df['sku'].str.lower() == target_sku.lower()]
            if sku_match.empty:
                raise ValueError(f" SKU '{target_sku}' not found in file.")
            
            clean_df = pd.DataFrame({
                'Date': sku_match[date_col],
                'Demand': pd.to_numeric(sku_match['demand'], errors='coerce').fillna(0)
            })
        else:
            # Auto-select top SKU
            top_sku = df['sku'].value_counts().idxmax()
            print(f"No SKU specified. Auto-selecting: '{top_sku}'")
            sku_match = df[df['sku'] == top_sku]
            clean_df = pd.DataFrame({
                'Date': sku_match[date_col],
                'Demand': pd.to_numeric(sku_match['demand'], errors='coerce').fillna(0)
            })
            target_sku = top_sku
            
    else:
        # Wide Format logic (Date, SKU1, SKU2...)
        available_skus = [c for c in df.columns if c != date_col]
        if not target_sku:
            target_sku = df[available_skus].sum().idxmax()
            print(f"No SKU specified. Auto-selecting: '{target_sku}'")
        
        clean_df = pd.DataFrame({
            'Date': df[date_col],
            'Demand': pd.to_numeric(df[target_sku.lower()], errors='coerce').fillna(0)
        })

    # 6. Final Cleanup & Filling Gaps
    clean_df['Demand'] = clean_df['Demand'].clip(lower=0).astype(int)
    clean_df = clean_df.set_index('Date')
    full_idx = pd.date_range(start=clean_df.index.min(), end=clean_df.index.max(), freq='D')
    clean_df = clean_df.reindex(full_idx, fill_value=0).reset_index()
    clean_df.rename(columns={'index': 'Date'}, inplace=True)

    # 7. FEATURE EXTRACTION (Season/Spike)
    # Season = 30-day moving avg > 75th percentile
    rolling_avg = clean_df['Demand'].rolling(window=30, min_periods=1, center=True).mean()
    season_thresh = clean_df['Demand'].quantile(0.75)
    clean_df['is_season'] = (rolling_avg > season_thresh).astype(int)

    # Spike = Daily > 95th percentile
    spike_thresh = clean_df['Demand'].quantile(0.95)
    clean_df['is_spike'] = (clean_df['Demand'] > spike_thresh).astype(int)

    # RL Lookahead Flags (7 days prior)
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=7)
    clean_df['promo_flag'] = clean_df['is_spike'].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)
    clean_df['season_flag'] = clean_df['is_season'].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)
    
    # Basic Time Feats
    clean_df['day_of_week'] = clean_df['Date'].dt.dayofweek
    clean_df['month'] = clean_df['Date'].dt.month

    print(f" Successfully extracted data for: {target_sku}")
    return clean_df

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
        # Long format
        skus = sorted(df['sku'].astype(str).str.strip().unique().tolist())
    else:
        # Wide format — every column except the date column is a SKU
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
    Each DataFrame has the same format as load_and_process_data() output.
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


def plot_demand_preview(df, filename="demand_preview.png"):
    plt.figure(figsize=(15, 6))
    plt.plot(df['Date'], df['Demand'], label='Demand', color='blue')
    plt.fill_between(df['Date'], 0, df['season_flag']*df['Demand'].max(), color='orange', alpha=0.2, label='Season Active')
    plt.scatter(df[df['is_spike']==1]['Date'], df[df['is_spike']==1]['Demand'], color='red', label='Spikes')
    plt.title("Demand Preview (with Detected Seasons/Spikes)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(filename)
    print(f"Saved preview graph to: {filename}")
    plt.close()