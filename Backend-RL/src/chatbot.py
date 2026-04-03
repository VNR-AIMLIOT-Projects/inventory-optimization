"""
Demand Modification Chatbot — NL → Action Parser
Uses Google Gemini 2.5 Flash to parse natural language demand modification requests
into structured action dicts that the backend can execute directly.

Uses the new `google-genai` SDK (google-generativeai is deprecated).
"""

import os
import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# System Prompt
# Must be EXTREMELY explicit — Gemini needs to know every action and its fields.
# The parser's only job is: NL → single JSON action dict. Nothing else.
# ──────────────────────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """
You are a strict demand-modification JSON parser for an inventory optimization system.
The user describes a change to a demand dataset. Your ONLY output is a single valid JSON object.

NEVER output explanations, markdown, code fences, or any text outside the JSON.

═══════════════════════════════════════════
CURRENT DEMAND CONTEXT
═══════════════════════════════════════════
Baseline average demand : {baseline} units/day
Seasonal peak demand    : {seasonal_peak} units/day
Festival peak demand    : {festival_peak} units/day
Data date range         : {start_date} to {end_date}
Total days              : {num_days}

═══════════════════════════════════════════
SUPPORTED ACTIONS  (output exactly one)
═══════════════════════════════════════════

ACTION 1 — spike
  Add extra units on ONE specific date (event, promotion, anomaly).
  Use when: "add spike", "add X units on date", "boost demand on date".
  JSON: {{"action": "spike", "date": "YYYY-MM-DD", "amount": <positive int>}}
  Example: "Add a spike of 500 units on 2025-06-15"
    → {{"action": "spike", "date": "2025-06-15", "amount": 500}}

ACTION 2 — remove_units
  Subtract units from ONE specific date (cancellation, returns, correction).
  Use when: "remove X units on date", "reduce demand by X on date", "cut demand on date", "decrease demand on date".
  JSON: {{"action": "remove_units", "date": "YYYY-MM-DD", "amount": <positive int>}}
  Example: "Remove 200 units on 2025-07-10"
    → {{"action": "remove_units", "date": "2025-07-10", "amount": 200}}
  Example: "Reduce demand by 150 units on June 3"
    → {{"action": "remove_units", "date": "2025-06-03", "amount": 150}}

ACTION 3 — set_value
  Set demand to an EXACT number on ONE specific date (override/fix a value).
  Use when: "set demand to X on date", "fix demand at X on date", "make demand exactly X on date".
  JSON: {{"action": "set_value", "date": "YYYY-MM-DD", "amount": <positive int>}}
  Example: "Set demand to exactly 100 units on 2025-08-01"
    → {{"action": "set_value", "date": "2025-08-01", "amount": 100}}

ACTION 4 — scale
  Multiply (percentage change) demand across a DATE RANGE. Factor > 1 increases, < 1 decreases.
  Use when: "scale up/down by X%", "increase demand by X% from A to B", "reduce demand by X% during period".
  JSON: {{"action": "scale", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "factor": <positive float>}}
  Conversion rules:
    "increase by 20%"  → factor = 1.20
    "decrease by 20%"  → factor = 0.80
    "reduce by 30%"    → factor = 0.70
    "double"           → factor = 2.00
    "halve"            → factor = 0.50
    "cut in half"      → factor = 0.50
    "triple"           → factor = 3.00
  Example: "Scale demand up by 20% from 2025-03-01 to 2025-05-31"
    → {{"action": "scale", "start_date": "2025-03-01", "end_date": "2025-05-31", "factor": 1.20}}
  Example: "Reduce demand by 30% for the whole year"
    → {{"action": "scale", "start_date": "{start_date}", "end_date": "{end_date}", "factor": 0.70}}

ACTION 5 — adjust_range
  Add or subtract a flat number of units from EVERY day in a range.
  Use when: "add X units per day from A to B", "remove X units from every day in period", "cut X units daily during summer".
  Positive delta = add units. Negative delta = remove units.
  JSON: {{"action": "adjust_range", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "delta": <int, can be negative>}}
  Example: "Add 50 units per day from 2025-06-01 to 2025-06-30"
    → {{"action": "adjust_range", "start_date": "2025-06-01", "end_date": "2025-06-30", "delta": 50}}
  Example: "Remove 100 units per day from January to March"
    → {{"action": "adjust_range", "start_date": "2025-01-01", "end_date": "2025-03-31", "delta": -100}}

ACTION 6 — remove_spike
  Remove/normalise a known spike on ONE date, replacing it with the local average.
  Use when: "remove spike on date", "normalise demand on date", "undo spike on date", "fix the outlier on date".
  JSON: {{"action": "remove_spike", "date": "YYYY-MM-DD"}}
  Example: "Remove the spike on 2025-06-15"
    → {{"action": "remove_spike", "date": "2025-06-15"}}

ACTION 7 — set_baseline
  Change the baseline (average normal-day) demand parameter.
  Use when: "set average demand to X", "change baseline to X units", "set normal demand to X".
  JSON: {{"action": "set_baseline", "value": <positive int>}}
  Example: "Set the average daily demand to 200 units"
    → {{"action": "set_baseline", "value": 200}}

ACTION 8 — set_seasonal_peak
  Change the seasonal peak demand parameter.
  JSON: {{"action": "set_seasonal_peak", "value": <positive int>}}

ACTION 9 — set_festival_peak
  Change the festival peak demand parameter.
  JSON: {{"action": "set_festival_peak", "value": <positive int>}}

ACTION 10 — set_season_count
  Change the number of seasonal periods.
  JSON: {{"action": "set_season_count", "value": <non-negative int>}}

ACTION 11 — set_festival_count
  Change the number of festival periods.
  JSON: {{"action": "set_festival_count", "value": <non-negative int>}}

ACTION 12 — reset
  Restore all demand data to original uploaded/generated values.
  Use when: "reset", "undo all changes", "restore original", "start over".
  JSON: {{"action": "reset"}}

ACTION 13 — unknown
  ONLY use when the request is genuinely ambiguous, impossible, or unrelated to demand modification.
  JSON: {{"action": "unknown", "message": "<one clear sentence explaining why>"}}

═══════════════════════════════════════════
DECISION RULES
═══════════════════════════════════════════
1. ALL dates must be in YYYY-MM-DD format within {start_date} to {end_date}.
   If a vague month name is given (e.g. "June"), assume year {dataset_year}.
   If a date is outside range, snap to the nearest boundary date.

2. SINGLE DATE operations (spike, remove_units, set_value, remove_spike):
   → requires exactly ONE date.

3. DATE RANGE operations (scale, adjust_range):
   → requires start_date AND end_date.
   → If only one date given (e.g. "in June"), infer the full month: first and last day.
   → If "whole year" / "all data" → use {start_date} to {end_date}.
   → If "summer" → infer June–August of the dataset year.

4. For "remove X units": always use remove_units (not spike with negative amount).
5. For "reduce by X%" over a range: always use scale (not adjust_range).
6. For "add X units per day": always use adjust_range (not spike).
7. For "add X units on ONE day": always use spike (not adjust_range).
8. Demand can never go below 0.
9. Output ONLY the JSON. No prose. No markdown. No code fences.
""".strip()


def _build_system_prompt(params: dict) -> str:
    """Inject current demand context into the system prompt."""
    try:
        baseline = params.get("baseline", {}).get("start", "unknown")
        seasonal_peak = params.get("seasonal", {}).get("peak", "unknown")
        festival_peak = params.get("festival", {}).get("peak", "unknown")
        num_days = params.get("num_days", "unknown")

        seasonal_periods = params.get("seasonal", {}).get("periods", [])
        festival_periods = params.get("festival", {}).get("periods", [])
        all_periods = seasonal_periods + festival_periods

        start_date = "2025-01-01"
        end_date = "2025-12-31"

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
            dataset_year=start_date[:4],
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
            dataset_year="2025",
        )


def _extract_json(text: str) -> Optional[dict]:
    """Robustly extract a JSON object from the LLM response."""
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("```").strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None


def parse_demand_intent(user_message: str, current_params: dict, history: list = None) -> dict:
    """
    Parse a natural-language demand modification request using Gemini 2.5 Flash.

    Returns a parsed action dict (always has "action" key).
    On failure: {"action": "unknown", "message": "<reason>"}
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "action": "unknown",
            "message": "The AI assistant is not configured. Please set GEMINI_API_KEY in the backend environment.",
        }

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)
        system_prompt = _build_system_prompt(current_params)

        contents = []
        if history:
            for msg in history[-8:]:   # last 8 turns for context
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "assistant":
                    role = "model"
                if content:
                    contents.append(types.Content(role=role, parts=[types.Part(text=content)]))

        contents.append(types.Content(role="user", parts=[types.Part(text=user_message)]))

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.0,   # fully deterministic
            ),
        )

        raw = response.text.strip() if response.text else ""
        logger.info(f"[Chatbot] Raw Gemini response: {raw[:300]}")

        action = _extract_json(raw)
        if action is None:
            return {
                "action": "unknown",
                "message": "I could not parse a valid action from your request. Please try rephrasing.",
            }

        if "action" not in action:
            return {
                "action": "unknown",
                "message": "The AI returned an unexpected response format.",
            }

        return action

    except ImportError:
        return {
            "action": "unknown",
            "message": "The google-genai package is not installed in the backend.",
        }
    except Exception as e:
        logger.error(f"[Chatbot] Gemini API error: {e}")
        return {
            "action": "unknown",
            "message": f"AI service error: {str(e)[:120]}",
        }


def action_to_human_message(action: dict, result: Optional[dict] = None) -> str:
    """Convert a parsed action dict into a human-readable chat confirmation."""
    a = action.get("action", "unknown")

    if a == "spike":
        return (
            f"✅ Added a demand spike of **{action.get('amount')} units** "
            f"on {action.get('date')}. Graph refreshed."
        )

    elif a == "remove_units":
        return (
            f"✅ Removed **{action.get('amount')} units** from demand "
            f"on {action.get('date')}. Graph refreshed."
        )

    elif a == "set_value":
        return (
            f"✅ Demand on {action.get('date')} set to exactly "
            f"**{action.get('amount')} units**. Graph refreshed."
        )

    elif a == "scale":
        factor = action.get("factor", 1.0)
        pct = round(abs(factor - 1) * 100)
        direction = "increased" if factor >= 1 else "decreased"
        return (
            f"✅ Demand {direction} by **{pct}%** from "
            f"{action.get('start_date')} to {action.get('end_date')}. Graph refreshed."
        )

    elif a == "adjust_range":
        delta = action.get("delta", 0)
        direction = "Added" if delta >= 0 else "Removed"
        return (
            f"✅ {direction} **{abs(delta)} units/day** "
            f"from {action.get('start_date')} to {action.get('end_date')}. Graph refreshed."
        )

    elif a == "remove_spike":
        return (
            f"✅ Spike on {action.get('date')} has been **normalised** "
            f"to local average demand. Graph refreshed."
        )

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
        return "✅ Demand data **reset to original values**. Graph refreshed."

    elif a == "unknown":
        return f"⚠️ {action.get('message', 'I could not understand that request. Please try rephrasing.')}"

    return "✅ Action applied. Graph refreshed."
