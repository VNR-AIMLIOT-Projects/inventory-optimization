# Universal Copilot Test Suite Design

## 1. Understanding Summary
- **What is being built:** A data-driven, automated `pytest` suite for the `copilot.py` backend module.
- **Why it exists:** To systematically verify LLM routing, parameter extraction, and strict refusal of out-of-scope tools (preventing hallucinations) across the 5 page contexts.
- **Who it is for:** Developers to safely refactor and tune system prompts without breaking existing functionality.
- **Key constraints:** Must run against the live Groq API. Must be resilient to slight verbiage changes in LLM text (fuzzy matching).
- **Explicit non-goals:** Not testing UI elements, React state, or the actual model training code—purely testing the LLM's JSON action generation.

## 2. Assumptions
- **API Usage:** Tests will consume actual Groq API credits.
- **Rate Limiting:** We rely on the speed of standard `pytest` sequential execution (or slight delays) to avoid hitting Groq API rate limits during bulk runs.
- **Data Storage:** Test scenarios will be stored in a declarative `yaml` format so non-engineers can add edge cases easily.

## 3. Decision Log
- **Decision 1:** Use `pytest` parameterized with a YAML file instead of a custom batch runner script.
  * *Why:* Integrates naturally with Python CI/CD, leverages existing assertion frameworks, and separates test data from test logic.
- **Decision 2:** Use fuzzy assertions for text, but strict assertions for JSON `action["type"]` and `action["params"]`.
  * *Why:* LLMs vary in their conversational text ("Sure, I can help!" vs "Done!"), but the required JSON payload for our frontend must always be perfectly structured.

## 4. Final Design

### Directory Structure
```text
Backend-RL/
  tests/
    test_copilot.py          # The pytest runner script
    copilot_cases.yaml       # The declarative test scenarios
```

### Scenario YAML Format (`copilot_cases.yaml`)
Defines the `page`, frontend `context`, user `message`, and the `expected_action` structure.

```yaml
- name: "Cross-page Hallucination Test (Stage 1)"
  page: "stage1"
  context: { "has_data": true }
  message: "Start training the model with 500 episodes"
  expected_action: "chat" # Must refuse tool execution
  must_contain_text: "training"

- name: "Valid Tool Execution (Modify Page)"
  page: "modify"
  context: { "sku": "summer-pack" }
  message: "Spike the demand by 20% starting tomorrow for 5 days"
  expected_action: "apply_spike"
  expected_params: 
    percentage: 20
    duration: 5
```

### Pytest Logic (`test_copilot.py`)
1. Parses `copilot_cases.yaml`.
2. Uses `@pytest.mark.parametrize` to loop over every test case.
3. Invokes `handle_copilot_message(page, message, history=[], context)`.
4. Asserts `action["type"] == case["expected_action"]`.
5. If `expected_params` exists, asserts that all key-values match the extracted parameters.
6. If `must_contain_text` exists, asserts the assistant's message contains the keyword (case-insensitive).
