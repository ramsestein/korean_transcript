#!/usr/bin/env python3
"""
Direct Soniox API test - sends audio directly to Soniox API
and shows full response to diagnose issues.

Usage:
    python test_soniox_direct.py <audio_file.wav>

Requires SONIOX_API_KEY env var or will prompt.
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Any

import httpx

SONIOX_BASE_URL = "https://api.soniox.com/v1"
POLL_INTERVAL = 1.5
MAX_POLL_SECONDS = 120


def get_api_key() -> str:
    key = os.getenv("SONIOX_API_KEY", "")
    if not key:
        key = input("Enter your Soniox API key: ").strip()
    return key


async def upload_file(
    client: httpx.AsyncClient,
    audio_path: Path,
    api_key: str,
) -> str:
    print(f"📤 Uploading {audio_path.name} to Soniox...")
    
    with audio_path.open("rb") as f:
        response = await client.post(
            f"{SONIOX_BASE_URL}/files",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (audio_path.name, f, "audio/wav")},
        )
    
    print(f"   Upload status: {response.status_code}")
    data = response.json()
    print(f"   Response: {data}")
    
    response.raise_for_status()
    
    file_id = data.get("id") or data.get("file_id")
    if not file_id:
        raise ValueError(f"No file_id in response: {data}")
    
    print(f"   File ID: {file_id}")
    return str(file_id)


async def create_transcription(
    client: httpx.AsyncClient,
    file_id: str,
    api_key: str,
    model: str = "stt-async-v4",
    max_retries: int = 5,
) -> str:
    print(f"📝 Creating transcription job (model={model})...")
    
    payload = {
        "file_id": file_id,
        "model": model,
        "language_hints": ["ko"],
        "enable_speaker_diarization": True,
        "include_timestamps": True,
    }
    print(f"   Payload: {payload}")
    
    for attempt in range(max_retries):
        try:
            response = await client.post(
                f"{SONIOX_BASE_URL}/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            
            print(f"   Create status: {response.status_code}")
            data = response.json()
            
            # Check for resource_exhausted error
            if response.status_code == 429 or "resource_exhausted" in str(data):
                wait_time = 2 ** attempt  # Exponential backoff
                print(f"   ⚠️  Resource exhausted (attempt {attempt+1}/{max_retries}), waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            
            print(f"   Response: {data}")
            response.raise_for_status()
            
            tx_id = data.get("id") or data.get("transcription_id")
            if not tx_id:
                raise ValueError(f"No transcription_id in response: {data}")
            
            print(f"   Transcription ID: {tx_id}")
            return str(tx_id)
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and attempt < max_retries - 1:
                wait_time = 2 ** attempt
                print(f"   ⚠️  Rate limited (attempt {attempt+1}/{max_retries}), waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
                continue
            raise
    
    raise RuntimeError(f"Failed to create transcription after {max_retries} attempts")


async def poll_until_done(
    client: httpx.AsyncClient,
    transcription_id: str,
    api_key: str,
) -> dict[str, Any]:
    print(f"⏳ Polling for results (max {MAX_POLL_SECONDS}s)...")
    
    elapsed = 0.0
    while elapsed < MAX_POLL_SECONDS:
        response = await client.get(
            f"{SONIOX_BASE_URL}/transcriptions/{transcription_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        
        status = data.get("status", "")
        print(f"   [{elapsed:.1f}s] Status: {status}")
        
        if status in ("completed", "done", "finished"):
            print(f"   ✅ Transcription complete!")
            return data
        
        if status in ("failed", "error"):
            print(f"   ❌ Transcription failed!")
            print(f"   Full error response: {data}")
            raise RuntimeError(f"Soniox transcription failed: {data}")
        
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    
    raise TimeoutError(f"Did not complete within {MAX_POLL_SECONDS}s")


def tokens_to_text(tokens: list[dict[str, Any]]) -> str:
    parts = []
    for tok in tokens:
        text = tok.get("text", "") or tok.get("word", "")
        if text:
            parts.append(text)
    return "".join(parts).strip()


async def test_soniox(audio_path: Path):
    api_key = get_api_key()
    
    if not api_key:
        print("❌ No API key provided. Set SONIOX_API_KEY env var.")
        sys.exit(1)
    
    print(f"🔑 Using API key: {api_key[:10]}...")
    print(f"🎵 Audio file: {audio_path}")
    print(f"📏 File size: {audio_path.stat().st_size / 1024:.1f} KB")
    print()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Step 1: Upload
            file_id = await upload_file(client, audio_path, api_key)
            print()
            
            # Step 2: Create transcription
            transcription_id = await create_transcription(client, file_id, api_key)
            print()
            
            # Step 3: Poll for results
            result = await poll_until_done(client, transcription_id, api_key)
            print()
            
            # Step 4: Show results
            print("="*60)
            print("RESULTS")
            print("="*60)
            
            tokens = result.get("tokens", [])
            text = tokens_to_text(tokens)
            speakers = result.get("speakers", [])
            
            print(f"\n📊 Tokens: {len(tokens)}")
            print(f"📝 Text ({len(text)} chars):\n{text[:500]}{'...' if len(text) > 500 else ''}")
            print(f"\n🗣️ Speakers: {len(speakers)}")
            for spk in speakers:
                print(f"   - {spk.get('speaker', '?')}: {spk.get('text', '')[:100]}...")
            
            # Save full response
            output_file = Path("soniox_response.json")
            import json
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 Full response saved to: {output_file}")
            
        except httpx.HTTPStatusError as e:
            print(f"\n❌ HTTP Error: {e.response.status_code}")
            try:
                print(f"   Response: {e.response.json()}")
            except:
                print(f"   Response text: {e.response.text[:500]}")
        except Exception as e:
            print(f"\n❌ Error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()


def main():
    if len(sys.argv) < 2:
        print("Usage: python test_soniox_direct.py <audio_file.wav>")
        print("\nMake sure to set SONIOX_API_KEY environment variable")
        sys.exit(1)
    
    audio_path = Path(sys.argv[1])
    if not audio_path.exists():
        print(f"❌ File not found: {audio_path}")
        sys.exit(1)
    
    asyncio.run(test_soniox(audio_path))


if __name__ == "__main__":
    main()
