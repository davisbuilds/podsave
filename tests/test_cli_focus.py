from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.models import ExtractionResult, Insight, VideoMeta
from src.pipeline import download
from src.pipeline import extract as extract_mod
from src.storage import log as log_store
from src.storage import paths
from src.storage import transcripts as transcript_store

runner = CliRunner()


def _seed_config(vault: Path) -> None:
    paths.config_path().write_text(
        '[api_keys]\nopenai = "sk-test"\nassemblyai = "aai-test"\n'
        f'[paths]\nvault = "{vault}"\n'
        '[extraction]\nmodel = "gpt-5.4-mini"\n'
    )


def _meta(video_id: str = "vvvvvvvvvvv") -> VideoMeta:
    return VideoMeta(
        video_id=video_id,
        url=f"https://youtu.be/{video_id}",
        title="The Title",
        channel="The Channel",
        published=date(2026, 4, 17),
        duration_sec=1800,
    )


def _extraction_with_items(focus: str | None = None) -> ExtractionResult:
    return ExtractionResult(
        items=[Insight(kind="insight", text="something", rank=1)],
        model="gpt-5.4-mini",
        prompt_version="v2",
        input_tokens=100,
        output_tokens=50,
        focus=focus,
    )


def _empty_extraction(focus: str | None = None) -> ExtractionResult:
    return ExtractionResult(
        items=[],
        model="gpt-5.4-mini",
        prompt_version="v2",
        input_tokens=10,
        output_tokens=0,
        focus=focus,
    )


def _stub_extract(captured: dict[str, Any], result: ExtractionResult) -> Any:
    def _fn(*args: Any, **kwargs: Any) -> ExtractionResult:
        captured["focus"] = kwargs.get("focus")
        return result.model_copy(update={"focus": kwargs.get("focus")})

    return _fn


def test_save_passes_focus_through_and_writes_focused_note(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta()
    transcript_store.save(m.video_id, {"text": "cached"}, m)
    monkeypatch.setattr(download, "probe", lambda url: m)

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        extract_mod, "extract", _stub_extract(captured, _extraction_with_items())
    )

    result = runner.invoke(app, ["save", m.url, "--focus", "career advice"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert captured["focus"] == "career advice"

    notes = list(vault.glob("*.md"))
    assert len(notes) == 1
    assert "(focus: career-advice)" in notes[0].name


def test_retry_passes_focus_through(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta("rrrrrrrrrr2")
    transcript_store.save(m.video_id, {"text": "cached"}, m)

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        extract_mod, "extract", _stub_extract(captured, _extraction_with_items())
    )

    result = runner.invoke(app, ["retry", m.video_id, "--focus", "AI policy"])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    assert captured["focus"] == "AI policy"

    notes = list(vault.glob("*.md"))
    assert len(notes) == 1
    assert "(focus: ai-policy)" in notes[0].name


def test_save_with_empty_focus_treated_as_unfocused(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta("eeeeeeeeee3")
    transcript_store.save(m.video_id, {"text": "cached"}, m)
    monkeypatch.setattr(download, "probe", lambda url: m)

    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        extract_mod, "extract", _stub_extract(captured, _extraction_with_items())
    )

    result = runner.invoke(app, ["save", m.url, "--focus", "   "])
    assert result.exit_code == 0, result.stdout + (result.stderr or "")
    # Whitespace focus should normalize to None at the boundary.
    assert captured["focus"] in (None, "")
    notes = list(vault.glob("*.md"))
    assert len(notes) == 1
    assert "(focus:" not in notes[0].name


def test_drain_does_not_accept_focus(podsave_home: Path) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    result = runner.invoke(app, ["drain", "--focus", "x"])
    assert result.exit_code != 0


def test_save_focus_no_matches_refuses_to_write_note(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta("nnnnnnnnnn4")
    transcript_store.save(m.video_id, {"text": "cached"}, m)
    monkeypatch.setattr(download, "probe", lambda url: m)
    monkeypatch.setattr(extract_mod, "extract", _stub_extract({}, _empty_extraction()))

    result = runner.invoke(app, ["save", m.url, "--focus", "quantum biology"])
    assert result.exit_code == 1
    combined = (result.stdout or "") + (result.stderr or "")
    assert "no items matched" in combined.lower()
    assert "quantum biology" in combined
    assert list(vault.glob("*.md")) == []

    failed = [r for r in log_store.read_all() if r.status == "failed"]
    assert len(failed) == 1
    assert failed[0].focus == "quantum biology"
    assert failed[0].channel == m.channel


def test_retry_focus_no_matches_refuses_to_write_note(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta("ssssssssss5")
    transcript_store.save(m.video_id, {"text": "cached"}, m)
    monkeypatch.setattr(extract_mod, "extract", _stub_extract({}, _empty_extraction()))

    result = runner.invoke(app, ["retry", m.video_id, "--focus", "memory"])
    assert result.exit_code == 1
    combined = (result.stdout or "") + (result.stderr or "")
    assert "no items matched" in combined.lower()
    assert list(vault.glob("*.md")) == []

    failed = [r for r in log_store.read_all() if r.status == "failed"]
    assert len(failed) == 1
    assert failed[0].focus == "memory"


def test_unfocused_save_with_zero_items_also_refuses(
    podsave_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner.invoke(app, ["init", "--no-prompt"])
    vault = tmp_path / "vault"
    _seed_config(vault)

    m = _meta("uuuuuuuuuu6")
    transcript_store.save(m.video_id, {"text": "cached"}, m)
    monkeypatch.setattr(download, "probe", lambda url: m)
    monkeypatch.setattr(extract_mod, "extract", _stub_extract({}, _empty_extraction()))

    result = runner.invoke(app, ["save", m.url])
    assert result.exit_code == 1
    assert list(vault.glob("*.md")) == []

    failed = [r for r in log_store.read_all() if r.status == "failed"]
    assert len(failed) == 1
    assert failed[0].focus is None
