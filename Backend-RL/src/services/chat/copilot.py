"""
Replenix Copilot — Universal Page-Scoped AI Agents
====================================================
One endpoint: POST /api/copilot/chat
Payload:  { page, message, history, context }
Response: { action, assistant_message, graph_refreshed }

Each page has its OWN isolated:
  - system_prompt   (defines scope, only the tools available on that page)
  - context_builder (injects live frontend state into the prompt)
  - response_builder (maps action dict → human message)

The LLM (Groq llama-3.3-70b-versatile) is prevented from hallucinating
because its system prompt never mentions tools from other pages.
"""

from __future__ import annotations
import os
import json
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# SHARED UTILITIES
# ─────────────────────────────────────────────────────────────────────────────

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


def _call_groq(system_prompt: str, user_message: str, history: list, retries: int = 5) -> str:
    """Call Groq with system prompt + history + user message. Returns raw string."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in the backend environment.")

    import groq
    import time
    import re as _re
    client = groq.Groq(api_key=api_key)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in (history or [])[-8:]:   # last 8 turns for context window
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": user_message})

    for attempt in range(retries):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=messages,
                temperature=0.0,
            )
            return (response.choices[0].message.content or "").strip()
        except groq.RateLimitError as e:
            if attempt == retries - 1:
                raise

            # Try to parse Groq's suggested wait time from the error message,
            # then add a buffer.  Fall back to exponential backoff.
            wait_time = 10 * (2 ** attempt)  # default: 10s, 20s, 40s, 80s
            match = _re.search(r"Please try again in ([\d.]+)s", str(e))
            if match:
                wait_time = float(match.group(1)) + 2.0  # add 2s buffer

            logger.warning(f"Groq rate limit exceeded. Retrying in {wait_time}s... (Attempt {attempt+1}/{retries})")
            time.sleep(wait_time)

    return ""


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 1: STAGE 1 — DATA INGESTION
# ─────────────────────────────────────────────────────────────────────────────

_STAGE1_SYSTEM_PROMPT = """
You are the Replenix Data Assistant. You help users load demand data into the system.
Your ONLY output is a single valid JSON object. NEVER output explanations, markdown,
code fences, or any text outside the JSON.

═══════════════════════════════════════════
CURRENT DATA CONTEXT
═══════════════════════════════════════════
Uploaded file  : {has_file}
Available SKUs : {skus}
Active SKU     : {current_sku}
Data loaded    : {has_data}
Data days      : {num_days}
Date range     : {date_range}

═══════════════════════════════════════════
SUPPORTED ACTIONS (output exactly one)
═══════════════════════════════════════════

ACTION 1 — generate_demand
  Generate synthetic demand data with specified parameters.
  Use when: user asks to generate, create, or synthesize demand.
  JSON: {{"action": "generate_demand", "season_type": "<summer|winter|none>", "num_days": <int>, "start_date": "<YYYY-MM-DD>", "seed": <int or null>}}
  Defaults: season_type="summer", num_days=365, start_date="2025-01-01", seed=42
  Example: "Generate 180 days of winter demand starting from March 2025"
    → {{"action": "generate_demand", "season_type": "winter", "num_days": 180, "start_date": "2025-03-01", "seed": 42}}

ACTION 2 — select_sku
  Select a specific SKU from the already-uploaded multi-SKU file.
  Use when: user says "switch to SKU X", "use SKU Y", "select <name>".
  Only valid when has_file is true and skus list is non-empty.
  JSON: {{"action": "select_sku", "sku": "<sku_name>"}}
  Example: "Switch to SKU_B" → {{"action": "select_sku", "sku": "SKU_B"}}

ACTION 3 — navigate_to_modify
  Tell the user to proceed to the next step (demand modification).
  Use when: user says "I'm done", "next step", "proceed", "ready to modify", "looks good".
  JSON: {{"action": "navigate_to_modify"}}

ACTION 4 — explain
  Answer a question about data loading, file formats, or what to do next.
  Do NOT use for questions about training, evaluation, or deployment — those are other pages.
  JSON: {{"action": "explain", "message": "<your clear, concise answer in 1-2 sentences>"}}
  Example: "What file formats are supported?" → {{"action": "explain", "message": "You can upload CSV or Excel (.xlsx) files. The file must have columns for date, demand quantity, and optionally a SKU identifier."}}

ACTION 5 — unknown
  ONLY use when the request is completely unrelated to data ingestion.
  JSON: {{"action": "unknown", "message": "<one sentence: what you can help with instead>"}}

═══════════════════════════════════════════
RULES
═══════════════════════════════════════════
1. You CANNOT modify demand, start training, evaluate, or control deployment.
   If asked to do any of those, return unknown with a pointer to the right page.
2. select_sku is only valid if has_file is true. Otherwise return unknown.
3. season_type must be exactly one of: summer, winter, none.
4. Output ONLY the valid JSON. No prose. No markdown. No code fences.
""".strip()


def _build_stage1_prompt(context: dict) -> str:
    skus = context.get("skus", [])
    return _STAGE1_SYSTEM_PROMPT.format(
        has_file=str(bool(context.get("has_file", False))).lower(),
        skus=", ".join(skus) if skus else "none",
        current_sku=context.get("current_sku") or "none",
        has_data=str(bool(context.get("has_data", False))).lower(),
        num_days=context.get("num_days", "unknown"),
        date_range=context.get("date_range", "unknown"),
    )


def _stage1_to_human(action: dict) -> tuple[str, bool]:
    """Returns (assistant_message, graph_refreshed)."""
    a = action.get("action", "unknown")
    if a == "generate_demand":
        st = action.get("season_type", "summer")
        days = action.get("num_days", 365)
        sd = action.get("start_date", "2025-01-01")
        return f"✅ Generating **{days} days** of **{st}** demand data starting from **{sd}**. Refreshing preview...", True
    if a == "select_sku":
        return f"✅ Switched to SKU **{action.get('sku')}**. Data updated.", True
    if a == "navigate_to_modify":
        return "✅ Your data looks good! Heading to the **Demand Modification** page now.", False
    if a == "explain":
        return action.get("message", ""), False
    if a == "unknown":
        return f"ℹ️ {action.get('message', 'I can only help with loading and generating demand data on this page.')}", False
    return "✅ Done.", False


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 2: MODIFY DEMAND  (migrated from chatbot.py — same logic, same tools)
# ─────────────────────────────────────────────────────────────────────────────

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


def _build_modify_prompt(context: dict) -> str:
    params = context.get("params", {})
    baseline = params.get("baseline", {}).get("start", "unknown")
    seasonal_peak = params.get("seasonal", {}).get("peak", "unknown")
    festival_peak = params.get("festival", {}).get("peak", "unknown")
    num_days = params.get("num_days", "unknown")

    # Infer date range from periods
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


def _modify_to_human(action: dict) -> tuple[str, bool]:
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


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 3: TRAINING
# ─────────────────────────────────────────────────────────────────────────────

_TRAIN_SYSTEM_PROMPT = """
You are the Replenix Training Assistant. You help users configure and control the
RL (Reinforcement Learning) training process. Your ONLY output is a single valid JSON object.
NEVER output explanations, markdown, code fences, or any text outside the JSON.

═══════════════════════════════════════════
CURRENT TRAINING CONTEXT
═══════════════════════════════════════════
Training status : {status}
Current episode : {current_episode} / {total_episodes}
Best reward     : {best_reward}
Latest reward   : {latest_reward}
Avg reward (50) : {avg_reward_last_50}
Active SKUs     : {active_skus}

═══════════════════════════════════════════
HYPERPARAMETER DEFAULTS  (use these unless user specifies)
═══════════════════════════════════════════
episodes        : 500  (range: 100–5000)
holding_cost    : 2    (cost per unit per day kept in inventory)
stockout_penalty: 100  (penalty per unit of unmet demand)
max_order       : null (no cap on order quantity)

═══════════════════════════════════════════
SUPPORTED ACTIONS (output exactly one)
═══════════════════════════════════════════

ACTION 1 — start_training
  Start or restart training with specified hyperparameters.
  Use when: "train", "start training", "train for X episodes", "retrain".
  JSON: {{"action": "start_training", "episodes": <int>, "holding_cost": <float>, "stockout_penalty": <float>, "max_order": <int or null>}}
  Example: "Train for 1000 episodes with a high stockout penalty of 200"
    → {{"action": "start_training", "episodes": 1000, "holding_cost": 2, "stockout_penalty": 200, "max_order": null}}
  Example: "Start training" → {{"action": "start_training", "episodes": 500, "holding_cost": 2, "stockout_penalty": 100, "max_order": null}}

ACTION 2 — stop_training
  Stop training immediately.
  Use when: "stop", "cancel training", "pause", "halt".
  JSON: {{"action": "stop_training"}}

ACTION 3 — get_status
  Report current training status in human-readable form.
  Use when: "how's training?", "status?", "what episode are we on?", "what's the reward?".
  JSON: {{"action": "get_status"}}

ACTION 4 — load_run
  Load a specific historical training run by its ID.
  Use when: "load run 5", "use run #3", "restore run <id>".
  JSON: {{"action": "load_run", "run_id": <int>}}

ACTION 5 — explain
  Explain a training concept (episodes, reward, holding cost, stockout penalty, etc.).
  JSON: {{"action": "explain", "message": "<your clear, concise answer>"}}
  Example: "What is holding cost?" → {{"action": "explain", "message": "Holding cost is the cost per unit per day that inventory sits in your warehouse. Higher values push the RL agent to order less and carry less stock."}}

ACTION 6 — unknown
  ONLY for requests completely unrelated to training.
  JSON: {{"action": "unknown", "message": "<one sentence pointing to the right page>"}}

═══════════════════════════════════════════
RULES
═══════════════════════════════════════════
1. You CANNOT generate demand data, modify demand data, evaluate the model, or control deployment. If requested, you MUST return the unknown action.
2. If status is "running", do not recommend start_training; suggest stop_training first.
3. episodes must be between 100 and 5000. Clamp silently if out of range.
4. Output ONLY the valid JSON. No prose. No markdown. No code fences.
""".strip()


def _build_train_prompt(context: dict) -> str:
    return _TRAIN_SYSTEM_PROMPT.format(
        status=context.get("status", "idle"),
        current_episode=context.get("current_episode", 0),
        total_episodes=context.get("total_episodes", 0),
        best_reward=context.get("best_reward", "n/a"),
        latest_reward=context.get("latest_reward", "n/a"),
        avg_reward_last_50=context.get("avg_reward_last_50", "n/a"),
        active_skus=", ".join(context.get("active_skus", [])) or "none",
    )


def _train_to_human(action: dict) -> tuple[str, bool]:
    a = action.get("action", "unknown")
    if a == "start_training":
        ep = action.get("episodes", 500)
        hc = action.get("holding_cost", 2)
        sp = action.get("stockout_penalty", 100)
        return (
            f"🚀 Starting training for **{ep} episodes** "
            f"(holding cost: {hc}, stockout penalty: {sp}). Watch the chart update in real-time!",
            False,
        )
    if a == "stop_training":
        return "🛑 Stopping training. The best model so far has been saved.", False
    if a == "get_status":
        return "__STATUS__", False   # sentinel — frontend will replace with live status
    if a == "load_run":
        return f"📂 Loading training run **#{action.get('run_id')}**...", False
    if a == "explain":
        return action.get("message", ""), False
    if a == "unknown":
        return f"ℹ️ {action.get('message', 'I can only help with training on this page.')}", False
    return "✅ Done.", False


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 4: EVALUATE
# ─────────────────────────────────────────────────────────────────────────────

_EVALUATE_SYSTEM_PROMPT = """
You are the Replenix Evaluation Assistant. You help users run model evaluation and
understand the comparison between RL, oracle, and rule-based policies.
Your ONLY output is a single valid JSON object.
NEVER output explanations, markdown, code fences, or any text outside the JSON.

═══════════════════════════════════════════
CURRENT EVALUATION CONTEXT
═══════════════════════════════════════════
Has trained model  : {has_model}
Has eval results   : {has_results}
RL reward          : {rl_reward}
Oracle reward      : {oracle_reward}
Rule-based reward  : {rule_reward}
RL vs Oracle (%)   : {rl_vs_oracle_pct}
Evaluated SKUs     : {evaluated_skus}
Active SKU         : {active_sku}

═══════════════════════════════════════════
SUPPORTED ACTIONS (output exactly one)
═══════════════════════════════════════════

ACTION 1 — run_evaluation
  Run evaluation on the current trained model.
  Use when: "evaluate", "run eval", "test the model", "evaluate for X days".
  JSON: {{"action": "run_evaluation", "horizon_days": <int or null>, "initial_inventory": <int or null>}}
  Defaults: horizon_days=null (uses training horizon), initial_inventory=null (uses training config)
  Example: "Evaluate over 90 days" → {{"action": "run_evaluation", "horizon_days": 90, "initial_inventory": null}}

ACTION 2 — run_multi_evaluation
  Run evaluation for ALL trained SKUs simultaneously.
  Use when: "evaluate all SKUs", "run multi-SKU eval", "test all models".
  JSON: {{"action": "run_multi_evaluation"}}

ACTION 3 — explain_results
  Explain the evaluation results, concepts, or what the metrics mean.
  Use when: "what does RL reward mean?", "why is oracle better?", "explain the results".
  JSON: {{"action": "explain_results", "message": "<clear explanation using the current results from context>"}}
  Example: "What does RL vs Oracle mean?"
    → {{"action": "explain_results", "message": "The oracle reward is the theoretical maximum achievable with perfect future demand knowledge. Your RL agent achieved {rl_vs_oracle_pct}% of the oracle, meaning it's capturing most of the possible value despite not seeing the future."}}

ACTION 4 — navigate_to_deploy
  Tell the user to proceed to the deployment simulation.
  Use when: "deploy", "I'm happy with results", "let's test live", "go to deployment".
  JSON: {{"action": "navigate_to_deploy"}}

ACTION 5 — explain
  Answer a general question about evaluation concepts.
  JSON: {{"action": "explain", "message": "<your clear, concise answer>"}}

ACTION 6 — unknown
  ONLY for requests unrelated to evaluation.
  JSON: {{"action": "unknown", "message": "<one sentence pointing to the right page>"}}

═══════════════════════════════════════════
RULES
═══════════════════════════════════════════
1. You CANNOT generate demand data, modify demand data, start training, or control deployment. If requested, you MUST return the unknown action.
2. run_evaluation requires has_model=true. If false, explain with unknown.
3. When explaining results, always reference the actual numbers from context.
4. Output ONLY the valid JSON. No prose. No markdown. No code fences.
""".strip()


def _build_evaluate_prompt(context: dict) -> str:
    rl = context.get("rl_reward")
    oracle = context.get("oracle_reward")
    rule = context.get("rule_reward")
    pct = context.get("rl_vs_oracle_pct")
    return _EVALUATE_SYSTEM_PROMPT.format(
        has_model=str(bool(context.get("has_model", False))).lower(),
        has_results=str(rl is not None).lower(),
        rl_reward=f"{rl:.2f}" if rl is not None else "n/a",
        oracle_reward=f"{oracle:.2f}" if oracle is not None else "n/a",
        rule_reward=f"{rule:.2f}" if rule is not None else "n/a",
        rl_vs_oracle_pct=f"{pct:.1f}%" if pct is not None else "n/a",
        evaluated_skus=", ".join(context.get("evaluated_skus", [])) or "none",
        active_sku=context.get("active_sku") or "none",
    )


def _evaluate_to_human(action: dict) -> tuple[str, bool]:
    a = action.get("action", "unknown")
    if a == "run_evaluation":
        h = action.get("horizon_days")
        suffix = f"over **{h} days**" if h else "using the training horizon"
        return f"🎯 Running evaluation {suffix}. This will compare RL, Oracle, and Rule-based policies...", False
    if a == "run_multi_evaluation":
        return "🎯 Running evaluation for **all SKUs**. Results will appear shortly...", False
    if a in ("explain_results", "explain"):
        return action.get("message", ""), False
    if a == "navigate_to_deploy":
        return "✅ Heading to the **Deployment Simulation** page. Let's see the RL agent in action!", False
    if a == "unknown":
        return f"ℹ️ {action.get('message', 'I can only help with model evaluation on this page.')}", False
    return "✅ Done.", False


# ─────────────────────────────────────────────────────────────────────────────
# PAGE 5: DEPLOYMENT SIMULATION
# ─────────────────────────────────────────────────────────────────────────────

_DEPLOY_SYSTEM_PROMPT = """
You are the Replenix Deployment Assistant. You help users control the interactive
day-by-day inventory simulation powered by the trained RL agent.
Your ONLY output is a single valid JSON object.
NEVER output explanations, markdown, code fences, or any text outside the JSON.

═══════════════════════════════════════════
CURRENT SIMULATION CONTEXT
═══════════════════════════════════════════
Session active     : {session_active}
Current day        : {current_day} / {total_days}
Current inventory  : {current_inventory}
RL next action     : {next_rl_action} units
Last human override: {last_override}
Active SKUs        : {active_skus}
Simulation complete: {is_complete}

═══════════════════════════════════════════
SUPPORTED ACTIONS (output exactly one)
═══════════════════════════════════════════

ACTION 1 — start_deployment
  Start a new deployment simulation session.
  Use when: "start simulation", "begin deployment", "start", "let's go".
  JSON: {{"action": "start_deployment"}}

ACTION 2 — step_day
  Advance the simulation by N days (1 by default).
  Use when: "next day", "advance", "step forward", "go 5 days", "advance 3 days".
  JSON: {{"action": "step_day", "num_days": <positive int>}}
  Example: "Go 5 days forward" → {{"action": "step_day", "num_days": 5}}
  Example: "Next day" → {{"action": "step_day", "num_days": 1}}

ACTION 3 — apply_override
  Override the RL agent's order quantity for a specific upcoming day.
  Use when: "override day X with Y units", "manually order Y units on day X", "set order to Y on day X".
  JSON: {{"action": "apply_override", "day": <int>, "override_qty": <non-negative int>}}
  Example: "Override day 10 with 200 units" → {{"action": "apply_override", "day": 10, "override_qty": 200}}
  Note: If the user specifies "current day" or "today", use the "Current day" from the context (currently {current_day}).

ACTION 4 — run_all
  Run the simulation to completion automatically.
  Use when: "run all", "complete simulation", "auto-run", "finish it", "run to end".
  JSON: {{"action": "run_all"}}

ACTION 5 — reset_simulation
  Reset the simulation back to day 0.
  Use when: "reset", "start over", "restart simulation", "go back to beginning".
  JSON: {{"action": "reset_simulation"}}

ACTION 6 — explain_decision
  Explain the RL agent's most recent ordering decision in the context of current inventory and demand.
  Use when: "why did it order X?", "explain the agent's decision", "why that much?", "what's the reasoning?".
  JSON: {{"action": "explain_decision", "message": "<explanation using current context: inventory={current_inventory}, RL action={next_rl_action}, day={current_day}>"}}

ACTION 7 — explain
  Answer a general question about the deployment simulation.
  JSON: {{"action": "explain", "message": "<clear answer>"}}

ACTION 8 — unknown
  ONLY for requests unrelated to deployment simulation.
  JSON: {{"action": "unknown", "message": "<one sentence pointing to the right page>"}}

═══════════════════════════════════════════
RULES
═══════════════════════════════════════════
1. You CANNOT generate demand data, modify demand data, train, or evaluate the model. If requested, you MUST return the unknown action.
2. step_day and apply_override require session_active=true. If not, suggest start_deployment.
3. num_days in step_day must be >= 1. If user says "a few days", use 3.
4. If is_complete=true, only reset_simulation or explain make sense.
5. Output ONLY the valid JSON. No prose. No markdown. No code fences.
""".strip()


def _build_deploy_prompt(context: dict) -> str:
    return _DEPLOY_SYSTEM_PROMPT.format(
        session_active=str(bool(context.get("session_active", False))).lower(),
        current_day=context.get("current_day", 0),
        total_days=context.get("total_days", 0),
        current_inventory=context.get("current_inventory", "n/a"),
        next_rl_action=context.get("next_rl_action", "n/a"),
        last_override=context.get("last_override", "none"),
        active_skus=", ".join(context.get("active_skus", [])) or "none",
        is_complete=str(bool(context.get("is_complete", False))).lower(),
    )


def _deploy_to_human(action: dict) -> tuple[str, bool]:
    a = action.get("action", "unknown")
    if a == "start_deployment":
        return "🚀 Starting deployment simulation! The RL agent is ready.", False
    if a == "step_day":
        n = action.get("num_days", 1)
        return f"⏭️ Advancing **{n} day{'s' if n != 1 else ''}**...", False
    if a == "apply_override":
        return (
            f"✋ Override set: **{action.get('override_qty')} units** will be ordered on day **{action.get('day')}**.",
            False,
        )
    if a == "run_all":
        return "⚡ Running simulation to completion. This may take a moment...", False
    if a == "reset_simulation":
        return "🔄 Simulation reset to day 0. Ready to start fresh.", False
    if a in ("explain_decision", "explain"):
        return action.get("message", ""), False
    if a == "unknown":
        return f"ℹ️ {action.get('message', 'I can only help with the deployment simulation on this page.')}", False
    return "✅ Done.", False


# ─────────────────────────────────────────────────────────────────────────────
# PAGE ROUTER — main entry point
# ─────────────────────────────────────────────────────────────────────────────

_PAGE_CONFIG = {
    "stage1":   (_build_stage1_prompt,   _stage1_to_human),
    "modify":   (_build_modify_prompt,   _modify_to_human),
    "train":    (_build_train_prompt,    _train_to_human),
    "evaluate": (_build_evaluate_prompt, _evaluate_to_human),
    "deploy":   (_build_deploy_prompt,   _deploy_to_human),
}


def handle_copilot_message(
    page: str,
    user_message: str,
    context: dict,
    history: list,
) -> dict:
    """
    Main entry point called by the FastAPI endpoint.

    Returns:
        {
            "action": dict,
            "assistant_message": str,
            "graph_refreshed": bool,
        }
    """
    if page not in _PAGE_CONFIG:
        return {
            "action": {"action": "unknown", "message": f"Unknown page '{page}'."},
            "assistant_message": f"⚠️ Unknown page '{page}'. Valid pages: {', '.join(_PAGE_CONFIG)}.",
            "graph_refreshed": False,
        }

    build_prompt, to_human = _PAGE_CONFIG[page]

    try:
        system_prompt = build_prompt(context)
        raw = _call_groq(system_prompt, user_message, history)
        logger.info(f"[Copilot:{page}] Raw Groq response: {raw[:300]}")

        action = _extract_json(raw)
        if action is None:
            action = {
                "action": "unknown",
                "message": "I could not parse a valid action from your request. Please try rephrasing.",
            }

        if "action" not in action:
            action = {"action": "unknown", "message": "Unexpected response format from AI."}

        assistant_message, graph_refreshed = to_human(action)
        return {
            "action": action,
            "assistant_message": assistant_message,
            "graph_refreshed": graph_refreshed,
        }

    except RuntimeError as e:
        logger.error(f"[Copilot:{page}] Config error: {e}")
        return {
            "action": {"action": "unknown", "message": str(e)},
            "assistant_message": f"⚠️ {e}",
            "graph_refreshed": False,
        }
    except Exception as e:
        logger.error(f"[Copilot:{page}] Unexpected error: {e}")
        return {
            "action": {"action": "unknown", "message": f"AI service error: {str(e)[:120]}"},
            "assistant_message": f"⚠️ AI service error: {str(e)[:120]}",
            "graph_refreshed": False,
        }
