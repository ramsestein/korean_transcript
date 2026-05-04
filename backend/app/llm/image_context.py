from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import Settings
from app.llm.client import get_provider

logger = logging.getLogger(__name__)

_CANDIDATE_PATHS = [
    # Docker layout: /app/app/llm/ -> /app/prompts/
    Path(__file__).parent.parent.parent / "prompts" / "image_context.md",
    # Local dev layout
    Path(__file__).parent.parent.parent.parent / "prompts" / "image_context.md",
]


def _load_prompt() -> str:
    for p in _CANDIDATE_PATHS:
        if p.exists():
            return p.read_text(encoding="utf-8")
    logger.error("Image context prompt not found in: %s", _CANDIDATE_PATHS)
    return ""


async def extract_image_context(
    image_bytes: bytes,
    filename: str,
    settings: Settings,
) -> dict:
    """
    Call the vision LLM to extract structured context from an image.
    Returns dict with: visible_text, entities, technical_terms, agenda_items, likely_relevance.
    """
    provider, model = get_provider("vision", settings)
    system_prompt = _load_prompt()

    user_text = (
        f"Please analyze this image (filename: {filename}) uploaded as context "
        "for a Korean academic or technical meeting. Extract structured information as specified."
    )

    result = await provider.complete_json(
        model=model,
        system=system_prompt,
        user=user_text,
        images=[image_bytes],
        max_tokens=1024,
    )

    return _validate_image_context_result(result)


def _validate_image_context_result(result: dict) -> dict:
    return {
        "visible_text": str(result.get("visible_text", "")),
        "entities": list(result.get("entities", [])),
        "technical_terms": list(result.get("technical_terms", [])),
        "agenda_items": list(result.get("agenda_items", [])),
        "likely_relevance": str(result.get("likely_relevance", "")),
    }
