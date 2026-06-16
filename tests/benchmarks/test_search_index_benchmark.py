from __future__ import annotations

import statistics
import time
from datetime import date, datetime
from pathlib import Path

from podsave.models import ExtractionResult, Insight, VideoMeta
from podsave.pipeline import render
from podsave.search import index


def _render_fixture_note(i: int) -> str:
    meta = VideoMeta(
        video_id=f"video{i:05d}",
        url=f"https://www.youtube.com/watch?v=video{i:05d}",
        title=f"Benchmark Video {i}",
        channel=f"Channel {i % 7}",
        published=date(2026, 4, (i % 28) + 1),
        duration_sec=1800 + i,
    )
    extraction = ExtractionResult(
        items=[
            Insight(
                kind="insight",
                text=f"Reasoning benchmark insight {i}-{j} about search indexing.",
                rank=j + 1,
                context=f"Context line {j} for benchmark note {i}.",
            )
            for j in range(5)
        ],
        model="gpt-5.4-mini",
        prompt_version="v2",
        speakers={},
    )
    return render.render_note(
        meta,
        extraction,
        version=1,
        processed_at=datetime(2026, 5, 5, 12, 0, 0),
        cost_usd={"stt": 0.0, "extract": 0.0},
    )


def _seed_vault(vault: Path, *, podsave_notes: int = 400, other_notes: int = 100) -> None:
    vault.mkdir(parents=True, exist_ok=True)
    ignored = vault / ".obsidian"
    ignored.mkdir()
    (ignored / "ignored.md").write_text("---\ntags:\n  - podsave\n---\n\nignored\n")

    for i in range(podsave_notes):
        (vault / f"podsave-{i:05d}.md").write_text(_render_fixture_note(i))

    for i in range(other_notes):
        (vault / f"daily-{i:05d}.md").write_text(
            "---\n"
            f"title: Daily {i}\n"
            "tags:\n"
            "  - daily\n"
            "---\n\n"
            "freeform notes that should not become search results\n"
        )


def test_walk_vault_benchmark(capsys, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """Focused lower-is-better benchmark for vault search indexing.

    Run with:
        uv run pytest tests/benchmarks/test_search_index_benchmark.py -q -s
    """
    _seed_vault(tmp_path)
    expected_notes = 400
    rounds = 7
    timings: list[float] = []

    assert len(index.walk_vault(tmp_path)) == expected_notes

    for _ in range(rounds):
        started = time.perf_counter()
        notes = index.walk_vault(tmp_path)
        timings.append(time.perf_counter() - started)
        assert len(notes) == expected_notes

    captured = capsys.readouterr()
    if captured.out:
        print(captured.out, end="")
    print(
        "BENCHMARK "
        "name=search_index_walk_vault "
        f"notes={expected_notes} "
        f"rounds={rounds} "
        f"median_seconds={statistics.median(timings):.6f} "
        f"min_seconds={min(timings):.6f} "
        f"max_seconds={max(timings):.6f} "
        "lower_is_better=true"
    )
