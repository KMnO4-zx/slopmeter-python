from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from slopmeter.providers.cursor import fetch_cursor_usage_csv
from slopmeter.providers.cursor import CursorAuthState, CursorUsageExportAuthError, load_cursor_rows


class DummyResponse:
    def __init__(self, text: str, *, is_success: bool = True):
        self.text = text
        self.is_success = is_success
        self.status_code = 200 if is_success else 401
        self.reason_phrase = "OK" if is_success else "Unauthorized"


class DummyClient:
    def __init__(self, calls: list[dict[str, str]], response_text: str, response_factory=None):
        self.calls = calls
        self.response_text = response_text
        self.response_factory = response_factory

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def get(self, url: str, headers: dict[str, str]):
        self.calls.append(
            {
                "url": url,
                "authorization": headers.get("Authorization", ""),
                "cookie": headers.get("Cookie", ""),
            }
        )
        if self.response_factory is not None:
            return self.response_factory(url, headers)
        return DummyResponse(self.response_text)


def test_fetch_cursor_usage_csv_uses_short_term_cache(monkeypatch, tmp_path):
    calls: list[dict[str, str]] = []
    csv_text = "Date,Model,Tokens\n2026-04-11,gpt-5.4,42\n"

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
    monkeypatch.setenv("SLOPMETER_CURSOR_CACHE_TTL_SECONDS", "300")
    monkeypatch.setattr(
        "slopmeter.providers.cursor.httpx.Client",
        lambda **kwargs: DummyClient(calls, csv_text),
    )

    first = fetch_cursor_usage_csv("token-123")
    second = fetch_cursor_usage_csv("token-123")

    assert first == csv_text
    assert second == csv_text
    assert len(calls) == 1


def test_fetch_cursor_usage_csv_respects_disabled_cache(monkeypatch, tmp_path):
    calls: list[dict[str, str]] = []
    csv_text = "Date,Model,Tokens\n2026-04-11,gpt-5.4,42\n"

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
    monkeypatch.setenv("SLOPMETER_CURSOR_CACHE_TTL_SECONDS", "0")
    monkeypatch.setattr(
        "slopmeter.providers.cursor.httpx.Client",
        lambda **kwargs: DummyClient(calls, csv_text),
    )

    fetch_cursor_usage_csv("token-123")
    fetch_cursor_usage_csv("token-123")

    assert len(calls) == 2


def test_fetch_cursor_usage_csv_remembers_successful_auth_attempt(monkeypatch, tmp_path):
    calls: list[dict[str, str]] = []
    csv_text = "Date,Model,Tokens\n2026-04-11,gpt-5.4,42\n"

    def response_factory(_url: str, headers: dict[str, str]):
        if headers.get("Cookie") == "WorkosCursorSessionToken=token-123":
            return DummyResponse(csv_text)
        return DummyResponse("unauthorized", is_success=False)

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
    monkeypatch.setenv("SLOPMETER_CURSOR_CACHE_TTL_SECONDS", "0")
    monkeypatch.setattr(
        "slopmeter.providers.cursor.httpx.Client",
        lambda **kwargs: DummyClient(calls, csv_text, response_factory=response_factory),
    )

    fetch_cursor_usage_csv("token-123")
    fetch_cursor_usage_csv("token-123")

    assert len(calls) == 3
    assert calls[0]["authorization"] == "Bearer token-123"
    assert calls[0]["cookie"] == ""
    assert calls[1]["cookie"] == "WorkosCursorSessionToken=token-123"
    assert calls[2]["cookie"] == "WorkosCursorSessionToken=token-123"


def test_fetch_cursor_usage_csv_marks_auth_failure(monkeypatch, tmp_path):
    calls: list[dict[str, str]] = []

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / ".cache"))
    monkeypatch.setenv("SLOPMETER_CURSOR_CACHE_TTL_SECONDS", "0")
    monkeypatch.setattr(
        "slopmeter.providers.cursor.httpx.Client",
        lambda **kwargs: DummyClient(
            calls,
            "forbidden",
            response_factory=lambda _url, _headers: DummyResponse("forbidden", is_success=False),
        ),
    )

    with pytest.raises(CursorUsageExportAuthError):
        fetch_cursor_usage_csv("token-123")


def test_load_cursor_rows_skips_expired_local_auth(monkeypatch, tmp_path):
    def reject_export(_access_token: str) -> str:
        raise CursorUsageExportAuthError("expired Cursor auth")

    monkeypatch.setattr("slopmeter.providers.cursor.get_cursor_state_db_path", lambda: tmp_path / "state.vscdb")
    monkeypatch.setattr(
        "slopmeter.providers.cursor.read_cursor_auth_state",
        lambda _database_path: CursorAuthState(access_token="token-123"),
    )
    monkeypatch.setattr("slopmeter.providers.cursor.fetch_cursor_usage_csv", reject_export)

    end = datetime.now()
    summary = load_cursor_rows(start=end - timedelta(days=365), end=end)

    assert summary.provider == "cursor"
    assert summary.daily == []
    assert summary.insights is not None
    assert summary.insights.streaks.longest == 0
