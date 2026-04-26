"""Render matched callouts to terminal (Rich) or to a vault search-results note."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from src.search.callout import Callout
from src.search.index import Note
from src.search.matcher import Match
from src.utils.filenames import focus_slug, next_version_path
from src.utils.youtube import timestamp_url

_CALLOUT_TYPE_BY_KIND = {"insight": "note", "quote": "quote", "spicy_take": "warning"}
_KIND_LABEL = {"insight": "Insight", "quote": "Quote", "spicy_take": "Spicy take"}
_CALLOUTS_SUBDIR = "Callouts"


def render_terminal(
    console: Console,
    matches: list[tuple[Match, Note]],
    *,
    query: str,
    filter_summary: str | None = None,
) -> None:
    """Print matching callouts as Rich panels, one per match, with a footer summary."""
    if not matches:
        msg = f'no callouts matched "{query}"'
        if filter_summary:
            msg += f" with filters: {filter_summary}"
        console.print(f"[yellow]{msg}[/yellow]")
        return

    for match, note in matches:
        console.print(_panel(match, note))

    unique_notes = len({note.path for _, note in matches})
    footer = (
        f'[dim]{len(matches)} callout(s) across {unique_notes} note(s) — '
        f'query: "{query}"[/dim]'
    )
    if filter_summary:
        footer += f" [dim]· filters: {filter_summary}[/dim]"
    console.print(footer)


def render_vault_note(
    vault: Path,
    matches: list[tuple[Match, Note]],
    *,
    query: str,
    notes_searched: int,
    filters: dict[str, object],
    generated_at: datetime,
) -> Path:
    """Write a search-results note into `<vault>/Callouts/`. Returns the path written."""
    callouts_dir = vault / _CALLOUTS_SUBDIR
    callouts_dir.mkdir(parents=True, exist_ok=True)

    base_name = _vault_note_basename(query, generated_at.date())
    path, _ = next_version_path(callouts_dir, base_name)
    path.write_text(
        _vault_note_body(
            matches,
            query=query,
            notes_searched=notes_searched,
            filters=filters,
            generated_at=generated_at,
        )
    )
    return path


def _vault_note_basename(query: str, on: date) -> str:
    slug = focus_slug(query) or "all"
    return f"Search — {slug} [{on.isoformat()}]"


def _vault_note_body(
    matches: list[tuple[Match, Note]],
    *,
    query: str,
    notes_searched: int,
    filters: dict[str, object],
    generated_at: datetime,
) -> str:
    fm_lines = [
        "---",
        f'title: \'Search — "{_yaml_quote(query)}"\'',
        f'query: "{_yaml_quote(query)}"',
        f"generated: {generated_at.isoformat(timespec='seconds')}",
        f"matches: {len(matches)}",
        f"notes_searched: {notes_searched}",
        "filters:",
        f"  kind: {filters.get('kind') or 'null'}",
        f"  channel: {_yaml_value(filters.get('channel'))}",
        f"  focus: {_yaml_value(filters.get('focus'))}",
        f"  since: {_yaml_value(filters.get('since'))}",
        "tags:",
        "  - podsave",
        "  - podsave/search",
        "---",
    ]
    body_blocks = [_callout_md_with_link(m, n) for m, n in matches]
    return "\n".join(
        [
            *fm_lines,
            "",
            f'# Search — "{query}"',
            "",
            f"*{len(matches)} callout(s) across "
            f"{len({n.path for _, n in matches})} note(s) "
            f"out of {notes_searched} searched.*",
            "",
            "\n\n".join(body_blocks),
            "",
        ]
    )


def _callout_md_with_link(match: Match, note: Note) -> str:
    callout = match.callout
    callout_type = _CALLOUT_TYPE_BY_KIND.get(callout.kind, "note")
    title = _callout_md_title(callout, note)
    body = _callout_md_body(callout)
    wikilink = f"↪ [[{note.path.stem}]]"
    return f"> [!{callout_type}] {title}\n{body}\n\n{wikilink}"


def _callout_md_title(callout: Callout, note: Note) -> str:
    base = f"{callout.rank}. {_KIND_LABEL[callout.kind]}"
    if callout.kind == "quote" and callout.start_ms is not None:
        seconds = callout.start_ms // 1000
        link = timestamp_url(note.video_id, seconds)
        speaker = callout.speaker or "Unknown"
        return f"{base} — [{speaker} @ {_mmss(seconds)}]({link})"
    return base


def _callout_md_body(callout: Callout) -> str:
    text = f'"{callout.text}"' if callout.kind == "quote" else callout.text
    lines = [f"> {text}"]
    if callout.context:
        lines.extend(["> ", f"> *{callout.context}*"])
    return "\n".join(lines)


def _panel(match: Match, note: Note) -> Panel:
    callout = match.callout
    body = Text()
    if callout.kind == "quote":
        body.append('"', style="cyan")
        body.append(callout.text)
        body.append('"', style="cyan")
    else:
        body.append(callout.text)
    if callout.context:
        body.append("\n\n")
        body.append(callout.context, style="italic dim")
    if callout.kind == "quote" and callout.start_ms is not None:
        seconds = callout.start_ms // 1000
        body.append("\n↪ ")
        body.append(timestamp_url(note.video_id, seconds), style="link")

    title = _panel_title(match, note)
    return Panel(body, title=title, title_align="left", border_style="cyan")


def _panel_title(match: Match, note: Note) -> str:
    callout = match.callout
    label = _KIND_LABEL[callout.kind]
    speaker_bit = ""
    if callout.kind == "quote" and callout.speaker and callout.start_ms is not None:
        speaker_bit = f" — {callout.speaker} @ {_mmss(callout.start_ms // 1000)}"
    return f"[bold]{note.path.stem}[/bold] · {callout.rank}. {label}{speaker_bit}"


def _mmss(seconds: int) -> str:
    minutes, secs = divmod(seconds, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _yaml_quote(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _yaml_value(value: object) -> str:
    if value in (None, ""):
        return "null"
    return f'"{_yaml_quote(str(value))}"'
