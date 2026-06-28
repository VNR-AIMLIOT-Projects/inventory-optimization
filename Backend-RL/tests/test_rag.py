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
        return [0.1, 0.2, 0.3]

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
    assert len(vec) == 3
    assert vec == [0.1, 0.2, 0.3]

def test_upsert_chunk(mock_db, mock_sentence_transformer):
    import services.rag.embedding_service
    services.rag.embedding_service._model = None
    upsert_chunk(mock_db, "table", 1, "train", "text")
    mock_db.execute.assert_called_once()
    mock_db.commit.assert_called_once()

def test_retrieve(mock_db, mock_sentence_transformer):
    import services.rag.embedding_service
    services.rag.embedding_service._model = None
    
    # Mock db.execute().fetchall()
    mock_result = MagicMock()
    mock_row = MagicMock()
    mock_row.chunk_text = "test chunk"
    mock_row.similarity = 0.9
    mock_result.fetchall.return_value = [mock_row]
    mock_db.execute.return_value = mock_result
    
    results = retrieve(mock_db, "query", stage="train", sku="sku1", top_k=2, min_similarity=0.5)
    
    assert len(results) == 1
    assert results[0] == "test chunk"
    mock_db.execute.assert_called_once()

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
