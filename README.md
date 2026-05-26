# podsave

Turn a YouTube URL into a curated Obsidian note — diarized transcript, top-10 insights/quotes/spicy-takes, quotes linked back to the exact YouTube timestamp.

```
yt-dlp audio → AssemblyAI diarized STT → OpenAI structured extraction → Obsidian markdown note
```

Transcripts cache locally, so re-processing a video is cheap (it only pays the extraction tokens). Re-processing the same URL bumps a version suffix on the note rather than overwriting.

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

## Status

v1 (full pipeline), v1.1 (stats / doctor / speaker resolution / filename dedup), v1.2 (focused extraction via `--focus`), and v2.0 (vault search) all shipped. See `docs/plans/`.

## Install

```bash
uv sync --extra dev
./podsave init           # creates ~/.podsave/, prompts for API keys
```

`init` also symlinks `./queue.txt` → `~/.podsave/queue.txt` when run from the project directory, so you can edit the queue alongside the codebase in your editor.

You'll need:
- **AssemblyAI API key** — `universal-3-pro` model, ~$0.21/hr of audio
- **OpenAI API key** — `gpt-5.4-mini` by default ($0.75 / $4.50 per M in/out tokens)

Vault defaults to `~/obsd/Resources/Podsave/`; override in `~/.podsave/config.toml` under `[paths] vault = "..."`.

## Usage

```bash
# Preview what a run will cost without spending anything
./podsave save --dry-run "https://www.youtube.com/watch?v=QVJcdfkRpH8"

# Process for real: download → transcribe → extract → write note
./podsave save "https://www.youtube.com/watch?v=QVJcdfkRpH8"

# Re-extract a cached transcript through a focus lens (cheap — no STT)
./podsave retry QVJcdfkRpH8 --focus "career advice"

# Search every callout across the vault; --write drops a results note into <vault>/Callouts/
./podsave search "memory consolidation" --kind quote
./podsave search "agency" --channel Anthropic --since 90d --write

# Queue management
./podsave queue add "https://youtu.be/..."
./podsave queue list
```

Playlist URLs are rejected with a clean error (no silent expansion). By default videos under 15 minutes or over 4 hours are refused; override with `--force`.

## External state

`~/.podsave/` holds everything mutable:

- `config.toml` — API keys, vault path, extraction model
- `queue.txt` — pending URLs (symlinked into the repo on `init`)
- `transcripts/<video_id>.json` + `.meta.json` — STT cache (reused on re-runs)
- `processed.jsonl` — append-only run log with cost breakdown
- `tmp/` — audio files, cleaned after transcription

## Tech

- Python 3.14, [uv](https://github.com/astral-sh/uv), [Typer](https://typer.tiangolo.com), [rich](https://github.com/Textualize/rich), [pydantic](https://docs.pydantic.dev)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for audio (native webm/m4a, no ffmpeg needed)
- [AssemblyAI](https://www.assemblyai.com) for diarized STT (`universal-3-pro`)
- [OpenAI](https://platform.openai.com) structured outputs for extraction

## Development

```bash
uv run pytest -q             # full test suite
uv run ruff check .          # lint

PODSAVE_INTEGRATION=1 uv run pytest -q    # includes real-API integration tests
```

## Documentation

- Agent guidance: [AGENTS.md](AGENTS.md)
- Architecture: [docs/system/ARCHITECTURE.md](docs/system/ARCHITECTURE.md)
- Features: [docs/system/FEATURES.md](docs/system/FEATURES.md)
- Operations: [docs/system/OPERATIONS.md](docs/system/OPERATIONS.md)
- Roadmap: [docs/project/ROADMAP.md](docs/project/ROADMAP.md)
- Plans: [docs/plans/](docs/plans/)

See `docs/plans/2026-04-23-podsave-v1.md` for the original full build plan.
