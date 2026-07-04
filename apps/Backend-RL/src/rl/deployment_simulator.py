"""
Deployment Simulator for Interactive RL Agent Testing
=====================================================
Allows users to:
- Step through simulation day by day
- Override RL decisions for future days
- Compare RL-only vs Human-modified performance
"""

import uuid
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from collections import deque

from rl.environment import InventoryEnvironment
from rl.dqn import DQNAgent


class DeploymentSimulator:
    """
    Manages an interactive simulation session where users can override
    RL agent decisions for future days.
    """

    def __init__(
        self,
        session_id: str,
        sku: str,
        agent: DQNAgent,
        demand_df: pd.DataFrame,
        max_order: int,
        action_step: int,
        holding_cost: float = 5,
        stockout_penalty: float = 200,
        order_fixed_cost: float = 10,
        price: float = 100,
        start_day: int = 0,
    ):
        self.session_id = session_id
        self.sku = sku
        self.agent = agent
        self.demand_df = demand_df.reset_index(drop=True)
        self.max_order = max_order
        self.action_step = action_step
        self.holding_cost = holding_cost
        self.stockout_penalty = stockout_penalty
        self.order_fixed_cost = order_fixed_cost
        self.price = price
        self.start_day = start_day

        self.total_days = len(demand_df)

        # Initialize the running environment
        self._init_environments()

        # Track overrides: {day_index: override_qty}
        self.overrides: Dict[int, int] = {}

        # Simulation state
        self.current_day = start_day
        self.history: List[Dict] = []

        # Compute initial inventory (demand-proportional)
        avg_demand = self.demand_df['demand'].mean()
        self.initial_inventory = int(avg_demand * 3)

        # Cache the current state AFTER each step, so we can ask the agent
        # for its next action without reconstructing a broken temp environment.
        # Prime the cache by advancing the env to start_day via greedy decisions
        # (same logic as reset() so __init__ and reset() are always consistent).
        self._current_state = self.rl_env._get_state()
        for _ in range(self.start_day):
            action_idx = self._greedy_action_idx(self._current_state)
            next_state, _, _, _ = self.rl_env.step(action_idx)
            self._current_state = next_state

    def _init_environments(self):
        """Initialize RL and human-modified environments."""
        self.rl_env = InventoryEnvironment(
            self.demand_df,
            lead_time=2,
            max_order_qty=self.max_order,
            action_step=self.action_step,
            holding_cost=self.holding_cost,
            stockout_penalty=self.stockout_penalty,
            order_fixed_cost=self.order_fixed_cost,
            price=self.price,
            demand_scale=1.0,
        )

    def reset(self):
        """Reset simulation to start day."""
        self.rl_env = InventoryEnvironment(
            self.demand_df,
            lead_time=2,
            max_order_qty=self.max_order,
            action_step=self.action_step,
            holding_cost=self.holding_cost,
            stockout_penalty=self.stockout_penalty,
            order_fixed_cost=self.order_fixed_cost,
            price=self.price,
            demand_scale=1.0,
        )

        # Advance env to start_day using greedy agent decisions, not 0-order
        # This correctly initialises the pipeline and inventory before the
        # interactive portion begins.
        self._current_state = self.rl_env._get_state()
        for _ in range(self.start_day):
            action_idx = self._greedy_action_idx(self._current_state)
            next_state, _, _, _ = self.rl_env.step(action_idx)
            self._current_state = next_state

        self.current_day = self.start_day
        self.history = []

    # ------------------------------------------------------------------
    # BUG FIX #1: Replace the broken get_rl_action_for_day() with a
    # simple greedy query on the RUNNING environment's current state.
    #
    # The old implementation created a fresh temp env and fast-forwarded
    # it with action=0 for every day, so by day N the env had:
    #   - inventory = 0  (drained by zero ordering)
    #   - stockout_flag = 1
    #   - last_demand = prev day demand
    # This gave the agent a "depleted" state, which (correctly) caused it
    # to output action=0 (there was no inventory to protect and no pending
    # orders — the agent learned not to order into a hopeless stockout).
    # Result: RL recommended 0 units regardless of actual live inventory.
    # ------------------------------------------------------------------

    def _greedy_action_idx(self, state) -> int:
        """Ask the agent for a greedy (epsilon=0) action index."""
        if state is None:
            return 0
        saved_epsilon = self.agent.epsilon
        self.agent.epsilon = 0.0
        action_idx = self.agent.act(state)
        self.agent.epsilon = saved_epsilon
        return action_idx

    def get_rl_recommendation(self) -> int:
        """
        Return the RL agent's recommended order quantity for the CURRENT day,
        based on the live running environment state (not a reconstructed temp env).
        """
        action_idx = self._greedy_action_idx(self._current_state)
        return self.rl_env.action_space[action_idx]

    def set_override(self, day: int, qty: int):
        """
        Set a human override for a future day.
        Only allows overrides for day >= current_day (future only).
        """
        if day < self.current_day:
            raise ValueError(f"Cannot override past day {day}. Only future days allowed.")

        if day >= self.total_days:
            raise ValueError(f"Day {day} exceeds total days {self.total_days}")

        # Clamp to valid action space
        valid_qty = min(qty, self.max_order)
        valid_qty = (valid_qty // self.action_step) * self.action_step

        self.overrides[day] = valid_qty

    def remove_override(self, day: int):
        """Remove a human override for a day."""
        if day in self.overrides:
            del self.overrides[day]

    def get_override(self, day: int) -> Optional[int]:
        """Get override quantity for a day, or None if not overridden."""
        return self.overrides.get(day)

    def step(self) -> Dict:
        """
        Advance simulation by one day.
        Returns the state for the day that was just processed.
        """
        if self.current_day >= self.total_days:
            raise ValueError("Simulation already at end")

        day = self.current_day
        row = self.demand_df.iloc[day]
        date_str = str(row['date']) if 'date' in row else str(row['Date'])
        demand = int(row['demand'] if 'demand' in row else row['Demand'])

        # FIX: Query RL recommendation from the LIVE state, not a temp env
        rl_action = self.get_rl_recommendation()

        # Check for human override
        human_action = self.overrides.get(day)

        # Use human action if override exists, otherwise RL action
        final_action = human_action if human_action is not None else rl_action

        # Find action index in action space
        action_space = self.rl_env.action_space
        # Snap final_action to nearest valid discrete action
        if final_action not in action_space:
            final_action = min(action_space, key=lambda a: abs(a - final_action))
        action_idx = action_space.index(final_action)

        # Snapshot inventory BEFORE step (used for accurate metrics later)
        # NOTE: inv_before_sale is populated from info after step() completes
        # since only the environment knows the post-arrival, pre-sale inventory.

        # Step the RUNNING environment (maintains inventory/pipeline state)
        next_state, reward, done, info = self.rl_env.step(action_idx)

        # Accurate inv_before_sale: inventory after arrivals, before sales
        # (populated by InventoryEnvironment.step() into the info dict)
        inv_before_sale = info.get('inv_before_sale', self.rl_env.inv_onhand)

        # Cache the new state so the next call to get_rl_recommendation() uses it
        self._current_state = next_state

        # Record history — include inv_before_sale for exact metric computation
        day_state = {
            'day': day,
            'date': date_str,
            'demand': demand,
            'inventory': info.get('inventory', 0),   # end-of-day (after sales)
            'inv_before_sale': inv_before_sale,       # start-of-sales-phase inventory
            'rl_action': rl_action,
            'human_action': human_action,
            'final_action': final_action,
            'reward': reward,
            'pipeline': list(self.rl_env.order_pipeline),
        }
        self.history.append(day_state)

        self.current_day += 1

        return day_state

    def get_next_prediction(self) -> Optional[Dict]:
        """Get RL's predicted action for the next day (without executing)."""
        if self.current_day >= self.total_days:
            return None

        next_day = self.current_day
        # Use the cached live state — accurate prediction
        rl_action = self.get_rl_recommendation()
        row = self.demand_df.iloc[next_day]

        return {
            'day': next_day,
            'date': str(row['date']) if 'date' in row else str(row['Date']),
            'demand': int(row['demand'] if 'demand' in row else row['Demand']),
            'rl_action': rl_action,
            'has_override': next_day in self.overrides,
            'override_qty': self.overrides.get(next_day),
        }

    def compute_metrics(self, rl_only: bool = False) -> Dict:
        """Compute cumulative metrics from history."""
        if not self.history:
            return self._empty_metrics()

        rewards = [h['reward'] for h in self.history]

        # Holding cost: computed from end-of-day inventory (after sales)
        holding_total = sum(
            self.holding_cost * h['inventory']
            for h in self.history
            if h['inventory'] > 0
        )

        # ------------------------------------------------------------------
        # Revenue & stockout computation
        # We store 'inv_before_sale' in history (the inventory level AFTER
        # arrivals but BEFORE sales, i.e. the exact value the environment
        # uses for min(demand, inv_before_sale)).  For backward-compatibility
        # with old history records that don't have this field, we fall back
        # to the reward-inversion algebra.
        # ------------------------------------------------------------------

        stockout_penalty_total = 0.0
        stockout_days = 0
        revenue_total = 0.0
        order_cost_total = 0.0

        for h in self.history:
            demand = h['demand']
            inv_end = h['inventory']
            final_action = h.get('final_action', 0)
            order_cost_day = self.order_fixed_cost if final_action > 0 else 0.0

            if 'inv_before_sale' in h:
                # Exact calculation — no algebraic inversion needed
                inv_before = h['inv_before_sale']
                units_sold = min(demand, inv_before)
                lost_sales = demand - units_sold
            else:
                # Legacy fallback: back-calculate from reward formula
                # reward = price*sold - holding*inv_end - penalty*lost - order_cost
                # => sold = (reward + holding*inv_end + penalty*demand + order_cost)
                #            / (price + penalty)
                numerator = (h['reward'] + self.holding_cost * inv_end
                             + self.stockout_penalty * demand + order_cost_day)
                denominator = self.price + self.stockout_penalty
                units_sold = max(0.0, min(float(demand), numerator / denominator))
                lost_sales = max(0.0, float(demand) - units_sold)

            revenue_total += self.price * units_sold
            if lost_sales > 0.5:  # small threshold to absorb float noise
                stockout_penalty_total += self.stockout_penalty * lost_sales
                stockout_days += 1

            order_cost_total += order_cost_day

        avg_inventory = float(np.mean([h['inventory'] for h in self.history]))

        return {
            'current_day': self.current_day,
            'total_days': self.total_days,
            'cumulative_reward': sum(rewards),
            'total_cost': holding_total + stockout_penalty_total + order_cost_total,
            'total_revenue': revenue_total,
            'stockout_days': stockout_days,
            'holding_cost_total': holding_total,
            'stockout_penalty_total': stockout_penalty_total,
            'order_cost_total': order_cost_total,
            'avg_inventory': avg_inventory,
        }

    def _empty_metrics(self) -> Dict:
        """Return empty metrics structure."""
        return {
            'current_day': self.current_day,
            'total_days': self.total_days,
            'cumulative_reward': 0.0,
            'total_cost': 0.0,
            'total_revenue': 0.0,
            'stockout_days': 0,
            'holding_cost_total': 0.0,
            'stockout_penalty_total': 0.0,
            'order_cost_total': 0.0,
            'avg_inventory': 0.0,
        }

    def run_all(self) -> List[Dict]:
        """Run simulation until end and return full history."""
        while self.current_day < self.total_days:
            self.step()
        return self.history

    def get_full_state(self) -> Dict:
        """Get complete simulation state."""
        metrics = self.compute_metrics()

        return {
            'session_id': self.session_id,
            'current_day': self.current_day,
            'total_days': self.total_days,
            'history': self.history,
            'metrics': metrics,
            'next_prediction': self.get_next_prediction(),
        }


class DeploymentSessionManager:
    """
    Manages multiple deployment sessions.
    """

    def __init__(self):
        self.sessions: Dict[str, DeploymentSimulator] = {}

    def create_session(
        self,
        sku: str,
        agent: DQNAgent,
        demand_df: pd.DataFrame,
        max_order: int,
        action_step: int,
        holding_cost: float = 5,
        stockout_penalty: float = 200,
        start_day: int = 0,
    ) -> str:
        """Create a new deployment session."""
        session_id = str(uuid.uuid4())

        simulator = DeploymentSimulator(
            session_id=session_id,
            sku=sku,
            agent=agent,
            demand_df=demand_df,
            max_order=max_order,
            action_step=action_step,
            holding_cost=holding_cost,
            stockout_penalty=stockout_penalty,
            start_day=start_day,
        )

        self.sessions[session_id] = simulator
        return session_id

    def get_session(self, session_id: str) -> Optional[DeploymentSimulator]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False


class MultiSkuDeploymentOrchestrator:
    """
    Orchestrates simultaneous deployment of multiple SKU RL agents.
    Each SKU gets its own DeploymentSimulator. Supports:
    - step_all(): advance every SKU by one day simultaneously
    - step_sku(sku): advance only one SKU by one day
    - override per-SKU future day order quantities
    - aggregate KPI metrics across all SKUs
    """

    def __init__(self):
        # sku_name -> DeploymentSimulator
        self.simulators: Dict[str, DeploymentSimulator] = {}
        self.session_id: str = str(uuid.uuid4())

    def add_sku(
        self,
        sku: str,
        agent: DQNAgent,
        demand_df: pd.DataFrame,
        max_order: int,
        action_step: int,
        holding_cost: float = 5,
        stockout_penalty: float = 200,
        start_day: int = 0,
    ):
        """Register a SKU simulator."""
        sim = DeploymentSimulator(
            session_id=f"{self.session_id}:{sku}",
            sku=sku,
            agent=agent,
            demand_df=demand_df,
            max_order=max_order,
            action_step=action_step,
            holding_cost=holding_cost,
            stockout_penalty=stockout_penalty,
            start_day=start_day,
        )
        self.simulators[sku] = sim

    def step_all(self) -> Dict[str, Dict]:
        """Advance every SKU by one day simultaneously. Returns per-SKU day states."""
        results = {}
        for sku, sim in self.simulators.items():
            if sim.current_day < sim.total_days:
                results[sku] = sim.step()
            else:
                results[sku] = None  # already finished
        return results

    def step_sku(self, sku: str) -> Optional[Dict]:
        """Advance a single SKU by one day."""
        sim = self.simulators.get(sku)
        if sim is None:
            raise ValueError(f"SKU '{sku}' not found in orchestrator")
        if sim.current_day >= sim.total_days:
            raise ValueError(f"SKU '{sku}' simulation already complete")
        return sim.step()

    def set_override(self, sku: str, day: int, qty: int):
        """Set a human override for a specific SKU on a specific day."""
        sim = self.simulators.get(sku)
        if sim is None:
            raise ValueError(f"SKU '{sku}' not found")
        sim.set_override(day, qty)

    def remove_override(self, sku: str, day: int):
        """Remove override for a SKU/day."""
        sim = self.simulators.get(sku)
        if sim:
            sim.remove_override(day)

    def reset_all(self):
        """Reset all simulators to their start days."""
        for sim in self.simulators.values():
            sim.reset()

    def reset_sku(self, sku: str):
        """Reset a single SKU simulator."""
        sim = self.simulators.get(sku)
        if sim:
            sim.reset()

    def remove_sku(self, sku: str) -> str:
        """
        Remove a SKU from the live session entirely.
        Returns the name of the removed SKU.
        Raises ValueError if SKU not found.
        """
        if sku not in self.simulators:
            raise ValueError(f"SKU '{sku}' not found in active session.")
        del self.simulators[sku]
        return sku

    def get_sku_state(self, sku: str) -> Optional[Dict]:
        """Return full state for one SKU (history, metrics, next prediction)."""
        sim = self.simulators.get(sku)
        if sim is None:
            return None
        return sim.get_full_state()

    def get_all_states(self) -> Dict[str, Dict]:
        """Return full state for every SKU."""
        return {sku: sim.get_full_state() for sku, sim in self.simulators.items()}

    def get_aggregate_metrics(self) -> Dict:
        """Compute combined KPIs across all SKUs."""
        total_revenue = 0.0
        total_cost = 0.0
        total_stockout_days = 0
        total_cumulative_reward = 0.0
        total_inventory_sum = 0.0
        total_days_count = 0
        total_inventory_value = 0.0

        # Average unit price across SKUs (default $100)
        unit_price = 100.0

        for sim in self.simulators.values():
            m = sim.compute_metrics()
            total_revenue += m["total_revenue"]
            total_cost += m["total_cost"]
            total_stockout_days += m["stockout_days"]
            total_cumulative_reward += m["cumulative_reward"]
            if m["avg_inventory"] > 0:
                total_inventory_sum += m["avg_inventory"]
                total_days_count += 1

            # BUG FIX #4: Current inventory value uses the LIVE environment
            # inventory (rl_env.inv_onhand), not the last history row which
            # lags by one day.  Falls back to initial_inventory if session
            # hasn't started yet.
            current_inv = sim.rl_env.inv_onhand if sim.history else sim.initial_inventory
            total_inventory_value += current_inv * unit_price

        # Current day = max across all simulators (for "global day")
        current_days = [sim.current_day for sim in self.simulators.values()]
        global_day = max(current_days) if current_days else 0
        total_days = max((sim.total_days for sim in self.simulators.values()), default=0)

        net_profit = total_revenue - total_cost

        return {
            "global_day": global_day,
            "total_days": total_days,
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "net_profit": round(net_profit, 2),
            "total_stockout_days": total_stockout_days,
            "total_cumulative_reward": round(total_cumulative_reward, 2),
            "avg_inventory": round(total_inventory_sum / max(total_days_count, 1), 1),
            "total_inventory_value": round(total_inventory_value, 2),
            "sku_count": len(self.simulators),
        }

    def get_sku_summary(self) -> Dict[str, Dict]:
        """Return lightweight per-SKU summary for the left panel (list view)."""
        summaries = {}
        for sku, sim in self.simulators.items():
            m = sim.compute_metrics()

            # FIX: Use the live environment's actual inventory, not lagged history
            current_inventory = sim.rl_env.inv_onhand if sim.history else sim.initial_inventory
            last_reward = sim.history[-1]["reward"] if sim.history else 0.0

            current_inventory_value = current_inventory * 100.0  # unit price $100

            # Health status
            if current_inventory == 0:
                health = "stockout"
            elif current_inventory < sim.initial_inventory * 0.2:
                health = "low"
            else:
                health = "healthy"

            next_pred = sim.get_next_prediction()
            summaries[sku] = {
                "sku": sku,
                "current_day": sim.current_day,
                "total_days": sim.total_days,
                "current_inventory": current_inventory,
                "current_inventory_value": current_inventory_value,
                "cumulative_revenue": round(m["total_revenue"], 2),
                "cumulative_cost": round(m["total_cost"], 2),
                "net_profit": round(m["total_revenue"] - m["total_cost"], 2),
                "stockout_days": m["stockout_days"],
                "avg_inventory": round(m["avg_inventory"], 1),
                "last_reward": round(last_reward, 2),
                "health": health,
                "is_complete": sim.current_day >= sim.total_days,
                "next_rl_action": next_pred["rl_action"] if next_pred else None,
                "next_demand": next_pred["demand"] if next_pred else None,
                "next_date": next_pred["date"] if next_pred else None,
            }
        return summaries

    @property
    def skus(self) -> list:
        return list(self.simulators.keys())

    @property
    def is_all_complete(self) -> bool:
        return all(sim.current_day >= sim.total_days for sim in self.simulators.values())


# Global session manager
_deployment_manager = DeploymentSessionManager()

# Global multi-SKU orchestrator (singleton, replaced on new deployment start)
_multi_sku_orchestrator: Optional[MultiSkuDeploymentOrchestrator] = None


def get_deployment_manager() -> DeploymentSessionManager:
    """Get the global deployment session manager."""
    return _deployment_manager


def get_multi_sku_orchestrator() -> Optional[MultiSkuDeploymentOrchestrator]:
    """Get the active multi-SKU orchestrator, or None if not started."""
    return _multi_sku_orchestrator


def set_multi_sku_orchestrator(orch: MultiSkuDeploymentOrchestrator):
    """Replace the global multi-SKU orchestrator."""
    global _multi_sku_orchestrator
    _multi_sku_orchestrator = orch
