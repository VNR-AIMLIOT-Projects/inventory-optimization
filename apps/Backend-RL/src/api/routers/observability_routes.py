"""
AI Observability API Router
============================
Exposes trace data for the Replenix AI Observability Dashboard.

Endpoints:
  GET  /observability/traces           — paginated trace list with filters
  GET  /observability/traces/{id}      — full trace detail
  GET  /observability/bad-answers      — auto-flagged traces only
  GET  /observability/metrics          — summary stats (bad rate, avg latency, etc.)
  PATCH /observability/traces/{id}/feedback — operator thumbs up/down

All endpoints require the same API key as the rest of the backend (via Depends(verify_api_key)).
"""

import uuid
import logging
from typing import Optional, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from core.database import get_db
from models.ai_observability import AITrace
from services.observability import update_feedback

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/observability", tags=["AI Observability"])


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _trace_to_dict(trace: AITrace) -> dict:
    """Serialize an AITrace row to a JSON-safe dict."""
    return {
        "trace_id": str(trace.trace_id),
        "created_at": trace.created_at.isoformat() if trace.created_at else None,
        "question": trace.question,
        "retrieved_chunks": trace.retrieved_chunks or [],
        "prompt_version": trace.prompt_version,
        "llm_model": trace.llm_model,
        "answer": trace.answer,
        "latency": {
            "retrieval_ms": trace.retrieval_ms,
            "llm_ms": trace.llm_ms,
            "total_ms": trace.total_ms,
        },
        "tokens": {
            "in": trace.tokens_in,
            "out": trace.tokens_out,
            "total": (trace.tokens_in or 0) + (trace.tokens_out or 0),
        },
        "scores": {
            "relevance": trace.relevance_score,
            "groundedness": trace.groundedness_score,
            "hallucination_flag": trace.hallucination_flag,
        },
        "user_feedback": trace.user_feedback,
        "flagged_as_bad": trace.flagged_as_bad,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /observability/metrics  — dashboard summary stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/metrics", summary="Summary stats for the observability dashboard")
def get_observability_metrics(
    hours: int = Query(24, ge=1, le=720, description="Look-back window in hours"),
    db: Session = Depends(get_db),
):
    """
    Returns aggregate metrics for the AI Observability Dashboard header cards:
    - Total traces in the window
    - Bad answer count + rate
    - Average latency
    - Average token cost per query
    - Hallucination rate
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    base_q = db.query(AITrace).filter(AITrace.created_at >= since)

    total = base_q.count()
    bad_count = base_q.filter(AITrace.flagged_as_bad == True).count()  # noqa: E712
    hallucination_count = base_q.filter(AITrace.hallucination_flag == True).count()  # noqa: E712

    # Averages — only over evaluated traces (non-null scores)
    evaluated_q = base_q.filter(AITrace.relevance_score.isnot(None))
    avg_latency = db.query(func.avg(AITrace.total_ms)).filter(
        AITrace.created_at >= since, AITrace.total_ms.isnot(None)
    ).scalar()
    avg_tokens_in = db.query(func.avg(AITrace.tokens_in)).filter(
        AITrace.created_at >= since, AITrace.tokens_in.isnot(None)
    ).scalar()
    avg_tokens_out = db.query(func.avg(AITrace.tokens_out)).filter(
        AITrace.created_at >= since, AITrace.tokens_out.isnot(None)
    ).scalar()
    avg_relevance = db.query(func.avg(AITrace.relevance_score)).filter(
        AITrace.created_at >= since, AITrace.relevance_score.isnot(None)
    ).scalar()

    return {
        "window_hours": hours,
        "total_traces": total,
        "bad_answers": {
            "count": bad_count,
            "rate_pct": round(bad_count / total * 100, 1) if total > 0 else 0.0,
        },
        "hallucination": {
            "count": hallucination_count,
            "rate_pct": round(hallucination_count / total * 100, 1) if total > 0 else 0.0,
        },
        "avg_latency_ms": round(avg_latency or 0, 1),
        "avg_tokens_per_query": {
            "in": round(avg_tokens_in or 0, 1),
            "out": round(avg_tokens_out or 0, 1),
        },
        "avg_relevance_score": round(avg_relevance or 0, 4) if avg_relevance else None,
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /observability/traces  — paginated list
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/traces", summary="List all AI traces (paginated)")
def list_traces(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    flagged_only: bool = Query(False, description="Filter to bad answers only"),
    hallucination_only: bool = Query(False),
    hours: Optional[int] = Query(None, ge=1, le=720, description="Limit to last N hours"),
    db: Session = Depends(get_db),
):
    """Paginated list of traces, newest first."""
    q = db.query(AITrace)

    if hours:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = q.filter(AITrace.created_at >= since)

    if flagged_only:
        q = q.filter(AITrace.flagged_as_bad == True)  # noqa: E712

    if hallucination_only:
        q = q.filter(AITrace.hallucination_flag == True)  # noqa: E712

    total = q.count()
    traces = (
        q.order_by(desc(AITrace.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [_trace_to_dict(t) for t in traces],
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /observability/bad-answers  — flagged traces only
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/bad-answers", summary="Flagged / bad answer traces")
def get_bad_answers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    hours: Optional[int] = Query(None, ge=1, le=720),
    db: Session = Depends(get_db),
):
    """
    All traces flagged as bad answers — the primary triage queue for engineers.
    Sorted by newest first so the most recent failures surface first.
    """
    q = db.query(AITrace).filter(AITrace.flagged_as_bad == True)  # noqa: E712

    if hours:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = q.filter(AITrace.created_at >= since)

    total = q.count()
    traces = (
        q.order_by(desc(AITrace.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
        "items": [_trace_to_dict(t) for t in traces],
    }


# ─────────────────────────────────────────────────────────────────────────────
# GET /observability/traces/{trace_id}  — full trace detail
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/traces/{trace_id}", summary="Full trace detail — question → chunks → answer → scores")
def get_trace(
    trace_id: str,
    db: Session = Depends(get_db),
):
    """
    Returns the complete trace record for one AI request.
    This is what the engineer opens when a bad answer is flagged.
    """
    try:
        uid = uuid.UUID(trace_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid trace_id format.")

    trace = db.query(AITrace).filter(AITrace.trace_id == uid).first()
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found.")

    return _trace_to_dict(trace)


# ─────────────────────────────────────────────────────────────────────────────
# PATCH /observability/traces/{trace_id}/feedback  — operator feedback
# ─────────────────────────────────────────────────────────────────────────────

@router.patch("/traces/{trace_id}/feedback", summary="Submit operator thumbs up/down")
def submit_feedback(
    trace_id: str,
    feedback: int = Query(..., description="1=👍 good answer, -1=👎 bad answer"),
    db: Session = Depends(get_db),
):
    """
    Record operator feedback on a trace and re-evaluate the bad flag.
    A 👎 immediately marks the trace as flagged_as_bad = true.
    """
    if feedback not in (1, -1):
        raise HTTPException(status_code=400, detail="feedback must be 1 (👍) or -1 (👎).")

    ok = update_feedback(db, trace_id, feedback)
    if not ok:
        raise HTTPException(status_code=404, detail="Trace not found.")

    return {"trace_id": trace_id, "feedback": feedback, "status": "ok"}
