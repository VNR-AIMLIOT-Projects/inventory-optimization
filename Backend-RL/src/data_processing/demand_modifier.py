import pandas as pd
import numpy as np


class DemandModifier:
    def __init__(self, original_df):
        self.original_df = original_df.copy()
        self.current_df = original_df.copy()
        # Tracks whether any direct mutations (spike / scale / etc.) have been applied.
        # When True, _apply_param_adjustments() is skipped in the preview endpoints
        # so that parameter-based rescaling never overwrites a copilot-applied spike.
        self.has_mutations: bool = False

    # ── Reset ─────────────────────────────────────────────────────────────────
    def reset(self):
        """Restore demand to original uploaded/generated values."""
        self.current_df = self.original_df.copy()
        self.has_mutations = False
        return self.current_df

    # ── Spike: add units on a single date ────────────────────────────────────
    def add_spike(self, date_str, amount):
        """Add `amount` extra units on a specific date."""
        try:
            date = pd.to_datetime(date_str)
            mask = self.current_df['Date'] == date
            if not mask.any():
                nearest = (self.current_df['Date'] - date).abs().idxmin()
                mask = self.current_df.index == nearest
            self.current_df.loc[mask, 'Demand'] += int(amount)
            self.has_mutations = True
        except Exception as e:
            print(f"add_spike error: {e}")
        return self._clamp().current_df

    # ── Remove units: subtract units from a single date ───────────────────────
    def remove_units(self, date_str, amount):
        """Reduce demand by `amount` units on a specific date (floor 0)."""
        try:
            date = pd.to_datetime(date_str)
            mask = self.current_df['Date'] == date
            if not mask.any():
                nearest = (self.current_df['Date'] - date).abs().idxmin()
                mask = self.current_df.index == nearest
            self.current_df.loc[mask, 'Demand'] -= int(amount)
            self.has_mutations = True
        except Exception as e:
            print(f"remove_units error: {e}")
        return self._clamp().current_df

    # ── Set exact value on a single date ─────────────────────────────────────
    def set_value(self, date_str, amount):
        """Set demand to exactly `amount` units on a specific date."""
        try:
            date = pd.to_datetime(date_str)
            mask = self.current_df['Date'] == date
            if not mask.any():
                nearest = (self.current_df['Date'] - date).abs().idxmin()
                mask = self.current_df.index == nearest
            self.current_df.loc[mask, 'Demand'] = int(amount)
            self.has_mutations = True
        except Exception as e:
            print(f"set_value error: {e}")
        return self._clamp().current_df

    # ── Scale: multiply demand by factor over a date range ───────────────────
    def scale(self, start_str, end_str, factor):
        """Multiply demand by factor across a date range. 1.2=+20%, 0.8=-20%."""
        try:
            s = pd.to_datetime(start_str)
            e = pd.to_datetime(end_str)
            mask = (self.current_df['Date'] >= s) & (self.current_df['Date'] <= e)
            if mask.any():
                self.current_df.loc[mask, 'Demand'] = (
                    self.current_df.loc[mask, 'Demand'] * float(factor)
                ).round().astype(int)
            self.has_mutations = True
        except Exception as e:
            print(f"scale error: {e}")
        return self._clamp().current_df

    # Alias for backward compatibility
    def scale_period(self, start_str, end_str, factor):
        return self.scale(start_str, end_str, factor)

    # ── Adjust range: add/subtract flat delta across a date range ─────────────
    def adjust_range(self, start_str, end_str, delta):
        """Add (delta > 0) or remove (delta < 0) flat units from every day in range."""
        try:
            s = pd.to_datetime(start_str)
            e = pd.to_datetime(end_str)
            mask = (self.current_df['Date'] >= s) & (self.current_df['Date'] <= e)
            if mask.any():
                self.current_df.loc[mask, 'Demand'] += int(delta)
            self.has_mutations = True
        except Exception as e:
            print(f"adjust_range error: {e}")
        return self._clamp().current_df

    # ── Remove spike: normalise a spike date to local average ─────────────────
    def remove_spike(self, date_str):
        """Replace a spike with the 7-day rolling window average around that date."""
        try:
            date = pd.to_datetime(date_str)
            mask = self.current_df['Date'] == date
            if not mask.any():
                nearest_idx = (self.current_df['Date'] - date).abs().idxmin()
                mask = self.current_df.index == nearest_idx

            idx = self.current_df[mask].index[0]
            window_mask = (
                (self.current_df['Date'] >= date - pd.Timedelta(days=3)) &
                (self.current_df['Date'] <= date + pd.Timedelta(days=3)) &
                ~mask
            )
            avg = int(self.current_df.loc[window_mask, 'Demand'].mean()) \
                if window_mask.any() else int(self.current_df['Demand'].mean())
            self.current_df.loc[idx, 'Demand'] = avg
            self.has_mutations = True
        except Exception as e:
            print(f"remove_spike error: {e}")
        return self._clamp().current_df

    # ── Clamp: demand never goes below 0 ─────────────────────────────────────
    def _clamp(self):
        self.current_df['Demand'] = self.current_df['Demand'].clip(lower=0)
        return self

    # ── Recalculate derivative columns ───────────────────────────────────────
    def get_data(self):
        df = self.current_df.copy()
        thresh = df['Demand'].quantile(0.90) if df['Demand'].max() > 0 else 0
        df['is_spike'] = (df['Demand'] > thresh).astype(int)
        indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=7)
        df['promo_flag'] = (
            df['is_spike'].rolling(window=indexer, min_periods=1).max()
            .fillna(0).astype(int)
        )
        return df