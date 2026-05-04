from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

from app.asr.openai_asr import transcribe_with_openai
from app.asr.soniox_asr import transcribe_with_soniox

logger = logging.getLogger(__name__)


async def run_parallel_asr(
    audio_path: Path,
    openai_api_key: str,
    soniox_api_key: str,
    openai_model: str = "gpt-4o-transcribe",
    soniox_model: str = "stt-async-v4",
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None, str | None]:
    """
    Run OpenAI and Soniox ASR in parallel.
    Returns (openai_result, soniox_result, openai_error, soniox_error).
    At least one result is non-None (or both errors are set and caller should raise).
    """
    openai_task = asyncio.create_task(
        _safe_transcribe(
            transcribe_with_openai(audio_path, openai_api_key, openai_model),
            "openai",
        )
    )
    soniox_task = asyncio.create_task(
        _safe_transcribe_with_retry(
            audio_path, soniox_api_key, soniox_model,
            max_retries=3,
        )
    )

    (openai_result, openai_error), (soniox_result, soniox_error) = await asyncio.gather(
        openai_task, soniox_task
    )

    if openai_result:
        logger.info("OpenAI ASR succeeded: %d chars", len(openai_result.get("text", "")))
    else:
        logger.warning("OpenAI ASR failed: %s", openai_error)

    if soniox_result:
        logger.info("Soniox ASR succeeded: %d chars", len(soniox_result.get("text", "")))
    else:
        logger.warning("Soniox ASR failed: %s", soniox_error)

    return openai_result, soniox_result, openai_error, soniox_error


async def _safe_transcribe(
    coro: Any,
    provider: str,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        result = await coro
        return result, None
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        logger.error("ASR provider %s error: %s", provider, err_msg)
        return None, err_msg


async def _safe_transcribe_with_retry(
    audio_path: Path,
    api_key: str,
    model: str,
    max_retries: int = 3,
) -> tuple[dict[str, Any] | None, str | None]:
    """Retry Soniox transcription with exponential backoff on resource exhaustion."""
    import time
    
    for attempt in range(max_retries):
        result, error = await _safe_transcribe(
            transcribe_with_soniox(audio_path, api_key, model),
            "soniox",
        )
        
        if result is not None:
            return result, None
        
        # Check if it's a resource exhaustion error
        if error and "resource_exhausted" in error.lower():
            wait_time = 2 ** attempt  # 1s, 2s, 4s
            logger.warning("Soniox resource exhausted (attempt %d/%d), retrying in %ds...", 
                          attempt + 1, max_retries, wait_time)
            await asyncio.sleep(wait_time)
            continue
        else:
            # Other errors, don't retry
            return None, error
    
    return None, f"Soniox failed after {max_retries} attempts. Last error: {error}"
