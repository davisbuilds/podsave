from __future__ import annotations

from datetime import date, datetime

from src.models import ExtractionResult, Insight, VideoMeta
from src.pipeline import render


def _fixture() -> tuple[VideoMeta, ExtractionResult]:
    meta = VideoMeta(
        video_id="QVJcdfkRpH8",
        url="https://www.youtube.com/watch?v=QVJcdfkRpH8",
        title="Claude Opus 4.7",
        channel="AI Explained",
        published=date(2026, 4, 17),
        duration_sec=1180,
    )
    extraction = ExtractionResult(
        items=[
            Insight(
                kind="insight",
                text="New models trade off hallucination for reasoning depth.",
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
        prompt_version="v1",
        input_tokens=4000,
        output_tokens=500,
    )
    return meta, extraction


def test_render_note_includes_frontmatter_and_callouts() -> None:
    meta, extraction = _fixture()
    note = render.render_note(
        meta,
        extraction,
        version=1,
        processed_at=datetime(2026, 4, 23, 12, 0, 0),
        cost_usd={"stt": 0.07, "extract": 0.01},
    )

    assert note.startswith("---\n")
    assert 'title: "Claude Opus 4.7"' in note
    assert "video_id: QVJcdfkRpH8" in note
    assert "duration: 19m 40s" in note
    assert "version: 1" in note
    assert "cost_usd: 0.08" in note
    assert "tags:\n  - podsave\n  - podsave/video" in note

    assert "# Claude Opus 4.7" in note
    assert "> [!note] 1. Insight" in note
    assert "> [!quote] 2. Quote — [Speaker A @ 0:17]" in note
    assert "&t=17s" in note
    assert "> [!warning] 3. Spicy take" in note
    assert '> "I ship code I don\'t read."' in note


def test_render_note_handles_missing_published() -> None:
    meta, extraction = _fixture()
    meta = meta.model_copy(update={"published": None})
    note = render.render_note(
        meta,
        extraction,
        version=1,
        processed_at=datetime(2026, 4, 23, 12, 0, 0),
        cost_usd={"stt": 0.0, "extract": 0.0},
    )
    assert "published:" in note
    assert "**Published:**" not in note


def test_render_note_hour_plus_timestamp() -> None:
    meta, extraction = _fixture()
    extraction = extraction.model_copy(
        update={
            "items": [
                Insight(
                    kind="quote",
                    text="Deep cut.",
                    speaker="B",
                    start_ms=3_723_000,  # 1:02:03
                    rank=1,
                )
            ]
        }
    )
    note = render.render_note(
        meta,
        extraction,
        version=1,
        processed_at=datetime(2026, 4, 23, 12, 0, 0),
        cost_usd={"stt": 0.0, "extract": 0.0},
    )
    assert "@ 1:02:03" in note
    assert "&t=3723s" in note
