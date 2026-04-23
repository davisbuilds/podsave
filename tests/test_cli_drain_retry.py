from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.errors import DownloadError
from src.models import ExtractionResult, Insight, VideoMeta
from src.pipeline import download
from src.pipeline import extract as extract_mod
from src.storage import log as log_store
from src.storage import paths
from src.storage import queue as queue_store
from src.storage import transcripts as transcript_store

runner = CliRunner()


def _seed_config(vault: Path) -> None:
    paths.config_path().write_text(
        '[api_keys]\nopenai = "sk-test"\nassemblyai = "aai-test"\n'
        f'[paths]\nvault = "{vault}"\n'
        '[extraction]\nmodel = "gpt-5.4-mini"\n'
    )


def _meta(video_id: str, *, duration_sec: int = 1800) -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        title=f"Title {video_id}",
        channel="Chan",
        published=date(2026, 4, 17),
        duration_sec=duration_sec,
    )


def _fake_extraction() -> ExtractionResult:
    return ExtractionResult(
        items=[Insight(kind="insight", text="something", rank=1)],
        model="gpt-5.4-mini",
        prompt_version="v1",
        input_tokens=100,
        output_tokens=50,
    )


# ---------- drain ----------


def test_drain_empty_queue_prints_message(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    result = runner.invoke(app, ["drain"])
    assert result.exit_code == 0
    assert "empty" in result.stdout.lower()


def test_drain_success_removes_entry(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta("aaaaaaaaaaa")
    queue_store.add(m.url)
    transcript_store.save(m.video_id, {"text": "cached"}, m)

    monkeypatch.setattr(download, "probe", lambda url: m)
    monkeypatch.setattr(extract_mod, "extract", lambda *a, **kw: _fake_extraction())

    result = runner.invoke(app, ["drain"])
    assert result.exit_code == 0, result.stdout
    assert "succeeded: 1" in result.stdout
    assert "failed:   0" in result.stdout
    assert queue_store.list_all() == []
    assert len(list(vault.glob("*.md"))) == 1


def test_drain_failure_leaves_entry_and_continues(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    good = _meta("gggggggggg1")
    bad = _meta("bbbbbbbbbb2")
    queue_store.add(bad.url)
    queue_store.add(good.url)
    transcript_store.save(good.video_id, {"text": "cached"}, good)

    def _probe(url: str) -> VideoMeta:
        if url == bad.url:
            raise DownloadError("yt-dlp blew up")
        return good

    monkeypatch.setattr(download, "probe", _probe)
    monkeypatch.setattr(extract_mod, "extract", lambda *a, **kw: _fake_extraction())

    result = runner.invoke(app, ["drain"])
    assert result.exit_code == 0, result.stdout
    assert "succeeded: 1" in result.stdout
    assert "failed:   1" in result.stdout
    # Bad URL stays, good URL is removed.
    assert queue_store.list_all() == [bad.url]
    # Failure is recorded in the log.
    failed_records = [r for r in log_store.read_all() if r.status == "failed"]
    assert len(failed_records) == 1
    assert failed_records[0].url == bad.url
    assert "yt-dlp blew up" in (failed_records[0].error or "")


# ---------- retry ----------


def test_retry_missing_cache_errors_cleanly(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    result = runner.invoke(app, ["retry", "zzzzzzzzzz"])
    assert result.exit_code == 1
    assert "no cached transcript" in result.stderr.lower()


def test_retry_reuses_cache_and_bumps_version(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta("cccccccccc3")
    transcript_store.save(m.video_id, {"text": "cached"}, m)

    # Assert no network or STT path is taken.
    def _no_download(*a: Any, **kw: Any) -> Any:
        raise AssertionError("download should not run during retry")

    monkeypatch.setattr(download, "download_audio", _no_download)
    monkeypatch.setattr(extract_mod, "extract", lambda *a, **kw: _fake_extraction())

    # First retry → v1.
    r1 = runner.invoke(app, ["retry", m.video_id])
    assert r1.exit_code == 0, r1.stdout
    # Second retry → (v2).
    r2 = runner.invoke(app, ["retry", m.video_id])
    assert r2.exit_code == 0, r2.stdout

    notes = sorted(p.name for p in vault.glob("*.md"))
    assert len(notes) == 2
    assert any("(v2)" in n for n in notes)

    # Both runs logged with stt cost of 0.
    records = log_store.read_all()
    assert len(records) == 2
    for rec in records:
        assert rec.cost_usd["stt"] == 0.0
