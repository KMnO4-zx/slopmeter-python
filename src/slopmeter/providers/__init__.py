from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..models import ProviderId, UsageSummary
from ..provider_meta import DEFAULT_PROVIDER_IDS, PROVIDER_IDS, PROVIDER_STATUS_LABEL
from ..utils import has_usage, merge_usage_summaries, run_with_concurrency
from .amp import is_amp_available, load_amp_rows
from .claude import is_claude_available, load_claude_rows
from .codex import is_codex_available, load_codex_rows
from .cursor import is_cursor_available, load_cursor_rows
from .gemini import is_gemini_available, load_gemini_rows
from .open_code import is_open_code_available, load_open_code_rows
from .pi import is_pi_available, load_pi_rows


@dataclass
class AggregateUsageResult:
    rows_by_provider: dict[ProviderId, UsageSummary | None]
    warnings: list[str]


ProviderAvailability = dict[ProviderId, bool]


def create_empty_provider_availability() -> ProviderAvailability:
    return {
        "amp": False,
        "claude": False,
        "codex": False,
        "cursor": False,
        "gemini": False,
        "opencode": False,
        "pi": False,
    }


def is_provider_available(provider: ProviderId) -> bool:
    if provider == "amp":
        return is_amp_available()
    if provider == "claude":
        return is_claude_available()
    if provider == "codex":
        return is_codex_available()
    if provider == "cursor":
        return is_cursor_available()
    if provider == "gemini":
        return is_gemini_available()
    if provider == "opencode":
        return is_open_code_available()
    if provider == "pi":
        return is_pi_available()
    raise ValueError(f"Unhandled provider: {provider}")


def get_provider_availability(providers: list[ProviderId] | None = None) -> ProviderAvailability:
    providers = providers or PROVIDER_IDS
    availability = create_empty_provider_availability()
    for provider in providers:
        availability[provider] = is_provider_available(provider)
    return availability


def merge_provider_usage(rows_by_provider: dict[ProviderId, UsageSummary | None], end: datetime) -> UsageSummary | None:
    summaries = [
        rows_by_provider[provider]
        for provider in PROVIDER_IDS
        if rows_by_provider.get(provider) is not None
    ]
    if not summaries:
        return None
    return merge_usage_summaries("all", summaries, end)


def load_provider_usage(
    provider: ProviderId,
    *,
    start: datetime,
    end: datetime,
) -> tuple[ProviderId, UsageSummary | None, list[str]]:
    warnings: list[str] = []

    if provider == "amp":
        summary = load_amp_rows(start, end)
    elif provider == "claude":
        summary = load_claude_rows(start, end)
    elif provider == "codex":
        summary = load_codex_rows(start, end, warnings)
    elif provider == "cursor":
        summary = load_cursor_rows(start, end)
    elif provider == "gemini":
        summary = load_gemini_rows(start, end)
    elif provider == "opencode":
        summary = load_open_code_rows(start, end)
    elif provider == "pi":
        summary = load_pi_rows(start, end)
    else:
        raise ValueError(f"Unhandled provider: {provider}")

    return provider, (summary if has_usage(summary) else None), warnings


def aggregate_usage(
    *,
    start: datetime,
    end: datetime,
    requested_providers: list[ProviderId] | None = None,
) -> AggregateUsageResult:
    providers_to_load = requested_providers or PROVIDER_IDS
    rows_by_provider: dict[ProviderId, UsageSummary | None] = {
        "amp": None,
        "claude": None,
        "codex": None,
        "cursor": None,
        "gemini": None,
        "opencode": None,
        "pi": None,
    }
    results = run_with_concurrency(
        providers_to_load,
        len(providers_to_load),
        lambda provider, _: load_provider_usage(provider, start=start, end=end),
    )
    warnings: list[str] = []

    for provider, summary, provider_warnings in results:
        rows_by_provider[provider] = summary
        warnings.extend(provider_warnings)

    return AggregateUsageResult(rows_by_provider=rows_by_provider, warnings=warnings)


__all__ = [
    "AggregateUsageResult",
    "DEFAULT_PROVIDER_IDS",
    "PROVIDER_IDS",
    "PROVIDER_STATUS_LABEL",
    "ProviderAvailability",
    "ProviderId",
    "aggregate_usage",
    "get_provider_availability",
    "is_provider_available",
    "merge_provider_usage",
]
