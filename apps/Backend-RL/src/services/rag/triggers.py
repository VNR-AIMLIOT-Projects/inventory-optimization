from sqlalchemy import event
from fastapi import BackgroundTasks
import logging

from models.domain import TrainingRun, EvaluationResult, DeploymentSession
from services.rag.embedding_service import upsert_chunk
from services.rag.ingestors import chunk_training_run, chunk_eval_result, chunk_deployment_session

logger = logging.getLogger(__name__)

def ingest_training_run(mapper, connection, target):
    # Skip if not finished
    if target.status not in ["success", "failure"]:
        return
        
    try:
        row_dict = {c.name: getattr(target, c.name) for c in target.__table__.columns}
        chunk = chunk_training_run(row_dict)
        
        # We need a new session since we're inside an event hook
        from core.database import SessionLocal
        with SessionLocal() as db:
            upsert_chunk(
                db=db,
                source_table="training_runs",
                source_id=target.id,
                stage="train",
                chunk_text=chunk,
                sku=target.sku,
                run_id=target.id,
                session_id=None
            )
            logger.info(f"RAG ingested training run {target.id}")
    except Exception as e:
        logger.error(f"Error ingesting training run {target.id}: {e}")

def ingest_eval_result(mapper, connection, target):
    try:
        row_dict = {c.name: getattr(target, c.name) for c in target.__table__.columns}
        chunk = chunk_eval_result(row_dict)
        
        from core.database import SessionLocal
        with SessionLocal() as db:
            upsert_chunk(
                db=db,
                source_table="evaluation_results",
                source_id=target.id,
                stage="evaluate",
                chunk_text=chunk,
                sku=target.sku,
                run_id=target.training_run_id,
                session_id=None
            )
            logger.info(f"RAG ingested eval result {target.id}")
    except Exception as e:
        logger.error(f"Error ingesting eval result {target.id}: {e}")

def ingest_deployment_session(mapper, connection, target):
    try:
        row_dict = {c.name: getattr(target, c.name) for c in target.__table__.columns}
        # Assuming we just want to summarize the session when it's created or updated
        chunk = chunk_deployment_session(row_dict)
        
        # session id is string UUID but pgvector source_id expects int.
        # So we'll hash it to int for source_id, and store the real string in session_id
        source_id = abs(hash(target.id)) % (10 ** 8)
        
        from core.database import SessionLocal
        with SessionLocal() as db:
            upsert_chunk(
                db=db,
                source_table="deployment_sessions",
                source_id=source_id,
                stage="deploy",
                chunk_text=chunk,
                sku=target.sku,
                run_id=target.run_id,
                session_id=target.id
            )
            logger.info(f"RAG ingested deployment session {target.id}")
    except Exception as e:
        logger.error(f"Error ingesting deployment session {target.id}: {e}")

# Register listeners for inserts AND updates
event.listen(TrainingRun, 'after_insert', ingest_training_run)
event.listen(TrainingRun, 'after_update', ingest_training_run)

event.listen(EvaluationResult, 'after_insert', ingest_eval_result)
event.listen(EvaluationResult, 'after_update', ingest_eval_result)

event.listen(DeploymentSession, 'after_insert', ingest_deployment_session)
event.listen(DeploymentSession, 'after_update', ingest_deployment_session)
