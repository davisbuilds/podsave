"""Match callouts against a query string.

The `Matcher` protocol is the seam for adding embedding-based search later. The
default `GrepMatcher` implements case-insensitive substring matching with
AND-of-tokens semantics over each callout's text + context. Callouts are
already in memory by the time we get here (parsed by `index.walk_vault`), so
matching is plain Python — no need to shell out to rg for in-memory strings.
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel

from src.search.callout import Callout


class Match(BaseModel):
    """One matched callout, scored against the query."""

    callout: Callout
    score: int
    matched_terms: list[str]

    @property
    def text(self) -> str:
        return self.callout.text


class Matcher(Protocol):
    def find(self, query: str, callouts: list[Callout]) -> list[Match]: ...


class GrepMatcher:
    """Case-insensitive AND-of-tokens substring matching over callout text + context."""

    def find(self, query: str, callouts: list[Callout]) -> list[Match]:
        terms = query.lower().split()
        if not terms:
            return [Match(callout=c, score=1, matched_terms=[]) for c in callouts]

        out: list[Match] = []
        for callout in callouts:
            haystack = self._haystack(callout)
            if not all(term in haystack for term in terms):
                continue
            score = sum(haystack.count(term) for term in terms)
            out.append(Match(callout=callout, score=score, matched_terms=list(terms)))
        return out

    @staticmethod
    def _haystack(callout: Callout) -> str:
        parts = [callout.text]
        if callout.context:
            parts.append(callout.context)
        return " ".join(parts).lower()


def _reset_cache() -> None:
    """No-op preserved for forward-compat; future RipgrepMatcher may cache `which('rg')`."""
