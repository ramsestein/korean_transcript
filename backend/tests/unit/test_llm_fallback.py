"""Tests for LLM client fallback logic."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.llm.client import _is_rate_limit, clear_provider_cache, complete_with_fallback
from app.llm.providers.base import LLMProvider


class FakeRateLimitError(Exception):
    """Simulates a Google-genai style rate-limit exception."""

    def __init__(self) -> None:
        super().__init__("429 Resource exhausted")
        self.code = 429


class Fake429StatusError(Exception):
    """Simulates an HTTP-style 429 exception."""

    def __init__(self) -> None:
        super().__init__("Too Many Requests")
        self.status_code = 429


class FakeResourceExhausted(Exception):
    """Simulates an exception whose name contains ResourceExhausted."""

    pass


class FakeGenericError(Exception):
    """Non-rate-limit error."""

    pass


class DummyProvider(LLMProvider):
    """Mock provider that returns configurable responses or raises."""

    def __init__(self, response: dict | None = None, exc: Exception | None = None) -> None:
        self.response = response
        self.exc = exc
        self.calls: list[tuple[str, str, str, int]] = []

    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        images: list[bytes] | None = None,
        max_tokens: int = 2048,
    ) -> dict:
        self.calls.append((model, system, user, max_tokens))
        if self.exc:
            raise self.exc
        return self.response or {}

    async def complete_text(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 2048,
    ) -> str:
        self.calls.append((model, system, user, max_tokens))
        if self.exc:
            raise self.exc
        return ""


@pytest.fixture(autouse=True)
def _clear_cache():
    clear_provider_cache()
    yield
    clear_provider_cache()


@pytest.mark.unit
class TestIsRateLimit:
    def test_code_429(self):
        assert _is_rate_limit(FakeRateLimitError()) is True

    def test_status_code_429(self):
        assert _is_rate_limit(Fake429StatusError()) is True

    def test_resource_exhausted_name(self):
        assert _is_rate_limit(FakeResourceExhausted()) is True

    def test_too_many_requests_name(self):
        class TooManyRequestsError(Exception):
            pass

        assert _is_rate_limit(TooManyRequestsError()) is True

    def test_string_contains_429(self):
        assert _is_rate_limit(Exception("Server returned 429")) is True

    def test_non_rate_limit_error(self):
        assert _is_rate_limit(FakeGenericError("something broke")) is False

    def test_empty_exception(self):
        assert _is_rate_limit(Exception()) is False


@pytest.mark.unit
@pytest.mark.anyio
class TestCompleteWithFallback:
    async def test_primary_succeeds_no_fallback(self, monkeypatch):
        primary = DummyProvider(response={"ok": True})

        def _fake_get_provider(task, settings):
            return primary, "primary-model"

        monkeypatch.setattr("app.llm.client.get_provider", _fake_get_provider)

        settings = Settings(
            openai_api_key="test",
            google_api_key="test",
            llm_provider_reconstruct="google",
            llm_model_reconstruct="gemini-2.5-flash",
            llm_fallback_provider_reconstruct="openai",
            llm_fallback_model_reconstruct="gpt-5.4-mini",
        )

        result = await complete_with_fallback(
            "reconstruct",
            settings,
            lambda p, m: p.complete_json(model=m, system="sys", user="user"),
        )
        assert result == {"ok": True}
        assert len(primary.calls) == 1
        assert primary.calls[0][0] == "primary-model"

    async def test_fallback_on_429(self, monkeypatch):
        primary = DummyProvider(exc=FakeRateLimitError())
        fallback = DummyProvider(response={"fallback": True})

        def _fake_get_provider(task, settings):
            return primary, "primary-model"

        monkeypatch.setattr("app.llm.client.get_provider", _fake_get_provider)

        # Force _get_or_create_provider to return our fallback when asked for openai
        original_get_or_create = __import__("app.llm.client", fromlist=[""])._get_or_create_provider

        def _fake_get_or_create(name, settings):
            if name == "openai":
                return fallback
            return original_get_or_create(name, settings)

        monkeypatch.setattr("app.llm.client._get_or_create_provider", _fake_get_or_create)

        settings = Settings(
            openai_api_key="test",
            google_api_key="test",
            llm_provider_reconstruct="google",
            llm_model_reconstruct="gemini-2.5-flash",
            llm_fallback_provider_reconstruct="openai",
            llm_fallback_model_reconstruct="gpt-5.4-mini",
        )

        result = await complete_with_fallback(
            "reconstruct",
            settings,
            lambda p, m: p.complete_json(model=m, system="sys", user="user"),
        )
        assert result == {"fallback": True}
        assert len(primary.calls) == 1
        assert len(fallback.calls) == 1
        assert fallback.calls[0][0] == "gpt-5.4-mini"

    async def test_non_429_error_raises(self, monkeypatch):
        primary = DummyProvider(exc=FakeGenericError("random error"))

        def _fake_get_provider(task, settings):
            return primary, "primary-model"

        monkeypatch.setattr("app.llm.client.get_provider", _fake_get_provider)

        settings = Settings(
            openai_api_key="test",
            google_api_key="test",
            llm_provider_reconstruct="google",
            llm_model_reconstruct="gemini-2.5-flash",
            llm_fallback_provider_reconstruct="openai",
            llm_fallback_model_reconstruct="gpt-5.4-mini",
        )

        with pytest.raises(FakeGenericError, match="random error"):
            await complete_with_fallback(
                "reconstruct",
                settings,
                lambda p, m: p.complete_json(model=m, system="sys", user="user"),
            )

    async def test_no_fallback_config_raises(self, monkeypatch):
        primary = DummyProvider(exc=FakeRateLimitError())

        def _fake_get_provider(task, settings):
            return primary, "primary-model"

        monkeypatch.setattr("app.llm.client.get_provider", _fake_get_provider)

        settings = Settings(
            openai_api_key="test",
            google_api_key="test",
            llm_provider_reconstruct="google",
            llm_model_reconstruct="gemini-2.5-flash",
            llm_fallback_provider_reconstruct="",
            llm_fallback_model_reconstruct="",
        )

        with pytest.raises(FakeRateLimitError):
            await complete_with_fallback(
                "reconstruct",
                settings,
                lambda p, m: p.complete_json(model=m, system="sys", user="user"),
            )

    async def test_translate_task_fallback(self, monkeypatch):
        primary = DummyProvider(exc=Fake429StatusError())
        fallback = DummyProvider(response={"translated": "hello"})

        def _fake_get_provider(task, settings):
            return primary, "primary-model"

        monkeypatch.setattr("app.llm.client.get_provider", _fake_get_provider)

        original_get_or_create = __import__("app.llm.client", fromlist=[""])._get_or_create_provider

        def _fake_get_or_create(name, settings):
            if name == "openai":
                return fallback
            return original_get_or_create(name, settings)

        monkeypatch.setattr("app.llm.client._get_or_create_provider", _fake_get_or_create)

        settings = Settings(
            openai_api_key="test",
            google_api_key="test",
            llm_provider_translate="google",
            llm_model_translate="gemini-2.5-flash",
            llm_fallback_provider_translate="openai",
            llm_fallback_model_translate="gpt-5.4-mini",
        )

        result = await complete_with_fallback(
            "translate",
            settings,
            lambda p, m: p.complete_json(model=m, system="sys", user="user"),
        )
        assert result == {"translated": "hello"}
        assert len(fallback.calls) == 1
        assert fallback.calls[0][0] == "gpt-5.4-mini"
