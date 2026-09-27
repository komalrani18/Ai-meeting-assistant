"""Pydantic models shared between jobs.py and main.py."""
from typing import List, Optional
from pydantic import BaseModel


class ActionItem(BaseModel):
    person: str
    action: str
    deadline: str


class TranscriptSegment(BaseModel):
    start: float
    end: float
    text: str


class JobStatus(BaseModel):
    job_id: str
    status: str  # queued | extracting_audio | transcribing | summarizing | done | error
    progress: float = 0.0
    message: Optional[str] = None
    filename: Optional[str] = None


class JobResult(BaseModel):
    job_id: str
    filename: str
    duration_seconds: Optional[float] = None
    word_count: int
    num_chunks: int
    summary: str
    action_items: List[ActionItem]
    transcript_preview: str  # first ~1000 chars, full transcript via /transcript endpoint
