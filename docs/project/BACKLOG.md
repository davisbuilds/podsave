# Backlog

Future-only opportunities from the earlier working menu. Agents can work from an
entry directly; use an issue when discussion or coordination helps. These are
candidates, not commitments or package-version promises. Date/source
volatile claims or label hypotheses; keep cross-repository detail with the
capability owner.

## Open

### Focus extraction and reprocessing polish

- **What**: tighten focused extraction, consider an explicit item cap, and make
  cached-transcript reprocessing easier after prompt changes.
- **Why or evidence**: the previous Roadmap recorded an undated focus-prompt spot-check with
  nine items for a narrow request; retry already reuses cached transcripts, avoiding
  another STT charge.
- **Next**: reproduce the focus case, then change one prompt or interface behavior
  at a time and compare the resulting notes.

### Reprocessed-note overlap

- **What**: flag substantially duplicate callouts across versions of one video.
- **Why or evidence**: retries write new note versions, so overlapping excerpts
  may accumulate rather than overwrite the originals.
- **Revisit when**: repeated notes make search or review noisy.

### Search and note-hygiene extensions

- **What**: consider stats slicing, older prompt-version checks in `doctor`,
  speaker links, tags, and optional search controls such as regex.
- **Why or evidence**: the current CLI exposes a fixed stats view and grep-based
  search; these were candidate conveniences in the earlier roadmap, without a
  measured user need for each.
- **Revisit when**: usage shows a concrete missed query, confusing note, or
  repeated manual step. Select one narrow improvement then.

### Embedding search

- **What**: consider an embedding matcher alongside grep.
- **Why or evidence**: conceptual variants may be missed by grep, but the benefit
  for this corpus has not been measured and embeddings can add noise.
- **Revisit when**: actual grep queries repeatedly miss known useful callouts.

### Cross-source and input expansion

- **What**: investigate a brief across sources or support beyond YouTube.
- **Why or evidence**: a cross-source view was a long-term thesis in the earlier
  roadmap; non-YouTube input requires changing the current source boundary.
- **Revisit when**: digest proves useful for one source and the user's actual
  content mix warrants a separate integration or provider design.

### Optional automation and presentation

- **What**: consider watch mode, pull-quote formatting, a demo asset, or a CI
  badge when they serve a concrete usage need.
- **Why or evidence**: watch mode conflicts with the current no-background-runs
  boundary; the others were unscheduled polish ideas in the earlier roadmap.
- **Revisit when**: queue freshness, repeated sharing, or onboarding friction
  demonstrates the respective need.

### End-to-end paid-pipeline coverage

- **What**: exercise save, focused retry, and search in one integration run.
- **Why or evidence**: the offline suite cannot establish behavior of the real
  paid APIs and rendered Obsidian output together.
- **Next**: scope one short-video case and run it only when a non-trivial pipeline
  change justifies the cost, following [Operations](../system/OPERATIONS.md#local-verification).

### Cost and budget guardrails

- **What**: consider a monthly spend warning in stats and an optional pre-run cap.
- **Why or evidence**: the pipeline uses paid STT and extraction APIs; the earlier
  Roadmap identified cost visibility as a possible control. No budget threshold
  or enforcement policy has been selected.
- **Revisit when**: actual spending or surprise charges justify a limit. Define
  whether the cap warns or blocks and how retries count before building it.

### Static type verification

- **What**: evaluate stricter type checking as a local or CI check.
- **Why or evidence**: the earlier roadmap notes that code is type-hinted but
  mypy is not enforced. That is a candidate, not evidence of an existing type bug.
- **Next**: try the checker against current code and assess actionable findings
  and maintenance cost before making it a gate.
