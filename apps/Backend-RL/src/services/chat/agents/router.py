import logging
import json
from typing import Optional
from .base import call_groq, extract_json

logger = logging.getLogger(__name__)

_ROUTER_SYSTEM_PROMPT = """
You are the Replenix Copilot Router. Your ONLY job is to read a user's message 
and classify their intent into exactly ONE of the following expert agents.

The user is currently on the '{current_page}' page. Unless their message explicitly asks to navigate to another page or perform an action exclusively belonging to another page, you MUST route them to their current page. This is critical: any questions about the data currently on their screen (e.g., asking about "best SKU", profits, metrics, or graphs) MUST be routed to the CURRENT PAGE'S agent so it can read the live context and explain it.

AGENTS:
- "demand": Uploading CSV files, generating new data. (Do NOT route questions about live SKU performance or profits here).
- "modify": Modifying existing demand data (e.g. adding spikes, setting exact values, scaling, adjusting baseline/seasonal/festival parameters, resetting data) or answering questions about these parameters.
- "train": Reinforcement Learning training runs (starting, stopping, checking status, loading runs, configuring hyperparameters) or explaining training progress/concepts.
- "evaluate": Running model evaluations (single or multi-SKU), explaining model vs oracle performance, conceptual questions about evaluation, or answering questions about evaluation metrics.
- "deploy": Deployment simulation, advancing days, overriding RL actions manually, resetting simulation, explaining deployment decisions. CRITICAL: ALL questions about live SKU metrics, "best SKU", profits, and inventory on the deployment dashboard MUST go to "deploy".
- "observe": Tracing and observability dashboard, changing time window, viewing bad answers, understanding hallucination rates and latency metrics.
- "unknown": For general chit-chat or anything completely outside the scope of inventory optimization.

Your ONLY output is a valid JSON object. NEVER output prose, explanations, or markdown.
JSON format: {{"selected_agent": "<agent_name>"}}
"""

def route_intent(user_message: str, history: list, current_page: str = "unknown") -> str:
    """
    Classifies the user's message and returns the name of the expert agent.
    Returns one of: "demand", "modify", "train", "evaluate", "deploy", "observe", "unknown".
    """
    try:
        system_prompt = _ROUTER_SYSTEM_PROMPT.format(current_page=current_page)
        raw = call_groq(system_prompt, user_message, history, model="llama-3.1-8b-instant")
        parsed = extract_json(raw)
        
        if parsed and "selected_agent" in parsed:
            agent = parsed["selected_agent"]
            if agent in ["demand", "modify", "train", "evaluate", "deploy", "observe"]:
                return agent
        
        logger.warning(f"Router returned invalid agent or parsing failed: {raw}")
        return "unknown"
    except Exception as e:
        logger.error(f"Error in router: {e}")
        return "unknown"
