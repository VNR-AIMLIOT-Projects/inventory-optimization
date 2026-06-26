import os
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger(__name__)

_model = None

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("Loading sentence-transformer model (nomic-embed-text-v1.5)...")
        # trust_remote_code=True is required for nomic-ai
        _model = SentenceTransformer("nomic-ai/nomic-embed-text-v1.5", trust_remote_code=True)
        logger.info("Model loaded successfully.")
    return _model

def embed_text(text: str, mode: str = "document") -> list[float]:
    """
    Embeds text using the nomic-embed-text-v1.5 model.
    mode must be either 'document' (for ingestion) or 'query' (for search).
    """
    model = get_model()
    prefix = "search_document: " if mode == "document" else "search_query: "
    full_text = prefix + text
    
    # encode() returns a numpy array, we convert to list for pgvector
    embedding = model.encode(full_text, normalize_embeddings=True)
    if hasattr(embedding, "tolist"):
        return embedding.tolist()
    return embedding

def upsert_chunk(db: Session, source_table: str, source_id: int,
                 stage: str, chunk_text: str, sku: str = None,
                 run_id: int = None, session_id: str = None):
    """
    Embeds the chunk_text and upserts it into the rag_chunks table.
    """
    try:
        vector = embed_text(chunk_text, mode="document")
        
        # We use SQLAlchemy's text parameter binding
        from sqlalchemy import text
        
        query = text("""
            INSERT INTO rag_chunks 
                (source_table, source_id, stage, sku, run_id, session_id, chunk_text, embedding)
            VALUES (:table, :sid, :stage, :sku, :run_id, :session_id, :text, :vec)
            ON CONFLICT (source_table, source_id) DO UPDATE
                SET chunk_text = EXCLUDED.chunk_text,
                    embedding   = EXCLUDED.embedding,
                    created_at  = NOW()
        """)
        
        db.execute(query, {
            "table": source_table, 
            "sid": source_id, 
            "stage": stage,
            "sku": sku, 
            "run_id": run_id, 
            "session_id": session_id,
            "text": chunk_text, 
            "vec": str(vector) # pgvector accepts string representation of list e.g. '[1,2,3]'
        })
        db.commit()
    except Exception as e:
        logger.error(f"Failed to upsert chunk for {source_table}:{source_id}: {e}")
        db.rollback()
