"""
Lists the models your Groq API key currently has access to, so you can pick a
valid LLM_MODEL value instead of guessing (Groq's lineup changes frequently).

Run from the backend/ folder (with your venv active):
    python list_groq_models.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import settings

if not settings.groq_api_key:
    print("GROQ_API_KEY is not set in your .env file. Set it first, then re-run this.")
    sys.exit(1)

from groq import Groq

client = Groq(api_key=settings.groq_api_key)

try:
    models = client.models.list()
    print("Models available to your Groq account:\n")
    for m in models.data:
        active = getattr(m, "active", None)
        print(f"  - {m.id}" + (f"  (active: {active})" if active is not None else ""))
    print(
        "\nCopy one of the model IDs above into your .env file as:\n"
        "  LLM_MODEL=<model_id>"
    )
except Exception as e:
    print("Could not list models:", repr(e))