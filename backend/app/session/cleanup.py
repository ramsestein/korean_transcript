from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings

logger = logging.getLogger(__name__)


async def cleanup_expired_sessions(settings: Settings) -> int:
    """
    Scan DATA_DIR and remove any session folder whose manifest.json.created_at
    is older than SESSION_TTL_HOURS. Returns count of removed sessions.
    """
    data_path = Path(settings.data_dir)
    if not data_path.exists():
        return 0

    removed = 0
    now = datetime.now(timezone.utc)
    ttl_seconds = settings.session_ttl_hours * 3600

    for entry in data_path.iterdir():
        if not entry.is_dir():
            continue
        manifest_path = entry / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                manifest = json.load(f)
            created_at_str = manifest.get("created_at", "")
            if not created_at_str:
                continue
            created_at = datetime.fromisoformat(created_at_str)
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            age_seconds = (now - created_at).total_seconds()
            if age_seconds > ttl_seconds:
                shutil.rmtree(entry)
                logger.info("Cleaned up expired session %s (age=%.0fh)", entry.name, age_seconds / 3600)
                removed += 1
        except Exception as exc:
            logger.warning("Error scanning session %s: %s", entry.name, exc)

    return removed


async def run_cleanup_loop(settings: Settings) -> None:
    """Background task: run cleanup every hour indefinitely."""
    while True:
        try:
            count = await cleanup_expired_sessions(settings)
            if count:
                logger.info("Cleanup cycle removed %d expired sessions", count)
        except Exception as exc:
            logger.error("Cleanup cycle error: %s", exc)
        await asyncio.sleep(3600)
