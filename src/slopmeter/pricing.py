from __future__ import annotations

from dataclasses import dataclass

from .models import DailyUsage, TokenTotals, UsageSummary


@dataclass(frozen=True)
class ModelPricing:
    key: str
    display_name: str
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float


PRICING_TABLE: dict[str, ModelPricing] = {
    "gpt-5.4": ModelPricing(
        key="gpt-5.4",
        display_name="gpt-5.4",
        input_per_million=2.50,
        cached_input_per_million=0.25,
        output_per_million=15.00,
    ),
    "claude-opus-4-6": ModelPricing(
        key="claude-opus-4-6",
        display_name="claude-opus-4-6",
        input_per_million=5.00,
        cached_input_per_million=0.50,
        output_per_million=25.00,
    ),
}

DEFAULT_MODEL_KEY = "claude-opus-4-6"
REFERENCE_MODEL_PRIORITY: tuple[str, ...] = ("claude-opus-4-6", "gpt-5.4")


def select_pricing_model(summary: UsageSummary) -> ModelPricing:
    """Pick the reference model to price a provider card with.

    Rules:
      - Both reference models present in the breakdown -> claude-opus-4-6.
      - Exactly one present -> that one.
      - Neither present -> DEFAULT_MODEL_KEY (claude-opus-4-6).
    """
    present = {
        item.name
        for row in summary.daily
        for item in row.breakdown
        if item.name in PRICING_TABLE
    }
    for key in REFERENCE_MODEL_PRIORITY:
        if key in present:
            return PRICING_TABLE[key]
    return PRICING_TABLE[DEFAULT_MODEL_KEY]


def compute_cost(totals: TokenTotals, pricing: ModelPricing) -> float:
    """Return the USD cost for a TokenTotals bucket.

    Semantics reconciled with models.py and the cursor CSV fixture
    (tests/test_cli.py::test_cursor_csv_summary_reconstructs_cache_split):
    ``totals.input`` already includes ``cache.input`` (cache reads) and
    ``cache.output`` (cache writes). We split as:

        cached_input_tokens   = totals.cache.input
        uncached_input_tokens = totals.input - totals.cache.input

    Cache writes stay folded into the uncached bucket and are charged at
    the standard input rate, which matches the user's 3-tier pricing
    table (no separate cache-write rate).
    """
    cached_input = max(totals.cache.input, 0)
    uncached_input = max(totals.input - cached_input, 0)
    output = max(totals.output, 0)
    return (
        uncached_input * pricing.input_per_million
        + cached_input * pricing.cached_input_per_million
        + output * pricing.output_per_million
    ) / 1_000_000


def compute_daily_cost(daily: DailyUsage, pricing: ModelPricing) -> float:
    totals = TokenTotals(
        input=daily.input,
        output=daily.output,
        cache=daily.cache,
        total=daily.total,
    )
    return compute_cost(totals, pricing)


def compute_summary_cost(summary: UsageSummary, pricing: ModelPricing) -> float:
    return sum(compute_daily_cost(row, pricing) for row in summary.daily)


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
