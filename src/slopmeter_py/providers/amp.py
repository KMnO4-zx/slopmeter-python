from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from ..models import CacheTokens, TokenTotals, UsageSummary
from ..utils import (
    DailyTotalsByDate,
    ModelTotals,
    add_daily_token_totals,
    add_model_token_totals,
    create_usage_summary,
    get_positive_integer_env,
    get_recent_window_start,
    list_files_recursive,
    merge_daily_totals_by_date,
    merge_model_totals,
    normalize_model_name,
    parse_datetime,
    read_json_document,
    run_with_concurrency,
    DEFAULT_FILE_PROCESS_CONCURRENCY,
    FILE_PROCESS_CONCURRENCY_ENV,
)

AMP_HOME_ENV = "AMP_DATA_DIR"


def get_amp_data_dir() -> Path:
    env_dir = os.environ.get(AMP_HOME_ENV, "").strip()
    if env_dir:
        return Path(env_dir).expanduser().resolve()

    xdg_data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    if not xdg_data_home:
        xdg_data_home = str(Path.home() / ".local" / "share")

    return Path(xdg_data_home) / "amp"


def get_amp_files() -> list[Path]:
    return list_files_recursive(get_amp_data_dir() / "threads", ".json")


def is_amp_available() -> bool:
    return (get_amp_data_dir() / "threads").exists()


def create_amp_token_totals(usage: dict[str, object]) -> TokenTotals:
    cache_read_input = int(usage.get("cacheReadInputTokens", 0) or 0)
    cache_creation_input = int(usage.get("cacheCreationInputTokens", 0) or 0)
    input_tokens = int(usage.get("inputTokens", 0) or 0) + cache_read_input
    output_tokens = int(usage.get("outputTokens", 0) or 0) + cache_creation_input
    return TokenTotals(
        input=input_tokens,
        output=output_tokens,
        cache=CacheTokens(input=cache_read_input, output=cache_creation_input),
        total=input_tokens + output_tokens,
    )


def process_amp_file(file_path: Path, start: datetime, end: datetime) -> tuple[DailyTotalsByDate, ModelTotals, ModelTotals]:
    totals: DailyTotalsByDate = {}
    recent_start = get_recent_window_start(end, 30)
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}

    try:
        thread = read_json_document(file_path)
    except Exception:
        return totals, model_totals, recent_model_totals

    messages = thread.get("messages")
    if not isinstance(messages, list):
        return totals, model_totals, recent_model_totals

    thread_date = parse_datetime(thread.get("created"))
    last_user_timestamp: datetime | None = None

    for message in messages:
        if not isinstance(message, dict):
            continue

        if message.get("role") == "user" and isinstance(message.get("meta"), dict):
            last_user_timestamp = parse_datetime(message["meta"].get("sentAt"))
            continue

        if message.get("role") != "assistant" or not isinstance(message.get("usage"), dict):
            continue

        usage = message["usage"]
        record_date = last_user_timestamp or thread_date
        if record_date is None or record_date < start or record_date > end:
            continue

        token_totals = create_amp_token_totals(usage)
        if token_totals.total <= 0:
            continue

        model_name = usage.get("model")
        normalized_model_name = normalize_model_name(str(model_name)) if model_name else None
        add_daily_token_totals(totals, record_date, token_totals, normalized_model_name)

        if not normalized_model_name:
            continue

        add_model_token_totals(model_totals, normalized_model_name, token_totals)
        if record_date >= recent_start:
            add_model_token_totals(recent_model_totals, normalized_model_name, token_totals)

    return totals, model_totals, recent_model_totals


def load_amp_rows(start: datetime, end: datetime) -> UsageSummary:
    files = get_amp_files()
    totals: DailyTotalsByDate = {}
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}
    file_concurrency = get_positive_integer_env(
        FILE_PROCESS_CONCURRENCY_ENV,
        DEFAULT_FILE_PROCESS_CONCURRENCY,
    )
    results = run_with_concurrency(
        files,
        file_concurrency,
        lambda file_path, _index: process_amp_file(file_path, start, end),
    )

    for result in results:
        result_totals, result_model_totals, result_recent_model_totals = result
        merge_daily_totals_by_date(totals, result_totals)
        merge_model_totals(model_totals, result_model_totals)
        merge_model_totals(recent_model_totals, result_recent_model_totals)

    return create_usage_summary("amp", totals, model_totals, recent_model_totals, end)

