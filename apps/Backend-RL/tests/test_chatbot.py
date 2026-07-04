import pytest
import json
import sys
from unittest.mock import patch, MagicMock

from services.chat import chatbot

def test_build_system_prompt_valid():
    params = {
        "baseline": {"start": 100},
        "seasonal": {"peak": 200, "periods": [{"start": "2025-06-01", "end": "2025-08-31"}]},
        "festival": {"peak": 300, "periods": [{"start": "2025-12-20", "end": "2025-12-25"}]},
        "num_days": 365
    }
    prompt = chatbot._build_system_prompt(params)
    assert "Baseline average demand : 100 units/day" in prompt
    assert "Seasonal peak demand    : 200 units/day" in prompt
    assert "Festival peak demand    : 300 units/day" in prompt
    assert "2025-06-01 to 2025-12-25" in prompt
    assert "Total days              : 365" in prompt

def test_build_system_prompt_empty_or_invalid():
    prompt = chatbot._build_system_prompt({})
    assert "Baseline average demand : unknown units/day" in prompt
    assert "2025-01-01 to 2025-12-31" in prompt
    
    # Trigger exception path (e.g. by passing None instead of dict to trigger AttributeError)
    prompt_exc = chatbot._build_system_prompt(None)
    assert "Baseline average demand : unknown units/day" in prompt_exc

def test_extract_json():
    # Valid JSON
    assert chatbot._extract_json('{"action": "spike"}') == {"action": "spike"}
    # Valid JSON with markdown
    assert chatbot._extract_json('```json\n{"action": "spike"}\n```') == {"action": "spike"}
    # Embedded JSON
    assert chatbot._extract_json('Here is the result: {"action": "scale", "factor": 1.2}') == {"action": "scale", "factor": 1.2}
    # Invalid
    assert chatbot._extract_json('No json here') is None
    # Embedded Invalid
    assert chatbot._extract_json('Here is { invalid }') is None

def test_parse_demand_intent_no_api_key():
    with patch("os.environ.get", return_value=None):
        res = chatbot.parse_demand_intent("hello", {})
        assert res["action"] == "unknown"
        assert "GROQ_API_KEY" in res["message"]

@patch("os.environ.get")
def test_parse_demand_intent_success(mock_env):
    mock_env.return_value = "fake-key"
    mock_groq = MagicMock()
    
    with patch.dict("sys.modules", {"groq": mock_groq}):
        # Setup mock Groq client
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"action": "spike", "amount": 100}'
        mock_client.chat.completions.create.return_value = mock_response
        
        res = chatbot.parse_demand_intent("Add 100 spike", {}, history=[{"role": "user", "content": "hello"}])
        assert res["action"] == "spike"
        assert res["amount"] == 100
        
        # Check history was passed correctly
        call_args = mock_client.chat.completions.create.call_args[1]
        messages = call_args["messages"]
        assert len(messages) == 3 # System, history, current
        assert messages[1]["content"] == "hello"

@patch("os.environ.get")
def test_parse_demand_intent_invalid_json(mock_env):
    mock_env.return_value = "fake-key"
    mock_groq = MagicMock()
    with patch.dict("sys.modules", {"groq": mock_groq}):
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = 'Not a json'
        mock_client.chat.completions.create.return_value = mock_response
        
        res = chatbot.parse_demand_intent("hello", {})
        assert res["action"] == "unknown"
        assert "could not parse" in res["message"]

@patch("os.environ.get")
def test_parse_demand_intent_missing_action(mock_env):
    mock_env.return_value = "fake-key"
    mock_groq = MagicMock()
    with patch.dict("sys.modules", {"groq": mock_groq}):
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"amount": 100}'
        mock_client.chat.completions.create.return_value = mock_response
        
        res = chatbot.parse_demand_intent("hello", {})
        assert res["action"] == "unknown"
        assert "unexpected response format" in res["message"]

@patch("os.environ.get")
def test_parse_demand_intent_import_error(mock_env):
    mock_env.return_value = "fake-key"
    
    # Simulate groq import failure by patching builtins.__import__
    original_import = __import__
    def mock_import(name, *args, **kwargs):
        if name == 'groq':
            raise ImportError("No module named groq")
        return original_import(name, *args, **kwargs)
        
    with patch("builtins.__import__", side_effect=mock_import):
        res = chatbot.parse_demand_intent("hello", {})
        assert res["action"] == "unknown"
        assert "not installed" in res["message"]

@patch("os.environ.get")
def test_parse_demand_intent_api_error(mock_env):
    mock_env.return_value = "fake-key"
    mock_groq = MagicMock()
    with patch.dict("sys.modules", {"groq": mock_groq}):
        mock_client = MagicMock()
        mock_groq.Groq.return_value = mock_client
        
        mock_client.chat.completions.create.side_effect = Exception("API down")
        
        res = chatbot.parse_demand_intent("hello", {})
        assert res["action"] == "unknown"
        assert "AI service error" in res["message"]

def test_action_to_human_message():
    assert "Added a demand spike" in chatbot.action_to_human_message({"action": "spike", "amount": 100})
    assert "Removed" in chatbot.action_to_human_message({"action": "remove_units", "amount": 100})
    assert "set to exactly" in chatbot.action_to_human_message({"action": "set_value", "amount": 100})
    
    assert "increased" in chatbot.action_to_human_message({"action": "scale", "factor": 1.2})
    assert "decreased" in chatbot.action_to_human_message({"action": "scale", "factor": 0.8})
    
    assert "Added" in chatbot.action_to_human_message({"action": "adjust_range", "delta": 10})
    assert "Removed" in chatbot.action_to_human_message({"action": "adjust_range", "delta": -10})
    
    assert "normalised" in chatbot.action_to_human_message({"action": "remove_spike"})
    assert "Baseline average demand" in chatbot.action_to_human_message({"action": "set_baseline", "value": 100})
    assert "Seasonal peak demand" in chatbot.action_to_human_message({"action": "set_seasonal_peak", "value": 100})
    assert "Festival peak demand" in chatbot.action_to_human_message({"action": "set_festival_peak", "value": 100})
    assert "Number of seasonal periods" in chatbot.action_to_human_message({"action": "set_season_count", "value": 100})
    assert "Number of festival periods" in chatbot.action_to_human_message({"action": "set_festival_count", "value": 100})
    assert "reset" in chatbot.action_to_human_message({"action": "reset"})
    assert "I could not understand" in chatbot.action_to_human_message({"action": "unknown"})
    assert "Action applied" in chatbot.action_to_human_message({"action": "some_new_action"})
