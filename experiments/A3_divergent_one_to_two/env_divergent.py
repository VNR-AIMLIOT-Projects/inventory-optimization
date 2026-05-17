"""
Divergent Supply Chain Environment — Experiment A3
===================================================
Topology: Supplier(∞) → Warehouse → {Retailer1, Retailer2} → {Demand1, Demand2}

State: 13-dimensional float32 vector
Actions: 7 × 7 × 7 = 343  (a_W, a_R1, a_R2)

When warehouse stock is insufficient, stock is rationed proportionally
to the orders placed by each retailer.
"""

import sys, os
import numpy as np
import pandas as pd
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from demand import generate_demand, prepare_env_data, compute_adaptive_params


class DivergentEnv:
    """
    1-Warehouse → 2-Retailer divergent inventory environment.

    The two retailers operate independently (different demand streams),
    but share the warehouse. Inventory rationing occurs when warehouse
    can't fully supply both retailers simultaneously.

    Rationing rule: proportional to order quantities.
    """

    def __init__(
        self,
        env_data_R1: pd.DataFrame,   # demand data for Retailer 1
        env_data_R2: pd.DataFrame,   # demand data for Retailer 2
        *,
        lead_time_W: int   = 3,      # supplier → warehouse
        lead_time_R: int   = 1,      # warehouse → each retailer
        h_W: float         = 2.0,
        h_R: float         = 5.0,
        b_R: float         = 500.,
        c_W: float         = 2.0,
        c_R: float         = 2.0,
        n_actions: int     = 7,
    ):
        assert len(env_data_R1) == len(env_data_R2), "Both demand streams must have same length"
        self.data_R1 = env_data_R1.reset_index(drop=True)
        self.data_R2 = env_data_R2.reset_index(drop=True)
        self.L_W = lead_time_W
        self.L_R = lead_time_R
        self.h_W = h_W
        self.h_R = h_R
        self.b_R = b_R
        self.c_W = c_W
        self.c_R = c_R
        self.n_act = n_actions
        self.action_size = n_actions ** 3

        # Use combined demand to calibrate warehouse action space
        combined = pd.concat([self.data_R1["demand"], self.data_R2["demand"]])
        r_demand = self.data_R1["demand"]

        self.max_W, self.step_W = compute_adaptive_params(combined, n_actions, lead_time_W)
        self.max_R, self.step_R = compute_adaptive_params(r_demand,  n_actions, lead_time_R)

        self.grid_W = [i * self.step_W for i in range(n_actions)]
        self.grid_R = [i * self.step_R for i in range(n_actions)]

        avg_d = float(r_demand.mean())
        self.max_inv_W = int(avg_d * 20)
        self.max_inv_R = int(avg_d * 10)

        self.reset()

    # ------------------------------------------------------------------
    # Action helpers
    # ------------------------------------------------------------------

    def decode_action(self, idx: int):
        """Flat idx → (a_W, a_R1, a_R2)."""
        n = self.n_act
        iW  = idx // (n * n)
        iR1 = (idx % (n * n)) // n
        iR2 = idx % n
        return self.grid_W[iW], self.grid_R[iR1], self.grid_R[iR2]

    def encode_action(self, aW, aR1, aR2) -> int:
        n = self.n_act
        def snap(a, step): return int(np.clip(round(a / step), 0, n - 1))
        return snap(aW, self.step_W) * n * n + snap(aR1, self.step_R) * n + snap(aR2, self.step_R)

    # ------------------------------------------------------------------
    # Environment loop
    # ------------------------------------------------------------------

    def reset(self):
        avg_d = float(self.data_R1["demand"].mean())
        self.t = 0

        self.inv_W  = int(avg_d * 8)
        self.inv_R1 = int(avg_d * 3)
        self.inv_R2 = int(avg_d * 3)

        self.bl_R1 = 0
        self.bl_R2 = 0

        self.pipe_W  = deque([0] * self.L_W, maxlen=self.L_W)
        self.pipe_R1 = deque([0] * self.L_R, maxlen=self.L_R)
        self.pipe_R2 = deque([0] * self.L_R, maxlen=self.L_R)

        self.last_d1 = 0
        self.last_d2 = 0
        self._dh1 = deque([int(avg_d)] * 3, maxlen=3)

        self.upstream_orders_log = []
        self.demand_log          = []   # combined demand

        return self._state()

    def step(self, action_idx: int):
        row1 = self.data_R1.iloc[self.t]
        row2 = self.data_R2.iloc[self.t]
        d1 = int(row1["demand"])
        d2 = int(row2["demand"])
        aW, aR1, aR2 = self.decode_action(action_idx)

        # ── Warehouse ────────────────────────────────────────────────
        self.inv_W += self.pipe_W.popleft()

        total_order = aR1 + aR2
        if total_order == 0:
            ship_R1, ship_R2 = 0, 0
        elif self.inv_W >= total_order:
            ship_R1, ship_R2 = aR1, aR2
        else:
            # Proportional rationing
            ship_R1 = int(self.inv_W * aR1 / total_order)
            ship_R2 = self.inv_W - ship_R1
            ship_R1 = min(ship_R1, aR1)
            ship_R2 = min(ship_R2, aR2)

        self.inv_W -= (ship_R1 + ship_R2)
        self.pipe_W.append(aW)

        # ── Retailer 1 ───────────────────────────────────────────────
        self.inv_R1 += self.pipe_R1.popleft()
        sold1 = min(d1, self.inv_R1)
        self.inv_R1 -= sold1
        self.bl_R1 = max(0, d1 - sold1)
        self.pipe_R1.append(ship_R1)

        # ── Retailer 2 ───────────────────────────────────────────────
        self.inv_R2 += self.pipe_R2.popleft()
        sold2 = min(d2, self.inv_R2)
        self.inv_R2 -= sold2
        self.bl_R2 = max(0, d2 - sold2)
        self.pipe_R2.append(ship_R2)

        # ── Reward ───────────────────────────────────────────────────
        hold   = (self.h_W * max(self.inv_W, 0)
                 + self.h_R * (max(self.inv_R1, 0) + max(self.inv_R2, 0)))
        backord = self.b_R * (self.bl_R1 + self.bl_R2)
        ocost  = (self.c_W * (1 if aW > 0 else 0)
                 + self.c_R * ((1 if aR1 > 0 else 0) + (1 if aR2 > 0 else 0)))
        reward = -(hold + backord + ocost)

        combined_demand = d1 + d2
        self.upstream_orders_log.append(aW)
        self.demand_log.append(combined_demand)
        self.last_d1 = d1
        self.last_d2 = d2
        self._dh1.append(d1)

        info = {
            "date":           str(row1["date"]),
            "demand":         combined_demand,     # for shared metrics bullwhip
            "demand_R1":      d1,
            "demand_R2":      d2,
            "inv_W":          self.inv_W,
            "inv_R1":         self.inv_R1,
            "inv_R2":         self.inv_R2,
            "inv_R":          (self.inv_R1 + self.inv_R2) // 2,  # alias
            "bl_R1":          self.bl_R1,
            "bl_R2":          self.bl_R2,
            "backlog_R":      self.bl_R1 + self.bl_R2,
            "a_W":            aW,
            "a_E1":           aW,
            "a_R1":           aR1,
            "a_R2":           aR2,
            "holding_total":  hold,
            "holding_W":      self.h_W * max(self.inv_W, 0),
            "holding_R":      self.h_R * (max(self.inv_R1, 0) + max(self.inv_R2, 0)),
            "backorder_R":    backord,
            "order_cost_total": ocost,
            "order_cost_W":   self.c_W * (1 if aW > 0 else 0),
            "order_cost_R":   self.c_R * ((1 if aR1 > 0 else 0) + (1 if aR2 > 0 else 0)),
            "reward":         reward,
            "ship_R1":        ship_R1,
            "ship_R2":        ship_R2,
        }

        self.t += 1
        done = self.t >= len(self.data_R1)
        return (self._state() if not done else None), reward, done, info

    def _state(self) -> np.ndarray:
        if self.t >= len(self.data_R1):
            return None
        row1 = self.data_R1.iloc[self.t]
        avg_d = float(self.data_R1["demand"].mean())

        ma3 = np.mean(list(self._dh1))
        dow = int(row1["day_of_week"])

        return np.array([
            np.log1p(self.inv_W)  / np.log1p(self.max_inv_W),
            np.clip(sum(self.pipe_W) / max(self.max_W, 1), 0, 2),
            np.log1p(self.inv_R1) / np.log1p(self.max_inv_R),
            np.clip(sum(self.pipe_R1) / max(self.max_R, 1), 0, 2),
            np.clip(self.bl_R1 / max(avg_d, 1), 0, 3),
            np.log1p(self.inv_R2) / np.log1p(self.max_inv_R),
            np.clip(sum(self.pipe_R2) / max(self.max_R, 1), 0, 2),
            np.clip(self.bl_R2 / max(avg_d, 1), 0, 3),
            np.clip(self.last_d1 / max(self.max_R, 1), 0, 1),
            np.clip(self.last_d2 / max(self.max_R, 1), 0, 1),
            np.clip(ma3 / max(self.max_R, 1), 0, 1),
            np.sin(2 * np.pi * dow / 7),
            np.cos(2 * np.pi * dow / 7),
        ], dtype=np.float32)

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
