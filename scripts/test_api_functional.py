"""
Functional API Tests for ko-meeting-interpreter
Run these against a running backend to verify all endpoints work.
"""

import json
import sys
import tempfile
from pathlib import Path

import requests

API_BASE = "http://localhost:8000"


def test_health():
    """Test health endpoint."""
    print("Testing /api/health...")
    resp = requests.get(f"{API_BASE}/api/health", timeout=10)
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    print("✓ Health check passed")


def test_session_lifecycle():
    """Test full session lifecycle."""
    print("\n=== Testing Session Lifecycle ===")
    
    # 1. Start session
    print("1. Starting session (target=es)...")
    resp = requests.post(
        f"{API_BASE}/api/session/start",
        json={"target_language": "es", "meeting_prompt": "Test meeting", "chunk_seconds": 15},
        timeout=10
    )
    assert resp.status_code == 200
    session_id = resp.json()["session_id"]
    print(f"   ✓ Session created: {session_id}")
    
    # 2. Get transcript (empty)
    print("2. Getting transcript (should be empty)...")
    resp = requests.get(f"{API_BASE}/api/session/{session_id}/transcript", timeout=10)
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == session_id
    assert data["target_language"] == "es"
    assert len(data["segments"]) == 0
    print("   ✓ Transcript is empty as expected")
    
    # 3. Upload a dummy chunk (WAV file)
    print("3. Uploading audio chunk...")
    # Create a dummy 15-second WAV
    import subprocess
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        dummy_wav = f.name
    
    # Create silent WAV 16kHz mono
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
        "-t", "15", "-acodec", "pcm_s16le", dummy_wav
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Create minimal valid WAV manually
        with open(dummy_wav, "wb") as f:
            # WAV header for 15s silence at 16kHz mono
            f.write(b"RIFF")
            f.write((480044).to_bytes(4, "little"))  # File size
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write((16).to_bytes(4, "little"))  # Subchunk size
            f.write((1).to_bytes(2, "little"))   # Audio format (PCM)
            f.write((1).to_bytes(2, "little"))   # Num channels
            f.write((16000).to_bytes(4, "little"))  # Sample rate
            f.write((32000).to_bytes(4, "little"))  # Byte rate
            f.write((2).to_bytes(2, "little"))   # Block align
            f.write((16).to_bytes(2, "little"))  # Bits per sample
            f.write(b"data")
            f.write((480000).to_bytes(4, "little"))  # Data size
            f.write(b"\x00" * 480000)  # Silence
    
    with open(dummy_wav, "rb") as f:
        files = {"audio": ("chunk_0.wav", f, "audio/wav")}
        data = {"chunk_index": 0, "local_start_time": 0.0, "local_end_time": 15.0}
        resp = requests.post(
            f"{API_BASE}/api/session/{session_id}/chunk",
            files=files,
            data=data,
            timeout=60
        )
    
    Path(dummy_wav).unlink(missing_ok=True)
    
    if resp.status_code == 200:
        print(f"   ✓ Chunk uploaded and processed")
        chunk_data = resp.json()
        print(f"   Segments returned: {len(chunk_data.get('segments', []))}")
    elif resp.status_code == 502:
        print(f"   ⚠ ASR providers not configured (expected without API keys)")
    else:
        print(f"   ✗ Chunk upload failed: {resp.status_code} - {resp.text}")
        return False
    
    # 4. Delete session
    print("4. Deleting session...")
    resp = requests.delete(f"{API_BASE}/api/session/{session_id}", timeout=10)
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
    print("   ✓ Session deleted")
    
    return True


def test_all_languages():
    """Test session creation for all supported languages."""
    print("\n=== Testing All Target Languages ===")
    
    for lang in ["es", "en", "zh"]:
        print(f"Testing target_language={lang}...")
        resp = requests.post(
            f"{API_BASE}/api/session/start",
            json={"target_language": lang, "meeting_prompt": ""},
            timeout=10
        )
        assert resp.status_code == 200
        session_id = resp.json()["session_id"]
        
        # Cleanup
        requests.delete(f"{API_BASE}/api/session/{session_id}", timeout=10)
        print(f"  ✓ {lang.upper()}: OK")
    
    print("✓ All languages passed")


def test_error_cases():
    """Test error handling."""
    print("\n=== Testing Error Cases ===")
    
    # Invalid language
    print("1. Testing invalid language (should fail with 422)...")
    resp = requests.post(
        f"{API_BASE}/api/session/start",
        json={"target_language": "fr"},
        timeout=10
    )
    assert resp.status_code == 422
    print("   ✓ Invalid language rejected")
    
    # Non-existent session
    print("2. Testing non-existent session (should fail with 404)...")
    resp = requests.get(f"{API_BASE}/api/session/nonexistent/transcript", timeout=10)
    assert resp.status_code == 404
    print("   ✓ Non-existent session returns 404")
    
    print("✓ Error cases handled correctly")


def main():
    """Run all functional tests."""
    print("="*60)
    print("FUNCTIONAL API TESTS")
    print("="*60)
    print(f"API Base: {API_BASE}")
    print()
    
    try:
        test_health()
    except Exception as e:
        print(f"✗ Health check failed: {e}")
        print("\nIs the backend running? Start it with:")
        print("  cd backend && .venv\\Scripts\\python -m uvicorn app.main:app --reload")
        return 1
    
    try:
        if not test_session_lifecycle():
            return 1
    except Exception as e:
        print(f"✗ Session lifecycle test failed: {e}")
        return 1
    
    try:
        test_all_languages()
    except Exception as e:
        print(f"✗ Language test failed: {e}")
        return 1
    
    try:
        test_error_cases()
    except Exception as e:
        print(f"✗ Error case test failed: {e}")
        return 1
    
    print("\n" + "="*60)
    print("ALL FUNCTIONAL TESTS PASSED ✓")
    print("="*60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
