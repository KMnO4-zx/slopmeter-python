from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import DailyUsage, Insights, JsonProviderSummary, ModelUsage, TokenTotals, UsageSummary
from .utils import format_local_date

JSON_EXPORT_VERSION = "2026-03-13"


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


def daily_usage_to_dict(value: DailyUsage) -> dict[str, Any]:
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
    return JsonProviderSummary(
        provider=summary.provider,
        id=summary.provider,
        title=title,
        colors=colors,
        daily=[daily_usage_to_dict(row) for row in summary.daily],
        insights=insights_to_dict(summary.insights),
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
            }
            for provider in providers
        ],
    }

