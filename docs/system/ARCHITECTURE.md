# Architecture

`podsave` is a single-user CLI that orchestrates four external dependencies (yt-dlp, AssemblyAI, OpenAI, a local Obsidian vault) into one pipeline: `YouTube URL → audio → diarized transcript → top-10 insights → Obsidian note`. No server, no daemon, no database. All state lives in plain files under `~/.podsave/`.

## Layers

```
┌─ CLI (src/cli.py, Typer) ─────────────────────────────────┐
│   init · save · drain · retry · queue {add,list,edit,…}   │
│   handle_errors → clean exit-1 messages                   │
├─ Pipeline (src/pipeline/) ────────────────────────────────┤
│   download.probe      yt-dlp --dump-single-json           │
│   download.download_audio  yt-dlp -f bestaudio            │
│   transcribe.transcribe    AssemblyAI universal-3-pro     │
│   extract.extract          OpenAI structured-output parse │
│   render.render_note       Obsidian-flavored markdown     │
├─ Storage (src/storage/) ──────────────────────────────────┤
│   config   TOML + env-var overrides                       │
│   queue    plain text, one URL per line                   │
│   transcripts  JSON + .meta.json sidecar per video_id     │
│   log       append-only JSONL of RunRecords               │
│   paths    $PODSAVE_HOME-aware path helpers               │
├─ Utils (src/utils/) ──────────────────────────────────────┤
│   youtube  URL parsing, playlist detection, video_id      │
│   cost     hard-coded rate constants, estimate() helper   │
│   filenames  NFC-safe filenames + versioned collision     │
├─ Models (src/models.py) ──────────────────────────────────┤
│   VideoMeta, Insight, ExtractionResult, RunRecord,        │
│   CostEstimate — shared across all layers                 │
└───────────────────────────────────────────────────────────┘
```

## Data flow (happy path)

```
URL
 └─ download.probe ───────────► VideoMeta
     └─ download.check_duration (15m..4h guard)
         └─ transcript_store.has(video_id)?
             ├─ yes → load cached
             └─ no  → download_audio → transcribe.transcribe
                     → transcript_store.save(raw, meta)
                 └─ extract.extract(raw, meta) ──► ExtractionResult
                     └─ render.render_note ──► markdown body
                         └─ note written to vault as `<Channel — Title [Date]>.md`
                             └─ log.append(RunRecord status="complete")
```

Transcripts are the only cache. Re-running the same URL skips download + STT and pays only the extraction tokens. Retrying a `video_id` skips everything but extract + render.

## Command composition

`save`, `drain`, and `retry` share two helpers in `cli.py`:

- `_process_url(meta, estimate, force, console)` — the full pipeline incl. cache short-circuit. Used by `save` and `drain`.
- `_extract_render_and_log(meta, raw_transcript, stt_cost, cfg, console)` — extraction + render + log only. Used by `retry` directly; `_process_url` calls it at the end.

`drain` wraps `_process_url` in a try/except to swallow `PodsaveError`s, log a `RunRecord(status="failed")`, and keep going. `save` lets errors propagate to `@handle_errors` for a clean exit-1.

## External state

| Path | Purpose | Lifecycle |
|------|---------|-----------|
| `~/.podsave/config.toml` | API keys, vault path, extraction model | Created by `init`, edited by user |
| `~/.podsave/queue.txt` | URL queue | Appended to; symlinked from repo on `init` |
| `~/.podsave/transcripts/<id>.json` | Raw AssemblyAI response | Written once per video, reused forever |
| `~/.podsave/transcripts/<id>.meta.json` | `VideoMeta` snapshot | Written with transcript |
| `~/.podsave/processed.jsonl` | Every run's `RunRecord` | Append-only, audit trail |
| `~/.podsave/tmp/` | Audio download scratch | Deleted after transcription (finally block) |
| `<vault>/<Channel — Title [Date]>.md` | Final output | New file per run, collision → `(v2)`, `(v3)`, … |

`$PODSAVE_HOME` overrides `~/.podsave/` (used by tests via the `podsave_home` fixture). `PODSAVE_OPENAI_API_KEY`, `PODSAVE_ASSEMBLYAI_API_KEY`, `PODSAVE_VAULT_PATH`, `PODSAVE_EXTRACTION_MODEL` override the corresponding config fields.

## Error handling

All user-facing errors are `PodsaveError` subclasses with actionable messages (name the file or command to fix the problem). `@handle_errors` on CLI commands converts them to `typer.Exit(1)` with a red `error:` prefix. Inside `drain`, the same errors are caught and logged so the loop can continue.

External exceptions (`subprocess.CalledProcessError`, `FileNotFoundError`, `assemblyai.types.TranscriptError`, raw `openai` errors) get wrapped at each pipeline boundary. Raw tracebacks should never reach end users.

## Cost model

All rates are hard-coded in `src/utils/cost.py`:

- AssemblyAI `universal-3-pro`: `$0.21/hr`
- OpenAI `gpt-5.4-mini`: `$0.75/M input`, `$4.50/M output`

`cost.estimate(duration_sec)` is used for `--dry-run` previews and as an optimistic "you saved ~$X" printout when a cached transcript short-circuits STT. The `RunRecord.cost_usd` field records actual spend (AssemblyAI charge from the duration; OpenAI charge from real `input_tokens`/`output_tokens` in the completion).

## Non-goals in v1

- No SQLite. JSONL is enough for a single user's history.
- No background scheduler, no watcher, no TUI.
- No multi-provider abstraction beyond thin wrappers — don't grow the provider surface until there's a real second provider to support.
- No incremental writes to the note. One call, one file, one line in the log.
