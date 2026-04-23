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


def test_init_creates_project_queue_symlink(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "pyproject.toml").write_text('[project]\nname = "podsave"\n')
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["init", "--no-prompt"])
    assert result.exit_code == 0, result.stdout

    link = project / "queue.txt"
    assert link.is_symlink()
    assert link.resolve() == paths.queue_path().resolve()
    assert "linked queue" in result.stdout.lower()


def test_init_skips_symlink_when_not_in_project(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = runner.invoke(app, ["init", "--no-prompt"])
    assert result.exit_code == 0
    assert not (elsewhere / "queue.txt").exists()
    assert "linked queue" not in result.stdout.lower()


def test_init_skips_symlink_when_queue_already_exists(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "pyproject.toml").write_text('name = "podsave"\n')
    (project / "queue.txt").write_text("pre-existing\n")
    monkeypatch.chdir(project)

    result = runner.invoke(app, ["init", "--no-prompt"])
    assert result.exit_code == 0
    assert (project / "queue.txt").read_text() == "pre-existing\n"
    assert "linked queue" not in result.stdout.lower()


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


def test_save_non_dry_run_uses_cached_transcript(
    podsave_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_meta = VideoMeta(
        video_id="dQw4w9WgXcQ",
        url="https://youtu.be/dQw4w9WgXcQ",
        title="T",
        channel="C",
        duration_sec=1800,
    )
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    paths.config_path().write_text(
        '[api_keys]\nopenai = "sk-test"\nassemblyai = "aai-test"\n'
        f'[paths]\nvault = "{vault}"\n'
        '[extraction]\nmodel = "gpt-5.4-mini"\n'
    )

    # Seed cache — save() should skip download + transcribe.
    from src.models import ExtractionResult, Insight
    from src.pipeline import extract as extract_mod
    from src.storage import transcripts as transcript_store

    transcript_store.save(fake_meta.video_id, {"text": "cached"}, fake_meta)

    monkeypatch.setattr(download, "probe", lambda url: fake_meta)

    def _boom(*a: object, **kw: object) -> None:
        raise AssertionError("download_audio should not be called when cached")

    monkeypatch.setattr(download, "download_audio", _boom)
    monkeypatch.setattr(
        extract_mod,
        "extract",
        lambda *a, **kw: ExtractionResult(
            items=[Insight(kind="insight", text="cached stuff", rank=1)],
            model="gpt-5.4-mini",
            prompt_version="v1",
            input_tokens=100,
            output_tokens=50,
        ),
    )

    result = runner.invoke(app, ["save", fake_meta.url])
    assert result.exit_code == 0, result.stdout
    assert "cached transcript" in result.stdout.lower()
    assert "note written" in result.stdout.lower()
    # Note file should exist in vault.
    notes = list(vault.glob("*.md"))
    assert len(notes) == 1


def test_save_rejects_playlist_url_with_clean_error() -> None:
    result = runner.invoke(app, ["save", "https://www.youtube.com/playlist?list=PLabc123"])
    assert result.exit_code == 1
    assert "playlist" in result.stderr.lower()
