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


def test_safe_name_strips_pipe_channel_suffix() -> None:
    name = filenames.safe_name(
        "AI Explained", "Foo Bar | AI Explained", published=date(2026, 4, 17)
    )
    assert name == "AI Explained — Foo Bar [2026-04-17]"


def test_safe_name_strips_em_dash_channel_suffix() -> None:
    name = filenames.safe_name(
        "Talks at Google", "Grit — Talks at Google", published=date(2016, 5, 6)
    )
    assert name == "Talks at Google — Grit [2016-05-06]"


def test_safe_name_strips_hyphen_channel_suffix() -> None:
    name = filenames.safe_name("Anthropic", "Prompt panel - Anthropic", published=None)
    assert name == "Anthropic — Prompt panel"


def test_safe_name_strips_case_insensitive() -> None:
    name = filenames.safe_name("AI Explained", "Foo Bar | ai explained", published=None)
    assert name == "AI Explained — Foo Bar"


def test_safe_name_keeps_partial_match() -> None:
    # Channel name is "AI" but the trailing token after `|` is "AI Explained".
    # Dedup should NOT fire — the channel doesn't equal the suffix.
    # (Existing sanitizer still strips `|`; the point is the suffix words remain.)
    name = filenames.safe_name("AI", "Foo Bar | AI Explained", published=None)
    assert "AI Explained" in name


def test_safe_name_keeps_when_channel_is_empty() -> None:
    # Empty channel must never dedup — there is no channel to match against.
    name = filenames.safe_name("", "Foo Bar AI Explained", published=None)
    assert "Foo Bar AI Explained" in name


def test_safe_name_strips_only_when_separator_present() -> None:
    name = filenames.safe_name("AI Explained", "Foo BarAI Explained", published=None)
    assert name == "AI Explained — Foo BarAI Explained"


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
