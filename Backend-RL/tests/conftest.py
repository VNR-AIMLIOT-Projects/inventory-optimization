import os
import pytest
import sys

# Ensure src is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

os.environ["TEST_DISABLE_AUTH"] = "1"
os.environ["RATE_LIMIT_PER_MINUTE"] = "10000"
os.environ["API_KEY"] = "test-secret-key"

# Load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass

# Verify if we have a real key or need a dummy one
groq_key = os.environ.get("GROQ_API_KEY", "")
if not groq_key or groq_key == "test_groq_api_key_for_testing":
    print("\nWARNING: Real GROQ_API_KEY not found in environment. Using dummy key which will cause 401 errors during tests!")
    os.environ["GROQ_API_KEY"] = "test_groq_api_key_for_testing"
else:
    print("\nSUCCESS: GROQ_API_KEY found in environment.")

if not os.environ.get("RESEND_API_KEY"):
    os.environ["RESEND_API_KEY"] = "test_resend_api_key_for_testing"
if not os.environ.get("SESSION_SECRET"):
    os.environ["SESSION_SECRET"] = "test_session_secret"

from core.database import Base, engine

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all database tables before running tests."""
    # Initialize FastAPI cache with a DummyBackend to disable caching during tests
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends import Backend
    from typing import Tuple, Optional
    class DummyBackend(Backend):
        async def get_with_ttl(self, key: str) -> Tuple[int, Optional[bytes]]: return 0, None
        async def get(self, key: str) -> Optional[bytes]: return None
        async def set(self, key: str, value: bytes, expire: Optional[int] = None) -> None: pass
        async def clear(self, namespace: Optional[str] = None, key: Optional[str] = None) -> int: return 0
    FastAPICache.init(DummyBackend())
    
    # Ensure the storage directory exists if using sqlite
    db_url = os.environ.get("DATABASE_URL", "")
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "")
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    
    # Create the tables
    Base.metadata.create_all(bind=engine)
    
    yield
    
    # Optional: drop tables after tests, but for sqlite we might just delete the file
    # Base.metadata.drop_all(bind=engine)
