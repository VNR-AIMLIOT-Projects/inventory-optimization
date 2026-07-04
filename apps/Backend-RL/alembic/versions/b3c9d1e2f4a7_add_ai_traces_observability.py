"""add_ai_traces_observability

Revision ID: b3c9d1e2f4a7
Revises: ac18af4b46f5
Create Date: 2026-07-02 00:00:00.000000

Adds the ai_traces table for end-to-end AI observability.
Every chatbot request produces one trace row that is scored
asynchronously by the eval engine.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision: str = 'b3c9d1e2f4a7'
down_revision: Union[str, None] = 'ac18af4b46f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    if conn.dialect.name == 'sqlite':
        # ── SQLite fallback for unit tests ────────────────────────────────
        op.execute("""
            CREATE TABLE IF NOT EXISTS ai_traces (
                trace_id        TEXT PRIMARY KEY,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                question        TEXT NOT NULL,
                retrieved_chunks TEXT,
                prompt_version  TEXT,
                llm_model       TEXT,
                answer          TEXT,
                retrieval_ms    INTEGER,
                llm_ms          INTEGER,
                total_ms        INTEGER,
                tokens_in       INTEGER,
                tokens_out      INTEGER,
                relevance_score REAL,
                groundedness_score REAL,
                hallucination_flag INTEGER DEFAULT 0,
                user_feedback   INTEGER,
                flagged_as_bad  INTEGER DEFAULT 0
            );
        """)
        return

    # ── Postgres ──────────────────────────────────────────────────────────
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_traces (
            trace_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            -- Request
            question            TEXT NOT NULL,
            retrieved_chunks    JSONB DEFAULT '[]'::jsonb,
            prompt_version      VARCHAR(64),
            llm_model           VARCHAR(64),

            -- Response
            answer              TEXT,

            -- Latency (ms)
            retrieval_ms        INTEGER,
            llm_ms              INTEGER,
            total_ms            INTEGER,

            -- Token costs
            tokens_in           INTEGER,
            tokens_out          INTEGER,

            -- Eval scores (written by background evaluator)
            relevance_score     FLOAT,
            groundedness_score  FLOAT,
            hallucination_flag  BOOLEAN NOT NULL DEFAULT FALSE,

            -- Human feedback: 1=👍, -1=👎, NULL=none
            user_feedback       SMALLINT,

            -- Triage
            flagged_as_bad      BOOLEAN NOT NULL DEFAULT FALSE
        );
    """)

    # Indexes for the observability dashboard queries
    op.create_index('ix_ai_traces_created_at',    'ai_traces', ['created_at'])
    op.create_index('ix_ai_traces_flagged_as_bad', 'ai_traces', ['flagged_as_bad'])
    op.create_index('ix_ai_traces_hallucination',  'ai_traces', ['hallucination_flag'])


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'sqlite':
        op.drop_index('ix_ai_traces_hallucination',  table_name='ai_traces')
        op.drop_index('ix_ai_traces_flagged_as_bad', table_name='ai_traces')
        op.drop_index('ix_ai_traces_created_at',     table_name='ai_traces')
    op.execute("DROP TABLE IF EXISTS ai_traces;")
