from __future__ import annotations


class GoogleProvider:
    """Stub for future Google Gemini provider support. Raises NotImplementedError."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        images: list[bytes] | None = None,
        max_tokens: int = 2048,
    ) -> dict:
        raise NotImplementedError(
            "GoogleProvider is not yet implemented. "
            "Set LLM_PROVIDER_<TASK>=openai in .env to use OpenAI instead."
        )
