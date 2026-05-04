import io
import json
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.config import Settings, get_settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def settings_override(tmp_path, monkeypatch):
    settings = Settings(
        openai_api_key="test-key",
        soniox_api_key="test-key",
        data_dir=str(tmp_path),
    )
    app.dependency_overrides[get_settings] = lambda: settings
    yield settings
    app.dependency_overrides.clear()


@pytest.mark.integration
@pytest.mark.anyio
class TestHealthEndpoint:
    async def test_health_ok(self, settings_override):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


@pytest.mark.integration
@pytest.mark.anyio
class TestSessionStartEndpoint:
    async def test_start_returns_session_id(self, settings_override):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/session/start", json={
                "target_language": "es",
                "meeting_prompt": "Test meeting",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert len(data["session_id"]) > 0

    async def test_start_invalid_language(self, settings_override):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/session/start", json={
                "target_language": "fr",
            })
        assert resp.status_code == 422

    async def test_transcript_404_for_missing_session(self, settings_override):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/session/nonexistent/transcript")
        assert resp.status_code == 404

    async def test_delete_nonexistent_session_404(self, settings_override):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.delete("/api/session/nonexistent")
        assert resp.status_code == 404

    async def test_full_session_lifecycle(self, settings_override):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            start_resp = await client.post("/api/session/start", json={
                "target_language": "en",
                "meeting_prompt": "Integration test",
            })
            assert start_resp.status_code == 200
            session_id = start_resp.json()["session_id"]

            transcript_resp = await client.get(f"/api/session/{session_id}/transcript")
            assert transcript_resp.status_code == 200
            assert transcript_resp.json()["session_id"] == session_id
            assert transcript_resp.json()["segments"] == []

            delete_resp = await client.delete(f"/api/session/{session_id}")
            assert delete_resp.status_code == 200
            assert delete_resp.json()["status"] == "deleted"
