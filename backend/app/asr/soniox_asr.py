from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SONIOX_BASE_URL = "https://api.soniox.com/v1"
POLL_INTERVAL = 1.5
MAX_POLL_SECONDS = 120


async def transcribe_with_soniox(
    audio_path: Path,
    api_key: str,
    model: str = "stt-async-v4",
) -> dict[str, Any]:
    """
    Transcribe a WAV file using Soniox async REST API.
    Returns dict with 'text', 'tokens' (with speaker, start, end), and 'speakers'.
    """
    logger.info("Soniox ASR starting for %s", audio_path.name)
    
    if not api_key:
        logger.error("Soniox API key is empty!")
        raise ValueError("Soniox API key is not configured")
    
    logger.debug("Soniox API key present: %s...", api_key[:10] if len(api_key) > 10 else "(short)")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("Uploading file to Soniox...")
        file_id = await _upload_file(client, audio_path, api_key)
        logger.info("Soniox file uploaded, id=%s", file_id)
        
        logger.info("Creating transcription job...")
        transcription_id = await _create_transcription(client, file_id, api_key, model)
        logger.info("Soniox transcription job created, id=%s", transcription_id)
        
        logger.info("Polling for transcription completion...")
        result = await _poll_until_done(client, transcription_id, api_key)
        logger.info("Soniox transcription completed")

    tokens = result.get("tokens", [])
    text = _tokens_to_text(tokens)

    logger.info(
        "Soniox ASR SUCCESS: model=%s, text_len=%d, tokens=%d",
        model,
        len(text),
        len(tokens),
    )

    return {
        "text": text,
        "tokens": tokens,
        "raw": result,
    }


async def _upload_file(
    client: httpx.AsyncClient,
    audio_path: Path,
    api_key: str,
) -> str:
    with audio_path.open("rb") as f:
        response = await client.post(
            f"{SONIOX_BASE_URL}/files",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (audio_path.name, f, "audio/wav")},
        )
    response.raise_for_status()
    data = response.json()
    file_id = data.get("id") or data.get("file_id")
    if not file_id:
        raise ValueError(f"Soniox file upload returned no id: {data}")
    return str(file_id)


async def _create_transcription(
    client: httpx.AsyncClient,
    file_id: str,
    api_key: str,
    model: str,
) -> str:
    payload = {
        "file_id": file_id,
        "model": model,
        "language_hints": ["ko"],
        "enable_speaker_diarization": True,
        "include_timestamps": True,
    }
    response = await client.post(
        f"{SONIOX_BASE_URL}/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
    )
    response.raise_for_status()
    data = response.json()
    tx_id = data.get("id") or data.get("transcription_id")
    if not tx_id:
        raise ValueError(f"Soniox create transcription returned no id: {data}")
    return str(tx_id)


async def _poll_until_done(
    client: httpx.AsyncClient,
    transcription_id: str,
    api_key: str,
) -> dict[str, Any]:
    elapsed = 0.0
    while elapsed < MAX_POLL_SECONDS:
        response = await client.get(
            f"{SONIOX_BASE_URL}/transcriptions/{transcription_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        status = data.get("status", "")
        if status in ("completed", "done", "finished"):
            return data
        if status in ("failed", "error"):
            raise RuntimeError(f"Soniox transcription failed: {data}")
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    raise TimeoutError(
        f"Soniox transcription {transcription_id} did not complete within {MAX_POLL_SECONDS}s"
    )


def _tokens_to_text(tokens: list[dict[str, Any]]) -> str:
    """Reconstruct plain text from Soniox token list."""
    parts = []
    for tok in tokens:
        text = tok.get("text", "") or tok.get("word", "")
        if text:
            parts.append(text)
    return "".join(parts).strip()
