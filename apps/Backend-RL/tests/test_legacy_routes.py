import pytest
from fastapi.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from main import app

client = TestClient(app)

def test_generate_and_modify_demand():
    # Generate demand
    response = client.post(
        "/api/demand/generate?season_type=summer&num_days=365&start_date=2025-01-01&seed=42"
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert data["data"]["num_days"] == 365
    
    # Check data retrieval
    response_data = client.get("/api/demand/data")
    assert response_data.status_code == 200
    assert response_data.json()["num_days"] == 365
    
    # Check modify spike
    spike_payload = {
        "date": "2025-01-02",
        "amount": 500
    }
    response_spike = client.post("/api/demand/modify/spike", json=spike_payload)
    assert response_spike.status_code == 200
    
    # Check scale
    scale_payload = {
        "start_date": "2025-01-05",
        "end_date": "2025-01-10",
        "factor": 1.5
    }
    response_scale = client.post("/api/demand/modify/scale", json=scale_payload)
    assert response_scale.status_code == 200
    
    # Check reset
    response_reset = client.post("/api/demand/modify/reset")
    assert response_reset.status_code == 200

def test_upload_demand_file(tmp_path):
    # Create a dummy CSV file
    csv_file = tmp_path / "dummy_demand.csv"
    csv_file.write_text("Date,SKU,Demand\n2025-01-01,SKU1,10\n2025-01-02,SKU1,20")
    
    with open(csv_file, "rb") as f:
        response = client.post("/api/demand/upload", files={"file": ("dummy_demand.csv", f, "text/csv")})
    
    assert response.status_code == 200
    
    # Test skus
    response_skus = client.get("/api/demand/skus")
    assert response_skus.status_code == 200
    assert "SKU1" in response_skus.json()["skus"]
    
    # Select sku
    response_select = client.post("/api/demand/select-sku?sku=SKU1")
    assert response_select.status_code == 200
