import pytest
import pandas as pd
from unittest.mock import MagicMock
from rl.deployment_simulator import (
    DeploymentSimulator,
    DeploymentSessionManager,
    MultiSkuDeploymentOrchestrator,
    get_deployment_manager,
    get_multi_sku_orchestrator,
    set_multi_sku_orchestrator
)
from rl.dqn import DQNAgent

@pytest.fixture
def dummy_agent():
    agent = DQNAgent(state_size=15, action_size=6)
    # mock the act method
    agent.act = MagicMock(return_value=2)  # returns index 2 for action
    return agent

@pytest.fixture
def dummy_demand_df():
    return pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04"],
        "demand": [10, 15, 5, 20],
        "day_of_week": [2, 3, 4, 5],
        "promo_flag": [0, 0, 0, 1]
    })

def test_deployment_simulator_init(dummy_agent, dummy_demand_df):
    sim = DeploymentSimulator(
        session_id="test-session",
        sku="SKU-TEST",
        agent=dummy_agent,
        demand_df=dummy_demand_df,
        max_order=50,
        action_step=10,
        start_day=0
    )
    assert sim.session_id == "test-session"
    assert sim.sku == "SKU-TEST"
    assert sim.total_days == 4
    assert sim.current_day == 0

def test_deployment_simulator_step(dummy_agent, dummy_demand_df):
    sim = DeploymentSimulator(
        session_id="test-session",
        sku="SKU-TEST",
        agent=dummy_agent,
        demand_df=dummy_demand_df,
        max_order=50,
        action_step=10,
        start_day=0
    )
    
    # Check predictions
    pred = sim.get_next_prediction()
    assert pred is not None
    assert pred["day"] == 0
    assert pred["rl_action"] == 20  # because index 2 * 10 = 20
    
    # Step
    day_state = sim.step()
    assert day_state["day"] == 0
    assert day_state["rl_action"] == 20
    assert sim.current_day == 1

def test_deployment_simulator_override(dummy_agent, dummy_demand_df):
    sim = DeploymentSimulator(
        session_id="test-session",
        sku="SKU-TEST",
        agent=dummy_agent,
        demand_df=dummy_demand_df,
        max_order=50,
        action_step=10,
        start_day=0
    )
    
    # set override for day 1
    sim.set_override(1, 30)
    assert sim.get_override(1) == 30
    
    # Day 0 step
    sim.step()
    
    # Day 1 prediction and step
    pred = sim.get_next_prediction()
    assert pred["has_override"] is True
    assert pred["override_qty"] == 30
    
    state1 = sim.step()
    assert state1["human_action"] == 30
    assert state1["final_action"] == 30
    
    # remove override (would raise error if stepping past, but removing is fine)
    sim.remove_override(1)
    
    # test error on past override
    with pytest.raises(ValueError):
        sim.set_override(0, 10)

    # test error on beyond end override
    with pytest.raises(ValueError):
        sim.set_override(5, 10)

def test_deployment_simulator_metrics(dummy_agent, dummy_demand_df):
    sim = DeploymentSimulator(
        session_id="test-session",
        sku="SKU-TEST",
        agent=dummy_agent,
        demand_df=dummy_demand_df,
        max_order=50,
        action_step=10,
        start_day=0
    )
    
    sim.run_all()
    metrics = sim.compute_metrics()
    assert metrics["current_day"] == 4
    assert metrics["total_days"] == 4
    assert "total_revenue" in metrics
    assert "total_cost" in metrics

def test_deployment_session_manager(dummy_agent, dummy_demand_df):
    mgr = DeploymentSessionManager()
    session_id = mgr.create_session(
        sku="SKU-MGR",
        agent=dummy_agent,
        demand_df=dummy_demand_df,
        max_order=50,
        action_step=10
    )
    assert session_id in mgr.sessions
    
    sim = mgr.get_session(session_id)
    assert sim is not None
    assert sim.sku == "SKU-MGR"
    
    mgr.delete_session(session_id)
    assert mgr.get_session(session_id) is None

def test_multi_sku_orchestrator(dummy_agent, dummy_demand_df):
    orch = MultiSkuDeploymentOrchestrator()
    orch.add_sku("SKU-1", dummy_agent, dummy_demand_df, 50, 10)
    orch.add_sku("SKU-2", dummy_agent, dummy_demand_df, 50, 10)
    
    assert len(orch.skus) == 2
    
    states = orch.get_all_states()
    assert "SKU-1" in states
    assert "SKU-2" in states
    
    orch.set_override("SKU-1", 1, 40)
    
    res = orch.step_all()
    assert res["SKU-1"]["day"] == 0
    assert res["SKU-2"]["day"] == 0
    
    res = orch.step_sku("SKU-1")
    assert res["day"] == 1
    assert res["final_action"] == 40
    
    summary = orch.get_sku_summary()
    assert "SKU-1" in summary
    assert "SKU-2" in summary
    
    agg_metrics = orch.get_aggregate_metrics()
    assert "total_revenue" in agg_metrics
    assert agg_metrics["sku_count"] == 2
    
    orch.reset_all()
    assert orch.simulators["SKU-1"].current_day == 0
    
    orch.remove_override("SKU-1", 1)
    
    orch.remove_sku("SKU-1")
    assert len(orch.skus) == 1
    
    with pytest.raises(ValueError):
        orch.remove_sku("NON_EXISTENT")

def test_globals():
    mgr = get_deployment_manager()
    assert isinstance(mgr, DeploymentSessionManager)
    
    orch = MultiSkuDeploymentOrchestrator()
    set_multi_sku_orchestrator(orch)
    assert get_multi_sku_orchestrator() is orch

def test_sim_empty_metrics(dummy_agent, dummy_demand_df):
    sim = DeploymentSimulator(
        session_id="test", sku="SKU", agent=dummy_agent, demand_df=dummy_demand_df, max_order=50, action_step=10
    )
    m = sim.compute_metrics()
    assert m["current_day"] == 0
    assert m["cumulative_reward"] == 0.0

def test_get_full_state(dummy_agent, dummy_demand_df):
    sim = DeploymentSimulator(
        session_id="test", sku="SKU", agent=dummy_agent, demand_df=dummy_demand_df, max_order=50, action_step=10
    )
    st = sim.get_full_state()
    assert st["session_id"] == "test"
    assert st["current_day"] == 0
    assert st["metrics"]["total_days"] == 4
    assert st["next_prediction"]["rl_action"] == 20
