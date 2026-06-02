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
from slopmeter.model_prices import (
    EXCHANGE_RATES,
    MODEL_PRICES,
    PROVIDER_MODEL_PRICE_TABLES,
    USD_PER_CNY,
)
from slopmeter.pricing import (
    ACTUAL_MODEL_PRICES_KEY,
    DEFAULT_MODEL_KEY,
    KNOWN_MODEL_PRICES_KEY,
    PRICING_TABLE,
    compute_cost,
    compute_daily_cost,
    compute_model_usage_cost,
    compute_summary_cost,
    format_cost,
    get_model_pricing,
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


def test_select_pricing_model_both_present_uses_actual_model_prices():
    summary = _summary([_day(["gpt-5.4", "claude-opus-4-6"])])
    assert select_pricing_model(summary).key == ACTUAL_MODEL_PRICES_KEY


def test_select_pricing_model_only_gpt54():
    summary = _summary([_day(["gpt-5.4"])])
    assert select_pricing_model(summary).key == "gpt-5.4"


def test_select_pricing_model_known_and_unknown_is_partial():
    summary = _summary([_day(["gpt-5.4", "gpt-4o-mini"])])
    assert select_pricing_model(summary).key == KNOWN_MODEL_PRICES_KEY


def test_select_pricing_model_only_claude_opus():
    summary = _summary([_day(["claude-opus-4-6"])])
    assert select_pricing_model(summary).key == "claude-opus-4-6"


def test_select_pricing_model_unknown_only_is_unpriced():
    summary = _summary([_day(["gpt-4o-mini"])])
    assert select_pricing_model(summary).key == DEFAULT_MODEL_KEY


def test_select_pricing_model_empty_summary_returns_default():
    summary = _summary([])
    assert select_pricing_model(summary).key == DEFAULT_MODEL_KEY


def test_select_pricing_model_multiple_priced_models_spans_days():
    summary = _summary(
        [
            _day(["gpt-5.4"], day_offset=0),
            _day(["claude-opus-4-6"], day_offset=1),
        ]
    )
    assert select_pricing_model(summary).key == ACTUAL_MODEL_PRICES_KEY


def test_get_model_pricing_normalizes_dated_model_ids():
    assert get_model_pricing("gpt-5.4-2026-04-01").key == "gpt-5.4"
    assert get_model_pricing("claude-sonnet-4-6-20260401").key == "claude-sonnet-4-6"


def test_provider_price_tables_are_merged():
    assert "openai" in PROVIDER_MODEL_PRICE_TABLES
    assert "deepseek" in PROVIDER_MODEL_PRICE_TABLES
    assert MODEL_PRICES["gpt-5.4"] is PROVIDER_MODEL_PRICE_TABLES["openai"]["gpt-5.4"]
    assert MODEL_PRICES["deepseek-v4-pro"] is PROVIDER_MODEL_PRICE_TABLES["deepseek"]["deepseek-v4-pro"]


def test_provider_price_tables_are_valid():
    expected_provider_ids = {
        "openai": "openai",
        "anthropic": "anthropic",
        "deepseek": "deepseek",
        "minimax": "minimax",
        "mimo": "xiaomi-mimo",
        "glm": "zai-glm",
        "stepfun": "stepfun",
        "gemini": "google-gemini",
        "qwen": "qwen",
        "kimi": "moonshot-kimi",
    }
    required_price_fields = (
        "input_per_million",
        "cached_input_per_million",
        "cache_write_per_million",
        "output_per_million",
    )

    assert set(PROVIDER_MODEL_PRICE_TABLES) == set(expected_provider_ids)
    assert sum(len(prices) for prices in PROVIDER_MODEL_PRICE_TABLES.values()) == len(MODEL_PRICES)
    for group, prices in PROVIDER_MODEL_PRICE_TABLES.items():
        for model_key, entry in prices.items():
            assert entry["provider"] == expected_provider_ids[group]
            assert entry["source_currency"] == "USD" or entry["source_currency"] in EXCHANGE_RATES
            assert entry.get("display_name")
            assert entry.get("source")
            for field in required_price_fields:
                assert isinstance(entry.get(field), (int, float)), (model_key, field)
                assert entry[field] >= 0, (model_key, field)


def test_china_provider_catalog_prices_are_cny():
    china_provider_groups = {
        "deepseek",
        "minimax",
        "mimo",
        "glm",
        "stepfun",
        "qwen",
        "kimi",
    }

    for group in china_provider_groups:
        for model_key, entry in PROVIDER_MODEL_PRICE_TABLES[group].items():
            assert entry["source_currency"] == "CNY", (group, model_key)


def test_deepseek_v4_pro_pricing_is_available():
    raw_price = MODEL_PRICES["deepseek-v4-pro"]
    assert raw_price["source_currency"] == "CNY"
    assert raw_price["input_per_million"] == pytest.approx(3.00)
    assert raw_price["cached_input_per_million"] == pytest.approx(0.025)
    assert raw_price["output_per_million"] == pytest.approx(6.00)

    pricing = get_model_pricing("deepseek-v4-pro")
    assert pricing is not None
    assert pricing.input_per_million == pytest.approx(3.00 * USD_PER_CNY)
    assert pricing.cached_input_per_million == pytest.approx(0.025 * USD_PER_CNY)
    assert pricing.output_per_million == pytest.approx(6.00 * USD_PER_CNY)


def test_cny_catalog_prices_are_converted_to_usd_for_pricing():
    raw_price = MODEL_PRICES["mimo-v2.5"]
    assert raw_price["source_currency"] == "CNY"
    assert raw_price["input_per_million"] == pytest.approx(1.00)
    assert raw_price["output_per_million"] == pytest.approx(2.00)

    pricing = PRICING_TABLE["mimo-v2.5"]
    assert pricing.input_per_million == pytest.approx(1.00 * USD_PER_CNY)
    assert pricing.cached_input_per_million == pytest.approx(0.02 * USD_PER_CNY)
    assert pricing.output_per_million == pytest.approx(2.00 * USD_PER_CNY)


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
        cache=CacheTokens(input=500_000, output=250_000),
        total=3_000_000,
    )
    pricing = PRICING_TABLE["claude-opus-4-6"]
    # cached_input = 500_000 -> 500_000 * 0.50 / 1M = 0.25
    # cache_write = 250_000 -> 250_000 * 6.25 / 1M = 1.5625
    # uncached = 1_250_000 -> 1_250_000 * 5.00 / 1M = 6.25
    # output = 1_000_000 -> 1_000_000 * 25.00 / 1M = 25.00
    # total = 33.0625
    assert compute_cost(totals, pricing) == pytest.approx(33.0625, rel=1e-9)


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


def test_compute_model_usage_cost_uses_model_specific_pricing():
    usage = ModelUsage(
        name="deepseek-chat",
        tokens=TokenTotals(
            input=1_000_000,
            output=500_000,
            cache=CacheTokens(input=200_000),
            total=1_500_000,
        ),
    )
    # deepseek-chat is a compatibility name for deepseek-v4-flash.
    # CNY before conversion:
    # uncached input 800k * 1 + cache read 200k * 0.02 + output 500k * 2 = 1.804 CNY
    assert compute_model_usage_cost(usage) == pytest.approx(1.804 * USD_PER_CNY, rel=1e-9)


def test_compute_summary_cost_sums_actual_model_breakdown_prices():
    daily = DailyUsage(
        date=date(2026, 1, 1),
        input=2_000_000,
        output=1_000_000,
        cache=CacheTokens(),
        total=3_000_000,
        breakdown=[
            ModelUsage(
                name="gpt-5.4",
                tokens=TokenTotals(input=1_000_000, output=500_000, total=1_500_000),
            ),
            ModelUsage(
                name="claude-sonnet-4-6",
                tokens=TokenTotals(input=1_000_000, output=500_000, total=1_500_000),
            ),
        ],
    )
    summary = UsageSummary(provider="codex", daily=[daily], insights=None)
    # gpt-5.4: 2.50 + 7.50; claude-sonnet-4-6: 3.00 + 7.50
    assert compute_summary_cost(summary) == pytest.approx(20.50, rel=1e-9)


def test_compute_summary_cost_does_not_price_unknown_models_as_default():
    daily = DailyUsage(
        date=date(2026, 1, 1),
        input=1_000_000,
        output=1_000_000,
        cache=CacheTokens(),
        total=2_000_000,
        breakdown=[
            ModelUsage(
                name="not-in-price-catalog",
                tokens=TokenTotals(input=1_000_000, output=1_000_000, total=2_000_000),
            )
        ],
    )
    summary = UsageSummary(provider="codex", daily=[daily], insights=None)
    assert compute_summary_cost(summary) == 0.0


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
