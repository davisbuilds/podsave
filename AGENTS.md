# AI Agent Guide

Guidance for coding agents working in this repository.

`podsave` is a single-user CLI that turns a YouTube URL into a curated Obsidian note. Pipeline:

```
yt-dlp audio → AssemblyAI diarized STT → OpenAI structured extraction → Obsidian markdown
```

For deeper context, read these in order:

- `docs/system/ARCHITECTURE.md` — layers, data flow, error model, external state
- `docs/system/FEATURES.md` — every user-facing command and behavior
- `docs/project/SPEC.md` — what's in scope and what's deliberately not

## Project Structure

```text
podsave/
├── podsave                 # Repo-local launcher (./podsave <cmd>)
├── queue.txt               # Symlink to ~/.podsave/queue.txt (gitignored)
├── src/
│   ├── cli.py              # Typer CLI; wires pipeline stages
│   ├── errors.py           # PodsaveError hierarchy
│   ├── models.py           # Shared Pydantic data models
│   ├── pipeline/
│   │   ├── download.py     # probe(), check_duration(), download_audio()
│   │   ├── transcribe.py   # AssemblyAI wrapper
│   │   ├── extract.py      # OpenAI structured-output extraction
│   │   ├── render.py       # Obsidian markdown rendering
│   │   └── prompts/extract_v1.md
│   ├── storage/            # config, queue, transcripts, log, paths
│   └── utils/              # youtube URL parsing, filenames, cost math
├── tests/                  # Pytest suite + opt-in integration
└── docs/{system,project,plans}/
```

## Key Commands

The project uses `uv` for dependency management.

- **Run CLI**: `./podsave <command>` (or `uv run podsave <command>`)
- **Tests**: `uv run pytest -q`
- **Lint**: `uv run ruff check .`
- **Install**: `uv sync --extra dev`
- **Integration tests** (real APIs, costs money): `PODSAVE_INTEGRATION=1 uv run pytest -q`

## External State

The CLI writes to paths outside the repo. These are not visible from `git status`:

- `~/.podsave/config.toml` — API keys, vault path, extraction model
- `~/.podsave/queue.txt` — URL queue (symlinked into repo root on `init`)
- `~/.podsave/transcripts/<video_id>.json` + `.meta.json` — STT cache (reused on re-runs)
- `~/.podsave/processed.jsonl` — append-only run log, cost-per-stage
- `~/.podsave/tmp/` — transient audio, cleaned in a `finally` block after transcription
- `~/obsd/Resources/Podsave/` — Obsidian vault output (configurable)

Tests isolate this state via the `podsave_home` fixture (sets `$PODSAVE_HOME` to a `tmp_path`). `PODSAVE_OPENAI_API_KEY`, `PODSAVE_ASSEMBLYAI_API_KEY`, `PODSAVE_VAULT_PATH`, and `PODSAVE_EXTRACTION_MODEL` override the matching config fields.

## Project Boundaries

- **YouTube only.** No RSS, Apple, Spotify, raw mp3s. Playlist URLs error cleanly — never silent-expand.
- **One provider per stage.** AssemblyAI for STT, OpenAI for extraction. Both sit behind thin wrappers, but don't grow a provider abstraction until a real second provider exists.
- **No background runs, no web UI, no TUI, no SQLite.** Plain files are enough for a single user.
- **Re-processing bumps the version.** Same URL → ` (v2)`, ` (v3)`, … Never overwrite an existing note.
- **Duration guards.** 15m floor / 4h ceiling, overridable with `--force`.
- **Default models** are `universal-3-pro` (STT) and `gpt-5.4-mini` (extraction). Rates are hard-coded in `src/utils/cost.py`; update them there if pricing changes.

## Output Format

Notes use Obsidian-flavored markdown (see the `obsidian-markdown` skill):

- YAML frontmatter with typed properties (`video_id`, `channel`, `url`, `published`, `duration`, `processed`, `version`, `model`, `prompt_version`, `cost_usd`) plus `tags: [podsave]`.
- Items render as callouts: `> [!note]` for insights, `> [!quote]` for quotes (with `[Speaker @ MM:SS](url&t=Ns)` link), `> [!warning]` for spicy takes.
- Filenames: `Channel — Title [YYYY-MM-DD].md`, NFC-normalized, path-unsafe chars stripped, 180-char cap. Versioning appends ` (v2)` etc.
- Quote timestamps are snapped to word-level boundaries, not raw utterance starts — keeps long monologue quotes from linking to the speaker's first word minutes earlier.

## Coding Conventions

Ruff is configured with import sorting and modern-Python upgrade rules (E/F/I/B/UP, line-length 100, target 3.14).

- Use `from __future__ import annotations`.
- Pydantic models live in `src/models.py`; don't scatter data shapes across modules.
- Pipeline stages are pure-ish functions over data models. The CLI wires them; commands like `save`/`drain`/`retry` share `_process_url` and `_extract_render_and_log` helpers in `cli.py`.
- Storage is plain files (TOML, JSONL, JSON).
- User-facing errors must name the file or command to fix them (e.g. `"ASSEMBLYAI_API_KEY not set in ~/.podsave/config.toml — run 'podsave init'"`). Wrap them in typed `PodsaveError` subclasses; `@handle_errors` converts them to a clean exit-1. External exceptions (subprocess, AssemblyAI, OpenAI) must be caught at the pipeline boundary — raw tracebacks should never reach the user.
- Prompts are versioned files in `src/pipeline/prompts/<name>_v<N>.md`. Bump the version when the prompt changes; `prompt_version` lands in the note frontmatter.

## Testing

**Pre-push check**: run `uv run ruff check .` and `uv run pytest -q`.

**TDD**: red/green on anything data-shaped — models, filename sanitizer, versioning, queue/log, render output, cost math. Skip TDD for thin SDK wrappers (`download.download_audio`, `transcribe.transcribe`); mock-test them after.

**Integration tests** live behind `PODSAVE_INTEGRATION=1` (they hit real YouTube + real APIs and cost real money). Run manually before shipping non-trivial pipeline changes; not part of pre-push.
