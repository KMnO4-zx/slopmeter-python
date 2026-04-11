from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import os
import sqlite3
import tempfile
import urllib.parse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from shutil import copyfile, rmtree
from typing import Any

import httpx

from ..models import CacheTokens, TokenTotals, UsageSummary
from ..utils import (
    DailyTotalsByDate,
    ModelTotals,
    add_daily_token_totals,
    add_model_token_totals,
    create_usage_summary,
    get_positive_integer_env,
    get_recent_window_start,
    normalize_model_name,
    parse_datetime,
)

CURSOR_CONFIG_DIR_ENV = "CURSOR_CONFIG_DIR"
CURSOR_STATE_DB_PATH_ENV = "CURSOR_STATE_DB_PATH"
CURSOR_WEB_BASE_URL_ENV = "CURSOR_WEB_BASE_URL"
CURSOR_CACHE_TTL_SECONDS_ENV = "SLOPMETER_CURSOR_CACHE_TTL_SECONDS"
CURSOR_STATE_DB_RELATIVE_PATH = Path("User") / "globalStorage" / "state.vscdb"
CURSOR_SESSION_COOKIE_NAME = "WorkosCursorSessionToken"
DEFAULT_CURSOR_CACHE_TTL_SECONDS = 300


@dataclass
class CursorAuthState:
    access_token: str | None = None
    refresh_token: str | None = None


@dataclass(frozen=True)
class CursorFetchAttempt:
    id: str
    label: str
    headers: dict[str, str]


def get_cursor_default_state_db_path() -> Path:
    if os.sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Cursor" / CURSOR_STATE_DB_RELATIVE_PATH
    if os.sys.platform == "win32":
        app_data = os.environ.get("APPDATA", "").strip()
        if not app_data:
            app_data = str(Path.home() / "AppData" / "Roaming")
        return Path(app_data) / "Cursor" / CURSOR_STATE_DB_RELATIVE_PATH

    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if not xdg_config_home:
        xdg_config_home = str(Path.home() / ".config")
    return Path(xdg_config_home) / "Cursor" / CURSOR_STATE_DB_RELATIVE_PATH


def get_cursor_state_db_candidates() -> list[Path]:
    explicit_db_path = os.environ.get(CURSOR_STATE_DB_PATH_ENV, "").strip()
    if explicit_db_path:
        return [Path(explicit_db_path).expanduser().resolve()]

    configured_dirs = os.environ.get(CURSOR_CONFIG_DIR_ENV, "").strip()
    if not configured_dirs:
        return [get_cursor_default_state_db_path()]

    results = []
    for value in configured_dirs.split(","):
        trimmed = value.strip()
        if not trimmed:
            continue
        resolved = Path(trimmed).expanduser().resolve()
        results.append(resolved if resolved.suffix == ".vscdb" else resolved / CURSOR_STATE_DB_RELATIVE_PATH)
    return results


def get_cursor_state_db_path() -> Path | None:
    seen: set[Path] = set()
    for candidate in get_cursor_state_db_candidates():
        if candidate.exists() and candidate not in seen:
            return candidate
        seen.add(candidate)
    return None


def normalize_cursor_db_value(value: Any) -> str | None:
    if isinstance(value, bytes):
        value = value.decode("utf-8", errors="replace")
    if not isinstance(value, str):
        return None
    trimmed = value.strip()
    return trimmed or None


def sqlite_readonly_uri(database_path: Path) -> str:
    return f"file:{urllib.parse.quote(str(database_path))}?mode=ro"


def read_cursor_auth_state_from_database(database_path: Path) -> CursorAuthState:
    database = sqlite3.connect(sqlite_readonly_uri(database_path), uri=True)
    try:
        query = "SELECT value FROM ItemTable WHERE key = ? LIMIT 1"
        access_row = database.execute(query, ("cursorAuth/accessToken",)).fetchone()
        refresh_row = database.execute(query, ("cursorAuth/refreshToken",)).fetchone()
        return CursorAuthState(
            access_token=normalize_cursor_db_value(access_row[0]) if access_row else None,
            refresh_token=normalize_cursor_db_value(refresh_row[0]) if refresh_row else None,
        )
    finally:
        database.close()


def is_sqlite_locked_error(error: Exception) -> bool:
    return isinstance(error, sqlite3.OperationalError) and "locked" in str(error).lower()


def with_cursor_state_snapshot(database_path: Path, callback):
    snapshot_dir = Path(tempfile.mkdtemp(prefix="slopmeter-cursor-"))
    snapshot_path = snapshot_dir / "state.vscdb"
    copyfile(database_path, snapshot_path)
    for suffix in ("-shm", "-wal"):
        companion_path = Path(f"{database_path}{suffix}")
        if companion_path.exists():
            copyfile(companion_path, Path(f"{snapshot_path}{suffix}"))
    try:
        return callback(snapshot_path)
    finally:
        rmtree(snapshot_dir, ignore_errors=True)


def read_cursor_auth_state(database_path: Path) -> CursorAuthState:
    try:
        return read_cursor_auth_state_from_database(database_path)
    except Exception as error:
        if not is_sqlite_locked_error(error):
            raise
        return with_cursor_state_snapshot(database_path, read_cursor_auth_state_from_database)


def is_cursor_available() -> bool:
    database_path = get_cursor_state_db_path()
    if not database_path:
        return False
    return bool(read_cursor_auth_state(database_path).access_token)


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    parts = token.split(".")
    if len(parts) < 2:
        return None

    encoded_payload = parts[1].replace("-", "+").replace("_", "/")
    padded = encoded_payload + "=" * ((4 - len(encoded_payload) % 4) % 4)
    try:
        decoded = base64.b64decode(padded)
        payload = json.loads(decoded.decode("utf-8"))
    except Exception:
        return None

    return payload if isinstance(payload, dict) else None


def get_cursor_web_base_url() -> str:
    return (os.environ.get(CURSOR_WEB_BASE_URL_ENV, "").strip() or "https://cursor.com").rstrip("/")


def build_cookie_header_value(cookie_value: str) -> str:
    return f"{CURSOR_SESSION_COOKIE_NAME}={cookie_value}"


def get_cursor_cache_ttl_seconds() -> int:
    raw = os.environ.get(CURSOR_CACHE_TTL_SECONDS_ENV, "").strip()
    if raw == "0":
        return 0
    return get_positive_integer_env(CURSOR_CACHE_TTL_SECONDS_ENV, DEFAULT_CURSOR_CACHE_TTL_SECONDS)


def get_slopmeter_cache_dir() -> Path:
    xdg_cache_home = os.environ.get("XDG_CACHE_HOME", "").strip()
    if xdg_cache_home:
        return Path(xdg_cache_home).expanduser().resolve() / "slopmeter"
    return Path.home() / ".cache" / "slopmeter"


def get_cursor_usage_cache_path(access_token: str) -> Path:
    key = hashlib.sha256(f"{get_cursor_web_base_url()}\n{access_token}".encode("utf-8")).hexdigest()
    return get_slopmeter_cache_dir() / f"cursor-usage-{key}.csv"


def get_cursor_auth_strategy_cache_path(subject: str | None) -> Path:
    key = hashlib.sha256(f"{get_cursor_web_base_url()}\n{subject or ''}".encode("utf-8")).hexdigest()
    return get_slopmeter_cache_dir() / f"cursor-auth-{key}.json"


def read_preferred_cursor_fetch_attempt_id(subject: str | None) -> str | None:
    cache_path = get_cursor_auth_strategy_cache_path(subject)
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    attempt_id = payload.get("attemptId")
    return attempt_id if isinstance(attempt_id, str) and attempt_id.strip() else None


def write_preferred_cursor_fetch_attempt_id(subject: str | None, attempt_id: str) -> None:
    cache_path = get_cursor_auth_strategy_cache_path(subject)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"attemptId": attempt_id}), encoding="utf-8")
    except OSError:
        return


def read_cursor_usage_cache(access_token: str) -> str | None:
    ttl_seconds = get_cursor_cache_ttl_seconds()
    if ttl_seconds <= 0:
        return None

    cache_path = get_cursor_usage_cache_path(access_token)
    try:
        if not cache_path.exists():
            return None
        if (datetime.now().timestamp() - cache_path.stat().st_mtime) > ttl_seconds:
            return None
        return cache_path.read_text(encoding="utf-8")
    except OSError:
        return None


def write_cursor_usage_cache(access_token: str, content: str) -> None:
    if get_cursor_cache_ttl_seconds() <= 0:
        return

    cache_path = get_cursor_usage_cache_path(access_token)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(content, encoding="utf-8")
    except OSError:
        return


def get_cursor_fetch_attempts(access_token: str) -> list[CursorFetchAttempt]:
    attempts: list[CursorFetchAttempt] = []
    seen: set[str] = set()
    subject = ((decode_jwt_payload(access_token) or {}).get("sub") or "").strip()
    cookie_values = [access_token]
    if subject:
        cookie_values.append(f"{subject}::{access_token}")

    def push_attempt(attempt_id: str, label: str, headers: dict[str, str]) -> None:
        signature = json.dumps({"id": attempt_id, "headers": sorted(headers.items())})
        if signature in seen:
            return
        seen.add(signature)
        attempts.append(CursorFetchAttempt(id=attempt_id, label=label, headers=headers))

    push_attempt("bearer", "bearer", {"Authorization": f"Bearer {access_token}"})
    for index, cookie_value in enumerate(cookie_values):
        suffix = "" if index == 0 else "-subject"
        push_attempt(f"cookie{suffix}", "cookie", {"Cookie": build_cookie_header_value(cookie_value)})
        push_attempt(
            f"cookie-encoded{suffix}",
            "cookie-encoded",
            {"Cookie": build_cookie_header_value(urllib.parse.quote(cookie_value))},
        )
        push_attempt(
            f"bearer+cookie{suffix}",
            "bearer+cookie",
            {
                "Authorization": f"Bearer {access_token}",
                "Cookie": build_cookie_header_value(cookie_value),
            },
        )
        push_attempt(
            f"bearer+cookie-encoded{suffix}",
            "bearer+cookie-encoded",
            {
                "Authorization": f"Bearer {access_token}",
                "Cookie": build_cookie_header_value(urllib.parse.quote(cookie_value)),
            },
        )
    return attempts


def prioritize_cursor_fetch_attempts(
    attempts: list[CursorFetchAttempt],
    preferred_attempt_id: str | None,
) -> list[CursorFetchAttempt]:
    if not preferred_attempt_id:
        return attempts
    return sorted(attempts, key=lambda attempt: attempt.id != preferred_attempt_id)


def fetch_cursor_usage_csv(access_token: str) -> str:
    cached_content = read_cursor_usage_cache(access_token)
    if cached_content is not None:
        return cached_content

    subject = ((decode_jwt_payload(access_token) or {}).get("sub") or "").strip() or None
    attempts = prioritize_cursor_fetch_attempts(
        get_cursor_fetch_attempts(access_token),
        read_preferred_cursor_fetch_attempt_id(subject),
    )
    url = f"{get_cursor_web_base_url()}/api/dashboard/export-usage-events-csv?strategy=tokens"
    failures: list[str] = []
    with httpx.Client(follow_redirects=True, timeout=60.0) as client:
        for attempt in attempts:
            response = client.get(
                url,
                headers={
                    "Accept": "text/csv,text/plain;q=0.9,*/*;q=0.8",
                    **attempt.headers,
                },
            )
            if response.is_success:
                write_preferred_cursor_fetch_attempt_id(subject, attempt.id)
                write_cursor_usage_cache(access_token, response.text)
                return response.text
            body = response.text.strip()[:200]
            status_line = f"{attempt.label}: {response.status_code} {response.reason_phrase}".strip()
            failures.append(f"{status_line} ({body})" if body else status_line)

    summary = "; ".join(failures)
    raise ValueError(
        f"Failed to authenticate Cursor usage export with local auth state from "
        f"{get_cursor_web_base_url()}. {summary}"
    )


def parse_cursor_date(value: str | None) -> datetime | None:
    trimmed = (value or "").strip()
    if not trimmed:
        return None
    if len(trimmed) == 10 and trimmed[4] == "-" and trimmed[7] == "-":
        return parse_datetime(f"{trimmed}T00:00:00")
    return parse_datetime(trimmed)


def parse_cursor_number(value: str | None) -> int | None:
    try:
        numeric = float((value or "").replace(",", "").strip())
    except ValueError:
        return None
    if not numeric or numeric <= 0:
        return None
    return round(numeric)


def create_cursor_token_totals(row: dict[str, str]) -> TokenTotals | None:
    total = parse_cursor_number(row.get("Total Tokens")) or parse_cursor_number(row.get("Tokens"))
    if not total:
        return None

    input_with_cache_write = parse_cursor_number(row.get("Input (w/ Cache Write)")) or 0
    input_without_cache_write = parse_cursor_number(row.get("Input (w/o Cache Write)")) or 0
    cache_input = parse_cursor_number(row.get("Cache Read")) or 0
    output_tokens = parse_cursor_number(row.get("Output Tokens")) or 0

    return TokenTotals(
        input=input_with_cache_write + input_without_cache_write + cache_input,
        output=output_tokens,
        cache=CacheTokens(input=cache_input, output=input_with_cache_write),
        total=total,
    )


def add_cursor_usage_row(
    row: dict[str, str],
    start: datetime,
    end: datetime,
    recent_start: datetime,
    totals: DailyTotalsByDate,
    model_totals: ModelTotals,
    recent_model_totals: ModelTotals,
) -> None:
    record_date = parse_cursor_date(row.get("Date"))
    raw_model = (row.get("Model") or "").strip()
    token_totals = create_cursor_token_totals(row)
    if record_date is None or not raw_model or token_totals is None:
        return
    if record_date < start or record_date > end:
        return

    model_name = normalize_model_name(raw_model)
    add_daily_token_totals(totals, record_date, token_totals, model_name)
    add_model_token_totals(model_totals, model_name, token_totals)
    if record_date >= recent_start:
        add_model_token_totals(recent_model_totals, model_name, token_totals)


def summarize_cursor_usage_csv_text(
    content: str,
    start: datetime,
    end: datetime,
    recent_start: datetime | None = None,
) -> UsageSummary:
    recent_start = recent_start or get_recent_window_start(end, 30)
    totals: DailyTotalsByDate = {}
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}

    reader = csv.DictReader(io.StringIO(content))
    for row in reader:
        add_cursor_usage_row(
            {key: value or "" for key, value in row.items()},
            start,
            end,
            recent_start,
            totals,
            model_totals,
            recent_model_totals,
        )

    return create_usage_summary("cursor", totals, model_totals, recent_model_totals, end)


def load_cursor_rows(start: datetime, end: datetime) -> UsageSummary:
    database_path = get_cursor_state_db_path()
    totals: DailyTotalsByDate = {}
    model_totals: ModelTotals = {}
    recent_model_totals: ModelTotals = {}
    if not database_path:
        return create_usage_summary("cursor", totals, model_totals, recent_model_totals, end)

    auth_state = read_cursor_auth_state(database_path)
    if not auth_state.access_token:
        return create_usage_summary("cursor", totals, model_totals, recent_model_totals, end)

    recent_start = get_recent_window_start(end, 30)
    content = fetch_cursor_usage_csv(auth_state.access_token)
    return summarize_cursor_usage_csv_text(content, start, end, recent_start)
