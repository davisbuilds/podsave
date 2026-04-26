"""Walk a vault directory and parse each podsave-tagged markdown note back into a Note."""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel

from src.search.callout import Callout

_FRONTMATTER_DELIM = "---"
_CALLOUT_HEADER = re.compile(r"^>\s*\[!(?P<type>note|quote|warning)\]\s*(?P<title>.*)$")
_CALLOUT_TITLE = re.compile(
    r"^(?P<rank>\d+)\.\s+(?P<label>Insight|Quote|Spicy take)"
    r"(?:\s+—\s+\[(?P<speaker>[^\]]+)\s+@\s+[^\]]+\]\((?P<url>[^)]+)\))?"
    r"\s*$"
)
_TIMESTAMP_PARAM = re.compile(r"[?&]t=(\d+)s")
_KIND_BY_CALLOUT_TYPE = {"note": "insight", "quote": "quote", "warning": "spicy_take"}


class Note(BaseModel):
    """A parsed podsave note: frontmatter + callouts."""

    path: Path
    title: str
    channel: str
    video_id: str
    url: str
    published: date | None = None
    processed: datetime | None = None
    focus: str | None = None
    callouts: list[Callout] = []


def walk_vault(vault_dir: Path) -> list[Note]:
    """Return every podsave-tagged note under `vault_dir`, recursively.

    Skips dotfiles/dotdirs (e.g. `.obsidian/`, `.git/`) and any markdown that
    doesn't carry `podsave` in its frontmatter `tags:` list.
    """
    notes: list[Note] = []
    for path in sorted(vault_dir.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(vault_dir).parts):
            continue
        note = _try_parse(path)
        if note is not None:
            notes.append(note)
    return notes


def parse_note(path: Path) -> Note:
    """Parse a single rendered podsave note. Raises on malformed frontmatter."""
    text = path.read_text()
    fm_text, body = _split_frontmatter(text)
    fm = yaml.safe_load(fm_text) or {}
    return Note(
        path=path,
        title=str(fm.get("title", "")),
        channel=str(fm.get("channel", "")),
        video_id=str(fm.get("video_id", "")),
        url=str(fm.get("url", "")),
        published=_coerce_date(fm.get("published")),
        processed=_coerce_datetime(fm.get("processed")),
        focus=(str(fm["focus"]) if fm.get("focus") else None),
        callouts=_parse_callouts(body),
    )


def _try_parse(path: Path) -> Note | None:
    """Return the parsed Note if the file is a podsave note, else None."""
    try:
        text = path.read_text()
    except OSError:
        return None
    try:
        fm_text, _ = _split_frontmatter(text)
        fm = yaml.safe_load(fm_text) or {}
    except (ValueError, yaml.YAMLError):
        return None
    tags = fm.get("tags") or []
    if "podsave" not in [str(t) for t in tags]:
        return None
    return parse_note(path)


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Return (frontmatter_yaml, body). Raises ValueError if not delimited."""
    if not text.startswith(_FRONTMATTER_DELIM):
        raise ValueError("missing opening frontmatter delimiter")
    end = text.find(f"\n{_FRONTMATTER_DELIM}", len(_FRONTMATTER_DELIM))
    if end == -1:
        raise ValueError("missing closing frontmatter delimiter")
    fm = text[len(_FRONTMATTER_DELIM) : end]
    body_start = end + len(_FRONTMATTER_DELIM) + 1
    return fm, text[body_start:]


def _coerce_date(value: object) -> date | None:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str) and value:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _coerce_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _parse_callouts(body: str) -> list[Callout]:
    """Walk the markdown body, grouping `>` lines into callout blocks."""
    callouts: list[Callout] = []
    block: list[str] = []
    for line in body.splitlines():
        if line.startswith(">"):
            block.append(line)
            continue
        if block:
            callout = _block_to_callout(block)
            if callout is not None:
                callouts.append(callout)
            block = []
    if block:
        callout = _block_to_callout(block)
        if callout is not None:
            callouts.append(callout)
    return callouts


def _block_to_callout(lines: list[str]) -> Callout | None:
    if not lines:
        return None
    header = _CALLOUT_HEADER.match(lines[0])
    if header is None:
        return None
    kind = _KIND_BY_CALLOUT_TYPE.get(header.group("type"))
    if kind is None:
        return None

    title_match = _CALLOUT_TITLE.match(header.group("title").strip())
    if title_match is None:
        return None
    rank = int(title_match.group("rank"))
    speaker = title_match.group("speaker")
    url = title_match.group("url")
    start_ms = _start_ms_from_url(url) if url else None

    body_lines = [_strip_quote_prefix(line) for line in lines[1:]]
    text, context = _split_text_and_context(body_lines)
    if kind == "quote":
        text = _strip_surrounding_quotes(text)

    return Callout(
        kind=kind,  # type: ignore[arg-type]
        rank=rank,
        text=text,
        context=context,
        speaker=speaker,
        start_ms=start_ms,
    )


def _strip_quote_prefix(line: str) -> str:
    if line.startswith("> "):
        return line[2:]
    if line.startswith(">"):
        return line[1:]
    return line


def _split_text_and_context(body_lines: list[str]) -> tuple[str, str | None]:
    """Reverse of render's body shape: text, then optional blank + *italic* context."""
    cleaned = [line.rstrip() for line in body_lines]
    while cleaned and not cleaned[-1]:
        cleaned.pop()

    context: str | None = None
    if len(cleaned) >= 2 and not cleaned[-2] and _looks_italic(cleaned[-1]):
        context = cleaned[-1].strip("*").strip()
        cleaned = cleaned[:-2]

    text = " ".join(line for line in cleaned if line).strip()
    return text, context


def _looks_italic(line: str) -> bool:
    stripped = line.strip()
    return len(stripped) >= 3 and stripped.startswith("*") and stripped.endswith("*")


def _strip_surrounding_quotes(text: str) -> str:
    if len(text) >= 2 and text.startswith('"') and text.endswith('"'):
        return text[1:-1]
    return text


def _start_ms_from_url(url: str) -> int | None:
    match = _TIMESTAMP_PARAM.search(url)
    if match is None:
        return None
    return int(match.group(1)) * 1000
