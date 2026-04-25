from __future__ import annotations

from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from src.cli import app
from src.models import RunRecord
from src.storage import log as log_store

runner = CliRunner()


def _record(
    video_id: str,
    *,
    status: str = "complete",
    version: int = 1,
    cost: dict[str, float] | None = None,
    duration_sec: int | None = 1800,
    channel: str | None = "Some Channel",
) -> RunRecord:
    return RunRecord(
        url=f"https://youtu.be/{video_id}",
        video_id=video_id,
        processed_at=datetime(2026, 4, 25, 12, 0, 0),
        version=version,
        status=status,  # type: ignore[arg-type]
        duration_sec=duration_sec,
        cost_usd=cost or {},
        channel=channel,
    )


def test_stats_empty_log(podsave_home: Path) -> None:
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "no runs" in result.stdout.lower()


def test_stats_counts_completes_and_failures(podsave_home: Path) -> None:
    log_store.append(_record("a", status="complete"))
    log_store.append(_record("b", status="complete"))
    log_store.append(_record("c", status="complete", version=2))
    log_store.append(_record("d", status="failed", duration_sec=None))

    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0, result.stdout
    out = result.stdout
    # 3 completes (2 v1 + 1 retry), 1 failed
    assert "3" in out
    assert "1" in out
    assert "fail" in out.lower()
    assert "retry" in out.lower() or "v2" in out.lower() or "retries" in out.lower()


def test_stats_sums_cost(podsave_home: Path) -> None:
    log_store.append(_record("a", cost={"stt": 0.20, "extract": 0.01}))
    log_store.append(_record("b", cost={"stt": 0.30, "extract": 0.02}))
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    # 0.20 + 0.01 + 0.30 + 0.02 = 0.53
    assert "0.53" in result.stdout


def test_stats_top_channels(podsave_home: Path) -> None:
    log_store.append(_record("a", channel="AI Explained", cost={"stt": 0.10}))
    log_store.append(_record("b", channel="AI Explained", cost={"stt": 0.10}))
    log_store.append(_record("c", channel="Anthropic", cost={"stt": 0.05}))
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    out = result.stdout
    assert "AI Explained" in out
    assert "Anthropic" in out
    # AI Explained should appear before Anthropic (sorted by count desc)
    assert out.index("AI Explained") < out.index("Anthropic")


def test_stats_handles_missing_channel(podsave_home: Path) -> None:
    # Old-style record: no channel field set.
    log_store.append(_record("a", channel=None))
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "unknown" in result.stdout.lower()
