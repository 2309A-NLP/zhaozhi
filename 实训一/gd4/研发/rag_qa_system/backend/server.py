"""Runnable HTTP server for the project."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from rag_qa_system.backend.api.http_api import HttpApi
from rag_qa_system.backend.utils.logger import get_logger


LOGGER = get_logger("rag.http")


class HttpRequestError(ValueError):
    def __init__(self, message: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        super().__init__(message)
        self.status = status


class RagRequestHandler(BaseHTTPRequestHandler):
    api: HttpApi
    frontend_dir: Path
    max_request_body_bytes: int = 80 * 1024 * 1024

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            LOGGER.info("http_request | method=GET | path=%s", parsed.path)
            if parsed.path == "/":
                self._serve_file(self.frontend_dir / "index.html", "text/html; charset=utf-8")
                return
            if parsed.path == "/app.js":
                self._serve_file(self.frontend_dir / "app.js", "application/javascript; charset=utf-8")
                return
            if parsed.path == "/styles.css":
                self._serve_file(self.frontend_dir / "styles.css", "text/css; charset=utf-8")
                return
            if parsed.path == "/api/health":
                self._write_json({"status": "ok"})
                return
            if parsed.path == "/api/files":
                self._write_json(self.api.get_files())
                return
            if parsed.path == "/api/stats":
                self._write_json(self.api.get_stats())
                return
            self._write_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except Exception:
            LOGGER.exception("http_failed | method=GET | path=%s", self.path)
            self._write_json({"error": "internal server error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            payload = self._read_json()
            LOGGER.info("http_request | method=POST | path=%s", parsed.path)
            if parsed.path == "/api/ask":
                self._write_json(self.api.post_answer(payload), status=self._status_from_payload)
                return
            if parsed.path == "/api/ingest-path":
                self._write_json(self.api.post_ingest_path(payload), status=self._status_from_payload)
                return
            if parsed.path == "/api/ingest-file":
                self._write_json(self.api.post_ingest_file(payload), status=self._status_from_payload)
                return
            self._write_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
        except HttpRequestError as exc:
            LOGGER.warning("http_bad_request | method=POST | path=%s | status=%s | error=%s", self.path, exc.status, exc)
            self._write_json({"error": str(exc)}, status=exc.status)
        except Exception:
            LOGGER.exception("http_failed | method=POST | path=%s", self.path)
            self._write_json({"error": "internal server error"}, status=HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _status_from_payload(self, payload: dict) -> HTTPStatus:
        return HTTPStatus.BAD_REQUEST if "error" in payload else HTTPStatus.OK

    def _read_json(self) -> dict:
        try:
            content_length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise HttpRequestError("invalid content length") from exc
        if content_length > self.max_request_body_bytes:
            raise HttpRequestError("request body is too large", status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        raw_body = self.rfile.read(content_length) if content_length else b"{}"
        if not raw_body:
            return {}
        try:
            return json.loads(raw_body.decode("utf-8"))
        except UnicodeDecodeError as exc:
            LOGGER.warning("http_bad_encoding | path=%s | error=%s", self.path, exc)
            raise HttpRequestError("request body must be utf-8") from exc
        except json.JSONDecodeError as exc:
            LOGGER.warning("http_bad_json | path=%s | error=%s", self.path, exc)
            raise HttpRequestError("invalid json payload") from exc

    def _serve_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._write_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)
            return
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_json(self, payload: dict, status: HTTPStatus | Callable[[dict], HTTPStatus] = HTTPStatus.OK) -> None:
        if callable(status):
            status = status(payload)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(
    host: str,
    port: int,
    api: HttpApi,
    frontend_dir: Path,
    max_request_body_bytes: int = 80 * 1024 * 1024,
) -> ThreadingHTTPServer:
    handler = type(
        "ConfiguredRagRequestHandler",
        (RagRequestHandler,),
        {"api": api, "frontend_dir": frontend_dir, "max_request_body_bytes": max_request_body_bytes},
    )
    return ThreadingHTTPServer((host, port), handler)
