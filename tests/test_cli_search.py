from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from typer.testing import CliRunner

from src.cli import app
from src.models import ExtractionResult, Insight, VideoMeta
from src.pipeline import render
from src.storage import paths

runner = CliRunner()


def _seed_config(vault: Path) -> None:
    paths.config_path().write_text(
        '[api_keys]\nopenai = "sk-test"\nassemblyai = "aai-test"\n'
        f'[paths]\nvault = "{vault}"\n'
        '[extraction]\nmodel = "gpt-5.4-mini"\n'
    )


def _meta(video_id: str = "QVJcdfkRpH8", channel: str = "Anthropic") -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        title="Test Title",
        channel=channel,
        published=date(2026, 4, 17),
        duration_sec=1180,
    )


def _seed_note(
    vault: Path,
    *,
    text: str,
    kind: str = "insight",
    speaker: str | None = None,
    start_ms: int | None = None,
    channel: str = "Anthropic",
    filename: str | None = None,
    focus: str | None = None,
) -> Path:
    vault.mkdir(parents=True, exist_ok=True)
    extraction = ExtractionResult(
        items=[
            Insight(
                kind=kind,  # type: ignore[arg-type]
                text=text,
                rank=1,
                speaker=speaker,
                start_ms=start_ms,
            )
        ],
        model="gpt-5.4-mini",
        prompt_version="v2",
        speakers={speaker: "Real Name"} if speaker else {},
        focus=focus,
    )
    body = render.render_note(
        _meta(channel=channel),
        extraction,
        version=1,
        processed_at=datetime(2026, 4, 23, 12, 0, 0),
        cost_usd={"stt": 0.0, "extract": 0.0},
    )
    name = filename or f"{channel} — {text[:30]}.md"
    path = vault / name
    path.write_text(body)
    return path


def test_search_basic_invocation(podsave_home: Path, tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)
    _seed_note(vault, text="Reasoning is the new bottleneck.", filename="a.md")
    _seed_note(vault, text="Hallucination rates are dropping.", filename="b.md")

    result = runner.invoke(app, ["search", "reasoning"])
    assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
    assert "Reasoning" in result.stdout
    assert "Hallucination" not in result.stdout


def test_search_no_matches_exits_zero_with_message(
    podsave_home: Path, tmp_path: Path
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)
    _seed_note(vault, text="content here", filename="a.md")

    result = runner.invoke(app, ["search", "xyzzy"])
    assert result.exit_code == 0
    assert "no callouts matched" in result.stdout.lower()


def test_search_with_write_drops_results_note(podsave_home: Path, tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)
    _seed_note(vault, text="Reasoning is the new bottleneck.", filename="a.md")

    result = runner.invoke(app, ["search", "reasoning", "--write"])
    assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
    written = list((vault / "Callouts").glob("*.md"))
    assert len(written) == 1
    text = written[0].read_text()
    assert "podsave/search" in text
    assert "[[a]]" in text


def test_search_filters_pass_through(podsave_home: Path, tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)
    _seed_note(
        vault,
        text="Quote about agency.",
        kind="quote",
        speaker="A",
        start_ms=1000,
        channel="Anthropic",
        filename="anthropic-q.md",
    )
    _seed_note(
        vault,
        text="Insight about agency.",
        kind="insight",
        channel="Anthropic",
        filename="anthropic-i.md",
    )
    _seed_note(
        vault,
        text="Quote about agency.",
        kind="quote",
        speaker="A",
        start_ms=1000,
        channel="Other",
        filename="other-q.md",
    )

    result = runner.invoke(app, ["search", "agency", "--kind", "quote", "--channel", "anthropic"])
    assert result.exit_code == 0, (result.stdout or "") + (result.stderr or "")
    # Only the Anthropic quote should appear.
    assert "anthropic-q" in result.stdout
    assert "anthropic-i" not in result.stdout
    assert "other-q" not in result.stdout


def test_search_limit_caps_results(podsave_home: Path, tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)
    for i in range(5):
        _seed_note(vault, text=f"Insight number {i} about agency.", filename=f"n{i}.md")

    result = runner.invoke(app, ["search", "agency", "--limit", "2"])
    assert result.exit_code == 0
    # Footer line names how many came back.
    assert "2 callout" in result.stdout


def test_search_errors_on_invalid_since(podsave_home: Path, tmp_path: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)
    _seed_note(vault, text="x", filename="a.md")

    result = runner.invoke(app, ["search", "x", "--since", "notarealdate"])
    assert result.exit_code == 1
    assert "since" in (result.stdout + result.stderr).lower()


def test_search_empty_query_with_filter_lists_all_matching(
    podsave_home: Path, tmp_path: Path
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)
    _seed_note(vault, text="alpha", channel="Anthropic", filename="anthropic.md")
    _seed_note(vault, text="beta", channel="Other", filename="other.md")

    result = runner.invoke(app, ["search", "", "--channel", "anthropic"])
    assert result.exit_code == 0
    assert "alpha" in result.stdout
    assert "beta" not in result.stdout
