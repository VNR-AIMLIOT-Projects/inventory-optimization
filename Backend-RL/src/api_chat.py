import os
import json
import google.generativeai as genai

# Configure Gemini API - requires GEMINI_API_KEY environment variable
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is required. Please set it before running the application.")
genai.configure(api_key=api_key)
model = genai.GenerativeModel("gemini-2.5-flash")

SYSTEM_PROMPT = """You are an AI assistant that helps users modify inventory demand parameters.
The user will provide their current parameters as JSON and a natural language request.
Your job is to figure out EXACTLY what parameters need to change.

Return a JSON document with this exact structure:
{
  "reply": "A concise, industrial utilitarian confirmation of the changes made.",
  "updated_params": {
    // Only include fields that actually change
    "baseline": {"start": 500}, 
    "seasonal": {"peak": 800, "num_seasons": 2},
    "festival": {"num_festivals": 5},
    "spikes": [{"date": "2025-03-15", "amount": 300}]
  }
}

Available modification areas:
- baseline: {start, min, max, sigma}
- seasonal: {peak, num_seasons}
- festival: {peak, num_festivals}
- ramp_days
- spikes: [{date, amount}] // Use this for one-off demand spikes on specific dates

IMPORTANT RULES:
1. ONLY return valid JSON. Do not include markdown code blocks.
2. Keep the reply short and professional.
3. Only include the keys in "updated_params" that actually need modifications based on the user's request.
4. For requests like "add a spike of 300 units on 2025-03-15", use the "spikes" field as shown above.
"""

async def process_chat_modification(message: str, current_params: dict):
    prompt = f"{SYSTEM_PROMPT}\n\nCurrent Params: {json.dumps(current_params)}\n\nUser Request: {message}"
    
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            response_mime_type="application/json",
        ),
    )
    
    try:
        data = json.loads(response.text.strip())
        return data.get("reply", "Parameters updated."), data.get("updated_params", {})
    except Exception as e:
        raise ValueError(f"Failed to parse AI response: {e}\nRaw output: {response.text}")
