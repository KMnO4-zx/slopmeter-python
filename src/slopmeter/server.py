from __future__ import annotations

import errno
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Type
from urllib.parse import urlsplit

MAX_PORT = 65535


class SnapshotHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def create_snapshot_handler(document: str) -> Type[BaseHTTPRequestHandler]:
    body = document.encode("utf-8")

    class SnapshotHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib handler signature
            path = urlsplit(self.path).path
            if path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return

            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

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
) -> tuple[SnapshotHTTPServer, str]:
    if port < 0 or port > MAX_PORT:
        raise ValueError(f"Port out of range: {port}")

    handler = create_snapshot_handler(document)
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


__all__ = ["SnapshotHTTPServer", "create_html_server"]
