import pytest
from app.asr.agreement import compute_agreement, confidence_hint, length_ratio, lexical_similarity


@pytest.mark.unit
class TestLexicalSimilarity:
    def test_identical(self):
        assert lexical_similarity("안녕하세요", "안녕하세요") == pytest.approx(1.0, abs=0.01)

    def test_empty_both(self):
        assert lexical_similarity("", "") == 1.0

    def test_one_empty(self):
        assert lexical_similarity("hello", "") == 0.0

    def test_partial_overlap(self):
        s = lexical_similarity("이 회의에서 논의하겠습니다", "이 회의에서 추가 논의하겠습니다")
        assert 0.5 <= s <= 1.0

    def test_no_overlap(self):
        s = lexical_similarity("완전히 다른 문장", "totally different sentence")
        assert s < 0.5


@pytest.mark.unit
class TestLengthRatio:
    def test_same_length(self):
        assert length_ratio("a b c", "d e f") == pytest.approx(1.0)

    def test_half(self):
        assert length_ratio("a b", "a b c d") == pytest.approx(0.5)

    def test_empty_both(self):
        assert length_ratio("", "") == 1.0

    def test_one_empty(self):
        assert length_ratio("", "hello") == 0.0


@pytest.mark.unit
class TestConfidenceHint:
    def test_high(self):
        assert confidence_hint(0.90, 0.90) == "high"

    def test_medium(self):
        assert confidence_hint(0.70, 0.70) == "medium"

    def test_low(self):
        assert confidence_hint(0.30, 0.30) == "low"


@pytest.mark.unit
class TestComputeAgreement:
    def test_returns_dict_with_expected_keys(self):
        result = compute_agreement("테스트입니다", "테스트입니다")
        assert "lexical_similarity" in result
        assert "length_ratio" in result
        assert "confidence_hint" in result

    def test_high_agreement_hint(self):
        result = compute_agreement("이 데이터를 분석합니다", "이 데이터를 분석합니다")
        assert result["confidence_hint"] == "high"
