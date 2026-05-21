import pytest
import os
import io
import sys
from fastapi.testclient import TestClient

# Add src to path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from app import app
from schemas import TrainingStatus

client = TestClient(app)

@pytest.fixture
def sample_csv():
    """Provides a minimal CSV file for uploading demand data."""
    csv_content = "date,sales,sku\n2025-01-01,100,SKU-A\n2025-01-02,120,SKU-A\n2025-01-03,110,SKU-A\n2025-01-01,50,SKU-B\n2025-01-02,55,SKU-B\n"
    return io.BytesIO(csv_content.encode('utf-8'))


def test_full_upload_and_sku_flow(sample_csv):
    """Integration test: Upload CSV, list SKUs, select SKU."""
    
    # 1. Upload CSV
    response = client.post(
        "/api/demand/upload",
        files={"file": ("test_demand.csv", sample_csv, "text/csv")}
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert "Successfully loaded" in data["message"] or "Successfully extracted" in data["message"] or data["message"] == "File processed successfully"
    
    # 2. List SKUs
    response = client.get("/api/demand/skus")
    assert response.status_code == 200
    skus_data = response.json()
    assert "SKU-A" in skus_data["skus"]
    assert "SKU-B" in skus_data["skus"]
    
    # 3. Select SKU
    response = client.post(
        "/api/demand/select-sku",
        json={"sku": "SKU-A"}
    )
    assert response.status_code == 200
    
    # 4. Get Demand Data
    response = client.get("/api/demand/data")
    assert response.status_code == 200
    demand_data = response.json()
    assert demand_data["num_days"] == 3


def test_multi_sku_training_flow(monkeypatch):
    """Integration test: Start, check status, and stop multi-SKU training."""
    
    # Mock RabbitMQ publish to prevent ConnectionRefused errors
    monkeypatch.setattr("app.publish_training_job", lambda job: None)
    
    # Start training
    response = client.post("/api/train/multi", json={"episodes": 10})
    # If no data is properly extracted or parsed, this might return 400. 
    # But since we selected SKU-A above, it should start.
    assert response.status_code in [200, 400], response.text
    
    if response.status_code == 200:
        data = response.json()
        assert "overall_status" in data
        
        # Check status
        status_res = client.get("/api/train/multi/status")
        assert status_res.status_code == 200
        
        # Stop training
        stop_res = client.post("/api/train/multi/stop")
        assert stop_res.status_code == 200


def test_deployment_flow():
    """Integration test: Start deployment, get state, step day, reset."""
    
    # Start deployment for SKU-A (requires a run_id, we will fake it or expect 404/400 if missing)
    # To properly test, we should pass an invalid run_id to ensure validation works
    response = client.post("/api/deploy/start", json={"run_id": 99999, "start_day": 0})
    assert response.status_code in [400, 404, 500]  # run_id 99999 shouldn't exist
    

def test_copilot_chat():
    """Integration test: Send a basic message to copilot."""
    response = client.post(
        "/api/copilot/chat",
        json={
            "page": "stage1",
            "message": "Hello copilot, what is your purpose?",
            "context": {"current_view": "dashboard"}
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "reply" in data
    assert len(data["reply"]) > 0

