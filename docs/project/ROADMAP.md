---
date: 2026-04-26
topic: roadmap
stage: living
status: open
source: conversation
last_updated: 2026-04-26
---

# podsave Roadmap

A living menu of what's shipped, what's next, and what's deliberately deferred. Read top-to-bottom in a fresh session and pick up where it makes sense.

## Where we are today (shipped)

- **v1** — Full pipeline: `podsave save / drain / retry / queue …`. yt-dlp → AssemblyAI diarized STT → OpenAI structured extraction → Obsidian markdown. Transcript cache, version-bumped notes, duration guards, playlist refusal.
- **v1.1** — Polish: filename channel-suffix dedup, `podsave stats`, `podsave doctor [--clean]`, in-prompt speaker name resolution (prompt v2 → `Speaker A` becomes the real name in callouts).
- **v1.2** — Focused extraction: `--focus TEXT` on `save` and `retry`. Focused notes land as separate files with `(focus: <slug>)` in the basename, `focus:` in frontmatter, and a `podsave/<slug>` sub-tag. Refuses to write on zero items (logs a `failed` RunRecord and exits 1).
- **v2.0** — Vault search: `podsave search QUERY [--kind --channel --focus --since --limit --write]`. Callout-level results with terminal panels by default; `--write` drops a real Obsidian MOC note into `<vault>/Callouts/` with `[[wikilinks]]` back to source notes.

Tests: ~200 passing, ruff clean, pre-push checks `uv run ruff check . && uv run pytest -q`.

## Near-term (next 1–3 sessions)

Ordered by my lean. Pick whichever pulls most.

### 1. Digest mode (`v2.2`)

`podsave digest [--since 7d] [--focus X] [--kind quote] [--write]`. Take the result set the v2.0 search engine produces, hand it to OpenAI, get a synthesized markdown brief. Lands in `<vault>/Digests/<title> [date].md`. Same filter surface as `search`, so it composes for free.

- **Why**: cheapest test of "is the corpus useful in aggregate?" — you stop just *making* notes and start *consuming* them. Stops being the question of "is the pipeline good" and becomes "is the curated vault valuable."
- **Synergy with `~/Dev/feed`**: gives podsave a digest counterpart to your weekly newsletter brief. Opens the cross-source door (item #4 below) without committing to it yet.
- **Scope**: ~1-day shipping target. New `src/digest/` subpackage, one OpenAI call, render to a new Obsidian template. Reuses search's filter pipeline.
- **My lean**: do this next.

### 2. Pipeline polish sweep (`v1.3`)

A maintenance pass over rough edges that have started to show with real use:

- **Tighter focus prompt** (v3): the v2 focus addendum is interpretive — "the word flywheel specifically" still got 9 items in the dogfood spot-check. Bias the model harder against off-topic items; document the change in the prompt diff.
- **`--items N`**: explicit cap on top-picks per note (currently capped at 10 in the prompt; making it configurable lets you tune for short content).
- **`podsave reprocess --since 30d --prompt-version v3`**: bulk retry to refresh old notes when the prompt improves. Uses the existing transcript cache, so it's purely OpenAI tokens.
- **Per-callout dedup detection**: when retrying through a new lens or a new prompt version, flag callouts whose text overlaps heavily with an existing version of the same video.

- **Why**: the rough edges aren't blockers but they're starting to be visible. A maintenance pass clears them in one focused session.
- **Scope**: ~half-day per item; bundle them or ship one at a time.
- **My lean**: do whichever item bites you first; don't preemptively sweep all four.

### 3. Embedding search (`v2.1`)

`EmbeddingMatcher` next to `GrepMatcher`, behind the existing `Matcher` Protocol. Pre-compute callout embeddings into a sidecar file per note (e.g., `<vault>/.podsave/embeddings/<basename>.npy` — gitignored). Toggle via `podsave search --mode embed`; default stays grep.

- **Why**: theoretical — embedding search would catch conceptual variants grep misses ("agency" matching "autonomy" or "self-directedness").
- **Risk**: speculative. Until you've used grep mode for a few weeks and noticed concrete misses, you don't know if the win is real or imagined. Embeddings can also surface noise.
- **My lean**: defer 2–4 weeks of grep usage first. If you find yourself rephrasing queries to find what you know is in the vault, that's the signal to build this.

## Mid-term (interesting but not urgent)

Discrete features that don't open new ground but add real polish or new slices of value.

### Better stats slicing

`podsave stats --by focus`, `podsave stats --by channel`, `podsave stats --since 30d`. The current `stats` output is a single fixed view; slicing it would help spot patterns ("I've spent $X on Anthropic videos", "my career-focused extractions average N items").

### Cost / budget guardrails

`--budget $10/month` config in `config.toml` with a soft warning in `stats` when you're tracking over. Optional hard guard via `podsave save` refusing to spend over the cap (with `--force`).

### Note hygiene extensions to `doctor`

Today: tmp orphans + transcripts-without-notes + config sanity. Could add:
- Notes with `prompt_version: v1` (candidates for retry under v2/v3 prompts)
- Notes whose source video has been deleted from YouTube (404 on URL probe)
- Notes missing a speakers map (pre-v1.1 vintage)

### Quote pull-quote helper

`podsave pullquote <video_id>` → identify *the* most shareable quote from a note (or its top 3) and format them for Twitter/Bluesky-ready copy/paste, including the timestamp link. Tiny feature, high "moment of delight" ratio.

### Speaker disambiguation across notes

When "Andrew Huberman" appears in N notes, surface it as a single Obsidian aliased entity. Could be implemented as a sidecar `<vault>/.podsave/speakers.json` and rendered into note frontmatter as `people: [Andrew Huberman]` — Obsidian's people-graph then works.

### Tag autosuggest

Model proposes 2–3 thematic tags per note (`#productivity`, `#systems-thinking`) at extract time; user accepts on first run. Adds another faceted browse axis without requiring per-video focus.

### `--regex` and `--no-color` for `search`

Power-user knobs. `--regex` lets the matcher take a real regex; `--no-color` makes piping into `grep`/`less` clean.

## Long-term thesis bets (v3+)

These are bigger architectural questions; each is months of discovery, not days.

### Cross-source intelligence brief (the `feed` synergy play)

Unify podsave callouts + `~/Dev/feed` newsletter highlights into one weekly brief — the killer "what mattered this week across everything I'm tracking" output. Probably implemented as a separate top-level tool that reads from both vaults; podsave and feed stay narrowly focused.

- **Prerequisite**: digest mode in podsave (item #1 above) so you can see what aggregation looks like with one source. Otherwise this is too speculative.
- **Open question**: does the unified brief live in Obsidian, in email, or as a CLI command that prints to terminal?

### Cross-vault retrieval / RAG

The "v2 thesis" we deferred when picking search first. Now that search exists, the question is whether semantic retrieval over callouts is meaningfully better for "what did anyone say about X" queries. Naturally folds into embedding search (v2.1).

### Multi-source extraction (RSS / Apple / Spotify / raw mp3)

Today the project explicitly refuses everything except YouTube (see `SPEC.md`). Lifting that requires a real provider abstraction (currently disallowed by the project boundary). Big lift, only worth it if the user's content sources broaden meaningfully.

### Watch mode

`podsave watch` polls a subscription list of YouTube channels for new uploads and auto-enqueues them. Conflicts with the "no background runs" boundary today. Worth revisiting only if drain becomes the user's main mode of operation and the queue is constantly stale.

## Maintenance / polish lane (parallel track)

Small wins that could be done anytime:

- **CI** — github-actions workflow running `ruff check` + `pytest` on push; badges on README.
- **Demo asset** — animated terminal capture (asciinema or vhs) of `save → search → digest`; embed in README.
- **MIT license / contributing notes** — if/when you decide to publicize more.
- **Type-hint coverage / mypy strict** — current code is type-hinted but mypy isn't enforced; could add as a pre-push step.
- **Integration test for v1.2 + v2.0** — a single integration test that processes one short video, retries with focus, then searches across the result set. Hits real APIs (~$0.05) but catches end-to-end regressions cheap.

## Explicitly NOT planned

Reaffirming the project boundaries (`docs/project/SPEC.md`, `CLAUDE.md`):

- Background scheduling, web UI, TUI, plugin
- SQLite or any database; plain files only
- Provider abstractions until a real second provider (STT or extraction) is needed
- Multi-user / sharing features
- Mid-run resume (if download succeeds but transcribe fails, you re-download)
- Partial extraction output (all-or-nothing)

If a roadmap item below requires breaking one of these, it's a separate conversation, not a silent expansion.

## How to use this doc

- **In a new session**: read top-to-bottom, then ask "what pulls at you?" to triage.
- **When picking up an item**: spec it out in `docs/plans/<date>-<topic>.md` first, then TDD per phase as in v1.1 / v1.2 / v2.0.
- **When something ships**: move it from "Near-term" up into "Where we are today" and update the `last_updated` field.
- **When something proves wrong**: delete it. This isn't an archive; it's a working menu.
