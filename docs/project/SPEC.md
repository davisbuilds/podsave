# podsave v1 — Spec

The shipped spec for v1. For the evolving plan, deviations, and open questions, see `docs/plans/2026-04-23-podsave-v1.md`.

## Problem

I (and people like me) watch long-form YouTube interviews, lectures, and panels. The useful signal is a handful of moments — insights, memorable quotes, contrarian takes — buried in 1–4 hours of audio. Rewatching to find them is expensive; taking notes during playback breaks the flow. I want a single command that turns a URL into a curated Obsidian note with those moments extracted and linked back to the exact timestamp.

## Shape

```
youtube_url → yt-dlp audio → AssemblyAI diarized STT → OpenAI structured extraction → Obsidian markdown note
```

One machine, one user, no server. All state is plain files on disk. External APIs are paid but cheap.

## Scope — v1

**In:**
- YouTube video URLs (single videos, not playlists)
- Diarized transcription via AssemblyAI `universal-3-pro`
- Up to 10 ranked items per video, each labeled `insight` / `quote` / `spicy_take`
- Quotes link back to the precise YouTube timestamp (`&t=Ns` URL, `MM:SS` or `H:MM:SS` display)
- Obsidian-flavored markdown output with typed YAML frontmatter and callouts
- Transcript cache keyed by `video_id` — re-processing costs only extraction tokens
- Per-run versioning — never overwrite existing notes
- Queue drain for batch processing; retry for re-extracting from cache
- `--dry-run` cost preview before spending real money

**Out (deferred to vNext or later):**
- Non-YouTube sources (RSS, Apple, Spotify, raw audio files)
- Speaker name resolution (labels stay as `A`, `B`, …)
- Scheduled background runs
- Web UI, TUI, native app
- Shared state across machines or users
- Provider abstraction beyond thin wrappers
- SQLite or any structured DB

## User flow

```
$ podsave init
# prompts for OpenAI and AssemblyAI keys

$ podsave save --dry-run https://youtube.com/watch?v=xxx
# prints metadata + estimated cost, no spend

$ podsave save https://youtube.com/watch?v=xxx
# full pipeline, writes note to ~/obsd/Resources/Podsave/

$ podsave queue add <url1>
$ podsave queue add <url2>
$ podsave drain
# processes both, removes successes from queue, leaves failures

$ podsave retry <video_id>
# re-extracts from cached transcript as (v2)
```

## Non-functional requirements

- **Idempotent on success**: running the same URL twice produces two valid notes (`.md` and ` (v2).md`), never corrupts state, never double-charges STT.
- **Actionable errors**: every failure names the file or command needed to fix it.
- **Auditable**: every run (success or failure) appends a `RunRecord` to `~/.podsave/processed.jsonl` with cost breakdown.
- **Cheap to dogfood**: a cached transcript + retry costs pennies.
- **Minimal deps**: no ffmpeg, no SQLite. Python stdlib + Typer + Pydantic + rich + the three vendor SDKs (yt-dlp, assemblyai, openai).

## Quality bars

- `uv run pytest -q` — green (~100+ unit/smoke tests).
- `uv run ruff check .` — clean (line-length 100, E/F/I/B/UP rules, target py314).
- Pre-push: both of the above.
- Before shipping: `PODSAVE_INTEGRATION=1 uv run pytest -q` with a real short video.

## Dogfood exit criteria

Process 3 real videos end-to-end with varied shapes:
1. A monologue (single speaker) — verify diarization degrades gracefully.
2. A 2-speaker interview — verify quote attribution.
3. A ≥3-speaker panel — verify speaker labels stay coherent in quotes.

Acceptable if each produces a note where:
- Frontmatter is valid YAML, readable in Obsidian's property view.
- At least 5 items are useful and correctly categorized.
- Every quote's timestamp link plays at the right moment (±3s).
- Total cost per 1h video is < $1.
