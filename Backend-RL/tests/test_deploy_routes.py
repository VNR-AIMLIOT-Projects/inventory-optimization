import pytest
from fastapi.testclient import TestClient
import sys
import os
import pandas as pd
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from main import app
from rl.dqn import DQNAgent

client = TestClient(app)

@pytest.fixture
def mock_store():
    agent = DQNAgent(state_size=15, action_size=6)
    
    with patch("api.routers.legacy_routes._store") as store:
        store.get.side_effect = lambda key, default=None: {
            "sku": "SKU-A",
            "trained_agent": agent,
            "train_max_order": 50,
            "train_action_step": 10,
            "train_holding_cost": 5,
            "train_stockout_penalty": 100,
            "current_run_id": 1,
            "modifier": MagicMock(get_data=lambda: pd.DataFrame({
                "date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"],
                "demand": [10, 15, 20, 10, 5],
                "day_of_week": [2, 3, 4, 5, 6],
                "promo_flag": [0, 0, 1, 0, 0]
            })),
            "raw_df": pd.DataFrame({
                "date": ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"],
                "demand": [10, 15, 20, 10, 5],
                "day_of_week": [2, 3, 4, 5, 6],
                "promo_flag": [0, 0, 1, 0, 0]
            })
        }.get(key, default)
        
        # Make the dict itself behave like our mocked get
        store.__getitem__.side_effect = lambda key: store.get(key)
        store.__setitem__.side_effect = lambda key, val: None
        
        yield store

def test_evaluate_endpoint(mock_store):
    with patch("api.routers.legacy_routes.evaluate_and_plot") as mock_eval:
        import pandas as pd
        mock_eval.return_value = (
            pd.DataFrame({"reward": [10]}),
            pd.DataFrame({"reward": [15]}),
            pd.DataFrame({"reward": [5]})
        )
        response = client.post("/api/evaluate")
        assert response.status_code == 200
        assert "rl_reward" in response.json()
        assert "oracle_reward" in response.json()

def test_evaluate_graph(mock_store):
    mock_store.get.side_effect = lambda key, default=None: None
    mock_store.__getitem__.side_effect = lambda key: None
    response = client.get("/api/evaluate/graph")
    assert response.status_code == 400 # Correct since it handles None

def test_evaluate_graph_real(mock_store):
    import pandas as pd
    mock_store.get.side_effect = lambda key, default=None: {
        "eval_results": {
            "rl_df": pd.DataFrame({"date": ["2025-01-01"], "inventory": [10], "action_order_qty": [10], "demand": [5], "reward": [10]}),
            "oracle_df": pd.DataFrame({"date": ["2025-01-01"], "inventory": [10], "action_order_qty": [10], "demand": [5], "reward": [15]}),
            "rule_df": pd.DataFrame({"date": ["2025-01-01"], "inventory": [10], "action_order_qty": [10], "demand": [5], "reward": [5]})
        }
    }.get(key, default)
    mock_store.__getitem__.side_effect = lambda key: mock_store.get(key)
    
    with patch("api.routers.legacy_routes._fig_to_base64", return_value="base64str"):
        response = client.get("/api/evaluate/graph")
        assert response.status_code == 200
        assert "image_base64" in response.json()

def test_start_deployment(mock_store):
    # Needs a DB record for the run if we want full integration, but we can mock it
    with patch("api.routers.legacy_routes.SessionLocal") as MockSession:
        mock_db = MockSession.return_value
        class MockRun:
            id = 1
            sku = "SKU-A"
            episodes = 50
            holding_cost = 5.0
            stockout_penalty = 100.0
            gamma = 0.98
            learning_rate = 0.001
            max_order = 50
            action_step = 10
            model_path = "dummy.pth"
            demand_params = {}
            status = "completed"
        
        mock_db.query().filter().first.return_value = MockRun()
        
        with patch("api.routers.legacy_routes.get_deployment_manager") as mock_get_mgr:
            mock_mgr = mock_get_mgr.return_value
            mock_mgr.create_session.return_value = "fake-session"
            
            mock_sim = mock_mgr.get_session.return_value
            mock_sim.session_id = "fake-session"
            mock_sim.total_days = 5
            mock_sim.current_day = 0
            mock_sim.sku = "SKU-A"
            mock_sim.max_order = 50
            mock_sim.action_step = 10
            mock_sim.holding_cost = 5.0
            mock_sim.stockout_penalty = 100.0
            
            mock_state = {
                "session_id": "fake-session", 
                "current_day": 0,
                "total_days": 5,
                "history": [], 
                "metrics": {
                    "current_day": 0,
                    "total_days": 5,
                    "cumulative_reward": 0,
                    "total_cost": 0,
                    "total_revenue": 0,
                    "stockout_days": 0,
                    "holding_cost_total": 0,
                    "stockout_penalty_total": 0,
                    "order_cost_total": 0,
                    "avg_inventory": 0
                },
                "next_prediction": {
                    "date": "2025-01-01",
                    "demand": 10,
                    "rl_action": 10
                }
            }
            mock_sim.get_full_state.return_value = mock_state
            mock_sim.get_metrics.return_value = mock_state["metrics"]
            mock_sim.compute_metrics.return_value = mock_state["metrics"]
            mock_sim.step.return_value = mock_state
            mock_sim.run_all.return_value = mock_state
            mock_sim.override_action.return_value = mock_state
            mock_sim.history = []
            
            # Use real app with mock db and sim
            response = client.post("/api/deploy/start", json={"run_id": 1, "start_day": 0})
            assert response.status_code == 200
            
            data = response.json()
            assert "session_id" in data
            session_id = data["session_id"]
            
            # Now state
            resp_state = client.get("/api/deploy/state")
            assert resp_state.status_code == 200
            
            # Step
            resp_step = client.post("/api/deploy/step")
            assert resp_step.status_code == 200
            
            # Override
            resp_override = client.post("/api/deploy/override", json={"day": 2, "override_qty": 30})
            assert resp_override.status_code == 200
            
            # Run all
            resp_run_all = client.post("/api/deploy/run-all")
            assert resp_run_all.status_code == 200
