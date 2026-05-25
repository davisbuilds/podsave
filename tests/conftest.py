from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _disable_rich_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render Rich output as plain text so CLI assertions are env-independent.

    A developer shell exporting FORCE_COLOR/CLICOLOR_FORCE makes Rich force ANSI
    styling even under CliRunner's non-tty capture, splitting asserted substrings
    (e.g. "succeeded: 1") across style codes. Clearing those vars lets Rich fall
    back to non-terminal output (no color, no bold), matching CI.
    """
    for var in ("FORCE_COLOR", "CLICOLOR_FORCE", "PY_COLORS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_COLOR", "1")


@pytest.fixture
def podsave_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate podsave state to a temp dir for the duration of the test."""
    home = tmp_path / ".podsave"
    monkeypatch.setenv("PODSAVE_HOME", str(home))
    return home
