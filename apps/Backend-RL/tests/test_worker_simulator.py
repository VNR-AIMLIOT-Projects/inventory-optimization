import pytest
import os
import sys
import numpy as np
import pandas as pd

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from rl.environment import InventoryEnvironment
from rl.dqn import DQNAgent
from rl.deployment_simulator import DeploymentSimulator
from models.domain import TrainingRun
from sqlalchemy.orm import Session

def get_mock_data():
    return pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"],
        "demand": [10, 15, 20, 10, 5],
        "day_of_week": [2, 3, 4, 5, 6],
        "promo_flag": [0, 0, 1, 0, 0]
    })

def test_rl_environment_init():
    """Test initializing the RL environment."""
    env = InventoryEnvironment(
        historical_data=get_mock_data(),
        holding_cost=5.0,
        stockout_penalty=100.0,
        max_order_qty=50
    )
    assert env.max_order_qty == 50
    assert env.h == 5.0
    
    # Check reset
    state = env.reset()
    assert state is not None
    assert len(state) == 15
    assert env.current_step == 0

def test_rl_environment_step():
    """Test stepping through the RL environment."""
    env = InventoryEnvironment(
        historical_data=get_mock_data(),
        holding_cost=5.0,
        stockout_penalty=100.0,
        max_order_qty=50,
        action_step=10
    )
    env.reset()
    
    # action space = [0, 10, 20, 30, 40, 50]
    # Let's pass index 2, which is action 20
    next_state, reward, done, info = env.step(action_index=2)
    
    # Demand on day 0 is 10.
    assert info["demand"] == 10
    assert info["action_order_qty"] == 20
    assert not done

def test_dqn_agent():
    """Test DQN Agent basic operations."""
    agent = DQNAgent(state_size=15, action_size=6)
    
    # Test action selection (random since epsilon is 1.0)
    state = np.zeros(15)
    action = agent.act(state)
    assert 0 <= action <= 5
    
    # Test memory and replay
    next_state = np.ones(15)
    agent.buffer.push(state, action, -50, next_state, False)
    assert len(agent.buffer) == 1
    
    # Won't replay if batch_size > memory
    agent.learn()

def test_deployment_simulator_mock(monkeypatch):
    """Test initializing DeploymentSimulator with mocked DB and model."""
    class MockRun:
        id = 1
        sku_name = "TEST-SKU"
        holding_cost = 5.0
        stockout_penalty = 100.0
        max_order = 50
        model_path = "fake.pth"
    
    def mock_query(*args, **kwargs):
        class Query:
            def filter(self, *a, **k):
                return self
            def first(self):
                return MockRun()
        return Query()
        
    def mock_load(*args, **kwargs):
        pass

    monkeypatch.setattr(Session, "query", mock_query)
    monkeypatch.setattr("torch.load", mock_load)
    monkeypatch.setattr("torch.load", mock_load)
    
    # Simulator expects run_id and a demand_data array or dataframe
    sim = DeploymentSimulator(
        session_id="test",
        sku="SKU-A",
        agent=DQNAgent(15, 6),
        demand_df=get_mock_data(),
        max_order=50,
        action_step=10
    )
    
    assert sim.session_id == "test"
    assert sim.sku == "SKU-A"
    assert sim.total_days == 5
    assert sim.current_day == 0

    # Step simulation without model (using mock act)
    monkeypatch.setattr(sim.agent, "act", lambda x: 2) # Action index 2 -> 20 qty
    
    state = sim.step()
    # Day 0: Demand 10
    assert state["day"] == 0
    assert state["demand"] == 10
    assert sim.current_day == 1
