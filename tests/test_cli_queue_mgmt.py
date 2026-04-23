from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.storage import paths
from src.storage import queue as queue_store

runner = CliRunner()


def test_queue_list_shows_file_path(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    queue_store.add("https://youtu.be/abc")
    result = runner.invoke(app, ["queue", "list"])
    assert result.exit_code == 0
    assert "https://youtu.be/abc" in result.stdout
    assert str(paths.queue_path()) in result.stdout


def test_queue_remove_drops_entry(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    queue_store.add("https://youtu.be/aaa")
    queue_store.add("https://youtu.be/bbb")

    result = runner.invoke(app, ["queue", "remove", "https://youtu.be/aaa"])
    assert result.exit_code == 0
    assert queue_store.list_all() == ["https://youtu.be/bbb"]


def test_queue_remove_missing_entry_errors(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    result = runner.invoke(app, ["queue", "remove", "https://youtu.be/nope"])
    assert result.exit_code == 1
    assert "not in queue" in result.stdout.lower()


def test_queue_clear_empty_is_noop(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    result = runner.invoke(app, ["queue", "clear", "--yes"])
    assert result.exit_code == 0
    assert "already empty" in result.stdout.lower()


def test_queue_clear_removes_all(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    queue_store.add("https://youtu.be/a")
    queue_store.add("https://youtu.be/b")
    result = runner.invoke(app, ["queue", "clear", "--yes"])
    assert result.exit_code == 0
    assert queue_store.list_all() == []
    assert "cleared 2" in result.stdout.lower()


def test_queue_edit_invokes_editor(
    podsave_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *a: object, **kw: object) -> object:
        calls.append(cmd)

        class _R:
            returncode = 0

        return _R()

    import src.cli as cli_mod

    monkeypatch.setattr(cli_mod.subprocess, "run", _fake_run)
    monkeypatch.setenv("EDITOR", "nvim")

    result = runner.invoke(app, ["queue", "edit"])
    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0][0] == "nvim"
    assert calls[0][1] == str(paths.queue_path())


def test_queue_edit_falls_back_to_open_on_no_editor(
    podsave_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    calls: list[list[str]] = []

    def _fake_run(cmd: list[str], *a: object, **kw: object) -> object:
        calls.append(cmd)

        class _R:
            returncode = 0

        return _R()

    import src.cli as cli_mod

    monkeypatch.setattr(cli_mod.subprocess, "run", _fake_run)
    monkeypatch.delenv("EDITOR", raising=False)

    result = runner.invoke(app, ["queue", "edit"])
    assert result.exit_code == 0
    assert calls[0][:2] == ["open", "-t"]
