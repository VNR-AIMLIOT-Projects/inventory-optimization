import pytest
import os
import sys
import numpy as np

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from environment import RLEnvironment
from dqn import DQNAgent
from deployment_simulator import DeploymentSimulator
from models import TrainingRun
from sqlalchemy.orm import Session

def test_rl_environment_init():
    """Test initializing the RL environment."""
    env = RLEnvironment(
        demand_data=[10, 15, 20, 10, 5],
        holding_cost=5.0,
        stockout_penalty=100.0,
        max_order=50
    )
    assert env.max_order == 50
    assert env.holding_cost == 5.0
    
    # Check reset
    state = env.reset()
    assert len(state) == 2  # [day, inventory]
    assert state[0] == 0
    assert state[1] == 0

def test_rl_environment_step():
    """Test stepping through the RL environment."""
    env = RLEnvironment(
        demand_data=[10, 15],
        holding_cost=5.0,
        stockout_penalty=100.0,
        max_order=50
    )
    env.reset()
    
    # Action: Order 20 units
    next_state, reward, done, info = env.step(action=20)
    
    # Demand is 10, we ordered 20. Inventory becomes 10.
    assert next_state[1] == 10
    # Cost = 10 * 5.0 (holding) + 0 (stockout) = 50
    # Reward = -50
    assert reward == -50
    assert not done

def test_dqn_agent():
    """Test DQN Agent basic operations."""
    agent = DQNAgent(state_size=2, action_size=51, hidden_size=64)
    
    # Test action selection (random since epsilon is 1.0)
    state = np.array([0, 0])
    action = agent.act(state)
    assert 0 <= action <= 50
    
    # Test memory and replay
    next_state = np.array([1, 10])
    agent.remember(state, action, -50, next_state, False)
    assert len(agent.memory) == 1
    
    # Won't replay if batch_size > memory
    agent.replay(batch_size=32)

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
        # Fake loading model
        pass

    monkeypatch.setattr(Session, "query", mock_query)
    monkeypatch.setattr("torch.load", mock_load)
    monkeypatch.setattr(DQNAgent, "load", lambda x, y: None)
    
    sim = DeploymentSimulator(run_id=1, demand_data=[10, 20, 30])
    
    assert sim.run_id == 1
    assert sim.sku == "TEST-SKU"
    assert sim.total_days == 3
    assert sim.current_day == 0
    assert sim.inventory == 0

    # Step simulation without model (using mock act)
    monkeypatch.setattr(sim.agent, "act", lambda x: 15)
    
    state = sim.step()
    # Day 0: Demand 10, Action 15 -> Inventory 5
    assert state.day == 0
    assert state.demand == 10
    assert state.inventory == 5
    assert sim.current_day == 1
