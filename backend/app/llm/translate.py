from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import Settings
from app.llm.client import get_provider
from app.schemas import ImageContext, Segment, TargetLanguage

logger = logging.getLogger(__name__)

_CANDIDATE_DIRS = [
    # Docker layout: /app/app/llm/ -> /app/prompts/
    Path(__file__).parent.parent.parent / "prompts",
    # Local dev layout
    Path(__file__).parent.parent.parent.parent / "prompts",
]

_PROMPT_FILES: dict[str, str] = {
    "es": "translate_es.md",
    "en": "translate_en.md",
    "zh": "translate_zh.md",
}


def _load_prompt(lang: str) -> str:
    fname = _PROMPT_FILES.get(lang, "translate_es.md")
    for d in _CANDIDATE_DIRS:
        path = d / fname
        if path.exists():
            return path.read_text(encoding="utf-8")
    logger.error("Translate prompt not found: %s", fname)
    return ""


async def translate_korean(
    reconstructed_ko: str,
    target_language: TargetLanguage,
    previous_segments: list[Segment],
    meeting_prompt: str,
    image_contexts: list[ImageContext],
    settings: Settings,
) -> dict:
    """
    Translate reconstructed Korean to target language.
    Returns dict with: translated_text, confidence, uncertainties.
    """
    provider, model = get_provider("translate", settings)
    system_prompt = _load_prompt(target_language)

    prev_translations = [
        s.translated_text
        for s in previous_segments[-settings.context_window_segments:]
    ]

    image_ctx_list = [
        {
            "visible_text": ic.visible_text,
            "entities": ic.entities,
            "technical_terms": ic.technical_terms,
        }
        for ic in image_contexts
    ]

    user_payload = {
        "reconstructed_ko": reconstructed_ko,
        "meeting_prompt": meeting_prompt,
        "image_context": image_ctx_list,
        "previous_translations": prev_translations,
        "target_language": target_language,
    }

    result = await provider.complete_json(
        model=model,
        system=system_prompt,
        user=json.dumps(user_payload, ensure_ascii=False),
        max_tokens=2048,
    )

    return _validate_translate_result(result)


def _validate_translate_result(result: dict) -> dict:
    return {
        "translated_text": str(result.get("translated_text", "")),
        "confidence": result.get("confidence", "low") if result.get("confidence") in ("high", "medium", "low") else "low",
        "uncertainties": list(result.get("uncertainties", [])),
    }
