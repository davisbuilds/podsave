# podsave

Turn YouTube videos into curated Obsidian notes — diarized transcripts, top-10 insights, quotes linked back to the exact moment.

> Early days. See `docs/plans/2026-04-23-podsave-v1.md` for the v1 spec and build plan.

## Quickstart (will work end of Phase 0)

```bash
uv sync --extra dev
./podsave --help
./podsave hello
```

## Tech

- Python 3.14, [uv](https://github.com/astral-sh/uv), [Typer](https://typer.tiangolo.com), [rich](https://github.com/Textualize/rich)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for audio download
- [AssemblyAI](https://www.assemblyai.com) for diarized speech-to-text
- [OpenAI](https://platform.openai.com) for insight extraction

## Development

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
```
