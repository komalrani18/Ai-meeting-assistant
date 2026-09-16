# AI Meeting Assistant — Transcription & Action Item Extractor

Upload a meeting recording (audio or video); get back a transcript, an executive
summary, and a structured list of action items ("who will do what by when") —
downloadable as a PDF.

## Architecture

```
Browser (Streamlit)
     │  POST /jobs  (multipart file upload)
     ▼
FastAPI backend
     │
     ├─ BackgroundTask kicks off async pipeline, returns job_id immediately
     │
     ▼
[1] extract_audio (ffmpeg, video → wav if needed)
     ▼
[2] transcribe (Faster-Whisper)              → full transcript + timestamped segments
     ▼
[3] chunk_transcript (overlapping word-count windows, only if transcript is long)
     ▼
[4] map: summarize each chunk → short bullet notes + candidate action items  (LLM)
     ▼
[5] reduce: combine chunk notes → final 3-sentence summary + deduped action items (LLM, strict JSON)
     ▼
[6] render_pdf (reportlab)
     ▼
Job store: status=done, result available at GET /jobs/{id}/result and /jobs/{id}/pdf

Frontend polls GET /jobs/{id} until status == "done", then renders + offers PDF download.
```

### Why chunking (map-reduce), not just "paste transcript into the LLM"
A 2-hour meeting can produce a transcript of 15,000-25,000+ words, which exceeds (or
eats most of) the context window of many models, and even when it fits, quality degrades
on very long single-shot summarization. This project splits the transcript into
overlapping chunks (default 1,400 words, 150-word overlap so no action item spanning a
chunk boundary gets lost), summarizes each chunk independently ("map"), then asks the
LLM to combine those chunk-level notes into one final summary + deduplicated action item
list ("reduce"). Short transcripts skip chunking entirely and go straight to a single
summarization call.

## Project layout

```
meeting_assistant/
├── backend/
│   ├── app/
│   │   ├── config.py         # env-driven settings (LLM provider, Whisper model size, etc.)
│   │   ├── llm.py            # LLM client factory: groq | openai | ollama
│   │   ├── schemas.py        # Pydantic models for job status/result
│   │   ├── transcription.py  # ffmpeg audio extraction + Faster-Whisper transcription
│   │   ├── chunking.py       # overlapping word-window chunker
│   │   ├── summarizer.py     # map-reduce summarization + action item extraction
│   │   ├── pdf_export.py     # renders the final report as a PDF (reportlab)
│   │   ├── jobs.py           # in-memory async job store + pipeline orchestration
│   │   └── main.py           # FastAPI app: upload, status, result, pdf endpoints
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── streamlit_app.py      # upload UI, polls job status, shows results, downloads PDF
│   ├── requirements.txt
│   └── Dockerfile
├── deploy/
│   ├── cloudrun/             # Google Cloud Run deploy notes + service config
│   ├── apprunner/            # AWS App Runner config
│   └── ec2_runpod/           # GPU deployment notes (EC2 g4dn / RunPod)
├── docker-compose.yml
└── .env.example
```

## Tech choices (all swappable via `.env`)

- **ASR**: `faster-whisper`, CTranslate2-optimized Whisper. Model size via
  `WHISPER_MODEL_SIZE` (`tiny`, `base`, `small`, `medium`, `large-v3`; default `base` —
  good speed/accuracy tradeoff on CPU). Device/compute type via `WHISPER_DEVICE`
  (`cpu`/`cuda`) and `WHISPER_COMPUTE_TYPE` (`int8` on CPU, `float16` on GPU).
- **LLM**: defaults to Groq's Llama 3.1 (`LLM_PROVIDER=groq`). Also supports
  `LLM_PROVIDER=openai` or `LLM_PROVIDER=ollama` (fully local, no API key).
- **Async processing**: FastAPI `BackgroundTasks` + an in-memory job dict. This is
  intentionally simple (no Redis/Celery) so the project runs with zero extra
  infrastructure; see "Scaling beyond this demo" below for the upgrade path.

## Quickstart (local, no Docker)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # fill in at least one LLM key
uvicorn app.main:app --reload --port 8000
```

Second terminal:

```bash
cd frontend
pip install -r requirements.txt
export BACKEND_URL=http://localhost:8000
streamlit run streamlit_app.py
```

Then open the Streamlit URL, upload an `.mp3`/`.wav`/`.mp4`/`.m4a` file, and watch it
process. First run will download the Whisper model weights (cached afterward).

## Quickstart (Docker Compose)

```bash
cp .env.example .env
docker compose up --build
# Streamlit UI:  http://localhost:8501
# Backend docs:  http://localhost:8000/docs
```

## API

- `POST /jobs` — multipart file upload (`file` field). Returns `{job_id, status}` immediately.
- `GET /jobs/{job_id}` — status + progress (`queued`, `extracting_audio`, `transcribing`,
  `summarizing`, `done`, `error`).
- `GET /jobs/{job_id}/result` — full JSON: transcript, summary, action items (once `done`).
- `GET /jobs/{job_id}/transcript` — plain-text transcript download.
- `GET /jobs/{job_id}/pdf` — the generated PDF report.

## Deployment

### Backend (needs more memory/CPU for Whisper)
- **Google Cloud Run**: see `deploy/cloudrun/` — set memory to at least 4Gi and CPU to
  2, and set `WHISPER_MODEL_SIZE=base` or smaller unless you provision a GPU-enabled
  Cloud Run instance.
- **AWS App Runner**: see `deploy/apprunner/apprunner.yaml` — similar memory/CPU notes.
- **GPU for fast transcription**: see `deploy/ec2_runpod/README.md` for an EC2 `g4dn.xlarge`
  or RunPod pod setup with `WHISPER_DEVICE=cuda`, `WHISPER_COMPUTE_TYPE=float16`.

### Frontend
Streamlit Community Cloud is the simplest free option for the Streamlit UI (point it
at this repo's `frontend/streamlit_app.py`, set the `BACKEND_URL` secret to your
deployed backend's URL). Vercel does not run long-lived Python/Streamlit processes
natively, so if you'd rather use Vercel, rebuild the frontend in React/Next.js calling
the same FastAPI endpoints (the API is framework-agnostic) — Render or Fly.io are also
good free/cheap options for hosting the Streamlit app itself if you stay with Python.

## Scaling beyond this demo

- **Job queue**: swap the in-memory dict in `jobs.py` for Redis + RQ/Celery once you
  need multiple backend replicas or durability across restarts.
- **Storage**: uploaded files and results currently live on local disk
  (`data/uploads/`, `data/results/`); move to S3/GCS for anything beyond a single-box demo.
- **Long meetings**: increase `CHUNK_WORDS`/`CHUNK_OVERLAP_WORDS` in `.env` if you want
  fewer, larger chunks (fewer LLM calls, more context loss risk) or the reverse.
- **Speaker labels**: this demo does not do speaker diarization. For "who said what",
  add a diarization step (e.g., `pyannote.audio`) between transcription and summarization,
  and merge speaker turns into the transcript before it reaches the LLM.
