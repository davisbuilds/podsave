from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from rich.console import Console

from src.search import render
from src.search.callout import Callout
from src.search.index import Note
from src.search.matcher import Match


def _note(*, title: str = "Source Note", path: Path | None = None) -> Note:
    return Note(
        path=path or Path("/vault/source-note.md"),
        title=title,
        channel="The Channel",
        video_id="QVJcdfkRpH8",
        url="https://www.youtube.com/watch?v=QVJcdfkRpH8",
        published=date(2026, 1, 1),
        processed=datetime(2026, 1, 1),
        callouts=[],
    )


def _quote_match() -> tuple[Match, Note]:
    callout = Callout(
        kind="quote",
        rank=2,
        text="The world is a dynamic mess.",
        speaker="Andrew Huberman",
        start_ms=83_000,
    )
    return (
        Match(callout=callout, score=2, matched_terms=["dynamic"]),
        _note(),
    )


def _insight_match() -> tuple[Match, Note]:
    callout = Callout(
        kind="insight",
        rank=1,
        text="Reasoning trades off against hallucination.",
        context="Central thesis.",
    )
    return (Match(callout=callout, score=1, matched_terms=["reasoning"]), _note())


def _capture_terminal(matches: list[tuple[Match, Note]], **kwargs: object) -> str:
    console = Console(record=True, width=120)
    render.render_terminal(console, matches, query="x", **kwargs)  # type: ignore[arg-type]
    return console.export_text()


def test_render_terminal_includes_source_note_basename() -> None:
    out = _capture_terminal([_quote_match()])
    assert "source-note" in out


def test_render_terminal_includes_quote_timestamp_link() -> None:
    out = _capture_terminal([_quote_match()])
    assert "QVJcdfkRpH8" in out
    assert "t=83s" in out


def test_render_terminal_zero_results() -> None:
    out = _capture_terminal([])
    assert "no callouts matched" in out.lower()


def test_render_terminal_summary_line_counts_unique_notes() -> None:
    n1 = _note(title="A", path=Path("/vault/a.md"))
    n2 = _note(title="B", path=Path("/vault/b.md"))
    c1 = Callout(kind="insight", rank=1, text="x")
    c2 = Callout(kind="insight", rank=1, text="y")
    pairs = [
        (Match(callout=c1, score=1, matched_terms=["x"]), n1),
        (Match(callout=c2, score=1, matched_terms=["x"]), n2),
    ]
    out = _capture_terminal(pairs)
    assert "2 callout" in out
    assert "2 note" in out


def test_render_vault_note_creates_callouts_dir(tmp_path: Path) -> None:
    out_path = render.render_vault_note(
        tmp_path,
        [_quote_match()],
        query="dynamic",
        notes_searched=5,
        filters={},
        generated_at=datetime(2026, 4, 26, 12, 0, 0),
    )
    assert (tmp_path / "Callouts").is_dir()
    assert out_path.parent == tmp_path / "Callouts"


def test_render_vault_note_writes_obsidian_callouts_with_wikilinks(tmp_path: Path) -> None:
    out_path = render.render_vault_note(
        tmp_path,
        [_quote_match(), _insight_match()],
        query="reasoning",
        notes_searched=3,
        filters={"kind": "insight"},
        generated_at=datetime(2026, 4, 26, 12, 0, 0),
    )
    text = out_path.read_text()
    assert "> [!quote]" in text
    assert "> [!note]" in text
    assert "[[source-note]]" in text
    assert 'query: "reasoning"' in text
    assert "kind: insight" in text
    assert "  - podsave\n  - podsave/search" in text


def test_render_vault_note_filename_slugs_query(tmp_path: Path) -> None:
    out_path = render.render_vault_note(
        tmp_path,
        [_insight_match()],
        query="Memory Consolidation Tactics!",
        notes_searched=1,
        filters={},
        generated_at=datetime(2026, 4, 26, 12, 0, 0),
    )
    assert out_path.name.startswith("Search — memory-consolidation-tactics [2026-04-26]")
    assert out_path.suffix == ".md"


def test_render_vault_note_versions_on_collision(tmp_path: Path) -> None:
    args = dict(
        query="x",
        notes_searched=1,
        filters={},
        generated_at=datetime(2026, 4, 26, 12, 0, 0),
    )
    p1 = render.render_vault_note(tmp_path, [_insight_match()], **args)  # type: ignore[arg-type]
    p2 = render.render_vault_note(tmp_path, [_insight_match()], **args)  # type: ignore[arg-type]
    assert p1.exists()
    assert p2.exists()
    assert p1 != p2
    assert "(v2)" in p2.name
