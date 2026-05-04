from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

import aiofiles

logger = logging.getLogger(__name__)


def session_dir(data_dir: str, session_id: str) -> Path:
    return Path(data_dir) / session_id


def ensure_session_dirs(data_dir: str, session_id: str) -> Path:
    base = session_dir(data_dir, session_id)
    for sub in ("audio_raw", "audio_processed", "asr", "llm", "images"):
        (base / sub).mkdir(parents=True, exist_ok=True)
    return base


async def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False, indent=2))


async def read_json(path: Path) -> dict | list | None:
    if not path.exists():
        return None
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        return json.loads(await f.read())


async def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "wb") as f:
        await f.write(data)


async def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(text)


def remove_session(data_dir: str, session_id: str) -> bool:
    base = session_dir(data_dir, session_id)
    if base.exists():
        shutil.rmtree(base)
        logger.info("Removed session %s at %s", session_id, base)
        return True
    return False
