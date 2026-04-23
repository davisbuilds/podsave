from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from src.errors import InvalidYouTubeURLError, PlaylistURLError

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_YT_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
}


def _parse(url: str) -> tuple[str, str, dict[str, list[str]]]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise InvalidYouTubeURLError(f"not a http(s) URL: {url!r}")
    host = parsed.hostname or ""
    if host not in _YT_HOSTS:
        raise InvalidYouTubeURLError(f"not a YouTube URL: {url!r}")
    return host, parsed.path, parse_qs(parsed.query)


def is_playlist(url: str) -> bool:
    """True iff url refers to a playlist (not a single video, even one in a playlist)."""
    _, path, query = _parse(url)
    # /playlist with list= and no v= → pure playlist
    if path.rstrip("/").endswith("/playlist") and "list" in query and "v" not in query:
        return True
    return False


def extract_video_id(url: str) -> str:
    """Return the 11-char YouTube video id from any supported URL shape.

    Raises PlaylistURLError for playlist URLs, InvalidYouTubeURLError otherwise.
    """
    if is_playlist(url):
        raise PlaylistURLError(
            f"playlist URLs are not supported in v1: {url!r} — "
            "paste individual video URLs instead"
        )

    host, path, query = _parse(url)
    candidate: str | None = None

    if "v" in query:
        candidate = query["v"][0]
    elif host == "youtu.be":
        candidate = path.lstrip("/").split("/")[0] or None
    else:
        parts = [p for p in path.split("/") if p]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "v", "live"}:
            candidate = parts[1]

    if not candidate or not _VIDEO_ID_RE.match(candidate):
        raise InvalidYouTubeURLError(f"could not extract video id from {url!r}")
    return candidate


def timestamp_url(video_id: str, seconds: int) -> str:
    """Return a YouTube URL that jumps to `seconds` into the video."""
    if not _VIDEO_ID_RE.match(video_id):
        raise InvalidYouTubeURLError(f"invalid video id: {video_id!r}")
    if seconds < 0:
        raise ValueError(f"seconds must be >= 0, got {seconds}")
    return f"https://www.youtube.com/watch?v={video_id}&t={seconds}s"
