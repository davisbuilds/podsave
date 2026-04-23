from __future__ import annotations

from datetime import date
from pathlib import Path

from src.utils import filenames


def test_safe_name_basic() -> None:
    name = filenames.safe_name("AI Explained", "Claude Opus 4.7", published=date(2026, 4, 17))
    assert name == "AI Explained — Claude Opus 4.7 [2026-04-17]"


def test_safe_name_strips_path_chars() -> None:
    name = filenames.safe_name('Ch/a:n*nel', 'A "Good" Title?', published=None)
    assert "/" not in name
    assert "*" not in name
    assert ":" not in name
    assert "?" not in name
    assert '"' not in name


def test_safe_name_collapses_whitespace() -> None:
    name = filenames.safe_name("  A   Lot    Of Space ", "Title\twith\nnewlines", published=None)
    assert "  " not in name


def test_safe_name_truncates_long_input() -> None:
    long = "X" * 500
    name = filenames.safe_name("Channel", long, published=None)
    assert len(name) <= 180


def test_next_version_path_first_free(tmp_path: Path) -> None:
    path, v = filenames.next_version_path(tmp_path, "Base")
    assert path == tmp_path / "Base.md"
    assert v == 1


def test_next_version_path_collision(tmp_path: Path) -> None:
    (tmp_path / "Base.md").write_text("existing")
    path, v = filenames.next_version_path(tmp_path, "Base")
    assert path == tmp_path / "Base (v2).md"
    assert v == 2


def test_next_version_path_many_versions(tmp_path: Path) -> None:
    (tmp_path / "Base.md").write_text("")
    (tmp_path / "Base (v2).md").write_text("")
    (tmp_path / "Base (v3).md").write_text("")
    path, v = filenames.next_version_path(tmp_path, "Base")
    assert path.name == "Base (v4).md"
    assert v == 4
