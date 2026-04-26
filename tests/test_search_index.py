from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from src.models import ExtractionResult, Insight, VideoMeta
from src.pipeline import render
from src.search import index


def _meta() -> VideoMeta:
    return VideoMeta(
        video_id="QVJcdfkRpH8",
        url="https://www.youtube.com/watch?v=QVJcdfkRpH8",
        title="Claude Opus 4.7",
        channel="AI Explained",
        published=date(2026, 4, 17),
        duration_sec=1180,
    )


def _extraction(focus: str | None = None) -> ExtractionResult:
    return ExtractionResult(
        items=[
            Insight(
                kind="insight",
                text="Reasoning depth trades off against hallucination rate.",
                rank=1,
                context="Central thesis of the episode.",
            ),
            Insight(
                kind="quote",
                text="I ship code I don't read.",
                speaker="A",
                start_ms=17_000,
                rank=2,
            ),
            Insight(
                kind="spicy_take",
                text="Benchmarks are theater until contract season.",
                rank=3,
            ),
        ],
        model="gpt-5.4-mini",
        prompt_version="v2",
        input_tokens=4000,
        output_tokens=500,
        speakers={"A": "Andrew Huberman"},
        focus=focus,
    )


def _write_note(
    vault: Path,
    extraction: ExtractionResult,
    *,
    meta: VideoMeta | None = None,
    filename: str = "AI Explained — Claude Opus 4.7 [2026-04-17].md",
) -> Path:
    body = render.render_note(
        meta or _meta(),
        extraction,
        version=1,
        processed_at=datetime(2026, 4, 23, 12, 0, 0),
        cost_usd={"stt": 0.07, "extract": 0.01},
    )
    path = vault / filename
    path.write_text(body)
    return path


def test_parse_note_extracts_frontmatter(tmp_path: Path) -> None:
    path = _write_note(tmp_path, _extraction())
    note = index.parse_note(path)
    assert note.title == "Claude Opus 4.7"
    assert note.channel == "AI Explained"
    assert note.video_id == "QVJcdfkRpH8"
    assert note.published == date(2026, 4, 17)
    assert note.focus is None


def test_parse_note_extracts_focus_when_set(tmp_path: Path) -> None:
    path = _write_note(
        tmp_path,
        _extraction(focus="career advice"),
        filename="AI Explained — Claude (focus career-advice).md",
    )
    note = index.parse_note(path)
    assert note.focus == "career advice"


def test_parse_note_extracts_callouts(tmp_path: Path) -> None:
    path = _write_note(tmp_path, _extraction())
    note = index.parse_note(path)
    assert len(note.callouts) == 3

    insight, quote, spicy = note.callouts
    assert insight.kind == "insight"
    assert insight.rank == 1
    assert "Reasoning depth" in insight.text
    assert insight.context == "Central thesis of the episode."

    assert quote.kind == "quote"
    assert quote.rank == 2
    assert quote.text == "I ship code I don't read."
    assert quote.speaker == "Andrew Huberman"
    assert quote.start_ms == 17_000

    assert spicy.kind == "spicy_take"
    assert spicy.rank == 3
    assert "Benchmarks" in spicy.text


def test_parse_note_quote_strips_surrounding_quotes(tmp_path: Path) -> None:
    # Render wraps quote text in literal "" — parse must strip them.
    path = _write_note(tmp_path, _extraction())
    note = index.parse_note(path)
    quote = next(c for c in note.callouts if c.kind == "quote")
    assert not quote.text.startswith('"')
    assert not quote.text.endswith('"')


def test_walk_vault_returns_all_podsave_notes(tmp_path: Path) -> None:
    _write_note(tmp_path, _extraction(), filename="a.md")
    _write_note(tmp_path, _extraction(), filename="b.md")
    notes = index.walk_vault(tmp_path)
    assert len(notes) == 2


def test_walk_vault_skips_non_podsave_notes(tmp_path: Path) -> None:
    _write_note(tmp_path, _extraction(), filename="podsave-note.md")
    (tmp_path / "daily-note.md").write_text(
        "---\ntitle: Daily Note\ntags:\n  - daily\n---\n\nfreeform notes\n"
    )
    notes = index.walk_vault(tmp_path)
    assert len(notes) == 1
    assert notes[0].title == "Claude Opus 4.7"


def test_walk_vault_skips_dot_directories(tmp_path: Path) -> None:
    _write_note(tmp_path, _extraction(), filename="real.md")
    obsidian_dir = tmp_path / ".obsidian"
    obsidian_dir.mkdir()
    (obsidian_dir / "config.md").write_text(
        "---\ntags:\n  - podsave\n---\n\nshould be ignored\n"
    )
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "leak.md").write_text("---\ntags: [podsave]\n---\nx\n")
    notes = index.walk_vault(tmp_path)
    assert len(notes) == 1


def test_walk_vault_recurses_into_subdirectories(tmp_path: Path) -> None:
    sub = tmp_path / "callouts"
    sub.mkdir()
    _write_note(tmp_path, _extraction(), filename="top.md")
    _write_note(sub, _extraction(), filename="nested.md")
    notes = index.walk_vault(tmp_path)
    assert len(notes) == 2


def test_render_then_parse_roundtrip(tmp_path: Path) -> None:
    """The whole point: render output must parse back to the same callouts."""
    extraction = _extraction()
    path = _write_note(tmp_path, extraction)
    note = index.parse_note(path)

    parsed_kinds = [c.kind for c in note.callouts]
    expected_kinds = [item.kind for item in extraction.items]
    assert parsed_kinds == expected_kinds

    parsed_ranks = [c.rank for c in note.callouts]
    expected_ranks = [item.rank for item in extraction.items]
    assert parsed_ranks == expected_ranks
