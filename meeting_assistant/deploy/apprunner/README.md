# AWS App Runner deployment

App Runner builds/runs a container similarly to Cloud Run. Two ways to deploy:

## Option A: from source repo (App Runner builds the image for you)
Point App Runner at this repo, source directory `/`, and use `apprunner.yaml` (below)
to define the build/run commands. Note App Runner's source-based builds run from the
repo root, so this config assumes the Dockerfile approach (Option B) instead, which
gives more control over installing ffmpeg — **recommended**.

## Option B: from a pre-built image (recommended, since ffmpeg + faster-whisper need
the custom Dockerfile)

```bash
# Build & push to Amazon ECR
aws ecr create-repository --repository-name meeting-assistant-backend
export ECR_URI=$(aws ecr describe-repositories --repository-names meeting-assistant-backend --query 'repositories[0].repositoryUri' --output text)

aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URI
docker build -f backend/Dockerfile -t $ECR_URI:latest .
docker push $ECR_URI:latest

# Create the App Runner service
aws apprunner create-service \
  --service-name meeting-assistant-backend \
  --source-configuration '{
    "ImageRepository": {
      "ImageIdentifier": "'"$ECR_URI"':latest",
      "ImageRepositoryType": "ECR",
      "ImageConfiguration": {
        "Port": "8000",
        "RuntimeEnvironmentVariables": {
          "LLM_PROVIDER": "groq",
          "LLM_MODEL": "llama-3.1-70b-versatile",
          "WHISPER_MODEL_SIZE": "base",
          "WHISPER_DEVICE": "cpu",
          "WHISPER_COMPUTE_TYPE": "int8"
        },
        "RuntimeEnvironmentSecrets": {
          "GROQ_API_KEY": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:groq-api-key"
        }
      }
    },
    "AutoDeploymentsEnabled": true
  }' \
  --instance-configuration '{"Cpu": "2 vCPU", "Memory": "4 GB"}'
```

Notes:
- App Runner max instance size is 4 vCPU / 12 GB in most regions — plenty for
  `WHISPER_MODEL_SIZE=small` or below on CPU; use a GPU-based option
  (`deploy/ec2_runpod/`) for `medium`/`large-v3` at real-time speed.
- App Runner instances are also ephemeral like Cloud Run — same caveat about the
  in-memory job store applies (see main README's "Scaling beyond this demo").
- App Runner's default request timeout is 120s; since `/jobs` returns immediately
  and processing happens in a background task polled via separate `/jobs/{id}`
  requests, this is not usually a problem — just don't put the whole pipeline behind
  one synchronous request.

## apprunner.yaml (for the source-based build path, if you don't want to manage ECR)
```yaml
version: 1.0
runtime: docker
build:
  commands:
    build:
      - echo "Using backend/Dockerfile for the build"
run:
  runtime-version: latest
  command: uvicorn app.main:app --host 0.0.0.0 --port 8000
  network:
    port: 8000
  env:
    - name: LLM_PROVIDER
      value: "groq"
    - name: WHISPER_MODEL_SIZE
      value: "base"
```
