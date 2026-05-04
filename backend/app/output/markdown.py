from __future__ import annotations

import re
from pathlib import Path


_UNSAFE_HEADING = re.compile(r"[^\w\s\-–—]")


def safe_markdown_heading(text: str) -> str:
    """Strip characters that could break Markdown heading rendering."""
    return _UNSAFE_HEADING.sub("", text).strip()


def write_markdown(path: Path, content: str) -> None:
    """Write Markdown content to a file, ensuring UTF-8 encoding."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_markdown(path: Path) -> str | None:
    """Read Markdown content from a file, return None if missing."""
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")
