# Contributing

Bug reports, focused fixes, documentation improvements, and supported proposals
are welcome. Discuss broad pipeline changes, paid-provider integration, new input
sources, or note-format changes before major implementation. This is a
solo-maintained, single-user tool; contributions do not imply a support or
response-time promise.

Agent-assisted work is welcome. Submitters should understand the change's intent,
important behavior, cost and data tradeoffs, and verification. Explain limitations
in the PR; a prompt transcript or manual rewrite is not required. A clear
[Backlog](docs/project/BACKLOG.md) entry can go directly to a PR; use an issue
when persistent discussion or coordination helps.

Work on a focused branch from `main`. [Operations](docs/system/OPERATIONS.md)
owns setup, offline checks, and the separately gated paid integration tests.
[Git policy](docs/project/GIT_HISTORY_POLICY.md) owns retained Conventional
Commits and merge strategy. Mark incompatible CLI/config/note changes with `!`
and migration details. Release Please drafts the changelog; review consumer
meaning and migration steps in its release PR. A package release does not
publish to a registry or imply a new feature-milestone label.
