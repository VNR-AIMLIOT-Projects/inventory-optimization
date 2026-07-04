"""
AI Observability ORM model — ai_traces table.
Tracks every RAG chatbot request end-to-end: question, retrieved chunks,
LLM answer, latency breakdown, token costs, eval scores, and hallucination flags.
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column, String, Text, Float, Integer, Boolean, DateTime, JSON, SmallInteger
)
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base


class AITrace(Base):
    """
    Full observability trace for one AI chatbot request.

    Lifecycle:
      1. Created synchronously when the user's question is answered.
      2. Updated asynchronously by the eval engine (relevance, groundedness, flags).
    """
    __tablename__ = "ai_traces"

    # ── Identity ─────────────────────────────────────────────────────────────
    trace_id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # ── Request ───────────────────────────────────────────────────────────────
    question = Column(Text, nullable=False)
    retrieved_chunks = Column(JSON, default=list)   # [{text, source, similarity}]
    prompt_version = Column(String(64), nullable=True)  # sha256[:8] of system prompt
    llm_model = Column(String(64), nullable=True)        # e.g. "llama-3.3-70b-versatile"

    # ── Response ──────────────────────────────────────────────────────────────
    answer = Column(Text, nullable=True)

    # ── Latency (milliseconds) ────────────────────────────────────────────────
    retrieval_ms = Column(Integer, nullable=True)
    llm_ms = Column(Integer, nullable=True)
    total_ms = Column(Integer, nullable=True)

    # ── Token costs ───────────────────────────────────────────────────────────
    tokens_in = Column(Integer, nullable=True)
    tokens_out = Column(Integer, nullable=True)

    # ── Eval scores (written by background evaluator) ─────────────────────────
    relevance_score = Column(Float, nullable=True)       # 0-1: answer ↔ question cosine
    groundedness_score = Column(Float, nullable=True)    # 0-1: answer supported by chunks
    hallucination_flag = Column(Boolean, default=False)  # true if groundedness < 0.6

    # ── Human feedback ────────────────────────────────────────────────────────
    user_feedback = Column(SmallInteger, nullable=True)  # 1=👍, -1=👎, NULL=none

    # ── Triage ────────────────────────────────────────────────────────────────
    is_action = Column(Boolean, default=False)
    flagged_as_bad = Column(Boolean, default=False, index=True)
    # true when: relevance < 0.65 OR hallucination_flag = true OR user_feedback = -1

    def __repr__(self) -> str:
        return (
            f"<AITrace trace_id={self.trace_id} "
            f"relevance={self.relevance_score} "
            f"flagged={self.flagged_as_bad}>"
        )
