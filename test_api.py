from fastapi.testclient import TestClient
import sys
import os
sys.path.append(os.path.abspath("apps/Backend-RL/src"))

from main import app

client = TestClient(app)
try:
    response = client.get("/api/runs")
    print("Status:", response.status_code)
    print("Body:", response.text)
except Exception as e:
    import traceback
    traceback.print_exc()
