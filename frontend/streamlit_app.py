"""
Streamlit frontend for the AI Meeting Assistant.
Uploads a recording, polls the backend job status, and renders the summary,
action items table, and download buttons once processing finishes.
"""
import os
import time

import requests
import streamlit as st

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

st.set_page_config(page_title="AI Meeting Assistant", page_icon="🎙️", layout="centered")
st.title("🎙️ AI Meeting Assistant")
st.caption("Upload a meeting recording to get a transcript, executive summary, and action items.")

STATUS_LABELS = {
    "queued": "Queued...",
    "extracting_audio": "Extracting audio...",
    "transcribing": "Transcribing (Faster-Whisper)...",
    "summarizing": "Summarizing & extracting action items...",
    "done": "Done!",
    "error": "Failed.",
}

with st.sidebar:
    st.subheader("Backend status")
    try:
        requests.get(f"{BACKEND_URL}/health", timeout=5).raise_for_status()
        st.success("Backend reachable")
    except Exception:
        st.error(f"Cannot reach backend at {BACKEND_URL}")
    st.caption(
        "First transcription after backend startup can be slow while the Whisper "
        "model weights download and load."
    )

if "job_id" not in st.session_state:
    st.session_state.job_id = None

uploaded = st.file_uploader(
    "Upload meeting recording",
    type=["mp3", "wav", "m4a", "flac", "ogg", "aac", "mp4", "mov", "mkv", "avi", "webm"],
)

col1, col2 = st.columns([1, 1])
with col1:
    start_clicked = st.button("Process recording", type="primary", disabled=uploaded is None)
with col2:
    if st.button("Reset"):
        st.session_state.job_id = None
        st.rerun()

if start_clicked and uploaded is not None:
    with st.spinner("Uploading..."):
        try:
            files = {"file": (uploaded.name, uploaded.getvalue())}
            resp = requests.post(f"{BACKEND_URL}/jobs", files=files, timeout=120)
            resp.raise_for_status()
            st.session_state.job_id = resp.json()["job_id"]
        except Exception as e:
            st.error(f"Upload failed: {e}")

if st.session_state.job_id:
    job_id = st.session_state.job_id
    status_placeholder = st.empty()
    progress_bar = st.progress(0.0)

    final_status = None
    while True:
        try:
            resp = requests.get(f"{BACKEND_URL}/jobs/{job_id}", timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            status_placeholder.error(f"Lost connection to backend: {e}")
            break

        status = data["status"]
        progress_bar.progress(min(data.get("progress", 0.0), 1.0))
        status_placeholder.info(f"**{STATUS_LABELS.get(status, status)}** — {data.get('message', '')}")

        if status in ("done", "error"):
            final_status = status
            break
        time.sleep(2)

    if final_status == "error":
        st.error(f"Processing failed: {data.get('message', 'unknown error')}")

    elif final_status == "done":
        try:
            result = requests.get(f"{BACKEND_URL}/jobs/{job_id}/result", timeout=10).json()
        except Exception as e:
            st.error(f"Could not fetch result: {e}")
            result = None

        if result:
            st.success("Processing complete!")

            meta_cols = st.columns(3)
            duration = result.get("duration_seconds")
            meta_cols[0].metric("Duration", f"{duration/60:.1f} min" if duration else "—")
            meta_cols[1].metric("Transcript length", f"{result['word_count']} words")
            meta_cols[2].metric("Chunks processed", result["num_chunks"])

            st.subheader("Executive Summary")
            st.write(result["summary"])

            st.subheader("Action Items")
            action_items = result.get("action_items", [])
            if action_items:
                st.table(
                    [
                        {"Person": a["person"], "Action": a["action"], "Deadline": a["deadline"]}
                        for a in action_items
                    ]
                )
            else:
                st.caption("No action items were identified in this meeting.")

            with st.expander("Transcript preview"):
                st.text(result["transcript_preview"] + ("..." if len(result["transcript_preview"]) >= 1000 else ""))

            dl_cols = st.columns(2)
            with dl_cols[0]:
                try:
                    pdf_bytes = requests.get(f"{BACKEND_URL}/jobs/{job_id}/pdf", timeout=30).content
                    st.download_button(
                        "📄 Download PDF report", data=pdf_bytes,
                        file_name=f"meeting_report_{job_id}.pdf", mime="application/pdf",
                    )
                except Exception:
                    st.caption("PDF not available.")
            with dl_cols[1]:
                try:
                    txt_bytes = requests.get(f"{BACKEND_URL}/jobs/{job_id}/transcript", timeout=30).content
                    st.download_button(
                        "📝 Download full transcript", data=txt_bytes,
                        file_name=f"transcript_{job_id}.txt", mime="text/plain",
                    )
                except Exception:
                    st.caption("Transcript not available.")
