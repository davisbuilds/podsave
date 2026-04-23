"""OpenAI-driven extraction: diarized transcript → top-10 insights/quotes/spicy takes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openai import OpenAI
from pydantic import BaseModel

from src.errors import PodsaveError
from src.models import ExtractionResult, Insight, VideoMeta

PROMPT_VERSION = "v1"
_PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_v1.md"

# Pydantic schema the model is asked to match. Kept separate from Insight so the
# wire format and the domain model can evolve independently.


class _ExtractedItem(BaseModel):
    kind: str
    text: str
    speaker: str | None = None
    start_ms: int | None = None
    context: str | None = None
    rank: int


class _ExtractionPayload(BaseModel):
    items: list[_ExtractedItem]


class ExtractionError(PodsaveError):
    pass


def _system_prompt() -> str:
    return _PROMPT_PATH.read_text()


def _format_utterances(raw: dict[str, Any]) -> str:
    """Render AssemblyAI utterances as `[A @ 12s] text` lines for the model."""
    utterances = raw.get("utterances") or []
    if not utterances:
        text = raw.get("text") or ""
        return f"[A @ 0s] {text}" if text else ""
    lines: list[str] = []
    for u in utterances:
        speaker = u.get("speaker") or "?"
        start_sec = (u.get("start") or 0) // 1000
        body = (u.get("text") or "").strip()
        lines.append(f"[{speaker} @ {start_sec}s] {body}")
    return "\n".join(lines)


def extract(
    raw_transcript: dict[str, Any],
    meta: VideoMeta,
    *,
    api_key: str,
    model: str,
) -> ExtractionResult:
    """Call OpenAI with the extraction prompt and the formatted transcript.

    Returns an ExtractionResult. Raises ExtractionError on API/parse failure.
    """
    client = OpenAI(api_key=api_key)
    utterances_text = _format_utterances(raw_transcript)
    if not utterances_text:
        raise ExtractionError(
            f"transcript for {meta.video_id} has no utterances or text to extract from"
        )

    user_message = (
        f"Video: {meta.title}\n"
        f"Channel: {meta.channel}\n"
        f"Duration: {meta.duration_sec}s\n\n"
        "Transcript:\n"
        f"{utterances_text}"
    )

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": user_message},
            ],
            response_format=_ExtractionPayload,
        )
    except Exception as exc:
        raise ExtractionError(
            f"OpenAI call failed ({model}): {exc}\n"
            "Check the openai key in ~/.podsave/config.toml "
            "(or PODSAVE_OPENAI_API_KEY) and the extraction model name."
        ) from exc

    payload = completion.choices[0].message.parsed
    if payload is None:
        raise ExtractionError("OpenAI returned no parsed payload")

    items = [_to_insight(item) for item in payload.items]
    items.sort(key=lambda i: i.rank)

    usage = completion.usage
    return ExtractionResult(
        items=items,
        model=model,
        prompt_version=PROMPT_VERSION,
        input_tokens=(usage.prompt_tokens if usage else 0),
        output_tokens=(usage.completion_tokens if usage else 0),
    )


def _to_insight(item: _ExtractedItem) -> Insight:
    kind = item.kind.strip().lower().replace(" ", "_")
    if kind not in ("insight", "quote", "spicy_take"):
        raise ExtractionError(f"unknown insight kind from model: {item.kind!r}")
    return Insight(
        kind=kind,  # type: ignore[arg-type]
        text=item.text.strip(),
        speaker=(item.speaker.strip() if item.speaker else None),
        start_ms=item.start_ms,
        context=(item.context.strip() if item.context else None),
        rank=item.rank,
    )
