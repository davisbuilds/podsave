from __future__ import annotations

import typer

app = typer.Typer(
    add_completion=False,
    help="YouTube videos into curated Obsidian notes.",
    no_args_is_help=True,
)


@app.command()
def hello() -> None:
    """Smoke command — proves the CLI is wired up."""
    typer.echo("podsave is alive.")


@app.command()
def version() -> None:
    """Print the installed podsave version."""
    from importlib.metadata import version as pkg_version

    typer.echo(pkg_version("podsave"))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
