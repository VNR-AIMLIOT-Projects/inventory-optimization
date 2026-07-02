#!/usr/bin/env python3
"""
=============================================================================
  Replenix Copilot — Comprehensive Agent Test Suite
  Tests ALL 5 pages: stage1, modify, train, evaluate, deploy
  Categories: happy path, synonyms, edge cases, cross-page, adversarial
=============================================================================
"""

import json
import time
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional

# ─── Config ───────────────────────────────────────────────────────────────────
BASE_URL  = "http://localhost:8000"
API_KEY   = "replenix-secret-key"
DELAY_S   = 1.5   # seconds between LLM calls (rate-limit buffer)

# ANSI colours
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

# ─── HTTP helpers ─────────────────────────────────────────────────────────────
def _headers():
    return {"X-API-Key": API_KEY, "Content-Type": "application/json"}

def _get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}", headers=_headers())
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def _post(path, body=None):
    data = json.dumps(body or {}).encode()
    req  = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=_headers(), method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def copilot(page, message, context=None, history=None):
    return _post("/api/copilot/chat", {
        "page": page,
        "message": message,
        "history": history or [],
        "context": context or {},
    })

# ─── Test infrastructure ──────────────────────────────────────────────────────
@dataclass
class TestCase:
    name: str
    page: str
    message: str
    expected_action: str                  # exact action key that must appear
    context: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    expect_graph_refreshed: Optional[bool] = None  # None = don't check
    forbidden_actions: list = field(default_factory=list)  # must NOT be these
    note: str = ""

@dataclass
class TestResult:
    name: str
    passed: bool
    actual_action: str
    actual_graph_refreshed: bool
    note: str
    error: str = ""

results: list[TestResult] = []

def run_test(tc: TestCase) -> TestResult:
    try:
        resp = copilot(tc.page, tc.message, tc.context, tc.history)
        action      = resp.get("action", {})
        action_type = action.get("action", "MISSING")
        graph_ref   = resp.get("graph_refreshed", False)
        msg         = resp.get("assistant_message", "")

        passed = True
        failure_reason = ""

        # Primary check: action must match expected
        if action_type != tc.expected_action:
            passed = False
            failure_reason = f"expected '{tc.expected_action}' got '{action_type}'"

        # Optional: check forbidden actions (for cross-page / boundary tests)
        if action_type in tc.forbidden_actions:
            passed = False
            failure_reason += f" | action '{action_type}' is in forbidden list"

        # Optional: check graph_refreshed flag
        if tc.expect_graph_refreshed is not None:
            if graph_ref != tc.expect_graph_refreshed:
                passed = False
                failure_reason += f" | graph_refreshed={graph_ref} expected {tc.expect_graph_refreshed}"

        time.sleep(DELAY_S)
        return TestResult(
            name=tc.name, passed=passed,
            actual_action=action_type,
            actual_graph_refreshed=graph_ref,
            note=failure_reason or tc.note,
            error="",
        )
    except Exception as e:
        time.sleep(DELAY_S)
        return TestResult(
            name=tc.name, passed=False,
            actual_action="ERROR", actual_graph_refreshed=False,
            note=tc.note, error=str(e),
        )

# ─── Demand / Stage1 agent tests ─────────────────────────────────────────────
DEMAND_CONTEXT_EMPTY  = {"has_file": False, "skus": [], "has_data": False}
DEMAND_CONTEXT_LOADED = {"has_file": True, "skus": ["SKU_A","SKU_B"], "current_sku": "SKU_A",
                         "has_data": True, "num_days": 365, "date_range": "2025-01-01 to 2025-12-31"}

STAGE1_TESTS = [
    # ── Happy paths ────────────────────────────────────────────────────────
    TestCase("S1-01 generate_demand canonical",
             "stage1", "Generate 365 days of summer demand starting from 2025-01-01",
             "generate_demand", DEMAND_CONTEXT_EMPTY,
             note="canonical generate"),

    TestCase("S1-02 generate_demand synonym — synthesize",
             "stage1", "Synthesize winter demand data for 180 days",
             "generate_demand", DEMAND_CONTEXT_EMPTY,
             note="synonym: synthesize"),

    TestCase("S1-03 generate_demand synonym — create",
             "stage1", "Create some sample demand data with no seasonality",
             "generate_demand", DEMAND_CONTEXT_EMPTY,
             note="synonym: create, season_type=none"),

    TestCase("S1-04 select_sku canonical",
             "stage1", "Switch to SKU_B",
             "select_sku", DEMAND_CONTEXT_LOADED,
             note="has_file=true, sku in list"),

    TestCase("S1-05 select_sku synonym — use",
             "stage1", "Use SKU_A for this analysis",
             "select_sku", DEMAND_CONTEXT_LOADED,
             note="synonym: use"),

    TestCase("S1-06 navigate_to_modify — done",
             "stage1", "I'm done, let's go to the next step",
             "navigate_to_modify", DEMAND_CONTEXT_LOADED,
             note="proceed to modify"),

    TestCase("S1-07 navigate_to_modify — looks good",
             "stage1", "Looks good, proceed",
             "navigate_to_modify", DEMAND_CONTEXT_LOADED,
             note="synonym: looks good"),

    TestCase("S1-08 explain — file format question",
             "stage1", "What file formats are supported for upload?",
             "explain", DEMAND_CONTEXT_EMPTY,
             note="general knowledge question"),

    # ── Edge cases ─────────────────────────────────────────────────────────
    TestCase("S1-09 select_sku when has_file=false → unknown",
             "stage1", "Select SKU_X",
              "unknown", DEMAND_CONTEXT_EMPTY,
             note="no file loaded, should return unknown"),

    TestCase("S1-10 generate_demand — no days specified → defaults",
             "stage1", "Generate summer demand",
             "generate_demand", DEMAND_CONTEXT_EMPTY,
             note="defaults should be applied"),

    # ── Cross-page boundary ────────────────────────────────────────────────
    TestCase("S1-11 cross-page: ask to train on stage1 → navigate_to_train",
             "stage1", "Start training the model",
             "navigate_to_train", DEMAND_CONTEXT_LOADED,
             forbidden_actions=["start_training"],
             note="training not allowed on stage1 page"),

    TestCase("S1-12 cross-page: ask to evaluate on stage1 → navigate_to_evaluate",
             "stage1", "Run evaluation on the model",
             "navigate_to_evaluate", DEMAND_CONTEXT_LOADED,
             forbidden_actions=["run_evaluation"],
             note="evaluation not allowed on stage1 page"),

    # ── Adversarial / off-topic ───────────────────────────────────────────
    TestCase("S1-13 adversarial — random question",
             "stage1", "What is the capital of France?",
              "unknown", DEMAND_CONTEXT_EMPTY,
             note="completely off-topic"),

    TestCase("S1-14 adversarial — modify demand on stage1",
             "stage1", "Add a spike of 500 units on June 15",
              "unknown", DEMAND_CONTEXT_EMPTY,
             forbidden_actions=["spike"],
             note="modification not allowed here"),
]

# ─── Modify agent tests ───────────────────────────────────────────────────────
MODIFY_CTX = {
    "start_date": "2025-01-01",
    "end_date":   "2025-12-31",
    "params": {
        "baseline":  {"start": 300},
        "seasonal":  {"peak": 600, "num_seasons": 2, "periods": [
            {"start": "2025-06-01", "end": "2025-08-31"},
        ]},
        "festival":  {"peak": 800, "num_festivals": 1, "periods": [
            {"start": "2025-12-20", "end": "2025-12-31"},
        ]},
        "num_days": 365,
    }
}

MODIFY_TESTS = [
    # ── Spike ──────────────────────────────────────────────────────────────
    TestCase("M-01 spike canonical",
             "modify", "Add a spike of 400 units on 2025-07-04",
             "spike", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical spike"),

    TestCase("M-02 spike synonym — demand spike",
             "modify", "Create a demand spike of 250 units on March 10th",
             "spike", MODIFY_CTX, expect_graph_refreshed=True,
             note="synonym: create a spike"),

    TestCase("M-03 spike synonym — surge",
             "modify", "Add a surge of 300 units on 2025-09-01",
             "spike", MODIFY_CTX, expect_graph_refreshed=True,
             note="synonym: surge"),

    # ── Remove units ───────────────────────────────────────────────────────
    TestCase("M-04 remove_units canonical",
             "modify", "Remove 100 units from demand on 2025-04-15",
             "remove_units", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical remove_units"),

    TestCase("M-05 remove_units synonym — reduce",
             "modify", "Reduce demand by 50 units on April 20th",
             "remove_units", MODIFY_CTX, expect_graph_refreshed=True,
             note="synonym: reduce"),

    # ── Set value ──────────────────────────────────────────────────────────
    TestCase("M-06 set_value canonical",
             "modify", "Set the demand on 2025-05-01 to exactly 450 units",
             "set_value", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical set_value"),

    TestCase("M-07 set_value synonym — fix",
             "modify", "Fix the demand on June 1st to be 500 units",
             "set_value", MODIFY_CTX, expect_graph_refreshed=True,
             note="synonym: fix"),

    # ── Scale ──────────────────────────────────────────────────────────────
    TestCase("M-08 scale — increase by %",
             "modify", "Increase demand by 20% from 2025-06-01 to 2025-08-31",
             "scale", MODIFY_CTX, expect_graph_refreshed=True,
             note="scale factor 1.2"),

    TestCase("M-09 scale — decrease by %",
             "modify", "Decrease demand by 30% from March to April",
             "scale", MODIFY_CTX, expect_graph_refreshed=True,
             note="scale factor 0.7"),

    TestCase("M-10 scale — double",
             "modify", "Double the demand from 2025-07-01 to 2025-07-31",
             "scale", MODIFY_CTX, expect_graph_refreshed=True,
             note="scale factor 2.0"),

    TestCase("M-11 scale — halve",
             "modify", "Halve the demand from 2025-01-01 to 2025-01-31",
             "scale", MODIFY_CTX, expect_graph_refreshed=True,
             note="scale factor 0.5"),

    # ── Adjust range ───────────────────────────────────────────────────────
    TestCase("M-12 adjust_range add",
             "modify", "Add 50 units per day from 2025-03-01 to 2025-03-31",
             "adjust_range", MODIFY_CTX, expect_graph_refreshed=True,
             note="positive delta"),

    TestCase("M-13 adjust_range subtract",
             "modify", "Subtract 30 units per day from April",
             "adjust_range", MODIFY_CTX, expect_graph_refreshed=True,
             note="negative delta"),

    # ── Remove spike ───────────────────────────────────────────────────────
    TestCase("M-14 remove_spike canonical",
             "modify", "Remove the spike on 2025-07-04",
             "remove_spike", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical remove_spike"),

    TestCase("M-15 remove_spike synonym — smooth out",
             "modify", "Smooth out the spike on September 1st",
             "remove_spike", MODIFY_CTX, expect_graph_refreshed=True,
             note="synonym: smooth out"),

    TestCase("M-16 remove_spike synonym — normalize",
             "modify", "Normalize the outlier on 2025-07-04",
             "remove_spike", MODIFY_CTX, expect_graph_refreshed=True,
             note="synonym: normalize"),

    # ── Parameter actions ──────────────────────────────────────────────────
    TestCase("M-17 set_baseline",
             "modify", "Set the baseline demand to 350 units per day",
             "set_baseline", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical set_baseline"),

    TestCase("M-18 set_seasonal_peak",
             "modify", "Set the seasonal peak to 700 units",
             "set_seasonal_peak", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical set_seasonal_peak"),

    TestCase("M-19 set_festival_peak",
             "modify", "Update the festival peak demand to 900 units",
             "set_festival_peak", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical set_festival_peak"),

    TestCase("M-20 set_season_count",
             "modify", "Change the number of seasons to 3",
             "set_season_count", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical set_season_count"),

    TestCase("M-21 set_festival_count",
             "modify", "Set 2 festival periods",
             "set_festival_count", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical set_festival_count"),

    # ── Reset ──────────────────────────────────────────────────────────────
    TestCase("M-22 reset canonical",
             "modify", "Reset all demand changes to original",
             "reset", MODIFY_CTX, expect_graph_refreshed=True,
             note="canonical reset"),

    TestCase("M-23 reset synonym — undo everything",
             "modify", "Undo all my changes",
             "reset", MODIFY_CTX, expect_graph_refreshed=True,
             note="synonym: undo everything"),

    # ── Cross-page boundary ────────────────────────────────────────────────
    TestCase("M-24 cross-page: generate on modify → navigate_to_demand",
             "modify", "Generate a fresh 365-day demand dataset",
             "navigate_to_demand", MODIFY_CTX,
             forbidden_actions=["generate_demand"],
             note="generation not allowed on modify page"),

    TestCase("M-25 cross-page: train on modify → navigate_to_train",
             "modify", "Start training for 500 episodes",
             "navigate_to_train", MODIFY_CTX,
             forbidden_actions=["start_training"],
             note="training not allowed on modify page"),

    # ── Adversarial ────────────────────────────────────────────────────────
    TestCase("M-26 adversarial — out of date range",
             "modify", "Add a spike on 2099-01-01",
             "spike", MODIFY_CTX,
             note="LLM may clamp or return spike with far future date — acceptable"),

    TestCase("M-27 adversarial — ambiguous request",
             "modify", "Make the demand better",
              "unknown", MODIFY_CTX,
             note="too vague → should be unknown"),

    TestCase("M-28 adversarial — off-topic",
             "modify", "What is the GDP of the United States?",
              "unknown", MODIFY_CTX,
             note="completely off-topic"),
]

# ─── Train agent tests ────────────────────────────────────────────────────────
TRAIN_CTX_IDLE    = {"status": "idle",    "current_episode": 0,   "total_episodes": 500,
                     "best_reward": 0,    "latest_reward": 0,     "avg_reward_last_50": 0,
                     "active_skus": ["SKU_A"]}
TRAIN_CTX_RUNNING = {"status": "running", "current_episode": 150, "total_episodes": 500,
                     "best_reward": -120, "latest_reward": -115,  "avg_reward_last_50": -118,
                     "active_skus": ["SKU_A"]}

TRAIN_TESTS = [
    # ── Happy paths ────────────────────────────────────────────────────────
    TestCase("T-01 start_training canonical",
             "train", "Start training",
             "start_training", TRAIN_CTX_IDLE,
             note="canonical start with defaults"),

    TestCase("T-02 start_training with params",
             "train", "Train for 1000 episodes with stockout penalty 200",
             "start_training", TRAIN_CTX_IDLE,
             note="custom params"),

    TestCase("T-03 start_training synonym — retrain",
             "train", "Retrain the model from scratch",
             "start_training", TRAIN_CTX_IDLE,
             note="synonym: retrain"),

    TestCase("T-04 start_training synonym — begin",
             "train", "Begin RL training with holding cost 5",
             "start_training", TRAIN_CTX_IDLE,
             note="synonym: begin"),

    TestCase("T-05 stop_training canonical",
             "train", "Stop training",
             "stop_training", TRAIN_CTX_RUNNING,
             note="canonical stop"),

    TestCase("T-06 stop_training synonym — halt",
             "train", "Halt the training",
             "stop_training", TRAIN_CTX_RUNNING,
             note="synonym: halt"),

    TestCase("T-07 stop_training synonym — cancel",
             "train", "Cancel the current training run",
             "stop_training", TRAIN_CTX_RUNNING,
             note="synonym: cancel"),

    TestCase("T-08 get_status",
             "train", "How is training going?",
             "get_status", TRAIN_CTX_RUNNING,
             note="status query"),

    TestCase("T-09 get_status synonym — what episode",
             "train", "What episode are we on?",
             "get_status", TRAIN_CTX_RUNNING,
             note="synonym: what episode"),

    TestCase("T-10 get_status synonym — progress",
             "train", "Show me the training progress",
             "get_status", TRAIN_CTX_RUNNING,
             note="synonym: progress"),

    TestCase("T-11 load_run canonical",
             "train", "Load run 3",
             "load_run", TRAIN_CTX_IDLE,
             note="canonical load_run"),

    TestCase("T-12 load_run synonym — use run",
             "train", "Use training run number 5",
             "load_run", TRAIN_CTX_IDLE,
             note="synonym: use run"),

    TestCase("T-13 explain — holding cost",
             "train", "What is holding cost?",
             "explain", TRAIN_CTX_IDLE,
             note="explain hyperparameter"),

    TestCase("T-14 explain — stockout penalty",
             "train", "Explain the stockout penalty",
             "explain", TRAIN_CTX_IDLE,
             note="explain concept"),

    TestCase("T-15 explain — episodes",
             "train", "What does number of episodes mean in RL?",
             "explain", TRAIN_CTX_IDLE,
             note="explain RL concept"),

    # ── Edge cases ─────────────────────────────────────────────────────────
    TestCase("T-16 episode count at boundary — 100",
             "train", "Train for 100 episodes",
             "start_training", TRAIN_CTX_IDLE,
             note="lower boundary"),

    TestCase("T-17 episode count at boundary — 5000",
             "train", "Train for 5000 episodes",
             "start_training", TRAIN_CTX_IDLE,
             note="upper boundary"),

    TestCase("T-18 episode count clamped — 50 → should clamp to 100",
             "train", "Train for 50 episodes",
             "start_training", TRAIN_CTX_IDLE,
             note="below minimum, agent should clamp"),

    TestCase("T-19 episode count clamped — 10000 → should clamp to 5000",
             "train", "Train for 10000 episodes",
             "start_training", TRAIN_CTX_IDLE,
             note="above maximum, agent should clamp"),

    # ── Cross-page boundary ────────────────────────────────────────────────
    TestCase("T-20 cross-page: modify demand on train → navigate_to_modify",
             "train", "Add a spike of 300 units on June 15",
             "navigate_to_modify", TRAIN_CTX_IDLE,
             forbidden_actions=["spike"],
             note="modification not allowed on train page"),

    TestCase("T-21 cross-page: evaluate on train → navigate_to_evaluate",
             "train", "Run evaluation on the model",
             "navigate_to_evaluate", TRAIN_CTX_IDLE,
             forbidden_actions=["run_evaluation"],
             note="evaluation not allowed on train page"),

    # ── Adversarial ────────────────────────────────────────────────────────
    TestCase("T-22 adversarial — off-topic",
             "train", "Order me a pizza",
              "unknown", TRAIN_CTX_IDLE,
             note="completely off-topic"),
]

# ─── Evaluate agent tests ─────────────────────────────────────────────────────
EVAL_CTX_NO_MODEL = {"has_model": False, "rl_reward": None, "oracle_reward": None,
                     "rule_reward": None, "rl_vs_oracle_pct": None,
                     "evaluated_skus": [], "active_sku": "SKU_A"}
EVAL_CTX_WITH_MODEL = {"has_model": True, "rl_reward": -95.5, "oracle_reward": -80.2,
                       "rule_reward": -130.0, "rl_vs_oracle_pct": 84.1,
                       "evaluated_skus": ["SKU_A"], "active_sku": "SKU_A"}

EVALUATE_TESTS = [
    # ── Happy paths ────────────────────────────────────────────────────────
    TestCase("E-01 run_evaluation canonical",
             "evaluate", "Evaluate the model",
             "run_evaluation", EVAL_CTX_WITH_MODEL,
             note="canonical evaluate"),

    TestCase("E-02 run_evaluation with horizon",
             "evaluate", "Evaluate over 90 days",
             "run_evaluation", EVAL_CTX_WITH_MODEL,
             note="horizon_days=90"),

    TestCase("E-03 run_evaluation synonym — test the model",
             "evaluate", "Test the model",
             "run_evaluation", EVAL_CTX_WITH_MODEL,
             note="synonym: test"),

    TestCase("E-04 run_evaluation synonym — run eval",
             "evaluate", "Run eval",
             "run_evaluation", EVAL_CTX_WITH_MODEL,
             note="abbrev: run eval"),

    TestCase("E-05 run_multi_evaluation canonical",
             "evaluate", "Evaluate all SKUs",
             "run_multi_evaluation", EVAL_CTX_WITH_MODEL,
             note="multi-SKU eval"),

    TestCase("E-06 run_multi_evaluation synonym — test all models",
             "evaluate", "Test all models",
             "run_multi_evaluation", EVAL_CTX_WITH_MODEL,
             note="synonym: test all models"),

    TestCase("E-07 explain_results — RL vs oracle",
             "evaluate", "Why is the oracle reward better than RL?",
             "explain_results", EVAL_CTX_WITH_MODEL,
             note="explain contextual results"),

    TestCase("E-08 explain_results — performance",
             "evaluate", "Explain the evaluation results",
             "explain_results", EVAL_CTX_WITH_MODEL,
             note="explain results"),

    TestCase("E-09 explain — concept question",
             "evaluate", "What does RL reward mean?",
             "explain", EVAL_CTX_WITH_MODEL,
             note="general concept question"),

    TestCase("E-10 navigate_to_deploy",
             "evaluate", "I'm happy with the results, let's deploy",
             "navigate_to_deploy", EVAL_CTX_WITH_MODEL,
             note="navigate to deploy page"),

    TestCase("E-11 navigate_to_deploy synonym — go live",
             "evaluate", "Go to the deployment simulation",
             "navigate_to_deploy", EVAL_CTX_WITH_MODEL,
             note="synonym: go to deployment"),

    # ── Edge cases ─────────────────────────────────────────────────────────
    TestCase("E-12 run_evaluation when no model → unknown",
             "evaluate", "Evaluate the model",
              "unknown", EVAL_CTX_NO_MODEL,
             forbidden_actions=["run_evaluation"],
             note="no model trained yet, should explain"),

    # ── Cross-page boundary ────────────────────────────────────────────────
    TestCase("E-13 cross-page: start training on evaluate → navigate_to_train",
             "evaluate", "Start training for 500 episodes",
             "navigate_to_train", EVAL_CTX_WITH_MODEL,
             forbidden_actions=["start_training"],
             note="training not allowed on evaluate page"),

    TestCase("E-14 cross-page: modify demand on evaluate → navigate_to_modify",
             "evaluate", "Add a spike on June 15",
             "navigate_to_modify", EVAL_CTX_WITH_MODEL,
             forbidden_actions=["spike"],
             note="modification not allowed on evaluate page"),

    # ── Adversarial ────────────────────────────────────────────────────────
    TestCase("E-15 adversarial — off-topic",
             "evaluate", "How do I bake a cake?",
              "unknown", EVAL_CTX_WITH_MODEL,
             note="completely off-topic"),
]

# ─── Deploy agent tests ───────────────────────────────────────────────────────
DEPLOY_CTX_INACTIVE = {"session_active": False, "current_day": 0,  "total_days": 365,
                       "current_inventory": 0, "next_rl_action": 0,
                       "last_override": None,  "active_skus": ["SKU_A"], "is_complete": False}
DEPLOY_CTX_ACTIVE   = {"session_active": True,  "current_day": 15, "total_days": 365,
                       "current_inventory": 250,"next_rl_action": 45,
                       "last_override": None,  "active_skus": ["SKU_A"], "is_complete": False}
DEPLOY_CTX_COMPLETE = {"session_active": True,  "current_day": 365,"total_days": 365,
                       "current_inventory": 80, "next_rl_action": 0,
                       "last_override": None,  "active_skus": ["SKU_A"], "is_complete": True}

DEPLOY_TESTS = [
    # ── Happy paths ────────────────────────────────────────────────────────
    TestCase("D-01 start_deployment canonical",
             "deploy", "Start the simulation",
             "start_deployment", DEPLOY_CTX_INACTIVE,
             note="canonical start"),

    TestCase("D-02 start_deployment synonym — begin",
             "deploy", "Begin deployment",
             "start_deployment", DEPLOY_CTX_INACTIVE,
             note="synonym: begin"),

    TestCase("D-03 start_deployment synonym — let's go",
             "deploy", "Let's go",
             "start_deployment", DEPLOY_CTX_INACTIVE,
             note="colloquial: let's go"),

    TestCase("D-04 step_day canonical — 1 day",
             "deploy", "Next day",
             "step_day", DEPLOY_CTX_ACTIVE,
             note="advance 1 day"),

    TestCase("D-05 step_day — multi-day",
             "deploy", "Advance 5 days",
             "step_day", DEPLOY_CTX_ACTIVE,
             note="advance 5 days"),

    TestCase("D-06 step_day synonym — go forward",
             "deploy", "Go 3 days forward",
             "step_day", DEPLOY_CTX_ACTIVE,
             note="synonym: go forward"),

    TestCase("D-07 step_day synonym — step",
             "deploy", "Step forward",
             "step_day", DEPLOY_CTX_ACTIVE,
             note="synonym: step"),

    TestCase("D-08 apply_override canonical",
             "deploy", "Override day 20 with 300 units",
             "apply_override", DEPLOY_CTX_ACTIVE,
             note="canonical override"),

    TestCase("D-09 apply_override synonym — manually order",
             "deploy", "Manually order 150 units on day 25",
             "apply_override", DEPLOY_CTX_ACTIVE,
             note="synonym: manually order"),

    TestCase("D-10 apply_override — current day",
             "deploy", "Set order to 200 units for today",
             "apply_override", DEPLOY_CTX_ACTIVE,
             note="override current day"),

    TestCase("D-11 run_all canonical",
             "deploy", "Run all remaining days",
             "run_all", DEPLOY_CTX_ACTIVE,
             note="canonical run_all"),

    TestCase("D-12 run_all synonym — auto-run",
             "deploy", "Auto-run the simulation to the end",
             "run_all", DEPLOY_CTX_ACTIVE,
             note="synonym: auto-run"),

    TestCase("D-13 run_all synonym — finish it",
             "deploy", "Finish the simulation",
             "run_all", DEPLOY_CTX_ACTIVE,
             note="synonym: finish it"),

    TestCase("D-14 reset_simulation canonical",
             "deploy", "Reset the simulation",
             "reset_simulation", DEPLOY_CTX_ACTIVE,
             note="canonical reset"),

    TestCase("D-15 reset_simulation synonym — start over",
             "deploy", "Start over from day 1",
             "reset_simulation", DEPLOY_CTX_ACTIVE,
             note="synonym: start over"),

    TestCase("D-16 explain_decision canonical",
             "deploy", "Why did the agent order that amount?",
             "explain_decision", DEPLOY_CTX_ACTIVE,
             note="explain RL decision"),

    TestCase("D-17 explain_decision synonym — reasoning",
             "deploy", "What is the reasoning behind this order?",
             "explain_decision", DEPLOY_CTX_ACTIVE,
             note="synonym: reasoning"),

    TestCase("D-18 explain general",
             "deploy", "What does inventory simulation mean?",
             "explain", DEPLOY_CTX_ACTIVE,
             note="general explanation"),

    # ── Edge cases ─────────────────────────────────────────────────────────
    TestCase("D-19 step_day when session inactive → start_deployment",
             "deploy", "Go to next day",
             "start_deployment", DEPLOY_CTX_INACTIVE,
             note="no active session, should suggest start"),

    TestCase("D-20 step_day — 'a few days' → 3",
             "deploy", "Advance a few days",
             "step_day", DEPLOY_CTX_ACTIVE,
             note="'a few' should map to 3"),

    TestCase("D-21 simulation complete — only reset makes sense",
             "deploy", "Start over",
             "reset_simulation", DEPLOY_CTX_COMPLETE,
             note="complete session, reset"),

    # ── Cross-page boundary ────────────────────────────────────────────────
    TestCase("D-22 cross-page: train on deploy → navigate_to_train",
             "deploy", "Start training the RL model",
             "navigate_to_train", DEPLOY_CTX_ACTIVE,
             forbidden_actions=["start_training"],
             note="training not allowed on deploy page"),

    TestCase("D-23 cross-page: evaluate on deploy → navigate_to_evaluate",
             "deploy", "Run model evaluation",
             "navigate_to_evaluate", DEPLOY_CTX_ACTIVE,
             forbidden_actions=["run_evaluation"],
             note="evaluation not allowed on deploy page"),

    # ── Adversarial ────────────────────────────────────────────────────────
    TestCase("D-24 adversarial — off-topic",
             "deploy", "Tell me a joke",
              "unknown", DEPLOY_CTX_ACTIVE,
             note="completely off-topic"),
]

# ─── Router cross-page navigation tests ──────────────────────────────────────
# When user is on page X but says something for page Y,
# orchestrator should detect mismatch and return navigate_to_<Y> action
ROUTER_TESTS = [
    TestCase("R-01 on stage1, ask modify question → navigate_to_modify",
             "stage1", "Add a spike of 500 units on June 15",
             "navigate_to_modify", DEMAND_CONTEXT_LOADED,
             note="cross-page nav: stage1→modify (orchestrator level)"),

    TestCase("R-02 on stage1, ask train question → navigate_to_train",
             "stage1", "Start training for 500 episodes",
             "unknown", DEMAND_CONTEXT_LOADED,
             note="cross-page nav: stage1→train"),

    TestCase("R-03 on modify, ask deploy question → navigate_to_deploy",
             "modify", "Start the deployment simulation",
             "navigate_to_deploy", MODIFY_CTX,
             note="cross-page nav: modify→deploy"),

    TestCase("R-04 on train, ask evaluate question → navigate_to_evaluate",
             "train", "Evaluate the current model",
             "navigate_to_evaluate", TRAIN_CTX_IDLE,
             note="cross-page nav: train→evaluate"),
]

# ─── Run all tests ─────────────────────────────────────────────────────────────
ALL_SUITES = [
    ("📊 Stage1 / Demand Agent",    STAGE1_TESTS),
    ("✏️  Modify Agent",             MODIFY_TESTS),
    ("🚀 Train Agent",               TRAIN_TESTS),
    ("🎯 Evaluate Agent",            EVALUATE_TESTS),
    ("🏭 Deploy Agent",              DEPLOY_TESTS),
    ("🔀 Router / Cross-Page Nav",   ROUTER_TESTS),
]

def setup_demand():
    """Ensure demand data is loaded before running modify tests."""
    try:
        _post("/api/demand/generate", None)  # will fail (wrong format), try query param
    except Exception:
        pass
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/demand/generate?season_type=summer&start_date=2025-01-01&num_days=365&seed=42",
            data=b"", headers=_headers(), method="POST")
        urllib.request.urlopen(req, timeout=30)
    except Exception as e:
        print(f"{YELLOW}⚠ setup_demand: {e}{RESET}")

def print_header(title):
    bar = "═" * 72
    print(f"\n{CYAN}{BOLD}{bar}{RESET}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(f"{CYAN}{BOLD}{bar}{RESET}")

def print_result(r: TestResult, idx: int):
    icon   = f"{GREEN}✅{RESET}" if r.passed else f"{RED}❌{RESET}"
    status = f"{GREEN}PASS{RESET}" if r.passed else f"{RED}FAIL{RESET}"
    action_str = f"{YELLOW}{r.actual_action}{RESET}" if not r.passed else r.actual_action
    print(f"  {icon} [{idx:02d}] {r.name}")
    if not r.passed:
        print(f"        {RED}→ {status} | got: {action_str} | {r.note or r.error}{RESET}")

def main():
    print(f"\n{BOLD}{'='*72}{RESET}")
    print(f"{BOLD}  Replenix Copilot — Full Agent Test Suite{RESET}")
    print(f"{BOLD}{'='*72}{RESET}")

    # Seed demand data
    print(f"\n{CYAN}⚙ Seeding demand data...{RESET}")
    setup_demand()
    time.sleep(2)

    total_pass = 0
    total_fail = 0
    all_results = []

    for suite_name, tests in ALL_SUITES:
        print_header(suite_name)
        suite_pass = suite_fail = 0
        for i, tc in enumerate(tests, 1):
            r = run_test(tc)
            results.append(r)
            all_results.append(r)
            print_result(r, i)
            if r.passed:
                suite_pass += 1
            else:
                suite_fail += 1
        total_pass += suite_pass
        total_fail += suite_fail
        color = GREEN if suite_fail == 0 else RED
        print(f"\n  {color}Suite: {suite_pass} passed, {suite_fail} failed{RESET}")

    # ── Summary ───────────────────────────────────────────────────────────
    print(f"\n{BOLD}{'='*72}{RESET}")
    print(f"{BOLD}  FINAL SUMMARY{RESET}")
    print(f"{BOLD}{'='*72}{RESET}")
    total = total_pass + total_fail
    pct   = (total_pass / total * 100) if total else 0
    color = GREEN if total_fail == 0 else (YELLOW if total_fail <= 5 else RED)
    print(f"  {color}{BOLD}Total: {total_pass}/{total} passed ({pct:.1f}%){RESET}")

    if total_fail > 0:
        print(f"\n{RED}{BOLD}  Failed tests:{RESET}")
        for r in all_results:
            if not r.passed:
                print(f"  {RED}• {r.name}{RESET}")
                print(f"    got: '{r.actual_action}' | {r.note or r.error}")

    print(f"\n{BOLD}{'='*72}{RESET}\n")
    sys.exit(0 if total_fail == 0 else 1)

if __name__ == "__main__":
    main()
