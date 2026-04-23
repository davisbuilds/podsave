from __future__ import annotations

import os
from pathlib import Path

DEFAULT_HOME = "~/.podsave"
DEFAULT_VAULT = "~/obsd/Resources/Podsave"


def get_home() -> Path:
    """Return the podsave state directory. Honors $PODSAVE_HOME for tests/CI."""
    raw = os.environ.get("PODSAVE_HOME", DEFAULT_HOME)
    return Path(raw).expanduser()


def config_path() -> Path:
    return get_home() / "config.toml"


def queue_path() -> Path:
    return get_home() / "queue.txt"


def log_path() -> Path:
    return get_home() / "processed.jsonl"


def transcripts_dir() -> Path:
    return get_home() / "transcripts"


def tmp_dir() -> Path:
    return get_home() / "tmp"
