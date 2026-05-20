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
