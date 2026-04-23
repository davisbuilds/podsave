"""Thin wrapper around the AssemblyAI SDK — submit audio, poll, return raw dict."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import assemblyai as aai
from rich.console import Console

from src.errors import TranscriptionError


def transcribe(audio_path: Path, api_key: str, *, console: Console | None = None) -> dict[str, Any]:
    """Send audio_path to AssemblyAI with speaker diarization and return the raw response dict.

    Blocks while the SDK polls for completion; a rich spinner shows activity.
    Raises TranscriptionError if the API returns an error status.
    """
    if not audio_path.exists():
        raise TranscriptionError(f"audio file not found: {audio_path}")

    aai.settings.api_key = api_key
    transcriber = aai.Transcriber(
        config=aai.TranscriptionConfig(
            speaker_labels=True,
            speech_models=["universal-3-pro"],
        )
    )

    console = console or Console()
    with console.status(
        f"[cyan]transcribing[/cyan] {audio_path.name} via AssemblyAI…",
        spinner="dots",
    ):
        try:
            transcript = transcriber.transcribe(str(audio_path))
        except aai.types.TranscriptError as exc:
            raise TranscriptionError(f"AssemblyAI request failed: {exc}") from exc

    if transcript.status == aai.TranscriptStatus.error:
        raise TranscriptionError(f"AssemblyAI error: {transcript.error}")

    raw = getattr(transcript, "json_response", None)
    if raw is None:
        raise TranscriptionError(
            "AssemblyAI SDK returned no json_response — unexpected SDK shape"
        )
    return raw
