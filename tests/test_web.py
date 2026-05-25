from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta
from typing import Any

from interview_prep.domain.models import Answer, ManualNote, NotebookEntry, QuestionCompetencyLink, Session, SessionOutcome
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


def call_wsgi_raw(
    app: Any,
    path: str,
    *,
    method: str = "GET",
    query_string: str = "",
) -> tuple[str, dict[str, str], str]:
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
    return response["status"], response["headers"], body.decode("utf-8")


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

    def test_read_only_web_adapter_exposes_html_smoke_page(self) -> None:
        services = AppServices(db_path=":memory:", config_path=None)
        try:
            app = create_web_app(services.read)
            before_stats = services.repository.stats()

            status, headers, body = call_wsgi_raw(app, "/")
            smoke_status, smoke_headers, smoke_body = call_wsgi_raw(app, "/smoke")

            after_stats = services.repository.stats()
        finally:
            services.close()

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        self.assertIn("<title>Interview Prep diagnostics</title>", body)
        self.assertIn("The TUI remains the primary interface.", body)
        self.assertIn('href="/api/dashboard"', body)
        self.assertIn('href="/api/readiness"', body)
        self.assertIn('href="/api/competencies"', body)
        self.assertIn('href="/api/notebook"', body)
        self.assertEqual(smoke_status, "200 OK")
        self.assertEqual(smoke_headers["Content-Type"], "text/html; charset=utf-8")
        self.assertEqual(smoke_body, body)
        self.assertEqual(before_stats["session_count"], after_stats["session_count"])
        self.assertEqual(before_stats["answered_count"], after_stats["answered_count"])

    def test_read_only_web_adapter_exposes_readiness_json(self) -> None:
        services = AppServices(db_path=":memory:", config_path=None)
        try:
            app = create_web_app(services.read)
            before_stats = services.repository.stats()

            status, headers, readiness = call_wsgi(app, "/api/readiness")

            after_stats = services.repository.stats()
        finally:
            services.close()

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("overall_summary", readiness)
        self.assertIn("competencies", readiness)
        self.assertIn("recommended_drill", readiness["overall_summary"])
        self.assertGreater(readiness["competency_count"], 0)
        self.assertEqual(before_stats["session_count"], after_stats["session_count"])
        self.assertEqual(before_stats["answered_count"], after_stats["answered_count"])

    def test_read_only_web_adapter_exposes_competencies_with_readiness_metadata(self) -> None:
        services = AppServices(db_path=":memory:", config_path=None)
        try:
            app = create_web_app(services.read)
            before_stats = services.repository.stats()

            status, headers, payload = call_wsgi(app, "/api/competencies")

            after_stats = services.repository.stats()
        finally:
            services.close()

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("generated_at", payload)
        self.assertGreater(payload["competency_count"], 0)
        self.assertEqual(payload["competency_count"], len(payload["competencies"]))
        self.assertIn("covered_competency_count", payload)
        self.assertIn("evaluated_competency_count", payload)
        first_competency = payload["competencies"][0]
        self.assertIn("competency", first_competency)
        self.assertIn("slug", first_competency["competency"])
        self.assertIn("linked_questions", first_competency)
        self.assertIn("answer_coverage", first_competency)
        self.assertIn("readiness_score", first_competency)
        self.assertIn("readiness_reasons", first_competency)
        self.assertEqual(before_stats["session_count"], after_stats["session_count"])
        self.assertEqual(before_stats["answered_count"], after_stats["answered_count"])

    def test_read_only_web_adapter_exposes_notebook_with_filters(self) -> None:
        services = AppServices(db_path=":memory:", config_path=None)
        try:
            runtime_topic = services.repository.find_topic_by_slug("python-runtime")
            async_topic = services.repository.find_topic_by_slug("async-backend")
            self.assertIsNotNone(runtime_topic)
            self.assertIsNotNone(async_topic)
            assert runtime_topic is not None
            assert async_topic is not None
            runtime_competency = services.repository.find_competency_by_slug("python-runtime")
            self.assertIsNotNone(runtime_competency)
            assert runtime_competency is not None
            runtime_question = services.repository.list_questions(runtime_topic.id or 0)[0]
            services.repository.set_question_competencies(
                runtime_question.id or 0,
                [QuestionCompetencyLink(competency=runtime_competency, is_primary=True, weight=1.0)],
            )
            started_at = datetime(2026, 5, 25, 10, 0, 0)
            runtime_entry = services.repository.add_notebook_entry(
                NotebookEntry(
                    id=None,
                    topic_id=runtime_topic.id or 0,
                    curriculum_subtopic_id=None,
                    dialog_session_id="learn-api-1",
                    source_message_id=None,
                    title="Runtime notebook",
                    body="Descriptor lookup note.",
                    source="learning-ai",
                    created_at=started_at,
                )
            )
            services.repository.add_notebook_entry(
                NotebookEntry(
                    id=None,
                    topic_id=async_topic.id or 0,
                    curriculum_subtopic_id=None,
                    dialog_session_id="learn-api-2",
                    source_message_id=None,
                    title="Async notebook",
                    body="Backpressure note.",
                    source="learning-ai",
                    created_at=started_at + timedelta(minutes=1),
                )
            )
            manual_note = services.repository.add_manual_note(
                ManualNote(
                    id=None,
                    topic_id=runtime_topic.id,
                    session_id=None,
                    context_type="manual",
                    context_id=None,
                    title="Runtime manual note",
                    body="User-authored runtime note.",
                    created_at=started_at + timedelta(minutes=2),
                    updated_at=started_at + timedelta(minutes=2),
                )
            )
            services.repository.add_manual_note(
                ManualNote(
                    id=None,
                    topic_id=runtime_topic.id,
                    session_id=None,
                    context_type="tui-notes-draft",
                    context_id=None,
                    title="TUI notes draft",
                    body="Internal draft should stay hidden.",
                    created_at=started_at + timedelta(minutes=3),
                    updated_at=started_at + timedelta(minutes=3),
                )
            )
            app = create_web_app(services.read)
            before_stats = services.repository.stats()

            topic_status, headers, topic_payload = call_wsgi(
                app,
                "/api/notebook",
                query_string=f"topic={runtime_topic.id}",
            )
            competency_status, _, competency_payload = call_wsgi(
                app,
                "/api/notebook",
                query_string="competency=python-runtime",
            )
            session_status, _, session_payload = call_wsgi(
                app,
                "/api/notebook",
                query_string="session=learn-api-1",
            )

            after_stats = services.repository.stats()
        finally:
            services.close()

        self.assertEqual(topic_status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(topic_payload["filters"]["topic_id"], runtime_topic.id)
        self.assertEqual([entry["id"] for entry in topic_payload["entries"]], [runtime_entry.id])
        self.assertEqual([note["id"] for note in topic_payload["manual_notes"]], [manual_note.id])
        self.assertEqual(competency_status, "200 OK")
        self.assertEqual([entry["title"] for entry in competency_payload["entries"]], ["Runtime notebook"])
        self.assertEqual([note["title"] for note in competency_payload["manual_notes"]], ["Runtime manual note"])
        self.assertEqual(session_status, "200 OK")
        self.assertEqual(session_payload["filters"]["session"], "learn-api-1")
        self.assertEqual([entry["id"] for entry in session_payload["entries"]], [runtime_entry.id])
        self.assertEqual(session_payload["manual_notes"], [])
        self.assertEqual(before_stats["session_count"], after_stats["session_count"])
        self.assertEqual(before_stats["answered_count"], after_stats["answered_count"])

    def test_read_only_web_adapter_exposes_completed_session_detail_with_outcome(self) -> None:
        services = AppServices(db_path=":memory:", config_path=None)
        try:
            topic = services.repository.find_topic_by_slug("python-runtime")
            self.assertIsNotNone(topic)
            assert topic is not None
            question = services.repository.list_questions(topic.id)[0]
            started_at = datetime(2026, 5, 25, 9, 0, 0)
            session = services.repository.create_session(
                Session(
                    id=None,
                    topic_id=topic.id,
                    started_at=started_at,
                    ended_at=None,
                    target_minutes=60,
                )
            )
            services.repository.add_answer(
                Answer(
                    id=None,
                    session_id=session.id or 0,
                    question_id=question.id or 0,
                    user_answer="Descriptors control attribute access.",
                    self_score=4,
                    ai_feedback="Feedback text.",
                    answered_at=started_at + timedelta(minutes=5),
                )
            )
            services.repository.finish_session(session.id or 0, started_at + timedelta(minutes=20))
            outcome = services.repository.upsert_session_outcome(
                SessionOutcome(
                    id=None,
                    session_id=session.id or 0,
                    summary="Уверенный ответ с понятным следующим drill.",
                    strengths=["Объяснил descriptor protocol."],
                    gaps=["Добавить production examples."],
                    next_drills=["Повторить descriptors in ORMs."],
                    readiness_delta=0.1,
                    created_at=started_at + timedelta(minutes=21),
                )
            )
            app = create_web_app(services.read)
            before_stats = services.repository.stats()

            status, headers, payload = call_wsgi(app, f"/api/sessions/{session.id}")
            missing_status, _, missing = call_wsgi(app, "/api/sessions/9999")
            invalid_status, _, invalid = call_wsgi(app, "/api/sessions/not-a-number")

            after_stats = services.repository.stats()
        finally:
            services.close()

        self.assertEqual(status, "200 OK")
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(payload["summary"]["id"], session.id)
        self.assertEqual(payload["summary"]["topic_title"], topic.title)
        self.assertEqual(payload["answers"][0]["question_id"], question.id)
        self.assertEqual(payload["answers"][0]["user_answer"], "Descriptors control attribute access.")
        self.assertEqual(payload["outcome"]["id"], outcome.id)
        self.assertEqual(payload["outcome"]["summary"], "Уверенный ответ с понятным следующим drill.")
        self.assertEqual(payload["outcome"]["next_drills"], ["Повторить descriptors in ORMs."])
        self.assertEqual(missing_status, "404 Not Found")
        self.assertEqual(missing["error"], "session_not_found")
        self.assertEqual(invalid_status, "400 Bad Request")
        self.assertEqual(invalid["error"], "invalid_session_id")
        self.assertEqual(before_stats["session_count"], after_stats["session_count"])
        self.assertEqual(before_stats["answered_count"], after_stats["answered_count"])

    def test_read_only_web_adapter_validates_notebook_query_params(self) -> None:
        services = AppServices(db_path=":memory:", config_path=None)
        try:
            app = create_web_app(services.read)
            before_stats = services.repository.stats()

            invalid_topic_status, _, invalid_topic = call_wsgi(
                app,
                "/api/notebook",
                query_string="topic=not-a-number",
            )
            invalid_limit_status, _, invalid_limit = call_wsgi(
                app,
                "/api/notebook",
                query_string="limit=0",
            )
            too_large_limit_status, _, too_large_limit = call_wsgi(
                app,
                "/api/notebook",
                query_string="limit=101",
            )
            valid_status, _, valid_payload = call_wsgi(
                app,
                "/api/notebook",
                query_string="topic=1&limit=1",
            )

            after_stats = services.repository.stats()
        finally:
            services.close()

        self.assertEqual(invalid_topic_status, "400 Bad Request")
        self.assertEqual(invalid_topic["error"], "invalid_topic")
        self.assertEqual(invalid_limit_status, "400 Bad Request")
        self.assertEqual(invalid_limit["error"], "invalid_limit")
        self.assertEqual(too_large_limit_status, "400 Bad Request")
        self.assertEqual(too_large_limit["error"], "invalid_limit")
        self.assertEqual(valid_status, "200 OK")
        self.assertEqual(valid_payload["filters"]["topic_id"], 1)
        self.assertEqual(before_stats["session_count"], after_stats["session_count"])
        self.assertEqual(before_stats["answered_count"], after_stats["answered_count"])
