# Operations

## Local Development

```bash
uv sync --extra dev
./podsave --help
uv run pytest -q
uv run ruff check .
```

`./podsave` is the local launcher. `uv run podsave <command>` exercises the installed
console entrypoint. Both should work during development.

## Configuration

Mutable runtime state lives outside the repo under `~/.podsave/` by default.

```bash
./podsave init
```

`init` creates:

- `config.toml`
- `queue.txt`
- `processed.jsonl`
- `transcripts/`
- `tmp/`

When run from the project root, `init` also symlinks `./queue.txt` to the real queue
file for in-editor access.

Required config values:

| Key | Used For |
| --- | --- |
| `api_keys.openai` | Structured extraction through OpenAI |
| `api_keys.assemblyai` | Diarized speech-to-text through AssemblyAI |

Optional config values:

| Key | Default | Used For |
| --- | --- | --- |
| `paths.vault` | `~/obsd/Resources/Podsave` | Obsidian note output |
| `extraction.model` | `gpt-5.4-mini` | OpenAI extraction model |

Environment overrides:

- `PODSAVE_HOME`
- `PODSAVE_OPENAI_API_KEY`
- `PODSAVE_ASSEMBLYAI_API_KEY`
- `PODSAVE_VAULT_PATH`
- `PODSAVE_EXTRACTION_MODEL`

`PODSAVE_HOME` is heavily used by tests. Avoid hard-coding `~/.podsave`; use
`src/storage/paths.py`.

## Paid Pipeline Safety

`save`, `drain`, `retry`, and integration tests can hit external services.

- Always use `./podsave save --dry-run "<youtube-url>"` before a first paid run.
- Do not run `save`, `drain`, or `retry` with placeholder keys.
- `retry <video_id>` skips download and STT but still spends extraction tokens.
- `drain` continues past failures and leaves failed URLs in the queue.
- `PODSAVE_INTEGRATION=1 uv run pytest -q` uses real YouTube/API services and costs
  money; run it only when explicitly needed.

## Common Commands

```bash
./podsave init
./podsave doctor
./podsave doctor --clean
./podsave stats
./podsave save --dry-run "<youtube-url>"
./podsave save "<youtube-url>"
./podsave retry <video_id> --focus "career advice"
./podsave queue add "<youtube-url>"
./podsave queue list
./podsave drain
./podsave search "memory consolidation" --kind quote
```

Long-running commands can produce verbose per-stage output. When running queues or
real integration paths, capture only actionable lines: per-URL success/skip/fail,
final totals, and error messages.

## CI

Workflow: `.github/workflows/ci.yml`

CI jobs:

- Lint/dead-code: `uv run ruff check .`, `uv run ruff format --check .`,
  `uv run python -m pytest -q tests/test_dead_code.py`
- Test: `uv run python -m pytest -q`

CI runs on Python 3.14 with `uv sync --frozen --extra dev`.

## Local Verification

Routine pre-push gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
./podsave --help
```

For pipeline changes, add targeted coverage around the affected boundary:

- Download/YouTube parsing: `tests/test_pipeline_download.py`,
  `tests/test_utils_youtube.py`
- STT wrapper: `tests/test_pipeline_transcribe.py`
- Extraction: `tests/test_pipeline_extract.py`
- Rendering/filenames: `tests/test_pipeline_render.py`,
  `tests/test_utils_filenames.py`
- Config/state: `tests/test_storage_config.py`, `tests/test_storage_transcripts.py`,
  `tests/test_storage_queue.py`, `tests/test_storage_log.py`
- CLI orchestration: `tests/test_cli_*.py`
- Search: `tests/test_search_*.py`

## External State

| Path | Meaning | Notes |
| --- | --- | --- |
| `~/.podsave/config.toml` | API keys, vault path, model | User-edited; env vars override |
| `~/.podsave/queue.txt` | Pending URLs | Plain text; duplicates allowed intentionally |
| `~/.podsave/transcripts/<video_id>.json` | Raw STT response | Reused forever unless manually deleted |
| `~/.podsave/transcripts/<video_id>.meta.json` | Video metadata snapshot | Written with transcript |
| `~/.podsave/processed.jsonl` | Append-only run log | Source for `stats` and doctor checks |
| `~/.podsave/tmp/` | Audio scratch | Cleaned after STT; `doctor --clean` removes leftovers |
| `<vault>/` | Final Obsidian notes | Existing notes are not overwritten; versions increment |

## Recovery And Cleanup

- Missing config: run `./podsave init`, then edit `~/.podsave/config.toml`.
- Placeholder keys: edit `config.toml` or set `PODSAVE_OPENAI_API_KEY` and
  `PODSAVE_ASSEMBLYAI_API_KEY`.
- Failed after transcription: run `./podsave retry <video_id>` to reuse the cached
  transcript.
- Failed queue item: inspect the error from `drain`; the URL remains in `queue.txt`.
- Stale audio files: run `./podsave doctor --clean`.
- Bad transcript cache: delete the matching transcript JSON and `.meta.json`, then
  run `save` again.
- Wrong vault path: update `paths.vault` in config or set `PODSAVE_VAULT_PATH`.

`doctor --clean` only deletes files under `~/.podsave/tmp/`. It does not delete
transcripts, logs, queue entries, or vault notes.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `config not found` | Run `./podsave init` or set `PODSAVE_HOME` to the intended state directory. |
| `missing api keys` | Replace `REPLACE_ME` values in `config.toml` or set env overrides. |
| Video rejected for duration | Use `--force` only after intentionally accepting short/long-video behavior. |
| Playlist rejected | Use an individual YouTube video URL; playlist expansion is intentionally unsupported. |
| No note after focused retry | Broaden `--focus` or retry without focus; zero focused items are logged as failed. |
| Search finds nothing | Confirm the vault path and that notes have `podsave` tags/callouts. |
| Note title/version surprising | Check filename sanitization and version collision behavior in `src/utils/filenames.py`. |

