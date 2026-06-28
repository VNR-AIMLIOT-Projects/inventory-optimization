import logging
import json
from typing import Optional
from .base import call_groq, extract_json

logger = logging.getLogger(__name__)

_ROUTER_SYSTEM_PROMPT = """
You are the Replenix Copilot Router. Your ONLY job is to read a user's message 
and classify their intent into exactly ONE of the following expert agents.

AGENTS:
- "demand": For generating new demand data, loading files, or selecting SKUs.
- "modify": For adding spikes, removing units, or changing baseline/seasonal parameters of existing demand data.
- "train": For starting, stopping, checking status, or loading Reinforcement Learning training runs.
- "evaluate": For running evaluation, running multi-SKU evaluation, or explaining model performance compared to the oracle.
- "deploy": For starting the deployment simulation, advancing days, or overriding RL agent actions.
- "unknown": For general chit-chat or anything completely outside the scope of inventory optimization.

Your ONLY output is a valid JSON object. NEVER output prose, explanations, or markdown.
JSON format: {{"selected_agent": "<agent_name>"}}
"""

def route_intent(user_message: str, history: list) -> str:
    """
    Classifies the user's message and returns the name of the expert agent.
    Returns one of: "demand", "modify", "train", "evaluate", "deploy", "unknown".
    """
    try:
        raw = call_groq(_ROUTER_SYSTEM_PROMPT, user_message, history, model="llama-3.1-8b-instant")
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
