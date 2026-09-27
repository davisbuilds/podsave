---
date: 2026-04-26
topic: roadmap
stage: living
status: open
source: conversation
last_updated: 2026-09-27
---

# podsave Roadmap

podsave turns YouTube videos into curated Obsidian notes, then lets one user
search and reuse their callouts. The current direction is to test whether the
existing corpus becomes useful in aggregate, rather than broaden the input or
provider surface first. [Features](../system/FEATURES.md) owns shipped behavior.

## Selected Next Experiment: Digest

The existing roadmap selected digest mode as the next experiment: reuse search
results and filters, synthesize a Markdown brief with OpenAI, and optionally write
it into the vault. Its purpose is to test whether the curated corpus produces a
useful cross-note view. Confirm the filter and cost behavior before implementation;
the earlier `v2.2` label was a feature milestone, not a package release.

## Conditional Directions

- Improve focus extraction, retries, and note hygiene when actual usage exposes
  those rough edges. [Backlog](BACKLOG.md) holds the individual candidates.
- Consider embedding search only after grep usage shows concrete missed matches;
  added recall alone is not proof it helps this corpus.
- Consider a cross-source brief after digest demonstrates value within podsave.
  Keep any integration boundary explicit; podsave and other sources remain
  separately owned.

## Product Boundaries

This remains a single-user, file-based tool: YouTube input, no scheduler or web
UI, no database, and no provider abstraction without a second real provider.
[The v1 specification](SPEC.md) records those deliberate exclusions. Reopen
any boundary explicitly before a feature depends on changing it.

The old v1/v1.1/v1.2/v2.0 labels describe feature milestones, not published
package versions. Package SemVer starts from real metadata and releases;
[Operations](../system/OPERATIONS.md#releases) owns that lifecycle. Shipped
feature detail remains in Git and [Features](../system/FEATURES.md); this Roadmap
tracks direction, not every completed change.
