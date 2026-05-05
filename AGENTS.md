# AI Agent Guide

`podsave` is a single-user CLI that turns a YouTube URL into a curated Obsidian note:

```
yt-dlp audio → AssemblyAI diarized STT → OpenAI structured extraction → Obsidian markdown
```

## Documentation Map

Read in order before touching code:

- `docs/system/ARCHITECTURE.md` — layers, data flow, command composition (`_process_url` / `_extract_render_and_log`), external state (`~/.podsave/` + env-var overrides), error handling (`PodsaveError` + `@handle_errors`), cost model, v1 non-goals.
- `docs/system/FEATURES.md` — every CLI command (`save`/`drain`/`retry`/`queue`/`stats`/`doctor`/`search`), output format, frontmatter spec, callout mapping, guards/limits, what's NOT supported in v1.
- `docs/project/SPEC.md` — v1 problem framing, in/out scope, user flow, non-functional requirements, dogfood exit criteria.
- `docs/project/ROADMAP.md` — shipped versions through v2.0, near-term plan (e.g. v2.2 digest mode).

## Key Commands

The project uses `uv` for dependency management.

- **Run CLI**: `./podsave <command>` (or `uv run podsave <command>`)
- **Tests**: `uv run pytest -q`
- **Lint**: `uv run ruff check .`
- **Install**: `uv sync --extra dev`
- **Integration tests** (real APIs, costs money): `PODSAVE_INTEGRATION=1 uv run pytest -q`

**Long-running commands**: run pipeline operations like `./podsave drain`, `./podsave save`, `./podsave retry`, and integration tests in the background (e.g. `run_in_background: true`) and stream only the lines you'd act on (per-URL success/skip/fail, totals). Their full stdout is verbose and burns context for no gain.

## Working Conventions

- **Pydantic models live in `src/models.py`** — don't scatter data shapes across modules.
- **Prompts are versioned files** in `src/pipeline/prompts/<name>_v<N>.md`. Bump the version when the prompt changes; `prompt_version` lands in note frontmatter.
- **Quote timestamps**: snap to word-level boundaries, not raw utterance starts — keeps long monologue quotes from linking to the speaker's first word minutes earlier.

## Testing

- **Pre-push**: `uv run ruff check .` and `uv run pytest -q`.
- **TDD**: red/green on anything data-shaped — models, filename sanitizer, versioning, queue/log, render output, cost math. Skip TDD for thin SDK wrappers (`download.download_audio`, `transcribe.transcribe`); mock-test them after.
- **Integration tests** behind `PODSAVE_INTEGRATION=1` hit real YouTube + real APIs and cost real money. Run manually before shipping non-trivial pipeline changes; not part of pre-push.
