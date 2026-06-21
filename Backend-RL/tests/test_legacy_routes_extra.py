import pytest
from fastapi.testclient import TestClient
import pandas as pd
from unittest.mock import patch, MagicMock

import sys
import os
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
        "raw_df": pd.DataFrame({"demand": [10, 20], "date": ["2025-01-01", "2025-01-02"]}),
        "current_run_id": 1,
        "best_params": valid_params.copy(),
        "modifier": mock_modifier,
        "uploaded_filepath": "/tmp/test.csv",
        "detected_params": valid_params.copy(),
        "train_status": {"status": TrainingStatus.RUNNING},
        "per_sku_modified_params": {},
        "per_sku_detected_params": {},
        "per_sku_modifiers": {},
        "per_sku_raw_dfs": {},
        "modified_params": valid_params.copy(),
        "all_skus_data": {"TEST-SKU": pd.DataFrame({"demand": [10, 20], "date": ["2025-01-01", "2025-01-02"]})}
    }
    
    original_store = api.routers.legacy_routes._store.copy()
    api.routers.legacy_routes._store.clear()
    api.routers.legacy_routes._store.update(store_data)
    
    yield api.routers.legacy_routes._store
    
    api.routers.legacy_routes._store.clear()
    api.routers.legacy_routes._store.update(original_store)

def test_list_skus_in_file(mock_store):
    with patch("os.path.exists", return_value=True):
        with patch("pandas.read_csv") as mock_read:
            mock_read.return_value = pd.DataFrame({"sku": ["TEST-SKU", "OTHER-SKU"]})
            response = client.get("/api/demand/skus")
            assert response.status_code == 200

def test_select_sku(mock_store):
    with patch("os.path.exists", return_value=True):
        with patch("api.routers.legacy_routes.load_and_process_data") as mock_load:
            mock_load.return_value = pd.DataFrame({"demand": [10, 20], "Date": pd.to_datetime(["2025-01-01", "2025-01-02"])})
            with patch("api.routers.legacy_routes.detect_demand_parameters") as mock_detect:
                mock_detect.return_value = {
                    "seasonality": 7, "trend": "linear", "noise": 0.1, "base_demand": 10,
                    "detected_season_type": "additive", "baseline": {"start": 10, "min": 5, "max": 15, "sigma": 1.0},
                    "seasonal": {"peak": 20, "periods": [], "num_seasons": 0},
                    "festival": {"peak": 50, "periods": [], "num_festivals": 0}, "num_days": 10
                }
                response = client.post("/api/demand/select-sku?sku=TEST-SKU")
                assert response.status_code == 200

def test_get_current_demand(mock_store):
    response = client.get("/api/demand/data")
    assert response.status_code == 200
    data = response.json()
    assert "dates" in data
    assert "demand" in data

def test_get_detected_parameters(mock_store):
    response = client.get("/api/demand/parameters")
    assert response.status_code == 200

def test_reset_parameters(mock_store):
    with patch("api.routers.legacy_routes.regenerate_demand_from_params") as mock_regen:
        mock_regen.return_value = pd.DataFrame({
            "date": ["2025-01-01"],
            "demand": [10],
            "day_of_week": [2],
            "promo_flag": [0]
        })
        response = client.post("/api/demand/parameters/reset")
        assert response.status_code == 200

def test_stop_training(mock_store, mock_db_session):
    response = client.post("/api/train/stop")
    assert response.status_code == 200

def test_list_training_runs(mock_db_session):
    mock_run = MagicMock()
    mock_run.id = 1
    mock_run.sku = "TEST"
    mock_db_session.query().order_by().all.return_value = [mock_run]
    
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert len(response.json()) > 0

def test_get_training_run(mock_db_session):
    mock_run = MagicMock()
    mock_run.id = 1
    mock_run.sku = "TEST"
    mock_db_session.query().filter().first.return_value = mock_run
    
    response = client.get("/api/runs/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1

def test_get_current_loaded_run(mock_store, mock_db_session):
    mock_run = MagicMock()
    mock_run.id = 1
    mock_db_session.query().filter().first.return_value = mock_run
    
    response = client.get("/api/history/current-loaded-run")
    assert response.status_code == 200
    assert response.json()["id"] == 1

def test_list_uploads(mock_db_session):
    mock_upload = MagicMock()
    mock_upload.id = 1
    mock_db_session.query().order_by().all.return_value = [mock_upload]
    
    response = client.get("/api/uploads")
    assert response.status_code == 200
    assert len(response.json()) > 0
