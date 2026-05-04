from __future__ import annotations

import re
import unicodedata


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return text.strip()


def lexical_similarity(a: str, b: str) -> float:
    """rapidfuzz token_set_ratio / 100 after NFC normalization."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    try:
        from rapidfuzz import fuzz
        return fuzz.token_set_ratio(_normalize(a), _normalize(b)) / 100.0
    except ImportError:
        tokens_a = set(_normalize(a).split())
        tokens_b = set(_normalize(b).split())
        if not tokens_a and not tokens_b:
            return 1.0
        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b
        return len(intersection) / len(union) if union else 1.0


def length_ratio(a: str, b: str) -> float:
    """min(len)/max(len) on whitespace-tokenized sequences; 1.0 if both empty."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    tokens_a = a.split()
    tokens_b = b.split()
    la, lb = len(tokens_a), len(tokens_b)
    if la == 0 and lb == 0:
        return 1.0
    if la == 0 or lb == 0:
        return 0.0
    return min(la, lb) / max(la, lb)


def confidence_hint(lex: float, lr: float) -> str:
    if lex >= 0.85 and lr >= 0.80:
        return "high"
    if lex >= 0.60:
        return "medium"
    return "low"


def compute_agreement(a: str, b: str) -> dict[str, object]:
    lex = lexical_similarity(a, b)
    lr = length_ratio(a, b)
    hint = confidence_hint(lex, lr)
    return {
        "lexical_similarity": round(lex, 4),
        "length_ratio": round(lr, 4),
        "confidence_hint": hint,
    }
