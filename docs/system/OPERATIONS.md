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
`src/podsave/storage/paths.py`.

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

The same CI workflow classifies retained non-merge commits on PRs and direct
main pushes (the actual `before..after` range). Main CI also checks the complete
unreleased non-merge history: after the real `v<manifest version>` tag if present,
otherwise after the configured bootstrap SHA. Both boundaries must resolve to
ancestors of the tested head. A tag at the head legitimately has no unreleased
commits; an empty push range is rejected. Missing/invalid metadata or revisions,
zero revisions, and non-forward histories fail closed. The release check has no
fixed commit-count limit and follows the release boundary as real tags advance.
If a release PR advances the manifest before its tag exists, the bootstrap
fallback checks a broader range conservatively. A later valid push cannot clear
an earlier unclassified unreleased commit whose CI failed.

CI runs on Python 3.14 with `uv sync --locked --extra dev`.

## Releases

The release unit is the Python `podsave` CLI, currently consumed from a Git
checkout with `uv sync` and the local launcher or installed console entrypoint.
`pyproject.toml` owns its package version; Release Please keeps the matching
`podsave` entry in `uv.lock`, `.release-please-manifest.json`, and `CHANGELOG.md`
in sync. `./podsave version` reads the installed package metadata. Releases
create `vX.Y.Z` tags and GitHub Releases with source archives;
there is no PyPI upload or automatic deployment.

Bootstrap starts after commit `e12f5fc774078ff597c269f1a0449ec78fc5ce28`.
On 2026-09-27, both package files were `0.1.0` and GitHub had no tags/releases.
The manifest uses `0.1.0` as an unreleased package baseline, not proof of a past
release. Manifest mode uses that nonzero baseline for version calculation even
without a real tag: the first fix/performance change proposes `0.1.1`, and the
first feature/breaking change proposes `0.2.0`. The automation setup alone is a
no-op. Roadmap labels such as v1 and v2.0 are feature milestones, independent
of package SemVer. Earlier work is not replayed into fictional releases.

For `0.x`, fixes/performance changes bump patch; new compatible features and
breaking changes bump minor. Mark incompatibility with `!` or `BREAKING CHANGE:`
and document migration steps. Choosing `1.0.0` is an explicit compatibility
commitment; do not infer it from a roadmap milestone. Normal docs, tests, CI,
refactoring, and maintenance commits alone do not trigger releases.

`.github/workflows/release-please.yml` runs only after successful same-repository
`main` push CI, confirms that `main` still matches the tested SHA, then uses a
repository-scoped GitHub App token. It never checks out event-head code or loads
its artifacts. Release writers serialize without cancellation. The preflight is
a point-in-time check, not a lock against later pushes.

Setup requires Actions variable `RELEASE_APP_CLIENT_ID`, secret
`RELEASE_APP_PRIVATE_KEY`, and an App installation on this repository with
Contents, Issues, and Pull requests write plus Metadata read. Keep the private
key out of source and logs. App tokens allow generated release PRs to start CI.

Review the generated release PR's version files, changelog, PR body (also used
for published notes), migration guidance, and green CI before merging it. That
merge authorizes tag/release creation after its `main` CI passes. This setup does
not authorize automatically merging release PRs. A green no-op means no
releasable changes, not a completed release.

For the first release, Release Please synthesizes a previous `v0.1.0` tag
from the manifest in comparison links despite that tag not existing. Before
merging, replace that comparison boundary with the real bootstrap SHA in both
`CHANGELOG.md` and the release PR body (published notes). Do not create a
fictitious previous tag. Recheck both after a bot refresh.

If an unclassified commit has already landed on main, keep release writes paused.
A later valid commit or retry does not erase it. Inspect the entire unreleased
range and compatibility intent; the owner must approve any recovery boundary or
classification exception in a separately reviewed change, with release notes
accounting for every skipped consumer change. Do not silently advance bootstrap,
create a fictitious tag, or rewrite published history to clear the gate.

To install a released checkout, fetch tags, check out the selected `vX.Y.Z`, and
run `uv sync --locked --extra dev`. For recovery, pause the release workflow and
inspect the run, release PR, manifest, tag target, and GitHub Release before
retrying. Fix incorrect pending metadata in the release PR. Correct a published
release with a follow-up commit/release; do not rewrite published tags. Returning
to a known-good checkout does not roll back external state under `~/.podsave/`.

## Local Verification

Routine pre-push gate:

```bash
uv run ruff check .
uv run ruff format --check .
python3 scripts/check_commit_subjects.py origin/main
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
| Note title/version surprising | Check filename sanitization and version collision behavior in `src/podsave/utils/filenames.py`. |

