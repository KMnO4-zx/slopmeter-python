from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import DailyUsage, Insights, JsonProviderSummary, ModelUsage, TokenTotals, UsageSummary
from .pricing import (
    ModelPricing,
    compute_daily_cost,
    compute_summary_cost,
    format_cost,
    select_pricing_model,
)
from .utils import format_local_date

JSON_EXPORT_VERSION = "2026-04-10"


def token_totals_to_dict(value: TokenTotals) -> dict[str, Any]:
    return {
        "input": value.input,
        "output": value.output,
        "cache": {
            "input": value.cache.input,
            "output": value.cache.output,
        },
        "total": value.total,
    }


def model_usage_to_dict(value: ModelUsage) -> dict[str, Any]:
    return {
        "name": value.name,
        "tokens": token_totals_to_dict(value.tokens),
    }


def insights_to_dict(value: Insights | None) -> dict[str, Any] | None:
    if value is None:
        return None

    return {
        "mostUsedModel": model_usage_to_dict(value.most_used_model) if value.most_used_model else None,
        "recentMostUsedModel": (
            model_usage_to_dict(value.recent_most_used_model)
            if value.recent_most_used_model
            else None
        ),
        "streaks": {
            "longest": value.streaks.longest,
            "current": value.streaks.current,
        },
    }


def daily_usage_to_dict(value: DailyUsage, *, pricing: ModelPricing) -> dict[str, Any]:
    payload = {
        "date": format_local_date(value.date),
        "input": value.input,
        "output": value.output,
        "cache": {
            "input": value.cache.input,
            "output": value.cache.output,
        },
        "total": value.total,
        "breakdown": [model_usage_to_dict(item) for item in value.breakdown],
        "costUsd": round(compute_daily_cost(value, pricing), 4),
    }
    if value.display_value is not None:
        payload["displayValue"] = value.display_value
    return payload


def to_json_provider_summary(
    summary: UsageSummary,
    *,
    title: str,
    colors: list[str],
) -> JsonProviderSummary:
    pricing = select_pricing_model(summary)
    total_cost = compute_summary_cost(summary, pricing)
    return JsonProviderSummary(
        provider=summary.provider,
        id=summary.provider,
        title=title,
        colors=colors,
        daily=[daily_usage_to_dict(row, pricing=pricing) for row in summary.daily],
        insights=insights_to_dict(summary.insights),
        pricing_model=pricing.display_name,
        pricing_model_key=pricing.key,
        total_cost_usd=round(total_cost, 4),
        total_cost_label=format_cost(total_cost) if total_cost > 0 else "",
    )


def build_json_export(
    *,
    start: datetime,
    end: datetime,
    color_mode: str,
    providers: list[JsonProviderSummary],
) -> dict[str, Any]:
    return {
        "version": JSON_EXPORT_VERSION,
        "start": format_local_date(start),
        "end": format_local_date(end),
        "colorMode": color_mode,
        "providers": [
            {
                "provider": provider.provider,
                "id": provider.id,
                "title": provider.title,
                "colors": provider.colors,
                "daily": provider.daily,
                "insights": provider.insights,
                "pricingModel": provider.pricing_model,
                "pricingModelKey": provider.pricing_model_key,
                "totalCostUsd": provider.total_cost_usd,
                "totalCostLabel": provider.total_cost_label,
            }
            for provider in providers
        ],
    }

