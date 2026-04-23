from __future__ import annotations

import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from src.errors import DownloadError, DurationGuardError, PlaylistURLError, ProbeError
from src.models import VideoMeta
from src.pipeline import download


def _fake_yt_dlp_ok(payload: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=0,
        stdout=json.dumps(payload),
        stderr="",
    )


def _fake_yt_dlp_fail(stderr: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=[],
        returncode=1,
        stdout="",
        stderr=stderr,
    )


def test_probe_parses_yt_dlp_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "id": "dQw4w9WgXcQ",
        "title": "How I Built This",
        "channel": "Some Channel",
        "uploader": "Some Channel",
        "upload_date": "20260412",
        "duration": 2712.3,
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_yt_dlp_ok(payload))

    meta = download.probe("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert meta.video_id == "dQw4w9WgXcQ"
    assert meta.title == "How I Built This"
    assert meta.channel == "Some Channel"
    assert meta.duration_sec == 2712
    assert meta.published == date(2026, 4, 12)


def test_probe_prefers_channel_over_uploader(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "id": "dQw4w9WgXcQ",
        "title": "Title",
        "channel": "Preferred Channel",
        "uploader": "Fallback Uploader",
        "upload_date": "20260101",
        "duration": 600,
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_yt_dlp_ok(payload))
    meta = download.probe("https://youtu.be/dQw4w9WgXcQ")
    assert meta.channel == "Preferred Channel"


def test_probe_falls_back_to_uploader_when_channel_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "id": "dQw4w9WgXcQ",
        "title": "Title",
        "uploader": "The Uploader",
        "upload_date": "20260101",
        "duration": 600,
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_yt_dlp_ok(payload))
    meta = download.probe("https://youtu.be/dQw4w9WgXcQ")
    assert meta.channel == "The Uploader"


def test_probe_handles_missing_upload_date(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "id": "dQw4w9WgXcQ",
        "title": "Title",
        "channel": "Channel",
        "duration": 600,
    }
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_yt_dlp_ok(payload))
    meta = download.probe("https://youtu.be/dQw4w9WgXcQ")
    assert meta.published is None


def test_probe_rejects_playlist_urls_before_shelling_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If subprocess.run gets called at all, this raises — proving we shortcut.
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: (_ for _ in ()).throw(AssertionError("should not shell out")),
    )
    with pytest.raises(PlaylistURLError):
        download.probe("https://www.youtube.com/playlist?list=PLabc123")


def test_probe_raises_probe_error_on_yt_dlp_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: _fake_yt_dlp_fail("ERROR: video unavailable")
    )
    with pytest.raises(ProbeError) as ei:
        download.probe("https://youtu.be/dQw4w9WgXcQ")
    assert "video unavailable" in str(ei.value)


def test_probe_raises_on_incomplete_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"id": "dQw4w9WgXcQ"}  # no title/channel/duration
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: _fake_yt_dlp_ok(payload))
    with pytest.raises(ProbeError):
        download.probe("https://youtu.be/dQw4w9WgXcQ")


def test_probe_raises_on_garbage_json(monkeypatch: pytest.MonkeyPatch) -> None:
    bad = subprocess.CompletedProcess(args=[], returncode=0, stdout="not json", stderr="")
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: bad)
    with pytest.raises(ProbeError):
        download.probe("https://youtu.be/dQw4w9WgXcQ")


def _meta(duration_sec: int) -> VideoMeta:
    return VideoMeta(
        video_id="abc12345678",
        url="https://youtu.be/abc12345678",
        title="t",
        channel="c",
        duration_sec=duration_sec,
    )


def test_check_duration_rejects_short() -> None:
    with pytest.raises(DurationGuardError):
        download.check_duration(_meta(5 * 60), force=False)


def test_check_duration_rejects_long() -> None:
    with pytest.raises(DurationGuardError):
        download.check_duration(_meta(5 * 3600), force=False)


def test_check_duration_passes_in_range() -> None:
    download.check_duration(_meta(30 * 60), force=False)  # no raise


def test_check_duration_force_bypasses_both_bounds() -> None:
    download.check_duration(_meta(60), force=True)
    download.check_duration(_meta(10 * 3600), force=True)


def test_download_audio_finds_file_after_yt_dlp_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    meta = _meta(1800)

    def fake_run(*a: object, **kw: object) -> subprocess.CompletedProcess[str]:
        # Simulate yt-dlp writing the file.
        (tmp_path / f"{meta.video_id}.m4a").write_bytes(b"fake audio")
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = download.download_audio(meta, tmp_path)
    assert result.exists()
    assert result.suffix == ".m4a"


def test_download_audio_raises_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="ERROR: unavailable"
        ),
    )
    with pytest.raises(DownloadError):
        download.download_audio(_meta(1800), tmp_path)


def test_download_audio_raises_when_no_file_produced(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **kw: subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr=""
        ),
    )
    with pytest.raises(DownloadError):
        download.download_audio(_meta(1800), tmp_path)
