from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

RunStatus = Literal["complete", "transcript_only", "failed"]
InsightKind = Literal["insight", "quote", "spicy_take"]


class VideoMeta(BaseModel):
    """Metadata about a YouTube video, populated from yt-dlp before download."""

    video_id: str
    url: str
    title: str
    channel: str
    published: date | None = None
    duration_sec: int


class CostEstimate(BaseModel):
    """Predicted cost for running a video through the full pipeline."""

    duration_sec: int
    stt_usd: float
    extraction_input_usd: float
    extraction_output_usd: float
    total_usd: float

    stt_rate_per_hour: float
    estimated_input_tokens: int
    input_rate_per_million: float
    estimated_output_tokens: int
    output_rate_per_million: float

    @property
    def extraction_usd(self) -> float:
        return self.extraction_input_usd + self.extraction_output_usd


class Insight(BaseModel):
    """One item in the top-10 extraction. Quotes require speaker + start_ms."""

    kind: InsightKind
    text: str
    speaker: str | None = None
    start_ms: int | None = None
    context: str | None = None
    rank: int = Field(ge=1, le=10)


class ExtractionResult(BaseModel):
    """Output of the extraction step: up to 10 ranked insights plus bookkeeping."""

    items: list[Insight]
    model: str
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0


class RunRecord(BaseModel):
    """One line in ~/.podsave/processed.jsonl. Append-only history of every run."""

    url: str
    video_id: str
    processed_at: datetime
    version: int = Field(ge=1)
    note_path: str | None = None
    transcript_path: str | None = None
    cost_usd: dict[str, float] = Field(default_factory=dict)
    duration_sec: int | None = None
    status: RunStatus
    error: str | None = None
    channel: str | None = None
