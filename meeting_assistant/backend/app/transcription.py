"""
Converts uploaded audio/video into a 16kHz mono WAV (via ffmpeg) and runs
Faster-Whisper transcription on it, returning full text + timestamped segments.
"""
import subprocess
from functools import lru_cache
from typing import List, Tuple

from app.config import settings
from app.schemas import TranscriptSegment

VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"}


def needs_conversion(filename: str) -> bool:
    """Whisper/ffmpeg can technically read most formats directly, but we normalize
    everything to 16kHz mono WAV up front for consistent, fast decoding."""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in VIDEO_EXTENSIONS or ext in AUDIO_EXTENSIONS


def extract_audio(input_path: str, output_path: str) -> None:
    """Uses the ffmpeg CLI to extract/convert to 16kHz mono WAV — works for both
    pure audio files and video files (grabs the audio track)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vn",                 # drop video stream
        "-ac", "1",            # mono
        "-ar", "16000",        # 16kHz, what Whisper expects
        "-f", "wav",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {result.stderr[-2000:]}")


@lru_cache(maxsize=1)
def _get_model():
    from faster_whisper import WhisperModel

    return WhisperModel(
        settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


def transcribe(wav_path: str) -> Tuple[str, List[TranscriptSegment], float]:
    """Returns (full_text, segments, duration_seconds)."""
    model = _get_model()
    segments_iter, info = model.transcribe(
        wav_path,
        language=settings.whisper_language,
        vad_filter=True,             # skip silence, speeds things up and reduces hallucination
        beam_size=5,
    )

    segments: List[TranscriptSegment] = []
    text_parts: List[str] = []
    for seg in segments_iter:
        segments.append(TranscriptSegment(start=seg.start, end=seg.end, text=seg.text.strip()))
        text_parts.append(seg.text.strip())

    full_text = " ".join(text_parts).strip()
    duration = getattr(info, "duration", None)
    return full_text, segments, duration
