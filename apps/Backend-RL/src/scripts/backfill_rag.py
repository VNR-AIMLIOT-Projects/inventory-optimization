import sys
import os
import logging
from sqlalchemy.orm import Session

# Add src to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.database import SessionLocal
from models.domain import TrainingRun, EvaluationResult, DeploymentSession
from services.rag.triggers import ingest_training_run, ingest_eval_result, ingest_deployment_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def backfill():
    logger.info("Starting RAG chunks backfill...")
    db: Session = SessionLocal()
    
    try:
        # 1. Backfill Training Runs
        runs = db.query(TrainingRun).all()
        logger.info(f"Found {len(runs)} training runs.")
        for run in runs:
            if run.status in ["success", "failure"]:
                ingest_training_run(None, None, run)
                
        # 2. Backfill Evaluation Results
        evals = db.query(EvaluationResult).all()
        logger.info(f"Found {len(evals)} evaluation results.")
        for eval_res in evals:
            ingest_eval_result(None, None, eval_res)
            
        # 3. Backfill Deployment Sessions
        sessions = db.query(DeploymentSession).all()
        logger.info(f"Found {len(sessions)} deployment sessions.")
        for session in sessions:
            ingest_deployment_session(None, None, session)
            
        logger.info("Backfill complete.")
    except Exception as e:
        logger.error(f"Backfill failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    backfill()
