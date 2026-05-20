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

    async def complete_text(
        self,
        model: str,
        system: str,
        user: str,
        max_tokens: int = 2048,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            max_output_tokens=max_tokens,
        )
        response = await self._client.aio.models.generate_content(
            model=model,
            contents=user,
            config=config,
        )
        return response.text or ""

    @staticmethod
    def _parse_json(raw: str) -> dict:
        # Gemini occasionally wraps JSON in markdown fences despite response_mime_type=application/json
        stripped = raw.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            # Drop first line (```json or ```) and last line (```)
            inner = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            stripped = inner.strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Gemini returned malformed JSON (%s), attempting repair | raw=%s", exc, raw[:200]
            )
            try:
                from json_repair import repair_json  # type: ignore[import-untyped]
                repaired = repair_json(stripped, return_objects=True)
                if isinstance(repaired, dict):
                    return repaired
            except Exception as repair_exc:
                logger.warning("json_repair also failed: %s", repair_exc)
            logger.error("Could not parse Gemini response as JSON; returning raw text | raw=%s", raw[:200])
            return {"__raw__": raw}
