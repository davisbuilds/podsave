# AI Agent Guide

Guidance for coding agents working in this repository.

`podsave` turns YouTube videos into curated Obsidian notes. Pipeline: yt-dlp download → AssemblyAI diarized STT (`universal-3-pro`) → OpenAI structured extraction (`gpt-5.4-mini`, up to 10 insights/quotes/spicy-takes) → Obsidian-flavored markdown note to `~/obsd/Resources/Videos/`.

See `docs/plans/2026-04-23-podsave-v1.md` for the full spec, build phases, and open questions.

## Current Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| P0 — scaffold | ✅ | Typer CLI, uv, ruff, pytest wired up |
| P1 — init + config + storage | ✅ | `~/.podsave/` layout, config.toml, queue, JSONL log |
| P2 — probe + `--dry-run` | ✅ | yt-dlp metadata probe, cost preview panel |
| P3 — download + transcribe | ✅ | yt-dlp `-f bestaudio` (no ffmpeg), AssemblyAI `universal-3-pro` |
| P4 — extract + render | ✅ | `gpt-5.4-mini` structured output, Obsidian callouts, versioned notes |
| P5 — queue drain + retry | ✅ | `drain`, `retry <video_id>`, queue edit/remove/clear |
| P6 — polish + docs | ✅ | Error audit, ARCHITECTURE/FEATURES/SPEC docs |
| Dogfood | ✅ | 4 videos, $0.90; revealed + fixed monologue quote timestamp snap |

## Project Structure

```text
podsave/
├── podsave                 # Repo-local launcher (./podsave <cmd>)
├── queue.txt               # Symlink to ~/.podsave/queue.txt (gitignored)
├── src/
│   ├── cli.py              # Typer CLI entry point
│   ├── errors.py           # PodsaveError hierarchy
│   ├── models.py           # Shared Pydantic data models
│   ├── pipeline/
│   │   ├── download.py     # probe(), check_duration(), download_audio()
│   │   ├── transcribe.py   # AssemblyAI wrapper
│   │   ├── extract.py      # OpenAI structured-output extraction
│   │   ├── render.py       # Obsidian markdown rendering
│   │   └── prompts/
│   │       └── extract_v1.md
│   ├── storage/            # config, queue, transcripts, log, paths
│   └── utils/              # youtube URL parsing, filenames, cost math
├── tests/                  # Pytest suite (93 tests + 1 opt-in integration)
├── docs/
│   ├── plans/              # Implementation plans
│   ├── system/             # Architecture, features (P6)
│   └── project/            # Spec (P6)
└── pyproject.toml
```

## Key Commands

The project uses `uv` for dependency management.

- **Run CLI**: `./podsave <command>` (or `uv run podsave <command>`)
- **Tests**: `uv run pytest -q`
- **Lint**: `uv run ruff check .`
- **Install**: `uv sync --extra dev`
- **Integration tests** (real APIs): `PODSAVE_INTEGRATION=1 uv run pytest -q`

## External State

The CLI writes to paths outside the repo. Know these exist:

- `~/.podsave/config.toml` — API keys, vault path, extraction model
- `~/.podsave/queue.txt` — URL queue (symlinked into repo root on `init`)
- `~/.podsave/transcripts/<video_id>.json` + `.meta.json` — STT cache (reused on re-runs)
- `~/.podsave/processed.jsonl` — append-only run log, cost-per-stage
- `~/.podsave/tmp/` — transient audio download, cleaned after transcription
- `~/obsd/Resources/Videos/` — Obsidian vault output (user-configurable)

Tests isolate state via the `podsave_home` fixture (sets `$PODSAVE_HOME` to a `tmp_path`).

## Project Boundaries

- YouTube only for v1 (no RSS, Apple, Spotify, raw mp3s). Playlist URLs error cleanly, never silent-expand.
- STT is AssemblyAI only in v1. OpenAI only for extraction. Both abstracted via thin wrappers for future providers — don't bolt on more until the second provider is actually needed.
- No scheduled background runs, no web UI, no TUI in v1.
- Re-processing a URL always bumps the version number (`(v2)`, `(v3)`, …) — never overwrite an existing note.
- Duration guards: 15m floor / 4h ceiling, overridable with `--force`.
- Default models: `universal-3-pro` (STT), `gpt-5.4-mini` (extraction). Costs hard-coded in `src/utils/cost.py`.

## Output Format

Notes use Obsidian-flavored markdown (see the `obsidian-markdown` skill):

- YAML frontmatter with typed properties (`video_id`, `channel`, `url`, `published`, `duration`, `processed`, `version`, `model`, `prompt_version`, `cost_usd`) plus `tags: [podsave, podsave/video]`.
- Items render as callouts: `> [!note]` for insights, `> [!quote]` for quotes (with `[Speaker @ MM:SS](url&t=Ns)` link), `> [!warning]` for spicy takes.
- Filenames: `Channel — Title [YYYY-MM-DD].md`, NFC-normalized, path-unsafe chars stripped, 180-char cap. Versioning appends ` (v2)` etc.

## Coding Conventions

Ruff is configured with import sorting and modern-Python upgrade rules (E/F/I/B/UP, line-length 100, target 3.14).

- Use `from __future__ import annotations`.
- Pydantic models in `src/models.py`; don't scatter data shapes across modules.
- Pipeline stages should be pure-ish functions over data models; the CLI wires them.
- Storage is plain files (TOML, JSONL, JSON). No SQLite in v1.
- User-facing errors must name the file/command to fix them (`"ASSEMBLYAI_API_KEY not set in ~/.podsave/config.toml — run 'podsave init'"`). Wrap them in typed `PodsaveError` subclasses and let `@handle_errors` convert to exit-1.
- Prompts are versioned files in `src/pipeline/prompts/<name>_v<N>.md`. Bump the version when the prompt changes; `prompt_version` lands in the note frontmatter.

## Testing

**Pre-push check**: Before pushing, run `uv run ruff check .` and `uv run pytest -q`.

**TDD**: Red/green on anything data-shaped — models, filename sanitizer, versioning, queue/log, render output, cost math. Skip TDD for thin SDK wrappers (`download.download_audio`, `transcribe.transcribe`); mock-test them after.

**Integration tests** live behind `PODSAVE_INTEGRATION=1` (they hit real YouTube + real APIs). Run manually before shipping each phase; not in pre-push.

## Git

Single-branch `main`. Ship each phase as its own commit with a descriptive message (see recent `git log` for style). Update the plan doc's status table in the same commit that ships a phase.

## Build Phases

The plan at `docs/plans/2026-04-23-podsave-v1.md` defines six phases. Ship each phase and feel it before moving on. Don't batch.
