from __future__ import annotations

from dataclasses import dataclass

from .models import ProviderId

OutputFormat = str


@dataclass
class ProviderSelectionValues:
    all: bool = False
    amp: bool = False
    claude: bool = False
    codex: bool = False
    cursor: bool = False
    gemini: bool = False
    opencode: bool = False
    pi: bool = False


OUTPUT_PROVIDER_IDS: list[ProviderId] = [
    "amp",
    "claude",
    "codex",
    "cursor",
    "gemini",
    "opencode",
    "pi",
]


def get_requested_providers_for_output(values: ProviderSelectionValues) -> list[ProviderId]:
    return [provider for provider in OUTPUT_PROVIDER_IDS if getattr(values, provider)]


def get_default_output_suffix(values: ProviderSelectionValues) -> str:
    if values.all:
        return "_all"

    requested_providers = get_requested_providers_for_output(values)
    if not requested_providers:
        return ""

    return f"_{'_'.join(requested_providers)}"


def get_default_output_path(values: ProviderSelectionValues, fmt: OutputFormat) -> str:
    return f"./heatmap-last-year{get_default_output_suffix(values)}.{fmt}"

