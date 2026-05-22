from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any
from urllib.parse import parse_qs

from interview_prep.services.read_facade import ReadOnlyApplicationFacade

HeaderList = list[tuple[str, str]]
StartResponse = Callable[[str, HeaderList], object]
WsgiEnviron = dict[str, Any]


class ReadOnlyWebApp:
    """Minimal WSGI adapter over the read-only application facade."""

    def __init__(self, read: ReadOnlyApplicationFacade):
        self._read = read

    def __call__(self, environ: WsgiEnviron, start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = _normalize_path(str(environ.get("PATH_INFO", "/")))

        if method != "GET":
            return _json_response(start_response, 405, {"error": "method_not_allowed"})

        if path in {"/health", "/api/health"}:
            return _json_response(start_response, 200, {"ok": True, "service": "interview-prep"})
        if path == "/api/smoke":
            topics = self._read.topics()
            return _json_response(
                start_response,
                200,
                {
                    "ok": True,
                    "service": "interview-prep",
                    "read_only": True,
                    "topics_count": len(topics),
                },
            )
        if path == "/api/dashboard":
            limit = _query_int(environ, "limit", default=10, minimum=1, maximum=50)
            return _json_response(start_response, 200, self._read.dashboard(limit=limit))

        return _json_response(start_response, 404, {"error": "not_found"})


def create_web_app(read: ReadOnlyApplicationFacade) -> ReadOnlyWebApp:
    return ReadOnlyWebApp(read)


def _normalize_path(path: str) -> str:
    if not path.startswith("/"):
        path = f"/{path}"
    if len(path) > 1:
        return path.rstrip("/")
    return path


def _query_int(
    environ: WsgiEnviron,
    name: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    values = parse_qs(str(environ.get("QUERY_STRING", ""))).get(name)
    if not values:
        return default
    try:
        value = int(values[0])
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


def _json_response(
    start_response: StartResponse,
    status_code: int,
    payload: dict[str, Any],
) -> list[bytes]:
    body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    headers = [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]
    start_response(_status_line(status_code), headers)
    return [body]


def _status_line(status_code: int) -> str:
    reasons = {
        200: "OK",
        404: "Not Found",
        405: "Method Not Allowed",
    }
    return f"{status_code} {reasons[status_code]}"
