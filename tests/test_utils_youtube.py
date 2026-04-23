from __future__ import annotations

import pytest

from src.errors import InvalidYouTubeURLError, PlaylistURLError
from src.utils.youtube import extract_video_id, is_playlist, timestamp_url

VALID_ID = "dQw4w9WgXcQ"  # 11 chars


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VALID_ID}",
        f"https://youtube.com/watch?v={VALID_ID}",
        f"https://m.youtube.com/watch?v={VALID_ID}",
        f"https://music.youtube.com/watch?v={VALID_ID}",
        f"https://youtu.be/{VALID_ID}",
        f"https://www.youtube.com/watch?v={VALID_ID}&list=PLabc&index=2",
        f"https://www.youtube.com/shorts/{VALID_ID}",
        f"https://www.youtube.com/embed/{VALID_ID}",
        f"https://www.youtube.com/live/{VALID_ID}",
        f"   https://youtu.be/{VALID_ID}   ",
    ],
)
def test_extract_video_id_valid_forms(url: str) -> None:
    assert extract_video_id(url) == VALID_ID


def test_playlist_url_rejected() -> None:
    url = "https://www.youtube.com/playlist?list=PLabc123"
    assert is_playlist(url) is True
    with pytest.raises(PlaylistURLError) as ei:
        extract_video_id(url)
    assert "playlist" in str(ei.value).lower()


def test_video_in_playlist_still_extracts() -> None:
    url = f"https://www.youtube.com/watch?v={VALID_ID}&list=PLabc123"
    assert is_playlist(url) is False
    assert extract_video_id(url) == VALID_ID


@pytest.mark.parametrize(
    "url",
    [
        "https://vimeo.com/12345",
        "https://example.com/watch?v=x",
        "ftp://youtube.com/watch?v=x",
        "https://www.youtube.com/watch",
        "https://www.youtube.com/watch?v=tooshort",
    ],
)
def test_invalid_urls_raise(url: str) -> None:
    with pytest.raises((InvalidYouTubeURLError, PlaylistURLError)):
        extract_video_id(url)


def test_timestamp_url_basic() -> None:
    assert timestamp_url(VALID_ID, 754) == f"https://www.youtube.com/watch?v={VALID_ID}&t=754s"
    assert timestamp_url(VALID_ID, 0) == f"https://www.youtube.com/watch?v={VALID_ID}&t=0s"


def test_timestamp_url_invalid_id() -> None:
    with pytest.raises(InvalidYouTubeURLError):
        timestamp_url("too-short", 5)


def test_timestamp_url_negative_seconds() -> None:
    with pytest.raises(ValueError):
        timestamp_url(VALID_ID, -1)
