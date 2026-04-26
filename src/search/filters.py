"""Filter parsed Notes by frontmatter (kind/channel/focus/since)."""

from __future__ import annotations

import re
from datetime import date, timedelta

from src.errors import PodsaveError
from src.search.callout import Callout
from src.search.index import Note
from src.utils.filenames import focus_slug

_RELATIVE_SINCE = re.compile(r"^(\d+)([dwmy])$")
_RELATIVE_DAYS = {"d": 1, "w": 7, "m": 30, "y": 365}


class FilterError(PodsaveError):
    pass


def apply(
    notes: list[Note],
    *,
    kind: str | None = None,
    channel: str | None = None,
    focus: str | None = None,
    since: str | None = None,
) -> list[Note]:
    """Return a new list of Notes (with possibly-narrowed callouts) matching all filters.

    Filters compose AND-style. Notes that end up with zero callouts are dropped
    so the matcher never sees an empty haystack note.
    """
    cutoff = _parse_since(since) if since else None
    target_focus_slug = focus_slug(focus) if focus else None
    channel_q = channel.lower() if channel else None

    out: list[Note] = []
    for note in notes:
        if cutoff is not None and (note.published is None or note.published < cutoff):
            continue
        if channel_q and channel_q not in note.channel.lower():
            continue
        if target_focus_slug and focus_slug(note.focus) != target_focus_slug:
            continue
        callouts = _filter_callouts(note.callouts, kind=kind)
        if not callouts:
            continue
        out.append(note.model_copy(update={"callouts": callouts}))
    return out


def _filter_callouts(callouts: list[Callout], *, kind: str | None) -> list[Callout]:
    if kind is None:
        return callouts
    return [c for c in callouts if c.kind == kind]


def _parse_since(value: str) -> date:
    rel = _RELATIVE_SINCE.match(value)
    if rel:
        n = int(rel.group(1))
        days = n * _RELATIVE_DAYS[rel.group(2)]
        return date.today() - timedelta(days=days)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise FilterError(
            f"--since: '{value}' is not a date (expected YYYY-MM-DD or e.g. 30d / 6m / 1y)"
        ) from exc
