"""
Two-Echelon Linear Supply Chain Environment
============================================
Experiment A1 — Replenix Multi-Echelon Research

Topology
--------
  Supplier (∞) --[L_W days]--> Warehouse --[L_R days]--> Retailer --> Demand

Design Principles
-----------------
- FULLY ISOLATED from Backend-RL/src/ — no imports from production code
- Demand generation is self-contained (mirrors Replenix's demand.py logic)
- The environment is a standard (state, action, reward, done) gym-style loop
- Action space is a Cartesian product: (warehouse_order, retailer_order)

State vector layout (10 dims):
    [0]  norm_inv_W         — log-normalized warehouse on-hand inventory
    [1]  norm_pipeline_W    — in-transit stock heading TO warehouse
    [2]  norm_backlog_R     — unfulfilled retailer demand (retailer backlog)
    [3]  norm_inv_R         — log-normalized retailer on-hand inventory
    [4]  norm_pipeline_R    — in-transit stock FROM warehouse TO retailer
    [5]  norm_demand_prev   — last period's actual demand (normalized)
    [6]  norm_demand_ma3    — 3-day moving average demand (normalized)
    [7]  day_sin            — cyclic weekday encoding (sin)
    [8]  day_cos            — cyclic weekday encoding (cos)
    [9]  promo_flag         — 0/1 upcoming promo/festival window
"""

import numpy as np
import pandas as pd
from collections import deque


# ---------------------------------------------------------------------------
# Demand Generation (self-contained, mirrors Replenix demand.py)
# ---------------------------------------------------------------------------

def generate_demand(season_type="summer", start_date="2025-01-01",
                    num_days=365, seed=42):
    """
    Synthetic demand with seasonal spikes and festival bursts.
    Mirrors the logic in Backend-RL/src/demand.py exactly so experiments
    are comparable to production Replenix results.
    """
    np.random.seed(seed)
    dates = pd.date_range(start=start_date, periods=num_days, freq="D")

    if season_type == "winter":
        off_season_base, seasonal_peak, festival_peak = 400, 1000, 1500
        baseline_start, baseline_sigma = 400, 15.0
        baseline_min, baseline_max = 200, 600
        season_periods  = [(0, 59), (335, 364)]
        base_festivals  = [(15, 19), (120, 124), (220, 224), (300, 304)]
    else:  # summer
        off_season_base, seasonal_peak, festival_peak = 700, 1250, 2000
        baseline_start, baseline_sigma = 375, 75.0
        baseline_min, baseline_max = 0, 750
        season_periods  = [(59, 148)]
        base_festivals  = [(15, 19), (200, 204), (250, 254), (310, 314)]

    ramp_days = 14

    # 1. Brownian baseline
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
        # ramp up
        for i, day in enumerate(range(max(0, s_start - ramp_days), s_start)):
            frac   = i / ramp_days
            target = baseline[day] + frac * (seasonal_peak - baseline[day])
            prev   = signal[day - 1] if day > 0 else baseline[day]
            signal[day] = np.clip(prev + 0.3*(target-prev) +
                                  np.random.normal(0, s_sigma*0.5),
                                  baseline_min, s_hi)
        # season block
        curr = seasonal_peak
        for day in range(s_start, s_end + 1):
            curr = np.clip(curr + np.random.normal(0, s_sigma), s_lo, s_hi)
            signal[day] = curr
        # ramp down
        for i, day in enumerate(range(s_end+1,
                                      min(num_days-1, s_end+ramp_days)+1)):
            frac   = (i+1)/ramp_days
            target = seasonal_peak - frac*(seasonal_peak - baseline[day])
            prev   = signal[day-1]
            signal[day] = np.clip(prev + 0.3*(target-prev) +
                                  np.random.normal(0, s_sigma*0.5),
                                  baseline_min, s_hi)

    # festivals
    f_sigma = festival_peak * 0.03
    f_lo, f_hi = festival_peak * 0.85, festival_peak * 1.15
    for f_start, f_end in base_festivals:
        curr = festival_peak
        for day in range(f_start, min(f_end+1, num_days)):
            curr = np.clip(curr + np.random.normal(0, f_sigma), f_lo, f_hi)
            signal[day] = curr

    demand = [max(0, int(v)) for v in signal]
    return pd.DataFrame({"Date": dates, "Demand": demand})


def prepare_env_data(df, season_type="summer"):
    """Add day_of_week and promo_flag columns (mirrors Replenix prepare_env_data)."""
    df = df.copy()
    df["date"] = df["Date"]
    df["demand"] = df["Demand"]
    df["day_of_week"] = df["date"].dt.dayofweek

    if season_type == "winter":
        festival_periods = [(15, 19), (120, 124), (220, 224), (300, 304)]
    else:
        festival_periods = [(15, 19), (200, 204), (250, 254), (310, 314)]

    df["promo_flag"] = 0
    for start, end in festival_periods:
        promo_start = max(0, start - 7)
        df.loc[(df.index >= promo_start) & (df.index <= end), "promo_flag"] = 1

    return df[["date", "demand", "day_of_week", "promo_flag"]]


# ---------------------------------------------------------------------------
# Helper: compute adaptive action-space params (mirrors Replenix _compute_adaptive_params)
# ---------------------------------------------------------------------------

def compute_adaptive_params(demand_series, n_actions=11, lead_time=2):
    """
    Compute max_order_qty and action_step from demand statistics.
    n_actions: number of discrete order levels (including 0).
    Returns (max_order, action_step).
    """
    max_d  = int(demand_series.max())
    avg_d  = float(demand_series.mean())
    raw_max = max(max_d, int(avg_d * (lead_time + 1)))
    action_step = max(1, int(raw_max / (n_actions - 1)))
    return raw_max, action_step


# ---------------------------------------------------------------------------
# Two-Echelon Environment
# ---------------------------------------------------------------------------

class StochasticTwoEchelonEnv:
    """
    Two-Echelon Linear Inventory Environment with Stochastic Lead Times for Experiment C2.

    Topology
    --------
      Supplier(∞) --[L_W]--> Warehouse --[L_R]--> Retailer --> Demand

    Action Space
    ------------
    A Cartesian product of N_W × N_R discrete actions.
    The agent receives a flat integer action_index; the env decodes it into
    (warehouse_order, retailer_order).

    State Space
    -----------
    10-dimensional float32 vector (documented in module docstring).

    Reward
    ------
    R_t = -(h_W * I_W  +  h_R * I_R  +  b_R * backlog_R
            +  c_W * 1[a_W>0]  +  c_R * 1[a_R>0])

    Units: cost per time-step (day). All costs are negative (we maximize reward).
    """

    def __init__(
        self,
        env_data: pd.DataFrame,
        *,
        lead_time_W_min: int = 2,    # supplier → warehouse min LT
        lead_time_W_max: int = 5,    # supplier → warehouse max LT
        lead_time_R: int   = 1,      # warehouse → retailer lead time
        h_W: float         = 2.0,  # warehouse holding cost / unit / day
        h_R: float         = 5.0,  # retailer  holding cost / unit / day
        b_R: float         = 100., # retailer  backorder penalty / unit / day
        c_W: float         = 10.,  # warehouse fixed ordering cost
        c_R: float         = 10.,  # retailer  fixed ordering cost
        n_actions_W: int   = 11,   # discrete order levels for warehouse
        n_actions_R: int   = 11,   # discrete order levels for retailer
        max_order_W: int   = None, # override; auto-computed if None
        max_order_R: int   = None, # override; auto-computed if None
    ):
        self.data        = env_data.reset_index(drop=True)
        self.L_W_min     = lead_time_W_min
        self.L_W_max     = lead_time_W_max
        self.L_R         = lead_time_R
        self.h_W         = h_W
        self.h_R         = h_R
        self.b_R         = b_R
        self.c_W         = c_W
        self.c_R         = c_R
        self.n_W         = n_actions_W
        self.n_R         = n_actions_R

        demand_series = self.data["demand"]

        # --- Auto-compute order capacity per node ---
        max_W, step_W = compute_adaptive_params(demand_series, n_actions_W, lead_time_W_max)
        max_R, step_R = compute_adaptive_params(demand_series, n_actions_R, lead_time_R)

        self.max_order_W  = max_order_W or max_W
        self.max_order_R  = max_order_R or max_R
        self.action_step_W = max(1, self.max_order_W  // (n_actions_W - 1))
        self.action_step_R = max(1, self.max_order_R  // (n_actions_R - 1))

        # Discrete action grids
        self.action_grid_W = [i * self.action_step_W
                               for i in range(n_actions_W)]   # len = n_W
        self.action_grid_R = [i * self.action_step_R
                               for i in range(n_actions_R)]   # len = n_R

        # Joint action space: flat index → (a_W_idx, a_R_idx)
        self.action_size = n_actions_W * n_actions_R  # 121

        # For normalization
        self.max_inv_W = int(demand_series.mean() * 15)   # ~15-day warehouse stock
        self.max_inv_R = int(demand_series.mean() * 10)   # ~10-day retail stock

        # Demand history for MA3 feature
        self._demand_history = deque([0, 0, 0], maxlen=3)

        # Metrics tracking (reset per episode)
        self.warehouse_orders_log = []   # for bullwhip computation
        self.retailer_demand_log  = []

        self.reset()

    # ------------------------------------------------------------------
    # Action helpers
    # ------------------------------------------------------------------

    def decode_action(self, action_index: int):
        """
        Decode a flat joint action index into (warehouse_qty, retailer_qty).
        Layout: action_index = a_W_idx * n_R + a_R_idx
        """
        a_W_idx = action_index // self.n_R
        a_R_idx = action_index  % self.n_R
        return self.action_grid_W[a_W_idx], self.action_grid_R[a_R_idx]

    def encode_action(self, a_W_qty: int, a_R_qty: int) -> int:
        """Encode (warehouse_qty, retailer_qty) → flat index (nearest grid)."""
        a_W_idx = round(a_W_qty / self.action_step_W)
        a_R_idx = round(a_R_qty / self.action_step_R)
        a_W_idx = np.clip(a_W_idx, 0, self.n_W - 1)
        a_R_idx = np.clip(a_R_idx, 0, self.n_R - 1)
        return int(a_W_idx * self.n_R + a_R_idx)

    # ------------------------------------------------------------------
    # Environment loop
    # ------------------------------------------------------------------

    def reset(self):
        """Reset to start of a new episode. Returns initial state vector."""
        avg_d = self.data["demand"].mean()

        self.current_step = 0

        # Inventories
        self.inv_W = int(avg_d * 5)   # warehouse: ~5 days supply
        self.inv_R = int(avg_d * 3)   # retailer:  ~3 days supply

        # Backlogs
        self.backlog_W = 0   # retailer orders W couldn't fill
        self.backlog_R = 0   # customer demand R couldn't fill

        # Order pipelines
        self.arrivals_W = {}  # dict mapping arrival_day -> qty
        self.pipeline_R = deque([0] * self.L_R, maxlen=self.L_R)  # to retailer

        # Last period memory
        self.last_demand    = 0
        self.last_a_W       = 0
        self.last_a_R       = 0

        # Demand history for MA3
        self._demand_history = deque([int(avg_d)] * 3, maxlen=3)

        # Per-episode logging (for bullwhip metric)
        self.warehouse_orders_log = []
        self.retailer_demand_log  = []

        return self._get_state()

    def step(self, action_index: int):
        """
        Execute one time step (one day) in the environment.

        Parameters
        ----------
        action_index : int
            Flat joint action index decoded into (a_W, a_R).

        Returns
        -------
        next_state : np.ndarray (10,)
        reward     : float
        done       : bool
        info       : dict  — detailed per-step breakdown
        """
        row = self.data.iloc[self.current_step]
        demand_t = int(row["demand"])

        a_W, a_R = self.decode_action(action_index)

        # ── WAREHOUSE STEP ──────────────────────────────────────────
        # 1. Receive incoming stock from supplier
        incoming_W = self.arrivals_W.pop(self.current_step, 0)
        self.inv_W += incoming_W

        # 2. Fulfill retailer's request (a_R from last period's request
        #    is what retailer "ordered"; here we fulfil it from warehouse)
        #    (In each step the retailer places order a_R; it arrives after L_R.
        #     The warehouse ships min(a_R, I_W) immediately into pipeline_R.)
        ship_to_R = min(a_R, self.inv_W)
        unfulfilled_R_order = a_R - ship_to_R
        self.backlog_W = unfulfilled_R_order  # unmet retailer demand at W level

        self.inv_W -= ship_to_R

        # 3. Warehouse places its own replenishment order to supplier
        if a_W > 0:
            lt = np.random.randint(self.L_W_min, self.L_W_max + 1)
            arrival_day = self.current_step + lt
            self.arrivals_W[arrival_day] = self.arrivals_W.get(arrival_day, 0) + a_W

        # ── RETAILER STEP ────────────────────────────────────────────
        # 4. Receive stock from warehouse pipeline
        incoming_R = self.pipeline_R.popleft()
        self.inv_R += incoming_R

        # 5. Fulfill customer demand
        units_sold = min(demand_t, self.inv_R)
        self.inv_R -= units_sold
        self.backlog_R = max(0, demand_t - units_sold)

        # 6. Retailer places order to warehouse (into R's pipeline)
        #    What arrives after L_R days = what warehouse shipped (ship_to_R)
        self.pipeline_R.append(ship_to_R)

        # ── REWARD ───────────────────────────────────────────────────
        holding_W    = self.h_W * max(self.inv_W, 0)
        holding_R    = self.h_R * max(self.inv_R, 0)
        backorder_R  = self.b_R * self.backlog_R
        order_cost_W = self.c_W if a_W > 0 else 0.0
        order_cost_R = self.c_R if a_R > 0 else 0.0

        reward = -(holding_W + holding_R + backorder_R +
                   order_cost_W + order_cost_R)

        # ── LOGGING ──────────────────────────────────────────────────
        self.warehouse_orders_log.append(a_W)
        self.retailer_demand_log.append(demand_t)

        # Update memory
        self.last_demand = demand_t
        self.last_a_W    = a_W
        self.last_a_R    = a_R
        self._demand_history.append(demand_t)

        self.current_step += 1
        done = self.current_step >= len(self.data)

        info = {
            "date":          str(row["date"]),
            "demand":        demand_t,
            "units_sold":    units_sold,
            "inv_W":         self.inv_W,
            "inv_R":         self.inv_R,
            "backlog_R":     self.backlog_R,
            "backlog_W":     self.backlog_W,
            "ship_to_R":     ship_to_R,
            "incoming_W":    incoming_W,
            "a_W":           a_W,
            "a_R":           a_R,
            "holding_W":     holding_W,
            "holding_R":     holding_R,
            "backorder_R":   backorder_R,
            "order_cost_W":  order_cost_W,
            "order_cost_R":  order_cost_R,
            "reward":        reward,
        }

        next_state = self._get_state() if not done else None
        return next_state, reward, done, info

    # ------------------------------------------------------------------
    # State construction
    # ------------------------------------------------------------------

    def _get_state(self) -> np.ndarray:
        """Build the 10-dim state vector from current environment state."""
        if self.current_step >= len(self.data):
            return None

        row = self.data.iloc[self.current_step]

        # Log-normalized inventories (same trick as Replenix for scale invariance)
        norm_inv_W = np.log1p(self.inv_W) / np.log1p(self.max_inv_W)
        norm_inv_R = np.log1p(self.inv_R) / np.log1p(self.max_inv_R)

        # Pipeline inventory (total in-transit, normalized by node max)
        in_transit_W = sum(self.arrivals_W.values())
        norm_pipeline_W = np.clip(
            in_transit_W / max(self.max_order_W, 1), 0, 2)
        norm_pipeline_R = np.clip(
            sum(self.pipeline_R) / max(self.max_order_R, 1), 0, 2)

        # Backlogs (normalized by avg demand)
        avg_d = self.data["demand"].mean()
        norm_backlog_R = np.clip(self.backlog_R / max(avg_d, 1), 0, 3)

        # Demand features
        norm_demand_prev = np.clip(
            self.last_demand / max(self.max_order_R, 1), 0, 1)
        ma3 = np.mean(list(self._demand_history))
        norm_demand_ma3  = np.clip(ma3 / max(self.max_order_R, 1), 0, 1)

        # Cyclic weekday encoding (avoids Monday=0, Sunday=6 discontinuity)
        dow = int(row["day_of_week"])
        day_sin = np.sin(2 * np.pi * dow / 7)
        day_cos = np.cos(2 * np.pi * dow / 7)

        promo = float(row["promo_flag"])

        state = np.array([
            norm_inv_W,
            norm_pipeline_W,
            norm_backlog_R,
            norm_inv_R,
            norm_pipeline_R,
            norm_demand_prev,
            norm_demand_ma3,
            day_sin,
            day_cos,
            promo,
        ], dtype=np.float32)

        return state

    # ------------------------------------------------------------------
    # Metric helpers
    # ------------------------------------------------------------------

    @property
    def state_size(self) -> int:
        return 10

    def bullwhip_ratio(self) -> float:
        """
        Bullwhip Ratio = Var(warehouse_orders) / Var(retailer_demand).
        Values > 1 indicate demand amplification upstream.
        """
        w_orders = np.array(self.warehouse_orders_log, dtype=float)
        r_demand = np.array(self.retailer_demand_log,  dtype=float)
        var_r = np.var(r_demand)
        if var_r < 1e-9:
            return float("nan")
        return float(np.var(w_orders) / var_r)

    def service_level(self, info_log: list) -> float:
        """
        Service level = 1 - (total_backlog / total_demand).
        Pass the list of info dicts collected during an episode.
        """
        total_demand  = sum(d["demand"]    for d in info_log)
        total_backlog = sum(d["backlog_R"] for d in info_log)
        if total_demand == 0:
            return 1.0
        return 1.0 - total_backlog / total_demand
