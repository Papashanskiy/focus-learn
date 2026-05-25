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

        if path in {"/", "/smoke"}:
            return _html_response(start_response, 200, self._smoke_page_html())
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
        if path == "/api/readiness":
            return _json_response(start_response, 200, self._read.readiness())
        if path == "/api/competencies":
            return _json_response(start_response, 200, self._read.competency_readiness())
        if path == "/api/notebook":
            try:
                limit = _query_int(environ, "limit", default=50, minimum=1, maximum=100, strict=True)
                topic_id = _optional_query_int(environ, "topic", error="invalid_topic")
            except QueryParamError as error:
                return _json_response(start_response, 400, {"error": error.code})
            competency = _query_string(environ, "competency")
            session = _query_string(environ, "session")
            return _json_response(
                start_response,
                200,
                self._read.notebook(
                    topic_id=topic_id,
                    competency_slug=competency,
                    session=session,
                    limit=limit,
                ),
            )
        if path.startswith("/api/sessions/"):
            session_id_text = path.removeprefix("/api/sessions/")
            try:
                session_id = int(session_id_text)
            except ValueError:
                return _json_response(start_response, 400, {"error": "invalid_session_id"})
            detail = self._read.completed_session_detail(session_id)
            if detail is None:
                return _json_response(start_response, 404, {"error": "session_not_found"})
            return _json_response(start_response, 200, detail)

        return _json_response(start_response, 404, {"error": "not_found"})

    def _smoke_page_html(self) -> str:
        dashboard = self._read.dashboard(limit=5)
        readiness = dashboard.get("readiness", {})
        stats = dashboard.get("stats", {})
        topics = dashboard.get("topics", [])
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Interview Prep diagnostics</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 760px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5; }}
    code {{ background: #f4f4f4; padding: 0.1rem 0.3rem; }}
    li {{ margin: 0.35rem 0; }}
  </style>
</head>
<body>
  <main>
    <h1>Interview Prep diagnostics</h1>
    <p>This read-only page is a smoke check for the future web adapter. The TUI remains the primary interface.</p>
    <dl>
      <dt>Topics</dt><dd>{len(topics)}</dd>
      <dt>Sessions</dt><dd>{stats.get("session_count", 0)}</dd>
      <dt>Answered questions</dt><dd>{stats.get("answered_count", 0)}</dd>
      <dt>Competencies</dt><dd>{readiness.get("competency_count", 0)}</dd>
    </dl>
    <h2>JSON endpoints</h2>
    <ul>
      <li><a href="/api/smoke"><code>/api/smoke</code></a></li>
      <li><a href="/api/dashboard"><code>/api/dashboard</code></a></li>
      <li><a href="/api/readiness"><code>/api/readiness</code></a></li>
      <li><a href="/api/competencies"><code>/api/competencies</code></a></li>
      <li><a href="/api/notebook"><code>/api/notebook</code></a></li>
    </ul>
  </main>
</body>
</html>
"""


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
    strict: bool = False,
) -> int:
    values = parse_qs(str(environ.get("QUERY_STRING", ""))).get(name)
    if not values:
        return default
    try:
        value = int(values[0])
    except (TypeError, ValueError):
        if strict:
            raise QueryParamError(f"invalid_{name}")
        return default
    if strict and not minimum <= value <= maximum:
        raise QueryParamError(f"invalid_{name}")
    return max(minimum, min(maximum, value))


def _optional_query_int(environ: WsgiEnviron, name: str, *, error: str) -> int | None:
    value = _query_string(environ, name)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        raise QueryParamError(error)


def _query_string(environ: WsgiEnviron, name: str) -> str | None:
    values = parse_qs(str(environ.get("QUERY_STRING", ""))).get(name)
    if not values:
        return None
    value = values[0].strip()
    return value or None


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


def _html_response(
    start_response: StartResponse,
    status_code: int,
    html: str,
) -> list[bytes]:
    body = html.encode("utf-8")
    headers = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(body))),
    ]
    start_response(_status_line(status_code), headers)
    return [body]


def _status_line(status_code: int) -> str:
    reasons = {
        200: "OK",
        400: "Bad Request",
        404: "Not Found",
        405: "Method Not Allowed",
    }
    return f"{status_code} {reasons[status_code]}"


class QueryParamError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code
