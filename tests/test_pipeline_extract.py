from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from src.models import VideoMeta
from src.pipeline import extract


def _meta() -> VideoMeta:
    return VideoMeta(
        video_id="QVJcdfkRpH8",
        url="https://youtu.be/QVJcdfkRpH8",
        title="Test",
        channel="Ch",
        published=date(2026, 4, 17),
        duration_sec=1180,
    )


def test_format_utterances_speaker_and_seconds() -> None:
    raw = {
        "utterances": [
            {"speaker": "A", "start": 400, "end": 1000, "text": "Hello there."},
            {"speaker": "B", "start": 12_500, "end": 14_000, "text": "General Kenobi."},
        ]
    }
    text = extract._format_utterances(raw)
    assert "[A @ 0s] Hello there." in text
    assert "[B @ 12s] General Kenobi." in text


def test_format_utterances_falls_back_to_plain_text() -> None:
    raw = {"text": "No utterances here."}
    text = extract._format_utterances(raw)
    assert text == "[A @ 0s] No utterances here."


def test_format_utterances_empty() -> None:
    assert extract._format_utterances({}) == ""


def test_extract_parses_openai_response(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_transcript = {
        "utterances": [
            {"speaker": "A", "start": 0, "end": 500, "text": "Hello."},
        ]
    }

    class _Usage:
        prompt_tokens = 1234
        completion_tokens = 56

    class _Message:
        parsed = extract._ExtractionPayload(
            items=[
                extract._ExtractedItem(
                    kind="insight", text="A thing.", rank=1, context="Matters because."
                ),
                extract._ExtractedItem(
                    kind="quote",
                    text="Exact words.",
                    speaker="A",
                    start_ms=500,
                    rank=2,
                ),
            ]
        )

    class _Choice:
        message = _Message()

    class _Completion:
        choices = [_Choice()]
        usage = _Usage()

    class _FakeParseEndpoint:
        def parse(self, *args: Any, **kwargs: Any) -> _Completion:
            return _Completion()

    class _FakeCompletions:
        parse = _FakeParseEndpoint().parse

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeBeta:
        chat = _FakeChat()

    class _FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self.beta = _FakeBeta()

    monkeypatch.setattr(extract, "OpenAI", _FakeClient)

    result = extract.extract(
        raw_transcript,
        _meta(),
        api_key="sk-test",
        model="gpt-5.4-mini",
    )

    assert len(result.items) == 2
    assert result.items[0].rank == 1
    assert result.items[0].kind == "insight"
    assert result.items[1].kind == "quote"
    assert result.items[1].start_ms == 500
    assert result.model == "gpt-5.4-mini"
    assert result.prompt_version == "v1"
    assert result.input_tokens == 1234
    assert result.output_tokens == 56


def test_extract_raises_on_empty_transcript() -> None:
    with pytest.raises(extract.ExtractionError):
        extract.extract({}, _meta(), api_key="k", model="gpt-5.4-mini")


def test_refine_quote_timestamps_snaps_to_word_start() -> None:
    from src.models import Insight

    words = [
        {"text": "The", "start": 10_000},
        {"text": "world", "start": 10_200},
        {"text": "is", "start": 10_400},
        {"text": "a", "start": 10_500},
        {"text": "dynamic", "start": 10_600},
        {"text": "mess.", "start": 10_800},
        {"text": "Later", "start": 450_000},
        {"text": "on,", "start": 450_400},
        {"text": "he", "start": 450_800},
        {"text": "said", "start": 451_000},
        {"text": "something", "start": 451_200},
        {"text": "quotable", "start": 451_500},
        {"text": "here.", "start": 451_800},
    ]
    items = [
        Insight(kind="insight", text="not a quote", start_ms=0, rank=1),
        Insight(
            kind="quote",
            text="The world is a dynamic mess.",
            speaker="A",
            start_ms=0,
            rank=2,
        ),
        Insight(
            kind="quote",
            text="he said something quotable here",
            speaker="A",
            start_ms=0,
            rank=3,
        ),
    ]
    extract._refine_quote_timestamps(items, words)
    assert items[0].start_ms == 0  # insights untouched
    assert items[1].start_ms == 10_000  # matched on 8-word prefix
    assert items[2].start_ms == 450_800  # matched via 4-word fallback


def test_refine_quote_timestamps_leaves_start_when_no_match() -> None:
    from src.models import Insight

    words = [{"text": "unrelated", "start": 5_000}, {"text": "words", "start": 5_200}]
    items = [
        Insight(kind="quote", text="completely different content", start_ms=12_345, rank=1),
    ]
    extract._refine_quote_timestamps(items, words)
    assert items[0].start_ms == 12_345


def test_refine_quote_timestamps_no_words_is_noop() -> None:
    from src.models import Insight

    items = [Insight(kind="quote", text="anything", start_ms=999, rank=1)]
    extract._refine_quote_timestamps(items, [])
    assert items[0].start_ms == 999


def test_extract_rejects_unknown_kind(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_transcript = {"utterances": [{"speaker": "A", "start": 0, "text": "x"}]}

    class _Parsed:
        parsed = extract._ExtractionPayload(
            items=[extract._ExtractedItem(kind="bogus", text="x", rank=1)]
        )

    class _Choice:
        message = _Parsed()

    class _Completion:
        choices = [_Choice()]
        usage = None

    class _FakeClient:
        def __init__(self, *a: Any, **kw: Any) -> None:
            self.beta = type(
                "_B",
                (),
                {
                    "chat": type(
                        "_C",
                        (),
                        {
                            "completions": type(
                                "_Comp",
                                (),
                                {"parse": staticmethod(lambda *a, **kw: _Completion())},
                            )
                        },
                    )
                },
            )()

    monkeypatch.setattr(extract, "OpenAI", _FakeClient)
    with pytest.raises(extract.ExtractionError):
        extract.extract(raw_transcript, _meta(), api_key="k", model="m")
