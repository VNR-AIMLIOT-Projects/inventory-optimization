from main import app
from fastapi.testclient import TestClient
import os
# Set dummy env vars for test if needed
os.environ["CORS_ORIGINS"] = "*"
os.environ["API_KEY"] = "test-secret-key"
os.environ["STORAGE_DIR"] = "./storage"
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["RABBITMQ_URL"] = "amqp://guest:guest@localhost:5672/"


client = TestClient(app)


def test_missing_api_key():
    os.environ["TEST_DISABLE_AUTH"] = "0"
    try:
        response = client.get("/api/demand/skus")  # An endpoint from legacy_routes
        assert response.status_code == 401
        assert "Missing API Key" in response.json()["detail"]
    finally:
        os.environ["TEST_DISABLE_AUTH"] = "1"


def test_invalid_api_key():
    os.environ["TEST_DISABLE_AUTH"] = "0"
    try:
        response = client.get("/api/demand/skus",
                              headers={"X-API-Key": "wrong-key"})
        assert response.status_code == 401
        assert "Invalid API Key" in response.json()["detail"]
    finally:
        os.environ["TEST_DISABLE_AUTH"] = "1"


def test_valid_api_key():
    os.environ["TEST_DISABLE_AUTH"] = "0"
    try:
        # Will return 400 because no file uploaded yet, but NOT 401
        response = client.get("/api/demand/skus",
                              headers={"X-API-Key": "test-secret-key"})
        assert response.status_code != 401
    finally:
        os.environ["TEST_DISABLE_AUTH"] = "1"


def test_rate_limiting():
    os.environ["RATE_LIMIT_PER_MINUTE"] = "100"
    # Clear state from previous tests
    from main import app
    for middleware in app.user_middleware:
        if hasattr(middleware.kwargs, 'requests_per_minute'):
            pass  # can't easily reach it if wrapped
    # Since we can't easily reach the middleware instance, let's just catch the 429 and break.
    # We want to ensure that EVENTUALLY it returns 429.
    hit_429 = False
    for i in range(105):
        response = client.get("/nonexistent-endpoint",
                              headers={"X-API-Key": "test-secret-key"})
        if response.status_code == 429:
            hit_429 = True
            break

    assert hit_429, "Did not hit rate limit"

    # The 101st request should be rate limited
    response = client.get("/nonexistent-endpoint",
                          headers={"X-API-Key": "test-secret-key"})
    assert response.status_code == 429
    assert response.json()["detail"] == "Too Many Requests"

    # Wait a bit (simulate if we want to reset), but we don't test reset here.
    os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
