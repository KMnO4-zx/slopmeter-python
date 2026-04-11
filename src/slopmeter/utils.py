from __future__ import annotations

import json
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, TypeVar

from .models import CacheTokens, DailyUsage, Insights, ModelUsage, Streaks, TokenTotals, UsageSummary

DEFAULT_FILE_PROCESS_CONCURRENCY = 16
FILE_PROCESS_CONCURRENCY_ENV = "SLOPMETER_FILE_PROCESS_CONCURRENCY"
MAX_JSONL_RECORD_BYTES_ENV = "SLOPMETER_MAX_JSONL_RECORD_BYTES"
DEFAULT_MAX_JSONL_RECORD_BYTES = 64 * 1024 * 1024

T = TypeVar("T")


@dataclass
class TokenTotalsByDate:
    tokens: TokenTotals
    models: dict[str, TokenTotals]


DailyTotalsByDate = dict[str, TokenTotalsByDate]
ModelTotals = dict[str, TokenTotals]


@dataclass
class JsonlRecordDecision:
    kind: str
    classification: Any = None


@dataclass
class JsonlRecord:
    line_number: int
    raw_line: str
    byte_length: int
    classification: Any


def format_local_date(value: date | datetime) -> str:
    if isinstance(value, datetime):
        value = value.date()

    return f"{value.year:04d}-{value.month:02d}-{value.day:02d}"


def clone_token_totals(totals: TokenTotals) -> TokenTotals:
    return TokenTotals(
        input=totals.input,
        output=totals.output,
        cache=CacheTokens(input=totals.cache.input, output=totals.cache.output),
        total=totals.total,
    )


def merge_token_totals(target: TokenTotals, source: TokenTotals) -> None:
    target.input += source.input
    target.output += source.output
    target.cache.input += source.cache.input
    target.cache.output += source.cache.output
    target.total += source.total


def add_model_token_totals(model_totals: ModelTotals, model_name: str, token_totals: TokenTotals) -> None:
    existing = model_totals.get(model_name)
    if existing is None:
        model_totals[model_name] = clone_token_totals(token_totals)
        return

    merge_token_totals(existing, token_totals)


def add_daily_token_totals(
    totals: DailyTotalsByDate,
    value: date | datetime,
    token_totals: TokenTotals,
    model_name: str | None = None,
) -> None:
    key = format_local_date(value)
    existing = totals.get(key)
    if existing is None:
        models: dict[str, TokenTotals] = {}
        if model_name:
            models[model_name] = clone_token_totals(token_totals)
        totals[key] = TokenTotalsByDate(tokens=clone_token_totals(token_totals), models=models)
        return

    merge_token_totals(existing.tokens, token_totals)
    if model_name:
        add_model_token_totals(existing.models, model_name, token_totals)


def merge_daily_totals_by_date(target: DailyTotalsByDate, source: DailyTotalsByDate) -> None:
    for date_key, source_totals in source.items():
        existing = target.get(date_key)
        if existing is None:
            target[date_key] = TokenTotalsByDate(
                tokens=clone_token_totals(source_totals.tokens),
                models={name: clone_token_totals(totals) for name, totals in source_totals.models.items()},
            )
            continue

        merge_token_totals(existing.tokens, source_totals.tokens)
        for model_name, totals in source_totals.models.items():
            add_model_token_totals(existing.models, model_name, totals)


def merge_model_totals(target: ModelTotals, source: ModelTotals) -> None:
    for model_name, totals in source.items():
        add_model_token_totals(target, model_name, totals)


def totals_to_rows(
    totals: DailyTotalsByDate,
    display_values_by_date: dict[str, int] | None = None,
) -> list[DailyUsage]:
    display_values_by_date = display_values_by_date or {}
    all_dates = sorted(set(totals.keys()) | set(display_values_by_date.keys()))
    rows: list[DailyUsage] = []

    for date_key in all_dates:
        entry = totals.get(date_key)
        tokens = entry.tokens if entry else TokenTotals()
        models = entry.models if entry else {}
        display_value = tokens.total if tokens.total > 0 else display_values_by_date.get(date_key, 0)

        rows.append(
            DailyUsage(
                date=datetime.strptime(date_key, "%Y-%m-%d").date(),
                input=tokens.input,
                output=tokens.output,
                cache=CacheTokens(input=tokens.cache.input, output=tokens.cache.output),
                total=tokens.total,
                display_value=display_value if display_value > 0 else None,
                breakdown=[
                    ModelUsage(
                        name=name,
                        tokens=TokenTotals(
                            input=totals_value.input,
                            output=totals_value.output,
                            cache=CacheTokens(
                                input=totals_value.cache.input,
                                output=totals_value.cache.output,
                            ),
                            total=totals_value.total,
                        ),
                    )
                    for name, totals_value in sorted(
                        models.items(),
                        key=lambda item: item[1].total,
                        reverse=True,
                    )
                ],
            )
        )

    return rows


def list_files_recursive(root_dir: Path, extension: str) -> list[Path]:
    if not root_dir.exists():
        return []

    files: list[Path] = []
    stack = [root_dir]
    while stack:
        current_dir = stack.pop()
        try:
            with os.scandir(current_dir) as iterator:
                entries = list(iterator)
        except OSError:
            continue

        for entry in entries:
            try:
                if entry.is_dir():
                    stack.append(Path(entry.path))
                elif entry.is_file() and entry.name.endswith(extension):
                    files.append(Path(entry.path))
            except OSError:
                continue

    return sorted(files)


def default_oversized_jsonl_record_message(
    *,
    file_path: str,
    line_number: int,
    max_record_bytes: int,
    env_var_name: str,
) -> str:
    return (
        f"JSONL record exceeds {max_record_bytes} bytes in {file_path}:{line_number}. "
        f"Increase {env_var_name} to process this file."
    )


def default_oversized_json_document_message(
    *,
    file_path: str,
    max_bytes: int,
    env_var_name: str,
) -> str:
    return (
        f"JSON document exceeds {max_bytes} bytes in {file_path}. "
        f"Increase {env_var_name} to process this file."
    )


def default_oversized_json_text_message(
    *,
    source_label: str,
    max_bytes: int,
    env_var_name: str,
) -> str:
    return (
        f"JSON payload exceeds {max_bytes} bytes in {source_label}. "
        f"Increase {env_var_name} to process this payload."
    )


def keep_all_jsonl_records(_: str) -> JsonlRecordDecision:
    return JsonlRecordDecision(kind="keep")


def read_jsonl_records(
    file_path: Path,
    *,
    classification_prefix_bytes: int | None = None,
    classify: Callable[[str], JsonlRecordDecision] | None = None,
    max_record_bytes: int | None = None,
    on_skipped_oversized_record: Callable[[dict[str, int]], None] | None = None,
    oversized_error_message: Callable[..., str] | None = None,
) -> Iterator[JsonlRecord]:
    max_record_bytes = max_record_bytes or get_positive_integer_env(
        MAX_JSONL_RECORD_BYTES_ENV,
        DEFAULT_MAX_JSONL_RECORD_BYTES,
    )
    classification_prefix_bytes = classification_prefix_bytes or max_record_bytes
    classify = classify or keep_all_jsonl_records
    oversized_error_message = oversized_error_message or default_oversized_jsonl_record_message

    line_number = 0
    line_bytes_seen = 0
    retained_bytes = 0
    prefix_bytes = 0
    exceeded_limit = False
    decision = JsonlRecordDecision(kind="unknown")
    prefix_chunks: list[bytes] = []
    retained_chunks: list[bytes] = []

    def reset_record() -> None:
        nonlocal line_bytes_seen, retained_bytes, prefix_bytes, exceeded_limit, decision
        nonlocal prefix_chunks, retained_chunks
        line_bytes_seen = 0
        retained_bytes = 0
        prefix_bytes = 0
        exceeded_limit = False
        decision = JsonlRecordDecision(kind="unknown")
        prefix_chunks = []
        retained_chunks = []

    def maybe_classify() -> None:
        nonlocal decision, retained_chunks, retained_bytes
        if decision.kind != "unknown" or prefix_bytes == 0:
            return
        decision = classify(b"".join(prefix_chunks).decode("utf-8", errors="replace"))
        if decision.kind == "skip":
            retained_chunks = []
            retained_bytes = 0

    def append_segment(segment: bytes) -> None:
        nonlocal line_bytes_seen, retained_bytes, prefix_bytes, exceeded_limit
        if not segment:
            return

        line_bytes_seen += len(segment)

        if prefix_bytes < classification_prefix_bytes:
            prefix_segment = segment[: min(len(segment), classification_prefix_bytes - prefix_bytes)]
            prefix_chunks.append(prefix_segment)
            prefix_bytes += len(prefix_segment)
            maybe_classify()

        if decision.kind == "skip":
            return

        remaining_bytes = max_record_bytes - retained_bytes
        if remaining_bytes > 0:
            retained_segment = segment[: min(len(segment), remaining_bytes)]
            if retained_segment:
                retained_chunks.append(retained_segment)
                retained_bytes += len(retained_segment)

        if len(segment) > remaining_bytes:
            exceeded_limit = True

    def resolve_decision() -> JsonlRecordDecision:
        if decision.kind != "unknown":
            return decision

        candidate_bytes = (
            b"".join(prefix_chunks)
            if exceeded_limit or retained_bytes == 0
            else b"".join(retained_chunks)
        )
        return classify(candidate_bytes.decode("utf-8", errors="replace"))

    def finalize_record() -> JsonlRecord | None:
        nonlocal line_number
        line_number += 1

        if line_bytes_seen == 0 and not exceeded_limit:
            reset_record()
            return None

        resolved = resolve_decision()
        if resolved.kind == "skip":
            if line_bytes_seen > max_record_bytes and on_skipped_oversized_record:
                on_skipped_oversized_record(
                    {"line_number": line_number, "byte_length": line_bytes_seen}
                )
            reset_record()
            return None

        if resolved.kind == "unknown":
            reset_record()
            return None

        if line_bytes_seen > max_record_bytes or exceeded_limit:
            raise ValueError(
                oversized_error_message(
                    file_path=str(file_path),
                    line_number=line_number,
                    max_record_bytes=max_record_bytes,
                    env_var_name=MAX_JSONL_RECORD_BYTES_ENV,
                )
            )

        raw_line = b"".join(retained_chunks).decode("utf-8", errors="replace").strip()
        if raw_line == "":
            reset_record()
            return None

        record = JsonlRecord(
            line_number=line_number,
            raw_line=raw_line,
            byte_length=line_bytes_seen,
            classification=resolved.classification,
        )
        reset_record()
        return record

    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            start = 0
            for index, byte in enumerate(chunk):
                if byte != 0x0A:
                    continue
                append_segment(chunk[start:index])
                record = finalize_record()
                if record is not None:
                    yield record
                start = index + 1
            append_segment(chunk[start:])

    if line_bytes_seen > 0:
        record = finalize_record()
        if record is not None:
            yield record


def read_json_lines(file_path: Path) -> Iterator[Any]:
    for record in read_jsonl_records(file_path):
        try:
            yield json.loads(record.raw_line)
        except json.JSONDecodeError:
            continue


def read_json_document(
    file_path: Path,
    *,
    max_bytes: int | None = None,
    oversized_error_message: Callable[..., str] | None = None,
) -> Any:
    max_bytes = max_bytes or get_positive_integer_env(
        MAX_JSONL_RECORD_BYTES_ENV,
        DEFAULT_MAX_JSONL_RECORD_BYTES,
    )
    oversized_error_message = oversized_error_message or default_oversized_json_document_message
    chunks: list[bytes] = []
    total_bytes = 0

    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise ValueError(
                    oversized_error_message(
                        file_path=str(file_path),
                        max_bytes=max_bytes,
                        env_var_name=MAX_JSONL_RECORD_BYTES_ENV,
                    )
                )
            chunks.append(chunk)

    return parse_json_text_with_limit(
        b"".join(chunks).decode("utf-8", errors="replace"),
        str(file_path),
        max_bytes=max_bytes,
        oversized_error_message=lambda *, source_label, max_bytes, env_var_name: oversized_error_message(
            file_path=source_label,
            max_bytes=max_bytes,
            env_var_name=env_var_name,
        ),
    )


def parse_json_text_with_limit(
    content: str,
    source_label: str,
    *,
    max_bytes: int | None = None,
    oversized_error_message: Callable[..., str] | None = None,
) -> Any:
    max_bytes = max_bytes or get_positive_integer_env(
        MAX_JSONL_RECORD_BYTES_ENV,
        DEFAULT_MAX_JSONL_RECORD_BYTES,
    )
    oversized_error_message = oversized_error_message or default_oversized_json_text_message

    if len(content.encode("utf-8")) > max_bytes:
        raise ValueError(
            oversized_error_message(
                source_label=source_label,
                max_bytes=max_bytes,
                env_var_name=MAX_JSONL_RECORD_BYTES_ENV,
            )
        )

    return json.loads(content)


def get_positive_integer_env(name: str, fallback: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return fallback

    try:
        parsed = int(raw)
    except ValueError:
        return fallback

    return parsed if parsed >= 1 else fallback


def run_with_concurrency(items: list[T], concurrency: int, worker: Callable[[T, int], Any]) -> list[Any]:
    if not items:
        return []

    limit = max(1, min(concurrency, len(items)))
    results: list[Any] = [None] * len(items)
    with ThreadPoolExecutor(max_workers=limit) as executor:
        futures = [executor.submit(worker, item, index) for index, item in enumerate(items)]
        for index, future in enumerate(futures):
            results[index] = future.result()
    return results


def get_recent_window_start(end_date: datetime, days: int = 30) -> datetime:
    start = end_date - timedelta(days=days - 1)
    return start.replace(hour=0, minute=0, second=0, microsecond=0)


def normalize_model_name(model_name: str) -> str:
    return re.sub(r"-\d{8}$", "", model_name)


def get_top_model(model_totals: ModelTotals) -> ModelUsage | None:
    if not model_totals:
        return None

    best_model: tuple[str, TokenTotals] | None = None
    for model_name, totals in model_totals.items():
        if totals.total <= 0:
            continue
        if best_model is None or totals.total > best_model[1].total:
            best_model = (model_name, totals)

    if best_model is None:
        return None

    model_name, totals = best_model
    return ModelUsage(
        name=model_name,
        tokens=TokenTotals(
            input=totals.input,
            output=totals.output,
            cache=CacheTokens(input=totals.cache.input, output=totals.cache.output),
            total=totals.total,
        ),
    )


def start_of_day(value: date) -> date:
    return value


def is_consecutive_day(prev_date: date, curr_date: date) -> bool:
    return curr_date.toordinal() - prev_date.toordinal() == 1


def compute_longest_streak(daily: list[DailyUsage]) -> int:
    if not daily:
        return 0

    longest = 1
    running = 1
    for index in range(1, len(daily)):
        if is_consecutive_day(daily[index - 1].date, daily[index].date):
            running += 1
            longest = max(longest, running)
        else:
            running = 1
    return longest


def compute_current_streak(daily: list[DailyUsage], end: datetime) -> int:
    if not daily:
        return 0

    end_day = end.date()
    last_entry_day = daily[-1].date
    if last_entry_day != end_day and not is_consecutive_day(last_entry_day, end_day):
        return 0

    current = 1
    for index in range(len(daily) - 2, -1, -1):
        if not is_consecutive_day(daily[index].date, daily[index + 1].date):
            break
        current += 1
    return current


def get_provider_insights(
    model_totals: ModelTotals,
    recent_model_totals: ModelTotals,
    daily: list[DailyUsage],
    end: datetime,
) -> Insights:
    measured_daily = [row for row in daily if (row.display_value or row.total) > 0]
    return Insights(
        most_used_model=get_top_model(model_totals),
        recent_most_used_model=get_top_model(recent_model_totals),
        streaks=Streaks(
            longest=compute_longest_streak(measured_daily),
            current=compute_current_streak(measured_daily, end),
        ),
    )


def create_usage_summary(
    provider: str,
    totals: DailyTotalsByDate,
    model_totals: ModelTotals,
    recent_model_totals: ModelTotals,
    end: datetime,
    display_values_by_date: dict[str, int] | None = None,
) -> UsageSummary:
    daily = totals_to_rows(totals, display_values_by_date)
    return UsageSummary(
        provider=provider,
        daily=daily,
        insights=get_provider_insights(model_totals, recent_model_totals, daily, end),
    )


def has_usage(summary: UsageSummary) -> bool:
    return any(row.total > 0 or (row.display_value or 0) > 0 for row in summary.daily)


def merge_usage_summaries(provider: str, summaries: list[UsageSummary], end: datetime) -> UsageSummary:
    totals: DailyTotalsByDate = {}
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}
    display_values_by_date: dict[str, int] = {}
    recent_start = get_recent_window_start(end, 30).date()

    for summary in summaries:
        for row in summary.daily:
            add_daily_token_totals(
                totals,
                row.date,
                TokenTotals(
                    input=row.input,
                    output=row.output,
                    cache=CacheTokens(input=row.cache.input, output=row.cache.output),
                    total=row.total,
                ),
            )

            date_key = format_local_date(row.date)
            display_value = row.display_value or row.total
            if display_value > 0:
                display_values_by_date[date_key] = display_values_by_date.get(date_key, 0) + display_value

            totals_for_date = totals.get(date_key)
            if totals_for_date is None:
                continue

            for breakdown in row.breakdown:
                add_model_token_totals(totals_for_date.models, breakdown.name, breakdown.tokens)
                add_model_token_totals(model_totals, breakdown.name, breakdown.tokens)
                if row.date >= recent_start:
                    add_model_token_totals(recent_model_totals, breakdown.name, breakdown.tokens)

    return create_usage_summary(
        provider,
        totals,
        model_totals,
        recent_model_totals,
        end,
        display_values_by_date,
    )


def parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value

    if isinstance(value, (int, float)):
        timestamp = float(value)
        if abs(timestamp) >= 10_000_000_000:
            timestamp /= 1000.0
        try:
            return datetime.fromtimestamp(timestamp)
        except (OverflowError, OSError, ValueError):
            return None

    if isinstance(value, str):
        trimmed = value.strip()
        if not trimmed:
            return None
        if trimmed.isdigit():
            return parse_datetime(int(trimmed))

        normalized = trimmed.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone().replace(tzinfo=None)
        return parsed

    return None


def ensure_within_range(value: datetime | None, start: datetime, end: datetime) -> bool:
    return value is not None and start <= value <= end
