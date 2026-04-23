from __future__ import annotations

import subprocess

from typer.testing import CliRunner

from src.cli import app

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
    assert "hello" in result.stdout.lower()


def test_hello_command() -> None:
    result = runner.invoke(app, ["hello"])

    assert result.exit_code == 0
    assert "alive" in result.stdout.lower()
