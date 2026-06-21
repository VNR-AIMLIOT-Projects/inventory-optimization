import os
import sys
import yaml
import pytest

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

@pytest.mark.skipif(os.environ.get("CI") == "true", reason="Skipping live LLM tests in CI to avoid rate limits")
@pytest.mark.parametrize("case", CASES, ids=idfn)
def test_copilot_routing_and_extraction(case):
    """
    Test the Universal Copilot's extraction, routing, and refusal
    logic across all 5 pages inside the backend.
    """
    # 1. Grab inputs from the test case format
    page = case["page"]
    message = case["message"]
    context = case.get("context", {})
    
    # 2. Call the real LLM endpoint function
    # Because we're connecting to Groq directly, ensure GROQ_API_KEY is loaded in your env
    # Note: handle_copilot_message is synchronous in copilot.py based on review,
    # if it uses async `await`, we should mark this test `async def` and `await handle_copilot_message` 
    # and use `pytest.mark.asyncio`. But copilot.py `handle_copilot_message` uses standard `client.chat.completions.create` it seems.
    result = handle_copilot_message(page, message, history=[], context=context)

    # 3. Core Assertions
    action = result.get("action", {})
    expected_action_type = case["expected_action"]
    
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
