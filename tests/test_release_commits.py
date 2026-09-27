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


def _check(repo: Path, base: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), base], cwd=repo, text=True, capture_output=True
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
