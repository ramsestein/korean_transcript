"""
Streamlit Frontend for ko-meeting-interpreter
Real-time Korean meeting interpreter with live transcription and translation.
"""

import os
import time
from datetime import datetime
from typing import Any

import requests
import streamlit as st
from audio_recorder_streamlit import audio_recorder

# Configuration
API_BASE = os.getenv("API_BASE_URL", "http://localhost:8000")
CHUNK_SECONDS = 15

st.set_page_config(
    page_title="🇰🇷 Korean Meeting Interpreter",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session():
    """Initialize session state."""
    defaults = {
        "session_id": None,
        "target_language": None,
        "meeting_prompt": "",
        "recording": False,
        "chunks": [],
        "segments": [],
        "image_contexts": [],
        "summary_generated": False,
        "summary_url": None,
        "error": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


def start_session(lang: str, prompt: str) -> str | None:
    """Create a new session via backend API."""
    try:
        resp = requests.post(
            f"{API_BASE}/api/session/start",
            json={"target_language": lang, "meeting_prompt": prompt, "chunk_seconds": CHUNK_SECONDS},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()["session_id"]
    except Exception as e:
        st.session_state.error = f"Failed to start session: {e}"
        return None


def upload_chunk(audio_bytes: bytes, chunk_idx: int) -> dict | None:
    """Upload audio chunk to backend."""
    if not st.session_state.session_id:
        return None
    try:
        files = {"audio": (f"chunk_{chunk_idx}.wav", audio_bytes, "audio/wav")}
        data = {
            "chunk_index": chunk_idx,
            "local_start_time": chunk_idx * CHUNK_SECONDS,
            "local_end_time": (chunk_idx + 1) * CHUNK_SECONDS,
        }
        resp = requests.post(
            f"{API_BASE}/api/session/{st.session_state.session_id}/chunk",
            files=files,
            data=data,
            timeout=60,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.session_state.error = f"Chunk upload failed: {e}"
        return None


def upload_images(files: list) -> dict | None:
    """Upload image context to backend."""
    if not st.session_state.session_id:
        return None
    try:
        file_list = [("images", (f.name, f.getvalue(), f.type)) for f in files]
        resp = requests.post(
            f"{API_BASE}/api/session/{st.session_state.session_id}/context/images",
            files=file_list,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.session_state.error = f"Image upload failed: {e}"
        return None


def fetch_transcript() -> list[dict]:
    """Fetch current transcript from backend."""
    if not st.session_state.session_id:
        return []
    try:
        resp = requests.get(
            f"{API_BASE}/api/session/{st.session_state.session_id}/transcript",
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("segments", [])
    except Exception as e:
        st.session_state.error = f"Fetch transcript failed: {e}"
        return []


def generate_summary() -> str | None:
    """Request summary generation."""
    if not st.session_state.session_id:
        return None
    try:
        resp = requests.post(
            f"{API_BASE}/api/session/{st.session_state.session_id}/summary",
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("download_url")
    except Exception as e:
        st.session_state.error = f"Summary generation failed: {e}"
        return None


def delete_session():
    """Delete current session."""
    if st.session_state.session_id:
        try:
            requests.delete(
                f"{API_BASE}/api/session/{st.session_state.session_id}",
                timeout=10,
            )
        except Exception:
            pass  # Best effort
    # Clear session state
    for key in list(st.session_state.keys()):
        if key not in ["_is_running", "_script_run_ctx"]:
            del st.session_state[key]
    init_session()


def render_setup():
    """Render session setup panel."""
    st.header("🎙️ Session Setup")

    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🇪🇸 Spanish", use_container_width=True):
            st.session_state.target_language = "es"
    with col2:
        if st.button("🇬🇧 English", use_container_width=True):
            st.session_state.target_language = "en"
    with col3:
        if st.button("🇨🇳 Chinese", use_container_width=True):
            st.session_state.target_language = "zh"

    if st.session_state.target_language:
        st.success(f"Selected: {st.session_state.target_language.upper()}")

    st.session_state.meeting_prompt = st.text_area(
        "Meeting Context (optional)",
        placeholder="Describe the meeting topic, participants, domain, known terms...",
        height=100,
    )

    if st.button("🚀 Start Recording", type="primary", disabled=not st.session_state.target_language):
        session_id = start_session(st.session_state.target_language, st.session_state.meeting_prompt)
        if session_id:
            st.session_state.session_id = session_id
            st.session_state.recording = True
            st.rerun()


def render_recorder():
    """Render continuous audio recorder with auto-chunking."""
    st.header("🔴 Recording in Progress - Auto Mode")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.info(f"Session: `{st.session_state.session_id}` | Auto-recording every {CHUNK_SECONDS}s")
        st.caption("Click the microphone to start. Recording auto-stops every 15 seconds and restarts automatically.")

        # Track recording state and chunk index
        if "auto_chunk_idx" not in st.session_state:
            st.session_state.auto_chunk_idx = 0
        if "last_record_time" not in st.session_state:
            st.session_state.last_record_time = None

        # Audio recorder widget with auto-key for continuous recording
        key = f"audio_rec_{st.session_state.auto_chunk_idx}"
        audio_bytes = audio_recorder(
            text=f"Recording chunk #{st.session_state.auto_chunk_idx + 1}",
            recording_color="#e8b62c",
            neutral_color="#6aa36f",
            icon_name="microphone",
            icon_size="3x",
            key=key,
        )

        # Process recorded chunk and auto-continue
        if audio_bytes and st.session_state.last_record_time != id(audio_bytes):
            st.session_state.last_record_time = id(audio_bytes)
            chunk_idx = st.session_state.auto_chunk_idx

            with st.spinner(f"Processing chunk #{chunk_idx + 1}..."):
                result = upload_chunk(audio_bytes, chunk_idx)
                if result:
                    st.session_state.chunks.append({"idx": chunk_idx, "status": "done"})
                    st.session_state.auto_chunk_idx += 1
                    # Refresh segments
                    segments = fetch_transcript()
                    if segments:
                        st.session_state.segments = segments
                    st.success(f"Chunk #{chunk_idx + 1} processed! Auto-continuing...")
                    # Auto-continue after short delay
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Chunk upload failed. Check backend connection.")

        # Show recording status
        if st.session_state.chunks:
            st.metric("Chunks Recorded", len(st.session_state.chunks))

    with col2:
        st.subheader("Upload Context Images")
        uploaded = st.file_uploader(
            "Drop slide images here",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
        )
        if uploaded and st.button("📎 Upload Images"):
            with st.spinner("Extracting image context..."):
                result = upload_images(uploaded)
                if result:
                    st.session_state.image_contexts.extend(result.get("extracted", []))
                    st.success(f"Uploaded {len(uploaded)} images")

        st.divider()

        if st.button("⏹ Stop Recording", type="secondary", use_container_width=True):
            st.session_state.recording = False
            st.session_state.auto_chunk_idx = 0
            st.session_state.last_record_time = None
            st.rerun()


def render_transcript():
    """Render live transcript view."""
    if not st.session_state.segments:
        return

    st.subheader("📜 Live Transcript")

    for seg in reversed(st.session_state.segments[-10:]):  # Show last 10
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**🇰🇷** {seg.get('reconstructed_ko', '')}")
                st.markdown(f"**🌐** {seg.get('translated_text', '')}")
            with col2:
                confidence = seg.get('confidence', 'low')
                status_color = {'high': 'green', 'medium': 'orange', 'low': 'red'}.get(confidence, 'gray')
                st.markdown(f"**:{status_color}[{confidence.upper()}]**")
                st.caption(f"{seg.get('time_start', 0):.1f}s - {seg.get('time_end', 0):.1f}s")
            st.divider()


def render_summary():
    """Render summary panel after recording stops."""
    st.header("✅ Session Complete")

    col1, col2 = st.columns(2)

    with col1:
        if not st.session_state.summary_generated:
            if st.button("📄 Generate Operational Summary", type="primary"):
                with st.spinner("Generating summary..."):
                    url = generate_summary()
                    if url:
                        st.session_state.summary_url = url
                        st.session_state.summary_generated = True
                        st.rerun()
        else:
            st.success("Summary generated!")
            download_url = f"{API_BASE}/api/session/{st.session_state.session_id}/summary.md"
            st.markdown(f"[⬇️ Download summary.md]({download_url})")

    with col2:
        if st.button("🔄 New Session", type="secondary"):
            delete_session()
            st.rerun()


def main():
    init_session()

    st.title("🇰🇷 Korean Meeting Interpreter")
    st.caption("Real-time transcription, reconstruction, and translation")

    # Error display
    if st.session_state.error:
        st.error(st.session_state.error)
        st.session_state.error = None

    # Main UI flow
    if not st.session_state.session_id:
        render_setup()
    elif st.session_state.recording:
        render_recorder()
        render_transcript()

        # Auto-refresh transcript every 5 seconds
        time.sleep(5)
        segments = fetch_transcript()
        if segments and len(segments) != len(st.session_state.segments):
            st.session_state.segments = segments
            st.rerun()
    else:
        render_transcript()
        render_summary()


if __name__ == "__main__":
    main()
