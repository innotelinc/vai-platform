"""Minimal local OpenAI-compatible 9Router gateway for Ollama.

The interview stack uses this service as its stable LLM endpoint. Keeping the
router as a small stdlib-only process makes the deployment reproducible and
keeps the model server private on the Docker network. It forwards the OpenAI
chat-completions and models APIs without buffering streaming responses.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


HOST = "0.0.0.0"
PORT = int(os.getenv("ROUTER_PORT", "20128"))
UPSTREAM = os.getenv("OLLAMA_UPSTREAM", "http://ollama:11434").rstrip("/")


class RouterHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: object) -> None:
        print(f"9router: {format % args}", flush=True)

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length) if length else None
        headers = {
            key: value
            for key, value in self.headers.items()
            if key.lower() not in {"host", "content-length", "connection"}
        }
        request = Request(
            f"{UPSTREAM}{self.path}",
            data=body,
            headers=headers,
            method=self.command,
        )
        try:
            with urlopen(request, timeout=600) as response:
                self.send_response(response.status)
                for key, value in response.headers.items():
                    if key.lower() not in {"content-length", "transfer-encoding", "connection"}:
                        self.send_header(key, value)
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                while True:
                    chunk = response.read(64 * 1024)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self._json(exc.code, {"error": {"message": detail, "type": "upstream_error"}})
        except (URLError, TimeoutError, OSError) as exc:
            self._json(502, {"error": {"message": str(exc), "type": "upstream_unavailable"}})

    def do_GET(self) -> None:
        if self.path == "/health":
            try:
                with urlopen(f"{UPSTREAM}/api/tags", timeout=5):
                    self._json(200, {"status": "ok", "upstream": UPSTREAM})
            except (URLError, TimeoutError, OSError) as exc:
                self._json(503, {"status": "unavailable", "error": str(exc)})
            return
        self._proxy()

    def do_POST(self) -> None:
        self._proxy()


if __name__ == "__main__":
    print(f"9router: listening on {HOST}:{PORT}, upstream={UPSTREAM}", flush=True)
    ThreadingHTTPServer((HOST, PORT), RouterHandler).serve_forever()
