from __future__ import annotations

from datetime import datetime, timezone

from .models import ColorMode, UsageSummary
from .provider_meta import ORDERABLE_PROVIDER_IDS, PROVIDER_IDS
from .render import HEATMAP_THEMES
from .utils import format_local_date


BUNDLE_FORMAT_VERSION = "2026-04-10"
BUNDLE_KIND = "slopmeter-bundle"


def format_timestamp(value: datetime) -> str:
    localized = value.astimezone()
    return localized.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def create_day_payload(day: dict[str, object]) -> dict[str, object]:
    return day


def build_provider_days(summary: UsageSummary) -> list[dict[str, object]]:
    days: list[dict[str, object]] = []
    for row in summary.daily:
        payload: dict[str, object] = {
            "date": format_local_date(row.date),
            "input": row.input,
            "output": row.output,
            "cache": {
                "input": row.cache.input,
                "output": row.cache.output,
            },
            "total": row.total,
            "breakdown": [
                {
                    "name": item.name,
                    "tokens": {
                        "input": item.tokens.input,
                        "output": item.tokens.output,
                        "cache": {
                            "input": item.tokens.cache.input,
                            "output": item.tokens.cache.output,
                        },
                        "total": item.tokens.total,
                    },
                }
                for item in row.breakdown
            ],
        }
        if row.display_value is not None:
            payload["displayValue"] = row.display_value
        days.append(payload)
    return days


def build_device_source(
    device_metadata: dict[str, str],
    provider_summaries: list[UsageSummary],
    *,
    generated_at: datetime,
) -> dict[str, object]:
    return {
        "device": {
            "id": device_metadata["id"],
            "name": device_metadata["name"],
            "platform": device_metadata["platform"],
            "generatedAt": format_timestamp(generated_at),
            "timeZone": device_metadata["timeZone"],
        },
        "providers": [
            {
                "id": summary.provider,
                "days": build_provider_days(summary),
            }
            for summary in provider_summaries
            if summary.provider in PROVIDER_IDS
        ],
    }


def build_bundle_payload(
    *,
    start: datetime,
    end: datetime,
    sources: list[dict[str, object]],
    generated_at: datetime | None = None,
) -> dict[str, object]:
    created_at = generated_at or datetime.now(timezone.utc)
    return {
        "version": BUNDLE_FORMAT_VERSION,
        "kind": BUNDLE_KIND,
        "generatedAt": format_timestamp(created_at),
        "window": {
            "start": format_local_date(start),
            "end": format_local_date(end),
        },
        "sources": sources,
    }


def build_theme_payload(color_mode: ColorMode) -> dict[str, dict[str, object]]:
    return {
        provider_id: {
            "title": theme.title,
            "titleCaption": theme.title_caption,
            "colors": theme.colors[color_mode],
        }
        for provider_id, theme in HEATMAP_THEMES.items()
        if provider_id in ORDERABLE_PROVIDER_IDS
    }
