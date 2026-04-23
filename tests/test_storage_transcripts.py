from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.errors import TranscriptNotFoundError
from src.models import VideoMeta
from src.storage import transcripts


def _meta(video_id: str = "abc123") -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        title="Test Episode",
        channel="Test Channel",
        published=date(2026, 1, 1),
        duration_sec=2400,
    )


def test_has_returns_false_when_missing(podsave_home: Path) -> None:
    assert transcripts.has("abc123") is False


def test_save_then_load_round_trip(podsave_home: Path) -> None:
    raw = {"text": "hello world", "utterances": [{"speaker": "A", "text": "hi"}]}
    meta = _meta()
    transcripts.save(meta.video_id, raw, meta)

    assert transcripts.has(meta.video_id) is True
    loaded_raw, loaded_meta = transcripts.load(meta.video_id)
    assert loaded_raw == raw
    assert loaded_meta == meta


def test_load_missing_raises(podsave_home: Path) -> None:
    with pytest.raises(TranscriptNotFoundError) as ei:
        transcripts.load("does-not-exist")
    assert "does-not-exist" in str(ei.value)
