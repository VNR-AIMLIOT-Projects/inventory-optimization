import os
import pytest
import sys

# Ensure src is in the python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

# Set dummy environment variables for tests
os.environ["GROQ_API_KEY"] = "test_groq_api_key_for_testing"
os.environ["RESEND_API_KEY"] = "test_resend_api_key_for_testing"
os.environ["SESSION_SECRET"] = "test_session_secret"

from database import Base, engine

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Create all database tables before running tests."""
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
