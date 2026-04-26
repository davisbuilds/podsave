from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.errors import EmptyExtractionError, PodsaveError, TranscriptNotFoundError
from src.models import CostEstimate, ExtractionResult, RunRecord, VideoMeta
from src.pipeline import download, extract, render, transcribe
from src.search import filters as search_filters
from src.search import index as search_index
from src.search import ranker as search_ranker
from src.search import render as search_render
from src.search.matcher import GrepMatcher
from src.storage import config as config_store
from src.storage import log as log_store
from src.storage import paths
from src.storage import queue as queue_store
from src.storage import transcripts as transcript_store
from src.utils import cost as cost_utils
from src.utils import filenames

app = typer.Typer(
    add_completion=False,
    help="YouTube videos into curated Obsidian notes.",
    no_args_is_help=True,
)
queue_app = typer.Typer(help="Manage the URL queue.", no_args_is_help=True)
app.add_typer(queue_app, name="queue")

err_console = Console(stderr=True)


def _fail(message: str) -> None:
    err_console.print(f"[red]error:[/red] {message}")
    raise typer.Exit(code=1)


def handle_errors(fn: Callable[..., Any]) -> Callable[..., Any]:
    """Convert any PodsaveError raised inside a command into a clean exit-1 message."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return fn(*args, **kwargs)
        except PodsaveError as exc:
            _fail(str(exc))

    return wrapper


@app.command()
def hello() -> None:
    """Smoke command — proves the CLI is wired up."""
    typer.echo("podsave is alive.")


@app.command()
def version() -> None:
    """Print the installed podsave version."""
    from importlib.metadata import version as pkg_version

    typer.echo(pkg_version("podsave"))


@app.command()
def init(
    no_prompt: bool = typer.Option(
        False,
        "--no-prompt",
        help="Don't prompt for API keys; write placeholders instead.",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite an existing config.toml.",
    ),
) -> None:
    """Create ~/.podsave/ and write a config.toml skeleton."""
    home = paths.get_home()
    home.mkdir(parents=True, exist_ok=True)
    paths.queue_path().touch(exist_ok=True)
    paths.log_path().touch(exist_ok=True)
    paths.transcripts_dir().mkdir(parents=True, exist_ok=True)
    paths.tmp_dir().mkdir(parents=True, exist_ok=True)

    cfg_path = paths.config_path()
    if cfg_path.exists() and not overwrite:
        typer.echo(f"config already exists at {cfg_path} (use --overwrite to replace)")
        return

    interactive = not no_prompt and sys.stdin.isatty()
    openai_key: str | None = None
    assemblyai_key: str | None = None
    if interactive:
        openai_key = (
            typer.prompt("OpenAI API key", hide_input=True, default="", show_default=False) or None
        )
        assemblyai_key = (
            typer.prompt("AssemblyAI API key", hide_input=True, default="", show_default=False)
            or None
        )

    written = config_store.write_skeleton(
        openai_api_key=openai_key,
        assemblyai_api_key=assemblyai_key,
        overwrite=overwrite,
    )
    typer.echo(f"wrote {written}")
    typer.echo(f"state directory: {home}")

    linked = _maybe_link_queue_into_project(Path.cwd(), paths.queue_path())
    if linked is not None:
        typer.echo(f"linked queue for in-editor access: {linked} → {paths.queue_path()}")


def _maybe_link_queue_into_project(cwd: Path, queue_target: Path) -> Path | None:
    """If cwd looks like the podsave project, symlink ./queue.txt → ~/.podsave/queue.txt.

    No-ops silently when cwd isn't the project, when a queue.txt already exists,
    or when the symlink can't be created.
    """
    pyproject = cwd / "pyproject.toml"
    if not pyproject.is_file():
        return None
    try:
        if "podsave" not in pyproject.read_text():
            return None
    except OSError:
        return None

    link = cwd / "queue.txt"
    if link.exists() or link.is_symlink():
        return None
    try:
        link.symlink_to(queue_target)
    except OSError:
        return None
    return link


@app.command()
@handle_errors
def save(
    url: str = typer.Argument(..., help="YouTube URL to process."),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Print metadata and estimated cost without spending money.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Bypass the 15m/4h duration guards.",
    ),
    focus: str | None = typer.Option(
        None,
        "--focus",
        help="Narrow extraction to items relevant to this lens (e.g. 'career advice').",
    ),
) -> None:
    """Process a single YouTube URL (use --dry-run to preview cost only)."""
    meta = download.probe(url)
    estimate = cost_utils.estimate(meta.duration_sec)

    if dry_run:
        _render_preview(meta, estimate)
        return

    _process_url(meta, estimate=estimate, force=force, console=Console(), focus=focus)


def _process_url(
    meta: VideoMeta,
    *,
    estimate: CostEstimate,
    force: bool,
    console: Console,
    focus: str | None = None,
) -> Path:
    """Full pipeline for a probed URL: guard → (download+STT|cache) → extract → render → log.

    Returns the note path on success. Raises `PodsaveError` subclasses on failure;
    callers decide whether to swallow (drain) or let exit-1 propagate (save).
    """
    download.check_duration(meta, force=force)
    cfg = config_store.load_config()

    stt_cost = 0.0
    if transcript_store.has(meta.video_id):
        console.print(
            f"[yellow]cached transcript found[/yellow] for {meta.video_id} — skipping "
            f"download + STT (saved ~${estimate.stt_usd:.2f})"
        )
    else:
        audio_path = download.download_audio(meta, paths.tmp_dir())
        console.print(f"[green]downloaded[/green] {audio_path.name}")

        try:
            raw = transcribe.transcribe(audio_path, cfg.assemblyai_api_key, console=console)
        finally:
            audio_path.unlink(missing_ok=True)

        tp, mp = transcript_store.save(meta.video_id, raw, meta)
        console.print(f"[green]transcript saved[/green] → {tp}")
        console.print(f"[green]metadata saved[/green]  → {mp}")
        stt_cost = estimate.stt_usd

    raw_transcript, _ = transcript_store.load(meta.video_id)
    return _extract_render_and_log(
        meta,
        raw_transcript,
        stt_cost=stt_cost,
        cfg=cfg,
        console=console,
        focus=focus,
    )


def _extract_render_and_log(
    meta: VideoMeta,
    raw_transcript: dict[str, Any],
    *,
    stt_cost: float,
    cfg: Any,
    console: Console,
    focus: str | None = None,
) -> Path:
    """Run extraction + render + append a RunRecord. Returns the note path.

    When extraction returns zero items, no note is written; a `status="failed"`
    RunRecord is appended and `EmptyExtractionError` is raised for the CLI to
    surface as a clean exit-1.
    """
    focus = focus.strip() if focus else None
    if not focus:
        focus = None
    with console.status(f"[cyan]extracting[/cyan] top insights via {cfg.extraction_model}…"):
        extraction = extract.extract(
            raw_transcript,
            meta,
            api_key=cfg.openai_api_key,
            model=cfg.extraction_model,
            focus=focus,
        )
    console.print(f"[green]extracted[/green] {len(extraction.items)} item(s)")

    extract_cost = _extraction_cost(extraction)
    processed_at = datetime.now()
    cost_usd = {"stt": round(stt_cost, 4), "extract": round(extract_cost, 4)}

    if not extraction.items:
        if extraction.focus:
            msg = (
                f"no items matched focus '{extraction.focus}' — try broader "
                "phrasing or run without --focus"
            )
        else:
            msg = f"extraction returned zero items for {meta.title}"
        log_store.append(
            RunRecord(
                url=meta.url,
                video_id=meta.video_id,
                processed_at=processed_at,
                version=1,
                cost_usd=cost_usd,
                duration_sec=meta.duration_sec,
                status="failed",
                error=msg,
                channel=meta.channel,
                focus=extraction.focus,
            )
        )
        raise EmptyExtractionError(msg)

    vault = cfg.vault_path
    vault.mkdir(parents=True, exist_ok=True)
    base_name = filenames.safe_name(
        meta.channel, meta.title, published=meta.published, focus=extraction.focus
    )
    note_path, version_num = filenames.next_version_path(vault, base_name)
    body = render.render_note(
        meta,
        extraction,
        version=version_num,
        processed_at=processed_at,
        cost_usd=cost_usd,
    )
    note_path.write_text(body)
    console.print(f"[green]note written[/green] → {note_path}")

    log_store.append(
        RunRecord(
            url=meta.url,
            video_id=meta.video_id,
            processed_at=processed_at,
            version=version_num,
            note_path=str(note_path),
            transcript_path=str(paths.transcripts_dir() / f"{meta.video_id}.json"),
            cost_usd=cost_usd,
            duration_sec=meta.duration_sec,
            status="complete",
            channel=meta.channel,
            focus=extraction.focus,
        )
    )
    console.print(f"[dim]total spent on this run: ${sum(cost_usd.values()):.2f}[/dim]")
    return note_path


def _extraction_cost(extraction: ExtractionResult) -> float:
    in_rate = cost_utils.OPENAI_INPUT_PER_MILLION_USD
    out_rate = cost_utils.OPENAI_OUTPUT_PER_MILLION_USD
    in_cost = (extraction.input_tokens / 1_000_000.0) * in_rate
    out_cost = (extraction.output_tokens / 1_000_000.0) * out_rate
    return in_cost + out_cost


def _render_preview(meta: VideoMeta, estimate: CostEstimate) -> None:
    console = Console()

    meta_table = Table.grid(padding=(0, 2))
    meta_table.add_column(style="bold cyan")
    meta_table.add_column()
    meta_table.add_row("Title", meta.title)
    meta_table.add_row("Channel", meta.channel)
    meta_table.add_row("Duration", f"{cost_utils.format_duration(meta.duration_sec)}")
    meta_table.add_row(
        "Published", meta.published.isoformat() if meta.published else "(unknown)"
    )
    meta_table.add_row("URL", meta.url)

    cost_table = Table.grid(padding=(0, 2))
    cost_table.add_column(style="bold")
    cost_table.add_column(justify="right")
    cost_table.add_column(style="dim")
    cost_table.add_row(
        "AssemblyAI STT",
        f"${estimate.stt_usd:.2f}",
        f"{meta.duration_sec / 3600:.2f}h @ ${estimate.stt_rate_per_hour:.2f}/hr",
    )
    cost_table.add_row(
        "OpenAI extract",
        f"${estimate.extraction_usd:.2f}",
        f"~{estimate.estimated_input_tokens:,} in + {estimate.estimated_output_tokens} out tok",
    )
    cost_table.add_row("", "─" * 8, "")
    cost_table.add_row("[green]Total[/green]", f"[green]${estimate.total_usd:.2f}[/green]", "")

    console.print(Panel(meta_table, title="Preview", border_style="cyan"))
    console.print(Panel(cost_table, title="Estimated cost", border_style="yellow"))


@queue_app.command("add")
def queue_add(url: str = typer.Argument(..., help="YouTube URL to enqueue.")) -> None:
    """Append a URL to the queue."""
    queue_store.add(url)
    typer.echo(f"queued {url} ({queue_store.count()} total)")


@queue_app.command("list")
def queue_list() -> None:
    """Print every queued URL in order, plus the backing file path."""
    items = queue_store.list_all()
    if not items:
        typer.echo("(queue empty)")
    else:
        for i, url in enumerate(items, start=1):
            typer.echo(f"{i:3}. {url}")
    typer.echo(f"\nfile: {paths.queue_path()}")


@queue_app.command("edit")
def queue_edit() -> None:
    """Open the queue file in $EDITOR (falls back to `open -t` on macOS)."""
    qp = paths.queue_path()
    qp.parent.mkdir(parents=True, exist_ok=True)
    qp.touch(exist_ok=True)
    editor = os.environ.get("EDITOR")
    cmd = [editor, str(qp)] if editor else ["open", "-t", str(qp)]
    subprocess.run(cmd, check=False)


@queue_app.command("remove")
def queue_remove(url: str = typer.Argument(..., help="URL to remove from the queue.")) -> None:
    """Remove the first occurrence of URL from the queue."""
    if queue_store.remove(url):
        typer.echo(f"removed {url} ({queue_store.count()} remaining)")
    else:
        typer.echo(f"not in queue: {url}")
        raise typer.Exit(code=1)


@queue_app.command("clear")
def queue_clear(
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation."),
) -> None:
    """Empty the queue."""
    n = queue_store.count()
    if n == 0:
        typer.echo("(queue already empty)")
        return
    if not yes and not typer.confirm(f"clear {n} URL(s) from the queue?"):
        typer.echo("aborted")
        raise typer.Exit(code=1)
    removed = queue_store.clear()
    typer.echo(f"cleared {removed} URL(s)")


@app.command()
@handle_errors
def drain(
    force: bool = typer.Option(False, "--force", help="Bypass 15m/4h duration guards."),
) -> None:
    """Process every URL in the queue; remove on success, leave on failure."""
    urls = queue_store.list_all()
    if not urls:
        typer.echo("(queue empty)")
        return

    console = Console()
    successes: list[str] = []
    failures: list[tuple[str, str]] = []

    for i, url in enumerate(urls, start=1):
        console.rule(f"[bold]{i}/{len(urls)}[/bold] {url}")
        meta: VideoMeta | None = None
        try:
            meta = download.probe(url)
            estimate = cost_utils.estimate(meta.duration_sec)
            _process_url(meta, estimate=estimate, force=force, console=console)
            queue_store.remove(url)
            successes.append(url)
        except PodsaveError as exc:
            console.print(f"[red]failed:[/red] {exc}")
            failures.append((url, str(exc)))
            log_store.append(
                RunRecord(
                    url=url,
                    video_id=meta.video_id if meta else "",
                    processed_at=datetime.now(),
                    version=1,
                    status="failed",
                    error=str(exc),
                    channel=meta.channel if meta else None,
                    duration_sec=meta.duration_sec if meta else None,
                )
            )

    console.rule("[bold]drain complete[/bold]")
    console.print(f"[green]succeeded:[/green] {len(successes)}")
    console.print(f"[red]failed:[/red]   {len(failures)}")
    if failures:
        for u, err in failures:
            console.print(f"  [dim]· {u}: {err}[/dim]")


@app.command()
def doctor(
    clean: bool = typer.Option(
        False, "--clean", help="Delete leftover audio files in ~/.podsave/tmp/."
    ),
) -> None:
    """Inspect podsave state — tmp orphans, cached transcripts without notes, config sanity."""
    console = Console()
    issues = 0

    tmp_files = sorted(p for p in paths.tmp_dir().glob("*") if p.is_file())
    if tmp_files:
        issues += 1
        tmp_table = Table.grid(padding=(0, 2))
        tmp_table.add_column(style="bold")
        tmp_table.add_column(justify="right", style="dim")
        for p in tmp_files:
            tmp_table.add_row(p.name, f"{p.stat().st_size / 1024:.1f} KB")
        title = "Tmp orphans (--clean to remove)" if not clean else "Tmp orphans (removing…)"
        console.print(Panel(tmp_table, title=title, border_style="yellow"))
        if clean:
            for p in tmp_files:
                p.unlink(missing_ok=True)
            console.print(f"[green]removed[/green] {len(tmp_files)} file(s)")

    completed_ids = {r.video_id for r in log_store.read_all() if r.status == "complete"}
    transcripts = sorted(paths.transcripts_dir().glob("*.json"))
    orphan_transcripts = [
        p
        for p in transcripts
        if not p.name.endswith(".meta.json") and p.stem not in completed_ids
    ]
    if orphan_transcripts:
        issues += 1
        orphan_table = Table.grid(padding=(0, 2))
        orphan_table.add_column(style="bold cyan")
        orphan_table.add_column()
        for p in orphan_transcripts:
            video_id = p.stem
            title = "(no meta)"
            meta_path = p.with_suffix(".meta.json")
            if meta_path.exists():
                try:
                    title = VideoMeta.model_validate_json(meta_path.read_text()).title
                except Exception:
                    pass
            orphan_table.add_row(video_id, title)
        console.print(
            Panel(
                orphan_table,
                title="Cached transcripts without a complete run (try `podsave retry <video_id>`)",
                border_style="yellow",
            )
        )

    config_issues = _config_sanity()
    if config_issues:
        issues += 1
        cfg_table = Table.grid(padding=(0, 2))
        cfg_table.add_column(style="bold red")
        cfg_table.add_column()
        for label, msg in config_issues:
            cfg_table.add_row(label, msg)
        console.print(Panel(cfg_table, title="Config", border_style="red"))

    if issues == 0:
        console.print("[green]all clear — no issues found.[/green]")


def _config_sanity() -> list[tuple[str, str]]:
    """Return (label, message) pairs for any config problems worth surfacing."""
    issues: list[tuple[str, str]] = []
    cfg_path = paths.config_path()
    if not cfg_path.exists():
        issues.append(("missing", f"no config at {cfg_path} — run `podsave init`"))
        return issues
    try:
        cfg = config_store.load_config()
    except PodsaveError as exc:
        issues.append(("invalid", str(exc)))
        return issues
    if not cfg.vault_path.exists():
        issues.append(
            (
                "vault",
                f"vault path missing: {cfg.vault_path} (will be created on first save)",
            )
        )
    return issues


@app.command()
def stats() -> None:
    """Print lifetime usage: notes, failed runs, hours saved, total spend, top channels."""
    records = log_store.read_all()
    if not records:
        typer.echo("no runs yet — try `podsave save <url>`")
        return

    completes = [r for r in records if r.status == "complete"]
    failures = [r for r in records if r.status == "failed"]
    v1_count = sum(1 for r in completes if r.version == 1)
    retry_count = len(completes) - v1_count
    hours = sum((r.duration_sec or 0) for r in completes) / 3600.0
    total_spend = sum(sum(r.cost_usd.values()) for r in records)
    avg_per_hour = (total_spend / hours) if hours > 0 else None

    console = Console()

    summary = Table.grid(padding=(0, 2))
    summary.add_column(style="bold cyan")
    summary.add_column(justify="right")
    summary.add_row("Notes", f"{len(completes)}  ({v1_count} v1, {retry_count} retries)")
    summary.add_row("Failed runs", str(len(failures)))
    summary.add_row("Hours saved", f"{hours:.1f}h of audio")
    summary.add_row("Total spend", f"${total_spend:.2f}")
    if avg_per_hour is not None:
        summary.add_row("Avg / hour", f"${avg_per_hour:.2f}")
    console.print(Panel(summary, title="Lifetime", border_style="cyan"))

    by_channel: dict[str, dict[str, float]] = {}
    for r in completes:
        key = r.channel or "(unknown)"
        bucket = by_channel.setdefault(key, {"count": 0.0, "spend": 0.0})
        bucket["count"] += 1
        bucket["spend"] += sum(r.cost_usd.values())

    if by_channel:
        ranked = sorted(by_channel.items(), key=lambda kv: (-kv[1]["count"], kv[0]))
        channels = Table.grid(padding=(0, 2))
        channels.add_column(style="bold")
        channels.add_column(justify="right")
        channels.add_column(justify="right", style="dim")
        for name, b in ranked[:10]:
            channels.add_row(name, str(int(b["count"])), f"${b['spend']:.2f}")
        console.print(Panel(channels, title="Top channels", border_style="yellow"))


@app.command()
@handle_errors
def retry(
    video_id: str = typer.Argument(..., help="video_id with a cached transcript."),
    focus: str | None = typer.Option(
        None,
        "--focus",
        help="Narrow extraction to items relevant to this lens.",
    ),
) -> None:
    """Re-run extraction + render from a cached transcript. No download/STT cost."""
    if not transcript_store.has(video_id):
        raise TranscriptNotFoundError(
            f"no cached transcript for video_id={video_id} in "
            f"{paths.transcripts_dir()} — process it with `podsave save <url>` first"
        )

    console = Console()
    raw_transcript, meta = transcript_store.load(video_id)
    cfg = config_store.load_config()
    console.print(f"[yellow]retrying[/yellow] {video_id} from cached transcript")
    _extract_render_and_log(
        meta,
        raw_transcript,
        stt_cost=0.0,
        cfg=cfg,
        console=console,
        focus=focus,
    )


@app.command()
@handle_errors
def search(
    query: str = typer.Argument("", help="Substring(s) to find in callouts. AND-of-tokens."),
    kind: str | None = typer.Option(
        None, "--kind", help="Limit to one callout kind: quote | insight | spicy_take."
    ),
    channel: str | None = typer.Option(
        None, "--channel", help="Substring match (case-insensitive) on note channel."
    ),
    focus: str | None = typer.Option(
        None, "--focus", help="Only notes whose focus slug matches this string."
    ),
    since: str | None = typer.Option(
        None, "--since", help="Filter by published date: YYYY-MM-DD or relative (e.g. 30d, 6m, 1y)."
    ),
    limit: int = typer.Option(20, "--limit", help="Cap result count. 0 = unlimited."),
    write: bool = typer.Option(
        False, "--write", help="Also write a results note to <vault>/Callouts/."
    ),
) -> None:
    """Search callouts across the vault. Output to terminal; optionally to a vault note."""
    cfg = config_store.load_config()
    vault = cfg.vault_path
    if not vault.exists():
        raise PodsaveError(
            f"vault path missing: {vault} — check ~/.podsave/config.toml or run `podsave init`"
        )

    notes = search_index.walk_vault(vault)
    notes_searched = len(notes)
    filtered = search_filters.apply(
        notes, kind=kind, channel=channel, focus=focus, since=since
    )

    matcher = GrepMatcher()
    pairs: list[tuple[Any, Any]] = []
    for note in filtered:
        for match in matcher.find(query, note.callouts):
            pairs.append((match, note))
    ranked = search_ranker.rank(pairs, limit=limit)

    console = Console()
    summary = _filter_summary(kind=kind, channel=channel, focus=focus, since=since)
    search_render.render_terminal(console, ranked, query=query, filter_summary=summary)

    if write:
        if not ranked:
            console.print("[yellow]nothing to write — skipping --write[/yellow]")
            return
        out_path = search_render.render_vault_note(
            vault,
            ranked,
            query=query,
            notes_searched=notes_searched,
            filters={"kind": kind, "channel": channel, "focus": focus, "since": since},
            generated_at=datetime.now(),
        )
        console.print(f"[green]wrote[/green] {out_path}")


def _filter_summary(**flags: object) -> str | None:
    parts = [f"{k}={v}" for k, v in flags.items() if v is not None]
    return ", ".join(parts) if parts else None


def main() -> None:
    try:
        app()
    except PodsaveError as exc:
        _fail(str(exc))


if __name__ == "__main__":
    main()
