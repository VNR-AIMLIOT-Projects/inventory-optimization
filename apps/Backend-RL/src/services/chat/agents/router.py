import logging
import json
from typing import Optional
from .base import call_groq, extract_json

logger = logging.getLogger(__name__)

_ROUTER_SYSTEM_PROMPT = """
You are the Replenix Copilot Router. Your ONLY job is to read a user's message 
and classify their intent into exactly ONE of the following expert agents.

The user is currently on the '{current_page}' page. Unless their message explicitly asks to navigate to another page or perform an action exclusively belonging to another page, you should bias towards routing them to their current page.

AGENTS:
- "demand": Generating new demand data, loading files, or selecting SKUs. Does NOT handle modifying existing data.
- "modify": Modifying existing demand data (e.g. adding spikes, setting exact values, scaling, adjusting baseline/seasonal/festival parameters, resetting data).
- "train": Reinforcement Learning training runs (starting, stopping, checking status, loading runs, configuring hyperparameters).
- "evaluate": Running model evaluations (single or multi-SKU), explaining model vs oracle performance, conceptual questions about evaluation.
- "deploy": Deployment simulation, advancing days, overriding RL actions manually, resetting simulation, explaining deployment decisions.
- "unknown": For general chit-chat or anything completely outside the scope of inventory optimization.

Your ONLY output is a valid JSON object. NEVER output prose, explanations, or markdown.
JSON format: {{"selected_agent": "<agent_name>"}}
"""

def route_intent(user_message: str, history: list, current_page: str = "unknown") -> str:
    """
    Classifies the user's message and returns the name of the expert agent.
    Returns one of: "demand", "modify", "train", "evaluate", "deploy", "unknown".
    """
    try:
        system_prompt = _ROUTER_SYSTEM_PROMPT.format(current_page=current_page)
        raw = call_groq(system_prompt, user_message, history, model="llama-3.1-8b-instant")
        parsed = extract_json(raw)
        
        if parsed and "selected_agent" in parsed:
            agent = parsed["selected_agent"]
            if agent in ["demand", "modify", "train", "evaluate", "deploy"]:
                return agent
        
        logger.warning(f"Router returned invalid agent or parsing failed: {raw}")
        return "unknown"
    except Exception as e:
        logger.error(f"Error in router: {e}")
        return "unknown"
