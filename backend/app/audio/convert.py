from __future__ import annotations

import asyncio
import glob
import logging
import os
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_ffmpeg() -> str:
    """Find ffmpeg binary, searching PATH and common Windows install locations."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    # winget installation paths (Gyan.FFmpeg)
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        pattern = os.path.join(
            local_app, "Microsoft", "WinGet", "Packages",
            "Gyan.FFmpeg*", "**", "ffmpeg.exe"
        )
        matches = glob.glob(pattern, recursive=True)
        if matches:
            return sorted(matches)[-1]  # pick highest version
    # chocolatey
    choco = r"C:\ProgramData\chocolatey\bin\ffmpeg.exe"
    if os.path.exists(choco):
        return choco
    # common manual install
    for p in [r"C:\ffmpeg\bin\ffmpeg.exe", r"C:\Program Files\ffmpeg\bin\ffmpeg.exe"]:
        if os.path.exists(p):
            return p
    return "ffmpeg"  # fallback, will raise clear error at run time


FFMPEG_BIN = _find_ffmpeg()
logger.info("ffmpeg binary: %s", FFMPEG_BIN)


def check_ffmpeg() -> bool:
    """Check if ffmpeg is installed and available."""
    global FFMPEG_BIN
    FFMPEG_BIN = _find_ffmpeg()
    return FFMPEG_BIN != "ffmpeg" or shutil.which("ffmpeg") is not None


async def convert_to_wav_16k_mono(input_path: Path, output_path: Path) -> None:
    """Convert any audio file to WAV 16 kHz mono using ffmpeg."""
    bin_path = _find_ffmpeg()
    if bin_path == "ffmpeg" and not shutil.which("ffmpeg"):
        raise RuntimeError(
            "ffmpeg not found. Install it: winget install Gyan.FFmpeg"
        )
    cmd = [
        bin_path,
        "-y",
        "-i", str(input_path),
        "-ar", "16000",
        "-ac", "1",
        "-f", "wav",
        str(output_path),
    ]
    logger.debug("Running ffmpeg: %s", " ".join(cmd))

    async def _run_cmd(cmd_list):
        """Try to run subprocess asynchronously; fall back to blocking run in a thread on Windows where Proactor may not be set."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stdout, stderr
        except NotImplementedError:
            # Fallback: run blocking subprocess in a thread to avoid event loop transport issues
            def _blocking():
                res = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return res.returncode, res.stdout, res.stderr

            return await asyncio.to_thread(_blocking)

    rc, stdout, stderr = await _run_cmd(cmd)
    if rc != 0:
        err_text = stderr.decode('utf-8', errors='replace')[:500]
        logger.error("ffmpeg rc=%d stderr: %s", rc, err_text)
        raise RuntimeError(
            f"ffmpeg rc={rc}: {err_text or '(no stderr)'}"
        )
    logger.debug("ffmpeg done: %s -> %s", input_path, output_path)


async def get_audio_duration(wav_path: Path) -> float:
    """Return duration in seconds of a WAV file using ffprobe."""
    ffprobe = shutil.which("ffprobe") or _find_ffmpeg().replace("ffmpeg", "ffprobe")
    cmd = [
        ffprobe,
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        str(wav_path),
    ]
    async def _run_cmd(cmd_list):
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stdout, stderr
        except NotImplementedError:
            def _blocking():
                res = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                return res.returncode, res.stdout, res.stderr

            return await asyncio.to_thread(_blocking)

    rc, stdout, stderr = await _run_cmd(cmd)
    if rc != 0:
        logger.warning("ffprobe failed: %s", stderr.decode()[:200])
        return 0.0
    try:
        return float(stdout.decode().strip())
    except ValueError:
        return 0.0
