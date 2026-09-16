# Build with the project root as context:
#   docker build -f backend/Dockerfile -t meeting-assistant-backend .
FROM python:3.11-slim

WORKDIR /app

# ffmpeg is required for audio/video extraction; build-essential for faster-whisper deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

ENV UPLOAD_DIR=/app/data/uploads
ENV RESULTS_DIR=/app/data/results
RUN mkdir -p /app/data/uploads /app/data/results

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "300"]
