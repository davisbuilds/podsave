from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.models import RunRecord
from src.storage import log as log_store


def _record(video_id: str, status: str = "complete", version: int = 1) -> RunRecord:
    return RunRecord(
        url=f"https://youtu.be/{video_id}",
        video_id=video_id,
        processed_at=datetime(2026, 4, 23, 12, 0, 0),
        version=version,
        status=status,  # type: ignore[arg-type]
        duration_sec=1800,
    )


def test_empty_log(podsave_home: Path) -> None:
    assert log_store.read_all() == []
    assert log_store.find_last("anything") is None


def test_append_and_read_round_trip(podsave_home: Path) -> None:
    r1 = _record("aaa")
    r2 = _record("bbb")
    log_store.append(r1)
    log_store.append(r2)
    rows = log_store.read_all()
    assert [r.video_id for r in rows] == ["aaa", "bbb"]


def test_find_last_returns_most_recent_match(podsave_home: Path) -> None:
    log_store.append(_record("aaa", version=1))
    log_store.append(_record("bbb"))
    log_store.append(_record("aaa", version=2))
    last = log_store.find_last("aaa")
    assert last is not None
    assert last.version == 2


def test_find_last_returns_none_when_no_match(podsave_home: Path) -> None:
    log_store.append(_record("aaa"))
    assert log_store.find_last("zzz") is None
