from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner, Result

from podsave.cli import app
from podsave.errors import DownloadError
from podsave.models import ExtractionResult, Insight, VideoMeta
from podsave.pipeline import download
from podsave.pipeline import extract as extract_mod
from podsave.storage import log as log_store
from podsave.storage import paths
from podsave.storage import queue as queue_store
from podsave.storage import transcripts as transcript_store

runner = CliRunner()


@pytest.fixture(params=[pytest.param([], id="human"), pytest.param(["--json"], id="json")])
def drain_flags(request: pytest.FixtureRequest) -> list[str]:
    return request.param


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


def _assert_drain_counts(
    result: Result, drain_flags: list[str], *, succeeded: int, failed: int
) -> None:
    if "--json" in drain_flags:
        summary = json.loads(result.stdout)
        assert summary == {"succeeded": succeeded, "failed": failed}
        assert all(type(count) is int for count in summary.values())
    elif succeeded or failed:
        assert f"succeeded: {succeeded}" in result.stdout
        assert f"failed:   {failed}" in result.stdout
    else:
        assert result.stdout == "(queue empty)\n"


def test_drain_empty_queue_prints_message(podsave_home: Path, drain_flags: list[str]) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    result = runner.invoke(app, ["drain", *drain_flags])
    assert result.exit_code == 0
    _assert_drain_counts(result, drain_flags, succeeded=0, failed=0)
    assert result.stderr == ""
    assert log_store.read_all() == []


def test_drain_success_removes_entry(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drain_flags: list[str]
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta("aaaaaaaaaaa")
    queue_store.add(m.url)
    transcript_store.save(m.video_id, {"text": "cached"}, m)

    monkeypatch.setattr(download, "probe", lambda url: m)
    monkeypatch.setattr(extract_mod, "extract", lambda *a, **kw: _fake_extraction())

    result = runner.invoke(app, ["drain", *drain_flags])
    assert result.exit_code == 0, result.output
    _assert_drain_counts(result, drain_flags, succeeded=1, failed=0)
    progress = result.stderr if "--json" in drain_flags else result.stdout
    assert m.url in progress
    assert "note written" in progress
    assert queue_store.list_all() == []
    assert len(list(vault.glob("*.md"))) == 1
    assert [(record.url, record.status) for record in log_store.read_all()] == [(m.url, "complete")]


def test_drain_failure_leaves_entry_and_continues(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drain_flags: list[str]
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

    result = runner.invoke(app, ["drain", *drain_flags])
    assert result.exit_code == 0, result.output
    _assert_drain_counts(result, drain_flags, succeeded=1, failed=1)
    progress = result.stderr if "--json" in drain_flags else result.stdout
    assert "yt-dlp blew up" in progress
    assert queue_store.list_all() == [bad.url]
    failed_record, completed_record = log_store.read_all()
    assert (failed_record.url, failed_record.status, failed_record.error) == (
        bad.url,
        "failed",
        "yt-dlp blew up",
    )
    assert (completed_record.url, completed_record.status) == (good.url, "complete")


def test_drain_all_failed_exits_one_and_records_each_failure_once(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drain_flags: list[str]
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    empty = _meta("eeeeeeeeee1")
    bad = _meta("bbbbbbbbbb2")
    queue_store.add(empty.url)
    queue_store.add(bad.url)
    transcript_store.save(empty.video_id, {"text": "cached"}, empty)

    def _probe(url: str) -> VideoMeta:
        if url == bad.url:
            raise DownloadError("yt-dlp blew up")
        return empty

    extraction = _fake_extraction().model_copy(update={"items": []})
    monkeypatch.setattr(download, "probe", _probe)
    monkeypatch.setattr(extract_mod, "extract", lambda *a, **kw: extraction)

    result = runner.invoke(app, ["drain", *drain_flags])
    assert result.exit_code == 1, result.output
    _assert_drain_counts(result, drain_flags, succeeded=0, failed=2)
    progress = result.stderr if "--json" in drain_flags else result.stdout
    assert "extraction returned zero items" in progress
    assert "yt-dlp blew up" in progress
    assert queue_store.list_all() == [empty.url, bad.url]
    assert list(vault.glob("*.md")) == []

    empty_record, probe_record = log_store.read_all()
    assert (empty_record.url, empty_record.status) == (empty.url, "failed")
    assert empty_record.error == f"extraction returned zero items for {empty.title}"
    assert empty_record.cost_usd["extract"] > 0
    assert (probe_record.url, probe_record.status) == (bad.url, "failed")


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

    def _no_download(*a: Any, **kw: Any) -> Any:
        raise AssertionError("download should not run during retry")

    monkeypatch.setattr(download, "download_audio", _no_download)
    monkeypatch.setattr(extract_mod, "extract", lambda *a, **kw: _fake_extraction())

    r1 = runner.invoke(app, ["retry", m.video_id])
    assert r1.exit_code == 0, r1.stdout
    r2 = runner.invoke(app, ["retry", m.video_id])
    assert r2.exit_code == 0, r2.stdout

    notes = sorted(p.name for p in vault.glob("*.md"))
    assert len(notes) == 2
    assert any("(v2)" in n for n in notes)

    records = log_store.read_all()
    assert len(records) == 2
    for rec in records:
        assert rec.cost_usd["stt"] == 0.0
