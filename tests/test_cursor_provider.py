from __future__ import annotations

from slopmeter.providers.cursor import fetch_cursor_usage_csv


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
