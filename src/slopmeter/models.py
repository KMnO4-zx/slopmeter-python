from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

ProviderId = Literal["amp", "claude", "codex", "cursor", "gemini", "opencode", "pi"]
UsageProviderId = Literal[
    "amp",
    "claude",
    "codex",
    "cursor",
    "gemini",
    "opencode",
    "pi",
    "all",
]
ColorMode = Literal["light", "dark"]


@dataclass
class CacheTokens:
    input: int = 0
    output: int = 0


@dataclass
class TokenTotals:
    input: int = 0
    output: int = 0
    cache: CacheTokens = field(default_factory=CacheTokens)
    total: int = 0


@dataclass
class ModelUsage:
    name: str
    tokens: TokenTotals


@dataclass
class DailyUsage:
    date: date
    input: int
    output: int
    cache: CacheTokens
    total: int
    breakdown: list[ModelUsage]
    display_value: int | None = None


@dataclass
class Streaks:
    longest: int
    current: int


@dataclass
class Insights:
    streaks: Streaks
    most_used_model: ModelUsage | None = None
    recent_most_used_model: ModelUsage | None = None


@dataclass
class UsageSummary:
    provider: UsageProviderId
    daily: list[DailyUsage]
    insights: Insights | None = None


@dataclass
class JsonProviderSummary:
    provider: UsageProviderId
    id: UsageProviderId
    title: str
    colors: list[str]
    daily: list[dict[str, object]]
    insights: dict[str, object] | None


@dataclass
class JsonExportPayload:
    version: str
    start: str
    end: str
    providers: list[JsonProviderSummary]
    color_mode: ColorMode
