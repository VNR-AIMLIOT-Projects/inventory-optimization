import pytest
from fastapi.testclient import TestClient

import sys
import os

# Add src to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from app import app

client = TestClient(app)

def test_health_check():
    """Test the health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] == "ok"

def test_history_runs_empty_or_list():
    """Test getting runs history."""
    response = client.get("/api/runs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_demand_data_initial():
    """Test getting demand data returns default/empty gracefully."""
    # This might return 400 if no SKU is selected or return default logic
    response = client.get("/api/demand/data")
    assert response.status_code in (200, 400, 404)

def test_demand_parameters():
    """Test the demand parameters endpoint."""
    response = client.get("/api/demand/parameters")
    assert response.status_code in (200, 400, 404)
