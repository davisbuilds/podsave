# AGENTS.md

`podsave` is a single-user CLI that turns a YouTube URL into a curated Obsidian note:

```txt
yt-dlp audio → AssemblyAI diarized STT → OpenAI structured extraction → Obsidian markdown
```

## Documentation Map

- `CONTRIBUTING.md` — contribution scope, review expectations, and delivery policy.
- `docs/system/ARCHITECTURE.md` — layers, data flow, command composition (`_process_url` / `_extract_render_and_log`), external state (`~/.podsave/` + env-var overrides), error handling (`PodsaveError` + `@handle_errors`), cost model, v1 non-goals.
- `docs/system/FEATURES.md` — every CLI command (`save`/`drain`/`retry`/`queue`/`stats`/`doctor`/`search`), output format, frontmatter spec, callout mapping, guards/limits, what's NOT supported in v1.
- `docs/system/OPERATIONS.md` — setup, config/env overrides, paid pipeline safety, commands, CI/local verification, external state, recovery, troubleshooting.
- `docs/project/SPEC.md` — v1 problem framing, in/out scope, user flow, non-functional requirements, dogfood exit criteria.
- `docs/project/ROADMAP.md` — selected digest experiment, conditional directions, and product boundaries.

## Key Commands

The project uses `uv` for dependency management.

- **Run CLI**: `./podsave <command>` (or `uv run podsave <command>`)
- **List commands**: `./podsave --help` (lists all available CLI commands)
- **Tests**: `uv run pytest -q`
- **Lint**: `uv run ruff check .`
- **Install**: `uv sync --extra dev`
- **Integration tests** (real APIs, costs money): `PODSAVE_INTEGRATION=1 uv run pytest -q`

**Long-running commands**: run pipeline operations like `./podsave drain`, `./podsave save`, `./podsave retry`, and integration tests in the background (e.g. `run_in_background: true`) and stream only the lines you'd act on (per-URL success/skip/fail, totals). Their full stdout is verbose and burns context for no gain.

## Working Conventions

- **Pydantic models live in `src/podsave/models.py`** — don't scatter data shapes across modules.
- **Prompts are versioned files** in `src/podsave/pipeline/prompts/<name>_v<N>.md`. Bump the version when the prompt changes; `prompt_version` lands in note frontmatter.
- **Quote timestamps**: snap to word-level boundaries, not raw utterance starts — keeps long monologue quotes from linking to the speaker's first word minutes earlier.

## Testing

- **Pre-push** (matches CI `.github/workflows/ci.yml`): `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest -q`.
- **TDD**: red/green for new features, major refactors, and large changes. The red step must fail for the behavior you're about to fix — a test that fails only because the symbol doesn't exist yet is a stub, not a red test; write the signature first, then a test that fails on the behavior. Skip the red step for code with no behavior to assert, and cover it after. For smaller edits, still run the relevant existing tests before wrapping up.
- **Integration tests** behind `PODSAVE_INTEGRATION=1` hit real YouTube + real APIs and cost real money. Run manually before shipping non-trivial pipeline changes; not part of pre-push.
- **Dead-code gate** (`tests/test_dead_code.py`): static checks for unused public symbols, orphaned modules, and unreachable code. It owns cross-file dead code; ruff `F`/`ERA` own within-file unused imports/locals and commented-out code. When a symbol/module is intentionally unreferenced (Protocol seam, framework-invoked), add it to `SYMBOL_EXCEPTIONS`/`MODULE_EXCEPTIONS` with a reason rather than silencing the test.

## Working Agreement

- **Push back before building.** If a request is incoherent or self-contradictory, or a spec/plan is vague or skips key decisions, stop and interview me — ask clarifying questions and confirm intent before writing code or changing files. Don't guess at scope or comply silently. (Clear, well-scoped requests don't need this.)
- **Keep docs current.** Update the owning reference when a change makes its contract, boundary, procedure, or direction inaccurate. Routine internal changes need no ceremonial doc edit.
- **Commit logically.** Commit completed work in coherent chunks as you proceed. Push only when explicitly asked.
- **Log durable follow-ups in `BACKLOG.md`.** Capture consequential design gaps,
  tech debt, and better approaches in `docs/project/BACKLOG.md`; fix small or
  blocking issues inline. Keep entries future-only, with evidence and a next step
  or revisit trigger; date/source volatile claims or label hypotheses. The
  capability-owning repo holds cross-repo detail. Agents can work directly from
  entries; use issues for discussion or coordination with one detailed owner.
  Reconcile affected entries as work lands; update `ROADMAP.md` when selected
  direction changes, not as a shipment log.
- **Re-ground after compaction.** A compaction summary loses precise paths, context, and verification state — before continuing, re-read this project's `AGENTS.md`, its reference docs, and recent commits.
