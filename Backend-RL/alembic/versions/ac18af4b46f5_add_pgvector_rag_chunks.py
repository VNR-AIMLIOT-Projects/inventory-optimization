"""add_pgvector_rag_chunks

Revision ID: ac18af4b46f5
Revises: 815259f84a29
Create Date: 2026-06-27 00:09:35.272978
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac18af4b46f5'
down_revision: Union[str, None] = '815259f84a29'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable pgvector
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    # 2. Create the table
    op.execute("""
        CREATE TABLE IF NOT EXISTS rag_chunks (
            id SERIAL PRIMARY KEY,
            source_table VARCHAR NOT NULL,
            source_id INTEGER NOT NULL,
            stage VARCHAR NOT NULL,
            sku VARCHAR,
            run_id INTEGER,
            session_id VARCHAR,
            chunk_text TEXT NOT NULL,
            embedding VECTOR(768),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(source_table, source_id)
        );
    """)
    
    # 3. Create HNSW index for vector similarity search
    op.execute("""
        CREATE INDEX IF NOT EXISTS rag_chunks_embedding_idx 
        ON rag_chunks 
        USING hnsw (embedding vector_cosine_ops) 
        WITH (m = 16, ef_construction = 64);
    """)
    
    # 4. Create indexes for metadata pre-filtering
    op.create_index('ix_rag_chunks_stage', 'rag_chunks', ['stage'])
    op.create_index('ix_rag_chunks_sku', 'rag_chunks', ['sku'])
    op.create_index('ix_rag_chunks_run_id', 'rag_chunks', ['run_id'])


def downgrade() -> None:
    op.drop_index('ix_rag_chunks_run_id', table_name='rag_chunks')
    op.drop_index('ix_rag_chunks_sku', table_name='rag_chunks')
    op.drop_index('ix_rag_chunks_stage', table_name='rag_chunks')
    
    op.execute("DROP INDEX IF EXISTS rag_chunks_embedding_idx;")
    op.execute("DROP TABLE IF EXISTS rag_chunks;")
    # Note: we generally leave the vector extension enabled in downgrade 
    # as other tables might use it in the future.
