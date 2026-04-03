from __future__ import annotations

import errno
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable, Type
from urllib.parse import urlsplit

MAX_PORT = 65535
ExportPngCallback = Callable[[list[str]], tuple[bytes, str]]


class SnapshotHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def sanitize_filename(filename: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in filename).strip("._")
    return cleaned or "slopmeter.png"


def send_bytes_response(
    handler: BaseHTTPRequestHandler,
    *,
    status: int,
    body: bytes,
    content_type: str,
    extra_headers: dict[str, str] | None = None,
) -> None:
    handler.send_response(status)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Content-Length", str(len(body)))
    for key, value in (extra_headers or {}).items():
        handler.send_header(key, value)
    handler.end_headers()
    if body:
        handler.wfile.write(body)


def send_json_response(
    handler: BaseHTTPRequestHandler,
    *,
    status: int,
    payload: dict[str, object],
) -> None:
    send_bytes_response(
        handler,
        status=status,
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json; charset=utf-8",
    )


def create_snapshot_handler(
    document: str,
    *,
    export_png: ExportPngCallback | None = None,
) -> Type[BaseHTTPRequestHandler]:
    body = document.encode("utf-8")

    class SnapshotHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler signature
            path = urlsplit(self.path).path
            if path == "/":
                send_bytes_response(
                    self,
                    status=200,
                    body=body,
                    content_type="text/html; charset=utf-8",
                )
                return

            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler signature
            path = urlsplit(self.path).path
            if path != "/api/export" or export_png is None:
                self.send_response(404)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return

            content_length = self.headers.get("Content-Length", "0")
            try:
                body_length = max(int(content_length), 0)
            except ValueError:
                send_json_response(
                    self,
                    status=400,
                    payload={"error": "Invalid Content-Length header."},
                )
                return

            try:
                request_payload = json.loads(self.rfile.read(body_length) or b"{}")
            except json.JSONDecodeError:
                send_json_response(
                    self,
                    status=400,
                    payload={"error": "Invalid JSON request body."},
                )
                return

            provider_ids = request_payload.get("providerIds")
            if not isinstance(provider_ids, list) or not all(isinstance(item, str) for item in provider_ids):
                send_json_response(
                    self,
                    status=400,
                    payload={"error": "Expected providerIds to be a list of strings."},
                )
                return

            try:
                png_bytes, filename = export_png(provider_ids)
            except ValueError as error:
                send_json_response(
                    self,
                    status=400,
                    payload={"error": str(error)},
                )
                return

            send_bytes_response(
                self,
                status=200,
                body=png_bytes,
                content_type="image/png",
                extra_headers={
                    "Content-Disposition": f'attachment; filename="{sanitize_filename(filename)}"',
                },
            )

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003 - stdlib signature
            return

    return SnapshotHandler


def iter_candidate_ports(start_port: int, strict_port: bool):
    if strict_port or start_port == 0:
        yield start_port
        return

    for candidate in range(start_port, MAX_PORT + 1):
        yield candidate


def create_bind_error(host: str, port: int, error: OSError) -> ValueError:
    message = str(error)
    if error.errno == errno.EADDRINUSE:
        message = f"Address already in use for {host}:{port}"
    return ValueError(message)


def create_html_server(
    document: str,
    *,
    host: str,
    port: int,
    strict_port: bool,
    export_png: ExportPngCallback | None = None,
) -> tuple[SnapshotHTTPServer, str]:
    if port < 0 or port > MAX_PORT:
        raise ValueError(f"Port out of range: {port}")

    handler = create_snapshot_handler(document, export_png=export_png)
    for candidate_port in iter_candidate_ports(port, strict_port):
        try:
            server = SnapshotHTTPServer((host, candidate_port), handler)
        except OSError as error:
            if not strict_port and error.errno == errno.EADDRINUSE and candidate_port < MAX_PORT:
                continue
            raise create_bind_error(host, candidate_port, error) from error

        actual_port = int(server.server_address[1])
        return server, f"http://{host}:{actual_port}"

    raise ValueError(f"Unable to bind a server starting from {host}:{port}")


__all__ = ["SnapshotHTTPServer", "create_html_server", "create_snapshot_handler"]
