import pytest
import pandas as pd
import numpy as np
import os
from unittest.mock import patch, MagicMock
from rl.trainer import train_agent, _compute_adaptive_params, evaluate_and_plot, run_perfect_human_oracle_fixed, run_rule_baseline, train_and_evaluate_single_sku, train_all_skus_parallel

@pytest.fixture
def sample_env_data():
    return pd.DataFrame({
        "date": pd.date_range(start="2025-01-01", periods=10),
        "demand": [10, 15, 20, 25, 30, 35, 40, 45, 50, 55],
        "is_weekend": [0]*10,
        "is_holiday": [0]*10,
        "price": [100.0]*10,
        "day_of_week": [0]*10,
        "promo_flag": [0]*10,
        "weather_index": [1.0]*10
    })

def test_compute_adaptive_params(sample_env_data):
    max_order, action_step = _compute_adaptive_params(sample_env_data["demand"], lead_time=2)
    # The max demand is 55. Avg is 32.5. 32.5 * 3 = 97.5. Max is 97.
    assert max_order >= 55
    assert action_step >= 1
    
    # test overrides
    max_o, act_s = _compute_adaptive_params(sample_env_data["demand"], max_order_override=1000, action_step_override=10)
    assert max_o == 1000
    assert act_s == 10

@patch('rl.trainer.DQNAgent')
@patch('rl.trainer.InventoryEnvironment')
def test_train_agent_custom_df(mock_env_class, mock_agent_class, sample_env_data):
    # Setup mocks
    mock_env = MagicMock()
    mock_env.reset.return_value = np.zeros(5)
    mock_env.action_size = 5
    mock_env.step.return_value = (np.zeros(5), 10.0, True, {})
    mock_env_class.return_value = mock_env
    
    mock_agent = MagicMock()
    mock_agent.act.return_value = 1
    mock_agent.epsilon = 0.5
    mock_agent_class.return_value = mock_agent

    # Run training for 2 episodes
    agent, rewards, mo, a_s, hc, sp = train_agent(
        season_type="custom",
        episodes=2,
        custom_df=sample_env_data,
        decay_type="linear",
        on_episode=lambda info: True
    )

    assert len(rewards) == 2
    assert mo > 0
    assert a_s > 0

@patch('rl.trainer.DQNAgent')
@patch('rl.trainer.InventoryEnvironment')
@patch('data_processing.demand.generate_demand')
@patch('data_processing.demand.prepare_env_data')
def test_train_agent_generated_demand(mock_prep, mock_gen, mock_env_class, mock_agent_class, sample_env_data):
    mock_prep.return_value = sample_env_data
    mock_gen.return_value = sample_env_data
    
    mock_env = MagicMock()
    mock_env.reset.return_value = np.zeros(5)
    mock_env.action_size = 5
    mock_env.step.return_value = (np.zeros(5), 10.0, True, {})
    mock_env_class.return_value = mock_env
    
    mock_agent = MagicMock()
    mock_agent.act.return_value = 1
    mock_agent.epsilon = 0.5
    mock_agent_class.return_value = mock_agent

    agent, rewards, mo, a_s, hc, sp = train_agent(
        season_type="summer",
        episodes=2,
        decay_type="exponential",
        on_episode=lambda info: False # Stop early
    )
    
    assert len(rewards) == 1 # stopped early

@patch('matplotlib.pyplot.savefig')
def test_evaluate_and_plot(mock_savefig, sample_env_data):
    mock_agent = MagicMock()
    mock_agent.act.return_value = 0
    mock_agent.epsilon = 0.0

    rl_df, oracle_df, rule_df = evaluate_and_plot(
        agent=mock_agent,
        season_type="custom",
        custom_df=sample_env_data,
        output_dir="/tmp"
    )
    
    assert len(rl_df) > 0
    assert len(oracle_df) > 0
    assert len(rule_df) > 0
    mock_savefig.assert_called_once()

@patch('matplotlib.pyplot.savefig')
@patch('data_processing.demand.generate_demand')
@patch('data_processing.demand.prepare_env_data')
def test_evaluate_and_plot_generated(mock_prep, mock_gen, mock_savefig, sample_env_data):
    mock_prep.return_value = sample_env_data
    mock_gen.return_value = sample_env_data
    
    mock_agent = MagicMock()
    mock_agent.act.return_value = 0
    mock_agent.epsilon = 0.0

    rl_df, oracle_df, rule_df = evaluate_and_plot(
        agent=mock_agent,
        season_type="summer",
        output_dir="/tmp",
        max_order=100,
        action_step=5
    )
    
    assert len(rl_df) > 0

@patch('rl.trainer.train_agent')
@patch('rl.trainer.evaluate_and_plot')
def test_train_and_evaluate_single_sku(mock_eval, mock_train, sample_env_data):
    mock_agent = MagicMock()
    mock_train.return_value = (mock_agent, [100.0, 110.0], 100, 5, 5, 200)
    mock_eval.return_value = (
        pd.DataFrame([{"reward": 100}]), 
        pd.DataFrame([{"reward": 150}]), 
        pd.DataFrame([{"reward": 50}])
    )
    
    res = train_and_evaluate_single_sku("sku_A", sample_env_data, episodes=2)
    assert res["sku"] == "sku_A"
    assert res["rl_reward"] == 100
    assert res["oracle_reward"] == 150
    assert res["rule_reward"] == 50

@patch('rl.trainer.train_and_evaluate_single_sku')
def test_train_all_skus_parallel(mock_single, sample_env_data):
    mock_single.return_value = {"sku": "A", "rl_reward": 100, "oracle_reward": 150, "rule_reward": 50, "rl_vs_oracle_pct": 66.6}
    
    skus = {
        "A": sample_env_data,
        "B": sample_env_data
    }
    
    results = train_all_skus_parallel(skus, episodes=2, max_workers=2)
    assert len(results) == 2
    assert "A" in results
    assert "B" in results
    assert results["A"]["rl_reward"] == 100

def test_run_rule_baseline(sample_env_data):
    # Overriding to make sure we hit the else case
    reward, df = run_rule_baseline(sample_env_data, max_order_qty=1000, action_step=1)
    assert len(df) == 10

