"""Thin wrapper around yt-dlp. `probe` fetches metadata; `download_audio` fetches audio."""

from __future__ import annotations

import glob
import json
import subprocess
from datetime import date
from pathlib import Path

from src.errors import DownloadError, DurationGuardError, ProbeError
from src.models import VideoMeta
from src.utils.youtube import extract_video_id, is_playlist

_YT_DLP_CMD = "yt-dlp"

MIN_DURATION_SEC = 15 * 60  # 15 minutes
MAX_DURATION_SEC = 4 * 3600  # 4 hours


def check_duration(meta: VideoMeta, *, force: bool) -> None:
    """Raise DurationGuardError if duration is outside [15m, 4h] and force is False."""
    if force:
        return
    if meta.duration_sec < MIN_DURATION_SEC:
        raise DurationGuardError(
            f"video is {meta.duration_sec}s (< {MIN_DURATION_SEC}s floor) — "
            "pass --force to process short videos"
        )
    if meta.duration_sec > MAX_DURATION_SEC:
        raise DurationGuardError(
            f"video is {meta.duration_sec}s (> {MAX_DURATION_SEC}s ceiling) — "
            "pass --force to process long videos (will cost more)"
        )


def probe(url: str) -> VideoMeta:
    """Return VideoMeta for url by calling `yt-dlp --dump-single-json` (no download).

    Raises PlaylistURLError before shelling out if the URL is a playlist.
    """
    if is_playlist(url):
        from src.errors import PlaylistURLError

        raise PlaylistURLError(
            f"playlist URLs are not supported in v1: {url!r} — "
            "paste individual video URLs instead"
        )

    try:
        proc = subprocess.run(
            [_YT_DLP_CMD, "--dump-single-json", "--no-warnings", "--skip-download", url],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ProbeError(
            "yt-dlp is not installed or not on $PATH — install via `brew install yt-dlp` "
            "or `pip install yt-dlp`"
        ) from exc
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "(no stderr)"
        raise ProbeError(
            f"yt-dlp failed for {url!r}: {stderr}\n"
            f"Try `yt-dlp --dump-single-json {url}` to reproduce outside podsave."
        )

    return _parse_dump_json(proc.stdout, fallback_url=url)


def _parse_dump_json(dump: str, *, fallback_url: str) -> VideoMeta:
    try:
        data = json.loads(dump)
    except json.JSONDecodeError as e:
        raise ProbeError(f"could not parse yt-dlp JSON: {e}") from e

    video_id = data.get("id") or extract_video_id(fallback_url)
    title = data.get("title")
    channel = data.get("channel") or data.get("uploader")
    duration = data.get("duration")
    webpage_url = data.get("webpage_url") or fallback_url
    published = _parse_upload_date(data.get("upload_date"))

    if not title or not channel or duration is None:
        raise ProbeError(
            f"yt-dlp response missing required fields for {fallback_url!r} "
            f"(title={title!r}, channel={channel!r}, duration={duration!r})"
        )

    return VideoMeta(
        video_id=video_id,
        url=webpage_url,
        title=title,
        channel=channel,
        published=published,
        duration_sec=int(duration),
    )


def _parse_upload_date(raw: str | None) -> date | None:
    if not raw or len(raw) != 8 or not raw.isdigit():
        return None
    return date(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]))


def download_audio(meta: VideoMeta, dest_dir: Path) -> Path:
    """Download the best audio-only stream for meta into dest_dir.

    Returns the path to the downloaded file (extension determined by YouTube:
    typically m4a or webm). AssemblyAI accepts both, so we skip ffmpeg conversion.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(dest_dir / f"{meta.video_id}.%(ext)s")

    try:
        proc = subprocess.run(
            [
                _YT_DLP_CMD,
                "-f",
                "bestaudio",
                "--no-warnings",
                "--no-playlist",
                "-o",
                output_template,
                meta.url,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise DownloadError(
            "yt-dlp is not installed or not on $PATH — install via `brew install yt-dlp` "
            "or `pip install yt-dlp`"
        ) from exc
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "(no stderr)"
        raise DownloadError(
            f"yt-dlp failed to download {meta.url!r}: {stderr}\n"
            "If this is a transient network error, re-run `podsave save <url>`; "
            "the transcript cache means a successful download only happens once."
        )

    matches = sorted(glob.glob(str(dest_dir / f"{meta.video_id}.*")))
    audio_matches = [m for m in matches if not m.endswith(".json")]
    if not audio_matches:
        raise DownloadError(
            f"yt-dlp reported success but no audio file found at {dest_dir}/{meta.video_id}.*"
        )
    return Path(audio_matches[0])
