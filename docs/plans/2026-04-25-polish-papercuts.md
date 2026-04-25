---
date: 2026-04-25
topic: polish-papercut-wins
stage: shipped
status: complete
source: conversation
last_updated: 2026-04-25
---

# podsave v1.1 — Polish & Papercut Wins

Four focused improvements after v1 landed and survived dogfood. None of these expand v1's surface meaningfully — they each pay down a known rough edge or add a small introspection command. Shipped together they make the daily-driver experience noticeably better without any new architecture.

## Goals

1. **Filename dedup** — stop duplicating the channel name when the title already ends with `| <Channel>`.
2. **`podsave stats`** — at-a-glance lifetime usage (count, spend, avg cost/hour, top channels).
3. **`podsave doctor`** — inspect & optionally fix tmp orphans and cached transcripts that never produced a note.
4. **Speaker name resolution** — replace `Speaker A / B / C` with real names extracted from the transcript itself.

Order is from cheapest → most invasive so each lands behind a green test bar before the next.

## Non-goals

- Cross-vault search / RAG (separate v2 thesis).
- `--focus` flag on save/retry (separate v1.2 idea).
- Chunk-and-merge for >3h videos (only worth it if quality cliff shows up).
- Any new external dependency.

## Current state recap

- 105 tests passing, ruff clean.
- Pipeline is `cli → pipeline/{download,transcribe,extract,render} → storage/{config,queue,log,transcripts}`.
- Filenames are produced by `src/utils/filenames.safe_name(channel, title, *, published)`.
- Speakers come out of AssemblyAI as `"A"`, `"B"`, `"C"` and are passed through unchanged into `Insight.speaker`, then rendered as `"Speaker A"` etc. in `src/pipeline/render._callout_title`.
- `processed.jsonl` already records `cost_usd` per stage and `duration_sec` — `stats` is essentially a reduce over `log.read_all()`.

## Phase 1 — Filename dedup

### Problem

When a video title ends with `... | AI Explained`, `safe_name("AI Explained", "Foo | AI Explained", ...)` yields `AI Explained — Foo | AI Explained [...]`. Channel appears twice. Same problem with `— <Channel>` and `- <Channel>` suffixes.

### Approach

Pure-function fix in `src/utils/filenames.py`. Strip a trailing channel marker from the title before composing the basename. Match patterns (case-insensitive, after NFC + whitespace collapse):

- `<title> | <channel>`
- `<title> — <channel>` (em dash)
- `<title> - <channel>` (hyphen with surrounding space)

Only strip when the trailing token equals `channel` exactly (after the same `_clean` normalization on both sides). Title in frontmatter stays as the original — only the filename basename is dedup'd.

### Tests (TDD, red first)

`tests/test_utils_filenames.py`:

- `test_safe_name_strips_pipe_channel_suffix` — `("AI Explained", "Foo | AI Explained")` → `"AI Explained — Foo [...]"`.
- `test_safe_name_strips_em_dash_channel_suffix` — same with `—`.
- `test_safe_name_strips_hyphen_channel_suffix` — same with ` - `.
- `test_safe_name_strips_case_insensitive` — `("AI Explained", "Foo | ai explained")` works.
- `test_safe_name_keeps_partial_match` — `("AI", "Foo | AI Explained")` does NOT strip (not equal).
- `test_safe_name_keeps_when_channel_is_empty` — empty channel never strips.

### Risk

Tiny. Only affects basename composition, not frontmatter. If we strip too aggressively, the file is still valid; user only loses some title context.

## Phase 2 — `podsave stats`

### Problem

You currently have to `jq` over `processed.jsonl` to know what the tool has done lifetime. Quick `podsave stats` makes the cost story visible.

### Approach

Read-only command. Reduce `log_store.read_all()` to a small report. No new file format, no new state.

Output (rich tables, two panels):

```
Lifetime
  Notes:        12  (10 v1, 2 retries)
  Failed runs:  1
  Hours saved:  9.3h of audio
  Total spend:  $1.84
  Avg / hour:   $0.20

Top channels
  AI Explained          4   $0.42
  Talks at Google       3   $0.61
  Anthropic             2   $0.41
  ...
```

Definitions:
- "Notes" = count of `RunRecord` rows with `status == "complete"`.
- "v1 / retries" = split by `version == 1` vs `> 1`.
- "Failed runs" = `status == "failed"`.
- "Hours saved" = sum of `duration_sec / 3600` across complete records.
- "Total spend" = sum of `cost_usd.values()` across all records (failed runs typically contribute 0).
- "Avg / hour" = total spend / hours saved (skip if hours saved = 0).
- "Top channels" — needs the channel name. Two options:
  1. Read each note's frontmatter to look up channel (slow, fragile if user moves notes).
  2. Add a `channel` field to `RunRecord` going forward, fall back to "(unknown)" for old rows.

Pick option (2). Channel is already in `meta` everywhere we write a record. Adding `channel: str | None = None` to `RunRecord` is backwards-compatible — old JSONL lines still parse.

### Files touched

- `src/models.py` — add `RunRecord.channel: str | None = None`.
- `src/cli.py` — set `channel=meta.channel` in both `_extract_render_and_log` and the `drain` failure path (use `meta.channel` if probed, else None).
- `src/cli.py` — new `@app.command() stats()` body.
- New `tests/test_cli_stats.py` — fixture writes a few `RunRecord`s into a tmp log, asserts the rich output mentions key totals.

### Tests

- `test_stats_empty_log` — prints "no runs yet" and exits 0.
- `test_stats_counts_completes_and_failures` — three completes + one failed, asserts both numbers.
- `test_stats_sums_cost` — assert printed total matches sum of `cost_usd` values.
- `test_stats_top_channels` — three completes with two distinct channels, top-row count is right.
- `test_stats_handles_missing_channel` — old-style records (no `channel`) bucket under "(unknown)".

### Risk

Schema migration is the only risk. Keeping `channel` optional on `RunRecord` makes it strictly additive — no migration needed.

## Phase 3 — `podsave doctor`

### Problem

After failed/interrupted runs we can leak:
- Audio files in `~/.podsave/tmp/` (download succeeded, transcribe crashed before the `finally`-block unlinked).
- Cached transcripts in `~/.podsave/transcripts/<id>.json[+.meta.json]` that never produced a note (extract crashed, or run was killed).

### Approach

`podsave doctor [--clean]` — read-only by default, prints a report. With `--clean`, removes tmp orphans and prints what it removed. Never deletes transcripts (they're expensive — `retry` is the right tool for those).

Report sections:
1. **Tmp orphans**: every file in `~/.podsave/tmp/` with size + mtime.
2. **Cached transcripts without a `complete` log entry**: list `<video_id>` + the meta sidecar's title. These are good candidates for `podsave retry <video_id>`.
3. **Config sanity**: API keys present? Vault path exists?

`--clean` only acts on section 1.

### Files touched

- New `src/cli.py::doctor` command.
- New `src/storage/doctor.py` (or inline helpers in `cli.py` if small enough — likely inline).
- New `tests/test_cli_doctor.py`.

### Tests

- `test_doctor_clean_state` — fresh `podsave_home`, prints all-OK report, exit 0.
- `test_doctor_finds_tmp_orphan` — drop a fake mp3 in tmp, doctor lists it.
- `test_doctor_clean_removes_tmp_orphan` — `--clean` actually unlinks it.
- `test_doctor_finds_orphan_transcript` — write transcript + meta sidecar, no log entry → listed as needing retry.
- `test_doctor_skips_transcripts_with_complete_run` — transcript + matching `RunRecord(status="complete")` → not listed.
- `test_doctor_warns_on_missing_keys` — config with placeholder keys → warning row.

### Risk

Low. The destructive path is gated behind `--clean` and only touches `~/.podsave/tmp/` files (already designated transient).

## Phase 4 — Speaker name resolution

### Problem

The transcript labels speakers `A`, `B`, `C`. The model already has the context to guess real names (intros, addressing each other, sign-offs) — and dogfood notes show it sometimes inlines the real name in `context` ("Amanda's closing definition"). Today the rendered note still says `Speaker A`, which feels rough.

### Approach

Single-pass extension of the existing extraction call:

1. Add a `speakers` field to `_ExtractionPayload` — `list[_SpeakerLabel]` where `_SpeakerLabel = {label: str, name: str | None, confidence: Literal["high", "low"] | None}`.
2. Update `extract_v2.md` (new prompt version) telling the model to:
   - Identify speaker names from intros/addresses/sign-offs.
   - Return one entry per distinct label seen in the transcript.
   - Set `name = null` if you can't identify them with at least medium confidence.
   - Set `confidence` to `"low"` for tentative guesses (rendered as `"Speaker A (Andrew?)"`).
3. New `SpeakerMap` model (or just a `dict[str, str | None]` on `ExtractionResult`). Keep it simple: `speakers: dict[str, str | None]` keyed by label.
4. Render passes the map into `_callout_title` to swap `"Speaker A"` → `"Andrew Huberman"` (high) or `"Speaker A (Andrew?)"` (low) or fall back to `"Speaker A"` (None).
5. Bump prompt to `v2`. `prompt_version` field in frontmatter already records this.

### Why a single pass

A second OpenAI call would double extraction cost for marginal benefit and add latency. The model already reads the whole transcript for ranking — surfacing speaker names is "free" in the same context.

### Files touched

- `src/pipeline/prompts/extract_v2.md` — copy v1, add the speaker-resolution section.
- `src/pipeline/extract.py` — bump `PROMPT_VERSION = "v2"`, point at v2 file, add `_SpeakerLabel` to schema, project to `dict[str, str | None]`.
- `src/models.py` — `ExtractionResult.speakers: dict[str, str | None] = Field(default_factory=dict)` (additive, optional).
- `src/pipeline/render.py` — `_callout_title` accepts the speaker map; render `_resolved_speaker(label, map)`.
- `tests/test_pipeline_extract.py` — extend mocked OpenAI parse to include speakers; assert plumbed through.
- `tests/test_pipeline_render.py` — new tests for resolved name, low-confidence suffix, fallback to letter.

### Tests

- `test_render_uses_resolved_speaker_name` — map `{"A": "Andrew Huberman"}`, callout title says `"Andrew Huberman @ MM:SS"`.
- `test_render_low_confidence_speaker` — value `"Andrew Huberman?"` (or a `(low)` marker — TBD by render shape) → renders with question mark.
- `test_render_falls_back_to_speaker_letter` — empty map → `"Speaker A"` (current behavior preserved).
- `test_extract_returns_speaker_map` — mocked payload with speakers list → `ExtractionResult.speakers` populated.

### Risk

- Prompt regression: the v2 prompt could degrade ranking quality. Mitigation: keep all v1 ranking rules verbatim; speaker resolution is a strictly additive section. Cost the v2 prompt against a cached transcript before declaring done.
- Hallucinated names: model invents a name. Mitigation: ask for confidence, render `(?)` for low; user can always look at the YouTube link if unsure.
- Frontmatter / Insight schema changes: none. `Insight.speaker` still stores the letter; render does the mapping. This means old notes still render correctly if rebuilt from cached transcript + retry.

## Sequencing & verification

1. **Phase 1** — TDD: red on the new filename tests, then implement, full suite green, ruff clean.
2. **Phase 2** — TDD on stats reducer first, then schema field, then CLI command. Full suite green.
3. **Phase 3** — TDD on doctor inspection, then `--clean` path. Full suite green.
4. **Phase 4** — biggest. Write v2 prompt, extend extract schema, render mapping, then exercise via `podsave retry <video_id>` against a cached transcript before declaring done. (Real-API retry, not in pre-push.)

After all four: update `docs/system/FEATURES.md` (new commands + filename rule + speaker section) and `docs/plans/2026-04-23-podsave-v1.md`'s "Known rough edges" to mark the resolved ones.

## Out of scope (caught while specing)

- A dedicated `Speaker` Pydantic model — `dict[str, str | None]` is enough for v1.1.
- Configurable filename template — not requested, premature.
- A `podsave reprocess --since <date>` bulk-retry — interesting for v1.2 once the speaker-name change makes everyone want a v2 of every note.
