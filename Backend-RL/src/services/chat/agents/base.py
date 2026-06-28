import os
import json
import re
import logging
import time
from typing import Optional
import groq

logger = logging.getLogger(__name__)

def extract_json(text: str) -> Optional[dict]:
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

def call_groq(system_prompt: str, user_message: str, history: list, retries: int = 5, model: str = "llama-3.1-8b-instant") -> str:
    """Call Groq with system prompt + history + user message. Returns raw string."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set in the backend environment.")

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
                model=model,
                messages=messages,
                temperature=0.0,
            )
            return (response.choices[0].message.content or "").strip()
        except groq.RateLimitError as e:
            if attempt == retries - 1:
                raise

            # Try to parse Groq's suggested wait time from the error message
            wait_time = 10 * (2 ** attempt)
            match = re.search(r"Please try again in ([\d.]+)s", str(e))
            if match:
                wait_time = float(match.group(1)) + 2.0

            logger.warning(f"Groq rate limit exceeded. Retrying in {wait_time}s... (Attempt {attempt+1}/{retries})")
            time.sleep(wait_time)

    return ""

def call_groq_with_rag(system_prompt: str, user_message: str, history: list, rag_chunks: list[str], model: str = "llama-3.3-70b-versatile") -> str:
    """Enhanced call_groq that injects RAG context into the system prompt."""
    
    rag_section = ""
    if rag_chunks:
        rag_section = (
            "\n\n═══════════════════════════════════════════\n"
            "HISTORICAL CONTEXT (from Replenix database)\n"
            "═══════════════════════════════════════════\n"
            + "\n---\n".join(rag_chunks)
            + "\n═══════════════════════════════════════════\n"
            "Use the above historical context to give more precise answers.\n"
            "Do not hallucinate data not present in the context above.\n"
        )
    
    enriched_prompt = system_prompt + rag_section
    return call_groq(enriched_prompt, user_message, history, model=model)
