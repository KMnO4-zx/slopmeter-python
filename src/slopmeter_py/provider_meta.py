from __future__ import annotations

from .models import ProviderId

PROVIDER_IDS: list[ProviderId] = [
    "amp",
    "claude",
    "codex",
    "cursor",
    "gemini",
    "opencode",
    "pi",
]

DEFAULT_PROVIDER_IDS: list[ProviderId] = ["claude", "codex", "cursor"]

PROVIDER_STATUS_LABEL: dict[ProviderId, str] = {
    "amp": "Amp",
    "claude": "Claude code",
    "codex": "Codex",
    "cursor": "Cursor",
    "gemini": "Gemini CLI",
    "opencode": "Open Code",
    "pi": "Pi Coding Agent",
}

