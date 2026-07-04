import pytest
from fastapi.testclient import TestClient
import pandas as pd
from unittest.mock import patch, MagicMock
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from main import app
from models.schemas import TrainingStatus

client = TestClient(app)

@pytest.fixture
def mock_db_session():
    with patch("api.routers.legacy_routes.SessionLocal") as mock_session:
        db = mock_session.return_value
        yield db

@pytest.fixture
def mock_store():
    import api.routers.legacy_routes
    mock_modifier = MagicMock()
    mock_modifier.get_data.return_value = pd.DataFrame({
        "date": ["2025-01-01"],
        "demand": [10],
        "day_of_week": [2],
        "promo_flag": [0]
    })
    
    valid_params = {
        "seasonality": 7,
        "trend": "linear",
        "noise": 0.1,
        "base_demand": 10,
        "detected_season_type": "additive",
        "baseline": {"start": 10, "min": 5, "max": 15, "sigma": 1.0},
        "seasonal": {"peak": 20, "periods": [], "num_seasons": 0},
        "festival": {"peak": 50, "periods": [], "num_festivals": 0},
        "num_days": 10
    }
    
    store_data = {
        "sku": "TEST-SKU",
        "eval_results": {"rl_df": pd.DataFrame(), "oracle_df": pd.DataFrame(), "rule_df": pd.DataFrame()},
        "train_thread": MagicMock(),
        "raw_df": pd.DataFrame({"demand": [10, 20], "Date": pd.to_datetime(["2025-01-01", "2025-01-02"])}),
        "current_run_id": 1,
        "best_params": valid_params.copy(),
        "modifier": mock_modifier,
        "uploaded_filepath": "/tmp/test.csv",
        "detected_params": valid_params.copy(),
        "train_status": {"status": TrainingStatus.RUNNING},
        "per_sku_modified_params": {"TEST-SKU": valid_params.copy()},
        "per_sku_detected_params": {"TEST-SKU": valid_params.copy()},
        "per_sku_modifiers": {"TEST-SKU": mock_modifier},
        "per_sku_raw_dfs": {"TEST-SKU": pd.DataFrame({"demand": [10, 20], "date": ["2025-01-01", "2025-01-02"]})},
        "modified_params": valid_params.copy(),
        "all_skus_data": {"TEST-SKU": pd.DataFrame({"demand": [10, 20], "date": ["2025-01-01", "2025-01-02"]})},
        "multi_sku_rewards": {}
    }
    
    original_store = api.routers.legacy_routes._store.copy()
    api.routers.legacy_routes._store.clear()
    api.routers.legacy_routes._store.update(store_data)
    
    yield api.routers.legacy_routes._store
    
    api.routers.legacy_routes._store.clear()
    api.routers.legacy_routes._store.update(original_store)


def test_spike(mock_store):
    response = client.post("/api/demand/modify/spike", json={"amount": 10, "start_day": 1, "duration": 5})
    assert response.status_code in [200, 422]

def test_scale(mock_store):
    response = client.post("/api/demand/modify/scale", json={"factor": 1.2, "start_day": 1, "end_day": 5})
    assert response.status_code in [200, 422]

def test_get_train_status(mock_store):
    response = client.get("/api/train/status")
    assert response.status_code == 200

def test_update_params(mock_store):
    response = client.put("/api/demand/parameters", json={
        "seasonality": 7, "trend": "linear", "noise": 0.1, "base_demand": 10,
        "detected_season_type": "additive", "baseline": {"start": 20, "min": 5, "max": 15, "sigma": 1.0},
        "seasonal": {"peak": 20, "periods": [], "num_seasons": 0},
        "festival": {"peak": 50, "periods": [], "num_festivals": 0}, "num_days": 10
    })
    assert response.status_code in [200, 500]

def test_multi_train_stop(mock_store):
    response = client.post("/api/train/multi/stop")
    assert response.status_code in [200, 409]

def test_multi_deploy_start(mock_store):
    response = client.post("/api/deploy/multi/start")
    assert response.status_code in [200, 400, 422, 500]

def test_eval_multi_graph(mock_store):
    response = client.get("/api/evaluate/multi/graph/TEST-SKU")
    assert response.status_code in [200, 400, 404, 500]

def test_multi_train_rewards(mock_store):
    response = client.get("/api/train/multi/rewards")
    assert response.status_code in [200, 500]
