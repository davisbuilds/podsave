from __future__ import annotations

from src.search import matcher
from src.search.callout import Callout


def _co(text: str, *, kind: str = "insight", rank: int = 1, context: str | None = None) -> Callout:
    return Callout(kind=kind, rank=rank, text=text, context=context)  # type: ignore[arg-type]


def test_grep_matcher_substring_hit() -> None:
    m = matcher.GrepMatcher()
    callouts = [_co("Talking about prompt engineering at scale.")]
    matches = m.find("prompt", callouts)
    assert len(matches) == 1
    assert matches[0].score > 0


def test_grep_matcher_case_insensitive() -> None:
    m = matcher.GrepMatcher()
    callouts = [_co("AI is changing everything.")]
    assert len(m.find("ai", callouts)) == 1
    assert len(m.find("CHANGING", callouts)) == 1


def test_grep_matcher_and_of_tokens() -> None:
    m = matcher.GrepMatcher()
    callouts = [
        _co("foo and bar appear together"),
        _co("only foo here"),
        _co("only bar here"),
    ]
    matches = m.find("foo bar", callouts)
    assert len(matches) == 1
    # The AND-matching callout is the one returned.
    assert "foo and bar" in matches[0].text


def test_grep_matcher_no_match_returns_empty() -> None:
    m = matcher.GrepMatcher()
    callouts = [_co("nothing relevant here")]
    assert m.find("xyzzy", callouts) == []


def test_grep_matcher_searches_context() -> None:
    m = matcher.GrepMatcher()
    callouts = [_co("dull body", context="this mentions reasoning specifically")]
    matches = m.find("reasoning", callouts)
    assert len(matches) == 1


def test_grep_matcher_empty_query_matches_everything() -> None:
    m = matcher.GrepMatcher()
    callouts = [_co("a"), _co("b"), _co("c")]
    matches = m.find("", callouts)
    assert len(matches) == 3


def test_match_carries_matched_terms() -> None:
    m = matcher.GrepMatcher()
    callouts = [_co("Foo and BAR")]
    matches = m.find("foo bar", callouts)
    assert sorted(matches[0].matched_terms) == ["bar", "foo"]
