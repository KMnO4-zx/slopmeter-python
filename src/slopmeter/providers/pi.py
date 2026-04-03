from __future__ import annotations

import os
import re
from datetime import datetime
from pathlib import Path

from ..models import CacheTokens, TokenTotals, UsageSummary
from ..utils import (
    DailyTotalsByDate,
    ModelTotals,
    DEFAULT_MAX_JSONL_RECORD_BYTES,
    MAX_JSONL_RECORD_BYTES_ENV,
    JsonlRecordDecision,
    add_daily_token_totals,
    add_model_token_totals,
    create_usage_summary,
    get_positive_integer_env,
    get_recent_window_start,
    list_files_recursive,
    normalize_model_name,
    parse_datetime,
    read_jsonl_records,
)

PI_AGENT_DIR_ENV = "PI_CODING_AGENT_DIR"
CLASSIFICATION_PREFIX_BYTES = 16 * 1024


def get_pi_agent_dir() -> Path:
    configured_agent_dir = os.environ.get(PI_AGENT_DIR_ENV, "").strip()
    return Path(configured_agent_dir).expanduser().resolve() if configured_agent_dir else Path.home() / ".pi" / "agent"


def get_pi_session_files() -> list[Path]:
    return list_files_recursive(get_pi_agent_dir() / "sessions", ".jsonl")


def is_pi_available() -> bool:
    return (get_pi_agent_dir() / "sessions").exists()


def classify_pi_record(prefix: str) -> JsonlRecordDecision:
    if re.search(r'"type"\s*:\s*"message"', prefix) and re.search(r'"role"\s*:\s*"assistant"', prefix):
        return JsonlRecordDecision(kind="keep")
    return JsonlRecordDecision(kind="skip")


def as_non_empty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def create_pi_token_totals(usage: dict[str, object]) -> TokenTotals:
    cache_read = int(usage.get("cacheRead", 0) or 0)
    cache_write = int(usage.get("cacheWrite", 0) or 0)
    input_tokens = int(usage.get("input", 0) or 0) + cache_read
    output_tokens = int(usage.get("output", 0) or 0) + cache_write
    total_tokens = int(usage.get("totalTokens", 0) or 0) or input_tokens + output_tokens
    return TokenTotals(
        input=input_tokens,
        output=output_tokens,
        cache=CacheTokens(input=cache_read, output=cache_write),
        total=total_tokens,
    )


def get_pi_timestamp(entry: dict[str, object]) -> datetime | None:
    message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
    return parse_datetime(entry.get("timestamp") or message.get("timestamp"))


def load_pi_rows(start: datetime, end: datetime) -> UsageSummary:
    files = get_pi_session_files()
    totals: DailyTotalsByDate = {}
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}
    recent_start = get_recent_window_start(end, 30)
    max_record_bytes = get_positive_integer_env(
        MAX_JSONL_RECORD_BYTES_ENV,
        DEFAULT_MAX_JSONL_RECORD_BYTES,
    )

    for file_path in files:
        for record in read_jsonl_records(
            file_path,
            classification_prefix_bytes=CLASSIFICATION_PREFIX_BYTES,
            classify=classify_pi_record,
            max_record_bytes=max_record_bytes,
            oversized_error_message=lambda *, file_path, line_number, max_record_bytes, env_var_name: (
                f"Relevant Pi Coding Agent record exceeds {max_record_bytes} bytes in "
                f"{file_path}:{line_number}. Increase {env_var_name} to process this file."
            ),
        ):
            try:
                entry = __import__("json").loads(record.raw_line)
            except Exception:
                continue

            message = entry.get("message")
            if entry.get("type") != "message" or not isinstance(message, dict) or message.get("role") != "assistant":
                continue

            usage = message.get("usage")
            if not isinstance(usage, dict):
                continue

            timestamp = get_pi_timestamp(entry)
            if timestamp is None or timestamp < start or timestamp > end:
                continue

            token_totals = create_pi_token_totals(usage)
            if token_totals.total <= 0:
                continue

            model_name = as_non_empty_string(message.get("model"))
            normalized_model_name = normalize_model_name(model_name) if model_name else None
            add_daily_token_totals(totals, timestamp, token_totals, normalized_model_name)
            if not normalized_model_name:
                continue

            add_model_token_totals(model_totals, normalized_model_name, token_totals)
            if timestamp >= recent_start:
                add_model_token_totals(recent_model_totals, normalized_model_name, token_totals)

    return create_usage_summary("pi", totals, model_totals, recent_model_totals, end)

