"""
FastAPI backend for the AI Meeting Assistant.

Endpoints:
    GET  /health                       - liveness check
    POST /jobs                         - upload a recording, kicks off background processing
    GET  /jobs/{job_id}                - poll status/progress
    GET  /jobs/{job_id}/result         - full JSON result once done
    GET  /jobs/{job_id}/transcript     - plain-text transcript download
    GET  /jobs/{job_id}/pdf            - PDF report download
"""
import os
import uuid

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app import jobs
from app.config import settings
from app.schemas import JobResult, JobStatus

app = FastAPI(title="AI Meeting Assistant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

ALLOWED_EXTENSIONS = {
    "mp3", "wav", "m4a", "flac", "ogg", "aac",   # audio
    "mp4", "mov", "mkv", "avi", "webm",           # video (audio track extracted)
}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/jobs", response_model=JobStatus)
async def upload_job(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if "." not in file.filename:
        raise HTTPException(status_code=400, detail="File has no extension.")
    ext = file.filename.rsplit(".", 1)[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '.{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.max_upload_mb:
        raise HTTPException(
            status_code=413,
            detail=f"File is {size_mb:.1f}MB, exceeds the {settings.max_upload_mb}MB limit.",
        )

    job_id = jobs.create_job(filename=file.filename)
    input_path = os.path.join(settings.upload_dir, f"{job_id}_{uuid.uuid4().hex[:6]}.{ext}")
    with open(input_path, "wb") as f:
        f.write(contents)

    background_tasks.add_task(jobs.run_pipeline, job_id, input_path, file.filename)

    return JobStatus(job_id=job_id, status="queued", progress=0.0, message="Job queued.", filename=file.filename)


@app.get("/jobs/{job_id}", response_model=JobStatus)
def job_status(job_id: str):
    status = jobs.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found.")
    if status.status == "error":
        status.message = jobs.get_error(job_id) or "Processing failed."
    return status


@app.get("/jobs/{job_id}/result", response_model=JobResult)
def job_result(job_id: str):
    status = jobs.get_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found.")
    if status.status == "error":
        raise HTTPException(status_code=500, detail=jobs.get_error(job_id) or "Processing failed.")
    if status.status != "done":
        raise HTTPException(status_code=409, detail=f"Job not finished yet (status: {status.status}).")

    result = jobs.get_result(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Result not found.")
    return result


@app.get("/jobs/{job_id}/pdf")
def job_pdf(job_id: str):
    path = jobs.get_pdf_path(job_id)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="PDF not available (job not finished or not found).")
    return FileResponse(path, media_type="application/pdf", filename=os.path.basename(path))


@app.get("/jobs/{job_id}/transcript")
def job_transcript(job_id: str):
    path = jobs.get_transcript_path(job_id)
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Transcript not available (job not finished or not found).")
    return FileResponse(path, media_type="text/plain", filename=os.path.basename(path))
