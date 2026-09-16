"""
In-memory job store + the pipeline that ties transcription -> summarization -> PDF
together. Deliberately simple (a dict guarded by a lock) so this runs with zero
extra infrastructure; see README "Scaling beyond this demo" for the Redis/Celery
upgrade path once you need multiple backend replicas.
"""
import os
import threading
import traceback
import uuid
from typing import Dict, Optional

from app.config import settings
from app.pdf_export import render_pdf
from app.schemas import JobResult, JobStatus
from app.summarizer import summarize_transcript
from app.transcription import extract_audio, needs_conversion, transcribe

_jobs: Dict[str, dict] = {}
_lock = threading.Lock()


def _update(job_id: str, **kwargs):
    with _lock:
        _jobs[job_id].update(kwargs)


def create_job(filename: str) -> str:
    job_id = uuid.uuid4().hex[:12]
    with _lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "status": "queued",
            "progress": 0.0,
            "message": "Job queued.",
            "filename": filename,
            "result": None,
            "error": None,
        }
    return job_id


def get_status(job_id: str) -> Optional[JobStatus]:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        return JobStatus(
            job_id=job["job_id"],
            status=job["status"],
            progress=job["progress"],
            message=job.get("message"),
            filename=job.get("filename"),
        )


def get_result(job_id: str) -> Optional[JobResult]:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["status"] != "done":
            return None
        return job["result"]


def get_pdf_path(job_id: str) -> Optional[str]:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["status"] != "done":
            return None
        return job.get("pdf_path")


def get_transcript_path(job_id: str) -> Optional[str]:
    with _lock:
        job = _jobs.get(job_id)
        if not job or job["status"] != "done":
            return None
        return job.get("transcript_path")


def get_error(job_id: str) -> Optional[str]:
    with _lock:
        job = _jobs.get(job_id)
        return job.get("error") if job else None


def run_pipeline(job_id: str, input_path: str, original_filename: str):
    """Runs synchronously inside a FastAPI BackgroundTask (a separate thread from the
    request that kicked it off), updating job status as it progresses."""
    try:
        wav_path = os.path.join(settings.upload_dir, f"{job_id}.wav")

        _update(job_id, status="extracting_audio", progress=0.1, message="Extracting audio...")
        if needs_conversion(original_filename):
            extract_audio(input_path, wav_path)
        else:
            # Unknown extension: still try ffmpeg normalization, it's tolerant of most formats
            extract_audio(input_path, wav_path)

        _update(job_id, status="transcribing", progress=0.3, message="Transcribing audio (this can take a while)...")
        full_text, segments, duration = transcribe(wav_path)
        word_count = len(full_text.split())

        transcript_path = os.path.join(settings.results_dir, f"{job_id}_transcript.txt")
        with open(transcript_path, "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(f"[{seg.start:7.1f}s - {seg.end:7.1f}s]  {seg.text}\n")

        _update(job_id, status="summarizing", progress=0.7, message="Generating summary and action items...")
        summary, action_items, num_chunks = summarize_transcript(full_text)

        result = JobResult(
            job_id=job_id,
            filename=original_filename,
            duration_seconds=duration,
            word_count=word_count,
            num_chunks=num_chunks,
            summary=summary,
            action_items=action_items,
            transcript_preview=full_text[:1000],
        )

        pdf_path = os.path.join(settings.results_dir, f"{job_id}_report.pdf")
        render_pdf(
            pdf_path,
            filename=original_filename,
            summary=summary,
            action_items=action_items,
            duration_seconds=duration,
            word_count=word_count,
            num_chunks=num_chunks,
        )

        with _lock:
            _jobs[job_id].update(
                {
                    "status": "done",
                    "progress": 1.0,
                    "message": "Complete.",
                    "result": result,
                    "pdf_path": pdf_path,
                    "transcript_path": transcript_path,
                }
            )

    except Exception as e:
        traceback.print_exc()
        _update(
            job_id,
            status="error",
            progress=1.0,
            message="Processing failed.",
            error=str(e),
        )
    finally:
        # Clean up the raw upload + intermediate wav to save disk; keep transcript/pdf.
        for path in (input_path, os.path.join(settings.upload_dir, f"{job_id}.wav")):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
