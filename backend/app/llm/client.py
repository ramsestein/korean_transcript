from __future__ import annotations

import logging
from typing import Literal

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


def clear_provider_cache() -> None:
    """Clear cached providers (useful for testing)."""
    _provider_cache.clear()
