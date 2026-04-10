from __future__ import annotations

from datetime import date

import pytest

from slopmeter.models import (
    CacheTokens,
    DailyUsage,
    ModelUsage,
    TokenTotals,
    UsageSummary,
)
from slopmeter.pricing import (
    DEFAULT_MODEL_KEY,
    PRICING_TABLE,
    compute_cost,
    compute_daily_cost,
    compute_summary_cost,
    format_cost,
    select_pricing_model,
)


def _day(breakdown_models: list[str], *, day_offset: int = 0) -> DailyUsage:
    return DailyUsage(
        date=date(2026, 1, 1 + day_offset),
        input=100,
        output=50,
        cache=CacheTokens(input=0, output=0),
        total=150,
        breakdown=[
            ModelUsage(name=name, tokens=TokenTotals(input=10, output=5, total=15))
            for name in breakdown_models
        ],
    )


def _summary(days: list[DailyUsage]) -> UsageSummary:
    return UsageSummary(provider="codex", daily=days, insights=None)


def test_select_pricing_model_both_present_prefers_claude_opus():
    summary = _summary([_day(["gpt-5.4", "claude-opus-4-6"])])
    assert select_pricing_model(summary).key == "claude-opus-4-6"


def test_select_pricing_model_only_gpt54():
    summary = _summary([_day(["gpt-5.4", "gpt-4o-mini"])])
    assert select_pricing_model(summary).key == "gpt-5.4"


def test_select_pricing_model_only_claude_opus():
    summary = _summary([_day(["claude-opus-4-6"])])
    assert select_pricing_model(summary).key == "claude-opus-4-6"


def test_select_pricing_model_neither_defaults_to_claude_opus():
    summary = _summary([_day(["gpt-4o-mini", "claude-sonnet-4-6"])])
    assert select_pricing_model(summary).key == DEFAULT_MODEL_KEY


def test_select_pricing_model_empty_summary_returns_default():
    summary = _summary([])
    assert select_pricing_model(summary).key == DEFAULT_MODEL_KEY


def test_select_pricing_model_reference_scan_spans_multiple_days():
    summary = _summary(
        [
            _day(["gpt-5.4"], day_offset=0),
            _day(["claude-opus-4-6"], day_offset=1),
        ]
    )
    assert select_pricing_model(summary).key == "claude-opus-4-6"


def test_compute_cost_manual_fixture_gpt54():
    totals = TokenTotals(
        input=1_000_000,
        output=500_000,
        cache=CacheTokens(input=200_000, output=50_000),
        total=1_500_000,
    )
    pricing = PRICING_TABLE["gpt-5.4"]
    # cached_input (cache reads) = 200_000 -> 200_000 * 0.25 / 1M = 0.05
    # uncached_input = 1_000_000 - 200_000 = 800_000 -> 800_000 * 2.50 / 1M = 2.00
    # output = 500_000 -> 500_000 * 15.00 / 1M = 7.50
    # total = 9.55
    assert compute_cost(totals, pricing) == pytest.approx(9.55, rel=1e-9)


def test_compute_cost_manual_fixture_claude_opus():
    totals = TokenTotals(
        input=2_000_000,
        output=1_000_000,
        cache=CacheTokens(input=500_000, output=0),
        total=3_000_000,
    )
    pricing = PRICING_TABLE["claude-opus-4-6"]
    # cached_input = 500_000 -> 500_000 * 0.50 / 1M = 0.25
    # uncached = 1_500_000 -> 1_500_000 * 5.00 / 1M = 7.50
    # output = 1_000_000 -> 1_000_000 * 25.00 / 1M = 25.00
    # total = 32.75
    assert compute_cost(totals, pricing) == pytest.approx(32.75, rel=1e-9)


def test_compute_cost_zero_totals_is_zero():
    totals = TokenTotals()
    assert compute_cost(totals, PRICING_TABLE["gpt-5.4"]) == 0.0


def test_compute_cost_cached_exceeding_input_clamped():
    # degenerate: cache.input larger than .input should clamp uncached to 0
    totals = TokenTotals(input=5, output=0, cache=CacheTokens(input=20), total=5)
    cost = compute_cost(totals, PRICING_TABLE["gpt-5.4"])
    # cached_input = 20 -> 20 * 0.25 / 1M = 5e-6; uncached clamped to 0; output 0
    assert cost == pytest.approx(20 * 0.25 / 1_000_000, rel=1e-9)


def test_compute_daily_cost_matches_compute_cost():
    daily = DailyUsage(
        date=date(2026, 1, 1),
        input=1_000_000,
        output=500_000,
        cache=CacheTokens(input=200_000, output=50_000),
        total=1_500_000,
        breakdown=[],
    )
    pricing = PRICING_TABLE["gpt-5.4"]
    assert compute_daily_cost(daily, pricing) == pytest.approx(9.55, rel=1e-9)


def test_compute_summary_cost_sums_over_days():
    pricing = PRICING_TABLE["gpt-5.4"]
    daily_a = DailyUsage(
        date=date(2026, 1, 1),
        input=1_000_000,
        output=0,
        cache=CacheTokens(),
        total=1_000_000,
        breakdown=[],
    )
    daily_b = DailyUsage(
        date=date(2026, 1, 2),
        input=0,
        output=1_000_000,
        cache=CacheTokens(),
        total=1_000_000,
        breakdown=[],
    )
    summary = UsageSummary(provider="codex", daily=[daily_a, daily_b], insights=None)
    # daily_a: 1M input -> 2.50; daily_b: 1M output -> 15.00; sum = 17.50
    assert compute_summary_cost(summary, pricing) == pytest.approx(17.50, rel=1e-9)


@pytest.mark.parametrize(
    "dollars,expected",
    [
        (0, "$0"),
        (-5, "$0"),
        (0.12, "$0.12"),
        (0.85, "$0.85"),
        (1, "$1"),
        (7, "$7"),
        (523, "$523"),
        (999, "$999"),
        (1_000, "$1K"),
        (1_234, "$1.23K"),
        (12_345, "$12.3K"),
        (123_456, "$123K"),
        (1_234_567, "$1.23M"),
        (1_500_000_000, "$1.5B"),
    ],
)
def test_format_cost_edges(dollars: float, expected: str):
    assert format_cost(dollars) == expected
