from __future__ import annotations

from .models import ProviderId, UsageProviderId

PROVIDER_IDS: list[ProviderId] = [
    "amp",
    "claude",
    "codex",
    "cursor",
    "gemini",
    "opencode",
    "pi",
]

ORDERABLE_PROVIDER_IDS: list[UsageProviderId] = ["all", *PROVIDER_IDS]
DEFAULT_PROVIDER_IDS: list[ProviderId] = ["claude", "codex", "cursor"]
SERVICE_DEFAULT_PROVIDER_IDS: list[ProviderId] = [
    "claude",
    "codex",
    "opencode",
    "cursor",
    "amp",
    "gemini",
    "pi",
]

PROVIDER_STATUS_LABEL: dict[UsageProviderId, str] = {
    "all": "All providers",
    "amp": "Amp",
    "claude": "Claude code",
    "codex": "Codex",
    "cursor": "Cursor",
    "gemini": "Gemini CLI",
    "opencode": "Open Code",
    "pi": "Pi Coding Agent",
}
