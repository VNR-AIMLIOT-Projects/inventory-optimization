from typing import Tuple

_MODIFY_SYSTEM_PROMPT = """
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
  JSON: {{"action": "spike", "date": "YYYY-MM-DD", "amount": <positive int>}}
ACTION 2 — remove_units
  JSON: {{"action": "remove_units", "date": "YYYY-MM-DD", "amount": <positive int>}}
ACTION 3 — set_value
  JSON: {{"action": "set_value", "date": "YYYY-MM-DD", "amount": <positive int>}}
ACTION 4 — scale
  JSON: {{"action": "scale", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "factor": <positive float>}}
  "increase by 20%"→1.20, "decrease by 20%"→0.80, "double"→2.00, "halve"→0.50
ACTION 5 — adjust_range
  JSON: {{"action": "adjust_range", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD", "delta": <int>}}
ACTION 6 — remove_spike
  JSON: {{"action": "remove_spike", "date": "YYYY-MM-DD"}}
ACTION 7 — set_baseline
  JSON: {{"action": "set_baseline", "value": <non-negative int>}}
ACTION 8 — set_seasonal_peak
  JSON: {{"action": "set_seasonal_peak", "value": <positive int>}}
ACTION 9 — set_festival_peak
  JSON: {{"action": "set_festival_peak", "value": <positive int>}}
ACTION 10 — set_season_count
  JSON: {{"action": "set_season_count", "value": <non-negative int>}}
ACTION 11 — set_festival_count
  JSON: {{"action": "set_festival_count", "value": <non-negative int>}}
ACTION 12 — reset
  JSON: {{"action": "reset"}}
ACTION 13 — unknown
  ONLY for genuinely ambiguous or off-topic requests.
  JSON: {{"action": "unknown", "message": "<one clear sentence>"}}

═══════════════════════════════════════════
RULES
═══════════════════════════════════════════
1. All dates must be YYYY-MM-DD within {start_date} to {end_date}. If month-only given, infer year {dataset_year}.
2. For "increase X by Y%": calculate new absolute value from context above.
3. If subtraction results in < 0, clamp to 0.
4. Multi-step requests: execute ONLY the FIRST action.
5. You CANNOT generate demand data, train the model, evaluate the model, or control deployment. If requested, you MUST return the unknown action.
6. Output ONLY the valid JSON. No prose. No markdown. No code fences.
""".strip()


def build_prompt(context: dict) -> str:
    params = context.get("params", {})
    baseline = params.get("baseline", {}).get("start", "unknown")
    seasonal_peak = params.get("seasonal", {}).get("peak", "unknown")
    festival_peak = params.get("festival", {}).get("peak", "unknown")
    num_days = params.get("num_days", "unknown")

    # Prefer the actual dataset date range injected by the backend endpoint.
    # Fall back to inferring from seasonal/festival period dates only if unavailable.
    if context.get("start_date") and context.get("end_date"):
        start_date = context["start_date"]
        end_date = context["end_date"]
    else:
        seasonal_periods = params.get("seasonal", {}).get("periods", [])
        festival_periods = params.get("festival", {}).get("periods", [])
        all_periods = seasonal_periods + festival_periods
        start_date, end_date = "2025-01-01", "2025-12-31"
        if all_periods:
            starts = [p.get("start", "") for p in all_periods if p.get("start")]
            ends = [p.get("end", "") for p in all_periods if p.get("end")]
            if starts:
                start_date = min(starts)
            if ends:
                end_date = max(ends)

    return _MODIFY_SYSTEM_PROMPT.format(
        baseline=baseline, seasonal_peak=seasonal_peak, festival_peak=festival_peak,
        start_date=start_date, end_date=end_date, num_days=num_days,
        dataset_year=start_date[:4],
    )


def to_human(action: dict) -> Tuple[str, bool]:
    a = action.get("action", "unknown")
    if a == "spike":
        return f"✅ Added demand spike of **{action.get('amount')} units** on {action.get('date')}. Graph refreshed.", True
    if a == "remove_units":
        return f"✅ Removed **{action.get('amount')} units** from demand on {action.get('date')}. Graph refreshed.", True
    if a == "set_value":
        return f"✅ Demand on {action.get('date')} set to exactly **{action.get('amount')} units**. Graph refreshed.", True
    if a == "scale":
        factor = action.get("factor", 1.0)
        pct = round(abs(factor - 1) * 100)
        direction = "increased" if factor >= 1 else "decreased"
        return f"✅ Demand {direction} by **{pct}%** from {action.get('start_date')} to {action.get('end_date')}. Graph refreshed.", True
    if a == "adjust_range":
        delta = action.get("delta", 0)
        d = "Added" if delta >= 0 else "Removed"
        return f"✅ {d} **{abs(delta)} units/day** from {action.get('start_date')} to {action.get('end_date')}. Graph refreshed.", True
    if a == "remove_spike":
        return f"✅ Spike on {action.get('date')} normalised to local average. Graph refreshed.", True
    if a == "set_baseline":
        return f"✅ Baseline average demand set to **{action.get('value')} units/day**. Graph refreshed.", True
    if a == "set_seasonal_peak":
        return f"✅ Seasonal peak updated to **{action.get('value')} units/day**. Graph refreshed.", True
    if a == "set_festival_peak":
        return f"✅ Festival peak updated to **{action.get('value')} units/day**. Graph refreshed.", True
    if a == "set_season_count":
        return f"✅ Seasonal periods updated to **{action.get('value')}**. Graph refreshed.", True
    if a == "set_festival_count":
        return f"✅ Festival periods updated to **{action.get('value')}**. Graph refreshed.", True
    if a == "reset":
        return "✅ Demand data **reset to original values**. Graph refreshed.", True
    if a == "unknown":
        return f"⚠️ {action.get('message', 'I could not understand that request. Please rephrase.')}", False
    return "✅ Action applied. Graph refreshed.", True
