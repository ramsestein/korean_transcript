import pytest
import tempfile
import os
from pathlib import Path

from app.config import Settings
from app.schemas import SessionStartRequest
from app.session.manager import (
    create_session,
    get_session_manifest,
    append_segment,
    delete_session,
)
from app.schemas import Segment, AgreementMetrics


def make_settings(tmp_path: str) -> Settings:
    return Settings(
        openai_api_key="test-key",
        soniox_api_key="test-key",
        data_dir=tmp_path,
    )


@pytest.fixture
def tmp_settings(tmp_path):
    return make_settings(str(tmp_path))


@pytest.mark.unit
class TestSessionLifecycle:
    @pytest.mark.asyncio
    async def test_create_and_retrieve(self, tmp_settings):
        req = SessionStartRequest(
            target_language="es",
            meeting_prompt="Test meeting",
        )
        session_id = await create_session(req, tmp_settings)
        assert session_id

        manifest = await get_session_manifest(session_id, tmp_settings)
        assert manifest is not None
        assert manifest.session_id == session_id
        assert manifest.target_language == "es"
        assert manifest.meeting_prompt == "Test meeting"

    @pytest.mark.asyncio
    async def test_missing_session_returns_none(self, tmp_settings):
        manifest = await get_session_manifest("nonexistent-id", tmp_settings)
        assert manifest is None

    @pytest.mark.asyncio
    async def test_append_segment(self, tmp_settings):
        req = SessionStartRequest(target_language="en", meeting_prompt="")
        session_id = await create_session(req, tmp_settings)

        seg = Segment(
            segment_id=f"{session_id}_0",
            chunk_index=0,
            time_start=0.0,
            time_end=15.0,
            openai_asr_ko="테스트",
            soniox_asr_ko="테스트",
            reconstructed_ko="테스트입니다",
            translated_text="This is a test.",
            target_language="en",
            confidence="high",
        )
        await append_segment(session_id, seg, tmp_settings)

        manifest = await get_session_manifest(session_id, tmp_settings)
        assert len(manifest.segments) == 1
        assert manifest.segments[0].reconstructed_ko == "테스트입니다"

    @pytest.mark.asyncio
    async def test_delete_session(self, tmp_settings):
        req = SessionStartRequest(target_language="zh", meeting_prompt="")
        session_id = await create_session(req, tmp_settings)

        deleted = await delete_session(session_id, tmp_settings)
        assert deleted is True

        manifest = await get_session_manifest(session_id, tmp_settings)
        assert manifest is None

    @pytest.mark.asyncio
    async def test_append_updates_existing_segment(self, tmp_settings):
        req = SessionStartRequest(target_language="es", meeting_prompt="")
        session_id = await create_session(req, tmp_settings)

        seg_id = f"{session_id}_0"
        seg = Segment(
            segment_id=seg_id,
            chunk_index=0,
            time_start=0.0,
            time_end=15.0,
            openai_asr_ko="원본",
            soniox_asr_ko="원본",
            reconstructed_ko="원본 텍스트",
            translated_text="Original text.",
            target_language="es",
            confidence="low",
        )
        await append_segment(session_id, seg, tmp_settings)

        seg_updated = Segment(
            segment_id=seg_id,
            chunk_index=0,
            time_start=0.0,
            time_end=15.0,
            openai_asr_ko="원본",
            soniox_asr_ko="원본",
            reconstructed_ko="수정된 텍스트",
            translated_text="Revised text.",
            target_language="es",
            confidence="high",
        )
        await append_segment(session_id, seg_updated, tmp_settings)

        manifest = await get_session_manifest(session_id, tmp_settings)
        assert len(manifest.segments) == 1
        assert manifest.segments[0].reconstructed_ko == "수정된 텍스트"
