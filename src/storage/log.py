from __future__ import annotations

from src.models import RunRecord
from src.storage import paths


def _ensure() -> None:
    home = paths.get_home()
    home.mkdir(parents=True, exist_ok=True)
    lp = paths.log_path()
    if not lp.exists():
        lp.touch()


def append(record: RunRecord) -> None:
    """Append a RunRecord as one JSON line."""
    _ensure()
    with paths.log_path().open("a") as fh:
        fh.write(record.model_dump_json() + "\n")


def read_all() -> list[RunRecord]:
    """Return every RunRecord in the log, oldest first."""
    lp = paths.log_path()
    if not lp.exists():
        return []
    out: list[RunRecord] = []
    for line in lp.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(RunRecord.model_validate_json(line))
    return out


def find_last(video_id: str) -> RunRecord | None:
    """Return the most recent RunRecord for a given video_id, or None."""
    matches = [r for r in read_all() if r.video_id == video_id]
    return matches[-1] if matches else None
