"""Render an ExtractionResult into an Obsidian-flavored markdown note."""

from __future__ import annotations

from datetime import datetime

from src.models import ExtractionResult, Insight, VideoMeta
from src.utils.cost import format_duration
from src.utils.youtube import timestamp_url

_CALLOUT_TYPE_BY_KIND = {
    "insight": "note",
    "quote": "quote",
    "spicy_take": "warning",
}

_KIND_LABEL = {
    "insight": "Insight",
    "quote": "Quote",
    "spicy_take": "Spicy take",
}


def render_note(
    meta: VideoMeta,
    extraction: ExtractionResult,
    *,
    version: int,
    processed_at: datetime,
    cost_usd: dict[str, float],
) -> str:
    """Return the full markdown document for this video's note."""
    return "\n".join(
        [
            _frontmatter(meta, extraction, version, processed_at, cost_usd),
            "",
            f"# {meta.title}",
            "",
            _header_line(meta),
            "",
            "## Top picks",
            "",
            _callouts(meta, extraction.items),
            "",
            _footer(extraction),
            "",
        ]
    )


def _frontmatter(
    meta: VideoMeta,
    extraction: ExtractionResult,
    version: int,
    processed_at: datetime,
    cost_usd: dict[str, float],
) -> str:
    cost_total = round(sum(cost_usd.values()), 4)
    published = meta.published.isoformat() if meta.published else ""
    lines = [
        "---",
        f'title: "{_yaml_quote(meta.title)}"',
        f"video_id: {meta.video_id}",
        f'channel: "{_yaml_quote(meta.channel)}"',
        f"url: {meta.url}",
        f"published: {published}" if published else "published:",
        f"duration: {format_duration(meta.duration_sec)}",
        f"processed: {processed_at.isoformat(timespec='seconds')}",
        f"version: {version}",
        f"model: {extraction.model}",
        f"prompt_version: {extraction.prompt_version}",
        f"cost_usd: {cost_total}",
        "tags:",
        "  - podsave",
        "---",
    ]
    return "\n".join(lines)


def _yaml_quote(s: str) -> str:
    """Escape `"` and `\\` so the string is safe between double quotes in YAML."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _header_line(meta: VideoMeta) -> str:
    pieces = [
        f"**Channel:** {meta.channel}",
        f"**Duration:** {format_duration(meta.duration_sec)}",
    ]
    if meta.published:
        pieces.insert(1, f"**Published:** {meta.published.isoformat()}")
    pieces.append(f"[Watch on YouTube]({meta.url})")
    return " · ".join(pieces)


def _callouts(meta: VideoMeta, items: list[Insight]) -> str:
    return "\n\n".join(_callout(meta, item) for item in items)


def _callout(meta: VideoMeta, item: Insight) -> str:
    callout_type = _CALLOUT_TYPE_BY_KIND.get(item.kind, "note")
    title = _callout_title(meta, item)
    body_lines = [f"> {line}" for line in _body_lines(item)]
    return f"> [!{callout_type}] {title}\n" + "\n".join(body_lines)


def _callout_title(meta: VideoMeta, item: Insight) -> str:
    base = f"{item.rank}. {_KIND_LABEL[item.kind]}"
    if item.kind == "quote" and item.start_ms is not None:
        seconds = item.start_ms // 1000
        link = timestamp_url(meta.video_id, seconds)
        speaker = f"Speaker {item.speaker}" if item.speaker else "Unknown"
        return f"{base} — [{speaker} @ {_mmss(seconds)}]({link})"
    return base


def _body_lines(item: Insight) -> list[str]:
    if item.kind == "quote":
        text = f'"{item.text}"'
    else:
        text = item.text
    lines = [text]
    if item.context:
        lines.extend(["", f"*{item.context}*"])
    return lines


def _mmss(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _footer(extraction: ExtractionResult) -> str:
    return (
        "---\n"
        f"*{len(extraction.items)} item(s) extracted by `{extraction.model}` "
        f"(prompt {extraction.prompt_version}).*"
    )
