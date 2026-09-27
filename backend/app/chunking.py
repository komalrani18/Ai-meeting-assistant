"""
Splits a long transcript into overlapping word-count windows so it fits comfortably
in the LLM's context per map-reduce step, without cutting an action item in half at
a chunk boundary (the overlap covers that).
"""
from typing import List

from app.config import settings


def needs_chunking(text: str) -> bool:
    return len(text.split()) > settings.chunk_threshold_words


def chunk_transcript(text: str, chunk_words: int = None, overlap_words: int = None) -> List[str]:
    chunk_words = chunk_words or settings.chunk_words
    overlap_words = overlap_words or settings.chunk_overlap_words

    words = text.split()
    if not words:
        return []

    step = max(chunk_words - overlap_words, 1)
    chunks = []
    for start in range(0, len(words), step):
        window = words[start : start + chunk_words]
        if not window:
            break
        chunks.append(" ".join(window))
        if start + chunk_words >= len(words):
            break
    return chunks
