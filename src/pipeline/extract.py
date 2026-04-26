"""OpenAI-driven extraction: diarized transcript → top-10 insights/quotes/spicy takes."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel

from src.errors import PodsaveError
from src.models import ExtractionResult, Insight, VideoMeta

PROMPT_VERSION = "v2"
_PROMPT_PATH = Path(__file__).parent / "prompts" / "extract_v2.md"
_QUOTE_MATCH_PREFIX_WORDS = 8
_QUOTE_MATCH_FALLBACK_WORDS = 4

# Pydantic schema the model is asked to match. Kept separate from Insight so the
# wire format and the domain model can evolve independently.


class _ExtractedItem(BaseModel):
    kind: str
    text: str
    speaker: str | None = None
    start_ms: int | None = None
    context: str | None = None
    rank: int


class _SpeakerLabel(BaseModel):
    label: str
    name: str | None = None
    confidence: Literal["high", "low"] | None = None


class _ExtractionPayload(BaseModel):
    items: list[_ExtractedItem]
    speakers: list[_SpeakerLabel] = []


class ExtractionError(PodsaveError):
    pass


def _system_prompt(focus: str | None = None) -> str:
    base = _PROMPT_PATH.read_text()
    if not focus:
        return base
    addendum = (
        "\n## Focus\n\n"
        f"Additionally, the user has asked you to focus this extraction on: **{focus}**.\n\n"
        "Apply your normal quality bar (verbatim quotes, non-obvious insights, no padding) "
        "— but only return items that are clearly relevant to this focus. "
        "If the video does not meaningfully address this focus, return zero items "
        "rather than padding with off-topic picks.\n\n"
        "Speaker resolution still applies regardless of focus.\n"
    )
    return base + addendum


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
    focus: str | None = None,
) -> ExtractionResult:
    """Call OpenAI with the extraction prompt and the formatted transcript.

    When `focus` is set (non-empty), the system prompt is extended with a focus
    addendum and the value is recorded on the result. Returns an ExtractionResult.
    Zero items is a valid response (the CLI handles refusal). Raises ExtractionError
    on API/parse failure only.
    """
    client = OpenAI(api_key=api_key)
    utterances_text = _format_utterances(raw_transcript)
    if not utterances_text:
        raise ExtractionError(
            f"transcript for {meta.video_id} has no utterances or text to extract from"
        )

    focus_value = focus.strip() if focus else None
    if not focus_value:
        focus_value = None

    user_message = (
        f"Video: {meta.title}\n"
        f"Channel: {meta.channel}\n"
        f"Duration: {meta.duration_sec}s\n\n"
        "Transcript:\n"
        f"{utterances_text}"
    )

    try:
        completion = client.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": _system_prompt(focus_value)},
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
    _refine_quote_timestamps(items, raw_transcript.get("words") or [])
    speakers = _project_speakers(payload.speakers)

    usage = completion.usage
    return ExtractionResult(
        items=items,
        model=model,
        prompt_version=PROMPT_VERSION,
        input_tokens=(usage.prompt_tokens if usage else 0),
        output_tokens=(usage.completion_tokens if usage else 0),
        speakers=speakers,
        focus=focus_value,
    )


def _project_speakers(labels: list[_SpeakerLabel]) -> dict[str, str]:
    """Build the label → display-name map. Drops entries with no name; tags low confidence."""
    out: dict[str, str] = {}
    for entry in labels:
        if not entry.name:
            continue
        clean_name = entry.name.strip()
        if not clean_name:
            continue
        if entry.confidence == "low":
            clean_name = f"{clean_name} (?)"
        out[entry.label.strip()] = clean_name
    return out


def _refine_quote_timestamps(items: list[Insight], words: list[dict[str, Any]]) -> None:
    """Snap each quote's start_ms to the word-level start time where its text begins.

    AssemblyAI utterances can span many minutes on monologue content, so the
    model often has only a coarse timestamp to return. When word-level data is
    available we match the quote's opening words against the word stream and
    overwrite start_ms with the true start. Leaves the model's value alone when
    no match is found or no words are available.
    """
    if not words:
        return
    normalized_words = [_normalize_for_match(w.get("text") or "") for w in words]
    for item in items:
        if item.kind != "quote":
            continue
        found = _find_word_start_ms(item.text, normalized_words, words)
        if found is not None:
            item.start_ms = found


def _find_word_start_ms(
    quote_text: str,
    normalized_words: list[str],
    words: list[dict[str, Any]],
) -> int | None:
    query_tokens = _normalize_for_match(quote_text).split()
    if not query_tokens:
        return None
    for n in (_QUOTE_MATCH_PREFIX_WORDS, _QUOTE_MATCH_FALLBACK_WORDS):
        prefix = query_tokens[:n]
        if len(prefix) < n:
            continue
        match_index = _find_subsequence(normalized_words, prefix)
        if match_index is not None:
            start = words[match_index].get("start")
            return int(start) if isinstance(start, (int, float)) else None
    return None


def _find_subsequence(haystack: list[str], needle: list[str]) -> int | None:
    if not needle or len(needle) > len(haystack):
        return None
    first = needle[0]
    for i in range(len(haystack) - len(needle) + 1):
        if haystack[i] != first:
            continue
        if haystack[i : i + len(needle)] == needle:
            return i
    return None


def _normalize_for_match(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", " ", s.lower()).strip()


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
