#!/usr/bin/env python3
"""
Test script to download Korean audio from YouTube and upload to API
Tests both OpenAI Whisper and Soniox ASR models

Requirements:
    pip install yt-dlp requests

Usage:
    python test_korean_audio.py
    
Or with specific YouTube URL:
    python test_korean_audio.py "https://youtube.com/watch?v=..."
"""

import os
import sys
import json
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

# Configuration
# Default to production URL - override with env var if testing locally
BASE_URL = os.getenv("API_URL", "https://korean-transcript.sliplane.app")
TOKEN = os.getenv("AUTH_TOKEN", "disabled")  # Set your auth token here if needed

# Korean test videos (news, podcasts, etc.)
# These are Korean news/educational videos that should be available
KOREAN_TEST_VIDEOS = [
    "https://www.youtube.com/watch?v=0p8UlxI1z2o",  # Korean news clip
    "https://www.youtube.com/watch?v=K0xL8uK1vtw",  # Korean learning content
    "https://www.youtube.com/watch?v=1FPIVjSTW4E",  # Korean conversation
]


def create_session(language="es", prompt="Test session with Korean audio"):
    """Create a new session via API"""
    url = f"{BASE_URL}/api/session/start"
    headers = {}
    if TOKEN and TOKEN != "disabled":
        headers["Authorization"] = f"Bearer {TOKEN}"
    
    payload = {
        "target_language": language,
        "meeting_prompt": prompt,
        "chunk_seconds": 15
    }
    
    resp = requests.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    session_id = data["session_id"]
    print(f"✅ Created session: {session_id}")
    return session_id


def download_youtube_audio(youtube_url, output_dir):
    """Download audio from YouTube video using yt-dlp Python API"""
    print(f"\n📥 Downloading audio from: {youtube_url}")
    
    try:
        import yt_dlp
    except ImportError:
        print("❌ yt-dlp not found. Install with: pip install yt-dlp")
        sys.exit(1)
    
    output_template = os.path.join(output_dir, "%(title)s.%(ext)s")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '0',
        }],
        'outtmpl': output_template,
        'noplaylist': True,
        'quiet': False,
        'no_warnings': False,
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            title = info.get('title', 'unknown')
            print(f"✅ Downloaded: {title}")
        
        # Find the downloaded file
        files = list(Path(output_dir).glob("*.mp3"))
        if files:
            return str(files[0])
        else:
            raise FileNotFoundError("No audio file found after download")
    except Exception as e:
        print(f"❌ Download failed: {e}")
        raise


def split_audio(audio_path, output_dir, chunk_seconds=15):
    """Split audio into chunks using ffmpeg"""
    print(f"\n✂️  Splitting audio into {chunk_seconds}s chunks...")
    
    chunk_dir = Path(output_dir) / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    
    # Use ffmpeg to split
    output_pattern = str(chunk_dir / "chunk_%03d.webm")
    cmd = [
        "ffmpeg",
        "-i", audio_path,
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-c", "copy",
        "-reset_timestamps", "1",
        output_pattern
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Get list of chunks
        chunks = sorted(chunk_dir.glob("chunk_*.webm"))
        print(f"✅ Created {len(chunks)} chunks")
        return chunks
    except subprocess.CalledProcessError as e:
        print(f"❌ Split failed: {e.stderr}")
        raise
    except FileNotFoundError:
        print("❌ ffmpeg not found. Please install ffmpeg")
        sys.exit(1)


def upload_chunk(session_id, chunk_path, chunk_index, start_time, end_time):
    """Upload a single chunk to the API"""
    url = f"{BASE_URL}/api/session/{session_id}/chunk"
    headers = {}
    if TOKEN and TOKEN != "disabled":
        headers["Authorization"] = f"Bearer {TOKEN}"
    
    files = {
        "audio": (f"chunk_{chunk_index}.webm", open(chunk_path, "rb"), "audio/webm")
    }
    data = {
        "chunk_index": chunk_index,
        "local_start_time": start_time,
        "local_end_time": end_time
    }
    
    resp = requests.post(url, files=files, data=data, headers=headers)
    files["audio"][1].close()
    
    resp.raise_for_status()
    return resp.json()


def process_chunks(session_id, chunks):
    """Upload all chunks and show results"""
    print(f"\n📤 Uploading {len(chunks)} chunks to API...\n")
    
    results = []
    for i, chunk_path in enumerate(chunks):
        start_time = i * 15  # 15 second chunks
        end_time = start_time + 15
        
        print(f"Chunk {i}: {chunk_path.name}...", end=" ")
        
        try:
            result = upload_chunk(session_id, chunk_path, i, start_time, end_time)
            
            # Check which ASR models responded
            segments = result.get("segments", [])
            if segments:
                seg = segments[0]  # First segment of this chunk
                asr_sources = seg.get("asr_sources", [])
                openai_text = seg.get("openai_asr_ko", "")[:30] + "..." if seg.get("openai_asr_ko") else "(no text)"
                soniox_text = seg.get("soniox_asr_ko", "")[:30] + "..." if seg.get("soniox_asr_ko") else "(no text)"
                
                status = "🔵🔵" if len(asr_sources) == 2 else "🔵⚪" if "openai" in asr_sources else "⚪🔵" if "soniox" in asr_sources else "⚪⚪"
                print(f"✅ {status} | OpenAI: {openai_text} | Soniox: {soniox_text}")
            else:
                print("⚠️  No segments returned")
            
            results.append(result)
            
            # Small delay to not overwhelm the API
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Failed: {e}")
    
    return results


def print_summary(session_id, results):
    """Print summary of ASR results"""
    print(f"\n{'='*60}")
    print(f"SUMMARY FOR SESSION: {session_id}")
    print(f"{'='*60}")
    
    both = sum(1 for r in results for s in r.get("segments", []) if len(s.get("asr_sources", [])) == 2)
    only_openai = sum(1 for r in results for s in r.get("segments", []) if s.get("asr_sources", []) == ["openai"])
    only_soniox = sum(1 for r in results for s in r.get("segments", []) if s.get("asr_sources", []) == ["soniox"])
    none_count = sum(1 for r in results for s in r.get("segments", []) if len(s.get("asr_sources", [])) == 0)
    
    print(f"\nSegments processed: {len(results)}")
    print(f"  🔵🔵 Both ASR models:    {both}")
    print(f"  🔵⚪ Only OpenAI:        {only_openai}")
    print(f"  ⚪🔵 Only Soniox:         {only_soniox}")
    print(f"  ⚪⚪ None (no speech?):   {none_count}")
    
    # Check overall health
    total = len(results)
    if total > 0:
        coverage = (both + only_openai + only_soniox) / total * 100
        print(f"\n🎯 Speech detection rate: {coverage:.1f}%")
        
        if both >= total * 0.5:
            print("✅ EXCELLENT: Both models working well")
        elif both + only_openai + only_soniox >= total * 0.7:
            print("✅ GOOD: Most speech detected")
        else:
            print("⚠️  WARNING: Low speech detection rate")


def main():
    # Check arguments
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
        # Check if it's a local file or URL
        if input_path.startswith('http'):
            source_type = 'youtube'
            youtube_url = input_path
        elif Path(input_path).exists():
            source_type = 'local'
            local_audio_path = input_path
        else:
            print(f"❌ Path not found: {input_path}")
            print("Usage: python test_korean_audio.py [YOUTUBE_URL|LOCAL_AUDIO_FILE]")
            sys.exit(1)
    else:
        source_type = 'youtube'
        youtube_url = KOREAN_TEST_VIDEOS[0]
    
    print("="*60)
    print("KOREAN ASR TEST - OpenAI Whisper vs Soniox")
    print("="*60)
    print(f"API URL: {BASE_URL}")
    print(f"Source: {'Local file: ' + local_audio_path if source_type == 'local' else 'YouTube: ' + youtube_url}")
    print(f"Auth: {'enabled' if TOKEN and TOKEN != 'disabled' else 'disabled'}")
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # Step 1: Create session
            session_id = create_session()
            
            # Step 2: Get audio (download or use local)
            if source_type == 'youtube':
                audio_path = download_youtube_audio(youtube_url, tmpdir)
            else:
                audio_path = local_audio_path
                print(f"\n📁 Using local audio file: {audio_path}")
            
            # Step 3: Split into chunks
            chunks = split_audio(audio_path, tmpdir, chunk_seconds=15)
            
            # Step 4: Upload and process
            results = process_chunks(session_id, chunks)
            
            # Step 5: Print summary
            print_summary(session_id, results)
            
            print(f"\n🔗 View transcript at: {BASE_URL}/api/session/{session_id}/transcript")
            
        except Exception as e:
            print(f"\n❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
