import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.rag.embedding_service import embed_text, upsert_chunk
from services.rag.retriever import retrieve
from services.rag.ingestors import chunk_training_run, chunk_eval_result, chunk_deployment_session
from services.rag.triggers import ingest_training_run, ingest_eval_result, ingest_deployment_session

class DummyModel:
    def encode(self, text, normalize_embeddings=True):
        return [0.1] * 768

@pytest.fixture
def mock_sentence_transformer():
    with patch("services.rag.embedding_service.SentenceTransformer") as mock:
        mock.return_value = DummyModel()
        yield mock

@pytest.fixture
def mock_db():
    db = MagicMock(spec=Session)
    return db

def test_embed_text(mock_sentence_transformer):
    import services.rag.embedding_service
    # Reset singleton if loaded
    services.rag.embedding_service._model = None
    vec = embed_text("hello", mode="document")
    assert isinstance(vec, list)
    assert len(vec) == 768
    assert vec == [0.1] * 768

def test_upsert_chunk(db_session, mock_sentence_transformer):
    import services.rag.embedding_service
    services.rag.embedding_service._model = None
    upsert_chunk(db_session, "test_table", 1, "train", "test chunk content")
    # Retrieve the inserted row
    res = db_session.execute(text("SELECT * FROM rag_chunks WHERE source_table='test_table'")).fetchone()
    assert res is not None
    assert res.chunk_text == "test chunk content"
    assert res.embedding is not None

def test_retrieve(db_session, mock_sentence_transformer):
    import services.rag.embedding_service
    services.rag.embedding_service._model = None
    
    # Clean table first
    db_session.execute(text("DELETE FROM rag_chunks"))
    db_session.commit()
    
    # Insert multiple chunks
    upsert_chunk(db_session, "test_table", 1, "train", "first test chunk")
    upsert_chunk(db_session, "test_table", 2, "train", "second test chunk")
    upsert_chunk(db_session, "test_table", 3, "deploy", "third test chunk")
    
    # Search within train stage
    results = retrieve(db_session, "query", stage="train", top_k=5, min_similarity=0.0)
    
    # We mocked sentence transformer to always return [0.1, 0.2, 0.3], 
    # so similarity will be exactly 1.0 (or very close). 
    assert len(results) == 2
    assert "first test chunk" in results
    assert "second test chunk" in results
    assert "third test chunk" not in results

def test_chunk_training_run():
    row = {
        "id": 1,
        "sku": "test_sku",
        "status": "success",
        "episodes": 100,
        "best_reward": -5.0,
        "final_avg_reward": -6.0,
        "holding_cost": 2.0,
        "stockout_penalty": 100.0,
        "completed_at": "2025-01-01"
    }
    chunk = chunk_training_run(row)
    assert "Training Run #1" in chunk
    assert "SKU: test_sku" in chunk
    assert "Episodes: 100" in chunk

def test_chunk_eval_result():
    row = {
        "sku": "test_sku",
        "training_run_id": 1,
        "rl_reward": -10.0,
        "oracle_reward": -5.0,
        "rule_reward": -20.0,
        "created_at": "2025-01-01"
    }
    chunk = chunk_eval_result(row)
    assert "Evaluation Result" in chunk
    assert "SKU: test_sku" in chunk
    assert "RL Efficiency: 200.0%" in chunk

def test_chunk_deployment_session():
    row = {
        "id": "uuid1",
        "sku": "test_sku",
        "run_id": 1,
        "status": "active",
        "current_day": 5,
        "initial_inventory": 100,
        "created_at": "2025-01-01"
    }
    chunk = chunk_deployment_session(row)
    assert "Deployment Session | ID: uuid1" in chunk
    assert "SKU: test_sku" in chunk
    assert "Current Day: 5" in chunk
