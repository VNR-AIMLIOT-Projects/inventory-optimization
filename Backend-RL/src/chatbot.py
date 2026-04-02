"""
Demand Modification Chatbot — NL → Action Parser
Uses Google Gemini Flash to parse natural language demand modification requests
into structured action dicts that the backend can execute directly.
"""

import os
import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# System Prompt Template
# Injected at runtime with current demand context
# ──────────────────────────────────────────────
_SYSTEM_PROMPT = """
You are a strict demand-parameter parser for an inventory optimization system.
The user describes changes they want to make to a demand dataset in natural language.
Your ONLY job is to parse the request and output a single valid JSON action object.

Do NOT output any explanation, markdown, code blocks, or extra text.
Output raw JSON only — nothing else.

Current demand context:
- Baseline average demand: {baseline} units/day
- Seasonal peak demand: {seasonal_peak} units/day
- Festival peak demand: {festival_peak} units/day
- Date range: {start_date} to {end_date}
- Total days: {num_days}

Supported JSON actions:

1. Add a demand spike on a specific date:
   {{"action": "spike", "date": "YYYY-MM-DD", "amount": <positive integer>}}

2. Scale (multiply) demand over a date range:
   {{"action": "scale", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "factor": <positive float>}}

3. Change the baseline (average) daily demand:
   {{"action": "set_baseline", "value": <positive integer>}}

4. Change the seasonal peak demand:
   {{"action": "set_seasonal_peak", "value": <positive integer>}}

5. Change the festival peak demand:
   {{"action": "set_festival_peak", "value": <positive integer>}}

6. Change the number of seasonal periods:
   {{"action": "set_season_count", "value": <non-negative integer>}}

7. Change the number of festival periods:
   {{"action": "set_festival_count", "value": <non-negative integer>}}

8. Reset all demand data to original values:
   {{"action": "reset"}}

9. If you cannot confidently parse the request, return:
   {{"action": "unknown", "message": "<one sentence explaining why>"}}

Rules:
- All dates must be in YYYY-MM-DD format.
- All dates must fall within {start_date} to {end_date}.
- For scale factor: 1.2 means +20%, 0.8 means -20%, 2.0 means double.
- If user says "increase by X%", compute factor = 1 + X/100.
- If user says "decrease by X%" or "reduce by X%", compute factor = 1 - X/100.
- If user says "double" → factor = 2.0, "halve" → factor = 0.5.
- If user says "summer", "peak season", etc. and seasonal periods are known, infer the date range.
- If a date is outside the known range, pick the nearest valid date.
- If the user says "reset" or "undo" or "restore", output the reset action.
- Output ONLY the JSON. No prose. No markdown. No code fences.
""".strip()


def _build_system_prompt(params: dict) -> str:
    """Inject current demand context into the system prompt."""
    try:
        baseline = params.get("baseline", {}).get("start", "unknown")
        seasonal_peak = params.get("seasonal", {}).get("peak", "unknown")
        festival_peak = params.get("festival", {}).get("peak", "unknown")
        num_days = params.get("num_days", "unknown")

        # Try to get actual dates from seasonal periods or fallback
        seasonal_periods = params.get("seasonal", {}).get("periods", [])
        festival_periods = params.get("festival", {}).get("periods", [])

        # Build a rough date range from params
        all_periods = seasonal_periods + festival_periods
        start_date = "2025-01-01"  # fallback
        end_date = "2025-12-31"    # fallback

        if all_periods:
            starts = [p.get("start", "") for p in all_periods if p.get("start")]
            ends = [p.get("end", "") for p in all_periods if p.get("end")]
            if starts:
                start_date = min(starts)
            if ends:
                end_date = max(ends)

        return _SYSTEM_PROMPT.format(
            baseline=baseline,
            seasonal_peak=seasonal_peak,
            festival_peak=festival_peak,
            start_date=start_date,
            end_date=end_date,
            num_days=num_days,
        )
    except Exception as e:
        logger.warning(f"[Chatbot] Could not build system prompt context: {e}")
        return _SYSTEM_PROMPT.format(
            baseline="unknown",
            seasonal_peak="unknown",
            festival_peak="unknown",
            start_date="2025-01-01",
            end_date="2025-12-31",
            num_days="unknown",
        )


def _extract_json(text: str) -> Optional[dict]:
    """
    Robustly extract a JSON object from the LLM response.
    Handles cases where the model wraps in markdown code fences.
    """
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip()

    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find first {...} block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def parse_demand_intent(user_message: str, current_params: dict, history: list = None) -> dict:
    """
    Parse a natural-language demand modification request using Gemini Flash.

    Args:
        user_message: The user's natural language request
        current_params: Current demand parameter dict (DetectedParams schema)
        history: Optional list of {"role": "user"/"assistant", "content": str}

    Returns:
        Parsed action dict. Always has "action" key.
        On failure: {"action": "unknown", "message": "<reason>"}
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("[Chatbot] GEMINI_API_KEY not set in environment")
        return {
            "action": "unknown",
            "message": "The AI assistant is not configured. Please set GEMINI_API_KEY in the backend environment.",
        }

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            system_instruction=_build_system_prompt(current_params),
        )

        # Build conversation history for multi-turn context
        chat_history = []
        if history:
            for msg in history[-6:]:  # Keep last 6 turns for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role in ("user", "model") and content:
                    chat_history.append({"role": role, "parts": [content]})

        chat = model.start_chat(history=chat_history)
        response = chat.send_message(user_message)
        raw = response.text.strip()

        logger.info(f"[Chatbot] Raw Gemini response: {raw[:200]}")

        action = _extract_json(raw)
        if action is None:
            return {
                "action": "unknown",
                "message": "I could not parse a valid action from your request. Please try rephrasing.",
            }

        # Validate that action key exists
        if "action" not in action:
            return {
                "action": "unknown",
                "message": "The AI returned an unexpected response format.",
            }

        return action

    except ImportError:
        return {
            "action": "unknown",
            "message": "The google-generativeai package is not installed in the backend.",
        }
    except Exception as e:
        logger.error(f"[Chatbot] Gemini API error: {e}")
        return {
            "action": "unknown",
            "message": f"AI service error: {str(e)[:120]}",
        }


def action_to_human_message(action: dict, result: Optional[dict] = None) -> str:
    """
    Convert a parsed action dict into a human-readable confirmation message
    for the chat UI.
    """
    a = action.get("action", "unknown")

    if a == "spike":
        return f"✅ Added a demand spike of **{action.get('amount')} units** on {action.get('date')}. The graph has been refreshed."

    elif a == "scale":
        factor = action.get("factor", 1.0)
        pct = round((factor - 1) * 100)
        direction = "increased" if pct >= 0 else "decreased"
        return f"✅ Demand {direction} by **{abs(pct)}%** from {action.get('start_date')} to {action.get('end_date')}. Graph refreshed."

    elif a == "set_baseline":
        return f"✅ Baseline average demand set to **{action.get('value')} units/day**. Graph refreshed."

    elif a == "set_seasonal_peak":
        return f"✅ Seasonal peak demand updated to **{action.get('value')} units/day**. Graph refreshed."

    elif a == "set_festival_peak":
        return f"✅ Festival peak demand updated to **{action.get('value')} units/day**. Graph refreshed."

    elif a == "set_season_count":
        return f"✅ Number of seasonal periods updated to **{action.get('value')}**. Graph refreshed."

    elif a == "set_festival_count":
        return f"✅ Number of festival periods updated to **{action.get('value')}**. Graph refreshed."

    elif a == "reset":
        return "✅ Demand data has been **reset to original values**. Graph refreshed."

    elif a == "unknown":
        return f"⚠️ {action.get('message', 'I could not understand that request. Please try rephrasing.')}"

    return "✅ Action applied. Graph refreshed."
