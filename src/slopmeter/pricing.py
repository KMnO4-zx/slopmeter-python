from __future__ import annotations

import re
from dataclasses import dataclass

from .model_prices import MODEL_PRICE_ALIASES, MODEL_PRICES, convert_price_to_usd
from .models import DailyUsage, ModelUsage, TokenTotals, UsageSummary


@dataclass(frozen=True)
class ModelPricing:
    key: str
    display_name: str
    input_per_million: float
    cached_input_per_million: float
    cache_write_per_million: float
    output_per_million: float


ACTUAL_MODEL_PRICES_KEY = "actual-model-prices"
KNOWN_MODEL_PRICES_KEY = "known-model-prices"
UNPRICED_MODELS_KEY = "unpriced-models"
DEFAULT_MODEL_KEY = UNPRICED_MODELS_KEY


def create_model_pricing(key: str, entry: dict[str, object]) -> ModelPricing:
    source_currency = str(entry.get("source_currency") or "USD")
    input_per_million = convert_price_to_usd(float(entry["input_per_million"]), source_currency)
    return ModelPricing(
        key=key,
        display_name=str(entry.get("display_name") or key),
        input_per_million=input_per_million,
        cached_input_per_million=convert_price_to_usd(
            float(entry.get("cached_input_per_million", entry["input_per_million"])),
            source_currency,
        ),
        cache_write_per_million=convert_price_to_usd(
            float(entry.get("cache_write_per_million", entry["input_per_million"])),
            source_currency,
        ),
        output_per_million=convert_price_to_usd(float(entry["output_per_million"]), source_currency),
    )


PRICING_TABLE: dict[str, ModelPricing] = {
    key: create_model_pricing(key, entry)
    for key, entry in MODEL_PRICES.items()
}
ACTUAL_MODEL_PRICES = ModelPricing(
    key=ACTUAL_MODEL_PRICES_KEY,
    display_name="actual model prices",
    input_per_million=0,
    cached_input_per_million=0,
    cache_write_per_million=0,
    output_per_million=0,
)
KNOWN_MODEL_PRICES = ModelPricing(
    key=KNOWN_MODEL_PRICES_KEY,
    display_name="known model prices",
    input_per_million=0,
    cached_input_per_million=0,
    cache_write_per_million=0,
    output_per_million=0,
)
UNPRICED_MODELS = ModelPricing(
    key=UNPRICED_MODELS_KEY,
    display_name="unpriced models",
    input_per_million=0,
    cached_input_per_million=0,
    cache_write_per_million=0,
    output_per_million=0,
)


def normalize_pricing_key(model_name: str) -> str:
    value = model_name.strip().lower()
    value = re.sub(r"-(?:\d{8}|\d{4}-\d{2}-\d{2})$", "", value)
    return MODEL_PRICE_ALIASES.get(value, value)


def get_model_pricing(model_name: str) -> ModelPricing | None:
    return PRICING_TABLE.get(normalize_pricing_key(model_name))


def compute_cost(totals: TokenTotals, pricing: ModelPricing) -> float:
    """Return the USD cost for a TokenTotals bucket.

    ``totals.input`` includes ordinary input, cache reads, and cache writes.
    We split as:

        cached_input_tokens   = totals.cache.input
        cache_write_tokens    = totals.cache.output
        uncached_input_tokens = totals.input - cached_input_tokens - cache_write_tokens
    """
    cached_input = max(totals.cache.input, 0)
    cache_write = max(totals.cache.output, 0)
    uncached_input = max(totals.input - cached_input - cache_write, 0)
    output = max(totals.output, 0)
    return (
        uncached_input * pricing.input_per_million
        + cached_input * pricing.cached_input_per_million
        + cache_write * pricing.cache_write_per_million
        + output * pricing.output_per_million
    ) / 1_000_000


def compute_model_usage_cost(model_usage: ModelUsage) -> float:
    pricing = get_model_pricing(model_usage.name)
    if pricing is None:
        return 0.0
    return compute_cost(model_usage.tokens, pricing)


def compute_daily_cost(daily: DailyUsage, pricing: ModelPricing | None = None) -> float:
    if pricing is None:
        return sum(compute_model_usage_cost(item) for item in daily.breakdown)

    totals = TokenTotals(
        input=daily.input,
        output=daily.output,
        cache=daily.cache,
        total=daily.total,
    )
    return compute_cost(totals, pricing)


def compute_summary_cost(summary: UsageSummary, pricing: ModelPricing | None = None) -> float:
    return sum(compute_daily_cost(row, pricing) for row in summary.daily)


def select_pricing_model(summary: UsageSummary) -> ModelPricing:
    priced: dict[str, ModelPricing] = {}
    has_unpriced = False
    for row in summary.daily:
        for item in row.breakdown:
            pricing = get_model_pricing(item.name)
            if pricing is None:
                has_unpriced = True
                continue
            priced[pricing.key] = pricing

    if not priced:
        return UNPRICED_MODELS
    if has_unpriced:
        return KNOWN_MODEL_PRICES
    if len(priced) == 1 and not has_unpriced:
        return next(iter(priced.values()))
    return ACTUAL_MODEL_PRICES


def format_cost(dollars: float) -> str:
    """Compact USD formatter.

    Examples: ``$0``, ``$0.12``, ``$7``, ``$523``, ``$1.2K``, ``$12.3K``,
    ``$3.4M``. Mirrors ``format_token_total`` in ``render.py`` for the
    >=1000 thresholds, but keeps cents precision below $1 so tooltips
    don't collapse small per-day amounts to ``$0``.
    """
    if dollars <= 0:
        return "$0"
    units = (
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "K"),
    )
    for size, suffix in units:
        if dollars >= size:
            scaled = dollars / size
            precision = 0 if scaled >= 100 else 1 if scaled >= 10 else 2
            compact = f"{scaled:.{precision}f}".rstrip("0").rstrip(".")
            return f"${compact}{suffix}"
    if dollars >= 1:
        return f"${int(round(dollars))}"
    return f"${dollars:.2f}"
