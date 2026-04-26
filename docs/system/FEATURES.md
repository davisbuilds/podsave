# Features

What `podsave` does today, keyed to the CLI surface.

## Commands

### `podsave init [--no-prompt] [--overwrite]`

Creates `~/.podsave/` with `config.toml`, `queue.txt`, `processed.jsonl`, `transcripts/`, `tmp/`. In interactive mode prompts for OpenAI and AssemblyAI keys (hidden input). With `--no-prompt`, writes `REPLACE_ME` placeholders. When run from inside the project directory, also symlinks `./queue.txt → ~/.podsave/queue.txt` so the queue is editable in the project's editor.

### `podsave save <url> [--dry-run] [--force] [--focus TEXT]`

Processes one YouTube URL end-to-end.

- **`--dry-run`**: prints a panel with video metadata and an estimated cost breakdown (AssemblyAI `$X @ $/hr`, OpenAI `~N tokens @ $/M`). Does not touch the network beyond the metadata probe; no spend.
- **default**: probe → guard duration → (download + transcribe | cached transcript) → extract → render → write note to vault → append log entry. Prints per-stage status with rich; ends with total spend for the run.
- **`--force`**: bypasses the 15m floor / 4h ceiling duration guard.
- **`--focus TEXT`**: narrows extraction to items relevant to a free-form lens (e.g. `--focus "career advice"`). The note lands as a separate file with `(focus: <slug>)` in the basename and `podsave/<slug>` as a sub-tag, so different lenses on the same video coexist. If the model returns zero items, the CLI refuses to write a note (exits 1, logs a `failed` RunRecord). Empty/whitespace focus is treated as no focus.
- Playlist URLs are rejected before any network call with a `PlaylistURLError`.

### `podsave drain [--force]`

Loops over every URL in the queue in order. On success removes the URL; on failure leaves it and logs a `status="failed"` `RunRecord` with the error string. Continues past failures. Prints a final summary with success/fail counts and per-URL error detail. Doesn't retry failed entries automatically — a second `drain` will.

### `podsave retry <video_id> [--focus TEXT]`

Loads a cached transcript + meta for `video_id` and re-runs extract + render only. No download, no STT spend — only OpenAI tokens. The new note lands as `(v2)`, `(v3)`, etc. alongside the existing versions. Errors cleanly if no transcript is cached.

Supports `--focus TEXT` with the same semantics as `save --focus`: the focused note lands as its own file (`(focus: <slug>)` basename + `podsave/<slug>` sub-tag) and versions independently from broad and other-focus runs of the same video.

### `podsave queue …`

| Subcommand | Behavior |
|------------|----------|
| `add <url>` | Append to `queue.txt` (duplicates allowed intentionally — same video, different contexts) |
| `list` | Numbered list of queued URLs, plus the backing file path as a footer |
| `edit` | Open `queue.txt` in `$EDITOR` (fallback: `open -t` on macOS) |
| `remove <url>` | Remove the first matching URL; exit-1 if not found |
| `clear [--yes]` | Empty the queue; confirms interactively unless `--yes` |

### `podsave stats`

Lifetime usage summary read from `processed.jsonl`: completed-note count (split into v1 vs retries), failed-run count, hours of audio processed, total spend, average cost per hour, and a top-channels table by note count + spend. Returns "no runs yet" if the log is empty.

Channel attribution comes from `RunRecord.channel`, which is recorded on every new run. Older log lines without that field bucket under `(unknown)`.

### `podsave doctor [--clean]`

Inspects `~/.podsave/` for housekeeping issues:

- **Tmp orphans**: leftover audio in `~/.podsave/tmp/` (filename + size). With `--clean`, these are deleted.
- **Cached transcripts without a complete run**: `<video_id>` + cached title — hint to `podsave retry <video_id>`.
- **Config sanity**: missing or placeholder API keys, vault path that doesn't yet exist.

Read-only by default. `--clean` only ever touches files in `~/.podsave/tmp/` — never deletes transcripts (use `podsave retry` to re-extract from them, or delete the JSON manually to force re-transcription).

### `podsave hello` / `podsave version`

Smoke commands. `hello` proves the CLI is wired up. `version` prints the installed package version from `importlib.metadata`.

## Output format

Every note is Obsidian-flavored markdown written to `<vault>/<Channel — Title [YYYY-MM-DD]>.md`. Re-processing the same video writes `(v2)`, `(v3)` etc. beside the original — originals are never overwritten.

### Frontmatter

Typed YAML. Every field is always present so Obsidian property views stay stable:

```yaml
---
title: "<video title>"
video_id: <youtube id>
channel: "<channel name>"
url: https://www.youtube.com/watch?v=<id>
published: 2026-04-17
duration: 19m 40s
processed: 2026-04-23T11:30:47
version: 1
model: gpt-5.4-mini
prompt_version: v1
cost_usd: 0.007
tags:
  - podsave
---
```

When the run was focused, two extra elements appear: a `focus: "<raw text>"` line in the frontmatter (just above `tags:`) and a `podsave/<slug>` sub-tag alongside `podsave`. Broad runs are unchanged.

### Body

- Short header line with channel, publish date, duration, and a "Watch on YouTube" link.
- `## Top picks` section with up to 10 callouts, ranked.
- Callout kind mapping:
  - `insight` → `> [!note]`
  - `quote` → `> [!quote]` with title `N. Quote — [Speaker X @ MM:SS](url&t=Ns)`
  - `spicy_take` → `> [!warning]`
- Each callout body is the item text; an optional `*italic*` context line underneath explains *why* it matters.
- Footer: `*N item(s) extracted by <model> (prompt <version>).*`
- **Speaker names**: the extraction model resolves the `A/B/C` letters to real names from intros, addresses, and sign-offs in the transcript. Quote titles render the resolved name (`[Andrew Huberman @ MM:SS]`); a low-confidence guess gets a `(?)` suffix; falls back to `Speaker A` when no match is found. Speaker map lives on `ExtractionResult.speakers`, not in frontmatter.

## Guards and limits

- **Duration**: 15m floor, 4h ceiling. Override with `--force`.
- **Playlists**: rejected in `utils/youtube.is_playlist` before yt-dlp runs.
- **File names**: NFC-normalized, path-unsafe chars stripped (`\/:*?"<>|` + control), whitespace collapsed, 180-char cap. If the title ends with ` | <Channel>`, ` — <Channel>`, or ` - <Channel>` (case-insensitive), that suffix is dropped so the channel doesn't appear twice in the filename. The frontmatter `title` keeps the original verbatim. When `--focus` is set, ` (focus: <slug>)` is appended to the basename so different lenses on the same video are visually distinct.
- **Transcript cache**: never expires automatically; delete the JSON to force re-transcription.

## Cost awareness

- `--dry-run` always runs before a paid call on the first try.
- Cached-transcript runs print `saved ~$X` so you see the cache paying off.
- Every run appends a per-stage breakdown (`{"stt": 0.03, "extract": 0.007}`) to `processed.jsonl`. `jq -c '.cost_usd' ~/.podsave/processed.jsonl | paste -sd+ - | bc` will sum lifetime spend.

## What's NOT supported in v1

- Providers other than YouTube + AssemblyAI + OpenAI
- Background scheduling or watching
- Web UI, TUI, or plugin
- Mid-run resume (if download succeeds but transcribe fails, you re-download)
- Partial extraction output (either it all lands or the run fails)
