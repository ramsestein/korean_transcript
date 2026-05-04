from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Path

from app.config import Settings, get_settings
from app.session.manager import get_session_manifest
from app.schemas import SessionManifest


async def verify_session(
    session_id: Annotated[str, Path()],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SessionManifest:
    manifest = await get_session_manifest(session_id, settings)
    if manifest is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return manifest
