from __future__ import annotations

import sys

import typer
from rich.console import Console

from src.errors import PodsaveError
from src.storage import config as config_store
from src.storage import paths
from src.storage import queue as queue_store

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
