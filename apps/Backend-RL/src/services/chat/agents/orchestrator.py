import logging
from typing import Dict, Any

from . import demand_agent, modify_agent, train_agent, eval_agent, deploy_agent, observe_agent
from .router import route_intent
from .base import call_groq, call_groq_with_rag, extract_json
from services.rag.retriever import retrieve
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks
import time

from services.observability import emit_trace, evaluate_trace, compute_prompt_version

logger = logging.getLogger(__name__)

# Map agent names to their modules
_AGENTS = {
    "demand": demand_agent,
    "modify": modify_agent,
    "train": train_agent,
    "evaluate": eval_agent,
    "deploy": deploy_agent,
    "observe": observe_agent,
}

# Map frontend page identifiers to router agent names
_PAGE_TO_AGENT = {
    "stage1": "demand",
    "modify": "modify",
    "train": "train",
    "evaluate": "evaluate",
    "deploy": "deploy",
    "observe": "observe"
}

def handle_copilot_message(
    page: str,
    user_message: str,
    context: dict,
    history: list,
    db: Session = None,
    background_tasks: BackgroundTasks = None,
) -> dict:
    """
    Main entry point called by the FastAPI endpoint.
    Orchestrates the Router and Expert Agents.
    """
    current_agent_name = _PAGE_TO_AGENT.get(page, "unknown")

    # 1. Determine the intent using the Router
    selected_agent_name = route_intent(user_message, history, current_page=current_agent_name)
    logger.info(f"[Orchestrator] User on page '{page}' asked: '{user_message}' -> Routed to: '{selected_agent_name}'")

    # 2. Handle 'unknown' router selection
    if selected_agent_name == "unknown":
        return {
            "action": {"action": "unknown", "message": "I could not understand that request or it is outside my capabilities."},
            "assistant_message": "⚠️ I'm not sure how to help with that. Could you try rephrasing your request?",
            "graph_refreshed": False,
        }

    # 3. Handle Cross-Page Navigation
    if selected_agent_name != current_agent_name:
        logger.info(f"[Orchestrator] Cross-page navigation required from {current_agent_name} to {selected_agent_name}")
        return {
            "action": {"action": f"navigate_to_{selected_agent_name}"},
            "assistant_message": f"Sure! Let me take you to the {selected_agent_name.capitalize()} page to do that.",
            "graph_refreshed": False,
        }

    # 4. Same-Page Execution
    agent_module = _AGENTS[selected_agent_name]
    try:
        system_prompt = agent_module.build_prompt(context)
        
        # Determine active SKU from context if available
        active_sku = context.get("active_sku")
        if not active_sku and context.get("active_skus"):
            active_sku = context.get("active_skus")[0]
            
        rag_chunks = []
        # Only use RAG for agents that need it (exclude demand_agent and observe_agent)
        if selected_agent_name in ["modify", "train", "evaluate", "deploy"] and db is not None:
            rag_chunks = retrieve(
                db=db,
                query=user_message,
                stage=selected_agent_name,
                sku=active_sku,
                top_k=4
            )
            
        start_t = time.time()
        raw, meta = call_groq_with_rag(system_prompt, user_message, history, rag_chunks, return_meta=True)
        retrieval_ms = int((time.time() - start_t) * 1000) - meta["llm_ms"]
        if retrieval_ms < 0: retrieval_ms = 0
        total_ms = meta["llm_ms"] + retrieval_ms
        
        logger.info(f"[Agent:{selected_agent_name}] Raw Groq response (with RAG): {raw[:300]}")

        action = extract_json(raw)
        if action is None:
            action = {
                "action": "unknown",
                "message": "I could not parse a valid action from your request. Please try rephrasing.",
            }

        if "action" not in action:
            action = {"action": "unknown", "message": "Unexpected response format from AI."}

        assistant_message, graph_refreshed = agent_module.to_human(action)
        
        is_action = action.get("action", "unknown") not in ["answer", "unknown"]
        
        # ── OBSERVABILITY TRACING ──
        if db and background_tasks:
            trace_id = emit_trace(
                db=db,
                question=user_message,
                retrieved_chunks=[{"text": c, "source": "rag", "similarity": 0.0} for c in rag_chunks],
                prompt_version=compute_prompt_version(system_prompt),
                llm_model=meta.get("model", "unknown"),
                answer=assistant_message,
                retrieval_ms=retrieval_ms,
                llm_ms=meta.get("llm_ms", 0),
                total_ms=total_ms,
                tokens_in=meta.get("tokens_in", 0),
                tokens_out=meta.get("tokens_out", 0),
                is_action=is_action
            )
            background_tasks.add_task(evaluate_trace, db, trace_id)
            
        return {
            "action": action,
            "assistant_message": assistant_message,
            "graph_refreshed": graph_refreshed,
        }

    except RuntimeError as e:
        logger.error(f"[Agent:{selected_agent_name}] Config error: {e}")
        return {
            "action": {"action": "unknown", "message": str(e)},
            "assistant_message": f"⚠️ {e}",
            "graph_refreshed": False,
        }
    except Exception as e:
        logger.error(f"[Agent:{selected_agent_name}] Unexpected error: {e}")
        return {
            "action": {"action": "unknown", "message": f"AI service error: {str(e)[:120]}"},
            "assistant_message": f"⚠️ AI service error: {str(e)[:120]}",
            "graph_refreshed": False,
        }
