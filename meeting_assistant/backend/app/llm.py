"""
Provider-agnostic LLM chat client (Groq / OpenAI / Ollama), same pattern used
across the pipeline so summarizer.py doesn't need to know which provider is active.
"""
from app.config import settings


def get_chat_client():
    """Returns an object with `.invoke(messages: list[dict]) -> str`."""
    provider = settings.llm_provider

    if provider == "groq":
        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)

        class _GroqChat:
            def invoke(self, messages, temperature=0.2, max_tokens=1500):
                resp = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content

        return _GroqChat()

    if provider == "openai":
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)

        class _OpenAIChat:
            def invoke(self, messages, temperature=0.2, max_tokens=1500):
                resp = client.chat.completions.create(
                    model=settings.llm_model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content

        return _OpenAIChat()

    if provider == "ollama":
        import requests

        class _OllamaChat:
            def invoke(self, messages, temperature=0.2, max_tokens=1500):
                resp = requests.post(
                    f"{settings.ollama_base_url}/api/chat",
                    json={
                        "model": settings.ollama_model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature},
                    },
                    timeout=300,
                )
                resp.raise_for_status()
                return resp.json()["message"]["content"]

        return _OllamaChat()

    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
