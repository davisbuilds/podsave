"""Reject retained commit subjects that release automation cannot classify."""

import re
import subprocess
import sys

CONVENTIONAL_SUBJECT = re.compile(
    r"^(feat|fix|perf|refactor|docs|test|build|ci|chore|style|revert)"
    r"(?:\([^()\r\n]+\))?!?: \S.*$"
)


def _resolve_commit(revision: str) -> str:
    if not revision or revision == "0" * 40:
        raise ValueError("Missing or zero revision; refusing to guess a commit range.")
    commit = subprocess.check_output(
        ["git", "rev-parse", "--verify", "--end-of-options", f"{revision}^{{commit}}"],
        text=True,
        stderr=subprocess.PIPE,
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Revision did not resolve to a single commit.")
    return commit


def main() -> int:
    """Check non-merge commits since the supplied base revision."""
    if len(sys.argv) not in (2, 3):
        print("Usage: check_commit_subjects.py BASE_REV [HEAD_REV]", file=sys.stderr)
        return 2
    try:
        base = _resolve_commit(sys.argv[1])
        head = _resolve_commit(sys.argv[2] if len(sys.argv) == 3 else "HEAD")
        if base == head:
            raise ValueError("Empty commit range; refusing to skip classification.")
        if subprocess.run(["git", "merge-base", "--is-ancestor", base, head]).returncode != 0:
            raise ValueError("Base is not an ancestor of head; refusing an ambiguous range.")
        subjects = subprocess.check_output(
            ["git", "log", "--no-merges", "--format=%s", f"{base}..{head}"],
            text=True,
            stderr=subprocess.PIPE,
        ).splitlines()
    except (ValueError, subprocess.CalledProcessError) as error:
        print(f"Cannot classify commit range: {error}", file=sys.stderr)
        return 2
    invalid = [subject for subject in subjects if not CONVENTIONAL_SUBJECT.fullmatch(subject)]
    for subject in invalid:
        print(f"Unclassified commit subject: {subject}", file=sys.stderr)
    if invalid:
        print("Use type(scope): description; add ! for incompatible changes.", file=sys.stderr)
    return int(bool(invalid))


if __name__ == "__main__":
    sys.exit(main())
