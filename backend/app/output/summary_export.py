from __future__ import annotations

import logging
from pathlib import Path

from app.config import Settings
from app.llm.summarize import generate_summary
from app.output.markdown import write_markdown
from app.schemas import ImageContext, Segment, SessionManifest, TargetLanguage
from app.session.store import session_dir

logger = logging.getLogger(__name__)


async def export_summary(
    manifest: SessionManifest,
    settings: Settings,
) -> Path:
    """
    Generate the operational summary.md and write it to the session folder.
    Returns the path to the written file.
    """
    logger.info("Generating summary for session %s", manifest.session_id)

    markdown_text = await generate_summary(
        segments=manifest.segments,
        target_language=manifest.target_language,
        meeting_prompt=manifest.meeting_prompt,
        image_contexts=manifest.image_contexts,
        settings=settings,
    )

    out_path = session_dir(settings.data_dir, manifest.session_id) / "summary.md"
    write_markdown(out_path, markdown_text)
    logger.info("Summary written to %s", out_path)
    return out_path
