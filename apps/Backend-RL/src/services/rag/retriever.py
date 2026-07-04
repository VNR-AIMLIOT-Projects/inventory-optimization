from sqlalchemy.orm import Session
from sqlalchemy import text
from .embedding_service import embed_text
import os
import logging

logger = logging.getLogger(__name__)

def retrieve(
    db: Session,
    query: str,
    stage: str = None,
    sku: str = None,
    top_k: int = None,
    min_similarity: float = None,
) -> list[str]:
    """
    Hybrid retrieval: metadata pre-filter → vector similarity search.
    Returns a list of chunk_text strings to inject into the agent prompt.
    """
    if top_k is None:
        top_k = int(os.environ.get("RAG_TOP_K", 4))
    if min_similarity is None:
        min_similarity = float(os.environ.get("RAG_MIN_SIMILARITY", 0.65))
        
    try:
        # Get query embedding
        query_vec = embed_text(query, mode="query")
        
        # Build SQL with optional pre-filters
        filters = []
        params = {"vec": str(query_vec), "top_k": top_k}
        
        if stage:
            filters.append("stage = :stage")
            params["stage"] = stage
            
        if sku:
            filters.append("(sku = :sku OR sku IS NULL)")
            params["sku"] = sku
            
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        
        query_sql = text(f"""
            SELECT chunk_text, 1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM rag_chunks
            {where_clause}
            ORDER BY embedding <=> CAST(:vec AS vector)
            LIMIT :top_k
        """)
        
        rows = db.execute(query_sql, params).fetchall()
        
        # Apply similarity threshold
        results = [row.chunk_text for row in rows if float(row.similarity) >= min_similarity]
        logger.info(f"RAG retrieved {len(results)} chunks for stage={stage}, sku={sku}")
        return results
        
    except Exception as e:
        logger.error(f"RAG retrieval failed: {e}")
        return []
