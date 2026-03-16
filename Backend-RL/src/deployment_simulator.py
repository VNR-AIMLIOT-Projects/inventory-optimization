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

from environment import InventoryEnvironment
from dqn import DQNAgent


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
        
        # Initialize environments for both RL-only and human-modified runs
        self._init_environments()
        
        # Track overrides: {day_index: override_qty}
        self.overrides: Dict[int, int] = {}
        
        # Simulation state
        self.current_day = start_day
        self.history: List[Dict] = []
        
        # Compute initial inventory (demand-proportional)
        avg_demand = self.demand_df['demand'].mean()
        self.initial_inventory = int(avg_demand * 3)
        
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
        
        # Reset to start day
        for _ in range(self.start_day):
            self.rl_env.step(0)  # Step with no action
            
        self.current_day = self.start_day
        self.history = []
        
    def get_rl_action_for_day(self, day: int) -> int:
        """Get the RL agent's decision for a specific day."""
        # Create a temporary environment to get the action
        temp_env = InventoryEnvironment(
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
        
        # Reset and step to the target day
        for _ in range(day):
            temp_env.step(0)
            
        # Get state and ask agent for action (greedy)
        state = temp_env._get_state()
        if state is None:
            return 0
            
        saved_epsilon = self.agent.epsilon
        self.agent.epsilon = 0.0  # Greedy
        action_idx = self.agent.act(state)
        self.agent.epsilon = saved_epsilon
        
        return temp_env.action_space[action_idx]
    
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
        
        # Get RL action
        rl_action = self.get_rl_action_for_day(day)
        
        # Check for human override
        human_action = self.overrides.get(day)
        
        # Use human action if override exists, otherwise RL action
        final_action = human_action if human_action is not None else rl_action
        
        # Find action index in action space
        action_space = list(range(0, self.max_order + self.action_step, self.action_step))
        if final_action not in action_space:
            final_action = 0
        action_idx = action_space.index(final_action)
        
        # Step the environment
        next_state, reward, done, info = self.rl_env.step(action_idx)
        
        # Record history
        day_state = {
            'day': day,
            'date': date_str,
            'demand': demand,
            'inventory': info.get('inventory', 0),
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
        rl_action = self.get_rl_action_for_day(next_day)
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
        
        # Calculate costs
        holding_total = sum(
            self.holding_cost * h['inventory'] 
            for h in self.history 
            if h['inventory'] > 0
        )
        
        stockout_penalty_total = 0
        stockout_days = 0
        for h in self.history:
            demand = h['demand']
            inventory = h['inventory']
            sold = min(demand, inventory + demand)  # Units that could be sold
            lost_sales = demand - sold
            if lost_sales > 0:
                stockout_penalty_total += self.stockout_penalty * lost_sales
                stockout_days += 1
        
        order_cost_total = sum(
            self.order_fixed_cost for h in self.history 
            if h['final_action'] > 0
        )
        
        revenue_total = sum(
            self.price * min(h['demand'], h['inventory'] + h['demand'])
            for h in self.history
        )
        
        avg_inventory = np.mean([h['inventory'] for h in self.history])
        
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


# Global session manager
_deployment_manager = DeploymentSessionManager()


def get_deployment_manager() -> DeploymentSessionManager:
    """Get the global deployment session manager."""
    return _deployment_manager
