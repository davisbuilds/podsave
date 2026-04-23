from __future__ import annotations

from pathlib import Path

from src.storage import queue as queue_store


def test_empty_queue(podsave_home: Path) -> None:
    assert queue_store.list_all() == []
    assert queue_store.count() == 0


def test_add_and_list(podsave_home: Path) -> None:
    queue_store.add("https://youtu.be/aaa")
    queue_store.add("https://youtu.be/bbb")
    assert queue_store.list_all() == ["https://youtu.be/aaa", "https://youtu.be/bbb"]
    assert queue_store.count() == 2


def test_add_strips_whitespace(podsave_home: Path) -> None:
    queue_store.add("  https://youtu.be/aaa  \n")
    assert queue_store.list_all() == ["https://youtu.be/aaa"]


def test_remove_returns_true_when_present(podsave_home: Path) -> None:
    queue_store.add("https://youtu.be/aaa")
    queue_store.add("https://youtu.be/bbb")
    assert queue_store.remove("https://youtu.be/aaa") is True
    assert queue_store.list_all() == ["https://youtu.be/bbb"]


def test_remove_returns_false_when_absent(podsave_home: Path) -> None:
    queue_store.add("https://youtu.be/aaa")
    assert queue_store.remove("https://youtu.be/zzz") is False
    assert queue_store.list_all() == ["https://youtu.be/aaa"]


def test_remove_only_first_occurrence(podsave_home: Path) -> None:
    queue_store.add("https://youtu.be/aaa")
    queue_store.add("https://youtu.be/aaa")
    assert queue_store.remove("https://youtu.be/aaa") is True
    assert queue_store.list_all() == ["https://youtu.be/aaa"]
