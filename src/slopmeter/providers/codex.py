from __future__ import annotations

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from ..models import CacheTokens, TokenTotals, UsageSummary
from ..utils import (
    DailyTotalsByDate,
    ModelTotals,
    DEFAULT_FILE_PROCESS_CONCURRENCY,
    DEFAULT_MAX_JSONL_RECORD_BYTES,
    FILE_PROCESS_CONCURRENCY_ENV,
    MAX_JSONL_RECORD_BYTES_ENV,
    JsonlRecordDecision,
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
    read_jsonl_records,
    run_with_concurrency,
)

CLASSIFICATION_PREFIX_BYTES = 32 * 1024


def normalize_codex_usage(value: dict[str, object] | None) -> dict[str, int] | None:
    if not value:
        return None

    input_tokens = int(value.get("input_tokens", 0) or 0)
    cached_input_tokens = int(
        value.get("cached_input_tokens", value.get("cache_read_input_tokens", 0)) or 0
    )
    output_tokens = int(value.get("output_tokens", 0) or 0)
    reasoning_output_tokens = int(value.get("reasoning_output_tokens", 0) or 0)
    total_tokens = int(value.get("total_tokens", 0) or 0)
    if total_tokens <= 0:
        total_tokens = input_tokens + output_tokens

    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_output_tokens,
        "total_tokens": total_tokens,
    }


def add_codex_usage(base: dict[str, int] | None, delta: dict[str, int]) -> dict[str, int]:
    return {
        "input_tokens": (base or {}).get("input_tokens", 0) + delta["input_tokens"],
        "cached_input_tokens": (base or {}).get("cached_input_tokens", 0) + delta["cached_input_tokens"],
        "output_tokens": (base or {}).get("output_tokens", 0) + delta["output_tokens"],
        "reasoning_output_tokens": (base or {}).get("reasoning_output_tokens", 0) + delta["reasoning_output_tokens"],
        "total_tokens": (base or {}).get("total_tokens", 0) + delta["total_tokens"],
    }


def subtract_codex_usage(current: dict[str, int], previous: dict[str, int] | None) -> dict[str, int]:
    previous = previous or {}
    return {
        "input_tokens": max(current["input_tokens"] - previous.get("input_tokens", 0), 0),
        "cached_input_tokens": max(
            current["cached_input_tokens"] - previous.get("cached_input_tokens", 0),
            0,
        ),
        "output_tokens": max(current["output_tokens"] - previous.get("output_tokens", 0), 0),
        "reasoning_output_tokens": max(
            current["reasoning_output_tokens"] - previous.get("reasoning_output_tokens", 0),
            0,
        ),
        "total_tokens": max(current["total_tokens"] - previous.get("total_tokens", 0), 0),
    }


def did_codex_totals_rollback(current: dict[str, int], previous: dict[str, int] | None) -> bool:
    if not previous:
        return False

    return (
        current["input_tokens"] < previous["input_tokens"]
        or current["cached_input_tokens"] < previous["cached_input_tokens"]
        or current["output_tokens"] < previous["output_tokens"]
        or current["reasoning_output_tokens"] < previous["reasoning_output_tokens"]
        or current["total_tokens"] < previous["total_tokens"]
    )


def as_non_empty_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def extract_codex_model(payload: dict[str, Any] | None) -> str | None:
    if not isinstance(payload, dict):
        return None

    direct_model = as_non_empty_string(payload.get("model")) or as_non_empty_string(
        payload.get("model_name")
    )
    if direct_model:
        return direct_model

    info = payload.get("info")
    if isinstance(info, dict):
        info_model = as_non_empty_string(info.get("model")) or as_non_empty_string(
            info.get("model_name")
        )
        if info_model:
            return info_model
        metadata = info.get("metadata")
        if isinstance(metadata, dict):
            model = as_non_empty_string(metadata.get("model"))
            if model:
                return model

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        return as_non_empty_string(metadata.get("model"))

    return None


def get_codex_home() -> Path:
    codex_home = os.environ.get("CODEX_HOME", "").strip()
    return Path(codex_home).expanduser().resolve() if codex_home else Path.home() / ".codex"


def get_codex_files() -> list[Path]:
    return list_files_recursive(get_codex_home() / "sessions", ".jsonl")


def is_codex_available() -> bool:
    return (get_codex_home() / "sessions").exists()


def read_json_string(source: str, start: int) -> tuple[str, int] | None:
    if source[start] != '"':
        return None

    value: list[str] = []
    escaped = False
    for index in range(start + 1, len(source)):
        char = source[index]
        if escaped:
            value.append(char)
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if char == '"':
            return "".join(value), index + 1
        value.append(char)
    return None


def skip_whitespace(source: str, start: int) -> int:
    index = start
    while index < len(source) and source[index].isspace():
        index += 1
    return index


def skip_primitive(source: str, start: int) -> int:
    index = start
    while index < len(source):
        char = source[index]
        if char in ",}]" or char.isspace():
            return index
        index += 1
    return len(source)


def classify_codex_record(source: str) -> JsonlRecordDecision:
    stack: list[dict[str, Any]] = []
    top_level_type: str | None = None
    index = 0

    while index < len(source):
        index = skip_whitespace(source, index)
        if index >= len(source):
            break

        char = source[index]
        if not stack:
            if char != "{":
                return JsonlRecordDecision(kind="unknown")
            stack.append({"kind": "object", "expecting": "keyOrEnd", "is_payload_object": False})
            index += 1
            continue

        context = stack[-1]
        if context["kind"] == "object":
            if context["expecting"] == "keyOrEnd":
                if char == "}":
                    stack.pop()
                    index += 1
                    continue
                key = read_json_string(source, index)
                if key is None:
                    return JsonlRecordDecision(kind="unknown")
                context["key"] = key[0]
                context["expecting"] = "colon"
                index = key[1]
                continue

            if context["expecting"] == "colon":
                if char != ":":
                    return JsonlRecordDecision(kind="unknown")
                context["expecting"] = "value"
                index += 1
                continue

            if context["expecting"] == "value":
                if char == "{":
                    stack.append(
                        {
                            "kind": "object",
                            "expecting": "keyOrEnd",
                            "is_payload_object": len(stack) == 1 and context.get("key") == "payload",
                        }
                    )
                    context["expecting"] = "commaOrEnd"
                    context["key"] = None
                    index += 1
                    continue

                if char == "[":
                    stack.append({"kind": "array", "expecting": "valueOrEnd"})
                    context["expecting"] = "commaOrEnd"
                    context["key"] = None
                    index += 1
                    continue

                if char == '"':
                    value = read_json_string(source, index)
                    if value is None:
                        return JsonlRecordDecision(kind="unknown")

                    if len(stack) == 1 and context.get("key") == "type":
                        top_level_type = value[0]
                        if value[0] == "turn_context":
                            return JsonlRecordDecision(kind="keep", classification="turn_context")
                        if value[0] != "event_msg":
                            return JsonlRecordDecision(kind="skip")

                    if context["is_payload_object"] and context.get("key") == "type":
                        if value[0] == "token_count":
                            if top_level_type == "event_msg":
                                return JsonlRecordDecision(kind="keep", classification="token_count")
                            return JsonlRecordDecision(kind="unknown")
                        if top_level_type == "event_msg":
                            return JsonlRecordDecision(kind="skip")
                        return JsonlRecordDecision(kind="unknown")

                    context["expecting"] = "commaOrEnd"
                    context["key"] = None
                    index = value[1]
                    continue

                context["expecting"] = "commaOrEnd"
                context["key"] = None
                index = skip_primitive(source, index)
                continue

            if char == ",":
                context["expecting"] = "keyOrEnd"
                index += 1
                continue
            if char == "}":
                stack.pop()
                index += 1
                continue
            return JsonlRecordDecision(kind="unknown")

        if context["expecting"] == "valueOrEnd":
            if char == "]":
                stack.pop()
                index += 1
                continue
            if char == "{":
                stack.append({"kind": "object", "expecting": "keyOrEnd", "is_payload_object": False})
                context["expecting"] = "commaOrEnd"
                index += 1
                continue
            if char == "[":
                stack.append({"kind": "array", "expecting": "valueOrEnd"})
                context["expecting"] = "commaOrEnd"
                index += 1
                continue
            if char == '"':
                value = read_json_string(source, index)
                if value is None:
                    return JsonlRecordDecision(kind="unknown")
                context["expecting"] = "commaOrEnd"
                index = value[1]
                continue
            context["expecting"] = "commaOrEnd"
            index = skip_primitive(source, index)
            continue

        if char == ",":
            context["expecting"] = "valueOrEnd"
            index += 1
            continue
        if char == "]":
            stack.pop()
            index += 1
            continue
        return JsonlRecordDecision(kind="unknown")

    if top_level_type and top_level_type != "event_msg":
        return JsonlRecordDecision(kind="skip")
    return JsonlRecordDecision(kind="unknown")


def load_codex_rows(start: datetime, end: datetime, warnings: list[str] | None = None) -> UsageSummary:
    warnings = warnings or []
    files = get_codex_files()
    totals: DailyTotalsByDate = {}
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}
    max_record_bytes = get_positive_integer_env(
        MAX_JSONL_RECORD_BYTES_ENV,
        DEFAULT_MAX_JSONL_RECORD_BYTES,
    )
    file_concurrency = get_positive_integer_env(
        FILE_PROCESS_CONCURRENCY_ENV,
        DEFAULT_FILE_PROCESS_CONCURRENCY,
    )

    skipped_oversized_irrelevant_records = 0
    skipped_files = 0

    def worker(file_path: Path, _index: int) -> tuple[DailyTotalsByDate, ModelTotals, ModelTotals, int]:
        local_skipped = 0
        recent_start = get_recent_window_start(end, 30)
        local_totals: DailyTotalsByDate = {}
        local_model_totals: ModelTotals = {}
        local_recent_model_totals: ModelTotals = {}
        previous_totals: dict[str, int] | None = None
        current_model: str | None = None

        def on_skipped_oversized_record(_record: dict[str, int]) -> None:
            nonlocal local_skipped
            local_skipped += 1

        for record in read_jsonl_records(
            file_path,
            classification_prefix_bytes=CLASSIFICATION_PREFIX_BYTES,
            classify=classify_codex_record,
            max_record_bytes=max_record_bytes,
            on_skipped_oversized_record=on_skipped_oversized_record,
            oversized_error_message=lambda *, file_path, line_number, max_record_bytes, env_var_name: (
                f"Relevant Codex record exceeds {max_record_bytes} bytes in "
                f"{file_path}:{line_number}. Increase {env_var_name} to process this file."
            ),
        ):
            try:
                entry = json.loads(record.raw_line)
            except Exception:
                continue

            extracted_model = extract_codex_model(entry.get("payload"))
            if record.classification == "turn_context":
                current_model = extracted_model or current_model
                continue

            info = (entry.get("payload") or {}).get("info")
            if not isinstance(info, dict):
                continue

            last_usage = normalize_codex_usage(info.get("last_token_usage"))
            total_usage = normalize_codex_usage(info.get("total_token_usage"))
            raw_usage: dict[str, int] | None = None

            if total_usage:
                raw_usage = (
                    last_usage or total_usage
                    if did_codex_totals_rollback(total_usage, previous_totals)
                    else subtract_codex_usage(total_usage, previous_totals)
                )
                previous_totals = total_usage
            else:
                raw_usage = last_usage
                if raw_usage:
                    previous_totals = add_codex_usage(previous_totals, raw_usage)

            if not raw_usage:
                continue

            usage = TokenTotals(
                input=raw_usage["input_tokens"],
                output=raw_usage["output_tokens"],
                cache=CacheTokens(input=raw_usage["cached_input_tokens"], output=0),
                total=raw_usage["total_tokens"],
            )
            if usage.total <= 0:
                continue

            record_date = parse_datetime(entry.get("timestamp"))
            if record_date is None or record_date < start or record_date > end:
                continue

            model_name = extracted_model or current_model
            normalized_model_name = normalize_model_name(model_name) if model_name else None
            add_daily_token_totals(local_totals, record_date, usage, normalized_model_name)

            if not normalized_model_name:
                continue

            add_model_token_totals(local_model_totals, normalized_model_name, usage)
            if record_date >= recent_start:
                add_model_token_totals(local_recent_model_totals, normalized_model_name, usage)

        return local_totals, local_model_totals, local_recent_model_totals, local_skipped

    results = run_with_concurrency(files, file_concurrency, worker)
    for result in results:
        result_totals, result_model_totals, result_recent_model_totals, result_skipped = result
        merge_daily_totals_by_date(totals, result_totals)
        merge_model_totals(model_totals, result_model_totals)
        merge_model_totals(recent_model_totals, result_recent_model_totals)
        if result_skipped > 0:
            skipped_oversized_irrelevant_records += result_skipped
            skipped_files += 1

    if skipped_oversized_irrelevant_records > 0:
        warnings.append(
            f"Skipped {skipped_oversized_irrelevant_records} oversized irrelevant Codex "
            f"record(s) across {skipped_files} file(s); usage totals exclude those records. "
            f"Relevant oversized records fail the file. Override {MAX_JSONL_RECORD_BYTES_ENV} "
            f"to raise the cap."
        )

    return create_usage_summary("codex", totals, model_totals, recent_model_totals, end)
