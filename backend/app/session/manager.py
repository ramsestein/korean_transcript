from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import Settings
from app.schemas import ImageContext, Segment, SessionManifest, SessionStartRequest, TargetLanguage
from app.session.store import (
    ensure_session_dirs,
    read_json,
    remove_session,
    session_dir,
    write_json,
)


def _manifest_path(data_dir: str, session_id: str) -> Path:
    return session_dir(data_dir, session_id) / "manifest.json"


async def create_session(request: SessionStartRequest, settings: Settings) -> str:
    session_id = str(uuid.uuid4())
    ensure_session_dirs(settings.data_dir, session_id)

    manifest = SessionManifest(
        session_id=session_id,
        target_language=request.target_language,
        meeting_prompt=request.meeting_prompt,
        chunk_seconds=request.chunk_seconds,
        overlap_seconds=request.overlap_seconds,
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    await write_json(
        _manifest_path(settings.data_dir, session_id),
        manifest.model_dump(),
    )
    return session_id


async def get_session_manifest(
    session_id: str,
    settings: Settings,
) -> SessionManifest | None:
    path = _manifest_path(settings.data_dir, session_id)
    data = await read_json(path)
    if data is None:
        return None
    try:
        return SessionManifest.model_validate(data)
    except Exception:
        return None


async def save_session_manifest(manifest: SessionManifest, settings: Settings) -> None:
    await write_json(
        _manifest_path(settings.data_dir, manifest.session_id),
        manifest.model_dump(),
    )


async def append_segment(
    session_id: str,
    segment: Segment,
    settings: Settings,
) -> None:
    manifest = await get_session_manifest(session_id, settings)
    if manifest is None:
        return
    existing = {s.segment_id: i for i, s in enumerate(manifest.segments)}
    if segment.segment_id in existing:
        manifest.segments[existing[segment.segment_id]] = segment
    else:
        manifest.segments.append(segment)
    await save_session_manifest(manifest, settings)


async def update_segment(
    session_id: str,
    segment: Segment,
    settings: Settings,
) -> None:
    await append_segment(session_id, segment, settings)


async def add_image_context(
    session_id: str,
    image_context: ImageContext,
    settings: Settings,
) -> None:
    manifest = await get_session_manifest(session_id, settings)
    if manifest is None:
        return
    manifest.image_contexts.append(image_context)
    await save_session_manifest(manifest, settings)


async def delete_session(session_id: str, settings: Settings) -> bool:
    return remove_session(settings.data_dir, session_id)
