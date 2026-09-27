"""Exercise release commit classification against real Git histories."""

import subprocess
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parents[1] / "scripts" / "check_commit_subjects.py"


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


@pytest.fixture
def history(tmp_path: Path) -> tuple[Path, str]:
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.name", "Release test")
    _git(tmp_path, "config", "user.email", "test@example.invalid")
    _git(tmp_path, "commit", "--allow-empty", "-m", "Historical unclassified baseline")
    return tmp_path, _git(tmp_path, "rev-parse", "HEAD")


def _check(repo: Path, base: str, head: str | None = None) -> subprocess.CompletedProcess[str]:
    revisions = [base] if head is None else [base, head]
    return subprocess.run(
        [sys.executable, str(CHECKER), *revisions], cwd=repo, text=True, capture_output=True
    )


def test_accepts_retained_categories_and_excludes_merge_nodes(history: tuple[Path, str]):
    repo, base = history
    _git(repo, "checkout", "-b", "feature")
    _git(repo, "commit", "--allow-empty", "-m", "feat(cli)!: change arguments")
    _git(repo, "commit", "--allow-empty", "-m", "fix: preserve note output")
    _git(repo, "checkout", "main")
    _git(repo, "merge", "--no-ff", "feature", "-m", "Merge feature branch")
    result = _check(repo, base)
    assert result.returncode == 0, result.stderr


def test_valid_pr_head_does_not_hide_unclassified_earlier_commit(history: tuple[Path, str]):
    repo, base = history
    _git(repo, "commit", "--allow-empty", "-m", "Update CLI behavior")
    _git(repo, "commit", "--allow-empty", "-m", "chore: finish cleanup")
    result = _check(repo, base)
    assert result.returncode == 1
    assert "Unclassified commit subject: Update CLI behavior" in result.stderr


@pytest.mark.parametrize("subject", ["feat:", "feat(cli): ", "unknown: behavior"])
def test_rejects_missing_description_or_unknown_type(history: tuple[Path, str], subject: str):
    repo, base = history
    _git(repo, "commit", "--allow-empty", "-m", subject)
    assert _check(repo, base).returncode == 1


def test_empty_base_fails_closed(history: tuple[Path, str]):
    repo, _ = history
    result = _check(repo, "")
    assert result.returncode != 0


@pytest.mark.parametrize("subject, expected", [("fix: repair output", 0), ("Update output", 1)])
def test_classifies_actual_push_range_not_later_checkout(
    history: tuple[Path, str], subject: str, expected: int
):
    repo, base = history
    _git(repo, "commit", "--allow-empty", "-m", subject)
    pushed_head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "commit", "--allow-empty", "-m", "Unrelated later commit")
    assert _check(repo, base, pushed_head).returncode == expected


@pytest.mark.parametrize("invalid", ["", "0" * 40, "f" * 40, "not-a-revision"])
def test_invalid_push_revisions_fail_closed(history: tuple[Path, str], invalid: str):
    repo, base = history
    _git(repo, "commit", "--allow-empty", "-m", "fix: valid control")
    head = _git(repo, "rev-parse", "HEAD")
    assert _check(repo, base, head).returncode == 0
    assert _check(repo, invalid, head).returncode == 2
    assert _check(repo, base, invalid).returncode == 2


def test_empty_or_nonforward_push_range_fails_closed(history: tuple[Path, str]):
    repo, base = history
    assert _check(repo, base, base).returncode == 2
    _git(repo, "commit", "--allow-empty", "-m", "fix: later revision")
    later = _git(repo, "rev-parse", "HEAD")
    assert _check(repo, later, base).returncode == 2
    _git(repo, "checkout", "-b", "divergent", base)
    _git(repo, "commit", "--allow-empty", "-m", "fix: alternate revision")
    divergent = _git(repo, "rev-parse", "HEAD")
    assert _check(repo, later, divergent).returncode == 2
