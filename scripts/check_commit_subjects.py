"""Reject PR commit subjects that release automation cannot classify."""

import re
import subprocess
import sys

CONVENTIONAL_SUBJECT = re.compile(
    r"^(feat|fix|perf|refactor|docs|test|build|ci|chore|style|revert)"
    r"(?:\([^()\r\n]+\))?!?: \S.*$"
)


def main() -> int:
    """Check non-merge commits since the supplied base revision."""
    if len(sys.argv) != 2:
        print("Usage: check_commit_subjects.py BASE_SHA", file=sys.stderr)
        return 2
    subjects = subprocess.check_output(
        ["git", "log", "--no-merges", "--format=%s", f"{sys.argv[1]}..HEAD"],
        text=True,
    ).splitlines()
    invalid = [subject for subject in subjects if not CONVENTIONAL_SUBJECT.fullmatch(subject)]
    for subject in invalid:
        print(f"Unclassified commit subject: {subject}", file=sys.stderr)
    if invalid:
        print("Use type(scope): description; add ! for incompatible changes.", file=sys.stderr)
    return int(bool(invalid))


if __name__ == "__main__":
    sys.exit(main())
