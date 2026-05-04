import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.config import Settings
from app.session.cleanup import cleanup_expired_sessions


def make_session_dir(data_dir: Path, session_id: str, age_hours: float) -> None:
    session_path = data_dir / session_id
    session_path.mkdir(parents=True)
    created_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    manifest = {"session_id": session_id, "created_at": created_at.isoformat()}
    (session_path / "manifest.json").write_text(json.dumps(manifest))


@pytest.mark.unit
class TestCleanupExpiredSessions:
    @pytest.mark.asyncio
    async def test_removes_expired_session(self, tmp_path):
        settings = Settings(
            openai_api_key="k",
            soniox_api_key="k",
            data_dir=str(tmp_path),
            session_ttl_hours=24,
        )
        make_session_dir(tmp_path, "old-session", age_hours=25)
        removed = await cleanup_expired_sessions(settings)
        assert removed == 1
        assert not (tmp_path / "old-session").exists()

    @pytest.mark.asyncio
    async def test_keeps_fresh_session(self, tmp_path):
        settings = Settings(
            openai_api_key="k",
            soniox_api_key="k",
            data_dir=str(tmp_path),
            session_ttl_hours=24,
        )
        make_session_dir(tmp_path, "new-session", age_hours=1)
        removed = await cleanup_expired_sessions(settings)
        assert removed == 0
        assert (tmp_path / "new-session").exists()

    @pytest.mark.asyncio
    async def test_empty_data_dir(self, tmp_path):
        settings = Settings(
            openai_api_key="k",
            soniox_api_key="k",
            data_dir=str(tmp_path),
        )
        removed = await cleanup_expired_sessions(settings)
        assert removed == 0
