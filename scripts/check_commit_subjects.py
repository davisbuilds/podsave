"""Reject retained commit subjects that release automation cannot classify."""

import json
import re
import subprocess
import sys
from pathlib import Path

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


def _release_base() -> str:
    config = json.loads(Path("release-please-config.json").read_text())
    manifest = json.loads(Path(".release-please-manifest.json").read_text())
    version = manifest["."]
    if not isinstance(version, str) or not re.fullmatch(
        r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", version
    ):
        raise ValueError("Release manifest must contain a stable SemVer baseline.")
    tag = f"refs/tags/v{version}"
    status = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", tag], stderr=subprocess.PIPE
    ).returncode
    if status == 0:
        print(f"Checking unreleased commits after real tag {tag}.")
        return _resolve_commit(tag)
    if status != 1:
        raise ValueError("Cannot determine whether the release baseline tag exists.")
    bootstrap = config["bootstrap-sha"]
    if not isinstance(bootstrap, str) or not re.fullmatch(r"[0-9a-f]{40}", bootstrap):
        raise ValueError("Missing or invalid bootstrap commit; refusing to guess history.")
    print(f"No matching real tag; checking unreleased commits after bootstrap {bootstrap}.")
    return _resolve_commit(bootstrap)


def main() -> int:
    """Check a PR/push range or the full unreleased main history."""
    if len(sys.argv) not in (2, 3):
        print(
            "Usage: check_commit_subjects.py BASE_REV [HEAD_REV] | --unreleased HEAD_REV",
            file=sys.stderr,
        )
        return 2
    try:
        unreleased = sys.argv[1] == "--unreleased"
        if unreleased and len(sys.argv) != 3:
            raise ValueError("Unreleased check requires the tested head revision.")
        head = _resolve_commit(sys.argv[2] if len(sys.argv) == 3 else "HEAD")
        if unreleased and head != _resolve_commit("HEAD"):
            raise ValueError("Release metadata checkout does not match the tested head.")
        base = _release_base() if unreleased else _resolve_commit(sys.argv[1])
        if base == head and not unreleased:
            raise ValueError("Empty commit range; refusing to skip classification.")
        if subprocess.run(["git", "merge-base", "--is-ancestor", base, head]).returncode != 0:
            raise ValueError("Base is not an ancestor of head; refusing an ambiguous range.")
        subjects = subprocess.check_output(
            ["git", "log", "--no-merges", "--format=%s", f"{base}..{head}"],
            text=True,
            stderr=subprocess.PIPE,
        ).splitlines()
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as error:
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
