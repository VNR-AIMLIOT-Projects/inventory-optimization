"""
Three-Echelon Linear Environment — Experiment A2
=================================================
Topology: Supplier(∞) → Warehouse(E1) → DC(E2) → Retailer(E3) → Demand

State: 13-dimensional float32 vector
Actions: 7 × 7 × 7 = 343 joint discrete actions (one order qty per echelon)
"""

import sys, os
import numpy as np
import pandas as pd
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from demand import generate_demand, prepare_env_data, compute_adaptive_params


class ThreeEchelonEnv:
    """
    Three-Echelon Linear Inventory Environment.

    Inventory dynamics (each step, executed E1→E2→E3):
      Ei receives in-transit stock, ships to Ei+1, places order to Ei-1.
    Backorders at E1 and E2 delay downstream replenishment.
    Only E3 (retailer) faces customer demand.

    Parameters
    ----------
    env_data    : prepared DataFrame with [date, demand, day_of_week, promo_flag]
    lead_time_i : lead times for each echelon link (L1=E0→E1, L2=E1→E2, L3=E2→E3)
    h_E1/2/3    : holding cost per unit per day (decreases upstream)
    b_E3        : customer stockout penalty per unit per day
    c_Ei        : fixed ordering cost per order placed
    n_actions_i : discrete order levels per echelon (default 7 → 7³=343)
    """

    N_ECHELONS = 3

    def __init__(
        self,
        env_data: pd.DataFrame,
        *,
        lead_time_1: int   = 4,    # supplier  → warehouse
        lead_time_2: int   = 2,    # warehouse → DC
        lead_time_3: int   = 1,    # DC        → retailer
        h_E1: float        = 1.0,
        h_E2: float        = 3.0,
        h_E3: float        = 5.0,
        b_E3: float        = 500.,
        c_E1: float        = 2.0,
        c_E2: float        = 2.0,
        c_E3: float        = 2.0,
        n_actions: int     = 7,    # per echelon; total = n_actions³
    ):
        self.data     = env_data.reset_index(drop=True)
        self.L        = [lead_time_1, lead_time_2, lead_time_3]
        self.h        = [h_E1, h_E2, h_E3]
        self.b_E3     = b_E3
        self.c        = [c_E1, c_E2, c_E3]
        self.n_act    = n_actions
        self.action_size = n_actions ** 3

        demand_series = self.data["demand"]
        avg_d = float(demand_series.mean())

        # Action grids per echelon (scale to lead-time × demand)
        self.max_orders = []
        self.act_steps  = []
        self.grids      = []
        for i, L in enumerate(self.L):
            mx, step = compute_adaptive_params(demand_series, n_actions, L)
            self.max_orders.append(mx)
            self.act_steps.append(step)
            self.grids.append([j * step for j in range(n_actions)])

        # Normalization caps
        self.max_inv = [int(avg_d * k) for k in [20, 12, 8]]

        self.reset()

    # ------------------------------------------------------------------
    # Action helpers
    # ------------------------------------------------------------------

    def decode_action(self, idx: int):
        """Flat index → (a_E1, a_E2, a_E3) order quantities."""
        n = self.n_act
        i1 = idx // (n * n)
        i2 = (idx % (n * n)) // n
        i3 = idx % n
        return (self.grids[0][i1], self.grids[1][i2], self.grids[2][i3])

    def encode_action(self, a1, a2, a3) -> int:
        n = self.n_act
        def snap(a, step, grid): return int(np.clip(round(a / step), 0, n - 1))
        i1 = snap(a1, self.act_steps[0], self.grids[0])
        i2 = snap(a2, self.act_steps[1], self.grids[1])
        i3 = snap(a3, self.act_steps[2], self.grids[2])
        return i1 * n * n + i2 * n + i3

    # ------------------------------------------------------------------
    # Environment loop
    # ------------------------------------------------------------------

    def reset(self):
        avg_d = self.data["demand"].mean()
        self.t = 0

        # On-hand inventories (warm-start proportional to echelon coverage days)
        self.inv   = [int(avg_d * d) for d in [8, 5, 3]]

        # Backlogs: [WH can't fill DC, DC can't fill Retailer, customer backlog]
        self.bl    = [0, 0, 0]

        # Pipelines (deques for each link)
        self.pipes = [deque([0] * L, maxlen=L) for L in self.L]

        # Memory
        self.last_demand = 0
        self._dh = deque([int(avg_d)] * 3, maxlen=3)

        # Logging
        self.upstream_orders_log = []
        self.demand_log          = []

        return self._state()

    def step(self, action_idx: int):
        row = self.data.iloc[self.t]
        demand_t  = int(row["demand"])
        a1, a2, a3 = self.decode_action(action_idx)

        # ── E1 (Warehouse) ──────────────────────────────────────────
        incoming_E1 = self.pipes[0].popleft()
        self.inv[0] += incoming_E1
        ship_E2 = min(a2, self.inv[0])           # fulfill DC order
        self.bl[0] = max(0, a2 - ship_E2)        # WH backlog
        self.inv[0] -= ship_E2
        self.pipes[0].append(a1)                  # WH orders from supplier

        # ── E2 (Distribution Centre) ─────────────────────────────────
        incoming_E2 = self.pipes[1].popleft()
        self.inv[1] += incoming_E2
        ship_E3 = min(a3, self.inv[1])            # fulfill retailer order
        self.bl[1] = max(0, a3 - ship_E3)         # DC backlog
        self.inv[1] -= ship_E3
        self.pipes[1].append(ship_E2)              # what WH actually shipped

        # ── E3 (Retailer) ────────────────────────────────────────────
        incoming_E3 = self.pipes[2].popleft()
        self.inv[2] += incoming_E3
        sold = min(demand_t, self.inv[2])
        self.inv[2] -= sold
        self.bl[2] = max(0, demand_t - sold)       # customer backlog
        self.pipes[2].append(ship_E3)              # what DC actually shipped

        # ── Reward ───────────────────────────────────────────────────
        holding = sum(self.h[i] * max(self.inv[i], 0) for i in range(3))
        backorder = self.b_E3 * self.bl[2]
        order_cost = sum(self.c[i] * (1 if [a1, a2, a3][i] > 0 else 0)
                         for i in range(3))
        reward = -(holding + backorder + order_cost)

        # ── Logging ──────────────────────────────────────────────────
        self.upstream_orders_log.append(a1)
        self.demand_log.append(demand_t)
        self.last_demand = demand_t
        self._dh.append(demand_t)

        info = {
            "date":          str(row["date"]),
            "demand":        demand_t,
            "inv_E1":        self.inv[0],
            "inv_E2":        self.inv[1],
            "inv_E3":        self.inv[2],
            # Aliases used by shared metrics (expects inv_W / inv_R keys)
            "inv_W":         self.inv[0],
            "inv_R":         self.inv[2],
            "backlog_R":     self.bl[2],
            "backlog_E2":    self.bl[1],
            "a_E1":          a1,
            "a_E2":          a2,
            "a_E3":          a3,
            # shared metrics aliases
            "a_W":           a1,
            "holding_total": holding,
            "holding_W":     self.h[0] * max(self.inv[0], 0),
            "holding_R":     self.h[2] * max(self.inv[2], 0),
            "backorder_R":   self.b_E3 * self.bl[2],
            "order_cost_total": order_cost,
            "order_cost_W":  self.c[0] * (1 if a1 > 0 else 0),
            "order_cost_R":  self.c[2] * (1 if a3 > 0 else 0),
            "reward":        reward,
        }

        self.t += 1
        done = self.t >= len(self.data)
        next_state = self._state() if not done else None
        return next_state, reward, done, info

    def _state(self) -> np.ndarray:
        if self.t >= len(self.data):
            return None
        row  = self.data.iloc[self.t]
        avg_d = self.data["demand"].mean()

        def norm_inv(i):
            return np.log1p(self.inv[i]) / np.log1p(self.max_inv[i])

        def norm_pipe(i):
            return np.clip(sum(self.pipes[i]) / max(self.max_orders[i], 1), 0, 2)

        def norm_bl(i):
            return np.clip(self.bl[i] / max(avg_d, 1), 0, 3)

        ma3  = np.mean(list(self._dh))
        dow  = int(row["day_of_week"])

        return np.array([
            norm_inv(0), norm_pipe(0), norm_bl(0),   # E1
            norm_inv(1), norm_pipe(1), norm_bl(1),   # E2
            norm_inv(2), norm_pipe(2), norm_bl(2),   # E3 (bl=customer)
            np.clip(self.last_demand / max(self.max_orders[2], 1), 0, 1),
            np.clip(ma3 / max(self.max_orders[2], 1), 0, 1),
            np.sin(2 * np.pi * dow / 7),
            np.cos(2 * np.pi * dow / 7),
        ], dtype=np.float32)

    # ------------------------------------------------------------------
    @property
    def state_size(self): return 13

    def bullwhip_ratio(self) -> float:
        w = np.array(self.upstream_orders_log, float)
        d = np.array(self.demand_log, float)
        vd = np.var(d)
        return float(np.var(w) / vd) if vd > 1e-9 else float("nan")

    def service_level(self, info_log) -> float:
        td = sum(d["demand"]   for d in info_log)
        tb = sum(d["backlog_R"] for d in info_log)
        return 1.0 - tb / td if td > 0 else 1.0
