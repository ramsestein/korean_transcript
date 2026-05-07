from __future__ import annotations

import io
import json
import logging

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)


class GoogleProvider:
    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    async def complete_json(
        self,
        model: str,
        system: str,
        user: str,
        images: list[bytes] | None = None,
        max_tokens: int = 2048,
    ) -> dict:
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            temperature=0.2,
            max_output_tokens=max_tokens,
        )

        if images:
            import PIL.Image

            parts: list[types.PartUnionDict] = [types.Part.from_text(text=user)]
            for img_bytes in images:
                img = PIL.Image.open(io.BytesIO(img_bytes))
                fmt = (img.format or "JPEG").lower()
                mime = f"image/{fmt}"
                parts.append(types.Part.from_bytes(data=img_bytes, mime_type=mime))
            contents: types.ContentUnionDict = parts
        else:
            contents = user

        response = await self._client.aio.models.generate_content(
            model=model,
            contents=contents,
            config=config,
        )

        raw = response.text or "{}"
        logger.debug("Gemini %s response: %d chars", model, len(raw))
        return self._parse_json(raw)

    @staticmethod
    def _parse_json(raw: str) -> dict:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Gemini JSON response: %s | raw=%s", exc, raw[:200])
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc
