from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Literal, TypeVar

T = TypeVar("T")

from app.config import Settings
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.llm.providers.base import LLMProvider
from app.llm.providers.google_provider import GoogleProvider
from app.llm.providers.openai_provider import OpenAIProvider

logger = logging.getLogger(__name__)

TaskName = Literal["reconstruct", "translate", "vision", "summary", "judge_a", "judge_b"]

_provider_cache: dict[str, LLMProvider] = {}


def _get_or_create_provider(provider_name: str, settings: Settings) -> LLMProvider:
    if provider_name in _provider_cache:
        return _provider_cache[provider_name]

    name = provider_name.lower()
    if name == "openai":
        provider: LLMProvider = OpenAIProvider(api_key=settings.openai_api_key)
    elif name == "anthropic":
        provider = AnthropicProvider(api_key=settings.anthropic_api_key)
    elif name in ("google", "gemini"):
        provider = GoogleProvider(api_key=settings.google_api_key)
    else:
        raise ValueError(f"Unknown LLM provider: '{provider_name}'")

    _provider_cache[provider_name] = provider
    return provider


def get_provider(task: TaskName, settings: Settings) -> tuple[LLMProvider, str]:
    """Return (provider_instance, model_name) for the given task."""
    task_upper = task.upper().replace("-", "_")
    provider_name: str = getattr(settings, f"llm_provider_{task_upper.lower()}")
    model_name: str = getattr(settings, f"llm_model_{task_upper.lower()}")

    provider = _get_or_create_provider(provider_name, settings)
    logger.debug("Task %s → provider=%s model=%s", task, provider_name, model_name)
    return provider, model_name


def _is_rate_limit(exc: Exception) -> bool:
    """Detect 429 / rate-limit errors from any provider."""
    if hasattr(exc, "code") and getattr(exc, "code", None) == 429:
        return True
    if hasattr(exc, "status_code") and getattr(exc, "status_code", None) == 429:
        return True
    exc_name = type(exc).__name__
    if "ResourceExhausted" in exc_name or "TooManyRequests" in exc_name:
        return True
    if "429" in str(exc):
        return True
    return False


async def complete_with_fallback(
    task: TaskName,
    settings: Settings,
    completion_fn: Callable[[LLMProvider, str], Awaitable[T]],
) -> T:
    """Run a completion using the primary provider; fall back on 429 errors."""
    provider, model = get_provider(task, settings)
    try:
        return await completion_fn(provider, model)
    except Exception as exc:
        if _is_rate_limit(exc):
            fb_provider_name: str = getattr(
                settings, f"llm_fallback_provider_{task}", ""
            )
            fb_model: str = getattr(
                settings, f"llm_fallback_model_{task}", ""
            )
            if fb_provider_name and fb_model:
                logger.warning(
                    "Rate limit (429) on primary provider for task %s. "
                    "Falling back to %s/%s",
                    task,
                    fb_provider_name,
                    fb_model,
                )
                fb_provider = _get_or_create_provider(fb_provider_name, settings)
                return await completion_fn(fb_provider, fb_model)
        raise


def clear_provider_cache() -> None:
    """Clear cached providers (useful for testing)."""
    _provider_cache.clear()
