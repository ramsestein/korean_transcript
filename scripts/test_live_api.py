"""
Live API Verification with Real API Keys
Tests OpenAI ASR, Soniox ASR, and LLM reconstruction with actual API calls.
"""

import asyncio
import io
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dotenv import load_dotenv

# Load API keys from .env
load_dotenv(Path(__file__).parent.parent / ".env")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
SONIOX_API_KEY = os.getenv("SONIOX_API_KEY")


def create_dummy_korean_wav() -> str:
    """Create a dummy 5-second WAV file for testing."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        wav_path = f.name
    
    # Create silent WAV 16kHz mono 5 seconds
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=16000:cl=mono",
        "-t", "5", "-acodec", "pcm_s16le", wav_path
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Create minimal valid WAV manually
        with open(wav_path, "wb") as f:
            # WAV header for 5s silence at 16kHz mono
            data_size = 16000 * 2 * 5  # samples * bytes_per_sample * seconds
            f.write(b"RIFF")
            f.write((data_size + 36).to_bytes(4, "little"))
            f.write(b"WAVE")
            f.write(b"fmt ")
            f.write((16).to_bytes(4, "little"))
            f.write((1).to_bytes(2, "little"))   # PCM
            f.write((1).to_bytes(2, "little"))   # Mono
            f.write((16000).to_bytes(4, "little"))
            f.write((32000).to_bytes(4, "little"))
            f.write((2).to_bytes(2, "little"))
            f.write((16).to_bytes(2, "little"))
            f.write(b"data")
            f.write((data_size).to_bytes(4, "little"))
            f.write(b"\x00" * data_size)
    
    return wav_path


async def test_openai_asr():
    """Test OpenAI ASR with real API."""
    print("\n[Test 1/4] OpenAI ASR (gpt-4o-transcribe)...")
    print("-" * 60)
    
    if not OPENAI_API_KEY:
        print("[SKIP] OPENAI_API_KEY not found")
        return False
    
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        wav_path = create_dummy_korean_wav()
        
        print(f"Uploading dummy audio: {wav_path}")
        start = time.time()
        
        with open(wav_path, "rb") as f:
            result = await client.audio.transcriptions.create(
                model="gpt-4o-transcribe",
                file=("test.wav", f, "audio/wav"),
                language="ko",
                response_format="text",
            )
        
        elapsed = time.time() - start
        Path(wav_path).unlink(missing_ok=True)
        
        print(f"[OK] OpenAI ASR responded in {elapsed:.2f}s")
        print(f"     Text: {result.text[:100] if result.text else '(empty)'}")
        return True
        
    except Exception as e:
        print(f"[FAIL] OpenAI ASR error: {e}")
        return False


async def test_soniox_asr():
    """Test Soniox ASR with real API."""
    print("\n[Test 2/4] Soniox ASR (stt-async-v4)...")
    print("-" * 60)
    
    if not SONIOX_API_KEY:
        print("[SKIP] SONIOX_API_KEY not found")
        return False
    
    try:
        import httpx
        
        wav_path = create_dummy_korean_wav()
        
        print(f"Uploading to Soniox: {wav_path}")
        start = time.time()
        
        async with httpx.AsyncClient() as client:
            # Soniox: Primero subir archivo, luego crear transcripción
            with open(wav_path, "rb") as f:
                # Step 1: Upload file
                upload_resp = await client.post(
                    "https://api.soniox.com/v1/files",
                    headers={"Authorization": f"Bearer {SONIOX_API_KEY}"},
                    files={"file": ("test.wav", f, "audio/wav")},
                    timeout=60
                )
            
            if upload_resp.status_code != 200:
                print(f"[FAIL] Soniox file upload failed: {upload_resp.status_code}")
                return False
            
            file_data = upload_resp.json()
            file_id = file_data.get("id") or file_data.get("file_id")
            
            # Step 2: Create transcription
            tx_resp = await client.post(
                "https://api.soniox.com/v1/transcriptions",
                headers={"Authorization": f"Bearer {SONIOX_API_KEY}"},
                json={
                    "file_id": file_id,
                    "model": "stt-async-v4",
                    "language_hints": ["ko"],
                    "enable_speaker_diarization": True,
                    "include_timestamps": True
                },
                timeout=60
            )
            
            if tx_resp.status_code == 200:
                tx_data = tx_resp.json()
                tx_id = tx_data.get("id") or tx_data.get("transcription_id")
                print(f"[OK] Soniox transcription created: {tx_id}")
                return True
            else:
                print(f"[FAIL] Soniox transcription creation failed: {tx_resp.status_code}")
                return False
        
        Path(wav_path).unlink(missing_ok=True)
        elapsed = time.time() - start
        
        if upload_resp.status_code == 200:
            data = upload_resp.json()
            print(f"[OK] Soniox ASR responded in {elapsed:.2f}s")
            print(f"     Status: {data.get('status', 'unknown')}")
            return True
        else:
            print(f"[FAIL] Soniox returned {upload_resp.status_code}: {upload_resp.text[:200]}")
            return False
            
    except Exception as e:
        print(f"[FAIL] Soniox ASR error: {e}")
        return False


async def test_openai_llm():
    """Test OpenAI LLM (gpt-4o) for Korean reconstruction."""
    print("\n[Test 3/4] OpenAI LLM (gpt-4o reconstruction)...")
    print("-" * 60)
    
    if not OPENAI_API_KEY:
        print("[SKIP] OPENAI_API_KEY not found")
        return False
    
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        prompt = """You are a Korean speech reconstruction expert.
Given these two ASR outputs:
OpenAI: "이 프로젝트 목표는 AI 기술을 활용하는 것입니다"
Soniox: "이 프로젝트 목표는 AI 기술을 활용하는 것입니다"

Return JSON:
{
  "reconstructed_ko": "reconstructed Korean text",
  "confidence": "high|medium|low",
  "uncertainties": []
}"""
        
        print("Sending reconstruction request...")
        start = time.time()
        
        response = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a Korean speech reconstruction expert."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        elapsed = time.time() - start
        result = response.choices[0].message.content
        
        print(f"[OK] gpt-4o responded in {elapsed:.2f}s")
        print(f"     Response preview: {result[:150]}")
        return True
        
    except Exception as e:
        print(f"[FAIL] LLM error: {e}")
        return False


async def test_openai_vision():
    """Test OpenAI Vision (gpt-4o-mini) for image context extraction."""
    print("\n[Test 4/4] OpenAI Vision (gpt-4o-mini)...")
    print("-" * 60)
    
    if not OPENAI_API_KEY:
        print("[SKIP] OPENAI_API_KEY not found")
        return False
    
    try:
        from openai import AsyncOpenAI
        
        client = AsyncOpenAI(api_key=OPENAI_API_KEY)
        
        # Create a simple 1x1 PNG
        import base64
        # Minimal valid 1x1 white PNG
        png_data = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        )
        
        print("Sending vision request with test image...")
        start = time.time()
        
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract visible text and technical terms from this image. Return JSON with fields: visible_text, entities, technical_terms"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64.b64encode(png_data).decode()}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )
        
        elapsed = time.time() - start
        result = response.choices[0].message.content
        
        print(f"[OK] gpt-4o-mini vision responded in {elapsed:.2f}s")
        print(f"     Response preview: {result[:150]}")
        return True
        
    except Exception as e:
        print(f"[FAIL] Vision error: {e}")
        return False


async def main():
    """Run all live API tests."""
    print("=" * 60)
    print("LIVE API VERIFICATION")
    print("Testing with REAL API keys from .env")
    print("=" * 60)
    
    # Check for API keys
    if not OPENAI_API_KEY:
        print("\n[ERROR] OPENAI_API_KEY not found in .env")
    if not SONIOX_API_KEY:
        print("\n[ERROR] SONIOX_API_KEY not found in .env")
    
    if not OPENAI_API_KEY and not SONIOX_API_KEY:
        print("\nNo API keys found. Exiting.")
        return 1
    
    results = []
    
    # Run tests
    results.append(("OpenAI ASR", await test_openai_asr()))
    results.append(("Soniox ASR", await test_soniox_asr()))
    results.append(("OpenAI LLM", await test_openai_llm()))
    results.append(("OpenAI Vision", await test_openai_vision()))
    
    # Summary
    print("\n" + "=" * 60)
    print("LIVE VERIFICATION SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "[OK]" if result else "[FAIL/SKIP]"
        print(f"{status} {name}")
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\n[OK] ALL LIVE TESTS PASSED - APIs are working!")
        return 0
    else:
        print(f"\n[WARN] {total - passed} tests failed or skipped")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
