from __future__ import annotations

import base64
import json
import logging
from typing import Any

import openai

logger = logging.getLogger(__name__)


class OpenAIProvider:
    def __init__(self, api_key: str) -> None:
        self._client = openai.AsyncOpenAI(api_key=api_key)

    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        images: list[bytes] | None = None,
        max_tokens: int = 2048,
    ) -> dict:
        messages = self._build_messages(system, user, images)
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_completion_tokens=max_tokens,
            temperature=0.2,
        )
        raw = response.choices[0].message.content or "{}"
        logger.debug("OpenAI %s response: %d chars", model, len(raw))
        return self._parse_json(raw)

    async def complete_text(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 2048,
    ) -> str:
        messages = self._build_messages(system, user, None)
        response = await self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_tokens,
            temperature=0.2,
        )
        return response.choices[0].message.content or ""

    def _build_messages(
        self,
        system: str,
        user: str,
        images: list[bytes] | None,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        if images:
            content: list[dict[str, Any]] = [{"type": "text", "text": user}]
            for img_bytes in images:
                b64 = base64.b64encode(img_bytes).decode("utf-8")
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                })
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": user})
        return messages

    @staticmethod
    def _parse_json(raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning(
                "OpenAI returned malformed JSON (%s), attempting repair | raw=%s", exc, raw[:200]
            )
            try:
                from json_repair import repair_json  # type: ignore[import-untyped]
                repaired = repair_json(raw, return_objects=True)
                if isinstance(repaired, dict):
                    return repaired
            except Exception as repair_exc:
                logger.warning("json_repair also failed: %s", repair_exc)
            logger.error("Could not parse OpenAI response as JSON; returning raw text | raw=%s", raw[:200])
            return {"__raw__": raw}
