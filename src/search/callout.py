"""Callout: the unit returned by parsing a rendered podsave note."""

from __future__ import annotations

from pydantic import BaseModel

from src.models import InsightKind


class Callout(BaseModel):
    """One callout block parsed back out of a rendered note.

    Mirrors `Insight` from extraction time but with resolved speaker name
    (the letter has already been mapped via the speakers map at render time).
    """

    kind: InsightKind
    rank: int
    text: str
    context: str | None = None
    speaker: str | None = None
    start_ms: int | None = None
