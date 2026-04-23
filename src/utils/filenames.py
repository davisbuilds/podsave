"""Filesystem-safe, readable filenames for Obsidian notes with versioning."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

_UNSAFE_CHARS = re.compile(r'[\\/:\*\?"<>\|\x00-\x1f]')
_VERSION_SUFFIX = re.compile(r" \(v(\d+)\)$")


def safe_name(channel: str, title: str, *, published: date | None) -> str:
    """Return a readable, filesystem-safe basename (no extension): `Channel — Title [YYYY-MM-DD]`.

    Collapses runs of whitespace, strips path/control characters, trims to 180 chars so
    the whole basename stays well under macOS's 255-byte limit.
    """
    channel_clean = _clean(channel)
    title_clean = _clean(title)
    base = f"{channel_clean} — {title_clean}"
    if published:
        base = f"{base} [{published.isoformat()}]"
    return base[:180].rstrip()


def _clean(s: str) -> str:
    normalized = unicodedata.normalize("NFC", s)
    stripped = _UNSAFE_CHARS.sub("", normalized)
    collapsed = re.sub(r"\s+", " ", stripped).strip()
    return collapsed or "untitled"


def next_version_path(
    vault_dir: Path, base_name: str, *, extension: str = ".md"
) -> tuple[Path, int]:
    """Pick the next non-colliding path for base_name in vault_dir.

    First free slot is `<base>.md` (version 1). If taken, `<base> (v2).md`, etc.
    Returns (path, version).
    """
    v1 = vault_dir / f"{base_name}{extension}"
    if not v1.exists():
        return v1, 1

    n = 2
    while True:
        candidate = vault_dir / f"{base_name} (v{n}){extension}"
        if not candidate.exists():
            return candidate, n
        n += 1
