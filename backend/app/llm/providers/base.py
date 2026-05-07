from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        images: list[bytes] | None = None,
        max_tokens: int = 2048,
    ) -> dict: ...

    async def complete_text(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 2048,
    ) -> str: ...
