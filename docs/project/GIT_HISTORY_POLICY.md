# Git History and Branch Hygiene

Last updated: September 27, 2026

## Repository Merge Settings

Configured on GitHub repository `davisbuilds/podsave`:

- `allow_squash_merge`: `false`
- `allow_merge_commit`: `true`
- `allow_rebase_merge`: `true`
- `delete_branch_on_merge`: `true`
- `merge_commit_title`: `PR_TITLE`
- `merge_commit_message`: `PR_BODY`

Result:

- PR branches retain their full commit history when merged.
- `main` receives either a merge commit (preserving the PR boundary) or rebased commits (linear history), depending on which strategy the merger picks for that PR.
- Squash merging is disabled — full per-commit history is preserved.
- Merged remote branches are auto-deleted.

## Merge Strategy

Merge commits and rebase merges are both allowed; squash merges are disabled. This
is this repository's standing merge policy.

- **Default — merge commit.** Preserves the PR as a discoverable boundary in `main`'s history. Best when the PR contains multiple meaningful commits worth keeping addressable individually.
- **Rebase merge.** Use when the PR's commits are clean and the linear history reads better without an extra merge node. Avoid if the PR's commits are noisy (WIP, fixups) — clean them up locally first.
- **Authoring expectation.** Because squash is gone, individual PR commits land in `main`. Keep PR commit messages tidy: meaningful subjects, no WIP markers, no fixup chains. Squash or reword locally before opening the PR if needed. End agent commit/PR messages with the co-author trailer:

  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

## Release Commit Classification

Release Please reads retained non-merge commits, so every PR commit must use
`type(scope): description` (scope optional). Allowed types: `feat`, `fix`, `perf`,
`refactor`, `docs`, `test`, `build`, `ci`, `chore`, `style`, and `revert`.
CI checks the PR's commits against its base; merge nodes are excluded. PR titles
should follow the same convention, but a valid title cannot rescue invalid
retained commits. Reword/squash local WIP commits before delivery.

Use `feat` for new consumer behavior, `fix` for corrections, and `perf` for
performance improvements. Add `!` before `:` and migration details in a
`BREAKING CHANGE:` body/footer for incompatible CLI, config, state, or note-format
changes. Syntax checks do not establish compatibility intent. Dependencies that
fix a consumer bug need an appropriately classified commit or explicit release
notes; `chore(deps)` alone does not release.

Pre-1.0 features/breaking changes bump minor and fixes bump patch. See
[Operations](../system/OPERATIONS.md#releases) for version sources, bootstrap,
release review, and recovery. Release PRs still require review and green CI;
merging one permits the subsequent tag/GitHub Release, not registry publishing.

## CI Gates

GitHub Actions workflow: `.github/workflows/ci.yml`.

Quality gates before merge (also the pre-push expectation locally):

- `uv run ruff check .`
- `uv run ruff format --check .`
- `python3 scripts/check_commit_subjects.py origin/main` (PR commits)
- `uv run pytest -q`

Integration tests behind `PODSAVE_INTEGRATION=1` hit real APIs and cost money — run manually before shipping pipeline changes; not part of the gate.

## Branch Protection Status

This is a public repository, so the branch-protection APIs are available. No
required reviews or status checks are enforced as branch rules yet — CI gates
below are enforced by convention. Enable `required_conversation_resolution` when
the review flow warrants it.

## Recommended Ongoing Hygiene

1. Create short-lived feature branches from `main` (`feat/*`, `fix/*`, `docs/*`, `chore/*`).
2. Open PRs early; keep them focused on one intent.
3. Tidy your PR commit history *before* merging — reword/squash locally so what lands on `main` reads cleanly.
4. Pick **Create a merge commit** by default; pick **Rebase and merge** when linear history is materially better.
5. Periodically prune local branches:

```bash
git fetch --prune
git branch --merged main | grep -v ' main$' | xargs -n 1 git branch -d
```
