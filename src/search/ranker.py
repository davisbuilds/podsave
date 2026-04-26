"""Rank matches by score (more hits first) with note recency as tiebreak."""

from __future__ import annotations

from datetime import datetime

from src.search.index import Note
from src.search.matcher import Match


def rank(
    pairs: list[tuple[Match, Note]],
    *,
    limit: int | None = None,
) -> list[tuple[Match, Note]]:
    """Sort (Match, Note) pairs by score desc, then by note.processed desc. Truncate to limit."""
    ranked = sorted(
        pairs,
        key=lambda pair: (pair[0].score, _processed_key(pair[1])),
        reverse=True,
    )
    if limit and limit > 0:
        ranked = ranked[:limit]
    return ranked


def _processed_key(note: Note) -> datetime:
    return note.processed or datetime.min
