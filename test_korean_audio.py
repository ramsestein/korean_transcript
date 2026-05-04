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
import shutil
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


def login(username: str, password: str) -> str:
    """Login to get auth token"""
    url = f"{BASE_URL}/api/auth/login"
    payload = {
        "username": username,
        "password": password
    }
    
    resp = requests.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()
    token = data["token"]
    print(f"✅ Logged in as: {data.get('username', 'unknown')}")
    return token


def create_session(token: str, language="es", prompt="Test session with Korean audio"):
    """Create a new session via API"""
    url = f"{BASE_URL}/api/session/start"
    headers = {}
    if token and token != "disabled":
        headers["Authorization"] = f"Bearer {token}"
    
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


def find_ffmpeg():
    """Find ffmpeg executable in common locations"""
    import shutil
    
    # Check if already in PATH
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path
    
    # Common locations to search
    common_paths = [
        r"C:\Program Files\CapCut\Apps\3.7.0.1379\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
    ]
    
    for path in common_paths:
        if Path(path).exists():
            return path
    
    return None


def extract_audio_with_ffmpeg(video_path, output_wav):
    """Extract audio from video file using ffmpeg-python"""
    try:
        import ffmpeg
    except ImportError:
        print("❌ ffmpeg-python not found. Install with: pip install ffmpeg-python")
        sys.exit(1)
    
    # Find ffmpeg binary
    ffmpeg_exe = find_ffmpeg()
    if not ffmpeg_exe:
        print("❌ ffmpeg.exe not found. Please install ffmpeg or ensure it's in PATH")
        print("   Common locations checked: CapCut, C:\ffmpeg, Program Files")
        sys.exit(1)
    
    print(f"   Using ffmpeg from: {ffmpeg_exe}")
    
    # Set ffmpeg binary for ffmpeg-python
    import os
    os.environ['FFMPEG_BINARY'] = ffmpeg_exe
    
    print(f"   Extracting audio from video...")
    try:
        # Extract audio to mono 16kHz WAV (optimal for ASR)
        (
            ffmpeg
            .input(video_path)
            .output(output_wav, ac=1, ar=16000, vn=None)
            .overwrite_output()
            .run(cmd=ffmpeg_exe, quiet=True)
        )
        return output_wav
    except ffmpeg.Error as e:
        print(f"❌ ffmpeg extraction failed: {e}")
        raise


def split_audio(audio_path, output_dir, chunk_seconds=15):
    """Split audio into chunks using pydub"""
    print(f"\n✂️  Splitting audio into {chunk_seconds}s chunks...")
    
    try:
        from pydub import AudioSegment
    except ImportError:
        print("❌ pydub not found. Install with: pip install pydub")
        sys.exit(1)
    
    # Configure pydub to use our found ffmpeg
    ffmpeg_exe = find_ffmpeg()
    if ffmpeg_exe:
        AudioSegment.converter = ffmpeg_exe
        AudioSegment.ffmpeg = ffmpeg_exe
    
    chunk_dir = Path(output_dir) / "chunks"
    chunk_dir.mkdir(exist_ok=True)
    
    # Check if input is video, extract audio first
    audio_ext = Path(audio_path).suffix.lower()
    if audio_ext in ['.mp4', '.avi', '.mov', '.mkv', '.webm']:
        wav_path = str(Path(output_dir) / "extracted_audio.wav")
        audio_path = extract_audio_with_ffmpeg(audio_path, wav_path)
    
    try:
        # Load audio file
        print(f"   Loading audio file...")
        audio = AudioSegment.from_file(audio_path)
        
        # Ensure mono 16kHz
        if audio.channels != 1 or audio.frame_rate != 16000:
            print(f"   Converting to mono 16kHz...")
            audio = audio.set_channels(1).set_frame_rate(16000)
        
        chunk_length_ms = chunk_seconds * 1000
        chunks = []
        
        for i, start_ms in enumerate(range(0, len(audio), chunk_length_ms)):
            end_ms = min(start_ms + chunk_length_ms, len(audio))
            chunk = audio[start_ms:end_ms]
            
            # Export as WAV (simplest format, no encoding issues)
            chunk_path = chunk_dir / f"chunk_{i:03d}.wav"
            chunk.export(str(chunk_path), format="wav")
            chunks.append(chunk_path)
            
        print(f"✅ Created {len(chunks)} chunks")
        return chunks
        
    except Exception as e:
        print(f"❌ Split failed: {e}")
        raise


def upload_chunk(token: str, session_id, chunk_path, chunk_index, start_time, end_time):
    """Upload a single chunk to the API"""
    url = f"{BASE_URL}/api/session/{session_id}/chunk"
    headers = {}
    if token and token != "disabled":
        headers["Authorization"] = f"Bearer {token}"
    
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


def process_chunks(token: str, session_id, chunks):
    """Upload all chunks and show results"""
    print(f"\n📤 Uploading {len(chunks)} chunks to API...\n")
    
    results = []
    for i, chunk_path in enumerate(chunks):
        start_time = i * 15  # 15 second chunks
        end_time = start_time + 15
        
        print(f"Chunk {i}: {chunk_path.name}...", end=" ")
        
        try:
            result = upload_chunk(token, session_id, chunk_path, i, start_time, end_time)
            
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


def fetch_and_display_transcript(token: str, session_id):
    """Fetch the complete transcript from the API and display it"""
    url = f"{BASE_URL}/api/session/{session_id}/transcript"
    headers = {}
    if token and token != "disabled":
        headers["Authorization"] = f"Bearer {token}"
    
    print(f"\n{'='*70}")
    print(f"📄 TRANSCRIPT FOR SESSION: {session_id}")
    print(f"{'='*70}")
    
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        
        segments = data.get("segments", [])
        if not segments:
            print("\n   No transcript segments available yet.")
            return
        
        print(f"\nTotal segments: {len(segments)}\n")
        
        for seg in segments:
            idx = seg.get("chunk_index", 0)
            asr_sources = seg.get("asr_sources", [])
            
            # ASR indicator
            if len(asr_sources) == 2:
                asr_indicator = "🔵🔵 BOTH"
            elif "openai" in asr_sources:
                asr_indicator = "🔵⚪ OpenAI"
            elif "soniox" in asr_sources:
                asr_indicator = "⚪🔵 Soniox"
            else:
                asr_indicator = "⚪⚪ NONE"
            
            ko_text = seg.get("reconstructed_ko", "") or seg.get("translated_text", "")
            trans_text = seg.get("translated_text", "")
            confidence = seg.get("confidence", "unknown")
            
            print(f"Chunk {idx:3d} | {asr_indicator} | confidence: {confidence.upper()}")
            print(f"         Korean: {ko_text[:80]}{'...' if len(ko_text) > 80 else ''}")
            if trans_text and trans_text != ko_text:
                print(f"         Trans:  {trans_text[:80]}{'...' if len(trans_text) > 80 else ''}")
            print()
            
    except Exception as e:
        print(f"\n   ⚠️  Could not fetch transcript: {e}")


def print_summary(session_id, results):
    """Print summary of ASR results"""
    print(f"\n{'='*70}")
    print(f"SUMMARY FOR SESSION: {session_id}")
    print(f"{'='*70}")
    
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
    
    # Get credentials from env or prompt
    username = os.getenv("API_USERNAME", "ramses")
    password = os.getenv("API_PASSWORD", "mellamoRalph12")
    
    # Step 0: Login to get token
    try:
        token = login(username, password)
    except Exception as e:
        print(f"❌ Login failed: {e}")
        print("   Set API_USERNAME and API_PASSWORD env vars, or edit the script")
        sys.exit(1)
    
    # Create temp directory (manual cleanup to avoid Windows permission issues)
    import atexit
    tmpdir = tempfile.mkdtemp(prefix="korean_test_")
    atexit.register(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
    
    try:
        # Step 1: Create session
        session_id = create_session(token)
        
        # Step 2: Get audio (download or use local)
        if source_type == 'youtube':
            audio_path = download_youtube_audio(youtube_url, tmpdir)
        else:
            audio_path = local_audio_path
            print(f"\n📁 Using local audio file: {audio_path}")
        
        # Step 3: Split into chunks
        chunks = split_audio(audio_path, tmpdir, chunk_seconds=15)
        
        # Step 4: Upload and process
        results = process_chunks(token, session_id, chunks)
        
        # Step 5: Print summary
        print_summary(session_id, results)
        
        # Step 6: Fetch and display the transcript
        fetch_and_display_transcript(token, session_id)
        
        print(f"\n🔗 View transcript at: {BASE_URL}/api/session/{session_id}/transcript")
        print(f"   Temp files location: {tmpdir}")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
