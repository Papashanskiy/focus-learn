from __future__ import annotations

import json
import unittest
from typing import Any

from interview_prep.services.app_factory import AppServices
from interview_prep.ui.web import create_web_app


def call_wsgi(
    app: Any,
    path: str,
    *,
    method: str = "GET",
    query_string: str = "",
) -> tuple[str, dict[str, str], dict[str, Any]]:
    response: dict[str, Any] = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        response["status"] = status
        response["headers"] = dict(headers)

    body = b"".join(
        app(
            {
                "REQUEST_METHOD": method,
                "PATH_INFO": path,
                "QUERY_STRING": query_string,
            },
            start_response,
        )
    )
    return response["status"], response["headers"], json.loads(body.decode("utf-8"))


class WebAdapterTests(unittest.TestCase):
    def test_read_only_web_adapter_exposes_smoke_and_dashboard_json(self) -> None:
        services = AppServices(db_path=":memory:", config_path=None)
        try:
            app = create_web_app(services.read)
            before_stats = services.repository.stats()

            smoke_status, smoke_headers, smoke = call_wsgi(app, "/api/smoke")
            dashboard_status, dashboard_headers, dashboard = call_wsgi(
                app,
                "/api/dashboard",
                query_string="limit=1",
            )
            not_found_status, _, not_found = call_wsgi(app, "/missing")
            method_status, _, method_error = call_wsgi(app, "/api/smoke", method="POST")

            after_stats = services.repository.stats()
        finally:
            services.close()

        self.assertEqual(smoke_status, "200 OK")
        self.assertEqual(smoke_headers["Content-Type"], "application/json; charset=utf-8")
        self.assertTrue(smoke["ok"])
        self.assertTrue(smoke["read_only"])
        self.assertGreater(smoke["topics_count"], 0)

        self.assertEqual(dashboard_status, "200 OK")
        self.assertEqual(dashboard_headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("stats", dashboard)
        self.assertIn("topics", dashboard)
        self.assertIn("readiness", dashboard)
        self.assertIn("overall_summary", dashboard["readiness"])
        self.assertIn("competencies", dashboard["readiness"])
        self.assertIn("recommended_drill", dashboard["readiness"]["overall_summary"])
        self.assertGreater(dashboard["readiness"]["competency_count"], 0)
        self.assertEqual(before_stats["session_count"], after_stats["session_count"])
        self.assertEqual(before_stats["answered_count"], after_stats["answered_count"])

        self.assertEqual(not_found_status, "404 Not Found")
        self.assertEqual(not_found["error"], "not_found")
        self.assertEqual(method_status, "405 Method Not Allowed")
        self.assertEqual(method_error["error"], "method_not_allowed")
