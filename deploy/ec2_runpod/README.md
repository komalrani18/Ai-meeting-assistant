# GPU deployment for fast transcription: AWS EC2 (g4dn) or RunPod

For real-time or faster-than-real-time transcription with the `medium`/`large-v3`
Whisper models, run on a GPU instance.

## Option A: AWS EC2 g4dn.xlarge (1x NVIDIA T4, 16GB VRAM)

```bash
# Launch a g4dn.xlarge with the AWS "Deep Learning AMI (Ubuntu)" — it ships with
# NVIDIA drivers + Docker + nvidia-container-toolkit preinstalled.

# On the instance:
git clone <your-repo-url> && cd meeting_assistant
cp .env.example .env
# Edit .env:
#   WHISPER_MODEL_SIZE=large-v3
#   WHISPER_DEVICE=cuda
#   WHISPER_COMPUTE_TYPE=float16

docker build -f backend/Dockerfile -t meeting-assistant-backend .
docker run --gpus all -p 8000:8000 --env-file .env meeting-assistant-backend
```

The Dockerfile in this repo installs the CPU-friendly `faster-whisper` package via
pip, which pulls in CUDA-enabled CTranslate2 wheels automatically when CUDA/cuDNN
are present on the host (as they are on the Deep Learning AMI + `--gpus all`); no
Dockerfile changes needed, just install CUDA/cuDNN on the host or use an
nvidia/cuda base image if you prefer a fully self-contained image (see Option B's
Dockerfile snippet, which also works fine on EC2).

Cost note: g4dn.xlarge is billed per-hour — stop the instance when not in use, or
put it behind an auto-scaling group that scales to zero, since this workload is
bursty (meetings aren't uploaded 24/7).

## Option B: RunPod (pay-per-second GPU pods, simpler to spin up/down)

1. Create a RunPod account, choose a pod template with CUDA + cuDNN (e.g., the
   "RunPod PyTorch" template) on an RTX 4090 or A4000 (both comfortably run
   `large-v3` in real time or faster).
2. Use this custom Dockerfile (CUDA base image) instead of the CPU one for your
   RunPod deployment:

```dockerfile
FROM nvidia/cuda:12.1.0-cudnn8-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY backend/app ./app
ENV WHISPER_DEVICE=cuda
ENV WHISPER_COMPUTE_TYPE=float16
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

3. Push the image to Docker Hub or the GitHub Container Registry, point your RunPod
   pod/template at it, expose port 8000 (RunPod's HTTP proxy or "Expose Port" setting),
   and set your `.env` vars (API keys, `WHISPER_MODEL_SIZE=large-v3`) as pod environment
   variables.
4. Point your frontend's `BACKEND_URL` at the RunPod-provided public endpoint URL.

## Choosing CPU vs GPU
- **CPU (Cloud Run / App Runner, `base`/`small` model)**: cheapest, fine for short
  meetings (< 30 min) or if a few minutes of processing latency is acceptable.
- **GPU (EC2 g4dn / RunPod, `large-v3` model)**: needed for near-real-time
  transcription of long meetings, or for the best transcription accuracy.
