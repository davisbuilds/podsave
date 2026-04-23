"""Cost estimation for a single video pass.

Rates are knowledge-cutoff estimates (Jan 2026). Real bills should be used to
calibrate these after Phase 3's first live run.
"""

from __future__ import annotations

from src.models import CostEstimate

ASSEMBLYAI_PER_HOUR_USD = 0.21  # universal-3-pro

OPENAI_INPUT_PER_MILLION_USD = 0.75  # gpt-5.4-mini
OPENAI_OUTPUT_PER_MILLION_USD = 4.50

TOKENS_PER_MINUTE_AUDIO = 200  # ~150 spoken words/min × ~1.3 tokens/word
OUTPUT_TOKENS_PER_RUN = 500  # 10 insights × ~50 tokens each, padded


def estimate(duration_sec: int) -> CostEstimate:
    stt = (duration_sec / 3600.0) * ASSEMBLYAI_PER_HOUR_USD

    input_tokens = int(duration_sec / 60 * TOKENS_PER_MINUTE_AUDIO)
    extract_in = (input_tokens / 1_000_000.0) * OPENAI_INPUT_PER_MILLION_USD
    extract_out = (OUTPUT_TOKENS_PER_RUN / 1_000_000.0) * OPENAI_OUTPUT_PER_MILLION_USD

    total = stt + extract_in + extract_out

    return CostEstimate(
        duration_sec=duration_sec,
        stt_usd=round(stt, 4),
        extraction_input_usd=round(extract_in, 4),
        extraction_output_usd=round(extract_out, 4),
        total_usd=round(total, 4),
        stt_rate_per_hour=ASSEMBLYAI_PER_HOUR_USD,
        estimated_input_tokens=input_tokens,
        input_rate_per_million=OPENAI_INPUT_PER_MILLION_USD,
        estimated_output_tokens=OUTPUT_TOKENS_PER_RUN,
        output_rate_per_million=OPENAI_OUTPUT_PER_MILLION_USD,
    )


def format_duration(seconds: int) -> str:
    """Human-readable duration: `45m 12s` or `2h 13m 04s`."""
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {secs:02d}s"
    return f"{minutes}m {secs:02d}s"
