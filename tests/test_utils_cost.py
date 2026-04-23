from __future__ import annotations

from src.utils import cost as cost_utils


def test_zero_duration_is_zero_cost() -> None:
    est = cost_utils.estimate(0)
    assert est.stt_usd == 0
    assert est.extraction_input_usd == 0
    # Output tokens are fixed per run, so there's a floor from extraction output.
    assert est.total_usd == est.extraction_output_usd


def test_one_hour_matches_expected_rate() -> None:
    est = cost_utils.estimate(3600)
    assert est.duration_sec == 3600
    assert est.stt_usd == round(cost_utils.ASSEMBLYAI_PER_HOUR_USD, 4)
    # 3600s / 60 * 200 = 12_000 input tokens
    assert est.estimated_input_tokens == 12_000


def test_three_hour_rogan() -> None:
    est = cost_utils.estimate(3 * 3600)
    assert est.stt_usd > 0.5
    assert est.stt_usd < 0.7  # $0.21 × 3 ≈ $0.63
    assert est.estimated_input_tokens == 36_000


def test_total_is_sum_of_parts() -> None:
    est = cost_utils.estimate(1800)
    expected_total = est.stt_usd + est.extraction_input_usd + est.extraction_output_usd
    assert abs(est.total_usd - expected_total) < 0.001


def test_format_duration_under_hour() -> None:
    assert cost_utils.format_duration(0) == "0m 00s"
    assert cost_utils.format_duration(65) == "1m 05s"
    assert cost_utils.format_duration(2712) == "45m 12s"


def test_format_duration_over_hour() -> None:
    assert cost_utils.format_duration(3600) == "1h 00m 00s"
    assert cost_utils.format_duration(7980) == "2h 13m 00s"
