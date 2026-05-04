from __future__ import annotations

import asyncio
import logging
import struct
import wave
from pathlib import Path

logger = logging.getLogger(__name__)


async def build_augmented_clip(
    current_wav: Path,
    previous_wav: Path | None,
    overlap_seconds: float,
    output_path: Path,
) -> float:
    """
    Prepend the last `overlap_seconds` of previous_wav to current_wav.
    Returns the actual prepended duration (0.0 if previous_wav is None or too short).
    """
    if previous_wav is None or not previous_wav.exists():
        import shutil
        shutil.copy2(current_wav, output_path)
        return 0.0

    prepended = await _extract_tail(previous_wav, overlap_seconds)
    if prepended is None:
        import shutil
        shutil.copy2(current_wav, output_path)
        return 0.0

    tail_data, tail_params, actual_tail_seconds = prepended
    await _concat_wav(tail_data, tail_params, current_wav, output_path)
    logger.debug("Prepended %.2fs of previous chunk to %s", actual_tail_seconds, output_path)
    return actual_tail_seconds


async def _extract_tail(
    wav_path: Path,
    seconds: float,
) -> tuple[bytes, tuple, float] | None:
    """Extract the last `seconds` of a WAV file. Returns (pcm_bytes, wav_params, actual_seconds)."""
    try:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _extract_tail_sync, wav_path, seconds)
    except Exception as exc:
        logger.warning("Could not extract tail from %s: %s", wav_path, exc)
        return None


def _extract_tail_sync(
    wav_path: Path,
    seconds: float,
) -> tuple[bytes, tuple, float] | None:
    with wave.open(str(wav_path), "rb") as wf:
        params = wf.getparams()
        framerate = wf.getframerate()
        nframes = wf.getnframes()
        n_tail = min(int(seconds * framerate), nframes)
        if n_tail == 0:
            return None
        wf.setpos(nframes - n_tail)
        data = wf.readframes(n_tail)
        actual_seconds = n_tail / framerate
        return data, params, actual_seconds


async def _concat_wav(
    prefix_pcm: bytes,
    prefix_params: tuple,
    suffix_wav: Path,
    output_path: Path,
) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None, _concat_wav_sync, prefix_pcm, prefix_params, suffix_wav, output_path
    )


def _concat_wav_sync(
    prefix_pcm: bytes,
    prefix_params: tuple,
    suffix_wav: Path,
    output_path: Path,
) -> None:
    with wave.open(str(suffix_wav), "rb") as wf:
        suffix_pcm = wf.readframes(wf.getnframes())

    combined = prefix_pcm + suffix_pcm

    with wave.open(str(output_path), "wb") as out:
        out.setparams(prefix_params)
        out.writeframes(combined)
