"""
Centralized, environment-driven configuration. Import `settings` everywhere else.
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    # --- LLM ---
    llm_provider: str = os.getenv("LLM_PROVIDER", "groq").lower()
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.1-70b-versatile")
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3")

    # --- Whisper ---
    whisper_model_size: str = os.getenv("WHISPER_MODEL_SIZE", "base")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "cpu")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    whisper_language: str = os.getenv("WHISPER_LANGUAGE", "") or None

    # --- Chunking ---
    chunk_words: int = int(os.getenv("CHUNK_WORDS", "1400"))
    chunk_overlap_words: int = int(os.getenv("CHUNK_OVERLAP_WORDS", "150"))
    chunk_threshold_words: int = int(os.getenv("CHUNK_THRESHOLD_WORDS", "1600"))

    # --- Storage ---
    upload_dir: str = os.getenv("UPLOAD_DIR", "./data/uploads")
    results_dir: str = os.getenv("RESULTS_DIR", "./data/results")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "500"))


settings = Settings()

os.makedirs(settings.upload_dir, exist_ok=True)
os.makedirs(settings.results_dir, exist_ok=True)
