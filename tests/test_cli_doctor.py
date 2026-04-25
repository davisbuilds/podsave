from __future__ import annotations

from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from src.cli import app
from src.models import RunRecord, VideoMeta
from src.storage import log as log_store
from src.storage import paths
from src.storage import transcripts as transcript_store

runner = CliRunner()


def _init(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    paths.config_path().write_text(
        '[api_keys]\nopenai = "sk-test"\nassemblyai = "aai-test"\n'
        f'[paths]\nvault = "{podsave_home / "vault"}"\n'
        '[extraction]\nmodel = "gpt-5.4-mini"\n'
    )
    (podsave_home / "vault").mkdir(parents=True, exist_ok=True)


def test_doctor_clean_state(podsave_home: Path) -> None:
    _init(podsave_home)
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0, result.stdout
    out = result.stdout.lower()
    assert "ok" in out or "no issues" in out or "all clear" in out


def test_doctor_finds_tmp_orphan(podsave_home: Path) -> None:
    _init(podsave_home)
    orphan = paths.tmp_dir() / "leftover.m4a"
    orphan.write_bytes(b"x" * 1024)

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "leftover.m4a" in result.stdout


def test_doctor_clean_removes_tmp_orphan(podsave_home: Path) -> None:
    _init(podsave_home)
    orphan = paths.tmp_dir() / "leftover.m4a"
    orphan.write_bytes(b"x" * 1024)

    result = runner.invoke(app, ["doctor", "--clean"])
    assert result.exit_code == 0
    assert not orphan.exists()
    assert "removed" in result.stdout.lower()


def test_doctor_finds_orphan_transcript(podsave_home: Path) -> None:
    _init(podsave_home)
    meta = VideoMeta(
        video_id="abc123", url="https://youtu.be/abc123", title="T", channel="C", duration_sec=1800
    )
    transcript_store.save(meta.video_id, {"text": "x"}, meta)
    # No corresponding `complete` log entry.

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "abc123" in result.stdout
    # Hint at the fix.
    assert "retry" in result.stdout.lower()


def test_doctor_skips_transcripts_with_complete_run(podsave_home: Path) -> None:
    _init(podsave_home)
    meta = VideoMeta(
        video_id="abc123", url="https://youtu.be/abc123", title="T", channel="C", duration_sec=1800
    )
    transcript_store.save(meta.video_id, {"text": "x"}, meta)
    log_store.append(
        RunRecord(
            url=meta.url,
            video_id=meta.video_id,
            processed_at=datetime(2026, 4, 25, 12, 0, 0),
            version=1,
            status="complete",
        )
    )

    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    # Should not flag the transcript as orphaned (no retry hint involving abc123).
    assert "abc123" not in result.stdout


def test_doctor_warns_on_missing_keys(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])  # writes REPLACE_ME placeholders
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    out = result.stdout.lower()
    assert "openai" in out or "assemblyai" in out
    assert "key" in out or "config" in out
