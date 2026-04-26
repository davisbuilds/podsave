from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from src.search import filters
from src.search.callout import Callout
from src.search.index import Note


def _note(
    *,
    title: str = "T",
    channel: str = "Ch",
    focus: str | None = None,
    published: date | None = date(2026, 1, 1),
    callouts: list[Callout] | None = None,
) -> Note:
    return Note(
        path=Path("/tmp/x.md"),
        title=title,
        channel=channel,
        video_id="vid",
        url="https://x",
        published=published,
        processed=datetime(2026, 1, 1),
        focus=focus,
        callouts=callouts
        or [
            Callout(kind="insight", rank=1, text="i"),
            Callout(kind="quote", rank=2, text="q", speaker="A", start_ms=0),
        ],
    )


def test_filter_by_kind_keeps_only_matching_callouts() -> None:
    notes = [_note()]
    out = filters.apply(notes, kind="quote")
    assert len(out) == 1
    assert [c.kind for c in out[0].callouts] == ["quote"]


def test_filter_by_kind_drops_notes_with_no_surviving_callouts() -> None:
    notes = [_note(callouts=[Callout(kind="insight", rank=1, text="i")])]
    out = filters.apply(notes, kind="quote")
    assert out == []


def test_filter_by_channel_substring_case_insensitive() -> None:
    notes = [_note(channel="Anthropic"), _note(channel="AI Explained")]
    out = filters.apply(notes, channel="anthropic")
    assert len(out) == 1
    assert out[0].channel == "Anthropic"


def test_filter_by_focus_slug_match() -> None:
    notes = [
        _note(focus="career advice"),
        _note(focus="model personality"),
        _note(focus=None),
    ]
    out = filters.apply(notes, focus="Career  Advice!!")
    assert len(out) == 1
    assert out[0].focus == "career advice"


def test_filter_by_focus_skips_unfocused_notes() -> None:
    notes = [_note(focus=None), _note(focus="x")]
    out = filters.apply(notes, focus="x")
    assert len(out) == 1


def test_filter_by_since_absolute_date() -> None:
    notes = [
        _note(published=date(2024, 6, 1)),
        _note(published=date(2026, 6, 1)),
    ]
    out = filters.apply(notes, since="2025-01-01")
    assert len(out) == 1
    assert out[0].published == date(2026, 6, 1)


def test_filter_by_since_relative() -> None:
    today = date.today()
    notes = [
        _note(published=today - timedelta(days=10)),
        _note(published=today - timedelta(days=60)),
    ]
    out = filters.apply(notes, since="30d")
    assert len(out) == 1


def test_filter_by_since_invalid_raises() -> None:
    with pytest.raises(filters.FilterError):
        filters.apply([_note()], since="notarealdate")


def test_filters_compose_and() -> None:
    notes = [
        _note(channel="Anthropic", callouts=[Callout(kind="quote", rank=1, text="q")]),
        _note(channel="Anthropic", callouts=[Callout(kind="insight", rank=1, text="i")]),
        _note(channel="Other", callouts=[Callout(kind="quote", rank=1, text="q")]),
    ]
    out = filters.apply(notes, kind="quote", channel="anthropic")
    assert len(out) == 1
    assert out[0].channel == "Anthropic"
    assert out[0].callouts[0].kind == "quote"
