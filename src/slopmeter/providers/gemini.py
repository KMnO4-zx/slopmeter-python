from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path

from ..models import CacheTokens, TokenTotals, UsageSummary
from ..utils import (
    DailyTotalsByDate,
    ModelTotals,
    add_daily_token_totals,
    add_model_token_totals,
    create_usage_summary,
    get_recent_window_start,
    list_files_recursive,
    normalize_model_name,
    parse_datetime,
    read_json_document,
)

GEMINI_CONFIG_DIR_ENV = "GEMINI_CONFIG_DIR"
GEMINI_SESSION_PATH_RE = re.compile(r"[\\/]chats[\\/]session-[^\\/]+\.json$")


def get_gemini_base_dir() -> Path:
    configured_dir = os.environ.get(GEMINI_CONFIG_DIR_ENV, "").strip()
    return Path(configured_dir).expanduser().resolve() if configured_dir else Path.home() / ".gemini"


def get_gemini_session_files() -> list[Path]:
    files = list_files_recursive(get_gemini_base_dir() / "tmp", ".json")
    return [file_path for file_path in files if GEMINI_SESSION_PATH_RE.search(str(file_path))]


def is_gemini_available() -> bool:
    return (get_gemini_base_dir() / "tmp").exists()


def create_gemini_token_totals(tokens: dict[str, object]) -> TokenTotals:
    cache_input = int(tokens.get("cached", 0) or 0)
    input_tokens = int(tokens.get("input", 0) or 0) + cache_input
    output_tokens = (
        int(tokens.get("output", 0) or 0)
        + int(tokens.get("thoughts", 0) or 0)
        + int(tokens.get("tool", 0) or 0)
    )
    return TokenTotals(
        input=input_tokens,
        output=output_tokens,
        cache=CacheTokens(input=cache_input, output=0),
        total=input_tokens + output_tokens,
    )


def get_gemini_message_key(session_id: object, message: dict[str, object]) -> str:
    return json.dumps(
        {
            "sessionId": session_id,
            "messageId": message.get("id"),
            "timestamp": message.get("timestamp"),
            "model": message.get("model"),
            "tokens": message.get("tokens"),
        },
        sort_keys=True,
    )


def parse_gemini_session(file_path: Path) -> dict[str, object]:
    return read_json_document(
        file_path,
        oversized_error_message=lambda *, file_path, max_bytes, env_var_name: (
            f"Gemini session JSON document exceeds {max_bytes} bytes in {file_path}. "
            f"Increase {env_var_name} to process this file."
        ),
    )


def load_gemini_rows(start: datetime, end: datetime) -> UsageSummary:
    files = get_gemini_session_files()
    totals: DailyTotalsByDate = {}
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}
    recent_start = get_recent_window_start(end, 30)
    dedupe: set[str] = set()

    for file_path in files:
        session = parse_gemini_session(file_path)
        for message in session.get("messages", []) or []:
            if not isinstance(message, dict):
                continue
            if message.get("type") != "gemini" or not isinstance(message.get("tokens"), dict):
                continue

            record_date = parse_datetime(message.get("timestamp"))
            if record_date is None or record_date < start or record_date > end:
                continue

            token_totals = create_gemini_token_totals(message["tokens"])
            if token_totals.total <= 0:
                continue

            message_key = get_gemini_message_key(session.get("sessionId"), message)
            if message_key in dedupe:
                continue
            dedupe.add(message_key)

            model_name = (
                normalize_model_name(str(message.get("model")))
                if str(message.get("model", "")).strip()
                else None
            )
            add_daily_token_totals(totals, record_date, token_totals, model_name)
            if not model_name:
                continue

            add_model_token_totals(model_totals, model_name, token_totals)
            if record_date >= recent_start:
                add_model_token_totals(recent_model_totals, model_name, token_totals)

    return create_usage_summary("gemini", totals, model_totals, recent_model_totals, end)

