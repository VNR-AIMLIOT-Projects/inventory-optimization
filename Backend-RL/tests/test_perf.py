import time
import pytest
from fastapi.testclient import TestClient

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
from app import app

client = TestClient(app)

@pytest.mark.performance
def test_health_check_performance():
    """Ensure the health check responds under 50ms."""
    start_time = time.time()
    for _ in range(20):
        response = client.get("/api/health")
        assert response.status_code == 200
    duration = time.time() - start_time
    
    # average duration should be < 50ms per request (total < 1 second for 20)
    assert duration < 1.0, f"Health check too slow! Took {duration}s for 20 requests"


@pytest.mark.performance
def test_db_read_performance():
    """Ensure history endpoint reads fast under load."""
    start_time = time.time()
    for _ in range(50):
        response = client.get("/api/runs")
        assert response.status_code == 200
    duration = time.time() - start_time
    assert duration < 2.0, f"DB reads too slow! Took {duration}s for 50 requests"


@pytest.mark.performance
def test_concurrent_simulation_step_performance():
    """Ensure the deploy/step API handles load reasonably fast."""
    start_time = time.time()
    # Mocking or expecting 404 is fine, we just want to test endpoint overhead
    for _ in range(100):
        response = client.post("/api/deploy/start", json={"run_id": 99999, "start_day": 0})
        assert response.status_code in [400, 404, 500]
    duration = time.time() - start_time
    assert duration < 3.0, f"Simulation API too slow! Took {duration}s for 100 requests"
