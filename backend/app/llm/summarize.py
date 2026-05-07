from __future__ import annotations

import json
import logging
from pathlib import Path

from app.config import Settings
from app.llm.client import get_provider
from app.schemas import ImageContext, Segment, TargetLanguage

logger = logging.getLogger(__name__)

_CANDIDATE_PATHS = [
    # Docker layout: /app/app/llm/ -> /app/prompts/
    Path(__file__).parent.parent.parent / "prompts" / "operational_summary.md",
    # Local dev layout
    Path(__file__).parent.parent.parent.parent / "prompts" / "operational_summary.md",
]


def _load_prompt() -> str:
    for p in _CANDIDATE_PATHS:
        if p.exists():
            return p.read_text(encoding="utf-8")
    logger.error("Summary prompt not found in: %s", _CANDIDATE_PATHS)
    return ""


MAX_INPUT_CHARS = 60_000  # ~15k tokens, safe for most models
MAX_OUTPUT_TOKENS = 16_000


def _truncate_text(text: str, max_chars: int, label: str) -> str:
    """Truncate text with a notice if it exceeds the limit."""
    if len(text) <= max_chars:
        return text
    logger.warning("Truncating %s from %d to %d chars for summary", label, len(text), max_chars)
    return text[:max_chars] + f"\n\n[... {label} truncated due to length ...]"


async def generate_summary(
    segments: list[Segment],
    target_language: TargetLanguage,
    meeting_prompt: str,
    image_contexts: list[ImageContext],
    settings: Settings,
) -> str:
    """
    Generate an operational summary in Markdown.
    Returns the raw Markdown string.
    """
    provider, model = get_provider("summary", settings)
    system_prompt = _load_prompt()

    reconstructed_ko_full = "\n\n".join(
        f"[{s.time_start:.0f}s-{s.time_end:.0f}s] {s.reconstructed_ko}"
        for s in segments
        if s.reconstructed_ko
    )
    translated_full = "\n\n".join(
        f"[{s.time_start:.0f}s-{s.time_end:.0f}s] {s.translated_text}"
        for s in segments
        if s.translated_text
    )

    # Truncate if too long to avoid context window overflow
    half_limit = MAX_INPUT_CHARS // 2
    reconstructed_ko_full = _truncate_text(reconstructed_ko_full, half_limit, "reconstructed_ko")
    translated_full = _truncate_text(translated_full, half_limit, "translated")

    all_uncertainties = []
    for s in segments:
        all_uncertainties.extend(s.uncertainties)

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
        "meeting_prompt": meeting_prompt,
        "reconstructed_ko_full": reconstructed_ko_full,
        "translated_full": translated_full,
        "image_contexts": image_ctx_list,
        "segment_uncertainties": all_uncertainties[:50],  # Cap uncertainties
        "target_language": target_language,
        "total_segments": len(segments),
    }

    logger.info(
        "Generating summary: %d segments, ko=%d chars, translated=%d chars",
        len(segments), len(reconstructed_ko_full), len(translated_full),
    )

    markdown = await provider.complete_text(
        model=model,
        system=system_prompt,
        user=json.dumps(user_payload, ensure_ascii=False),
        max_tokens=MAX_OUTPUT_TOKENS,
    )

    return markdown.strip()
