from __future__ import annotations

import os
import sqlite3
import tempfile
import urllib.parse
from datetime import datetime
from pathlib import Path
from shutil import copyfile, rmtree
from typing import Any

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
    parse_json_text_with_limit,
    read_json_document,
)


def sum_open_code_tokens(tokens: dict[str, object] | None) -> TokenTotals:
    tokens = tokens or {}
    cache = tokens.get("cache") or {}
    cache_input = int((cache or {}).get("read", 0) or 0)
    cache_output = int((cache or {}).get("write", 0) or 0)
    input_tokens = int(tokens.get("input", 0) or 0) + cache_input
    output_tokens = int(tokens.get("output", 0) or 0) + cache_output
    return TokenTotals(
        input=input_tokens,
        output=output_tokens,
        cache=CacheTokens(input=cache_input, output=cache_output),
        total=input_tokens + output_tokens,
    )


def parse_open_code_file(file_path: Path) -> dict[str, Any]:
    return read_json_document(file_path)


def get_open_code_base_dir() -> Path:
    base_dir = os.environ.get("OPENCODE_DATA_DIR", "").strip()
    return Path(base_dir).expanduser().resolve() if base_dir else Path.home() / ".local" / "share" / "opencode"


def get_open_code_source() -> tuple[str, Path | list[Path]]:
    base_dir = get_open_code_base_dir()
    database_path = base_dir / "opencode.db"
    if database_path.exists():
        return "database", database_path

    messages_dir = base_dir / "storage" / "message"
    return "legacy", list_files_recursive(messages_dir, ".json")


def is_open_code_available() -> bool:
    base_dir = get_open_code_base_dir()
    return (base_dir / "opencode.db").exists() or (base_dir / "storage" / "message").exists()


def parse_open_code_message_data(row_id: str, source_label: str, content: str) -> dict[str, Any]:
    message = parse_json_text_with_limit(content, source_label)
    if not isinstance(message, dict):
        raise ValueError(f"OpenCode payload in {source_label} is not an object.")
    message["id"] = message.get("id") or row_id
    return message


def sqlite_readonly_uri(database_path: Path) -> str:
    return f"file:{urllib.parse.quote(str(database_path))}?mode=ro"


def is_sqlite_locked_error(error: Exception) -> bool:
    return isinstance(error, sqlite3.OperationalError) and "locked" in str(error).lower()


def with_database_snapshot(database_path: Path, callback):
    snapshot_dir = Path(tempfile.mkdtemp(prefix="slopmeter-opencode-"))
    snapshot_path = snapshot_dir / "opencode.db"
    copyfile(database_path, snapshot_path)
    for suffix in ("-shm", "-wal"):
        companion_path = Path(f"{database_path}{suffix}")
        if companion_path.exists():
            copyfile(companion_path, Path(f"{snapshot_path}{suffix}"))
    try:
        return callback(snapshot_path)
    finally:
        rmtree(snapshot_dir, ignore_errors=True)


def iterate_open_code_database_messages(database_path: Path, on_message) -> None:
    database = sqlite3.connect(sqlite_readonly_uri(database_path), uri=True)
    try:
        query = "SELECT id, data FROM message ORDER BY time_created ASC"
        for row_id, data in database.execute(query):
            on_message(parse_open_code_message_data(str(row_id), f"{database_path}:message:{row_id}", str(data)))
    finally:
        database.close()


def load_open_code_database_messages(database_path: Path, on_message) -> None:
    try:
        iterate_open_code_database_messages(database_path, on_message)
    except Exception as error:
        if not is_sqlite_locked_error(error):
            raise
        with_database_snapshot(database_path, lambda snapshot_path: iterate_open_code_database_messages(snapshot_path, on_message))


def add_open_code_message(
    message: dict[str, Any],
    start: datetime,
    end: datetime,
    recent_start: datetime,
    totals: DailyTotalsByDate,
    model_totals: ModelTotals,
    recent_model_totals: ModelTotals,
    dedupe: set[str],
) -> None:
    message_id = str(message.get("id") or "")
    if message_id in dedupe:
        return
    dedupe.add(message_id)

    token_totals = sum_open_code_tokens(message.get("tokens") if isinstance(message.get("tokens"), dict) else None)
    if token_totals.total <= 0:
        return

    time_value = message.get("time")
    created_at = time_value.get("created") if isinstance(time_value, dict) else None
    record_date = parse_datetime(created_at)
    if record_date is None or record_date < start or record_date > end:
        return

    raw_model_id = str(message.get("modelID", "")).strip()
    model_name = normalize_model_name(raw_model_id) if raw_model_id else None
    add_daily_token_totals(totals, record_date, token_totals, model_name)
    if not model_name:
        return

    add_model_token_totals(model_totals, model_name, token_totals)
    if record_date >= recent_start:
        add_model_token_totals(recent_model_totals, model_name, token_totals)


def load_open_code_rows(start: datetime, end: datetime) -> UsageSummary:
    source_kind, source_value = get_open_code_source()
    totals: DailyTotalsByDate = {}
    dedupe: set[str] = set()
    recent_start = get_recent_window_start(end, 30)
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}

    if source_kind == "database":
        load_open_code_database_messages(
            source_value,
            lambda message: add_open_code_message(
                message,
                start,
                end,
                recent_start,
                totals,
                model_totals,
                recent_model_totals,
                dedupe,
            ),
        )
    else:
        for file_path in source_value:
            message = parse_open_code_file(file_path)
            if isinstance(message, dict):
                add_open_code_message(
                    message,
                    start,
                    end,
                    recent_start,
                    totals,
                    model_totals,
                    recent_model_totals,
                    dedupe,
                )

    return create_usage_summary("opencode", totals, model_totals, recent_model_totals, end)

