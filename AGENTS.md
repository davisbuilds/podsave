# AI Agent Guide

Guidance for coding agents working in this repository.

`podsave` turns YouTube videos into curated Obsidian notes. Pipeline: yt-dlp download → AssemblyAI diarized STT → OpenAI extraction (top-10 insights/quotes/spicy takes) → markdown note to `~/obsd/Resources/Videos/`.

See `docs/plans/2026-04-23-podsave-v1.md` for the full spec, build phases, and open questions.

## Project Structure

```text
podsave/
├── podsave                 # Repo-local launcher wrapper
├── src/
│   ├── cli.py              # Typer CLI entry point
│   ├── models.py           # Shared Pydantic data models (Phase 1+)
│   ├── pipeline/           # download, transcribe, extract, render (Phase 2+)
│   ├── storage/            # config, queue, transcripts, log (Phase 1+)
│   └── utils/              # youtube URL parsing, filenames, cost math
├── tests/                  # Pytest suite
├── docs/
│   ├── plans/              # Implementation plans
│   ├── system/             # Architecture, features (Phase 6)
│   └── project/            # Spec (Phase 6)
└── pyproject.toml
```

## Key Commands

The project uses `uv` for dependency management.

- **Run CLI**: `./podsave <command>` (or `uv run podsave <command>`)
- **Tests**: `uv run pytest -q`
- **Lint**: `uv run ruff check .`
- **Install**: `uv sync --extra dev`

## External State

The CLI writes to paths outside the repo. Know these exist:

- `~/.podsave/config.toml` — API keys, vault path
- `~/.podsave/queue.txt` — URL queue
- `~/.podsave/transcripts/<video_id>.json` + `.meta.json` — STT output cache
- `~/.podsave/processed.jsonl` — append-only run log
- `~/.podsave/tmp/` — transient mp3 download, cleaned after transcription
- `~/obsd/Resources/Videos/` — Obsidian vault output (user-configurable)

## Project Boundaries

- YouTube only for v1 (no RSS, Apple, Spotify, raw mp3s). Playlist URLs error cleanly, never silent-expand.
- STT is AssemblyAI only in v1. OpenAI only for extraction. Both abstracted via thin Protocol for future providers — don't bolt on more until the second provider is actually needed.
- No scheduled background runs, no web UI, no TUI in v1.
- Re-processing a URL always bumps the version number — never overwrite an existing note.

## Coding Conventions

Ruff is configured with import sorting and modern-Python upgrade rules (E/F/I/B/UP, line-length 100, target 3.14).

- Use `from __future__ import annotations`.
- Pydantic models in `src/models.py`; don't scatter data shapes across modules.
- Pipeline stages should be pure-ish functions over data models; the CLI wires them.
- Storage is plain files (TOML, JSONL, JSON). No SQLite in v1.
- User-facing errors must name the file/command to fix them (`"ASSEMBLYAI_API_KEY not set in ~/.podsave/config.toml — run `podsave init`"`).

## Testing

**Pre-push check**: Before pushing, run `uv run ruff check .` and `uv run pytest -q`.

**TDD**: Red/green on anything data-shaped — models, filename sanitizer, versioning, queue/log, render output. Skip TDD for thin SDK wrappers (download.fetch, transcribe.run); mock-test them after.

**Integration tests** live behind `PODSAVE_INTEGRATION=1` (they hit real YouTube + real APIs). Run manually before shipping each phase; not in pre-push.

## Build Phases

The plan at `docs/plans/2026-04-23-podsave-v1.md` defines six phases:

- P0 — scaffold
- P1 — init + config + storage skeleton
- P2 — probe + `--dry-run`
- P3 — download + transcribe
- P4 — extract + render
- P5 — queue drain + retry
- P6 — polish + dogfood

Ship each phase and feel it before moving on. Don't batch.
