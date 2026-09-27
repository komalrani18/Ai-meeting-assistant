# Deploying the backend to Google Cloud Run

Cloud Run is a good fit for the CPU-only version of this backend (Whisper `tiny`/`base`/
`small` models run acceptably on CPU; `medium`/`large-v3` will be slow without a GPU).

## 1. Build & push the image

```bash
export PROJECT_ID=your-gcp-project
export REGION=us-central1

gcloud auth configure-docker

docker build -f backend/Dockerfile -t gcr.io/$PROJECT_ID/meeting-assistant-backend .
docker push gcr.io/$PROJECT_ID/meeting-assistant-backend
```

## 2. Deploy

```bash
gcloud run deploy meeting-assistant-backend \
  --image gcr.io/$PROJECT_ID/meeting-assistant-backend \
  --region $REGION \
  --platform managed \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 900 \
  --concurrency 4 \
  --set-env-vars LLM_PROVIDER=groq,LLM_MODEL=llama-3.1-70b-versatile,WHISPER_MODEL_SIZE=base,WHISPER_DEVICE=cpu,WHISPER_COMPUTE_TYPE=int8 \
  --set-secrets GROQ_API_KEY=groq-api-key:latest
```

Notes:
- `--timeout 900` (15 min, Cloud Run's max) matters because transcription + summarization
  of a long meeting can take a while; the frontend polls asynchronously, but the initial
  `POST /jobs` request itself should return almost immediately (it just saves the file and
  schedules a background task) — the timeout mainly protects long-running requests, not
  the async job itself, but generous timeouts avoid edge cases on large uploads.
- `--concurrency 4` limits how many requests hit one instance at once; keep this low since
  Whisper transcription is CPU/memory heavy per request.
- Cloud Run instances are stateless/ephemeral — the in-memory job store in `jobs.py`
  and locally-saved PDFs/transcripts will NOT survive a cold start or scale-to-zero.
  For production, swap in Cloud SQL/Firestore for job state and GCS for file storage
  (see the main README's "Scaling beyond this demo" section), or pin `--min-instances 1`
  as a quick (non-durable) mitigation for a demo.
- Store secrets (`GROQ_API_KEY`, etc.) in Secret Manager and reference them with
  `--set-secrets` as shown, rather than plain env vars.
- Cloud Run does not currently support GPUs in the fully-managed environment; for GPU
  inference use Cloud Run's GPU preview (if available in your region) or see
  `deploy/ec2_runpod/README.md` for a GPU-based alternative.

## service.yaml (declarative alternative to the gcloud CLI command above)

Apply with `gcloud run services replace deploy/cloudrun/service.yaml`.
Update `PROJECT_ID` and the secret reference before applying.
