from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.models import VideoMeta
from src.pipeline import download
from src.storage import paths

runner = CliRunner()


def test_bin_launcher_help_smoke() -> None:
    result = subprocess.run(
        ["./podsave", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "podsave" in result.stdout.lower()


def test_cli_help_smoke() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "init" in result.stdout.lower()
    assert "queue" in result.stdout.lower()


def test_hello_command() -> None:
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "alive" in result.stdout.lower()


def test_init_creates_state_dir_and_config(podsave_home: Path) -> None:
    result = runner.invoke(app, ["init", "--no-prompt"])
    assert result.exit_code == 0, result.stdout
    assert podsave_home.exists()
    assert paths.config_path().exists()
    assert paths.queue_path().exists()
    assert paths.log_path().exists()
    assert paths.transcripts_dir().exists()


def test_init_does_not_overwrite_existing_config(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    paths.config_path().write_text("custom = true\n")
    result = runner.invoke(app, ["init", "--no-prompt"])
    assert result.exit_code == 0
    assert "custom = true" in paths.config_path().read_text()


def test_queue_add_and_list(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    add_result = runner.invoke(app, ["queue", "add", "https://youtu.be/aaa"])
    assert add_result.exit_code == 0
    assert "queued" in add_result.stdout.lower()

    list_result = runner.invoke(app, ["queue", "list"])
    assert list_result.exit_code == 0
    assert "https://youtu.be/aaa" in list_result.stdout


def test_queue_list_empty(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    result = runner.invoke(app, ["queue", "list"])
    assert result.exit_code == 0
    assert "empty" in result.stdout.lower()


def test_save_dry_run_prints_preview(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_meta = VideoMeta(
        video_id="dQw4w9WgXcQ",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        title="How I Built This",
        channel="Some Channel",
        published=date(2026, 4, 12),
        duration_sec=2712,
    )
    monkeypatch.setattr(download, "probe", lambda url: fake_meta)

    result = runner.invoke(app, ["save", "--dry-run", fake_meta.url])
    assert result.exit_code == 0, result.stdout
    assert "How I Built This" in result.stdout
    assert "Some Channel" in result.stdout
    assert "45m 12s" in result.stdout
    assert "Total" in result.stdout
    assert "$" in result.stdout


def test_save_non_dry_run_is_stubbed(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_meta = VideoMeta(
        video_id="dQw4w9WgXcQ",
        url="https://youtu.be/dQw4w9WgXcQ",
        title="T",
        channel="C",
        duration_sec=1800,
    )
    monkeypatch.setattr(download, "probe", lambda url: fake_meta)
    result = runner.invoke(app, ["save", fake_meta.url])
    assert result.exit_code == 1
    assert "phase 3" in result.stderr.lower()


def test_save_rejects_playlist_url_with_clean_error() -> None:
    result = runner.invoke(app, ["save", "https://www.youtube.com/playlist?list=PLabc123"])
    assert result.exit_code == 1
    assert "playlist" in result.stderr.lower()
