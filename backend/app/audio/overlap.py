from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def drop_prefix_tokens(
    tokens: list[dict[str, Any]],
    overlap_seconds: float,
) -> list[dict[str, Any]]:
    """
    Drop tokens whose start timestamp is less than overlap_seconds.
    Tokens without a 'start' field are kept (conservative approach).
    """
    if not tokens or overlap_seconds <= 0:
        return tokens

    kept = []
    dropped_count = 0
    for token in tokens:
        start = token.get("start")
        if start is None or start >= overlap_seconds:
            kept.append(token)
        else:
            dropped_count += 1

    logger.debug(
        "Dropped %d prefix tokens (threshold=%.2fs), kept %d",
        dropped_count,
        overlap_seconds,
        len(kept),
    )
    return kept


def tokens_to_text(tokens: list[dict[str, Any]], field: str = "text") -> str:
    """Join token text fields into a single string."""
    parts = []
    for tok in tokens:
        text = tok.get(field, "")
        if text:
            parts.append(text)
    return "".join(parts).strip()


def tokens_to_speaker_turns(
    tokens: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """
    Group tokens by speaker field into consecutive turns.
    Returns list of {"speaker": "1", "text": "..."}.
    """
    if not tokens:
        return []

    turns: list[dict[str, str]] = []
    current_speaker: str | None = None
    current_parts: list[str] = []

    for token in tokens:
        speaker = str(token.get("speaker", "1"))
        text = token.get("text", "")
        if not text:
            continue
        if speaker != current_speaker:
            if current_speaker is not None and current_parts:
                turns.append({"speaker": current_speaker, "text": "".join(current_parts).strip()})
            current_speaker = speaker
            current_parts = [text]
        else:
            current_parts.append(text)

    if current_speaker is not None and current_parts:
        turns.append({"speaker": current_speaker, "text": "".join(current_parts).strip()})

    return turns


def drop_prefix_from_plain_text(
    text: str,
    overlap_seconds: float,
    total_seconds: float,
) -> str:
    """
    Heuristic prefix drop for plain-text ASR output that lacks token timestamps.
    Drops an estimated proportion of the text corresponding to overlap_seconds / total_seconds.
    This is a last resort — prefer token-based drop when available.
    """
    if overlap_seconds <= 0 or total_seconds <= 0:
        return text

    ratio = overlap_seconds / total_seconds
    words = text.split()
    n_drop = int(len(words) * ratio)
    logger.debug(
        "Heuristic prefix drop: %.0f%% of %d words → keeping %d",
        ratio * 100,
        len(words),
        len(words) - n_drop,
    )
    return " ".join(words[n_drop:])
