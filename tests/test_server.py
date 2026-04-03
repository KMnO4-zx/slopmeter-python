from __future__ import annotations

import errno
import io

import pytest

from slopmeter.server import create_html_server, create_snapshot_handler


def test_create_snapshot_handler_serves_root_document():
    handler_class = create_snapshot_handler("<html><body>ok</body></html>")
    handler = object.__new__(handler_class)
    responses: list[int] = []
    headers: list[tuple[str, str]] = []

    handler.path = "/"
    handler.wfile = io.BytesIO()
    handler.send_response = lambda code: responses.append(code)
    handler.send_header = lambda key, value: headers.append((key, value))
    handler.end_headers = lambda: None

    handler.do_GET()

    assert responses == [200]
    assert ("Content-Type", "text/html; charset=utf-8") in headers
    assert handler.wfile.getvalue() == b"<html><body>ok</body></html>"


def test_create_snapshot_handler_returns_404_for_unknown_path():
    handler_class = create_snapshot_handler("<html></html>")
    handler = object.__new__(handler_class)
    responses: list[int] = []
    headers: list[tuple[str, str]] = []

    handler.path = "/missing"
    handler.wfile = io.BytesIO()
    handler.send_response = lambda code: responses.append(code)
    handler.send_header = lambda key, value: headers.append((key, value))
    handler.end_headers = lambda: None

    handler.do_GET()

    assert responses == [404]
    assert ("Content-Length", "0") in headers


def test_create_html_server_moves_to_next_port_when_port_is_in_use(monkeypatch):
    attempts: list[int] = []

    class FakeServer:
        def __init__(self, server_address, handler):
            host, port = server_address
            attempts.append(port)
            if len(attempts) == 1:
                raise OSError(errno.EADDRINUSE, "Address already in use")
            self.server_address = (host, port)

    monkeypatch.setattr("slopmeter.server.SnapshotHTTPServer", FakeServer)

    server, url = create_html_server(
        "<html></html>",
        host="127.0.0.1",
        port=8000,
        strict_port=False,
    )

    assert attempts == [8000, 8001]
    assert server.server_address == ("127.0.0.1", 8001)
    assert url == "http://127.0.0.1:8001"


def test_create_html_server_strict_port_fails_when_port_is_in_use(monkeypatch):
    class FakeServer:
        def __init__(self, server_address, handler):
            raise OSError(errno.EADDRINUSE, "Address already in use")

    monkeypatch.setattr("slopmeter.server.SnapshotHTTPServer", FakeServer)

    with pytest.raises(ValueError, match="Address already in use"):
        create_html_server(
            "<html></html>",
            host="127.0.0.1",
            port=8000,
            strict_port=True,
        )
