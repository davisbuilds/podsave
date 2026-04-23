"""Thin wrapper around yt-dlp. `probe` fetches metadata without downloading audio."""

from __future__ import annotations

import json
import subprocess
from datetime import date

from src.errors import ProbeError
from src.models import VideoMeta
from src.utils.youtube import extract_video_id, is_playlist

_YT_DLP_CMD = "yt-dlp"


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

    proc = subprocess.run(
        [_YT_DLP_CMD, "--dump-single-json", "--no-warnings", "--skip-download", url],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = proc.stderr.strip() or "(no stderr)"
        raise ProbeError(f"yt-dlp failed for {url!r}: {stderr}")

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
