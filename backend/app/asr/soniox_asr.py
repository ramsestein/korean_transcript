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
    
    # Upload/create use 30s timeout; individual poll requests use a longer timeout
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        logger.info("Uploading file to Soniox...")
        file_id = await _upload_file(client, audio_path, api_key)
        logger.info("Soniox file uploaded, id=%s", file_id)
        
        logger.info("Creating transcription job...")
        transcription_id = await _create_transcription(client, file_id, api_key, model)
        logger.info("Soniox transcription job created, id=%s", transcription_id)
        
        logger.info("Polling for transcription completion...")
        try:
            result = await _poll_until_done(client, transcription_id, api_key)
            logger.info("Soniox transcription completed")
        finally:
            # Always clean up remote resources to avoid hitting file/transcription limits
            await _delete_resources(client, file_id, transcription_id, api_key)

    tokens = result.get("tokens", [])
    # Normalize timestamps: Soniox returns start_ms/end_ms (int, milliseconds)
    # but the rest of the pipeline expects start/end (float, seconds).
    for tok in tokens:
        if "start_ms" in tok and "start" not in tok:
            tok["start"] = tok["start_ms"] / 1000.0
        if "end_ms" in tok and "end" not in tok:
            tok["end"] = tok["end_ms"] / 1000.0
    # Prefer the pre-built text from the transcript endpoint over reconstruction.
    text = result.get("text") or _tokens_to_text(tokens)

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
    if response.status_code == 429:
        raise RuntimeError(f"Soniox rate limited on file upload: {response.text}")
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
        "enable_speaker_diarization": False,  # Disabled for chunk-level processing
    }
    logger.info("Soniox create transcription payload: %s", payload)
    
    response = await client.post(
        f"{SONIOX_BASE_URL}/transcriptions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=payload,
    )
    
    logger.info("Soniox create response status: %s", response.status_code)
    
    if response.status_code == 429:
        raise RuntimeError(f"Soniox rate limited: {response.text}")
    
    response.raise_for_status()
    data = response.json()
    logger.info("Soniox create response: %s", data)
    
    tx_id = data.get("id") or data.get("transcription_id")
    if not tx_id:
        raise ValueError(f"Soniox create transcription returned no id: {data}")
    return str(tx_id)


async def _poll_until_done(
    client: httpx.AsyncClient,
    transcription_id: str,
    api_key: str,
) -> dict[str, Any]:
    """Poll until complete, then fetch transcript from /transcript endpoint."""
    elapsed = 0.0
    last_status = None
    
    while elapsed < MAX_POLL_SECONDS:
        response = await client.get(
            f"{SONIOX_BASE_URL}/transcriptions/{transcription_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        response.raise_for_status()
        data = response.json()
        status = data.get("status", "")
        
        # Only log on status change
        if status != last_status:
            logger.info("Soniox transcription %s status: %s", transcription_id, status)
            last_status = status
        
        if status == "completed":
            logger.info("Soniox transcription %s completed in %.1fs", transcription_id, elapsed)
            # Fetch actual transcript from separate endpoint
            transcript_resp = await client.get(
                f"{SONIOX_BASE_URL}/transcriptions/{transcription_id}/transcript",
                headers={"Authorization": f"Bearer {api_key}"},
            )
            transcript_resp.raise_for_status()
            transcript_data = transcript_resp.json()
            logger.info("Soniox transcript fetched: %d tokens", len(transcript_data.get("tokens", [])))
            return transcript_data
            
        if status == "error":
            error_msg = data.get("error_message", str(data))
            logger.error("Soniox transcription %s failed: %s", transcription_id, error_msg)
            raise RuntimeError(f"Soniox transcription failed: {error_msg}")
        
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    logger.error("Soniox transcription %s timeout after %.1fs", transcription_id, elapsed)
    raise TimeoutError(
        f"Soniox transcription {transcription_id} did not complete within {MAX_POLL_SECONDS}s"
    )


async def _delete_resources(
    client: httpx.AsyncClient,
    file_id: str,
    transcription_id: str,
    api_key: str,
) -> None:
    """Delete file and transcription from Soniox to avoid hitting storage limits."""
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        resp = await client.delete(f"{SONIOX_BASE_URL}/transcriptions/{transcription_id}", headers=headers)
        if resp.status_code not in (200, 204, 404):
            logger.warning("Soniox delete transcription %s returned %s", transcription_id, resp.status_code)
        else:
            logger.debug("Soniox transcription %s deleted", transcription_id)
    except Exception as exc:
        logger.warning("Soniox delete transcription %s failed: %s", transcription_id, exc)

    try:
        resp = await client.delete(f"{SONIOX_BASE_URL}/files/{file_id}", headers=headers)
        if resp.status_code not in (200, 204, 404):
            logger.warning("Soniox delete file %s returned %s", file_id, resp.status_code)
        else:
            logger.debug("Soniox file %s deleted", file_id)
    except Exception as exc:
        logger.warning("Soniox delete file %s failed: %s", file_id, exc)


def _tokens_to_text(tokens: list[dict[str, Any]]) -> str:
    """Reconstruct plain text from Soniox token list."""
    parts = []
    for tok in tokens:
        text = tok.get("text", "") or tok.get("word", "")
        if text:
            parts.append(text)
    return "".join(parts).strip()
