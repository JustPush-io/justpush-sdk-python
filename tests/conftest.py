"""A tiny local HTTP server that stands in for the JustPush API."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest


class FakeAPI:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.status = 201
        self.body: Any = {"status": 1, "key": "abc123"}
        self.headers = {
            "X-Limit-App-Limit": "10000",
            "X-Limit-App-Remaining": "9895",
            "X-Limit-App-Reset": "234512",
        }
        self.delay = 0.0

    def respond(self, status: int, body: Any, headers: dict[str, str] | None = None) -> None:
        self.status, self.body = status, body
        if headers is not None:
            self.headers = headers

    @property
    def last(self) -> dict[str, Any]:
        return self.requests[-1]


@pytest.fixture
def api():
    fake = FakeAPI()

    class Handler(BaseHTTPRequestHandler):
        def _handle(self) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length else b""
            fake.requests.append(
                {
                    "method": self.command,
                    "path": self.path,
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "json": json.loads(raw) if raw else None,
                }
            )
            if fake.delay:
                import time

                time.sleep(fake.delay)
            payload = fake.body if isinstance(fake.body, bytes) else json.dumps(fake.body).encode()
            self.send_response(fake.status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            for key, value in fake.headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

        do_GET = do_POST = do_PUT = _handle

        def log_message(self, *args: Any) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    fake.url = f"http://127.0.0.1:{server.server_address[1]}"
    yield fake
    server.shutdown()
    server.server_close()
