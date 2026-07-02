"""
AI Observability Service
========================
Handles the two core responsibilities of the observability layer:

1. **Tracing** — emit a full trace row to ai_traces for every chatbot request.
2. **Evaluation** — score each trace asynchronously (relevance, groundedness,
   hallucination detection) and update the row + set flagged_as_bad.

Design notes:
- Uses the existing Groq/Llama setup (GROQ_API_KEY env var) for consistency.
- Embedding reuses the existing embedding_service for cosine similarity scoring.
- All DB writes use the existing SQLAlchemy session pattern.
- The evaluator runs as a FastAPI BackgroundTask (zero extra infrastructure).
"""

import uuid
import hashlib
import logging
import time
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Thresholds — tune these over time as you accumulate data
RELEVANCE_BAD_THRESHOLD = 0.65      # below this → flagged
GROUNDEDNESS_BAD_THRESHOLD = 0.60   # below this → hallucination_flag = True


# ─────────────────────────────────────────────────────────────────────────────
# Prompt version pinning
# ─────────────────────────────────────────────────────────────────────────────

def compute_prompt_version(system_prompt: str) -> str:
    """Return the first 8 hex chars of the SHA-256 of the system prompt."""
    return hashlib.sha256(system_prompt.encode()).hexdigest()[:8]


# ─────────────────────────────────────────────────────────────────────────────
# Tracer — write a new trace row
# ─────────────────────────────────────────────────────────────────────────────

def emit_trace(
    db: Session,
    *,
    question: str,
    retrieved_chunks: list[dict],   # [{text, source, similarity}]
    prompt_version: str,
    llm_model: str,
    answer: str,
    retrieval_ms: int,
    llm_ms: int,
    total_ms: int,
    tokens_in: int,
    tokens_out: int,
) -> str:
    """
    Persist a new trace row.
    Returns the trace_id (UUID str) so the caller can reference it.
    Eval scores are written later by evaluate_trace().
    """
    from models.ai_observability import AITrace  # local import to avoid circular deps

    trace_id = uuid.uuid4()
    trace = AITrace(
        trace_id=trace_id,
        created_at=datetime.utcnow(),
        question=question,
        retrieved_chunks=retrieved_chunks,
        prompt_version=prompt_version,
        llm_model=llm_model,
        answer=answer,
        retrieval_ms=retrieval_ms,
        llm_ms=llm_ms,
        total_ms=total_ms,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        # eval fields filled later
        hallucination_flag=False,
        flagged_as_bad=False,
    )
    try:
        db.add(trace)
        db.commit()
        logger.info(f"[Observability] Trace emitted: {trace_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"[Observability] Failed to emit trace {trace_id}: {e}")

    return str(trace_id)


# ─────────────────────────────────────────────────────────────────────────────
# Evaluator — score a trace after the response is sent
# ─────────────────────────────────────────────────────────────────────────────

def _cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Fast cosine similarity without numpy dependency."""
    import math
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def _score_relevance(question: str, answer: str) -> float:
    """
    Relevance = cosine similarity between embeddings of question and answer.
    Uses the existing embedding_service — same model as RAG retrieval.
    """
    try:
        from services.rag.embedding_service import embed_text
        q_vec = embed_text(question, mode="query")
        a_vec = embed_text(answer, mode="passage")
        score = _cosine_similarity(q_vec, a_vec)
        return round(max(0.0, min(1.0, score)), 4)
    except Exception as e:
        logger.warning(f"[Eval] Relevance scoring failed: {e}")
        return 0.0


def _score_groundedness(answer: str, chunks: list[dict]) -> float:
    """
    Groundedness = fraction of answer tokens that appear in at least one chunk.
    A simple but fast lexical overlap heuristic (no extra API calls).
    """
    if not chunks or not answer:
        return 0.0
    try:
        chunk_text = " ".join(c.get("text", "") for c in chunks).lower()
        chunk_tokens = set(chunk_text.split())
        answer_tokens = [t for t in answer.lower().split() if len(t) > 3]
        if not answer_tokens:
            return 0.5  # short answers get benefit of doubt
        overlap = sum(1 for t in answer_tokens if t in chunk_tokens)
        return round(overlap / len(answer_tokens), 4)
    except Exception as e:
        logger.warning(f"[Eval] Groundedness scoring failed: {e}")
        return 0.0


def evaluate_trace(db: Session, trace_id: str) -> None:
    """
    Background eval job: score the trace and update flagged_as_bad.
    Called as a FastAPI BackgroundTask — runs after response is sent to user.
    """
    from models.ai_observability import AITrace  # local import

    try:
        trace = db.query(AITrace).filter(
            AITrace.trace_id == uuid.UUID(trace_id)
        ).first()

        if not trace:
            logger.warning(f"[Eval] Trace {trace_id} not found — skipping eval.")
            return

        question = trace.question or ""
        answer = trace.answer or ""
        chunks = trace.retrieved_chunks or []

        # Score
        relevance = _score_relevance(question, answer)
        groundedness = _score_groundedness(answer, chunks)
        hallucination = groundedness < GROUNDEDNESS_BAD_THRESHOLD

        # Triage: bad if relevance low OR hallucination detected OR user disliked it
        flagged = (
            relevance < RELEVANCE_BAD_THRESHOLD
            or hallucination
            or trace.user_feedback == -1
        )

        # Persist
        trace.relevance_score = relevance
        trace.groundedness_score = groundedness
        trace.hallucination_flag = hallucination
        trace.flagged_as_bad = flagged
        db.commit()

        logger.info(
            f"[Eval] Trace {trace_id}: "
            f"relevance={relevance:.3f} groundedness={groundedness:.3f} "
            f"hallucination={hallucination} flagged={flagged}"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"[Eval] evaluate_trace failed for {trace_id}: {e}")


def update_feedback(db: Session, trace_id: str, feedback: int) -> bool:
    """
    Apply operator feedback (1=👍, -1=👎) and re-evaluate bad flag.
    Returns True on success.
    """
    from models.ai_observability import AITrace

    try:
        trace = db.query(AITrace).filter(
            AITrace.trace_id == uuid.UUID(trace_id)
        ).first()
        if not trace:
            return False

        trace.user_feedback = feedback
        # Re-evaluate bad flag with new feedback
        trace.flagged_as_bad = (
            (trace.relevance_score or 1.0) < RELEVANCE_BAD_THRESHOLD
            or bool(trace.hallucination_flag)
            or feedback == -1
        )
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        logger.error(f"[Eval] update_feedback failed for {trace_id}: {e}")
        return False
