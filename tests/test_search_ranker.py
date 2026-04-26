from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from src.search import ranker
from src.search.callout import Callout
from src.search.index import Note
from src.search.matcher import Match


def _note(processed: datetime) -> Note:
    return Note(
        path=Path("/tmp/x.md"),
        title="T",
        channel="Ch",
        video_id="v",
        url="https://x",
        published=date(2026, 1, 1),
        processed=processed,
        callouts=[],
    )


def _match(text: str, score: int) -> tuple[Match, Note]:
    callout = Callout(kind="insight", rank=1, text=text)
    note = _note(datetime(2026, 1, 1))
    return Match(callout=callout, score=score, matched_terms=["x"]), note


def test_rank_more_matches_first() -> None:
    a = _match("low", 1)
    b = _match("high", 5)
    ranked = ranker.rank([a, b])
    assert [m.callout.text for m, _ in ranked] == ["high", "low"]


def test_rank_recency_breaks_ties() -> None:
    older_note = _note(datetime(2024, 1, 1))
    newer_note = _note(datetime(2026, 1, 1))
    older = (
        Match(
            callout=Callout(kind="insight", rank=1, text="older"),
            score=3,
            matched_terms=["x"],
        ),
        older_note,
    )
    newer = (
        Match(
            callout=Callout(kind="insight", rank=1, text="newer"),
            score=3,
            matched_terms=["x"],
        ),
        newer_note,
    )
    ranked = ranker.rank([older, newer])
    assert [m.callout.text for m, _ in ranked] == ["newer", "older"]


def test_rank_truncates_to_limit() -> None:
    matches = [_match(f"m{i}", 1) for i in range(10)]
    ranked = ranker.rank(matches, limit=3)
    assert len(ranked) == 3


def test_rank_limit_zero_returns_all() -> None:
    matches = [_match(f"m{i}", 1) for i in range(7)]
    ranked = ranker.rank(matches, limit=0)
    assert len(ranked) == 7
