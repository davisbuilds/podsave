from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import assemblyai as aai
import pytest

from src.errors import TranscriptionError
from src.pipeline import transcribe


class _FakeTranscript:
    def __init__(self, *, status: Any, error: str | None, response: dict[str, Any] | None) -> None:
        self.status = status
        self.error = error
        self.json_response = response


class _FakeTranscriber:
    def __init__(self, result: _FakeTranscript, *args: Any, **kwargs: Any) -> None:
        self._result = result
        self.calls: list[str] = []

    def transcribe(self, audio_path: str) -> _FakeTranscript:
        self.calls.append(audio_path)
        return self._result


def test_transcribe_returns_raw_json_response(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio = tmp_path / "x.m4a"
    audio.write_bytes(b"fake")
    payload = {"id": "t1", "text": "hello", "utterances": []}
    fake = _FakeTranscript(status=aai.TranscriptStatus.completed, error=None, response=payload)
    monkeypatch.setattr(
        aai, "Transcriber", lambda *a, **kw: _FakeTranscriber(fake, *a, **kw)
    )

    raw = transcribe.transcribe(audio, api_key="test-key")
    assert raw == payload


def test_transcribe_raises_on_error_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    audio = tmp_path / "x.m4a"
    audio.write_bytes(b"fake")
    fake = _FakeTranscript(
        status=aai.TranscriptStatus.error, error="quota exceeded", response=None
    )
    monkeypatch.setattr(
        aai, "Transcriber", lambda *a, **kw: _FakeTranscriber(fake, *a, **kw)
    )

    with pytest.raises(TranscriptionError) as ei:
        transcribe.transcribe(audio, api_key="test-key")
    assert "quota exceeded" in str(ei.value)


def test_transcribe_raises_when_audio_missing(tmp_path: Path) -> None:
    with pytest.raises(TranscriptionError):
        transcribe.transcribe(tmp_path / "missing.m4a", api_key="k")


@pytest.mark.skipif(
    os.environ.get("PODSAVE_INTEGRATION") != "1",
    reason="integration test — set PODSAVE_INTEGRATION=1 to run (spends real money)",
)
def test_integration_real_transcription(tmp_path: Path) -> None:
    """Hits real AssemblyAI. Requires PODSAVE_ASSEMBLYAI_API_KEY and a short audio fixture."""
    key = os.environ.get("PODSAVE_ASSEMBLYAI_API_KEY")
    fixture = os.environ.get("PODSAVE_INTEGRATION_AUDIO")
    if not key or not fixture:
        pytest.skip("set PODSAVE_ASSEMBLYAI_API_KEY and PODSAVE_INTEGRATION_AUDIO")
    raw = transcribe.transcribe(Path(fixture), api_key=key)
    assert "text" in raw
