# podsave

Single-user CLI that turns a YouTube URL into a curated Obsidian note with a
diarized transcript, top insights, quotes, spicy takes, and timestamp links back
to the source video.

```text
yt-dlp audio -> AssemblyAI diarized STT -> OpenAI structured extraction -> Obsidian markdown note
```

Transcripts cache locally, so re-processing a video is cheap: it reuses STT and
only pays extraction tokens. Re-processing the same URL writes a versioned note
instead of overwriting the prior one.

## Agent Setup

New here? Paste the prompt below into your coding agent (Claude Code, Codex, etc.) and it will install and verify the pipeline, then tell you exactly which API keys you need before processing a video.

```text
Set up the `podsave` repo for me. It's a single-user CLI that turns a YouTube URL
into a curated Obsidian note (yt-dlp audio → AssemblyAI diarized transcript →
OpenAI structured extraction → markdown). Python 3.14 + uv.

Do this, in order:

1. Install deps. Ensure `uv` is installed (https://astral.sh/uv); run
   `uv sync --extra dev` from the repo root. Clone
   https://github.com/davisbuilds/podsave.git and cd in first if needed.

2. Understand config (don't run the interactive wizard with fake keys). Real runs
   read API keys + vault path from `~/.podsave/config.toml`, created by
   `./podsave init`. Two keys are REQUIRED to process a video (both cost money):
   - ASSEMBLYAI_API_KEY (diarized speech-to-text, ~$0.21/hr audio)
   - OPENAI_API_KEY (structured extraction)
   The Obsidian vault defaults to ~/obsd/Resources/Podsave/ and can be overridden in
   config.toml. Just report these — don't fabricate keys.

3. Verify WITHOUT any keys: run `uv run pytest -q`, `uv run ruff check .`, and
   `./podsave --help`. All should pass offline. If any fail, show me the error and
   stop.

4. Report back: confirm tests + lint + help worked; list the two required API keys
   and that I'll add them via `./podsave init`; and give me the first real command
   (`./podsave save --dry-run "<youtube-url>"` to preview cost, then
   `./podsave save "<youtube-url>"` to process for real).

Don't commit anything, and don't run `save`/`drain`/`retry` until I've added real
API keys.
```

Prefer to do it yourself? The manual steps are below.

## What It Does

- Downloads YouTube audio with `yt-dlp`.
- Sends audio to AssemblyAI for diarized speech-to-text.
- Extracts structured insights with OpenAI.
- Writes Obsidian Markdown notes with timestamp-linked quotes.
- Caches transcripts under `~/.podsave/transcripts/`.
- Supports focused re-extraction from cached transcripts via `--focus`.
- Searches existing vault callouts and can write search result notes.
- Manages a simple queue under `~/.podsave/queue.txt`.

## Quick Start

Requirements:

- Python `3.14+`
- `uv`
- AssemblyAI API key for real transcription
- OpenAI API key for real extraction

```bash
uv sync --extra dev
./podsave init
./podsave save --dry-run "https://www.youtube.com/watch?v=QVJcdfkRpH8"
```

`./podsave init` creates `~/.podsave/`, prompts for API keys, and symlinks
`./queue.txt` to `~/.podsave/queue.txt` when run from the project directory.

## Common Commands

```bash
./podsave save --dry-run "https://www.youtube.com/watch?v=QVJcdfkRpH8"
./podsave save "https://www.youtube.com/watch?v=QVJcdfkRpH8"
./podsave retry QVJcdfkRpH8 --focus "career advice"
./podsave search "memory consolidation" --kind quote
./podsave search "agency" --channel Anthropic --since 90d --write
./podsave queue add "https://youtu.be/..."
./podsave queue list

uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Playlist URLs are rejected with a clean error. By default, videos under 15
minutes or over 4 hours are refused; override with `--force`.

## Configuration And External State

`~/.podsave/` holds mutable state:

- `config.toml` — API keys, vault path, extraction model
- `queue.txt` — pending URLs
- `transcripts/<video_id>.json` and `.meta.json` — STT cache
- `processed.jsonl` — append-only run log with cost breakdown
- `tmp/` — temporary audio files, cleaned after transcription

Required keys for real processing:

- `ASSEMBLYAI_API_KEY` — diarized STT using `universal-3-pro`
- `OPENAI_API_KEY` — structured extraction, `gpt-5.4-mini` by default

Vault output defaults to `~/obsd/Resources/Podsave/`. Override it in
`~/.podsave/config.toml` under `[paths] vault = "..."`.

## Code Layout

```text
src/podsave/           Typer CLI, pipeline, integrations, extraction, vault output
tests/         pytest suite
docs/          system, project, and plan docs
podsave        local launcher
queue.txt      project symlink to ~/.podsave/queue.txt after init
```

## Documentation

- Agent guidance: [AGENTS.md](AGENTS.md)
- Architecture: [docs/system/ARCHITECTURE.md](docs/system/ARCHITECTURE.md)
- Features: [docs/system/FEATURES.md](docs/system/FEATURES.md)
- Operations: [docs/system/OPERATIONS.md](docs/system/OPERATIONS.md)
- Roadmap: [docs/project/ROADMAP.md](docs/project/ROADMAP.md)
- Plans: [docs/plans/](docs/plans/)
- Original full build plan: [docs/plans/2026-04-23-podsave-v1.md](docs/plans/2026-04-23-podsave-v1.md)

## Current Boundaries

- Real `save`, `drain`, and `retry` processing requires paid API keys.
- Integration tests are opt-in with `PODSAVE_INTEGRATION=1`.
- Playlist expansion is intentionally rejected.
- Video duration guardrails are enforced unless `--force` is provided.
