import os
import requests
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

HF_API_KEY = os.getenv("HF_API_KEY")
HF_API_URL = "https://api-inference.huggingface.co/pipeline/feature-extraction/nomic-ai/nomic-embed-text-v1.5"

def embed_text(text: str, mode: str = "document") -> list[float]:
    """
    Embeds text using the nomic-embed-text-v1.5 model via Hugging Face API.
    mode must be either 'document' (for ingestion) or 'query' (for search).
    """
    prefix = "search_document: " if mode == "document" else "search_query: "
    full_text = prefix + text
    
    if not HF_API_KEY:
        logger.error("HF_API_KEY is missing! Cannot generate embeddings.")
        return []

    headers = {"Authorization": f"Bearer {HF_API_KEY}"}
    payload = {"inputs": [full_text], "options": {"wait_for_model": True}}

    try:
        response = requests.post(HF_API_URL, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        # Hugging Face Feature Extraction API returns a nested array for batches
        # e.g. [[[0.1, 0.2, ...]]]
        data = response.json()
        
        if isinstance(data, list) and len(data) > 0:
            embedding = data[0]
            # Some models return 3D list for feature extraction, Nomic might return 2D or 1D
            while isinstance(embedding, list) and len(embedding) > 0 and isinstance(embedding[0], list):
                embedding = embedding[0]
            return embedding
        return []
    except Exception as e:
        logger.error(f"Failed to get embeddings from Hugging Face API: {e}")
        return []

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
                    created_at  = CURRENT_TIMESTAMP
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
