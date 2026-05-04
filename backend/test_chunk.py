"""Quick integration test for the chunk upload endpoint."""
import asyncio
import json
import random
import string
import urllib.error
import urllib.request
from pathlib import Path


def start_session():
    body = json.dumps({"target_language": "es", "meeting_prompt": "test", "chunk_seconds": 15}).encode()
    req = urllib.request.Request(
        "http://localhost:8080/api/session/start",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["session_id"]


def upload_chunk(sid, webm_path):
    boundary = "".join(random.choices(string.ascii_letters, k=16))
    audio_bytes = Path(webm_path).read_bytes()
    print(f"webm size: {len(audio_bytes):,} bytes")

    parts = []
    for name, val in [("chunk_index", "0"), ("local_start_time", "0.0"), ("local_end_time", "15.0")]:
        parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{val}\r\n".encode())
    parts.append(
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"chunk_0.webm\"\r\n"
        f"Content-Type: audio/webm\r\n\r\n".encode()
    )
    parts.append(audio_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    req = urllib.request.Request(
        f"http://localhost:8080/api/session/{sid}/chunk",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r2:
            resp = json.loads(r2.read())
        print(f"SUCCESS — status={resp.get('status')} segments={len(resp.get('segments', []))}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {body[:800]}")


if __name__ == "__main__":
    BASE = "http://localhost:8080"
    data = Path(r"C:\Users\Ramsés\Desktop\Proyectos\korean-transcript\data")
    webm_files = sorted(data.rglob("*.webm"), key=lambda x: x.stat().st_size, reverse=True)
    if not webm_files:
        print("No webm files found — record a chunk first")
        raise SystemExit(1)

    webm = webm_files[0]
    print(f"Using: {webm} ({webm.stat().st_size:,} bytes)")
    sid = start_session()
    print(f"Session: {sid}")
    upload_chunk(sid, webm)
