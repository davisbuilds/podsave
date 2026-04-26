"""Filesystem-safe, readable filenames for Obsidian notes with versioning."""

from __future__ import annotations

import re
import unicodedata
from datetime import date
from pathlib import Path

_UNSAFE_CHARS = re.compile(r'[\\/:\*\?"<>\|\x00-\x1f]')
_VERSION_SUFFIX = re.compile(r" \(v(\d+)\)$")
_TRAILING_CHANNEL_SEPARATORS = ("|", "—", "-")
_FOCUS_SLUG_NONALNUM = re.compile(r"[^a-z0-9]+")
_FOCUS_SLUG_MAX = 40


def safe_name(
    channel: str,
    title: str,
    *,
    published: date | None,
    focus: str | None = None,
) -> str:
    """Return a readable, filesystem-safe basename (no extension): `Channel — Title [YYYY-MM-DD]`.

    Collapses runs of whitespace, strips path/control characters, trims to 180 chars so
    the whole basename stays well under macOS's 255-byte limit. If the title ends with
    a separator (`|`, `—`, ` - `) followed by the channel name, that suffix is removed
    so the channel doesn't appear twice in the filename. When `focus` is set and slugifies
    to a non-empty value, ` (focus: <slug>)` is appended so different lenses of the same
    video are visually distinct in the vault.
    """
    title_no_suffix = _strip_trailing_channel(title, channel)
    channel_clean = _clean(channel)
    title_clean = _clean(title_no_suffix)
    base = f"{channel_clean} — {title_clean}"
    if published:
        base = f"{base} [{published.isoformat()}]"
    base = base[:180].rstrip()
    slug = focus_slug(focus)
    if slug:
        base = f"{base} (focus: {slug})"
    return base


def focus_slug(focus: str | None) -> str | None:
    """Slugify a focus string for use in filenames and tags.

    Lowercase, NFC-normalized, runs of non-`[a-z0-9]` collapse to a single `-`,
    leading/trailing `-` trimmed, capped at 40 chars (cut on a separator boundary
    when possible). Empty / whitespace-only input returns None.
    """
    if focus is None:
        return None
    normalized = unicodedata.normalize("NFC", focus).strip().lower()
    if not normalized:
        return None
    slug = _FOCUS_SLUG_NONALNUM.sub("-", normalized).strip("-")
    if not slug:
        return None
    if len(slug) > _FOCUS_SLUG_MAX:
        slug = slug[:_FOCUS_SLUG_MAX].rstrip("-")
    return slug or None


def _strip_trailing_channel(title: str, channel: str) -> str:
    """If title ends with a known separator + channel name, drop that suffix."""
    if not channel.strip():
        return title
    channel_norm = unicodedata.normalize("NFC", channel).strip().casefold()
    title_norm = unicodedata.normalize("NFC", title).rstrip()
    for sep in _TRAILING_CHANNEL_SEPARATORS:
        idx = title_norm.rfind(sep)
        if idx == -1:
            continue
        before = title_norm[:idx]
        suffix = title_norm[idx + len(sep) :].strip()
        # Hyphen needs a space before it to count as a separator (avoid splitting
        # mid-word like "state-of-the-art").
        if sep == "-" and (not before or not before.endswith(" ")):
            continue
        if suffix.casefold() == channel_norm:
            return before.rstrip()
    return title


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
