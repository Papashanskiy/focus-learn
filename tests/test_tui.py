from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from textual.containers import VerticalScroll
from textual.widgets import Button, OptionList, TextArea

from datetime import datetime, timedelta

from interview_prep.domain.models import (
    Answer,
    CurriculumSubtopic,
    CurriculumTopic,
    LearningDialogMessage,
    LearningMaterial,
    ManualNote,
    NotebookEntry,
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_ARCHIVED,
    QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
    Question,
    QuestionCompetencyLink,
    SESSION_STATUS_ABANDONED,
    SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
    Session,
    SessionOutcome,
    SystemDesignArtifact,
    SystemDesignFeedbackArtifact,
    SystemDesignScenario,
    SystemDesignTranscriptMessage,
    Tag,
    Topic,
)
from interview_prep.services.learning_service import LearningService
from interview_prep.services.session_service import (
    FEEDBACK_FALLBACK_FLAG,
    FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG,
    FeedbackQuality,
    GeneratedFeedback,
)
from interview_prep.services.system_design_service import DEFAULT_SYSTEM_DESIGN_SCENARIO, SystemDesignService
from interview_prep.ui.content_worker_controller import ContentWorkerOrchestrator, PAUSED_MESSAGE
from interview_prep.ui.learning_controller import (
    LEARNING_ENTRY_FEEDBACK,
    build_learning_entry_snapshot,
    build_learning_finish_snapshot,
    build_learning_request_snapshot,
    resolve_learning_context_topic_id,
)
from interview_prep.ui.practice_controller import (
    build_practice_answer_scoring_snapshot,
    build_practice_answered_snapshot,
    build_practice_next_question_snapshot,
    build_practice_session_reset_snapshot,
    build_practice_session_start_snapshot,
    decide_practice_submit,
    parse_practice_self_score,
)
from interview_prep.ui.system_design_controller import (
    SYSTEM_DESIGN_ENTRY_FEEDBACK,
    build_system_design_checkpoint_finish_snapshot,
    build_system_design_checkpoint_loading_snapshot,
    build_system_design_entry_snapshot,
    build_system_design_feedback_finish_snapshot,
    build_system_design_feedback_loading_snapshot,
    build_system_design_finish_turn_snapshot,
    build_system_design_pressure_finish_snapshot,
    build_system_design_pressure_loading_snapshot,
    build_system_design_request_snapshot,
)
from interview_prep.ui.tui import (
    Composer,
    InterviewPrepTUI,
    command_palette_text,
    content_artifact_id_label,
    extract_system_design_artifact_commands,
    format_feedback_quality_warning,
    format_duration,
    notes_line_count,
    one_line_preview,
    render_chat_message,
    render_llm_markdown,
)


class PracticeControllerTests(unittest.TestCase):
    def test_decide_practice_submit_routes_topic_selection_and_answering(self) -> None:
        self.assertEqual(decide_practice_submit("select_topic", "").action, "start_today_drill")

        topic_decision = decide_practice_submit("select_topic", "3")
        self.assertIsNotNone(topic_decision)
        assert topic_decision is not None
        self.assertEqual(topic_decision.action, "start_topic_session")
        self.assertEqual(topic_decision.value, "3")

        empty_answer = decide_practice_submit("answering", "")
        self.assertIsNotNone(empty_answer)
        assert empty_answer is not None
        self.assertEqual(empty_answer.action, "empty_answer")

        answer_decision = decide_practice_submit("answering", "Мой ответ")
        self.assertIsNotNone(answer_decision)
        assert answer_decision is not None
        self.assertEqual(answer_decision.action, "capture_answer")
        self.assertEqual(answer_decision.value, "Мой ответ")

    def test_decide_practice_submit_routes_scoring_and_answered_steps(self) -> None:
        score_decision = decide_practice_submit("scoring", "4")
        self.assertIsNotNone(score_decision)
        assert score_decision is not None
        self.assertEqual(score_decision.action, "capture_score")
        self.assertEqual(score_decision.value, "4")

        blank_score = decide_practice_submit("scoring", "")
        self.assertIsNotNone(blank_score)
        assert blank_score is not None
        self.assertEqual(blank_score.action, "capture_score")
        self.assertEqual(blank_score.value, "")

        next_question = decide_practice_submit("answered", "")
        self.assertIsNotNone(next_question)
        assert next_question is not None
        self.assertEqual(next_question.action, "next_question")

        replacement_answer = decide_practice_submit("answered", "Дополнительный ответ")
        self.assertIsNotNone(replacement_answer)
        assert replacement_answer is not None
        self.assertEqual(replacement_answer.action, "capture_answer")
        self.assertEqual(replacement_answer.value, "Дополнительный ответ")

    def test_decide_practice_submit_ignores_non_practice_modes(self) -> None:
        for mode in ["learning", "content", "loading_feedback", "history", "readiness"]:
            with self.subTest(mode=mode):
                self.assertIsNone(decide_practice_submit(mode, "text"))

    def test_build_practice_session_start_snapshot_resets_question_flow(self) -> None:
        started_at = datetime(2026, 5, 22, 9, 0, 0)
        session = Session(id=7, topic_id=3, started_at=started_at, target_minutes=60)
        topic = Topic(
            id=3,
            slug="python-runtime",
            title="Python runtime",
            description="Runtime internals",
            level="middle+",
        )

        snapshot = build_practice_session_start_snapshot(session, topic)

        self.assertIs(snapshot.session, session)
        self.assertIs(snapshot.topic, topic)
        self.assertIsNone(snapshot.question)
        self.assertIsNone(snapshot.current_answer)
        self.assertIsNone(snapshot.pending_answer_text)
        self.assertEqual(snapshot.started_at, started_at)
        self.assertEqual(snapshot.answered_count, 0)
        self.assertEqual(snapshot.skipped_count, 0)
        self.assertEqual(snapshot.skipped_question_ids, frozenset())
        self.assertFalse(snapshot.showing_hint)
        self.assertFalse(snapshot.showing_reference)
        self.assertEqual(snapshot.mode, "answering")
        self.assertIsNone(snapshot.generated_learning_material)
        self.assertIsNone(snapshot.generated_learning_material_topic_id)

    def test_build_practice_session_reset_snapshot_returns_topic_selection_state(self) -> None:
        snapshot = build_practice_session_reset_snapshot()

        self.assertIsNone(snapshot.session)
        self.assertIsNone(snapshot.topic)
        self.assertIsNone(snapshot.question)
        self.assertIsNone(snapshot.current_answer)
        self.assertIsNone(snapshot.pending_answer_text)
        self.assertIsNone(snapshot.started_at)
        self.assertEqual(snapshot.answered_count, 0)
        self.assertEqual(snapshot.skipped_count, 0)
        self.assertEqual(snapshot.skipped_question_ids, frozenset())
        self.assertFalse(snapshot.showing_hint)
        self.assertFalse(snapshot.showing_reference)
        self.assertFalse(snapshot.command_palette_visible)
        self.assertEqual(snapshot.mode, "select_topic")

    def test_build_practice_answer_scoring_snapshot_moves_saved_answer_to_scoring(self) -> None:
        answer = Answer(
            id=11,
            session_id=7,
            question_id=3,
            user_answer="Дескриптор управляет доступом к атрибуту.",
            self_score=None,
            ai_feedback=None,
            answered_at=datetime(2026, 5, 22, 10, 0, 0),
        )

        snapshot = build_practice_answer_scoring_snapshot(answer, answered_count=2)

        self.assertIs(snapshot.current_answer, answer)
        self.assertEqual(snapshot.pending_answer_text, answer.user_answer)
        self.assertEqual(snapshot.answered_count, 2)
        self.assertTrue(snapshot.showing_reference)
        self.assertEqual(snapshot.mode, "scoring")

    def test_practice_self_score_contract_moves_scoring_to_answered(self) -> None:
        self.assertEqual(parse_practice_self_score("").score, None)
        self.assertEqual(parse_practice_self_score("4").score, 4)
        self.assertEqual(
            parse_practice_self_score("high").error,
            "Самооценка должна быть числом 1-5 или пустой строкой.",
        )
        self.assertEqual(
            parse_practice_self_score("6").error,
            "Самооценка должна быть от 1 до 5.",
        )

        scored_answer = Answer(
            id=12,
            session_id=7,
            question_id=3,
            user_answer="Дескриптор управляет доступом к атрибуту.",
            self_score=4,
            ai_feedback=None,
            answered_at=datetime(2026, 5, 22, 10, 0, 0),
        )

        snapshot = build_practice_answered_snapshot(scored_answer)

        self.assertIs(snapshot.current_answer, scored_answer)
        self.assertTrue(snapshot.showing_reference)
        self.assertEqual(snapshot.mode, "answered")

    def test_build_practice_next_question_snapshot_resets_answer_state(self) -> None:
        question = Question(
            id=21,
            topic_id=1,
            difficulty="middle+",
            prompt="Как descriptor protocol влияет на lookup?",
            hint="Вспомни __get__.",
            reference_answer="Descriptor участвует в поиске атрибутов.",
            source="test",
        )

        snapshot = build_practice_next_question_snapshot(question)

        self.assertIs(snapshot.question, question)
        self.assertIsNone(snapshot.current_answer)
        self.assertIsNone(snapshot.pending_answer_text)
        self.assertEqual(snapshot.last_feedback, "")
        self.assertFalse(snapshot.showing_hint)
        self.assertFalse(snapshot.showing_reference)
        self.assertEqual(snapshot.mode, "answering")


class ContentWorkerControllerTests(unittest.TestCase):
    def test_pause_resume_and_start_decisions_update_worker_state(self) -> None:
        worker = ContentWorkerOrchestrator()

        start = worker.request_start()
        self.assertTrue(start.should_start_thread)
        self.assertTrue(worker.running)
        self.assertEqual(worker.status, "generating...")

        pause = worker.pause()
        self.assertFalse(pause.should_start_thread)
        self.assertTrue(worker.paused)
        self.assertEqual(worker.status, "paused")
        self.assertEqual(
            pause.history_message,
            "TUI content worker поставлен на паузу после текущей running-задачи.",
        )

        worker.running = False
        paused_start = worker.request_start()
        self.assertFalse(paused_start.should_start_thread)
        self.assertEqual(paused_start.history_message, PAUSED_MESSAGE)

        resume = worker.resume()
        self.assertTrue(resume.should_start_thread)
        self.assertFalse(worker.paused)
        self.assertEqual(worker.status, "idle")
        self.assertEqual(resume.history_message, "TUI content worker возобновлен.")

    def test_start_is_noop_while_worker_is_running(self) -> None:
        worker = ContentWorkerOrchestrator()
        worker.request_start()

        second_start = worker.request_start()

        self.assertFalse(second_start.should_start_thread)
        self.assertFalse(second_start.should_render)
        self.assertEqual(worker.status, "generating...")

    def test_process_available_jobs_stops_after_empty_queue_or_limit(self) -> None:
        class FakeContentGeneration:
            def __init__(self) -> None:
                self.calls = 0

            def process_next_job(self):
                self.calls += 1
                if self.calls > 2:
                    return None
                return f"job-{self.calls}"

        class FakeLLM:
            last_error = "fallback used"

        worker = ContentWorkerOrchestrator()
        content_generation = FakeContentGeneration()

        run = worker.process_available_jobs(content_generation, FakeLLM(), limit=3)

        self.assertEqual(run.results, ("job-1", "job-2"))
        self.assertEqual(run.last_error, "fallback used")
        self.assertEqual(content_generation.calls, 3)

    def test_process_available_jobs_captures_processing_exception(self) -> None:
        class FailingContentGeneration:
            def process_next_job(self):
                raise RuntimeError("database locked")

        worker = ContentWorkerOrchestrator()

        run = worker.process_available_jobs(FailingContentGeneration(), object())

        self.assertEqual(run.results, ())
        self.assertEqual(run.last_error, "database locked")

    def test_finish_run_normalizes_results_and_updates_status(self) -> None:
        worker = ContentWorkerOrchestrator()
        worker.running = True
        done_result = SimpleNamespace(job=SimpleNamespace(status="done"))
        failed_result = SimpleNamespace(job=SimpleNamespace(status="failed"))

        empty = worker.finish_run(None)
        self.assertFalse(worker.running)
        self.assertEqual(empty.results, ())
        self.assertEqual(empty.status, "idle")
        self.assertEqual(empty.history_message, "Автогенерация контента: задач в очереди нет.")

        done = worker.finish_run([done_result])
        self.assertEqual(done.results, (done_result,))
        self.assertEqual(done.status, "done 1 job(s)")
        self.assertEqual(worker.status, "done 1 job(s)")

        failed = worker.finish_run((done_result, failed_result))
        self.assertEqual(failed.status, "failed")
        self.assertEqual(failed.results, (done_result, failed_result))

    def test_finish_run_keeps_paused_status_after_result(self) -> None:
        worker = ContentWorkerOrchestrator()
        worker.running = True
        worker.paused = True
        done_result = SimpleNamespace(job=SimpleNamespace(status="done"))

        finish = worker.finish_run(done_result)

        self.assertFalse(worker.running)
        self.assertEqual(finish.results, (done_result,))
        self.assertEqual(finish.status, "paused")
        self.assertEqual(worker.status, "paused")

    def test_mark_unmounted_clears_running_state(self) -> None:
        worker = ContentWorkerOrchestrator()
        worker.request_start()

        worker.mark_unmounted()

        self.assertFalse(worker.running)
        self.assertEqual(worker.status, "idle")


class LearningControllerTests(unittest.TestCase):
    def test_resolve_learning_context_topic_id_keeps_pre_topic_learning_topicless(self) -> None:
        self.assertIsNone(
            resolve_learning_context_topic_id(
                source_mode="select_topic",
                current_topic_id=1,
                session_topic_id=None,
                has_session=False,
            )
        )

        self.assertEqual(
            resolve_learning_context_topic_id(
                source_mode="answering",
                current_topic_id=1,
                session_topic_id=2,
                has_session=True,
            ),
            1,
        )

        self.assertEqual(
            resolve_learning_context_topic_id(
                source_mode="answered",
                current_topic_id=None,
                session_topic_id=2,
                has_session=True,
            ),
            2,
        )

    def test_build_learning_entry_snapshot_starts_topicless_learning_cleanly(self) -> None:
        snapshot = build_learning_entry_snapshot(
            current_mode="select_topic",
            current_topic_id=1,
            session_topic_id=None,
            has_session=False,
            current_learning_return_mode="answering",
            current_learning_dialog_session_id="old-session",
            generated_learning_material="stale material",
            generated_learning_material_topic_id=1,
            new_dialog_session_id="new-learning-session",
        )

        self.assertEqual(snapshot.learning_return_mode, "select_topic")
        self.assertEqual(snapshot.learning_dialog_session_id, "new-learning-session")
        self.assertIsNone(snapshot.learning_topic_id)
        self.assertTrue(snapshot.clear_current_practice_context)
        self.assertEqual(snapshot.mode, "learning")
        self.assertFalse(snapshot.command_palette_visible)
        self.assertEqual(snapshot.last_feedback, LEARNING_ENTRY_FEEDBACK)
        self.assertTrue(snapshot.should_clear_generated_learning_material)
        self.assertFalse(snapshot.should_ensure_learning_material)

    def test_build_learning_entry_snapshot_reuses_active_learning_session_and_material(self) -> None:
        snapshot = build_learning_entry_snapshot(
            current_mode="loading_learning",
            current_topic_id=3,
            session_topic_id=4,
            has_session=True,
            current_learning_return_mode="answering",
            current_learning_dialog_session_id="learn-existing",
            generated_learning_material="current material",
            generated_learning_material_topic_id=3,
            new_dialog_session_id="learn-new",
        )

        self.assertEqual(snapshot.learning_return_mode, "answering")
        self.assertEqual(snapshot.learning_dialog_session_id, "learn-existing")
        self.assertEqual(snapshot.learning_topic_id, 3)
        self.assertFalse(snapshot.clear_current_practice_context)
        self.assertFalse(snapshot.should_clear_generated_learning_material)
        self.assertFalse(snapshot.should_ensure_learning_material)

    def test_build_learning_entry_snapshot_requests_material_for_new_topic(self) -> None:
        snapshot = build_learning_entry_snapshot(
            current_mode="answering",
            current_topic_id=5,
            session_topic_id=5,
            has_session=True,
            current_learning_return_mode="select_topic",
            current_learning_dialog_session_id=None,
            generated_learning_material="other topic material",
            generated_learning_material_topic_id=4,
            new_dialog_session_id="learn-5",
        )

        self.assertEqual(snapshot.learning_return_mode, "answering")
        self.assertEqual(snapshot.learning_dialog_session_id, "learn-5")
        self.assertEqual(snapshot.learning_topic_id, 5)
        self.assertFalse(snapshot.clear_current_practice_context)
        self.assertFalse(snapshot.should_clear_generated_learning_material)
        self.assertTrue(snapshot.should_ensure_learning_material)

    def test_build_learning_request_snapshot_moves_question_to_loading_state(self) -> None:
        snapshot = build_learning_request_snapshot(
            user_message="Объясни descriptor lookup",
            current_learning_topic_id=3,
            current_learning_dialog_session_id="learn-existing",
            new_dialog_session_id="learn-new",
        )

        self.assertEqual(snapshot.learning_topic_id, 3)
        self.assertEqual(snapshot.learning_dialog_session_id, "learn-existing")
        self.assertEqual(snapshot.learning_question, "Объясни descriptor lookup")
        self.assertEqual(snapshot.learning_pending_message, "Объясни descriptor lookup")
        self.assertEqual(snapshot.learning_dialog_offset, 0)
        self.assertFalse(snapshot.command_palette_visible)
        self.assertEqual(snapshot.mode, "loading_learning")
        self.assertEqual(snapshot.ollama_status, "разбирает тему...")
        self.assertEqual(snapshot.last_feedback, "")
        self.assertEqual(snapshot.history_message, "Готовлю учебное объяснение через Ollama...")

    def test_build_learning_request_snapshot_creates_dialog_session_when_missing(self) -> None:
        snapshot = build_learning_request_snapshot(
            user_message="Что такое GIL?",
            current_learning_topic_id=None,
            current_learning_dialog_session_id=None,
            new_dialog_session_id="learn-created",
        )

        self.assertIsNone(snapshot.learning_topic_id)
        self.assertEqual(snapshot.learning_dialog_session_id, "learn-created")

    def test_build_learning_finish_snapshot_records_success_reply(self) -> None:
        snapshot = build_learning_finish_snapshot(
            explanation="Descriptor управляет доступом к атрибуту.",
            learning_question="Объясни descriptor lookup",
            last_error=None,
        )

        self.assertEqual(snapshot.ollama_status, "ok")
        self.assertEqual(snapshot.history_message, "Учебный разбор готов.")
        self.assertEqual(
            snapshot.transcript_entries,
            (
                ("Ты", "Объясни descriptor lookup"),
                ("ИИ", "Descriptor управляет доступом к атрибуту."),
            ),
        )
        self.assertEqual(snapshot.learning_pending_message, "")
        self.assertEqual(snapshot.learning_dialog_offset, 0)
        self.assertEqual(
            snapshot.last_feedback,
            "Учебный разбор\nВопрос: Объясни descriptor lookup\n\n"
            "Descriptor управляет доступом к атрибуту.",
        )
        self.assertEqual(snapshot.mode, "learning")

    def test_build_learning_finish_snapshot_records_fallback_without_empty_user_turn(self) -> None:
        snapshot = build_learning_finish_snapshot(
            explanation="Fallback разбор.",
            learning_question="",
            last_error="timeout",
        )

        self.assertEqual(snapshot.ollama_status, "fallback")
        self.assertEqual(snapshot.history_message, "Учебный fallback: timeout")
        self.assertEqual(snapshot.transcript_entries, (("ИИ", "Fallback разбор."),))


class SystemDesignControllerTests(unittest.TestCase):
    def test_build_system_design_entry_snapshot_saves_practice_context_and_uses_scenario(self) -> None:
        topic = Topic(
            id=3,
            slug="python-runtime",
            title="Python runtime",
            description="Runtime internals",
            level="middle+",
        )
        question = Question(
            id=21,
            topic_id=3,
            difficulty="middle+",
            prompt="Как работает descriptor lookup?",
            hint="Вспомни __get__.",
            reference_answer="Descriptor участвует в поиске атрибутов.",
            source="test",
        )
        answer = Answer(
            id=11,
            session_id=7,
            question_id=21,
            user_answer="Черновик ответа.",
            self_score=None,
            ai_feedback=None,
            answered_at=datetime(2026, 5, 22, 10, 0, 0),
        )

        snapshot = build_system_design_entry_snapshot(
            current_mode="answering",
            current_topic=topic,
            current_question=question,
            current_answer=answer,
            current_pending_answer="pending",
            current_showing_hint=True,
            current_showing_reference=True,
            current_system_design_return_mode="select_topic",
            current_system_design_saved_topic=None,
            current_system_design_saved_question=None,
            current_system_design_saved_answer=None,
            current_system_design_saved_pending_answer=None,
            current_system_design_saved_showing_hint=False,
            current_system_design_saved_showing_reference=False,
            current_system_design_scenario=DEFAULT_SYSTEM_DESIGN_SCENARIO,
            current_system_design_scenario_id=None,
            current_system_design_transcript=[("Кандидат", "old")],
            scenario="Спроектируй notification service.",
            scenario_id=42,
        )

        self.assertEqual(snapshot.system_design_return_mode, "answering")
        self.assertIs(snapshot.system_design_saved_topic, topic)
        self.assertIs(snapshot.system_design_saved_question, question)
        self.assertIs(snapshot.system_design_saved_answer, answer)
        self.assertEqual(snapshot.system_design_saved_pending_answer, "pending")
        self.assertTrue(snapshot.system_design_saved_showing_hint)
        self.assertTrue(snapshot.system_design_saved_showing_reference)
        self.assertEqual(snapshot.system_design_scenario, "Спроектируй notification service.")
        self.assertEqual(snapshot.system_design_scenario_id, 42)
        self.assertEqual(snapshot.system_design_transcript, ())
        self.assertTrue(snapshot.should_reset_artifacts)
        self.assertFalse(snapshot.showing_hint)
        self.assertFalse(snapshot.showing_reference)
        self.assertEqual(snapshot.mode, "system_design")
        self.assertEqual(snapshot.last_feedback, SYSTEM_DESIGN_ENTRY_FEEDBACK)

    def test_build_system_design_entry_snapshot_preserves_saved_context_while_already_focused(self) -> None:
        saved_topic = Topic(
            id=5,
            slug="databases",
            title="Databases",
            description="Transactions",
            level="middle+",
        )
        transcript = [("Кандидат", "Начал с requirements."), ("Интервьюер", "Что с API?")]

        snapshot = build_system_design_entry_snapshot(
            current_mode="loading_system_design_checkpoint",
            current_topic=None,
            current_question=None,
            current_answer=None,
            current_pending_answer=None,
            current_showing_hint=False,
            current_showing_reference=False,
            current_system_design_return_mode="answered",
            current_system_design_saved_topic=saved_topic,
            current_system_design_saved_question=None,
            current_system_design_saved_answer=None,
            current_system_design_saved_pending_answer="saved pending",
            current_system_design_saved_showing_hint=True,
            current_system_design_saved_showing_reference=False,
            current_system_design_scenario="Existing scenario",
            current_system_design_scenario_id=9,
            current_system_design_transcript=transcript,
            scenario="",
            scenario_id=None,
        )

        self.assertEqual(snapshot.system_design_return_mode, "answered")
        self.assertIs(snapshot.system_design_saved_topic, saved_topic)
        self.assertEqual(snapshot.system_design_saved_pending_answer, "saved pending")
        self.assertTrue(snapshot.system_design_saved_showing_hint)
        self.assertEqual(snapshot.system_design_scenario, "Existing scenario")
        self.assertEqual(snapshot.system_design_scenario_id, 9)
        self.assertEqual(snapshot.system_design_transcript, tuple(transcript))
        self.assertFalse(snapshot.should_reset_artifacts)

    def test_build_system_design_entry_snapshot_defaults_empty_fresh_transcript(self) -> None:
        snapshot = build_system_design_entry_snapshot(
            current_mode="select_topic",
            current_topic=None,
            current_question=None,
            current_answer=None,
            current_pending_answer=None,
            current_showing_hint=False,
            current_showing_reference=False,
            current_system_design_return_mode="answering",
            current_system_design_saved_topic=None,
            current_system_design_saved_question=None,
            current_system_design_saved_answer=None,
            current_system_design_saved_pending_answer=None,
            current_system_design_saved_showing_hint=False,
            current_system_design_saved_showing_reference=False,
            current_system_design_scenario="Stale scenario",
            current_system_design_scenario_id=8,
            current_system_design_transcript=[],
            scenario="",
            scenario_id=None,
        )

        self.assertEqual(snapshot.system_design_scenario, DEFAULT_SYSTEM_DESIGN_SCENARIO)
        self.assertIsNone(snapshot.system_design_scenario_id)
        self.assertEqual(snapshot.system_design_transcript, ())

    def test_build_system_design_request_snapshot_sets_loading_candidate_turn(self) -> None:
        snapshot = build_system_design_request_snapshot("Начну с requirements и API.")

        self.assertEqual(snapshot.system_design_pending_message, "Начну с requirements и API.")
        self.assertEqual(snapshot.mode, "loading_system_design")
        self.assertEqual(snapshot.ollama_status, "system design interviewer...")
        self.assertEqual(snapshot.last_feedback, "Интервьюер готовит следующий вопрос...")
        self.assertEqual(
            snapshot.history_message,
            "System design interviewer думает над следующим вопросом...",
        )

    def test_build_system_design_finish_turn_snapshot_records_success_reply(self) -> None:
        snapshot = build_system_design_finish_turn_snapshot(
            user_message="Начну с requirements и API.",
            response="Какие NFR ключевые?",
            last_error=None,
        )

        self.assertEqual(
            snapshot.transcript_entries,
            (
                ("Кандидат", "Начну с requirements и API."),
                ("Интервьюер", "Какие NFR ключевые?"),
            ),
        )
        self.assertEqual(snapshot.system_design_pending_message, "")
        self.assertEqual(snapshot.ollama_status, "ok")
        self.assertEqual(snapshot.last_feedback, "Какие NFR ключевые?")
        self.assertEqual(snapshot.history_message, "Интервьюер ответил.")
        self.assertEqual(snapshot.mode, "system_design")

    def test_build_system_design_finish_turn_snapshot_records_fallback_without_empty_user_turn(self) -> None:
        snapshot = build_system_design_finish_turn_snapshot(
            user_message="",
            response="Fallback interviewer.",
            last_error="timeout",
        )

        self.assertEqual(snapshot.transcript_entries, (("Интервьюер", "Fallback interviewer."),))
        self.assertEqual(snapshot.ollama_status, "fallback")
        self.assertEqual(snapshot.history_message, "System design fallback: timeout")

    def test_build_system_design_checkpoint_snapshots_cover_loading_and_finish(self) -> None:
        loading = build_system_design_checkpoint_loading_snapshot()

        self.assertEqual(loading.mode, "loading_system_design_checkpoint")
        self.assertEqual(loading.ollama_status, "system design checkpoint...")
        self.assertEqual(loading.last_feedback, "Готовлю короткий system design checkpoint...")
        self.assertEqual(
            loading.history_message,
            "System design interviewer готовит checkpoint без финальной оценки...",
        )

        finish = build_system_design_checkpoint_finish_snapshot(
            checkpoint="Checkpoint body.",
            last_error=None,
        )

        self.assertEqual(finish.transcript_entries, (("Интервьюер", "Checkpoint body."),))
        self.assertEqual(finish.ollama_status, "ok")
        self.assertEqual(finish.last_feedback, "System design checkpoint\n\nCheckpoint body.")
        self.assertEqual(finish.history_message, "System design checkpoint готов.")
        self.assertEqual(finish.mode, "system_design")

    def test_build_system_design_pressure_snapshots_cover_loading_and_fallback_finish(self) -> None:
        loading = build_system_design_pressure_loading_snapshot()

        self.assertEqual(loading.mode, "loading_system_design_pressure")
        self.assertEqual(loading.ollama_status, "system design pressure...")
        self.assertEqual(loading.last_feedback, "Готовлю pressure follow-up question...")
        self.assertEqual(
            loading.history_message,
            "System design interviewer готовит pressure follow-up question...",
        )

        finish = build_system_design_pressure_finish_snapshot(
            pressure="Pressure body.",
            last_error="timeout",
        )

        self.assertEqual(finish.transcript_entries, (("Интервьюер", "Pressure body."),))
        self.assertEqual(finish.ollama_status, "fallback")
        self.assertEqual(finish.last_feedback, "System design pressure follow-up\n\nPressure body.")
        self.assertEqual(finish.history_message, "System design pressure follow-up fallback: timeout")
        self.assertEqual(finish.mode, "system_design")

    def test_build_system_design_feedback_snapshots_cover_loading_and_finish_source(self) -> None:
        loading = build_system_design_feedback_loading_snapshot()

        self.assertEqual(loading.mode, "loading_system_design_feedback")
        self.assertEqual(loading.ollama_status, "оценивает system design...")
        self.assertEqual(loading.last_feedback, "Готовлю итоговый system design feedback...")
        self.assertEqual(
            loading.history_message,
            "Генерирую итоговый feedback по system design mock interview...",
        )

        success = build_system_design_feedback_finish_snapshot(
            feedback="Feedback body.",
            last_error=None,
        )
        fallback = build_system_design_feedback_finish_snapshot(
            feedback="Fallback body.",
            last_error="bad json",
        )

        self.assertEqual(success.ollama_status, "ok")
        self.assertEqual(success.last_feedback, "Итоговый system design feedback\n\nFeedback body.")
        self.assertEqual(success.history_message, "Итоговый system design feedback готов.")
        self.assertEqual(success.source, "llm")
        self.assertEqual(success.mode, "system_design")
        self.assertEqual(fallback.ollama_status, "fallback")
        self.assertEqual(fallback.history_message, "System design feedback fallback: bad json")
        self.assertEqual(fallback.source, "fallback")


class TUITests(unittest.IsolatedAsyncioTestCase):
    class QuietContentGeneration:
        def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
            return None

        def ensure_learning_material(self, topic_id, note=""):
            return None

        def ensure_system_design_scenario(self, topic_id, note=""):
            return None

        def list_jobs(self, limit=100):
            return []

    def seed_one_practice_answer(self, app: InterviewPrepTUI, topic_slug: str = "python-runtime") -> None:
        repository = app.services.repository
        topic = repository.find_topic_by_slug(topic_slug)
        self.assertIsNotNone(topic)
        assert topic is not None
        question = repository.list_questions(topic.id or 0)[0]
        answered_at = datetime(2026, 5, 22, 10, 0, 0)
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=answered_at - timedelta(minutes=10),
                ended_at=None,
                target_minutes=60,
            )
        )
        repository.add_answer(
            Answer(
                id=None,
                session_id=session.id or 0,
                question_id=question.id or 0,
                user_answer="Короткий baseline ответ для readiness signal.",
                self_score=3,
                ai_feedback=None,
                answered_at=answered_at,
            )
        )
        repository.finish_session(session.id or 0, answered_at + timedelta(minutes=15))

    def seed_low_rubric_answer(self, app: InterviewPrepTUI, topic_slug: str = "databases") -> None:
        repository = app.services.repository
        topic = repository.find_topic_by_slug(topic_slug)
        self.assertIsNotNone(topic)
        assert topic is not None
        question = repository.list_questions(topic.id or 0)[0]
        answered_at = datetime(2026, 5, 22, 10, 0, 0)
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=answered_at - timedelta(minutes=10),
                ended_at=None,
                target_minutes=60,
            )
        )
        answer = repository.add_answer(
            Answer(
                id=None,
                session_id=session.id or 0,
                question_id=question.id or 0,
                user_answer="не знаю",
                self_score=1,
                ai_feedback=None,
                answered_at=answered_at,
            )
        )
        repository.finish_session(session.id or 0, answered_at + timedelta(minutes=15))
        app.services.evaluations.evaluate_and_store_answer(answer, question, use_llm=False)

    def seed_completed_baseline_outcome(self, app: InterviewPrepTUI, *, days_ago: int = 8) -> int:
        repository = app.services.repository
        completed_at = datetime.now() - timedelta(days=days_ago)
        session = repository.create_session(
            Session(
                id=None,
                topic_id=None,
                started_at=completed_at - timedelta(minutes=25),
                ended_at=None,
                target_minutes=25,
            )
        )
        repository.finish_session(session.id or 0, completed_at)
        repository.upsert_session_outcome(
            SessionOutcome(
                id=None,
                session_id=session.id or 0,
                summary="Baseline calibration. Synthetic previous baseline.",
                strengths=["Previous baseline signal."],
                gaps=["Repeat baseline later."],
                next_drills=["Повторить baseline через 7 дней."],
                readiness_delta=0.18,
                created_at=completed_at,
                outcome_type=SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
            )
        )
        return session.id or 0

    def test_feedback_quality_warning_formats_fallback_and_suspicious_payload(self) -> None:
        fallback = SimpleNamespace(
            raw_payload_json=(
                f'{{"feedback_quality": {{"flags": ["{FEEDBACK_FALLBACK_FLAG}"], '
                '"fallback": true, "suspicious": false, "fallback_error": "timeout while waiting"}}'
            )
        )
        suspicious = SimpleNamespace(
            raw_payload_json=(
                f'{{"feedback_quality": {{"flags": ["{FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG}"], '
                '"fallback": false, "suspicious": true}}'
            )
        )

        self.assertIn("fallback", format_feedback_quality_warning(fallback))
        self.assertIn("timeout while waiting", format_feedback_quality_warning(fallback))
        self.assertIn("Похвала", format_feedback_quality_warning(suspicious))

    async def test_tui_start_screen_shows_today_recommended_readiness_drill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_readiness.db"))
            self.seed_one_practice_answer(app)
            try:
                async with app.run_test(size=(120, 36)):
                    center = app.question_text()

                    self.assertIn("[bold cyan]Today[/bold cyan]", center)
                    self.assertIn("Recommended drill: Провести system design mock и сохранить transcript.", center)
                    self.assertIn(
                        "Why this drill: System Design (system-design) is the top readiness gap",
                        center,
                    )
                    self.assertIn("Expected time: 45-60 min", center)
                    self.assertIn(
                        "Primary action: Enter - начать mock senior interview; ID темы слева - ручной practice.",
                        center,
                    )
                    self.assertIn("мало ответов: 0/3", center)
                    self.assertNotIn("Выбери тему кликом в левой панели.", center)
            finally:
                app.services.close()

    async def test_tui_start_screen_shows_today_empty_state_without_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_empty_state.db"))
            try:
                async with app.run_test(size=(120, 36)):
                    center = app.question_text()

                    self.assertIn("[bold cyan]Today[/bold cyan]", center)
                    self.assertIn("Recommended drill: подготовить curriculum starter pack.", center)
                    self.assertIn("нет сохраненных ответов или rubric evidence", center)
                    self.assertIn("generated curriculum еще не создан", center)
                    self.assertIn("Primary action: Enter - поставить /generate-curriculum", center)
                    self.assertIn("первую baseline practice session", center)
            finally:
                app.services.close()

    async def test_tui_start_screen_shows_baseline_empty_state_when_curriculum_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_baseline_empty_state.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("databases")
                self.assertIsNotNone(topic)
                assert topic is not None
                app.services.repository.add_curriculum_topic(
                    CurriculumTopic(
                        id=None,
                        topic_id=topic.id,
                        slug="databases",
                        title=topic.title,
                        description=topic.description,
                        level=topic.level,
                        source="llm-seed",
                        order_index=1,
                    )
                )
                async with app.run_test(size=(120, 36)):
                    center = app.question_text()

                    self.assertIn("Recommended drill: первая baseline practice session.", center)
                    self.assertIn("curriculum уже создан", center)
                    self.assertIn(
                        "Primary action: Enter - начать первую baseline practice session",
                        center,
                    )
            finally:
                app.services.close()

    async def test_tui_enter_starts_baseline_session_from_empty_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_baseline_start.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("databases")
                self.assertIsNotNone(topic)
                assert topic is not None
                app.services.repository.add_curriculum_topic(
                    CurriculumTopic(
                        id=None,
                        topic_id=topic.id,
                        slug="databases",
                        title=topic.title,
                        description=topic.description,
                        level=topic.level,
                        source="llm-seed",
                        order_index=1,
                    )
                )
                expected_plan = app.services.calibration.baseline_question_plan()

                async with app.run_test(size=(120, 36)) as pilot:
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertIsNotNone(app.session)
                    self.assertIsNone(app.session.topic_id)
                    self.assertEqual(
                        app.baseline_question_ids,
                        tuple(pick.question.id for pick in expected_plan),
                    )
                    self.assertIsNotNone(app.question)
                    self.assertEqual(app.question.id, expected_plan[0].question.id)
                    self.assertIn("Baseline session", "\n".join(app.history))
            finally:
                app.services.close()

    async def test_tui_today_shows_due_repeat_baseline_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_baseline_repeat_due.db"))
            self.seed_one_practice_answer(app)
            previous_session_id = self.seed_completed_baseline_outcome(app, days_ago=8)
            try:
                async with app.run_test(size=(120, 36)):
                    center = app.question_text()

                    self.assertIn("Recommended drill: повторная baseline practice session.", center)
                    self.assertIn("Repeat baseline", app.readiness_text())
                    self.assertIn(f"session #{previous_session_id}", app.readiness_text())
                    self.assertIn("Action: /baseline-repeat - начать повторную baseline session.", app.readiness_text())
                    self.assertIn("Primary action: Enter - начать повторную baseline session", center)
            finally:
                app.services.close()

    async def test_tui_enter_starts_due_repeat_baseline_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_baseline_repeat_start.db"))
            self.seed_one_practice_answer(app)
            self.seed_completed_baseline_outcome(app, days_ago=8)
            try:
                expected_plan = app.services.calibration.baseline_question_plan()
                async with app.run_test(size=(120, 36)) as pilot:
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.session)
                    self.assertIsNone(app.session.topic_id)
                    self.assertEqual(
                        app.baseline_question_ids,
                        tuple(pick.question.id for pick in expected_plan),
                    )
                    self.assertIsNotNone(app.question)
                    self.assertEqual(app.question.id, expected_plan[0].question.id)
                    self.assertIn("Baseline session", "\n".join(app.history))
            finally:
                app.services.close()

    async def test_tui_baseline_review_shows_progress_and_remaining_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_baseline_progress.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("databases")
                self.assertIsNotNone(topic)
                assert topic is not None
                app.services.repository.add_curriculum_topic(
                    CurriculumTopic(
                        id=None,
                        topic_id=topic.id,
                        slug="databases",
                        title=topic.title,
                        description=topic.description,
                        level=topic.level,
                        source="llm-seed",
                        order_index=1,
                    )
                )
                expected_plan = app.services.calibration.baseline_question_plan()
                expected_total = len(expected_plan)
                self.assertGreater(expected_total, 1)

                async with app.run_test(size=(120, 36)) as pilot:
                    await pilot.press("enter")
                    await pilot.pause()
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "Baseline ответ с кратким reasoning."
                    await pilot.press("enter")
                    await pilot.pause()

                    scoring_text = app.question_text()
                    progress_text = f"Baseline progress: 1/{expected_total} answered, {expected_total - 1} remaining."
                    self.assertEqual(app.mode, "scoring")
                    self.assertIn(progress_text, scoring_text)
                    self.assertIn(progress_text, app.history_text())

                    input_bar.value = "4"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "answered")
                    self.assertIn(progress_text, app.question_text())
                    self.assertIn(progress_text, app.history_text())
            finally:
                app.services.close()

    async def test_tui_baseline_finish_marks_session_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_baseline_outcome.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("databases")
                self.assertIsNotNone(topic)
                assert topic is not None
                app.services.repository.add_curriculum_topic(
                    CurriculumTopic(
                        id=None,
                        topic_id=topic.id,
                        slug="databases",
                        title=topic.title,
                        description=topic.description,
                        level=topic.level,
                        source="llm-seed",
                        order_index=1,
                    )
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertIsNotNone(app.session)
                    session_id = app.session.id or 0
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "Baseline ответ с кратким evidence."
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "3"
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "/finish-session"
                    await pilot.press("enter")
                    await pilot.pause()

                    outcome = app.services.repository.get_session_outcome_for_session(session_id)
                    self.assertIsNotNone(outcome)
                    assert outcome is not None
                    self.assertEqual(outcome.outcome_type, SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE)
                    self.assertIn("Baseline calibration.", outcome.summary)
                    self.assertIn("Type: calibration_baseline", app.question_text())
            finally:
                app.services.close()

    async def test_tui_today_action_buttons_are_visible_and_start_primary_drill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_actions.db"))
            self.seed_one_practice_answer(app)
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(140, 36)) as pilot:
                    expected_labels = {
                        "today-start-drill": "Start Drill",
                        "today-review-weak-answer": "Review Weak Answer",
                        "today-system-design": "Mock Senior Interview",
                        "today-open-readiness": "Open Readiness",
                        "today-notebook": "Notebook",
                    }
                    for button_id, label in expected_labels.items():
                        self.assertEqual(str(app.query_one(f"#{button_id}", Button).label), label)

                    clicked = await pilot.click("#today-start-drill")
                    await pilot.pause()

                    self.assertTrue(clicked)
                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.session)
                    self.assertIsNone(app.session.topic_id)
                    self.assertTrue(app.mock_interview_question_ids)
                    self.assertEqual(app.question.id, app.mock_interview_question_ids[0])
                    self.assertIn("Mock senior interview", "\n".join(app.history))
            finally:
                app.services.close()

    async def test_tui_today_review_weak_answer_click_starts_low_rubric_practice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_review_weak_answer.db"))
            self.seed_low_rubric_answer(app)
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(140, 36)) as pilot:
                    center = app.question_text()
                    self.assertIn("Recommended drill: Перерешать слабый ответ", center)
                    self.assertIn("низкая rubric оценка", center)

                    clicked = await pilot.click("#today-review-weak-answer")
                    await pilot.pause()

                    self.assertTrue(clicked)
                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.topic)
                    assert app.topic is not None
                    self.assertEqual(app.topic.slug, "databases")
                    self.assertIn("Вопрос #", app.question_text())
            finally:
                app.services.close()

    async def test_tui_today_enter_starts_recommended_drill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_today_enter_recommended_drill.db"))
            self.seed_one_practice_answer(app)
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(140, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    self.assertEqual(input_bar.value, "")
                    self.assertEqual(app.mode, "select_topic")
                    self.assertIn(
                        "Primary action: Enter - начать mock senior interview",
                        app.question_text(),
                    )

                    await pilot.press("enter")
                    await pilot.pause()

                    expected_plan = app.services.calibration.mock_senior_interview_plan()
                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.session)
                    self.assertIsNone(app.session.topic_id)
                    self.assertEqual(
                        app.mock_interview_question_ids,
                        tuple(pick.question.id for pick in expected_plan.picks),
                    )
                    self.assertIsNotNone(app.question)
                    self.assertEqual(app.question.id, expected_plan.picks[0].question.id)
            finally:
                app.services.close()

    async def test_tui_start_screen_warns_when_generated_curriculum_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_curriculum_missing_warning.db"))
            try:
                async with app.run_test(size=(120, 36)):
                    center = app.question_text()

                    self.assertIn("[bold yellow]Curriculum warning[/bold yellow]", center)
                    self.assertIn(
                        "Generated curriculum отсутствует; база работает только на bootstrap/fallback.",
                        center,
                    )
                    self.assertIn("python -m interview_prep generate-seed", center)
                    self.assertIn("python -m interview_prep curriculum-status", center)
            finally:
                app.services.close()

    async def test_tui_readiness_screen_lists_competency_scores_and_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_readiness_screen.db"))
            try:
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = "/readiness"
                    await pilot.press("enter")
                    await pilot.pause()

                    center = app.question_text()
                    side_panel = app.history_text()

                    self.assertEqual(app.mode, "readiness")
                    self.assertTrue(app.is_focused_mode())
                    self.assertIn("[bold cyan]Readiness dashboard[/bold cyan]", center)
                    self.assertIn("[bold]Overall senior readiness[/bold]", center)
                    self.assertIn("System Design (system-design)", center)
                    self.assertIn("Score:", center)
                    self.assertIn("Evidence: answers 0; rubric 0;", center)
                    self.assertIn("Next action: Провести system design mock и сохранить transcript.", center)
                    self.assertIn("[bold]Must fix before interview[/bold]", center)
                    self.assertIn("Провести один `/mock-interview`", center)
                    self.assertIn("[bold]Readiness[/bold]", side_panel)
                    self.assertIn("/mock-interview", side_panel)
                    self.assertIn("/readiness", side_panel)
                    self.assertIn("/practice", side_panel)
            finally:
                app.services.close()

    async def test_tui_mock_interview_command_starts_from_readiness_without_topic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_mock_interview_from_readiness.db"))
            self.seed_one_practice_answer(app)
            try:
                expected_plan = app.services.calibration.mock_senior_interview_plan()
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = "/readiness"
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertEqual(app.mode, "readiness")

                    input_bar.value = "/mock-interview"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.session)
                    self.assertIsNone(app.session.topic_id)
                    self.assertEqual(
                        app.mock_interview_question_ids,
                        tuple(pick.question.id for pick in expected_plan.picks),
                    )
                    self.assertIsNotNone(app.question)
                    self.assertEqual(app.question.id, expected_plan.picks[0].question.id)
                    self.assertIn("Mock senior interview", "\n".join(app.history))
            finally:
                app.services.close()

    async def test_tui_mock_interview_review_shows_section_progress(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_mock_interview_progress.db"))
            self.seed_one_practice_answer(app)
            try:
                expected_plan = app.services.calibration.mock_senior_interview_plan()
                self.assertEqual(expected_plan.sections, ("coding", "theory", "system_design", "debugging"))
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = "/mock-interview"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mock_interview_sections, expected_plan.sections)
                    input_bar.value = "Разбираю задачу, проговариваю constraints и tradeoffs."
                    await pilot.press("enter")
                    await pilot.pause()

                    progress_text = (
                        "Mock interview progress: section Coding (1/4), "
                        "remaining sections: Theory, System Design, Debugging."
                    )
                    self.assertEqual(app.mode, "scoring")
                    self.assertIn(progress_text, app.question_text())
                    self.assertIn(progress_text, app.history_text())

                    input_bar.value = "4"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "answered")
                    self.assertIn(progress_text, app.question_text())
                    self.assertIn(progress_text, app.history_text())
            finally:
                app.services.close()

    async def test_tui_readiness_screen_shows_weekly_trend_when_enough_session_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_readiness_trend.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("python-runtime")
                self.assertIsNotNone(topic)
                assert topic is not None
                for ended_at, readiness_delta in (
                    (datetime(2026, 5, 5, 10, 0, 0), 0.10),
                    (datetime(2026, 5, 6, 10, 0, 0), 0.20),
                    (datetime(2026, 5, 13, 10, 0, 0), -0.10),
                ):
                    session = app.services.repository.create_session(
                        Session(
                            id=None,
                            topic_id=topic.id,
                            started_at=ended_at - timedelta(minutes=30),
                            ended_at=None,
                            target_minutes=60,
                        )
                    )
                    app.services.repository.finish_session(session.id or 0, ended_at)
                    app.services.repository.upsert_session_outcome(
                        SessionOutcome(
                            id=None,
                            session_id=session.id or 0,
                            summary="Synthetic readiness trend outcome.",
                            strengths=[],
                            gaps=[],
                            next_drills=[],
                            readiness_delta=readiness_delta,
                            created_at=ended_at,
                        )
                    )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = "/readiness"
                    await pilot.press("enter")
                    await pilot.pause()

                    center = app.question_text()

                    self.assertIn("[bold]Weekly readiness trend[/bold]", center)
                    self.assertIn("2026-05-04..2026-05-10: sessions 2; avg delta +0.15", center)
                    self.assertIn("2026-05-11..2026-05-17: sessions 1; avg delta -0.10", center)
            finally:
                app.services.close()

    async def test_tui_shows_curriculum_recommended_topic_on_practice_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_curriculum_recommendation.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("databases")
                self.assertIsNotNone(topic)
                app.services.repository.add_curriculum_topic(
                    CurriculumTopic(
                        id=None,
                        topic_id=topic.id,
                        slug="databases",
                        title=topic.title,
                        description=topic.description,
                        level=topic.level,
                        source="llm-seed",
                        order_index=1,
                    )
                )
                async with app.run_test(size=(120, 36)) as pilot:
                    center = app.question_text()
                    self.assertIn("Предложенная следующая тема", center)
                    self.assertIn("Базы данных и persistence", center)
                    self.assertIn("Следующая новая тема по curriculum order", center)

                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = str(topic.id)
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertIsNotNone(app.topic)
                    self.assertEqual(app.topic.id, topic.id)
            finally:
                app.services.close()

    async def test_tui_accept_topic_command_starts_curriculum_recommended_topic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_accept_topic_command.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("databases")
                self.assertIsNotNone(topic)
                app.services.repository.add_curriculum_topic(
                    CurriculumTopic(
                        id=None,
                        topic_id=topic.id,
                        slug="databases",
                        title=topic.title,
                        description=topic.description,
                        level=topic.level,
                        source="llm-seed",
                        order_index=1,
                    )
                )
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = "/accept-topic"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertIsNotNone(app.topic)
                    self.assertEqual(app.topic.id, topic.id)
                    self.assertEqual(app.mode, "answering")
            finally:
                app.services.close()

    async def test_tui_clicking_practice_topic_starts_topic_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_click_topic_selection.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(120, 36)) as pilot:
                    topics = app.query_one("#topics", OptionList)
                    first_topic = next(
                        option for option in topics.options if option.id and option.id.startswith("topic-")
                    )
                    expected_topic_id = int(first_topic.id.removeprefix("topic-"))

                    clicked = await pilot.click("#topics", offset=(4, 2))
                    await pilot.pause()

                    self.assertTrue(clicked)
                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.topic)
                    self.assertEqual(app.topic.id, expected_topic_id)
                    self.assertIsNotNone(app.session)
                    self.assertEqual(app.session.topic_id, expected_topic_id)
            finally:
                app.services.close()

    async def test_tui_practice_question_shows_linked_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_question_tags.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                question = app.services.repository.list_questions()[0]
                concurrency = app.services.repository.upsert_tag(Tag(id=None, slug="concurrency", title="Concurrency"))
                python_runtime = app.services.repository.upsert_tag(
                    Tag(id=None, slug="python-runtime", title="Python runtime")
                )
                app.services.repository.set_question_tags(
                    question.id or 0,
                    [python_runtime.id or 0, concurrency.id or 0],
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = str(question.topic_id)
                    await pilot.press("enter")
                    await pilot.pause()

                    rendered = app.question_text()
                    self.assertEqual(app.mode, "answering")
                    self.assertEqual(app.question.id if app.question else None, question.id)
                    self.assertIn("Теги: Concurrency (concurrency), Python runtime (python-runtime)", rendered)
                    self.assertLess(rendered.index("Теги:"), rendered.index(question.prompt))
            finally:
                app.services.close()

    async def test_tui_practice_question_shows_linked_competencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_question_competencies.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                question = app.services.repository.list_questions()[0]
                python_runtime = app.services.repository.find_competency_by_slug("python-runtime")
                observability = app.services.repository.find_competency_by_slug("observability")
                self.assertIsNotNone(python_runtime)
                self.assertIsNotNone(observability)
                app.services.repository.set_question_competencies(
                    question.id or 0,
                    [
                        QuestionCompetencyLink(competency=observability, weight=0.25),
                        QuestionCompetencyLink(competency=python_runtime, is_primary=True, weight=0.75),
                    ],
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = str(question.topic_id)
                    await pilot.press("enter")
                    await pilot.pause()

                    rendered = app.question_text()
                    self.assertEqual(app.mode, "answering")
                    self.assertEqual(app.question.id if app.question else None, question.id)
                    self.assertIn(
                        "Компетенции: Python Runtime (python-runtime) [основная], Observability (observability)",
                        rendered,
                    )
                    self.assertLess(rendered.index("Компетенции:"), rendered.index(question.prompt))
            finally:
                app.services.close()

    async def test_tui_clicking_mode_actions_switches_main_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_click_mode_actions.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(120, 36)) as pilot:
                    clicked_learn = await pilot.click("#action-learn")
                    await pilot.pause()

                    self.assertTrue(clicked_learn)
                    self.assertEqual(app.mode, "learning")
                    self.assertIn("Режим обучения", app.question_text())

                    clicked_practice = await pilot.click("#action-practice")
                    await pilot.pause()

                    self.assertTrue(clicked_practice)
                    self.assertEqual(app.mode, "select_topic")

                    clicked_practice_start = await pilot.click("#action-practice")
                    await pilot.pause()

                    self.assertTrue(clicked_practice_start)
                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.session)
                    self.assertIsNotNone(app.topic)

                    practice_topic_id = app.topic.id
                    clicked_system_design = await pilot.click("#action-system-design")
                    await pilot.pause()

                    self.assertTrue(clicked_system_design)
                    self.assertEqual(app.mode, "system_design")
                    self.assertIn("System Design Mock Interview", app.question_text())

                    clicked_practice_return = await pilot.click("#action-practice")
                    await pilot.pause()

                    self.assertTrue(clicked_practice_return)
                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.topic)
                    self.assertEqual(app.topic.id, practice_topic_id)
            finally:
                app.services.close()

    async def test_tui_smoke_switches_today_practice_learn_system_design_readiness_practice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_mode_chain_smoke.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(140, 36)) as pilot:
                    self.assertEqual(app.mode, "select_topic")
                    self.assertIn("[bold cyan]Today[/bold cyan]", app.question_text())

                    clicked_practice = await pilot.click("#action-practice")
                    await pilot.pause()

                    self.assertTrue(clicked_practice)
                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.session)
                    self.assertIsNotNone(app.topic)
                    self.assertIsNotNone(app.question)
                    practice_session_id = app.session.id
                    practice_topic_id = app.topic.id
                    practice_question_id = app.question.id

                    clicked_learn = await pilot.click("#action-learn")
                    await pilot.pause()

                    self.assertTrue(clicked_learn)
                    self.assertEqual(app.mode, "learning")
                    self.assertIn("Режим обучения", app.question_text())

                    clicked_system_design = await pilot.click("#action-system-design")
                    await pilot.pause()

                    self.assertTrue(clicked_system_design)
                    self.assertEqual(app.mode, "system_design")
                    self.assertIn("System Design Mock Interview", app.question_text())

                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = "/readiness"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "readiness")
                    self.assertIn("[bold cyan]Readiness dashboard[/bold cyan]", app.question_text())

                    clicked_practice_return = await pilot.click("#action-practice")
                    await pilot.pause()

                    self.assertTrue(clicked_practice_return)
                    self.assertEqual(app.mode, "answering")
                    self.assertIsNotNone(app.session)
                    self.assertIsNotNone(app.topic)
                    self.assertIsNotNone(app.question)
                    self.assertEqual(app.session.id, practice_session_id)
                    self.assertEqual(app.topic.id, practice_topic_id)
                    self.assertEqual(app.question.id, practice_question_id)
            finally:
                app.services.close()

    async def test_tui_notebook_action_opens_current_topic_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_notebook_action.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                topic = app.services.repository.find_topic_by_slug("python-runtime")
                other_topic = app.services.repository.find_topic_by_slug("async-backend")
                created_at = datetime(2026, 5, 14, 9, 0, 0)
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-runtime",
                        source_message_id=None,
                        title="Runtime notebook entry",
                        body="Descriptor lookup note.",
                        source="learning-ai",
                        created_at=created_at,
                    )
                )
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=other_topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-async",
                        source_message_id=None,
                        title="Async notebook entry",
                        body="Backpressure note.",
                        source="learning-ai",
                        created_at=created_at + timedelta(minutes=1),
                    )
                )
                async with app.run_test(size=(120, 36)) as pilot:
                    self.assertIn("Конспект обучения", str(app.query_one("#action-notebook").label))
                    self.assertIn("Конспект обучения", app.question_text())
                    self.assertIn("/notebook", app.question_text())

                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = str(topic.id)
                    await pilot.press("enter")
                    await pilot.pause()

                    clicked_notebook = await pilot.click("#action-notebook")
                    await pilot.pause()

                    self.assertTrue(clicked_notebook)
                    self.assertEqual(app.mode, "notebook")
                    self.assertEqual(app.notebook_topic_filter, topic.id)
                    self.assertIsNone(app.notebook_subtopic_filter)
                    notebook_text = app.question_text()
                    self.assertIn(f"[bold]Фильтр[/bold]: topic #{topic.id}", notebook_text)
                    self.assertIn("Runtime notebook entry", notebook_text)
                    self.assertNotIn("Async notebook entry", notebook_text)
            finally:
                app.services.close()

    async def test_tui_clicking_mode_actions_before_topic_does_not_stick_in_learning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_click_mode_actions_before_topic.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(120, 36)) as pilot:
                    clicked_learn = await pilot.click("#action-learn")
                    await pilot.pause()

                    self.assertTrue(clicked_learn)
                    self.assertEqual(app.mode, "learning")
                    self.assertIsNone(app.topic)
                    self.assertIsNone(app.session)

                    clicked_system_design = await pilot.click("#action-system-design")
                    await pilot.pause()

                    self.assertTrue(clicked_system_design)
                    self.assertEqual(app.mode, "system_design")

                    clicked_practice = await pilot.click("#action-practice")
                    await pilot.pause()

                    self.assertTrue(clicked_practice)
                    self.assertNotEqual(app.mode, "learning")
                    self.assertFalse(app.is_focused_mode())
                    self.assertIn(app.mode, {"select_topic", "answering"})
            finally:
                app.services.close()

    async def test_tui_slash_mode_actions_before_topic_do_not_stack_focused_modes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_slash_mode_actions_before_topic.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "/learn"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "learning")
                    self.assertIsNone(app.topic)
                    self.assertIsNone(app.session)

                    input_bar.value = "/system-design"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "system_design")

                    input_bar.value = "/practice"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertNotEqual(app.mode, "learning")
                    self.assertFalse(app.is_focused_mode())
                    self.assertIn(app.mode, {"select_topic", "answering"})
            finally:
                app.services.close()

    async def test_tui_history_browser_lists_completed_practice_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_history_browser.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                topic = app.services.repository.find_topic_by_slug("python-runtime")
                self.assertIsNotNone(topic)
                question = app.services.repository.list_questions(topic.id)[0]
                started_at = datetime(2026, 5, 13, 8, 30, 0)
                session = app.services.repository.create_session(
                    Session(
                        id=None,
                        topic_id=topic.id,
                        started_at=started_at,
                        ended_at=None,
                        target_minutes=60,
                    )
                )
                app.services.repository.add_answer(
                    Answer(
                        id=None,
                        session_id=session.id or 0,
                        question_id=question.id or 0,
                        user_answer="Ответ для history browser.",
                        self_score=5,
                        ai_feedback="ok",
                        answered_at=started_at + timedelta(minutes=7),
                    )
                )
                app.services.repository.finish_session(session.id or 0, started_at + timedelta(minutes=25))
                app.services.repository.add_learning_dialog_message(
                    LearningDialogMessage(
                        id=None,
                        topic_id=topic.id,
                        role="user",
                        content="Что почитать про descriptors?",
                        created_at=started_at + timedelta(hours=1),
                    )
                )
                app.services.repository.add_learning_dialog_message(
                    LearningDialogMessage(
                        id=None,
                        topic_id=topic.id,
                        role="assistant",
                        content="Начни с data descriptors и MRO.",
                        created_at=started_at + timedelta(hours=1, minutes=2),
                    )
                )
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id=None,
                        source_message_id=None,
                        title="Descriptor notebook entry",
                        body="Разбор data descriptors из learning history.",
                        source="learning-ai",
                        created_at=started_at + timedelta(hours=1, minutes=3),
                    )
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", Composer)
                    input_bar.value = "/history"
                    await pilot.press("enter")
                    await pilot.pause()

                    center = app.question_text()
                    side_panel = app.history_text()
                    self.assertEqual(app.mode, "history")
                    self.assertIn("History browser", center)
                    self.assertIn(f"Session #{session.id}", center)
                    self.assertIn(topic.title, center)
                    self.assertIn("Started: 2026-05-13T08:30", center)
                    self.assertIn("Answers: 1", center)
                    self.assertIn("Avg self-score: 5.0/5", center)
                    self.assertIn("Завершенных sessions: 1", side_panel)

                    input_bar.value = f"/history {session.id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    detail = app.question_text()
                    detail_side_panel = app.history_text()
                    self.assertEqual(app.mode, "history")
                    self.assertEqual(app.history_selected_session_id, session.id)
                    self.assertIn(f"Session #{session.id}", detail)
                    self.assertIn(f"Question #{question.id}", detail)
                    self.assertIn(question.prompt, detail)
                    self.assertIn("Ответ для history browser.", detail)
                    self.assertIn("Self-score: 5/5", detail)
                    self.assertIn("Эталонный ответ", detail)
                    self.assertIn("AI feedback", detail)
                    self.assertIn("ok", detail)
                    self.assertIn(f"Открыта session: #{session.id}", detail_side_panel)

                    input_bar.value = "/history learning"
                    await pilot.press("enter")
                    await pilot.pause()

                    learning_history = app.question_text()
                    learning_side_panel = app.history_text()
                    self.assertEqual(app.mode, "history")
                    self.assertEqual(app.history_browser_view, "learning")
                    self.assertIn("Learning dialogs", learning_history)
                    self.assertIn(topic.title, learning_history)
                    self.assertIn("Date: 2026-05-13", learning_history)
                    self.assertIn("Messages: 2", learning_history)
                    self.assertIn(f"/history learning {topic.id} 2026-05-13", learning_history)
                    self.assertIn(f"/notebook topic {topic.id}", learning_history)
                    self.assertIn("Learning dialogs: 1", learning_side_panel)

                    input_bar.value = f"/history learning {topic.id} 2026-05-13"
                    await pilot.press("enter")
                    await pilot.pause()

                    learning_detail = app.question_text()
                    learning_detail_side_panel = app.history_text()
                    self.assertEqual(app.history_browser_view, "learning")
                    self.assertEqual(app.history_selected_learning_topic_id, topic.id)
                    self.assertEqual(app.history_selected_learning_date, "2026-05-13")
                    self.assertIn("Learning dialog", learning_detail)
                    self.assertIn(f"topic #{topic.id}", learning_detail)
                    self.assertIn("Что почитать про descriptors?", learning_detail)
                    self.assertIn("Начни с data descriptors и MRO.", learning_detail)
                    self.assertIn("Ты", learning_detail)
                    self.assertIn("ИИ", learning_detail)
                    self.assertIn(f"Конспект обучения: /notebook topic {topic.id}", learning_detail)
                    self.assertIn("Открыт learning dialog", learning_detail_side_panel)

                    input_bar.value = f"/notebook topic {topic.id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    notebook_text = app.question_text()
                    notebook_side_panel = app.history_text()
                    self.assertEqual(app.mode, "notebook")
                    self.assertEqual(app.notebook_topic_filter, topic.id)
                    self.assertIn(f"[bold]Фильтр[/bold]: topic #{topic.id}", notebook_text)
                    self.assertIn("Descriptor notebook entry", notebook_text)
                    self.assertIn("В текущем фильтре: 1", notebook_side_panel)

                    input_bar.value = "/practice"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "select_topic")
            finally:
                app.services.close()

    async def test_tui_history_browser_shows_system_design_feedback_and_rubric_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design_history.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                topic = app.services.repository.find_topic_by_slug("system-design")
                self.assertIsNotNone(topic)
                assert topic is not None
                started_at = datetime(2026, 5, 21, 9, 0, 0)
                session = app.services.repository.create_session(
                    Session(
                        id=None,
                        topic_id=topic.id,
                        started_at=started_at,
                        ended_at=None,
                        target_minutes=60,
                    )
                )
                scenario = app.services.repository.add_system_design_scenario(
                    SystemDesignScenario(
                        id=None,
                        topic_id=topic.id or 0,
                        title="Notifications",
                        scenario="Спроектируй сервис уведомлений.",
                        focus_areas=["requirements", "api", "risks"],
                        source="test",
                        created_at=started_at + timedelta(minutes=1),
                    )
                )
                app.services.system_design.save_transcript_turn(
                    topic.id or 0,
                    "Фиксирую SLA, публичный API, таблицу notifications, retries и abuse protection.",
                    "Какие метрики покажут user impact?",
                    scenario_id=scenario.id,
                )
                app.services.system_design.add_artifact(
                    topic.id or 0,
                    "requirements",
                    "SLA 99.9%, email/push notifications.",
                    scenario_id=scenario.id,
                )
                app.services.system_design.add_artifact(
                    topic.id or 0,
                    "api",
                    "POST /notifications, retry-safe idempotency key.",
                    scenario_id=scenario.id,
                )
                app.services.system_design.add_artifact(
                    topic.id or 0,
                    "risks",
                    "Provider outage, retries, abuse protection.",
                    scenario_id=scenario.id,
                )
                feedback = app.services.system_design.save_final_feedback(
                    topic.id or 0,
                    "Уровень: middle+. Пробелы: добавь observability dashboard.",
                    scenario_id=scenario.id,
                    session_id=session.id,
                    source="llm",
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", Composer)
                    input_bar.value = "/history system-design"
                    await pilot.press("enter")
                    await pilot.pause()

                    center = app.question_text()
                    side_panel = app.history_text()
                    self.assertEqual(app.mode, "history")
                    self.assertEqual(app.history_browser_view, "system_design")
                    self.assertIn("System design sessions", center)
                    self.assertIn(f"Feedback #{feedback.id}", center)
                    self.assertIn(f"Session: #{session.id}", center)
                    self.assertIn("Notifications", center)
                    self.assertIn("Rubric:", center)
                    self.assertIn(f"/history system-design {feedback.id}", center)
                    self.assertIn("System design feedbacks: 1", side_panel)

                    input_bar.value = f"/history system-design {feedback.id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    detail = app.question_text()
                    detail_side_panel = app.history_text()
                    self.assertEqual(app.history_selected_system_design_feedback_id, feedback.id)
                    self.assertIn(f"System design feedback #{feedback.id}", detail)
                    self.assertIn("System design final feedback", detail)
                    self.assertIn("Уровень: middle+", detail)
                    self.assertIn("System design rubric", detail)
                    self.assertIn("Average score:", detail)
                    self.assertIn("Requirements", detail)
                    self.assertIn("Observability", detail)
                    self.assertIn(f"Открыт system design feedback: #{feedback.id}", detail_side_panel)
            finally:
                app.services.close()

    async def test_tui_composer_keeps_fast_command_and_topic_submit_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_composer_fast_flow.db"))
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", Composer)

                input_bar.value = " /commands "
                await pilot.press("enter")
                await pilot.pause()

                self.assertTrue(app.command_palette_visible)
                self.assertEqual(app.mode, "select_topic")
                self.assertEqual(input_bar.value, "")
                self.assertEqual(input_bar.styles.height.value, Composer.MIN_HEIGHT)

                input_bar.value = " 1 "
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "answering")
                self.assertIsNotNone(app.topic)
                self.assertEqual(app.topic.id, 1)
                self.assertEqual(input_bar.value, "")

    async def test_tui_auto_queues_background_content_on_topic_start(self) -> None:
        class FakeContentGeneration:
            def __init__(self):
                self.called_with = None

            def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
                self.called_with = (topic_id, min_questions, note)
                return SimpleNamespace(id=42)

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_auto_content.db"))
            fake_content = FakeContentGeneration()
            app.services.content_generation = fake_content
            app.start_background_content_worker = lambda: setattr(app, "content_status", "worker started")
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                self.assertIsNotNone(fake_content.called_with)
                self.assertEqual(fake_content.called_with[1], 4)
                self.assertEqual(app.content_status, "worker started")
                self.assertIn("Content: worker started", app.topbar_text())

    async def test_tui_content_status_shows_queue_counts_and_latest_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_content_status.db"))
            try:
                queued = app.services.repository.create_content_generation_job(
                    "question",
                    '{"topic_id": 1}',
                )
                running = app.services.repository.create_content_generation_job(
                    "learning-material",
                    '{"topic_id": 1}',
                )
                failed = app.services.repository.create_content_generation_job(
                    "question",
                    '{"topic_id": 1}',
                )
                done = app.services.repository.create_content_generation_job(
                    "system-design-scenario",
                    '{"topic_id": 1}',
                )
                app.services.repository.update_content_generation_job(running.id or 0, "running")
                app.services.repository.update_content_generation_job(failed.id or 0, "failed", error="boom")
                app.services.repository.update_content_generation_job(
                    done.id or 0,
                    "done",
                    result_json='{"kind": "system-design-scenario", "scenario_id": 7}',
                )

                text = app.topbar_text()

                self.assertIn("queue q1/r1/f1", text)
                self.assertIn(f"last done #{done.id} system-design-scenario -> scenario#7", text)
                self.assertNotIn(f"last done #{queued.id}", text)
            finally:
                app.services.close()

    async def test_tui_notebook_screen_filters_ai_explanations_by_topic_and_subtopic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_notebook.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("python-runtime")
                other_topic = app.services.repository.find_topic_by_slug("async-backend")
                curriculum_topic = app.services.repository.add_curriculum_topic(
                    CurriculumTopic(
                        id=None,
                        topic_id=topic.id,
                        slug="python-runtime-notebook",
                        title="Python runtime notebook",
                        description="Runtime notes.",
                        level="middle+",
                        source="test",
                        order_index=1,
                    )
                )
                subtopic = app.services.repository.add_curriculum_subtopic(
                    CurriculumSubtopic(
                        id=None,
                        curriculum_topic_id=curriculum_topic.id or 0,
                        slug="descriptor-lookup",
                        title="Descriptor lookup",
                        description="Attribute lookup order.",
                        source="test",
                        order_index=1,
                    )
                )
                created_at = datetime(2026, 5, 13, 10, 0, 0)
                descriptor_entry = app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=topic.id,
                        curriculum_subtopic_id=subtopic.id,
                        dialog_session_id="learn-session-1",
                        source_message_id=None,
                        title="Descriptor lookup order",
                        body="Data descriptors override instance attributes.\n\n- property\n- ORM fields",
                        source="learning-ai",
                        created_at=created_at,
                    )
                )
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=other_topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-session-2",
                        source_message_id=None,
                        title="Async backpressure",
                        body="Bound queues and propagate overload.",
                        source="learning-ai",
                        created_at=created_at + timedelta(minutes=1),
                    )
                )
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "/notebook"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "notebook")
                    self.assertEqual(app.query_one("#left_panel").styles.display, "none")
                    self.assertEqual(app.query_one("#right_panel").styles.display, "block")
                    self.assertIn("Конспект обучения", app.question_text())
                    self.assertIn("Разбивка по темам", app.question_text())
                    self.assertIn("AI explanations", app.question_text())
                    self.assertIn("Descriptor lookup order", app.question_text())
                    self.assertIn("Async backpressure", app.question_text())
                    self.assertIn("/notebook topic", app.question_text())
                    self.assertIn("/notebook subtopic", app.question_text())
                    self.assertIn("Конспект обучения", app.history_text())
                    self.assertIn("Всего entries: 2", app.history_text())

                    input_bar.value = f"/notebook topic {topic.id}"
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertIn(f"[bold]Фильтр[/bold]: topic #{topic.id}", app.question_text())
                    self.assertIn("Descriptor lookup order", app.question_text())
                    self.assertNotIn("Async backpressure", app.question_text())

                    input_bar.value = f"/notebook subtopic {subtopic.id}"
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertIn(f"[bold]Фильтр[/bold]: subtopic #{subtopic.id}", app.question_text())
                    self.assertIn("Descriptor lookup", app.question_text())
                    self.assertIn("Descriptor lookup order", app.question_text())
                    self.assertNotIn("Async backpressure", app.question_text())

                    input_bar.value = f"/notebook entry {descriptor_entry.id}"
                    await pilot.press("enter")
                    await pilot.pause()
                    entry_text = app.question_text()
                    self.assertIn(f"[bold]Фильтр[/bold]: entry #{descriptor_entry.id}", entry_text)
                    self.assertIn("Data descriptors override instance attributes.", entry_text)
                    self.assertIn("property", entry_text)
                    self.assertIn("Открыта одна запись конспекта", app.history_text())
            finally:
                app.services.close()

    async def test_tui_notebook_screen_shows_manual_notes_with_ai_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_notebook_manual_notes.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("python-runtime")
                other_topic = app.services.repository.find_topic_by_slug("databases")
                self.assertIsNotNone(topic)
                self.assertIsNotNone(other_topic)
                assert topic is not None
                assert other_topic is not None
                created_at = datetime(2026, 5, 14, 10, 0, 0)
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-session-1",
                        source_message_id=None,
                        title="Descriptor lookup order",
                        body="Data descriptors override instance attributes.",
                        source="learning-ai",
                        created_at=created_at,
                    )
                )
                app.services.repository.add_manual_note(
                    ManualNote(
                        id=None,
                        topic_id=topic.id,
                        session_id=None,
                        context_type="tui-saved-note",
                        context_id=f"topic:{topic.id}",
                        title="Retry semantics",
                        body="Проверить idempotency keys перед повторным ответом.",
                        created_at=created_at + timedelta(minutes=1),
                        updated_at=created_at + timedelta(minutes=1),
                    )
                )
                app.services.repository.add_manual_note(
                    ManualNote(
                        id=None,
                        topic_id=topic.id,
                        session_id=None,
                        context_type="tui-notes-draft",
                        context_id=f"topic:{topic.id}",
                        title="TUI notes draft",
                        body="Черновик правой панели не должен попадать в notebook.",
                        created_at=created_at + timedelta(minutes=2),
                        updated_at=created_at + timedelta(minutes=2),
                    )
                )
                app.services.repository.add_manual_note(
                    ManualNote(
                        id=None,
                        topic_id=other_topic.id,
                        session_id=None,
                        context_type="tui-saved-note",
                        context_id=f"topic:{other_topic.id}",
                        title="Other topic note",
                        body="Эта заметка относится к другой теме.",
                        created_at=created_at + timedelta(minutes=3),
                        updated_at=created_at + timedelta(minutes=3),
                    )
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = f"/notebook topic {topic.id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    center = app.question_text()
                    side_panel = app.history_text()

                    self.assertIn("AI explanations", center)
                    self.assertIn("Descriptor lookup order", center)
                    self.assertIn("Manual notes", center)
                    self.assertIn("Retry semantics", center)
                    self.assertIn("Проверить idempotency keys", center)
                    self.assertNotIn("TUI notes draft", center)
                    self.assertNotIn("Черновик правой панели", center)
                    self.assertNotIn("Other topic note", center)
                    self.assertIn("Всего entries: 1", side_panel)
                    self.assertIn("Всего manual notes: 2", side_panel)
                    self.assertIn("В текущем фильтре: 1 entries; 1 manual notes", side_panel)
            finally:
                app.services.close()

    async def test_tui_notebook_screen_filters_entries_by_competency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_notebook_competency.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("python-runtime")
                other_topic = app.services.repository.find_topic_by_slug("async-backend")
                self.assertIsNotNone(topic)
                self.assertIsNotNone(other_topic)
                assert topic is not None
                assert other_topic is not None
                created_at = datetime(2026, 5, 14, 11, 0, 0)
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-runtime",
                        source_message_id=None,
                        title="Runtime competency entry",
                        body="Descriptor lookup belongs to Python runtime practice.",
                        source="learning-ai",
                        created_at=created_at,
                    )
                )
                app.services.repository.add_manual_note(
                    ManualNote(
                        id=None,
                        topic_id=topic.id,
                        session_id=None,
                        context_type="tui-saved-note",
                        context_id=f"topic:{topic.id}",
                        title="Runtime manual note",
                        body="Повторить MRO и data descriptors.",
                        created_at=created_at + timedelta(minutes=1),
                        updated_at=created_at + timedelta(minutes=1),
                    )
                )
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=other_topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-async",
                        source_message_id=None,
                        title="Async competency entry",
                        body="Backpressure belongs to async competency practice.",
                        source="learning-ai",
                        created_at=created_at + timedelta(minutes=2),
                    )
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = "/notebook competency python-runtime"
                    await pilot.press("enter")
                    await pilot.pause()

                    center = app.question_text()
                    side_panel = app.history_text()

                    self.assertEqual(app.mode, "notebook")
                    self.assertEqual(app.notebook_competency_filter, "python-runtime")
                    self.assertIn("[bold]Фильтр[/bold]: competency python-runtime Python Runtime", center)
                    self.assertIn("/notebook competency <slug>", center)
                    self.assertIn("Runtime competency entry", center)
                    self.assertIn("Runtime manual note", center)
                    self.assertNotIn("Async competency entry", center)
                    self.assertIn("В текущем фильтре: 1 entries; 1 manual notes", side_panel)
            finally:
                app.services.close()

    async def test_tui_content_screen_lists_service_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_content_screen.db"))
            try:
                queued = app.services.repository.create_content_generation_job(
                    "question",
                    '{"topic_id": 1, "note": "Добавить вопрос про descriptor protocol."}',
                )
                running = app.services.repository.create_content_generation_job(
                    "learning-material",
                    '{"topic_id": 1, "note": "Подготовить учебный материал."}',
                )
                failed = app.services.repository.create_content_generation_job(
                    "system-design-scenario",
                    '{"topic_id": 1, "retry": {"attempt": 1, "max_attempts": 3, "next_attempt_at": "2026-05-13T10:00:00", "last_error": "timeout"}}',
                )
                app.services.repository.update_content_generation_job(running.id or 0, "running")
                app.services.repository.update_content_generation_job(failed.id or 0, "failed", error="Ollama timeout")

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "/content"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "content")
                    self.assertEqual(app.query_one("#left_panel").styles.display, "none")
                    self.assertEqual(app.query_one("#right_panel").styles.display, "block")
                    center = app.question_text()
                    self.assertIn("Content jobs", center)
                    self.assertIn("Queued: 1", center)
                    self.assertIn("Running: 1", center)
                    self.assertIn("Failed: 1", center)
                    self.assertIn(f"#{queued.id} [question] queued", center)
                    self.assertIn(f"#{running.id} [learning-material] running", center)
                    self.assertIn(f"#{failed.id} [system-design-scenario] failed", center)
                    self.assertIn("Добавить вопрос про descriptor protocol.", center)
                    self.assertIn("Retry: 1/3; next 2026-05-13T10:00:00; timeout", center)
                    self.assertIn("Error: Ollama timeout", center)

                    side_panel = app.history_text()
                    self.assertIn("Content jobs", side_panel)
                    self.assertIn("Следующее действие", side_panel)
                    self.assertIn("Queued: 1", side_panel)
                    self.assertIn("/pause-content", side_panel)
                    self.assertIn("/resume-content", side_panel)
                    self.assertIn("/retry-job <id>", side_panel)
                    self.assertIn("/generate-curriculum", side_panel)
                    self.assertIn("/materials", side_panel)
                    self.assertIn("/retry-job", center)
                    self.assertIn("/pause-content", center)
                    self.assertIn("/generate-curriculum", center)
            finally:
                app.services.close()

    async def test_tui_questions_review_lists_and_updates_pending_generated_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_questions_review.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("async-backend")
                self.assertIsNotNone(topic)
                assert topic is not None
                first = app.services.repository.add_question(
                    Question(
                        id=None,
                        topic_id=topic.id or 0,
                        difficulty="senior",
                        prompt="Как review-ить generated вопрос перед practice loop?",
                        hint="Проверь uniqueness, senior coverage и production realism.",
                        reference_answer="Нужно принять полезные вопросы и архивировать слабые.",
                        source="background-llm",
                        source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                    )
                )
                second = app.services.repository.add_question(
                    Question(
                        id=None,
                        topic_id=topic.id or 0,
                        difficulty="middle+",
                        prompt="Когда archived generated вопрос не должен попадать в practice?",
                        hint="Слабые или дублирующиеся вопросы надо скрывать.",
                        reference_answer="Archive меняет source_quality_status без удаления строки.",
                        source="llm-seed",
                        source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                    )
                )
                accepted = app.services.repository.add_question(
                    Question(
                        id=None,
                        topic_id=topic.id or 0,
                        difficulty="middle+",
                        prompt="Accepted question не должен быть в pending review.",
                        hint="Этот вопрос уже принят.",
                        reference_answer="Accepted скрыт из review queue.",
                        source="background-llm",
                        source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
                    )
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "/questions-review"
                    await pilot.press("enter")
                    await pilot.pause()

                    center = app.question_text()
                    side_panel = app.history_text()
                    self.assertEqual(app.mode, "questions_review")
                    self.assertEqual(app.query_one("#left_panel").styles.display, "none")
                    self.assertEqual(app.query_one("#right_panel").styles.display, "block")
                    self.assertIn("Generated questions review", center)
                    self.assertIn("Pending generated questions", center)
                    self.assertIn(f"#{first.id} Async backend", center)
                    self.assertIn(f"#{second.id} Async backend", center)
                    self.assertNotIn(f"#{accepted.id} Async backend", center)
                    self.assertIn(f"/questions-review accept {first.id}", center)
                    self.assertIn(f"/questions-review archive {second.id}", center)
                    self.assertIn("Pending: 2", side_panel)

                    input_bar.value = f"/questions-review accept {first.id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    saved_first = app.services.repository.get_question(first.id or 0)
                    self.assertIsNotNone(saved_first)
                    assert saved_first is not None
                    self.assertEqual(saved_first.source_quality_status, QUESTION_SOURCE_QUALITY_ACCEPTED)
                    self.assertIn(f"Question #{first.id} accepted", app.history_text())
                    self.assertNotIn(f"#{first.id} Async backend", app.question_text())
                    self.assertIn(f"#{second.id} Async backend", app.question_text())
                    self.assertIn("Pending: 1", app.history_text())

                    input_bar.value = f"/questions-review archive {second.id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    saved_second = app.services.repository.get_question(second.id or 0)
                    self.assertIsNotNone(saved_second)
                    assert saved_second is not None
                    self.assertEqual(saved_second.source_quality_status, QUESTION_SOURCE_QUALITY_ARCHIVED)
                    self.assertIn(f"Question #{second.id} archived", app.history_text())
                    self.assertIn("pending generated questions не найдены", app.question_text())
                    self.assertIn("Pending: 0", app.history_text())
            finally:
                app.services.close()

    async def test_tui_content_screen_pauses_and_resumes_worker_without_deleting_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_content_pause.db"))
            try:
                queued = app.services.repository.create_content_generation_job(
                    "question",
                    '{"topic_id": 1, "note": "Оставить в очереди во время pause."}',
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "/content"
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "/pause-content"
                    await pilot.press("enter")
                    await pilot.pause()

                    app.start_background_content_worker()
                    paused_job = app.services.repository.get_content_generation_job(queued.id or 0)
                    self.assertTrue(app.content_worker_paused)
                    self.assertFalse(app.content_worker_running)
                    self.assertIsNotNone(paused_job)
                    self.assertEqual(paused_job.status, "queued")
                    self.assertIn("TUI worker: paused", app.question_text())
                    self.assertIn("queue q1/r0/f0", app.content_status_text())

                    app.start_background_content_worker = lambda: setattr(
                        app,
                        "content_status",
                        "resume worker requested",
                    )
                    input_bar.value = "/resume-content"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertFalse(app.content_worker_paused)
                    self.assertIn("resume worker requested", app.content_status_text())
                    resumed_job = app.services.repository.get_content_generation_job(queued.id or 0)
                    self.assertIsNotNone(resumed_job)
                    self.assertEqual(resumed_job.status, "queued")
            finally:
                app.services.close()

    async def test_tui_content_screen_retries_failed_job(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_content_retry.db"))
            try:
                failed = app.services.repository.create_content_generation_job(
                    "question",
                    (
                        '{"topic_id": 1, "note": "Повторить генерацию.", '
                        '"retry": {"attempt": 1, "max_attempts": 3, '
                        '"next_attempt_at": "2026-05-13T10:00:00", "last_error": "timeout"}}'
                    ),
                )
                app.services.repository.update_content_generation_job(
                    failed.id or 0,
                    "failed",
                    error="Ollama timeout",
                )
                app.start_background_content_worker = lambda: setattr(
                    app,
                    "content_status",
                    "retry worker started",
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "/content"
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = f"/retry-job {failed.id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    retried = app.services.repository.get_content_generation_job(failed.id or 0)
                    self.assertIsNotNone(retried)
                    self.assertEqual(retried.status, "queued")
                    self.assertIsNone(retried.error)
                    self.assertIn(f"Content job #{failed.id} возвращен в queued", app.history_text())
                    self.assertIn("retry worker started", app.content_status_text())
                    self.assertIn("Queued: 1", app.question_text())
                    self.assertIn("Failed: 0", app.question_text())
            finally:
                app.services.close()

    async def test_tui_generate_curriculum_command_queues_job_and_starts_worker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_generate_curriculum.db"))
            try:
                app.start_background_content_worker = lambda: setattr(
                    app,
                    "content_status",
                    "curriculum worker started",
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "/generate-curriculum"
                    await pilot.press("enter")
                    await pilot.pause()

                    jobs = app.services.repository.list_content_generation_jobs(status="queued")
                    self.assertEqual(len(jobs), 1)
                    self.assertEqual(jobs[0].kind, "curriculum")
                    self.assertIn("TUI /generate-curriculum", jobs[0].payload_json)
                    self.assertIn('"topic_count": 3', jobs[0].payload_json)
                    self.assertIn("Curriculum generation job", app.history_text())
                    self.assertIn("curriculum worker started", app.content_status_text())
                    self.assertIn("queue q1/r0/f0", app.content_status_text())
            finally:
                app.services.close()

    async def test_tui_auto_queues_learning_material_when_entering_learning_mode(self) -> None:
        class FakeContentGeneration:
            def __init__(self):
                self.learning_called_with = None

            def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
                return None

            def ensure_learning_material(self, topic_id, note=""):
                self.learning_called_with = (topic_id, note)
                return SimpleNamespace(id=43)

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_auto_learning.db"))
            fake_content = FakeContentGeneration()
            app.services.content_generation = fake_content
            app.start_background_content_worker = lambda: setattr(app, "content_status", "learning worker started")
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "learning")
                self.assertIsNotNone(fake_content.learning_called_with)
                self.assertEqual(fake_content.learning_called_with[0], 1)
                self.assertEqual(app.content_status, "learning worker started")

    async def test_tui_auto_queues_system_design_scenario_when_entering_mode(self) -> None:
        class FakeContentGeneration:
            def __init__(self):
                self.scenario_called_with = None

            def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
                return None

            def ensure_system_design_scenario(self, topic_id, note=""):
                self.scenario_called_with = (topic_id, note)
                return SimpleNamespace(id=44)

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_auto_system_design.db"))
            fake_content = FakeContentGeneration()
            app.services.content_generation = fake_content
            app.start_background_content_worker = lambda: setattr(app, "content_status", "scenario worker started")
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/system-design"
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "system_design")
                self.assertIsNotNone(fake_content.scenario_called_with)
                self.assertEqual(app.content_status, "scenario worker started")

    async def test_tui_reuses_saved_learning_material_without_queueing_job(self) -> None:
        class FakeContentGeneration:
            def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
                return None

            def ensure_learning_material(self, topic_id, note=""):
                raise AssertionError("learning material should be loaded from SQLite")

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_saved_learning.db"))
            app.services.repository.add_learning_material(
                LearningMaterial(
                    id=None,
                    topic_id=1,
                    title="Учебный разбор: saved",
                    body="Сохраненный учебный материал про descriptors.",
                    source="test",
                    created_at=datetime.now(),
                )
            )
            app.services.content_generation = FakeContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "learning")
                self.assertIn("Сохраненный учебный материал", app.question_text())

    async def test_tui_reuses_saved_system_design_scenario_without_queueing_job(self) -> None:
        class FakeContentGeneration:
            def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
                return None

            def ensure_system_design_scenario(self, topic_id, note=""):
                raise AssertionError("system design scenario should be loaded from SQLite")

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_saved_system_design.db"))
            topic = app.services.repository.find_topic_by_slug("system-design")
            app.services.repository.add_system_design_scenario(
                SystemDesignScenario(
                    id=None,
                    topic_id=topic.id,
                    title="Saved scenario",
                    scenario="Спроектируй сохраненный сервис коротких ссылок.",
                    focus_areas=["requirements", "API", "observability"],
                    source="test",
                    created_at=datetime.now(),
                )
            )
            app.services.content_generation = FakeContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/system-design"
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "system_design")
                self.assertIn("сохраненный сервис коротких ссылок", app.question_text())
                self.assertIn("observability", app.question_text())

    async def test_tui_materials_screen_lists_and_opens_saved_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_materials.db"))
            created_at = datetime.now()
            app.services.repository.add_learning_material(
                LearningMaterial(
                    id=None,
                    topic_id=1,
                    title="Учебный разбор: descriptors",
                    body="Материал про data descriptor и ORM поля.",
                    source="test",
                    created_at=created_at,
                )
            )
            app.services.repository.add_learning_material(
                LearningMaterial(
                    id=None,
                    topic_id=2,
                    title="Учебный разбор: async workers",
                    body="Материал про async worker backpressure.",
                    source="test",
                    created_at=created_at + timedelta(minutes=1),
                )
            )
            app.services.repository.add_learning_material(
                LearningMaterial(
                    id=None,
                    topic_id=1,
                    title="Учебный разбор: descriptors v2",
                    body="Последняя версия материала про descriptors.",
                    source="test",
                    created_at=created_at + timedelta(minutes=2),
                )
            )
            topic = app.services.repository.find_topic_by_slug("system-design")
            app.services.repository.add_system_design_scenario(
                SystemDesignScenario(
                    id=None,
                    topic_id=topic.id,
                    title="Scenario: links",
                    scenario="Спроектируй сервис коротких ссылок с аналитикой.",
                    focus_areas=["requirements", "API"],
                    source="test",
                    created_at=created_at,
                )
            )
            app.services.repository.add_system_design_scenario(
                SystemDesignScenario(
                    id=None,
                    topic_id=2,
                    title="Scenario: async workers",
                    scenario="Спроектируй worker platform с backpressure и DLQ.",
                    focus_areas=["queues", "retries"],
                    source="test",
                    created_at=created_at + timedelta(minutes=1),
                )
            )
            app.services.repository.add_system_design_scenario(
                SystemDesignScenario(
                    id=None,
                    topic_id=topic.id,
                    title="Scenario: links v2",
                    scenario="Спроектируй последнюю версию сервиса коротких ссылок.",
                    focus_areas=["scaling", "observability"],
                    source="test",
                    created_at=created_at + timedelta(minutes=2),
                )
            )
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/materials"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "artifacts")
                self.assertEqual(app.query_one("#left_panel").styles.display, "none")
                self.assertEqual(app.query_one("#right_panel").styles.display, "block")
                self.assertIn("Learning materials", app.question_text())
                self.assertIn("/material 1", app.question_text())
                self.assertIn("/material 3", app.question_text())
                self.assertNotIn("/material 2", app.question_text())
                self.assertIn("v1/2", app.question_text())
                self.assertIn("v2/2 latest", app.question_text())
                self.assertIn("/material latest", app.question_text())
                self.assertIn("/scenario 1", app.question_text())
                self.assertIn("/scenario 3", app.question_text())
                self.assertNotIn("/scenario 2", app.question_text())
                self.assertIn("/scenario latest", app.question_text())
                self.assertNotIn("Последние события", app.question_text())
                materials_side_panel = app.history_text()
                self.assertIn("Materials", materials_side_panel)
                self.assertIn("Следующее действие", materials_side_panel)
                self.assertIn("Фильтр learning materials: current topic", materials_side_panel)
                self.assertIn("Фильтр system design scenarios: current topic", materials_side_panel)
                self.assertIn("Learning materials: 2", materials_side_panel)
                self.assertIn("System design scenarios: 2", materials_side_panel)
                self.assertIn("/regen-material", materials_side_panel)
                self.assertNotIn("Материал про data descriptor", materials_side_panel)

                input_bar.value = "/materials all"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("[bold]Фильтр learning materials[/bold]: все темы", app.question_text())
                self.assertIn("/material 1", app.question_text())
                self.assertIn("/material 2", app.question_text())
                self.assertIn("/material 3", app.question_text())
                self.assertIn("Материал про async worker backpressure", app.question_text())
                self.assertIn("Фильтр learning materials: all topics", app.history_text())
                self.assertIn("Learning materials: 3", app.history_text())

                input_bar.value = "/materials scenarios all"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("[bold]Фильтр system design scenarios[/bold]: все темы", app.question_text())
                self.assertIn("/scenario 1", app.question_text())
                self.assertIn("/scenario 2", app.question_text())
                self.assertIn("/scenario 3", app.question_text())
                self.assertIn("Спроектируй worker platform", app.question_text())
                self.assertIn("Фильтр system design scenarios: all topics", app.history_text())
                self.assertIn("System design scenarios: 3", app.history_text())

                input_bar.value = "/materials scenarios current"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("/scenario 1", app.question_text())
                self.assertIn("/scenario 3", app.question_text())
                self.assertNotIn("/scenario 2", app.question_text())

                input_bar.value = "/materials current"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("/material 1", app.question_text())
                self.assertIn("/material 3", app.question_text())
                self.assertNotIn("/material 2", app.question_text())

                input_bar.value = "/archive-material 3"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("Для архивации используй", app.history_text())
                self.assertIn("/material 3", app.question_text())

                input_bar.value = "/archive-material 3 confirm hallucinated details"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("Учебный материал #3 archived", app.history_text())
                self.assertIn("Reason: hallucinated details", app.history_text())
                self.assertIn("/material 1", app.question_text())
                self.assertNotIn("/material 3", app.question_text())
                self.assertIsNone(app.services.repository.get_learning_material(3))
                archived_material = app.services.repository.get_learning_material(3, include_archived=True)
                self.assertIsNotNone(archived_material)
                self.assertIsNotNone(archived_material.archived_at)
                self.assertEqual(archived_material.archive_reason, "hallucinated details")

                input_bar.value = "/preview-material latest"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "artifacts")
                preview_text = app.question_text()
                self.assertIn("Artifact preview", preview_text)
                self.assertIn("Preview: learning material", preview_text)
                self.assertIn("Версия: v1/1 latest", preview_text)
                self.assertIn("Материал про data descriptor и ORM поля.", preview_text)

                input_bar.value = "/preview-scenario latest"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "artifacts")
                preview_text = app.question_text()
                self.assertIn("Preview: system design scenario", preview_text)
                self.assertIn("Версия: v2/2 latest", preview_text)
                self.assertIn("Спроектируй последнюю версию сервиса коротких ссылок.", preview_text)
                self.assertIn("- scaling", preview_text)

                input_bar.value = "/archive-scenario 3"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("Для архивации используй", app.history_text())
                self.assertIn("/scenario 3", app.question_text())

                input_bar.value = "/archive-scenario 3 confirm missing reliability focus"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("System design scenario #3 archived", app.history_text())
                self.assertIn("Reason: missing reliability focus", app.history_text())
                self.assertIn("/scenario 1", app.question_text())
                self.assertNotIn("/scenario 3", app.question_text())
                self.assertIsNone(app.services.repository.get_system_design_scenario(3))
                archived_scenario = app.services.repository.get_system_design_scenario(3, include_archived=True)
                self.assertIsNotNone(archived_scenario)
                self.assertIsNotNone(archived_scenario.archived_at)
                self.assertEqual(archived_scenario.archive_reason, "missing reliability focus")

                input_bar.value = "/preview-scenario latest"
                await pilot.press("enter")
                await pilot.pause()
                preview_text = app.question_text()
                self.assertIn("Preview: system design scenario", preview_text)
                self.assertIn("Версия: v1/1 latest", preview_text)
                self.assertIn("Спроектируй сервис коротких ссылок с аналитикой.", preview_text)

                input_bar.value = "/material latest"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "learning")
                self.assertIn("Материал про data descriptor и ORM поля.", app.question_text())

                input_bar.value = "/materials"
                await pilot.press("enter")
                await pilot.pause()
                input_bar.value = "/scenario 1"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "system_design")
                self.assertIn("сервис коротких ссылок", app.question_text())
                self.assertIn("requirements", app.question_text())

    async def test_tui_materials_screen_links_to_notebook_topic_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_materials_notebook.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                current_topic = app.services.repository.find_topic_by_slug("python-runtime")
                other_topic = app.services.repository.find_topic_by_slug("async-backend")
                self.assertIsNotNone(current_topic)
                self.assertIsNotNone(other_topic)
                created_at = datetime(2026, 5, 19, 9, 0, 0)
                app.services.repository.add_learning_material(
                    LearningMaterial(
                        id=None,
                        topic_id=current_topic.id,
                        title="Runtime material",
                        body="Материал про descriptor protocol.",
                        source="test",
                        created_at=created_at,
                    )
                )
                app.services.repository.add_learning_material(
                    LearningMaterial(
                        id=None,
                        topic_id=other_topic.id,
                        title="Async material",
                        body="Материал про backpressure.",
                        source="test",
                        created_at=created_at + timedelta(minutes=1),
                    )
                )
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=current_topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-runtime",
                        source_message_id=None,
                        title="Runtime notebook entry",
                        body="Descriptor notebook note.",
                        source="learning-ai",
                        created_at=created_at + timedelta(minutes=2),
                    )
                )
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=other_topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-async",
                        source_message_id=None,
                        title="Async notebook entry",
                        body="Backpressure notebook note.",
                        source="learning-ai",
                        created_at=created_at + timedelta(minutes=3),
                    )
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)
                    input_bar.value = str(current_topic.id)
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "/materials"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "artifacts")
                    self.assertIn(f"/notebook topic {current_topic.id}", app.question_text())
                    self.assertIn(f"/notebook topic {current_topic.id}", app.history_text())

                    input_bar.value = "/materials all"
                    await pilot.press("enter")
                    await pilot.pause()

                    materials_text = app.question_text()
                    self.assertIn("Async material", materials_text)
                    self.assertIn(f"/notebook topic {other_topic.id}", materials_text)

                    input_bar.value = f"/notebook topic {other_topic.id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    notebook_text = app.question_text()
                    self.assertEqual(app.mode, "notebook")
                    self.assertEqual(app.notebook_topic_filter, other_topic.id)
                    self.assertIn(f"[bold]Фильтр[/bold]: topic #{other_topic.id}", notebook_text)
                    self.assertIn("Async notebook entry", notebook_text)
                    self.assertNotIn("Runtime notebook entry", notebook_text)
            finally:
                app.services.close()

    async def test_tui_can_answer_one_question_and_save_score(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui.db"))
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                topic = app.services.questions.list_topics()[0]
                input_bar.value = str(topic.id)
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "answering")
                self.assertIsNotNone(app.session)
                self.assertIsNotNone(app.question)

                input_bar.value = "Дескрипторы помогают управлять доступом к атрибутам."
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "scoring")
                self.assertIsNotNone(app.current_answer)
                scoring_text = app.question_text()
                self.assertIn("Ответ сохранен. Осталось указать самооценку", scoring_text)
                self.assertIn("Ожидает самооценку 1-5", scoring_text)
                self.assertLess(scoring_text.index("Твой ответ"), scoring_text.index("Самооценка"))
                self.assertLess(scoring_text.index("Самооценка"), scoring_text.index("Эталонный ответ"))
                scoring_side_panel = app.history_text()
                self.assertIn("Следующее действие", scoring_side_panel)
                self.assertIn("Введи самооценку 1-5", scoring_side_panel)
                self.assertIn("Последние события", scoring_side_panel)
                self.assertIn("Ответ сохранен как", scoring_side_panel)
                self.assertNotIn("Дескрипторы помогают управлять доступом", scoring_side_panel)
                self.assertNotIn("Эталонный ответ", scoring_side_panel)

                input_bar.value = "4"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "answered")
                self.assertEqual(app.current_answer.self_score, 4)
                evaluations = app.services.repository.list_answer_evaluations_for_answer(app.current_answer.id or 0)
                self.assertEqual(len(evaluations), 1)
                self.assertEqual(evaluations[0].answer_id, app.current_answer.id)
                self.assertEqual(evaluations[0].source, "heuristic")
                self.assertIsNone(app.current_answer.ai_feedback)
                question_text = app.question_text()
                self.assertIn("Ответ сохранен, самооценка 4/5", question_text)
                self.assertIn("/feedback запросит AI feedback", question_text)
                self.assertIn("Rubric scores", question_text)
                self.assertIn("Средний rubric score", question_text)
                self.assertIn("Correctness (correctness)", question_text)
                self.assertLess(question_text.index("Твой ответ"), question_text.index("Самооценка"))
                self.assertLess(question_text.index("Самооценка"), question_text.index("Rubric scores"))
                self.assertLess(question_text.index("Rubric scores"), question_text.index("Эталонный ответ"))
                self.assertIn("4/5", question_text)
                answered_side_panel = app.history_text()
                self.assertIn("Следующее действие", answered_side_panel)
                self.assertIn("Нажми Enter для следующего вопроса", answered_side_panel)
                self.assertNotIn("Эталонный ответ", answered_side_panel)
                self.assertEqual(app.services.repository.stats()["answered_count"], 1)

    async def test_tui_composer_submits_multiline_practice_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_multiline_composer.db"))
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                answer = "Дескриптор вызывается через lookup.\n\n```python\nobj.field\n```"
                input_bar.value = answer
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "scoring")
                self.assertIsNotNone(app.current_answer)
                self.assertEqual(app.current_answer.user_answer, answer)
                self.assertEqual(input_bar.value, "")

    async def test_tui_composer_expands_for_long_multiline_draft(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_composer_expand.db"))
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", Composer)

                self.assertEqual(input_bar.styles.height.value, Composer.MIN_HEIGHT)

                input_bar.value = "\n".join(
                    [
                        "```python",
                        "def service():",
                        "    return 'ok'",
                        "```",
                        "",
                        "Пояснение к решению.",
                    ]
                )
                await pilot.pause()

                self.assertEqual(input_bar.styles.height.value, 8)

                input_bar.value = "\n".join(f"строка {index}" for index in range(20))
                await pilot.pause()

                self.assertEqual(input_bar.styles.height.value, Composer.MAX_HEIGHT)

                input_bar.value = ""
                await pilot.pause()

                self.assertEqual(input_bar.styles.height.value, Composer.MIN_HEIGHT)

    async def test_tui_composer_shift_enter_inserts_newline_before_submit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_shift_enter_composer.db"))
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "Первая строка"
                input_bar.move_cursor(input_bar.document.end)
                await pilot.press("shift+enter")
                await pilot.pause()
                input_bar.insert("Вторая строка")

                self.assertEqual(input_bar.value, "Первая строка\nВторая строка")

                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "scoring")
                self.assertIsNotNone(app.current_answer)
                self.assertEqual(
                    app.current_answer.user_answer,
                    "Первая строка\nВторая строка",
                )

    async def test_tui_composer_submits_multiline_code_block_to_learning(self) -> None:
        class FakeLearning:
            def __init__(self):
                self.last_message = ""

            def explain(self, user_message, topic=None, question=None):
                self.last_message = user_message
                return f"Разбор сохраненного вопроса:\n{user_message}"

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_learning_multiline_composer.db"))
            app.services.content_generation = self.QuietContentGeneration()
            fake_learning = FakeLearning()
            app.services.learning = fake_learning
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "Объясни descriptor lookup на примере"
                input_bar.move_cursor(input_bar.document.end)
                await pilot.press("shift+enter")
                await pilot.pause()
                input_bar.insert("\n```python\nobj.field\n```")
                expected_message = "Объясни descriptor lookup на примере\n\n```python\nobj.field\n```"

                self.assertEqual(input_bar.value, expected_message)

                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "learning" and len(app.learning_transcript) == 2:
                        break

                self.assertEqual(fake_learning.last_message, expected_message)
                self.assertEqual(app.learning_transcript[0], ("Ты", expected_message))
                self.assertIn("obj.field", app.question_text())
                self.assertEqual(input_bar.value, "")

    async def test_tui_composer_submits_multiline_code_block_to_system_design(self) -> None:
        class FakeSystemDesign:
            def __init__(self):
                self.last_message = ""

            def next_turn(self, scenario, transcript, user_message):
                self.last_message = user_message
                return "Интервьюер: уточни rate limits и failure modes."

            def final_feedback(self, scenario, transcript):
                return "Feedback не используется в этом тесте."

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design_multiline_composer.db"))
            app.services.content_generation = self.QuietContentGeneration()
            fake_system_design = FakeSystemDesign()
            app.services.system_design = fake_system_design
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/system-design"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "Начну с API контракта"
                input_bar.move_cursor(input_bar.document.end)
                await pilot.press("shift+enter")
                await pilot.pause()
                input_bar.insert("\n```http\nPOST /links\nGET /{code}\n```")
                expected_message = "Начну с API контракта\n\n```http\nPOST /links\nGET /{code}\n```"

                self.assertEqual(input_bar.value, expected_message)

                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "system_design" and len(app.system_design_transcript) == 2:
                        break

                self.assertEqual(fake_system_design.last_message, expected_message)
                self.assertEqual(app.system_design_transcript[0], ("Кандидат", expected_message))
                self.assertIn("POST /links", app.question_text())
                self.assertEqual(input_bar.value, "")

    async def test_tui_daily_practice_shows_ai_feedback_in_center_panel(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_feedback.db"))
            app.services.sessions.feedback_with_quality = lambda question, answer: GeneratedFeedback(
                text="AI говорит: добавь tradeoffs и failure modes.",
                quality=FeedbackQuality(flags=()),
            )
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "Дескрипторы управляют доступом к атрибутам."
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "4"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/feedback"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if "AI говорит" in app.question_text():
                        break

                self.assertEqual(app.mode, "answered")
                self.assertIn("AI feedback", app.question_text())
                self.assertIn("AI feedback готов", app.question_text())
                self.assertIn("failure modes", app.question_text())
                side_panel = app.history_text()
                self.assertIn("Следующее действие", side_panel)
                self.assertIn("Нажми Enter, чтобы перейти к следующему вопросу", side_panel)
                self.assertIn("AI feedback готов", side_panel)
                self.assertNotIn("failure modes", side_panel)

    async def test_tui_note_from_answer_saves_feedback_gap_to_notebook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_note_from_answer.db"))
            app.services.sessions.feedback_with_quality = lambda question, answer: GeneratedFeedback(
                text=(
                    "Хорошо:\n"
                    "- Ты обозначил descriptors.\n\n"
                    "Упущено:\n"
                    "- Добавь failure modes и production tradeoffs.\n\n"
                    "Что повторить:\n"
                    "- Idempotency и retry policy."
                ),
                quality=FeedbackQuality(flags=()),
            )
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "Дескрипторы управляют доступом к атрибутам."
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "3"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/feedback"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if "failure modes" in app.question_text():
                        break

                answer_id = app.current_answer.id if app.current_answer is not None else None
                topic_id = app.question.topic_id if app.question is not None else None
                input_bar.value = "/note-from-answer"
                await pilot.press("enter")
                await pilot.pause()

                entries = app.services.repository.list_notebook_entries(topic_id=topic_id)
                self.assertEqual(len(entries), 1)
                saved = entries[0]
                self.assertEqual(saved.source, "answer-feedback")
                self.assertEqual(saved.dialog_session_id, f"answer:{answer_id}")
                self.assertIn("Feedback gap", saved.body)
                self.assertIn("Упущено", saved.body)
                self.assertIn("failure modes", saved.body)
                self.assertIn("Idempotency", saved.body)
                self.assertNotIn("Ты обозначил descriptors", saved.body)
                self.assertIn("Gap из последнего feedback сохранен", "\n".join(app.history))

                input_bar.value = "/notebook"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("answer-feedback", app.question_text())

                input_bar.value = f"/notebook entry {saved.id}"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("failure modes", app.question_text())

    async def test_tui_recheck_feedback_replaces_last_feedback_with_strict_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_recheck_feedback.db"))
            app.services.sessions.feedback_with_quality = lambda question, answer: GeneratedFeedback(
                text="Хорошо:\n- Отлично раскрыл B-tree и query plans.\n\nУпущено:\n- Добавь детали.",
                quality=FeedbackQuality(flags=(FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG,)),
            )
            recheck_calls = []

            def recheck_feedback(question, answer, previous_feedback=None):
                recheck_calls.append((answer, previous_feedback))
                return GeneratedFeedback(
                    text=(
                        "Понял твой ответ:\n"
                        "- Ты написал, что не знаешь.\n\n"
                        "Хорошо:\n"
                        "- Пока нет подтвержденных сильных сторон в ответе.\n\n"
                        "Упущено:\n"
                        "- Нужно разобрать B-tree и query plans."
                    ),
                    quality=FeedbackQuality(flags=()),
                )

            app.services.sessions.recheck_feedback_with_quality = recheck_feedback
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "не знаю"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/feedback"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if "Отлично раскрыл B-tree" in app.question_text():
                        break
                old_feedback = app.current_answer.ai_feedback

                input_bar.value = "/recheck-feedback"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if "Пока нет подтвержденных сильных сторон" in app.question_text():
                        break

                self.assertEqual(app.mode, "answered")
                self.assertEqual(recheck_calls, [("не знаю", old_feedback)])
                self.assertIn("AI feedback перепроверен строгим prompt", "\n".join(app.history))
                self.assertIn("Пока нет подтвержденных сильных сторон", app.question_text())
                self.assertNotIn("Отлично раскрыл B-tree", app.question_text())
                row = app.services.repository.connection.execute(
                    "SELECT ai_feedback FROM answers WHERE id = ?",
                    (app.current_answer.id,),
                ).fetchone()
                self.assertIn("Пока нет подтвержденных сильных сторон", row["ai_feedback"])

    async def test_tui_daily_practice_warns_about_suspicious_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_feedback_warning.db"))
            app.services.sessions.feedback_with_quality = lambda question, answer: GeneratedFeedback(
                text="Хорошо:\n- Отлично раскрыл эталонные tradeoffs.\n\nУпущено:\n- Добавь evidence.",
                quality=FeedbackQuality(flags=(FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG,)),
            )
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "не знаю"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/feedback"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if "Проверь AI feedback" in app.question_text():
                        break

                question_text = app.question_text()
                self.assertIn("Проверь AI feedback", question_text)
                self.assertIn("Похвала в feedback может быть не подтверждена", question_text)
                self.assertIn("rubric scores", question_text)
                self.assertIn("AI feedback", question_text)

    async def test_tui_slash_commands_update_visible_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_commands.db"))
            app.services.repository.add_question(
                Question(
                    id=None,
                    topic_id=1,
                    difficulty="middle+",
                    prompt="Дополнительный вопрос для проверки skip.",
                    hint="Проверь, что skip переходит дальше.",
                    reference_answer="Skip должен выбрать следующий доступный вопрос.",
                    source="test",
                )
            )
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/hint"
                await pilot.press("enter")
                await pilot.pause()
                self.assertTrue(app.showing_hint)

                input_bar.value = "/answer"
                await pilot.press("enter")
                await pilot.pause()
                self.assertTrue(app.showing_reference)

                input_bar.value = "/stats"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("Статистика:", app.last_feedback)

                input_bar.value = "/commands"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIn("Command palette", app.last_feedback)
                self.assertIn("/feedback", app.last_feedback)

                first_question_id = app.question.id
                input_bar.value = "/skip"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.skipped_count, 1)
                self.assertNotEqual(app.question.id, first_question_id)

                input_bar.value = "/quit"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "ended")
                self.assertIn("Summary сессии", app.last_feedback)

    async def test_tui_quit_after_answer_shows_session_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_quit_outcome.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "1"
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertIsNotNone(app.session)
                    session_id = app.session.id or 0

                    input_bar.value = "Использую индексы, но без деталей про tradeoffs."
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "2"
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "/quit"
                    await pilot.press("enter")
                    await pilot.pause()

                    outcome = app.services.repository.get_session_outcome_for_session(session_id)
                    self.assertIsNotNone(outcome)
                    self.assertEqual(app.mode, "ended")
                    self.assertIn("Итог сессии", app.last_feedback)
                    self.assertIn("Средняя самооценка: 2.0/5.", app.last_feedback)
                    self.assertIn("Readiness delta", app.question_text())
                    self.assertIn("Next drills", app.question_text())
            finally:
                app.services.close()

    async def test_tui_finish_session_shows_outcome_without_exiting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_finish_session_outcome.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "1"
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertIsNotNone(app.session)
                    session_id = app.session.id or 0

                    input_bar.value = "Использую индексы, но без деталей про tradeoffs."
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "2"
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "/finish-session"
                    await pilot.press("enter")
                    await pilot.pause()

                    outcome = app.services.repository.get_session_outcome_for_session(session_id)
                    self.assertIsNotNone(outcome)
                    self.assertEqual(app.mode, "session_finished")
                    self.assertIn("Итог сессии", app.question_text())
                    self.assertIn("без выхода из TUI", "\n".join(app.history))
                    self.assertIn("/practice для новой сессии", app.question_text())

                    input_bar.value = f"/history {session_id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    self.assertEqual(app.mode, "history")
                    history_detail = app.question_text()
                    self.assertIn(f"Session #{session_id}", history_detail)
                    self.assertIn("Итог сессии", history_detail)
                    self.assertIn("Средняя самооценка: 2.0/5.", history_detail)
                    self.assertIn("Answers", history_detail)
            finally:
                app.services.close()

    async def test_tui_target_time_completion_shows_session_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_target_time_outcome.db"))
            app.services.content_generation = self.QuietContentGeneration()
            try:
                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "1"
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertIsNotNone(app.session)
                    session_id = app.session.id or 0

                    input_bar.value = "Кратко объясняю ответ для проверки завершения по времени."
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "3"
                    await pilot.press("enter")
                    await pilot.pause()

                    app.started_at = datetime.now() - timedelta(minutes=61)
                    app.refresh_topbar()
                    await pilot.pause()

                    outcome = app.services.repository.get_session_outcome_for_session(session_id)
                    self.assertIsNotNone(outcome)
                    self.assertEqual(app.mode, "ended")
                    self.assertIn("Target time истек", "\n".join(app.history))
                    self.assertIn("Итог сессии", app.question_text())
            finally:
                app.services.close()

    async def test_tui_quit_without_answers_marks_session_abandoned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_abandoned_session.db"))
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()
                self.assertIsNotNone(app.session)
                session_id = app.session.id or 0

                input_bar.value = "/quit"
                await pilot.press("enter")
                await pilot.pause()

                saved = app.services.repository.get_session(session_id)
                self.assertIsNotNone(saved)
                self.assertEqual(saved.status, SESSION_STATUS_ABANDONED)
                self.assertIsNotNone(saved.ended_at)
                self.assertEqual(app.services.sessions.list_completed_sessions(), [])

    async def test_tui_has_scrollable_panels_and_notes_editor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_layout.db"))
            async with app.run_test(size=(120, 36)) as pilot:
                self.assertIsInstance(app.query_one("#left_panel"), VerticalScroll)
                self.assertIsInstance(app.query_one("#center_panel"), VerticalScroll)
                self.assertIsInstance(app.query_one("#history_scroll"), VerticalScroll)
                notes = app.query_one("#notes_editor", TextArea)
                notes.text = "Заметка 1\n\nЗаметка 2"

                input_bar = app.query_one("#input_bar", TextArea)
                input_bar.value = "/notes"
                await pilot.press("enter")
                await pilot.pause()
                self.assertTrue(notes.has_focus)

                app.focus_input()
                self.assertEqual(app.notes_text(), "Заметка 1\n\nЗаметка 2")

    async def test_tui_save_note_command_persists_multiline_composer_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_save_note.db"))
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()
                session_id = app.session.id if app.session is not None else None
                topic_id = app.topic.id if app.topic is not None else None
                self.assertIsNotNone(session_id)
                self.assertIsNotNone(topic_id)

                input_bar.value = (
                    "/save-note Retry semantics\n"
                    "Проверить idempotency keys перед повторным ответом.\n"
                    "Сравнить retry/backoff и exactly-once иллюзии."
                )
                await pilot.press("enter")
                await pilot.pause()

                saved = app.services.repository.list_manual_notes(
                    context_type="tui-saved-note",
                    context_id=f"session:{session_id}",
                )
                self.assertEqual(len(saved), 1)
                self.assertEqual(saved[0].title, "Retry semantics")
                self.assertEqual(
                    saved[0].body,
                    "Проверить idempotency keys перед повторным ответом.\n"
                    "Сравнить retry/backoff и exactly-once иллюзии.",
                )
                self.assertEqual(saved[0].session_id, session_id)
                self.assertEqual(saved[0].topic_id, topic_id)
                self.assertEqual(input_bar.value, "")
                self.assertIn("Manual note", app.history_text())

    async def test_tui_saves_notes_editor_draft_on_mode_switch_and_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_notes_draft.db"))
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()
                session_id = app.session.id if app.session is not None else None
                self.assertIsNotNone(session_id)

                notes = app.query_one("#notes_editor", TextArea)
                notes.text = "Разобрать idempotency keys после ответа."
                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()

                saved = app.services.repository.list_manual_notes(
                    context_type="tui-notes-draft",
                    context_id=f"session:{session_id}",
                )
                self.assertEqual(len(saved), 1)
                self.assertEqual(saved[0].body, "Разобрать idempotency keys после ответа.")
                self.assertEqual(saved[0].session_id, session_id)

                notes.text = "Обновленный draft перед выходом."
                input_bar.value = "/quit"
                await pilot.press("enter")
                await pilot.pause()

                updated = app.services.repository.list_manual_notes(
                    context_type="tui-notes-draft",
                    context_id=f"session:{session_id}",
                )
                self.assertEqual([note.id for note in updated], [saved[0].id])
                self.assertEqual(updated[0].body, "Обновленный draft перед выходом.")

    async def test_tui_restores_notes_editor_draft_when_context_returns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_notes_restore.db"))
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)
                notes = app.query_one("#notes_editor", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()
                session = app.session
                topic = app.topic
                self.assertIsNotNone(session)
                self.assertIsNotNone(topic)

                notes.text = "Session draft: проверить ретраи после practice."
                app.persist_notes_draft()

                app.session = None
                app.topic = None
                app.mode = "select_topic"
                app.render_all()
                self.assertEqual(notes.text, "")

                app.session = session
                app.topic = topic
                app.mode = "answering"
                app.render_all()
                self.assertEqual(notes.text, "Session draft: проверить ретраи после practice.")

                app.session = None
                app.topic = topic
                app.mode = "select_topic"
                app.render_all()
                notes.text = "Topic draft: перечитать descriptors."
                app.persist_notes_draft()

                other_topic = app.services.repository.find_topic_by_slug("async-backend")
                app.topic = other_topic
                app.render_all()
                self.assertEqual(notes.text, "")

                app.topic = topic
                app.render_all()
                self.assertEqual(notes.text, "Topic draft: перечитать descriptors.")

    async def test_tui_unmount_persists_notes_draft_across_database_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "tui_notes_unmount_reopen.db")
            first_app = InterviewPrepTUI(db_path)
            async with first_app.run_test(size=(120, 36)):
                notes = first_app.query_one("#notes_editor", TextArea)
                notes.text = "Global draft before closing TUI."

            reopened_app = InterviewPrepTUI(db_path)
            try:
                async with reopened_app.run_test(size=(120, 36)):
                    notes = reopened_app.query_one("#notes_editor", TextArea)
                    self.assertEqual(notes.text, "Global draft before closing TUI.")
            finally:
                reopened_app.services.close()

    async def test_tui_unmount_clears_running_content_worker_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_worker_unmount.db"))
            async with app.run_test(size=(120, 36)):
                app.content_worker_running = True
                app.content_status = "generating..."

            self.assertFalse(app.content_worker_running)
            self.assertEqual(app.content_status, "idle")

    async def test_tui_learning_mode_does_not_save_interview_answer(self) -> None:
        class FakeLearning:
            def explain(self, user_message, topic=None, question=None):
                return f"Учебный ответ: {user_message}"

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_learning.db"))
            app.services.learning = FakeLearning()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "learning")
                self.assertEqual(app.query_one("#left_panel").styles.display, "none")
                self.assertEqual(app.query_one("#right_panel").styles.display, "block")
                learning_side_panel = app.history_text()
                self.assertIn("Learning", learning_side_panel)
                self.assertIn("Следующее действие", learning_side_panel)
                self.assertIn("Реплик в диалоге: 0", learning_side_panel)

                input_bar.value = "Почему дескрипторы вызываются при доступе к атрибуту?"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "learning" and "Учебный ответ" in app.last_feedback:
                        break

                self.assertEqual(app.mode, "learning")
                self.assertIn("Учебный ответ", app.last_feedback)
                self.assertIn("Учебный ответ", app.question_text())
                self.assertNotIn("Учебный ответ", app.history_text())
                self.assertEqual(len(app.learning_transcript), 2)
                self.assertIn("Почему дескрипторы", app.question_text())
                self.assertEqual(app.services.repository.stats()["answered_count"], 0)

                input_bar.value = "А чем data descriptor отличается?"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if len(app.learning_transcript) == 4:
                        break

                self.assertEqual(len(app.learning_transcript), 4)
                self.assertIn("А чем data descriptor отличается?", app.question_text())
                self.assertIn("Учебный диалог", app.question_text())

                input_bar.value = "/practice"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "answering")
                self.assertEqual(app.query_one("#left_panel").styles.display, "block")
                self.assertEqual(app.query_one("#right_panel").styles.display, "block")

    async def test_tui_learning_mode_persists_dialog_through_service(self) -> None:
        class StaticLearningLLM:
            def generate(self, prompt: str) -> str:
                return "Учебный ответ сохранен через сервис."

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_learning_persist.db"))
            app.services.learning = LearningService(app.services.repository, StaticLearningLLM())
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "1"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "Почему descriptor lookup идет через type?"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "learning" and "сохранен через сервис" in app.question_text():
                        break

                messages = app.services.repository.list_learning_dialog_messages(app.topic.id)
                notebook_entries = app.services.repository.list_notebook_entries(topic_id=app.topic.id)

                self.assertEqual([message.role for message in messages], ["user", "assistant"])
                self.assertEqual(messages[0].content, "Почему descriptor lookup идет через type?")
                self.assertEqual(messages[1].content, "Учебный ответ сохранен через сервис.")
                self.assertEqual(len(notebook_entries), 1)
                self.assertEqual(notebook_entries[0].title, "Почему descriptor lookup идет через type?")
                self.assertEqual(notebook_entries[0].body, "Учебный ответ сохранен через сервис.")
                self.assertEqual(notebook_entries[0].source_message_id, messages[1].id)

    async def test_tui_learning_explanation_is_visible_in_topic_notebook(self) -> None:
        class StaticLearningLLM:
            def generate(self, prompt: str) -> str:
                return "Data descriptor проверяется до instance dict, поэтому property выигрывает."

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_learning_notebook_topic.db"))
            app.services.content_generation = self.QuietContentGeneration()
            app.services.learning = LearningService(app.services.repository, StaticLearningLLM())
            try:
                other_topic = app.services.repository.find_topic_by_slug("async-backend")
                app.services.repository.add_notebook_entry(
                    NotebookEntry(
                        id=None,
                        topic_id=other_topic.id,
                        curriculum_subtopic_id=None,
                        dialog_session_id="learn-other-topic",
                        source_message_id=None,
                        title="Async backpressure note",
                        body="Bounded queues protect workers from overload.",
                        source="learning-ai",
                        created_at=datetime(2026, 5, 19, 10, 0, 0),
                    )
                )

                async with app.run_test(size=(120, 36)) as pilot:
                    input_bar = app.query_one("#input_bar", TextArea)

                    input_bar.value = "1"
                    await pilot.press("enter")
                    await pilot.pause()
                    topic_id = app.topic.id

                    input_bar.value = "/learn"
                    await pilot.press("enter")
                    await pilot.pause()

                    input_bar.value = "Почему property перекрывает значение в __dict__?"
                    await pilot.press("enter")
                    for _ in range(20):
                        await pilot.pause()
                        if app.mode == "learning" and "Data descriptor проверяется" in app.question_text():
                            break

                    notebook_entries = app.services.repository.list_notebook_entries(topic_id=topic_id)
                    self.assertEqual(len(notebook_entries), 1)
                    self.assertEqual(
                        notebook_entries[0].title,
                        "Почему property перекрывает значение в __dict__?",
                    )
                    self.assertEqual(notebook_entries[0].source, "learning-ai")

                    input_bar.value = f"/notebook topic {topic_id}"
                    await pilot.press("enter")
                    await pilot.pause()

                    notebook_text = app.question_text()
                    self.assertEqual(app.mode, "notebook")
                    self.assertEqual(app.notebook_topic_filter, topic_id)
                    self.assertIn(f"[bold]Фильтр[/bold]: topic #{topic_id}", notebook_text)
                    self.assertIn("Почему property перекрывает значение в __dict__?", notebook_text)
                    self.assertIn("Data descriptor проверяется до instance dict", notebook_text)
                    self.assertNotIn("Async backpressure note", notebook_text)
            finally:
                app.services.close()

    async def test_tui_learning_mode_loads_saved_dialog_on_enter(self) -> None:
        class FakeContentGeneration:
            def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
                return None

            def ensure_learning_material(self, topic_id, note=""):
                return None

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_learning_restore.db"))
            app.services.content_generation = FakeContentGeneration()
            topic = app.services.repository.find_topic_by_slug("python-runtime")
            app.services.repository.add_learning_dialog_message(
                LearningDialogMessage(
                    id=None,
                    topic_id=topic.id,
                    role="user",
                    content="Что мы уже обсуждали про descriptor lookup?",
                    created_at=datetime(2026, 5, 12, 10, 0, 0),
                )
            )
            app.services.repository.add_learning_dialog_message(
                LearningDialogMessage(
                    id=None,
                    topic_id=topic.id,
                    role="assistant",
                    content="Разбирали порядок поиска через класс и data descriptors.",
                    created_at=datetime(2026, 5, 12, 10, 0, 1),
                )
            )

            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = str(topic.id)
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "learning")
                self.assertEqual(app.learning_transcript[0], ("Ты", "Что мы уже обсуждали про descriptor lookup?"))
                self.assertEqual(
                    app.learning_transcript[1],
                    ("ИИ", "Разбирали порядок поиска через класс и data descriptors."),
                )
                self.assertIn("Что мы уже обсуждали", app.question_text())
                self.assertTrue(
                    any("Загружены последние учебные реплики: 2." in item for item in app.history)
                )

    async def test_tui_learning_before_topic_selection_does_not_load_saved_topic_dialog(self) -> None:
        class NoTopicContentGeneration:
            def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
                return None

            def ensure_learning_material(self, topic_id, note=""):
                raise AssertionError("topicless learning should not queue topic learning material")

            def ensure_system_design_scenario(self, topic_id, note=""):
                return None

            def list_jobs(self, limit=100):
                return []

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_learning_before_topic.db"))
            app.services.content_generation = NoTopicContentGeneration()
            topic = app.services.repository.find_topic_by_slug("python-runtime")
            self.assertIsNotNone(topic)
            app.services.repository.add_learning_dialog_message(
                LearningDialogMessage(
                    id=None,
                    topic_id=topic.id,
                    role="user",
                    content="Старый topic-bound вопрос про descriptor lookup",
                    created_at=datetime(2026, 5, 12, 10, 0, 0),
                )
            )
            app.services.repository.add_learning_dialog_message(
                LearningDialogMessage(
                    id=None,
                    topic_id=topic.id,
                    role="assistant",
                    content="Старое topic-bound объяснение про порядок lookup.",
                    created_at=datetime(2026, 5, 12, 10, 0, 1),
                )
            )

            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(app.mode, "learning")
                self.assertIsNone(app.topic)
                self.assertIsNone(app.session)
                self.assertIsNone(app.learning_topic_id)
                self.assertEqual(app.learning_transcript, [])
                self.assertIsNone(app.generated_learning_material)
                learning_view = app.question_text()
                self.assertIn("без выбранной темы", learning_view)
                self.assertIn("Диалог еще не начат", learning_view)
                self.assertNotIn("Старый topic-bound вопрос", learning_view)
                self.assertNotIn("Старое topic-bound объяснение", learning_view)
                self.assertFalse(
                    any("Загружены последние учебные реплики" in item for item in app.history)
                )

    async def test_tui_learning_mode_navigates_long_dialog(self) -> None:
        class FakeContentGeneration:
            def ensure_question_backlog(self, topic_id, min_questions=4, note=""):
                return None

            def ensure_learning_material(self, topic_id, note=""):
                return None

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_learning_navigation.db"))
            app.services.content_generation = FakeContentGeneration()
            topic = app.services.repository.find_topic_by_slug("python-runtime")
            for index in range(1, 13):
                app.services.repository.add_learning_dialog_message(
                    LearningDialogMessage(
                        id=None,
                        topic_id=topic.id,
                        role="user" if index % 2 else "assistant",
                        content=f"Диалоговая реплика {index:02d}",
                        created_at=datetime(2026, 5, 12, 10, 0, index),
                    )
                )

            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = str(topic.id)
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/learn"
                await pilot.press("enter")
                await pilot.pause()

                self.assertIn("Показаны реплики 3-12 из 12", app.question_text())
                self.assertNotIn("Диалоговая реплика 01", app.question_text())
                self.assertIn("Диалоговая реплика 12", app.question_text())

                input_bar.value = "/learn-older"
                await pilot.press("enter")
                await pilot.pause()

                self.assertIn("Показаны реплики 1-10 из 12", app.question_text())
                self.assertIn("Диалоговая реплика 01", app.question_text())
                self.assertNotIn("Диалоговая реплика 12", app.question_text())

                input_bar.value = "/learn-newer"
                await pilot.press("enter")
                await pilot.pause()

                self.assertIn("Показаны реплики 3-12 из 12", app.question_text())
                self.assertIn("Диалоговая реплика 12", app.question_text())

    async def test_tui_system_design_mode_runs_interviewer_flow_without_saving_answer(self) -> None:
        class FakeSystemDesign:
            def __init__(self, repository):
                self.repository = repository

            def next_turn(self, scenario, transcript, user_message):
                return f"Интервьюер: уточни API для `{user_message}`"

            def final_feedback(self, scenario, transcript):
                return "Уровень: senior. Пробелы: добавь observability."

            def save_transcript_turn(self, topic_id, user_message, interviewer_response, scenario_id=None):
                self.repository.add_system_design_transcript_message(
                    SystemDesignTranscriptMessage(
                        id=None,
                        topic_id=topic_id,
                        scenario_id=scenario_id,
                        role="candidate",
                        content=user_message,
                        created_at=datetime.now(),
                    )
                )
                self.repository.add_system_design_transcript_message(
                    SystemDesignTranscriptMessage(
                        id=None,
                        topic_id=topic_id,
                        scenario_id=scenario_id,
                        role="interviewer",
                        content=interviewer_response,
                        created_at=datetime.now(),
                    )
                )

            def save_final_feedback(self, topic_id, feedback, scenario_id=None, session_id=None, source="llm"):
                return self.repository.add_system_design_feedback_artifact(
                    SystemDesignFeedbackArtifact(
                        id=None,
                        topic_id=topic_id,
                        scenario_id=scenario_id,
                        session_id=session_id,
                        content=feedback.strip(),
                        source=source,
                        created_at=datetime.now(),
                    )
                )

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design.db"))
            app.services.system_design = FakeSystemDesign(app.services.repository)
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/system-design"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "system_design")
                self.assertIsNotNone(app.session)
                self.assertEqual(app.query_one("#left_panel").styles.display, "none")
                self.assertEqual(app.query_one("#right_panel").styles.display, "block")
                system_design_side_panel = app.history_text()
                self.assertIn("System design", system_design_side_panel)
                self.assertIn("Следующее действие", system_design_side_panel)
                self.assertIn("Начни с requirements", system_design_side_panel)
                self.assertIn("Реплик в transcript: 0", system_design_side_panel)

                artifacts = [
                    ("/req SLA 99.9%, короткие ссылки доступны публично", "requirements", "SLA 99.9%"),
                    ("/api POST /links и GET /{code}", "api", "POST /links"),
                    ("/data links(id, code, target_url)", "data_model", "links(id"),
                    ("/decision Redis cache для hot links", "decisions", "Redis cache"),
                    ("/risk hot keys и abuse", "risks", "hot keys"),
                ]
                for command, section, expected in artifacts:
                    input_bar.value = command
                    await pilot.press("enter")
                    await pilot.pause()
                    self.assertIn(expected, app.system_design_artifacts[section][-1])
                    self.assertIn(expected, app.question_text())

                input_bar.value = "Начну с требований, SLA и публичного API."
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "system_design" and "Интервьюер" in app.last_feedback:
                        break

                self.assertEqual(app.mode, "system_design")
                self.assertEqual(len(app.system_design_transcript), 2)
                system_design_side_panel = app.history_text()
                self.assertIn("Продолжай решение", system_design_side_panel)
                self.assertIn("Реплик в transcript: 2", system_design_side_panel)
                self.assertNotIn("Начну с требований", system_design_side_panel)
                self.assertNotIn("уточни API", system_design_side_panel)
                self.assertIn("Начну с требований", app.question_text())
                self.assertIn("уточни API", app.question_text())
                saved_transcript = app.services.repository.list_system_design_transcript_messages(
                    app.topic.id,
                    scenario_id=app.system_design_scenario_id,
                )
                self.assertEqual([message.role for message in saved_transcript], ["candidate", "interviewer"])
                self.assertIn("Начну с требований", saved_transcript[0].content)
                self.assertEqual(app.services.repository.stats()["answered_count"], 0)

                input_bar.value = "/sd-feedback"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if "Итоговый system design feedback" in app.last_feedback:
                        break

                self.assertIn("Уровень: senior", app.last_feedback)
                saved_feedback = app.services.repository.list_system_design_feedback_artifacts(
                    app.topic.id,
                    scenario_id=app.system_design_scenario_id,
                    session_id=app.session.id,
                )
                self.assertEqual(len(saved_feedback), 1)
                self.assertIn("Уровень: senior", saved_feedback[0].content)
                self.assertEqual(saved_feedback[0].source, "llm")
                self.assertEqual(app.services.repository.stats()["answered_count"], 0)

                input_bar.value = "/practice"
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(app.mode, "answering")
                self.assertIsNotNone(app.question)
                self.assertEqual(app.query_one("#left_panel").styles.display, "block")
                self.assertEqual(app.query_one("#right_panel").styles.display, "block")

    async def test_tui_system_design_artifact_commands_improve_final_rubric_score(self) -> None:
        class EvaluatingSystemDesign(SystemDesignService):
            def next_turn(self, scenario, transcript, user_message):
                return f"Интервьюер: зафиксировал sparse ответ `{user_message}`."

            def final_feedback(self, scenario, transcript):
                return "Уровень: middle+. Итоговый feedback сохранен для rubric evaluation."

        def scores_by_slug(evaluation):
            return {score.dimension.slug: score.score for score in evaluation.scores}

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design_artifact_scores.db"))
            app.services.system_design = EvaluatingSystemDesign(app.services.repository, app.services.llm)
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/system-design"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "Опишу детали позже."
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "system_design" and "sparse ответ" in app.last_feedback:
                        break

                input_bar.value = "/sd-feedback"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "system_design" and "Итоговый system design feedback" in app.last_feedback:
                        break

                baseline_feedback = app.services.repository.list_system_design_feedback_artifacts(
                    app.topic.id,
                    scenario_id=app.system_design_scenario_id,
                    session_id=app.session.id,
                )
                self.assertEqual(len(baseline_feedback), 1)
                baseline_evaluation = app.services.repository.get_system_design_evaluation_for_feedback(
                    baseline_feedback[0].id or 0
                )
                self.assertIsNotNone(baseline_evaluation)
                assert baseline_evaluation is not None
                baseline_scores = scores_by_slug(baseline_evaluation)

                artifact_commands = [
                    "/req requirements scope actors SLA availability latency constraints",
                    "/api API POST /links GET /{code} request response status 400 404 429",
                    "/data data model table links schema storage postgres index migration",
                    "/decision decision choose Redis cache versus database alternative cost risk",
                    "/risk failure retries timeout fallback DLQ circuit abuse protection risk",
                ]
                for command in artifact_commands:
                    input_bar.value = command
                    await pilot.press("enter")
                    await pilot.pause()

                input_bar.value = "/sd-feedback"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    feedback_artifacts = app.services.repository.list_system_design_feedback_artifacts(
                        app.topic.id,
                        scenario_id=app.system_design_scenario_id,
                        session_id=app.session.id,
                    )
                    if len(feedback_artifacts) == 2:
                        break

                feedback_artifacts = app.services.repository.list_system_design_feedback_artifacts(
                    app.topic.id,
                    scenario_id=app.system_design_scenario_id,
                    session_id=app.session.id,
                )
                self.assertEqual(len(feedback_artifacts), 2)
                improved_evaluation = app.services.repository.get_system_design_evaluation_for_feedback(
                    feedback_artifacts[-1].id or 0
                )
                self.assertIsNotNone(improved_evaluation)
                assert improved_evaluation is not None
                improved_scores = scores_by_slug(improved_evaluation)

                self.assertGreater(
                    sum(improved_scores.values()) / len(improved_scores),
                    sum(baseline_scores.values()) / len(baseline_scores),
                )
                for slug in ("requirements", "api", "data-model", "tradeoffs", "reliability"):
                    with self.subTest(slug=slug):
                        self.assertGreater(improved_scores[slug], baseline_scores[slug])
                        self.assertGreaterEqual(improved_scores[slug], 4)

    async def test_tui_system_design_checkpoint_saves_interviewer_message_without_final_feedback(self) -> None:
        class FakeSystemDesign:
            def __init__(self, repository):
                self.repository = repository
                self.final_feedback_called = False
                self.checkpoint_artifacts = None

            def checkpoint(self, scenario, transcript, artifacts):
                self.checkpoint_artifacts = artifacts
                return (
                    "Checkpoint:\n"
                    "- Что уже понятно: есть SLA.\n"
                    "- Главный риск или пробел: не хватает data model.\n"
                    "- Следующий лучший шаг: зафиксируй storage.\n"
                    "Вопрос интервьюера: как ты задашь idempotency key?"
                )

            def add_transcript_message(self, topic_id, role, content, scenario_id=None):
                return self.repository.add_system_design_transcript_message(
                    SystemDesignTranscriptMessage(
                        id=None,
                        topic_id=topic_id,
                        scenario_id=scenario_id,
                        role=role,
                        content=content,
                        created_at=datetime.now(),
                    )
                )

            def final_feedback(self, scenario, transcript):
                self.final_feedback_called = True
                return "Этот метод не должен вызываться."

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design_checkpoint.db"))
            fake_system_design = FakeSystemDesign(app.services.repository)
            app.services.system_design = fake_system_design
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/system-design"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/req SLA 99.9%, transactional notifications"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/sd-checkpoint"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "system_design" and "System design checkpoint" in app.last_feedback:
                        break

                self.assertEqual(app.mode, "system_design")
                self.assertFalse(fake_system_design.final_feedback_called)
                self.assertIsNotNone(fake_system_design.checkpoint_artifacts)
                self.assertIn("SLA 99.9%", fake_system_design.checkpoint_artifacts["requirements"][0])
                self.assertEqual(len(app.system_design_transcript), 1)
                self.assertEqual(app.system_design_transcript[0][0], "Интервьюер")
                self.assertIn("idempotency key", app.question_text())
                saved_transcript = app.services.repository.list_system_design_transcript_messages(
                    app.topic.id,
                    scenario_id=app.system_design_scenario_id,
                )
                self.assertEqual([message.role for message in saved_transcript], ["interviewer"])
                saved_feedback = app.services.repository.list_system_design_feedback_artifacts(app.topic.id)
                self.assertEqual(saved_feedback, [])
                self.assertEqual(app.services.repository.stats()["answered_count"], 0)

    async def test_tui_system_design_pressure_saves_interviewer_follow_up_without_final_feedback(self) -> None:
        class FakeSystemDesign:
            def __init__(self, repository):
                self.repository = repository
                self.final_feedback_called = False
                self.pressure_artifacts = None

            def pressure_follow_up(self, scenario, transcript, artifacts):
                self.pressure_artifacts = artifacts
                return (
                    "Pressure follow-up:\n"
                    "- Focus: capacity planning и hot keys.\n"
                    "- Why now: текущий дизайн должен выдержать traffic skew.\n"
                    "Question: как ты задашь capacity target, hot key mitigation и abuse limit?"
                )

            def add_transcript_message(self, topic_id, role, content, scenario_id=None):
                return self.repository.add_system_design_transcript_message(
                    SystemDesignTranscriptMessage(
                        id=None,
                        topic_id=topic_id,
                        scenario_id=scenario_id,
                        role=role,
                        content=content,
                        created_at=datetime.now(),
                    )
                )

            def final_feedback(self, scenario, transcript):
                self.final_feedback_called = True
                return "Этот метод не должен вызываться."

        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design_pressure.db"))
            fake_system_design = FakeSystemDesign(app.services.repository)
            app.services.system_design = fake_system_design
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/system-design"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/risk hot keys и abuse на public endpoint"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/sd-pressure"
                await pilot.press("enter")
                for _ in range(20):
                    await pilot.pause()
                    if app.mode == "system_design" and "System design pressure follow-up" in app.last_feedback:
                        break

                self.assertEqual(app.mode, "system_design")
                self.assertFalse(fake_system_design.final_feedback_called)
                self.assertIsNotNone(fake_system_design.pressure_artifacts)
                self.assertIn("hot keys", fake_system_design.pressure_artifacts["risks"][0])
                self.assertEqual(len(app.system_design_transcript), 1)
                self.assertEqual(app.system_design_transcript[0][0], "Интервьюер")
                self.assertIn("capacity target", app.question_text())
                saved_transcript = app.services.repository.list_system_design_transcript_messages(
                    app.topic.id,
                    scenario_id=app.system_design_scenario_id,
                )
                self.assertEqual([message.role for message in saved_transcript], ["interviewer"])
                saved_feedback = app.services.repository.list_system_design_feedback_artifacts(app.topic.id)
                self.assertEqual(saved_feedback, [])
                self.assertEqual(app.services.repository.stats()["answered_count"], 0)

    async def test_tui_persists_and_restores_system_design_artifacts_for_scenario(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = str(Path(tmp) / "tui_system_design_artifacts.db")
            first_app = InterviewPrepTUI(db_path)
            first_app.services.content_generation = self.QuietContentGeneration()
            topic_id = first_app.services.repository.find_topic_by_slug("system-design").id
            scenario = first_app.services.repository.add_system_design_scenario(
                SystemDesignScenario(
                    id=None,
                    topic_id=topic_id,
                    title="Notifications",
                    scenario="Спроектируй сервис уведомлений.",
                    focus_areas=["requirements", "risks"],
                    source="test",
                    created_at=datetime(2026, 5, 12, 10, 0, 0),
                )
            )
            async with first_app.run_test(size=(120, 36)) as pilot:
                input_bar = first_app.query_one("#input_bar", TextArea)

                input_bar.value = f"/scenario {scenario.id}"
                await pilot.press("enter")
                await pilot.pause()

                input_bar.value = "/req transactional и marketing уведомления"
                await pilot.press("enter")
                await pilot.pause()
                input_bar.value = "/risk provider outage и дубли доставки"
                await pilot.press("enter")
                await pilot.pause()

                saved = first_app.services.repository.list_system_design_artifacts(
                    topic_id,
                    scenario_id=scenario.id,
                )
                self.assertEqual([artifact.section for artifact in saved], ["requirements", "risks"])

            second_app = InterviewPrepTUI(db_path)
            second_app.services.content_generation = self.QuietContentGeneration()
            async with second_app.run_test(size=(120, 36)) as pilot:
                input_bar = second_app.query_one("#input_bar", TextArea)

                input_bar.value = f"/scenario {scenario.id}"
                await pilot.press("enter")
                await pilot.pause()

                self.assertEqual(
                    second_app.system_design_artifacts["requirements"],
                    ["transactional и marketing уведомления"],
                )
                self.assertEqual(second_app.system_design_artifacts["risks"], ["provider outage и дубли доставки"])
                self.assertIn("transactional и marketing", second_app.question_text())

    async def test_tui_autosaves_explicit_artifact_commands_from_system_design_transcript(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design_transcript_artifacts.db"))
            app.services.content_generation = self.QuietContentGeneration()
            async with app.run_test(size=(120, 36)) as pilot:
                input_bar = app.query_one("#input_bar", TextArea)

                input_bar.value = "/system-design"
                await pilot.press("enter")
                await pilot.pause()

                app.finish_system_design_turn(
                    "\n".join(
                        [
                            "Начну с явной фиксации decisions прямо в transcript.",
                            "/req SLA 99.9%, публичные короткие ссылки",
                            "/api POST /links и GET /{code}",
                            "/risk hot keys и abuse",
                        ]
                    ),
                    "Интервьюер: уточни data model.",
                    None,
                )

                artifacts = app.services.repository.list_system_design_artifacts(
                    app.topic.id,
                    scenario_id=app.system_design_scenario_id,
                )
                self.assertEqual(
                    [(artifact.section, artifact.content) for artifact in artifacts],
                    [
                        ("requirements", "SLA 99.9%, публичные короткие ссылки"),
                        ("api", "POST /links и GET /{code}"),
                        ("risks", "hot keys и abuse"),
                    ],
                )
                self.assertIn("SLA 99.9%", app.question_text())
                self.assertIn("Автоперенос artifact-команд", "\n".join(app.history))


class TUIHelperTests(unittest.TestCase):
    def test_format_duration(self) -> None:
        from datetime import timedelta

        self.assertEqual(format_duration(timedelta(seconds=75)), "01:15")

    def test_extract_system_design_artifact_commands(self) -> None:
        self.assertEqual(
            extract_system_design_artifact_commands(
                "\n".join(
                    [
                        "Начинаю с scope.",
                        "  /requirement только публичные ссылки",
                        "/data links(id, code, target_url)",
                        "/decision Redis для hot links",
                        "/risk  provider outage  ",
                        "/sd-feedback",
                    ]
                )
            ),
            [
                ("requirements", "только публичные ссылки"),
                ("data_model", "links(id, code, target_url)"),
                ("decisions", "Redis для hot links"),
                ("risks", "provider outage"),
            ],
        )

    def test_notes_line_count(self) -> None:
        self.assertEqual(notes_line_count(""), 0)
        self.assertEqual(notes_line_count("one\n\ntwo"), 2)

    def test_one_line_preview(self) -> None:
        self.assertEqual(one_line_preview("one\n two"), "one two")
        self.assertTrue(one_line_preview("x" * 200).endswith("..."))

    def test_render_chat_message_escapes_user_rich_markup(self) -> None:
        rendered = render_chat_message("Ты", "[bold]не markup[/bold]\n```python\nprint(1)\n```")

        self.assertIn("[bold cyan]Ты[/bold cyan]", rendered)
        self.assertIn("[dim]---[/dim]", rendered)
        self.assertIn(r"\[bold]не markup\[/bold]", rendered)
        self.assertIn("```python", rendered)

    def test_render_llm_markdown_uses_rich_markdown_output(self) -> None:
        rendered = render_llm_markdown("# Заголовок\n\n- пункт\n\n```python\nprint(1)\n```")

        self.assertIn("Заголовок", rendered)
        self.assertIn("пункт", rendered)
        self.assertIn("print(1)", rendered)
        self.assertNotIn("```", rendered)
        self.assertNotIn("# Заголовок", rendered)
        self.assertNotIn("- пункт", rendered)

    def test_render_chat_message_renders_ai_markdown_before_escaping(self) -> None:
        markdown = "\n".join(
            [
                "# Разбор ответа",
                "",
                "- сильная сторона",
                "- что повторить",
                "",
                "```python",
                "def example():",
                "    return 1",
                "```",
            ]
        )

        for role in ("ИИ", "Интервьюер", "Эталонный ответ", "AI feedback"):
            with self.subTest(role=role):
                rendered = render_chat_message(role, markdown)

                self.assertIn(f"[bold magenta]{role}[/bold magenta]", rendered)
                self.assertIn("Разбор ответа", rendered)
                self.assertIn("сильная сторона", rendered)
                self.assertIn("что повторить", rendered)
                self.assertIn("def example():", rendered)
                self.assertIn("return 1", rendered)
                self.assertNotIn("# Разбор ответа", rendered)
                self.assertNotIn("- сильная сторона", rendered)
                self.assertNotIn("```python", rendered)
                self.assertNotIn("```", rendered)

    def test_learning_text_uses_chat_renderer_for_dialog_and_pending_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_learning_renderer.db"))
            topic = app.services.repository.find_topic_by_slug("python-runtime")
            app.mode = "loading_learning"
            app.topic = topic
            app.learning_transcript = [
                ("Ты", "[bold]saved user[/bold]"),
                ("ИИ", "[green]saved assistant[/green]"),
            ]
            app.learning_pending_message = "[italic]pending question[/italic]"

            rendered = app.learning_text()

            self.assertGreaterEqual(rendered.count("[dim]---[/dim]"), 3)
            self.assertIn("[bold cyan]Ты[/bold cyan]", rendered)
            self.assertIn("[bold magenta]ИИ[/bold magenta]", rendered)
            self.assertIn(r"\[bold]saved user\[/bold]", rendered)
            self.assertIn(r"\[green]saved assistant\[/green]", rendered)
            self.assertIn(r"\[italic]pending question\[/italic]", rendered)
            self.assertNotIn("[bold]saved user[/bold]", rendered)
            self.assertNotIn("[green]saved assistant[/green]", rendered)

    def test_system_design_text_uses_chat_renderer_for_transcript_pending_and_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design_renderer.db"))
            try:
                topic = app.services.repository.find_topic_by_slug("system-design")
                app.mode = "system_design"
                app.topic = topic
                app.system_design_transcript = [
                    ("Кандидат", "[bold]candidate text[/bold]"),
                    ("Интервьюер", "[green]interviewer text[/green]"),
                ]
                app.system_design_pending_message = "[italic]pending design[/italic]"
                app.last_feedback = "Итоговый system design feedback\n\n[red]feedback text[/red]"

                rendered = app.system_design_text()

                self.assertGreaterEqual(rendered.count("[dim]---[/dim]"), 4)
                self.assertIn("[bold cyan]Кандидат[/bold cyan]", rendered)
                self.assertIn("[bold magenta]Интервьюер[/bold magenta]", rendered)
                self.assertIn("[bold magenta]ИИ[/bold magenta]", rendered)
                self.assertIn(r"\[bold]candidate text\[/bold]", rendered)
                self.assertIn(r"\[green]interviewer text\[/green]", rendered)
                self.assertIn(r"\[italic]pending design\[/italic]", rendered)
                self.assertIn(r"\[red]feedback text\[/red]", rendered)
                self.assertNotIn("[bold]candidate text[/bold]", rendered)
                self.assertNotIn("[green]interviewer text[/green]", rendered)
                self.assertNotIn("[italic]pending design[/italic]", rendered)
                self.assertNotIn("[red]feedback text[/red]", rendered)
            finally:
                app.services.close()

    def test_system_design_text_shows_missing_sections_before_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_system_design_missing_sections.db"))
            try:
                app.mode = "system_design"
                app.topic = app.services.repository.find_topic_by_slug("system-design")
                app.system_design_artifacts["requirements"].append("SLA 99.9% и публичный API.")

                rendered = app.system_design_text()

                self.assertIn("Missing sections before /sd-feedback", rendered)
                self.assertIn("Пустые секции: API, Data model, Risks / failure modes.", rendered)
                self.assertNotIn("Пустые секции: Requirements", rendered)

                app.system_design_artifacts["api"].append("POST /links и GET /{code}.")
                app.system_design_artifacts["data_model"].append("links(id, code, target_url).")
                app.system_design_artifacts["risks"].append("hot keys, retries и abuse.")

                self.assertNotIn("Missing sections before /sd-feedback", app.system_design_text())
            finally:
                app.services.close()

    def test_daily_practice_review_uses_chat_renderer_for_answer_reference_and_feedback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app = InterviewPrepTUI(str(Path(tmp) / "tui_practice_renderer.db"))
            try:
                app.mode = "answered"
                app.question = Question(
                    id=1,
                    topic_id=1,
                    difficulty="middle",
                    prompt="Что важно в descriptors?",
                    hint="Вспомни lookup order.",
                    reference_answer="[green]reference[/green]",
                )
                app.pending_answer_text = "[bold]candidate[/bold]"
                app.showing_reference = True
                app.current_answer = Answer(
                    id=1,
                    session_id=1,
                    question_id=1,
                    user_answer=app.pending_answer_text,
                    self_score=4,
                    ai_feedback="[red]feedback[/red]",
                    answered_at=datetime.now(),
                )

                rendered = app.question_text()

                self.assertGreaterEqual(rendered.count("[dim]---[/dim]"), 3)
                self.assertIn("[bold cyan]Твой ответ[/bold cyan]", rendered)
                self.assertIn("[bold magenta]Эталонный ответ[/bold magenta]", rendered)
                self.assertIn("[bold magenta]AI feedback[/bold magenta]", rendered)
                self.assertLess(rendered.index("Твой ответ"), rendered.index("Самооценка"))
                self.assertLess(rendered.index("Самооценка"), rendered.index("Эталонный ответ"))
                self.assertLess(rendered.index("Эталонный ответ"), rendered.index("[bold magenta]AI feedback"))
                self.assertIn(r"\[bold]candidate\[/bold]", rendered)
                self.assertIn(r"\[green]reference\[/green]", rendered)
                self.assertIn(r"\[red]feedback\[/red]", rendered)
                self.assertNotIn("[bold]candidate[/bold]", rendered)
                self.assertNotIn("[green]reference[/green]", rendered)
                self.assertNotIn("[red]feedback[/red]", rendered)
            finally:
                app.services.close()

    def test_command_palette_text_lists_core_commands(self) -> None:
        palette = command_palette_text()

        self.assertIn("Команды сгруппированы по workflow.", palette)
        for group in [
            "Today workflow",
            "Practice workflow",
            "Learning workflow",
            "Notebook workflow",
            "Content workflow",
            "Materials workflow",
            "System design workflow",
            "History workflow",
            "Utility",
        ]:
            self.assertIn(group, palette)
        self.assertLess(palette.index("Today workflow"), palette.index("/accept-topic"))
        self.assertLess(palette.index("Practice workflow"), palette.index("/hint"))
        self.assertLess(palette.index("Content workflow"), palette.index("/content"))
        self.assertLess(palette.index("System design workflow"), palette.index("/sd <сценарий>"))
        self.assertLess(palette.index("History workflow"), palette.index("/history   read-only"))
        self.assertIn("/learn", palette)
        self.assertIn("/accept-topic", palette)
        self.assertIn("/content", palette)
        self.assertIn("/generate-curriculum", palette)
        self.assertIn("/pause-content", palette)
        self.assertIn("/resume-content", palette)
        self.assertIn("/retry-job", palette)
        self.assertIn("/questions-review список", palette)
        self.assertIn("/questions-review accept", palette)
        self.assertIn("/questions-review archive", palette)
        self.assertIn("/materials", palette)
        self.assertIn("/materials current/all", palette)
        self.assertIn("/materials scenarios current/all", palette)
        self.assertIn("/archive-scenario", palette)
        self.assertIn("/notebook конспект обучения", palette)
        self.assertIn("/notebook competency", palette)
        self.assertIn("/note-from-answer", palette)
        self.assertIn("/readiness focused dashboard", palette)
        self.assertIn("/history system-design", palette)
        self.assertIn("/notes", palette)
        self.assertIn("/system-design", palette)
        self.assertIn("/sd-checkpoint", palette)
        self.assertIn("/sd-pressure", palette)
        self.assertIn("/sd-feedback", palette)
        self.assertIn("/finish-session", palette)
        self.assertIn("/req", palette)
        self.assertIn("/decision", palette)

    def test_content_artifact_label_formats_curriculum_jobs(self) -> None:
        label = content_artifact_id_label(
            "curriculum",
            {
                "kind": "curriculum",
                "topic_count": 1,
                "questions_saved": 1,
            },
        )

        self.assertEqual(label, "curriculum:1t/1q")


if __name__ == "__main__":
    unittest.main()
