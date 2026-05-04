from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import openai

logger = logging.getLogger(__name__)


async def transcribe_with_openai(
    audio_path: Path,
    api_key: str,
    model: str = "gpt-4o-transcribe",
) -> dict[str, Any]:
    """
    Transcribe a WAV file using OpenAI /v1/audio/transcriptions.
    Returns dict with 'text' and optionally 'words' (with timestamps).
    """
    client = openai.AsyncOpenAI(api_key=api_key)

    with audio_path.open("rb") as f:
        response = await client.audio.transcriptions.create(
            model=model,
            file=(audio_path.name, f, "audio/wav"),
            language="ko",
            response_format="text",
        )

    result: dict[str, Any] = {
        "text": response.text if hasattr(response, 'text') else str(response),
        "tokens": [],
    }

    logger.debug(
        "OpenAI ASR: model=%s, text_len=%d, tokens=%d",
        model,
        len(result["text"]),
        len(result["tokens"]),
    )
    return result
