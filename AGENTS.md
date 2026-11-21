# AGENTS.md

`podsave` is a single-user CLI that turns a YouTube URL into a curated Obsidian note:

```txt
yt-dlp audio → AssemblyAI diarized STT → OpenAI structured extraction → Obsidian markdown
```

## Documentation Map

- `CONTRIBUTING.md` — contribution scope, review expectations, and delivery policy.
- `docs/system/ARCHITECTURE.md` — layers, data flow, command composition, external state (`~/.podsave/` + env-var overrides), error handling, cost model, v1 non-goals.
- `docs/system/FEATURES.md` — every CLI command, output format, frontmatter spec, callout mapping, guards/limits, v1 exclusions.
- `docs/system/OPERATIONS.md` — setup, config/env overrides, paid pipeline safety, CI/local verification, releases, recovery, troubleshooting.
- `docs/project/SPEC.md` — v1 problem framing, scope, user flow, non-functional requirements, dogfood exit criteria.
- `docs/project/ROADMAP.md` and `docs/project/BACKLOG.md` — selected direction and unresolved work.
- `docs/project/GIT_HISTORY_POLICY.md` — merge strategy, commit-subject rules, Release Please, required checks.

## Verification

- **Gate** (matches CI `.github/workflows/ci.yml`): `uv sync --locked --extra dev`,
  then `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run pytest -q`, `python3 scripts/check_comments.py`, and
  `python3 scripts/check_commit_subjects.py origin/main`.
- **Integration tests** (`PODSAVE_INTEGRATION=1 uv run pytest -q`) hit real
  YouTube and paid APIs and cost money. Run them manually before shipping
  non-trivial pipeline changes; they are not part of the gate.
- **Long-running commands:** run pipeline operations (`./podsave drain`,
  `save`, `retry`) and integration tests in the background, and stream only the
  lines you'd act on (per-URL success/skip/fail, totals). Their full stdout is
  verbose and burns context.
- **Dead-code gate** (`tests/test_dead_code.py`) owns cross-file dead code;
  ruff `F`/`ERA` own within-file unused code. For an intentionally unreferenced
  symbol or module (Protocol seam, framework-invoked), add it to
  `SYMBOL_EXCEPTIONS`/`MODULE_EXCEPTIONS` with a reason rather than silencing
  the test.

## Working Conventions

- **Pydantic models live in `src/podsave/models.py`**; don't scatter data shapes across modules.
- **Prompts are versioned files** in `src/podsave/pipeline/prompts/<name>_v<N>.md`. Bump the version when the prompt changes; `prompt_version` lands in note frontmatter.
- **Quote timestamps** snap to word-level boundaries, not raw utterance starts, so long monologue quotes don't link to the speaker's first word minutes earlier.

## Working Agreement

- **Clarify before building** when a request is vague, contradictory, or skips a
  key decision; clear, well-scoped requests need no interview.
- **Fix small issues now; backlog the rest.** Fix simple, quick, or blocking
  issues in this repo as part of the current change and call them out. Record in
  `docs/project/BACKLOG.md` only what can't be finished now or needs the
  maintainer's decision; don't open a branch or PR just for a backlog entry.
  Keep entries future-only, with evidence and a next step or revisit trigger,
  and update `ROADMAP.md` when selected direction changes, not as a shipment log.
- **Keep docs current** when a change makes a documented contract, boundary,
  procedure, or direction stale.
- **Plan and hand off work.** Reuse clear task context. Save planning docs when
  decisions, acceptance, or coordination need persistence. Leave a brief
  handoff only when needed to resume unfinished work. Commit shared docs and
  keep status current. Before archiving reviewed, completed docs in ignored
  `docs/archive/`, preserve lasting decisions and open work in maintained docs
  and repair links.
- **TDD:** red/green for features, major refactors and large changes; the red
  test must fail on the behavior, not on a missing symbol. For smaller edits, run
  the relevant existing checks.
- **Comments.** Don't add code comments. The one exception is a decision record:
  start it with `WHY:` and state a non-obvious reason the code can't express.
  Never justify a shortcut in a comment; fix it or record it in
  `docs/project/BACKLOG.md`. `python3 scripts/check_comments.py` enforces a
  ratchet: after deleting comments run it with `--update`, and never raise a count
  in `.comment-baseline.json`.
- **Commit and push.** Commit coherent chunks, staging by explicit path. Push
  your task branch and open a PR once the work is complete and the local gate
  passes; don't push directly to `main`.
- **Merge** only under the standing merge authority in the maintainer's
  workspace instructions, or when the maintainer asks. Without those
  instructions in context, leave the PR for the maintainer.
- **Re-ground after compaction** in source, this file, the owning docs, and
  recent commits. A summary and your own earlier proposals are not user approval.

## Git

Merge with a merge commit (default) or rebase; squash is disabled, so every PR
commit lands in `main`. Release Please reads those commits, and CI rejects any
subject that isn't `type(scope): description`; reword WIP commits before
opening the PR. `main` requires `Lint & dead code`, `Test (pytest)` and
`check`. Merging a Release Please PR cuts the tag and GitHub Release (no
registry publish). The Git policy owns the details.
