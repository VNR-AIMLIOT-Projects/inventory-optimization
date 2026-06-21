import os
import sys
import yaml
import pytest
from unittest.mock import patch, MagicMock

# Add src package to path so we can import copilot directly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from services.chat.copilot import handle_copilot_message

# Load cases from yaml
def load_cases():
    yaml_path = os.path.join(os.path.dirname(__file__), "copilot_cases.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        cases = yaml.safe_load(f)
    return cases

CASES = load_cases()

# Create a test identifier from the name of the test
def idfn(case):
    return case["name"]

@pytest.mark.parametrize("case", CASES, ids=idfn)
@patch('services.chat.copilot._call_groq')
def test_copilot_routing_and_extraction(mock_call_groq, case):
    """
    Test the Universal Copilot's extraction, routing, and refusal
    logic across all 5 pages inside the backend.
    """
    # 1. Grab inputs from the test case format
    page = case["page"]
    message = case["message"]
    context = case.get("context", {})
    
    # 2. Mock the Groq response to return the expected json exactly
    import json
    
    # If the expected action requires a specific parameter, build that dict
    expected_action_type = case["expected_action"]
    mock_json_content = {
        "action": expected_action_type,
        "message": case.get("must_contain_text", "This is a mocked refusal or response.")
    }
    
    if "expected_params" in case:
        for k, v in case["expected_params"].items():
            mock_json_content[k] = v
            
    mock_call_groq.return_value = json.dumps(mock_json_content)

    # 3. Call the function which now hits the mock
    result = handle_copilot_message(page, message, history=[], context=context)

    # 4. Core Assertions
    action = result.get("action", {})
    
    # Check that it routed to the exactly correct tool/action
    assert action.get("action") == expected_action_type, \
        f"Expected tool '{expected_action_type}', but got '{action.get('action')}'"

    # 4. Parameter Assertions
    if "expected_params" in case:
        for param_key, expected_val in case["expected_params"].items():
            actual_val = action.get(param_key)
            assert actual_val == expected_val, \
                f"For parameter '{param_key}', expected {expected_val} but got {actual_val}."
                
    # 5. Assistant Message Fuzzy Text Assertions
    # Useful for checking if the model appropriately mentions why it refuses out-of-scope tools
    if "must_contain_text" in case:
        assistant_message = result.get("assistant_message", "").lower()
        must_contain = case["must_contain_text"].lower()
        assert must_contain in assistant_message, \
            f"Expected the assistant message to contain '{must_contain}'. Full message: '{result.get('assistant_message')}'"

def test_extract_json():
    from services.chat import copilot
    assert copilot._extract_json('{"test": 1}') == {"test": 1}
    assert copilot._extract_json('Here is json: ```{"test": 2}```') == {"test": 2}
    assert copilot._extract_json('Invalid') is None

@patch("os.environ.get")
def test_call_groq_no_api_key(mock_env):
    from services.chat import copilot
    mock_env.return_value = None
    with pytest.raises(RuntimeError, match="GROQ_API_KEY is not set"):
        copilot._call_groq("sys", "user", [])

@patch("os.environ.get")
def test_call_groq_success(mock_env):
    from services.chat import copilot
    mock_env.return_value = "fake-key"
    mock_groq = MagicMock()
    with patch.dict("sys.modules", {"groq": mock_groq}):
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'result'
        mock_client.chat.completions.create.return_value = mock_response
        
        res = copilot._call_groq("sys", "user", [{"role": "user", "content": "hist"}])
        assert res == "result"

def test_stage1():
    from services.chat import copilot
    context = {"has_file": True, "skus": ["A"], "current_sku": "A", "has_data": False}
    prompt = copilot._build_stage1_prompt(context)
    assert "Uploaded file  : true" in prompt
    assert "Available SKUs : A" in prompt
    
    assert copilot._stage1_to_human({"action": "generate_demand", "num_days": 10})[1] is True
    assert copilot._stage1_to_human({"action": "select_sku"})[1] is True
    assert copilot._stage1_to_human({"action": "navigate_to_modify"})[1] is False
    assert copilot._stage1_to_human({"action": "explain", "message": "msg"})[0] == "msg"
    assert copilot._stage1_to_human({"action": "unknown"})[1] is False
    assert copilot._stage1_to_human({"action": "other"})[1] is False

def test_modify():
    from services.chat import copilot
    context = {"params": {"baseline": {"start": 10}, "seasonal": {"periods": [{"start": "2025-01-01"}]}}}
    prompt = copilot._build_modify_prompt(context)
    assert "Baseline average demand : 10" in prompt
    
    assert copilot._modify_to_human({"action": "spike", "amount": 10})[1] is True
    assert copilot._modify_to_human({"action": "remove_units", "amount": 10})[1] is True
    assert copilot._modify_to_human({"action": "set_value", "amount": 10})[1] is True
    assert copilot._modify_to_human({"action": "scale", "factor": 1.2})[1] is True
    assert copilot._modify_to_human({"action": "adjust_range", "delta": -10})[1] is True
    assert copilot._modify_to_human({"action": "remove_spike"})[1] is True
    assert copilot._modify_to_human({"action": "set_baseline"})[1] is True
    assert copilot._modify_to_human({"action": "set_seasonal_peak"})[1] is True
    assert copilot._modify_to_human({"action": "set_festival_peak"})[1] is True
    assert copilot._modify_to_human({"action": "set_season_count"})[1] is True
    assert copilot._modify_to_human({"action": "set_festival_count"})[1] is True
    assert copilot._modify_to_human({"action": "reset"})[1] is True
    assert copilot._modify_to_human({"action": "unknown"})[1] is False
    assert copilot._modify_to_human({"action": "other"})[1] is True

def test_train():
    from services.chat import copilot
    prompt = copilot._build_train_prompt({"status": "running"})
    assert "Training status : running" in prompt
    
    assert "Starting training" in copilot._train_to_human({"action": "start_training"})[0]
    assert "Stopping training" in copilot._train_to_human({"action": "stop_training"})[0]
    assert "__STATUS__" in copilot._train_to_human({"action": "get_status"})[0]
    assert "Loading training run" in copilot._train_to_human({"action": "load_run"})[0]
    assert "msg" in copilot._train_to_human({"action": "explain", "message": "msg"})[0]
    assert "can only help" in copilot._train_to_human({"action": "unknown"})[0]
    assert "Done" in copilot._train_to_human({"action": "other"})[0]

def test_evaluate():
    from services.chat import copilot
    prompt = copilot._build_evaluate_prompt({"has_model": True, "rl_reward": 100})
    assert "Has trained model  : true" in prompt
    assert "RL reward          : 100.00" in prompt
    
    assert "Running evaluation" in copilot._evaluate_to_human({"action": "run_evaluation", "horizon_days": 10})[0]
    assert "all SKUs" in copilot._evaluate_to_human({"action": "run_multi_evaluation"})[0]
    assert "msg" in copilot._evaluate_to_human({"action": "explain_results", "message": "msg"})[0]
    assert "Simulation" in copilot._evaluate_to_human({"action": "navigate_to_deploy"})[0]
    assert "can only help" in copilot._evaluate_to_human({"action": "unknown"})[0]
    assert "Done" in copilot._evaluate_to_human({"action": "other"})[0]

def test_deploy():
    from services.chat import copilot
    prompt = copilot._build_deploy_prompt({"session_active": True})
    assert "Session active     : true" in prompt
    
    assert "Starting deployment" in copilot._deploy_to_human({"action": "start_deployment"})[0]
    assert "Advancing" in copilot._deploy_to_human({"action": "step_day", "num_days": 2})[0]
    assert "Override set" in copilot._deploy_to_human({"action": "apply_override", "day": 1, "override_qty": 10})[0]
    assert "Running simulation" in copilot._deploy_to_human({"action": "run_all"})[0]
    assert "Simulation reset" in copilot._deploy_to_human({"action": "reset_simulation"})[0]
    assert "msg" in copilot._deploy_to_human({"action": "explain_decision", "message": "msg"})[0]
    assert "can only help" in copilot._deploy_to_human({"action": "unknown"})[0]
    assert "Done" in copilot._deploy_to_human({"action": "other"})[0]

@patch("services.chat.copilot._call_groq")
def test_handle_copilot_message_edges(mock_call):
    from services.chat import copilot
    # Invalid page
    res = copilot.handle_copilot_message("invalid_page", "hi", {}, [])
    assert "Unknown page" in res["action"]["message"]
    
    # valid page
    mock_call.return_value = '{"action": "start_deployment"}'
    res = copilot.handle_copilot_message("deploy", "start", {}, [])
    assert res["action"]["action"] == "start_deployment"
    
    # Invalid JSON
    mock_call.return_value = 'not json'
    res = copilot.handle_copilot_message("deploy", "start", {}, [])
    assert res["action"]["action"] == "unknown"
    assert "could not parse" in res["action"]["message"]
    
    # Missing action key
    mock_call.return_value = '{"msg": "hi"}'
    res = copilot.handle_copilot_message("deploy", "start", {}, [])
    assert res["action"]["action"] == "unknown"
    assert "Unexpected" in res["action"]["message"]
    
    # Exception handling
    mock_call.side_effect = RuntimeError("API error")
    res = copilot.handle_copilot_message("deploy", "start", {}, [])
    assert res["action"]["action"] == "unknown"
    assert "API error" in res["action"]["message"]
    
    mock_call.side_effect = Exception("Generic")
    res = copilot.handle_copilot_message("deploy", "start", {}, [])
    assert res["action"]["action"] == "unknown"
    assert "AI service error" in res["action"]["message"]
