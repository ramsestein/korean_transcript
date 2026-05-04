from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import Settings
from app.llm.client import get_provider
from app.schemas import AgreementMetrics, ImageContext, Segment

logger = logging.getLogger(__name__)

_CANDIDATE_PATHS = [
    # Docker layout: /app/app/llm/ -> /app/prompts/
    Path(__file__).parent.parent.parent / "prompts" / "reconstruct_ko.md",
    # Local dev layout: backend/app/llm/ -> ../../prompts/
    Path(__file__).parent.parent.parent.parent / "prompts" / "reconstruct_ko.md",
]


def _load_prompt() -> str:
    for p in _CANDIDATE_PATHS:
        if p.exists():
            return p.read_text(encoding="utf-8")
    logger.error("Prompt file not found in any candidate path: %s", _CANDIDATE_PATHS)
    return ""


async def reconstruct_korean(
    openai_asr_ko: str,
    soniox_asr_ko: str,
    soniox_speakers: list[dict],
    agreement: AgreementMetrics,
    previous_segments: list[Segment],
    meeting_prompt: str,
    image_contexts: list[ImageContext],
    settings: Settings,
) -> dict:
    """
    Call the reconstruction LLM.
    Returns dict with: reconstructed_ko, confidence, uncertainties, terminology.
    """
    provider, model = get_provider("reconstruct", settings)
    system_prompt = _load_prompt()

    prev_ko = [s.reconstructed_ko for s in previous_segments[-settings.context_window_segments:]]
    prev_translations = [s.translated_text for s in previous_segments[-settings.context_window_segments:]]

    image_ctx_list = [
        {
            "visible_text": ic.visible_text,
            "entities": ic.entities,
            "technical_terms": ic.technical_terms,
            "agenda_items": ic.agenda_items,
        }
        for ic in image_contexts
    ]

    user_payload = {
        "openai_asr_ko": openai_asr_ko,
        "soniox_asr_ko": soniox_asr_ko,
        "soniox_speakers": soniox_speakers,
        "agreement": {
            "lexical_similarity": agreement.lexical_similarity,
            "length_ratio": agreement.length_ratio,
            "confidence_hint": agreement.confidence_hint,
        },
        "previous_segments": prev_ko,
        "previous_translations": prev_translations,
        "meeting_prompt": meeting_prompt,
        "image_context": image_ctx_list,
    }

    result = await provider.complete_json(
        model=model,
        system=system_prompt,
        user=json.dumps(user_payload, ensure_ascii=False),
        max_tokens=2048,
    )

    return _validate_reconstruct_result(result)


def _validate_reconstruct_result(result: dict) -> dict:
    return {
        "reconstructed_ko": str(result.get("reconstructed_ko", "")),
        "confidence": result.get("confidence", "low") if result.get("confidence") in ("high", "medium", "low") else "low",
        "uncertainties": list(result.get("uncertainties", [])),
        "terminology": list(result.get("terminology", [])),
    }
