from __future__ import annotations

from app.schemas import ImageContext, Segment


def build_context(
    segments: list[Segment],
    image_contexts: list[ImageContext],
    window_size: int,
) -> dict:
    """
    Build the LLM context window from the last `window_size` segments
    plus all image contexts.
    """
    recent = segments[-window_size:] if len(segments) > window_size else segments

    return {
        "previous_segments": [s.reconstructed_ko for s in recent if s.reconstructed_ko],
        "previous_translations": [s.translated_text for s in recent if s.translated_text],
        "image_contexts": [
            {
                "visible_text": ic.visible_text,
                "entities": ic.entities,
                "technical_terms": ic.technical_terms,
                "agenda_items": ic.agenda_items,
            }
            for ic in image_contexts
        ],
    }


def collect_known_terminology(
    segments: list[Segment],
    image_contexts: list[ImageContext],
) -> set[str]:
    """
    Collect all known terminology from previous segments and image contexts.
    Used by retroactive correction to detect new terms.
    """
    terms: set[str] = set()
    for seg in segments:
        terms.update(seg.terminology)
        terms.update(seg.uncertainties)
    for ic in image_contexts:
        terms.update(ic.technical_terms)
        terms.update(ic.entities)
    return terms
