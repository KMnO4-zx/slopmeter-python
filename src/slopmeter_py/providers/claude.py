from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path

from ..models import CacheTokens, TokenTotals, UsageSummary
from ..utils import (
    DailyTotalsByDate,
    ModelTotals,
    DEFAULT_FILE_PROCESS_CONCURRENCY,
    FILE_PROCESS_CONCURRENCY_ENV,
    add_daily_token_totals,
    add_model_token_totals,
    create_usage_summary,
    format_local_date,
    get_positive_integer_env,
    get_recent_window_start,
    list_files_recursive,
    normalize_model_name,
    parse_datetime,
    read_json_document,
    read_json_lines,
)

CLAUDE_CONFIG_DIR_ENV = "CLAUDE_CONFIG_DIR"
CLAUDE_PROJECTS_DIR_NAME = "projects"
CLAUDE_STATS_CACHE_FILE_NAME = "stats-cache.json"


def discover_claude_work_dirs() -> list[Path]:
    home = Path.home()
    try:
        entries = list(home.iterdir())
    except OSError:
        return []

    results: list[Path] = []
    for entry in entries:
        if not entry.is_dir() or not entry.name.startswith(".claude-"):
            continue
        if (entry / CLAUDE_PROJECTS_DIR_NAME).exists() or (entry / CLAUDE_STATS_CACHE_FILE_NAME).exists():
            results.append(entry)
    return results


def get_claude_config_paths() -> list[Path]:
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if not xdg_config_home:
        xdg_config_home = str(Path.home() / ".config")

    defaults = [Path(xdg_config_home) / "claude", Path.home() / ".claude"]
    env_paths = os.environ.get(CLAUDE_CONFIG_DIR_ENV, "").strip()
    resolved_env = []
    if env_paths:
        resolved_env = [
            Path(path.strip()).expanduser().resolve()
            for path in env_paths.split(",")
            if path.strip()
        ]

    seen = {path for path in resolved_env}
    paths = list(resolved_env)
    for path in [*defaults, *discover_claude_work_dirs()]:
        resolved = path.expanduser().resolve()
        if resolved not in seen:
            seen.add(resolved)
            paths.append(resolved)
    return paths


def get_claude_project_dirs() -> list[Path]:
    unique: set[Path] = set()
    dirs: list[Path] = []
    for base_path in get_claude_config_paths():
        projects_dir = base_path / CLAUDE_PROJECTS_DIR_NAME
        if projects_dir.exists() and projects_dir not in unique:
            unique.add(projects_dir)
            dirs.append(projects_dir)
    return dirs


def get_claude_stats_cache_files() -> list[Path]:
    unique: set[Path] = set()
    files: list[Path] = []
    for base_path in get_claude_config_paths():
        stats_cache_file = base_path / CLAUDE_STATS_CACHE_FILE_NAME
        if stats_cache_file.exists() and stats_cache_file not in unique:
            unique.add(stats_cache_file)
            files.append(stats_cache_file)
    return files


def get_claude_history_files() -> list[Path]:
    unique: set[Path] = set()
    files: list[Path] = []
    for base_path in get_claude_config_paths():
        history_file = base_path / "history.jsonl"
        if history_file.exists() and history_file not in unique:
            unique.add(history_file)
            files.append(history_file)
    return files


def get_claude_files() -> list[Path]:
    files: list[Path] = []
    for project_dir in get_claude_project_dirs():
        files.extend(list_files_recursive(project_dir, ".jsonl"))
    return files


def is_claude_available() -> bool:
    return bool(
        get_claude_project_dirs()
        or get_claude_stats_cache_files()
        or get_claude_history_files()
    )


def parse_claude_log_entry(entry: dict[str, object]) -> dict[str, object] | None:
    if not entry.get("timestamp"):
        return None

    message = entry.get("message")
    if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
        return None

    return {
        "timestamp": entry.get("timestamp"),
        "usage": message["usage"],
        "model": message.get("model"),
        "message_id": message.get("id"),
        "request_id": entry.get("requestId"),
    }


def create_claude_token_totals(usage: dict[str, object]) -> TokenTotals:
    cache_read_input = int(usage.get("cache_read_input_tokens", 0) or 0)
    cache_creation_input = int(usage.get("cache_creation_input_tokens", 0) or 0)
    input_tokens = int(usage.get("input_tokens", 0) or 0) + cache_read_input
    output_tokens = int(usage.get("output_tokens", 0) or 0) + cache_creation_input
    return TokenTotals(
        input=input_tokens,
        output=output_tokens,
        cache=CacheTokens(input=cache_read_input, output=cache_creation_input),
        total=input_tokens + output_tokens,
    )


def distribute_token_components(total: int, weights: list[int]) -> list[int]:
    weight_sum = sum(weights)
    if total <= 0 or weight_sum <= 0:
        return [0 for _ in weights]

    exact = [(weight / weight_sum) * total for weight in weights]
    allocated = [math.floor(value) for value in exact]
    remainder = total - sum(allocated)
    order = sorted(
        (
            {
                "index": index,
                "fraction": exact[index] - allocated[index],
                "weight": weights[index],
            }
            for index in range(len(weights))
        ),
        key=lambda item: (item["fraction"], item["weight"]),
        reverse=True,
    )
    for item in order:
        if remainder <= 0:
            break
        allocated[item["index"]] += 1
        remainder -= 1

    return allocated


def create_stats_cache_token_totals(total_tokens: int, usage: dict[str, object] | None) -> TokenTotals:
    if total_tokens <= 0:
        return TokenTotals()

    usage = usage or {}
    input_tokens = int(usage.get("inputTokens", 0) or 0)
    output_tokens = int(usage.get("outputTokens", 0) or 0)
    cache_read_input_tokens = int(usage.get("cacheReadInputTokens", 0) or 0)
    cache_creation_input_tokens = int(usage.get("cacheCreationInputTokens", 0) or 0)
    scaled_input, scaled_output, scaled_cache_read, scaled_cache_creation = distribute_token_components(
        total_tokens,
        [input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens],
    )

    if (
        scaled_input == 0
        and scaled_output == 0
        and scaled_cache_read == 0
        and scaled_cache_creation == 0
    ):
        return TokenTotals(input=total_tokens, total=total_tokens)

    return TokenTotals(
        input=scaled_input + scaled_cache_read,
        output=scaled_output + scaled_cache_creation,
        cache=CacheTokens(input=scaled_cache_read, output=scaled_cache_creation),
        total=total_tokens,
    )


def load_claude_stats_cache_rows(
    start_date: datetime,
    end_date: datetime,
    covered_dates: set[str],
    totals: DailyTotalsByDate,
    model_totals: ModelTotals,
    recent_model_totals: ModelTotals,
    recent_start: datetime,
) -> None:
    for file_path in get_claude_stats_cache_files():
        try:
            stats_cache = read_json_document(file_path)
        except Exception:
            continue

        for row in stats_cache.get("dailyModelTokens", []) or []:
            if not isinstance(row, dict):
                continue
            date_value = row.get("date")
            if not isinstance(date_value, str) or date_value in covered_dates:
                continue

            timestamp = parse_datetime(f"{date_value}T00:00:00")
            if timestamp is None or timestamp < start_date or timestamp > end_date:
                continue

            tokens_by_model = row.get("tokensByModel") or {}
            if not isinstance(tokens_by_model, dict):
                continue

            for raw_model_name, total_tokens in tokens_by_model.items():
                if not isinstance(total_tokens, (int, float)) or not math.isfinite(total_tokens) or total_tokens <= 0:
                    continue

                model_name = normalize_model_name(str(raw_model_name))
                token_totals = create_stats_cache_token_totals(
                    int(total_tokens),
                    (stats_cache.get("modelUsage") or {}).get(raw_model_name),
                )
                add_daily_token_totals(totals, timestamp, token_totals, model_name)
                add_model_token_totals(model_totals, model_name, token_totals)
                if timestamp >= recent_start:
                    add_model_token_totals(recent_model_totals, model_name, token_totals)


def load_claude_history_display_values(
    start_date: datetime,
    end_date: datetime,
    covered_dates: set[str],
    display_values_by_date: dict[str, int],
) -> None:
    for file_path in get_claude_history_files():
        for line in read_json_lines(file_path):
            if not isinstance(line, dict):
                continue
            timestamp = parse_datetime(line.get("timestamp"))
            if timestamp is None or timestamp < start_date or timestamp > end_date:
                continue
            date_key = format_local_date(timestamp)
            if date_key in covered_dates:
                continue
            display_values_by_date[date_key] = display_values_by_date.get(date_key, 0) + 1


def create_unique_hash(message_id: object, request_id: object) -> str | None:
    if not message_id or not request_id:
        return None
    return f"{message_id}:{request_id}"


def load_claude_rows(start_date: datetime, end_date: datetime) -> UsageSummary:
    _ = get_positive_integer_env(FILE_PROCESS_CONCURRENCY_ENV, DEFAULT_FILE_PROCESS_CONCURRENCY)
    files = get_claude_files()
    totals: DailyTotalsByDate = {}
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}
    display_values_by_date: dict[str, int] = {}
    recent_start = get_recent_window_start(end_date, 30)
    processed_hashes: set[str] = set()

    for file_path in files:
        for line in read_json_lines(file_path):
            if not isinstance(line, dict):
                continue
            entry = parse_claude_log_entry(line)
            if entry is None:
                continue

            unique_hash = create_unique_hash(entry.get("message_id"), entry.get("request_id"))
            if unique_hash and unique_hash in processed_hashes:
                continue
            if unique_hash:
                processed_hashes.add(unique_hash)

            timestamp = parse_datetime(entry.get("timestamp"))
            if timestamp is None or timestamp < start_date or timestamp > end_date:
                continue

            usage = entry.get("usage")
            if not isinstance(usage, dict):
                continue
            token_totals = create_claude_token_totals(usage)
            if token_totals.total <= 0:
                continue

            model_value = entry.get("model")
            model_name = None
            if model_value and model_value != "<synthetic>":
                model_name = normalize_model_name(str(model_value))

            add_daily_token_totals(totals, timestamp, token_totals, model_name)
            if not model_name:
                continue

            add_model_token_totals(model_totals, model_name, token_totals)
            if timestamp >= recent_start:
                add_model_token_totals(recent_model_totals, model_name, token_totals)

    load_claude_stats_cache_rows(
        start_date,
        end_date,
        set(totals.keys()),
        totals,
        model_totals,
        recent_model_totals,
        recent_start,
    )
    load_claude_history_display_values(
        start_date,
        end_date,
        set(totals.keys()),
        display_values_by_date,
    )

    return create_usage_summary(
        "claude",
        totals,
        model_totals,
        recent_model_totals,
        end_date,
        display_values_by_date,
    )

