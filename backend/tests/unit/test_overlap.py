import pytest
from app.audio.overlap import drop_prefix_tokens, tokens_to_text


def make_tokens(words: list[tuple[str, float, float]]) -> list[dict]:
    return [{"text": w, "start": s, "end": e} for w, s, e in words]


@pytest.mark.unit
class TestDropPrefixTokens:
    def test_no_overlap(self):
        tokens = make_tokens([("안녕", 0.0, 0.5), ("하세요", 0.5, 1.0)])
        result = drop_prefix_tokens(tokens, 0.0)
        assert result == tokens

    def test_drops_tokens_within_overlap(self):
        tokens = make_tokens([
            ("중복", 0.0, 0.5),
            ("구간", 0.5, 1.5),
            ("이후", 1.5, 2.0),
        ])
        result = drop_prefix_tokens(tokens, 1.2)
        texts = [t["text"] for t in result]
        assert "중복" not in texts
        assert "이후" in texts

    def test_empty_tokens(self):
        assert drop_prefix_tokens([], 2.0) == []

    def test_all_in_overlap(self):
        tokens = make_tokens([("단어", 0.0, 1.0)])
        result = drop_prefix_tokens(tokens, 2.0)
        assert result == []


@pytest.mark.unit
class TestTokensToText:
    def test_basic(self):
        tokens = make_tokens([("안녕", 0.0, 0.5), ("하세요", 0.5, 1.0)])
        # tokens_to_text concatenates without spaces (appropriate for Korean)
        assert tokens_to_text(tokens) == "안녕하세요"

    def test_empty(self):
        assert tokens_to_text([]) == ""
