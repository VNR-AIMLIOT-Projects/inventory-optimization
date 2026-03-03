import pandas as pd
import numpy as np

class DemandModifier:
    def __init__(self, original_df):
        self.original_df = original_df.copy()
        self.current_df = original_df.copy()
        
    def reset(self):
        self.current_df = self.original_df.copy()
        print("🔄 Data reset to original.")
        return self.current_df

    def add_spike(self, date_str, amount):
        try:
            date = pd.to_datetime(date_str)
            mask = self.current_df['Date'] == date
            if mask.any():
                self.current_df.loc[mask, 'Demand'] += amount
                print(f" Added {amount} units on {date.date()}")
            else:
                print(f"Date {date_str} not found in range.")
        except:
            print(" Invalid date format. Use YYYY-MM-DD.")
        return self.current_df

    def scale_period(self, start_str, end_str, factor):
        try:
            s = pd.to_datetime(start_str)
            e = pd.to_datetime(end_str)
            mask = (self.current_df['Date'] >= s) & (self.current_df['Date'] <= e)
            if mask.any():
                self.current_df.loc[mask, 'Demand'] = (self.current_df.loc[mask, 'Demand'] * factor).astype(int)
                print(f" Scaled demand by {factor}x from {s.date()} to {e.date()}")
            else:
                print("No data found in that range.")
        except:
            print(" Invalid date format.")
        return self.current_df

    def get_data(self):
        # Re-run flag detection on modified data
        df = self.current_df.copy()
        
        # Recalculate Spikes
        thresh = df['Demand'].quantile(0.90) if df['Demand'].max() > 0 else 0
        df['is_spike'] = (df['Demand'] > thresh).astype(int)
        
        # Recalculate Flags
        indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=7)
        df['promo_flag'] = df['is_spike'].rolling(window=indexer, min_periods=1).max().fillna(0).astype(int)
        
        return df