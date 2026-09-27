"""
Standalone diagnostic: tests ONLY the LLM connection, bypassing transcription/audio
entirely, so you can see the exact underlying error.

Run from the backend/ folder (with your venv active):
    python diagnose_llm.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

print(f"LLM_PROVIDER = {settings.llm_provider!r}")
print(f"LLM_MODEL    = {settings.llm_model!r}")

if settings.llm_provider == "groq":
    key = settings.groq_api_key
    print(f"GROQ_API_KEY set: {bool(key)}  (length: {len(key) if key else 0})")
elif settings.llm_provider == "openai":
    key = settings.openai_api_key
    print(f"OPENAI_API_KEY set: {bool(key)}  (length: {len(key) if key else 0})")
elif settings.llm_provider == "ollama":
    print(f"OLLAMA_BASE_URL = {settings.ollama_base_url}")

print("\nAttempting a real API call...\n")

try:
    from app.llm import get_chat_client

    client = get_chat_client()
    result = client.invoke(
        [{"role": "user", "content": "Reply with exactly one word: OK"}],
        max_tokens=10,
    )
    print("SUCCESS. Response:", result)
except Exception as e:
    print("FAILED with exception type:", type(e).__name__)
    print("Full error:", repr(e))
    import traceback
    traceback.print_exc()