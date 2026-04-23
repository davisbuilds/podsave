from __future__ import annotations

import sys
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.errors import PodsaveError
from src.models import CostEstimate, RunRecord, VideoMeta
from src.pipeline import download, extract, render, transcribe
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
) -> None:
    """Process a single YouTube URL (use --dry-run to preview cost only)."""
    meta = download.probe(url)
    estimate = cost_utils.estimate(meta.duration_sec)

    if dry_run:
        _render_preview(meta, estimate)
        return

    download.check_duration(meta, force=force)
    cfg = config_store.load_config()

    console = Console()
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

    with console.status(f"[cyan]extracting[/cyan] top insights via {cfg.extraction_model}…"):
        extraction = extract.extract(
            raw_transcript,
            meta,
            api_key=cfg.openai_api_key,
            model=cfg.extraction_model,
        )
    console.print(f"[green]extracted[/green] {len(extraction.items)} item(s)")

    extract_cost = _extraction_cost(extraction)
    processed_at = datetime.now()
    cost_usd = {"stt": round(stt_cost, 4), "extract": round(extract_cost, 4)}

    vault = cfg.vault_path
    vault.mkdir(parents=True, exist_ok=True)
    base_name = filenames.safe_name(meta.channel, meta.title, published=meta.published)
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
        )
    )
    console.print(
        f"[dim]total spent on this run: ${sum(cost_usd.values()):.2f}[/dim]"
    )


def _extraction_cost(extraction: Any) -> float:
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
    """Print every queued URL in order."""
    items = queue_store.list_all()
    if not items:
        typer.echo("(queue empty)")
        return
    for i, url in enumerate(items, start=1):
        typer.echo(f"{i:3}. {url}")


def main() -> None:
    try:
        app()
    except PodsaveError as exc:
        _fail(str(exc))


if __name__ == "__main__":
    main()
