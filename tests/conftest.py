from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def podsave_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate podsave state to a temp dir for the duration of the test."""
    home = tmp_path / ".podsave"
    monkeypatch.setenv("PODSAVE_HOME", str(home))
    return home
