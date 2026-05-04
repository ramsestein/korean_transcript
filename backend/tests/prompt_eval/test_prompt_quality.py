"""
Prompt quality evaluation tests using seed cases.
These tests use real LLM calls (marked live_api) or mock outputs (unit-style).
Run live: pytest tests/prompt_eval -m live_api --live-llm-judge
Run offline: pytest tests/prompt_eval -m unit
"""
import json
import pytest


SEED_RECONSTRUCT_CASES = [
    {
        "id": "rc-01",
        "openai_asr_ko": "이 모델은 GPT-4를 사용하여 MIMIC-IV 데이터셋에서 훈련되었습니다",
        "soniox_asr_ko": "이 모델은 GPT-4를 사용하여 MIMIC-IV 데이터셋에서 훈련되었습니다",
        "agreement": {"lexical_similarity": 1.0, "length_ratio": 1.0, "confidence_hint": "high"},
        "expected_constraints": (
            "Must preserve 'GPT-4' and 'MIMIC-IV' verbatim. "
            "reconstructed_ko must not omit or alter dataset names."
        ),
    },
    {
        "id": "rc-02",
        "openai_asr_ko": "환자의 혈당 수치가 정상 범위입니다",
        "soniox_asr_ko": "환자의 혈당 수준이 정상 범위입니다",
        "agreement": {"lexical_similarity": 0.80, "length_ratio": 1.0, "confidence_hint": "medium"},
        "expected_constraints": (
            "Must produce fluent Korean reconciling '수치' vs '수준'. "
            "Medical context should preserve accuracy."
        ),
    },
]

SEED_TRANSLATE_ES_CASES = [
    {
        "id": "tr-es-01",
        "reconstructed_ko": "본 연구에서는 BERT 모델을 사용하여 한국어 NLP를 개선했습니다",
        "target_language": "es",
        "expected_constraints": (
            "Must preserve 'BERT' verbatim. "
            "Translation must be in formal academic Spanish. "
            "NLP should remain 'NLP'."
        ),
    },
    {
        "id": "tr-es-02",
        "reconstructed_ko": "내일까지 보고서를 제출해 주세요",
        "target_language": "es",
        "expected_constraints": (
            "Should express a polite request/obligation. "
            "Deadline 'mañana' must be present."
        ),
    },
]


@pytest.mark.unit
class TestPromptQualitySeedCasesOffline:
    """
    Offline smoke tests: verify seed case structure is valid and constraints are non-empty.
    Real LLM evaluation is done under `live_api` marker.
    """

    def test_reconstruct_seed_cases_have_required_fields(self):
        for case in SEED_RECONSTRUCT_CASES:
            assert "id" in case
            assert "openai_asr_ko" in case
            assert "soniox_asr_ko" in case
            assert "agreement" in case
            assert "expected_constraints" in case
            assert len(case["expected_constraints"]) > 0

    def test_translate_seed_cases_have_required_fields(self):
        for case in SEED_TRANSLATE_ES_CASES:
            assert "id" in case
            assert "reconstructed_ko" in case
            assert "target_language" in case
            assert "expected_constraints" in case
            assert len(case["expected_constraints"]) > 0

    def test_agreement_fields_valid_range(self):
        for case in SEED_RECONSTRUCT_CASES:
            agr = case["agreement"]
            assert 0.0 <= agr["lexical_similarity"] <= 1.0
            assert 0.0 <= agr["length_ratio"] <= 1.0
            assert agr["confidence_hint"] in ("high", "medium", "low")


@pytest.mark.live_api
class TestPromptQualityLive:
    """
    Live tests: call real LLM, then judge output with judge_a.
    Requires OPENAI_API_KEY in environment.
    Run: pytest tests/prompt_eval -m live_api -v
    """

    @pytest.mark.asyncio
    async def test_reconstruct_high_agreement_preserves_entities(self):
        from app.config import Settings
        from app.llm.reconstruct import reconstruct_korean
        from app.schemas import AgreementMetrics

        settings = Settings()
        case = SEED_RECONSTRUCT_CASES[0]

        result = await reconstruct_korean(
            openai_asr_ko=case["openai_asr_ko"],
            soniox_asr_ko=case["soniox_asr_ko"],
            soniox_speakers=[],
            agreement=AgreementMetrics(**case["agreement"]),
            previous_segments=[],
            meeting_prompt="AI medical NLP research meeting",
            image_contexts=[],
            settings=settings,
        )

        assert "GPT-4" in result["reconstructed_ko"], "Entity 'GPT-4' must be preserved"
        assert "MIMIC-IV" in result["reconstructed_ko"], "Dataset name 'MIMIC-IV' must be preserved"
        assert result["confidence"] in ("high", "medium", "low")

    @pytest.mark.asyncio
    async def test_translate_preserves_technical_term(self):
        from app.config import Settings
        from app.llm.translate import translate_korean

        settings = Settings()
        case = SEED_TRANSLATE_ES_CASES[0]

        result = await translate_korean(
            reconstructed_ko=case["reconstructed_ko"],
            target_language="es",
            previous_segments=[],
            meeting_prompt="AI NLP research meeting",
            image_contexts=[],
            settings=settings,
        )

        assert "BERT" in result["translated_text"], "Technical term 'BERT' must not be translated"
        assert result["confidence"] in ("high", "medium", "low")
