from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from interview_prep.domain.models import (
    Answer,
    CurriculumObjective,
    CurriculumSubtopic,
    CurriculumTopic,
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_ARCHIVED,
    QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
    QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
    Question,
    QuestionAutoCurationAudit,
    QuestionCompetencyLink,
    Session,
    SessionOutcome,
    SystemDesignScenario,
    Tag,
)
from interview_prep.infra.database import connect, init_db
from interview_prep.infra.llm import FallbackLLMClient, LLMClient, LLMUnavailable, ResilientLLMClient
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.evaluation_service import EvaluationService
from interview_prep.services.question_source_service import SOURCE_BACKED_CANDIDATE_TEMPLATES
from interview_prep.services.system_design_service import SystemDesignService
from interview_prep.ui.cli import read_answer


class CLIFlowTests(unittest.TestCase):
    def test_read_answer_single_line_finishes_on_enter(self) -> None:
        with patch("builtins.input", return_value="Descriptor answer"):
            self.assertEqual(read_answer(), "Descriptor answer")

    def test_read_answer_multiline_has_explicit_terminator(self) -> None:
        with patch("builtins.input", side_effect=["/multi", "line one", "line two", ""]), redirect_stdout(
            StringIO()
        ):
            self.assertEqual(read_answer(), "line one\nline two")

    def test_session_no_feedback_saves_answer_after_single_line_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "session.db"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "session",
                    "--topic",
                    "1",
                    "--no-feedback",
                    "--db",
                    str(db_path),
                ],
                input="n\nОтвет про дескрипторы\nn\n",
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Ответ принят.", process.stdout)
        self.assertNotIn("Self-score", process.stdout)
        self.assertNotIn("Now rate your answer.", process.stdout)
        self.assertIn("Сохраняю ответ...", process.stdout)
        self.assertIn("Ответ сохранен как #1.", process.stdout)
        self.assertNotIn("Генерирую AI feedback", process.stdout)

    def test_content_generation_commands_are_registered(self) -> None:
        process = subprocess.run(
            [sys.executable, "-m", "interview_prep", "--help"],
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("content-enqueue", process.stdout)
        self.assertIn("content-worker", process.stdout)
        self.assertIn("content-jobs", process.stdout)
        self.assertIn("curriculum-status", process.stdout)
        self.assertIn("questions-review", process.stdout)
        self.assertIn("questions-audit", process.stdout)
        self.assertIn("questions-cleanup", process.stdout)
        self.assertIn("questions-source", process.stdout)
        self.assertIn("evaluations", process.stdout)
        self.assertIn("session-summary", process.stdout)
        self.assertIn("interview-report", process.stdout)
        self.assertIn("system-design-history", process.stdout)

    def test_content_enqueue_accepts_non_question_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "content.db"
            learning_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "content-enqueue",
                    "--topic",
                    "1",
                    "--kind",
                    "learning-material",
                    "Разбор descriptors",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            reference_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "content-enqueue",
                    "--topic",
                    "1",
                    "--kind",
                    "reference-answer",
                    "Обнови эталонные ответы",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(learning_process.returncode, 0, learning_process.stderr)
        self.assertIn("[learning-material] queued", learning_process.stdout)
        self.assertEqual(reference_process.returncode, 0, reference_process.stderr)
        self.assertIn("[reference-answer] queued", reference_process.stdout)

    def test_stats_command_shows_senior_readiness_top_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "stats.db"
            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "stats",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Senior readiness", process.stdout)
        self.assertIn("Signal:", process.stdout)
        self.assertIn("Label: Нужна baseline-практика", process.stdout)
        self.assertIn("Top gaps:", process.stdout)
        self.assertIn("Next action:", process.stdout)
        self.assertIn("Must fix before interview:", process.stdout)
        self.assertIn("не абсолютная оценка кандидата", process.stdout)

    def test_stats_command_shows_weekly_readiness_trend_when_enough_session_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "stats_trend.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("python-runtime")
            self.assertIsNotNone(topic)
            assert topic is not None

            for ended_at, readiness_delta in (
                (datetime(2026, 5, 5, 10, 0, 0), 0.10),
                (datetime(2026, 5, 6, 10, 0, 0), 0.20),
                (datetime(2026, 5, 13, 10, 0, 0), -0.10),
            ):
                session = repository.create_session(
                    Session(
                        id=None,
                        topic_id=topic.id,
                        started_at=ended_at - timedelta(minutes=30),
                        ended_at=None,
                        target_minutes=60,
                    )
                )
                repository.finish_session(session.id or 0, ended_at)
                repository.upsert_session_outcome(
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
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "stats",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Weekly readiness trend:", process.stdout)
        self.assertIn("2026-05-04..2026-05-10: sessions 2, avg delta +0.15", process.stdout)
        self.assertIn("2026-05-11..2026-05-17: sessions 1, avg delta -0.10", process.stdout)

    def test_curriculum_status_command_shows_counts_and_empty_zones(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "curriculum_status.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("python-runtime")
            self.assertIsNotNone(topic)
            assert topic is not None
            curriculum_topic = repository.add_curriculum_topic(
                CurriculumTopic(
                    id=None,
                    topic_id=topic.id,
                    slug="python-runtime-curriculum",
                    title="Python runtime curriculum",
                    description="Runtime internals.",
                    level="middle+",
                    source="llm-seed",
                    order_index=1,
                )
            )
            subtopic = repository.add_curriculum_subtopic(
                CurriculumSubtopic(
                    id=None,
                    curriculum_topic_id=curriculum_topic.id or 0,
                    slug="descriptors",
                    title="Descriptors",
                    description="Descriptor protocol.",
                    source="llm-seed",
                    order_index=1,
                )
            )
            repository.add_curriculum_objective(
                CurriculumObjective(
                    id=None,
                    curriculum_topic_id=curriculum_topic.id or 0,
                    curriculum_subtopic_id=subtopic.id,
                    text="Объяснять descriptor lookup order.",
                    source="llm-seed",
                    order_index=1,
                )
            )
            repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="middle+",
                    prompt="Как работает descriptor lookup order?",
                    hint="Начни с data descriptors.",
                    reference_answer="Descriptor lookup проверяет data descriptors до instance dict.",
                    source="llm-seed",
                )
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "curriculum-status",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Curriculum status (source=llm-seed)", process.stdout)
        self.assertIn("Curriculum topics: 1", process.stdout)
        self.assertIn("Subtopics: 1", process.stdout)
        self.assertIn("Learning objectives: 1", process.stdout)
        self.assertIn("Generated questions: 1", process.stdout)
        self.assertIn("python-runtime-curriculum -> Python runtime", process.stdout)
        self.assertIn("Empty zones:\n- none", process.stdout)

    def test_questions_command_shows_linked_question_tags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            question = repository.list_questions()[0]
            concurrency = repository.upsert_tag(Tag(id=None, slug="concurrency", title="Concurrency"))
            python_runtime = repository.upsert_tag(Tag(id=None, slug="python-runtime", title="Python runtime"))
            repository.set_question_tags(
                question.id or 0,
                [python_runtime.id or 0, concurrency.id or 0],
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions",
                    "--topic",
                    str(question.topic_id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Теги: Concurrency (concurrency), Python runtime (python-runtime)", process.stdout)

    def test_questions_command_shows_linked_question_competencies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            question = repository.list_questions()[0]
            python_runtime = repository.find_competency_by_slug("python-runtime")
            observability = repository.find_competency_by_slug("observability")
            self.assertIsNotNone(python_runtime)
            self.assertIsNotNone(observability)
            repository.set_question_competencies(
                question.id or 0,
                [
                    QuestionCompetencyLink(competency=observability, weight=0.25),
                    QuestionCompetencyLink(competency=python_runtime, is_primary=True, weight=0.75),
                ],
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions",
                    "--topic",
                    str(question.topic_id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(
            "Компетенции: Python Runtime (python-runtime) [основная], Observability (observability)",
            process.stdout,
        )

    def test_questions_command_filters_by_tag_slug(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            first_question, second_question = repository.list_questions()[:2]
            first_prompt = first_question.prompt
            second_prompt = second_question.prompt
            concurrency = repository.upsert_tag(Tag(id=None, slug="concurrency", title="Concurrency"))
            databases = repository.upsert_tag(Tag(id=None, slug="databases", title="Databases"))
            repository.set_question_tags(first_question.id or 0, [concurrency.id or 0])
            repository.set_question_tags(second_question.id or 0, [databases.id or 0])
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions",
                    "--tag",
                    "concurrency",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(first_prompt, process.stdout)
        self.assertIn("Теги: Concurrency (concurrency)", process.stdout)
        self.assertNotIn(second_prompt, process.stdout)

    def test_questions_review_lists_pending_generated_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_review.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("async-backend")
            self.assertIsNotNone(topic)
            assert topic is not None
            pending = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Какие tradeoffs проверить в generated вопросе перед practice loop?",
                    hint="Проверь uniqueness, senior coverage и production realism.",
                    reference_answer="Нужно принять полезные вопросы и архивировать слабые.",
                    source="background-llm",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                    source_url="https://example.com/interview-notes",
                    source_retrieved_at=datetime(2026, 5, 28, 10, 30),
                    source_category_hints=("async", "queues"),
                    source_frequency_hint="high",
                )
            )
            assert pending.id is not None
            repository.add_question_auto_curation_audit(
                QuestionAutoCurationAudit(
                    id=None,
                    question_id=pending.id,
                    previous_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                    decision="quarantined",
                    resulting_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                    confidence=0.72,
                    rationale="Нужна ручная проверка senior-specific constraints.",
                    quality_flags=["needs_audit"],
                    curator_model="deterministic",
                    curator_version="source-backed-auto-curation-v1",
                    source_url="https://example.com/interview-notes",
                    source_retrieved_at=datetime(2026, 5, 28, 10, 30),
                    source_category_hints=["async", "queues"],
                    source_frequency_hint="high",
                    created_at=datetime(2026, 5, 28, 10, 45),
                    curator_score=3,
                    curator_source_evidence="Source mentions async queue incident reviews.",
                )
            )
            accepted = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="middle+",
                    prompt="Этот вопрос уже принят и не должен быть в pending review.",
                    hint="accepted не показывается.",
                    reference_answer="accepted скрыт из pending review.",
                    source="background-llm",
                    source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
                )
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-review",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Generated question audit queue: 1", process.stdout)
        self.assertIn(
            "Auto-curation is the happy path; use this list only for pending_review audit exceptions.",
            process.stdout,
        )
        self.assertIn(f"#{pending.id} Async backend", process.stdout)
        self.assertIn("Source: background-llm", process.stdout)
        self.assertIn("Source metadata: url=https://example.com/interview-notes retrieved_at=2026-05-28T10:30:00", process.stdout)
        self.assertIn("Category hints: async, queues", process.stdout)
        self.assertIn("Frequency hint: high", process.stdout)
        self.assertIn("Quality flags: generic", process.stdout)
        self.assertIn("Latest auto-curation audit:", process.stdout)
        self.assertIn("Curator rationale: Нужна ручная проверка senior-specific constraints.", process.stdout)
        self.assertIn("Source evidence: Source mentions async queue incident reviews.", process.stdout)
        self.assertIn(
            f"Undo hint: questions-source undo --question {pending.id} restores pending_auto_review "
            "if current status is still pending_review",
            process.stdout,
        )
        self.assertIn("Какие tradeoffs проверить", process.stdout)
        self.assertIn("Audit actions: questions-review accept <id> вручную принимает exception", process.stdout)
        self.assertNotIn(f"#{accepted.id}", process.stdout)

    def test_questions_review_accepts_and_archives_pending_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_review_actions.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("databases")
            self.assertIsNotNone(topic)
            assert topic is not None
            first = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Когда принимать generated вопрос про индексы?",
                    hint="Проверь практическую ценность.",
                    reference_answer="Если вопрос уникальный и покрывает senior tradeoffs.",
                    source="llm-seed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                )
            )
            second = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Когда архивировать generated вопрос про индексы?",
                    hint="Проверь дубли и размытость.",
                    reference_answer="Если вопрос дублирует существующий или не дает useful practice.",
                    source="llm-seed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                )
            )
            repository.close()

            accept_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-review",
                    "accept",
                    str(first.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            archive_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-review",
                    "archive",
                    str(second.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            accepted = repository.get_question(first.id or 0)
            archived = repository.get_question(second.id or 0)
            repository.close()

        self.assertEqual(accept_process.returncode, 0, accept_process.stderr)
        self.assertIn("Manual audit override:", accept_process.stdout)
        self.assertIn(f"Question #{first.id} accepted.", accept_process.stdout)
        self.assertEqual(archive_process.returncode, 0, archive_process.stderr)
        self.assertIn("Manual audit override:", archive_process.stdout)
        self.assertIn(f"Question #{second.id} archived.", archive_process.stdout)
        self.assertIsNotNone(accepted)
        self.assertIsNotNone(archived)
        assert accepted is not None
        assert archived is not None
        self.assertEqual(accepted.source_quality_status, QUESTION_SOURCE_QUALITY_ACCEPTED)
        self.assertEqual(archived.source_quality_status, QUESTION_SOURCE_QUALITY_ARCHIVED)

    def test_questions_audit_lists_generic_duplicate_and_too_long_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_audit.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("async-backend")
            self.assertIsNotNone(topic)
            assert topic is not None

            generic = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Разбери ключевой production-риск в backend-flow и какие tradeoffs важны?",
                    hint="Слишком общий prompt должен попасть в audit.",
                    reference_answer="Audit only; no mutation.",
                    source="background-llm",
                    source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
                )
            )
            duplicate_base = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Как безопасно применить retry policy для idempotent payment worker при timeout внешнего API?",
                    hint="Покрой idempotency key, bounded retry, jitter and dead-letter queue.",
                    reference_answer="Сильный ответ связывает retries с idempotency и observability.",
                    source="canonical-2026",
                    source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
                )
            )
            duplicate = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Как безопасно применить retry policy для idempotent payment worker при timeout внешнего API?",
                    hint="Дубль должен ссылаться на первый похожий вопрос.",
                    reference_answer="Audit должен найти дубль, но не менять статус.",
                    source="background-llm",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                )
            )
            too_long = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt=(
                        "Как разобрать incident в asyncio worker pool, где downstream API периодически "
                        "отвечает timeout, очередь растет, retries создают повторные списания, а SLO "
                        "портится без понятного owner signal и rollback plan?"
                    ),
                    hint="Длинный prompt должен попасть в audit при низком пороге.",
                    reference_answer="Audit only; no mutation.",
                    source="llm-seed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                )
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-audit",
                    "--topic",
                    str(topic.id),
                    "--max-prompt-chars",
                    "160",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            saved_generic = repository.get_question(generic.id or 0)
            saved_duplicate = repository.get_question(duplicate.id or 0)
            saved_too_long = repository.get_question(too_long.id or 0)
            repository.close()

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(f"Question quality audit findings for topic #{topic.id}", process.stdout)
        self.assertIn(f"#{generic.id} kind=generic topic={topic.title}", process.stdout)
        self.assertIn("source=background-llm source_quality=accepted status=accepted", process.stdout)
        self.assertIn(f"#{duplicate.id} kind=duplicate topic={topic.title}", process.stdout)
        self.assertIn(f"duplicate_of=#{duplicate_base.id}", process.stdout)
        self.assertIn("source=background-llm source_quality=pending_review status=pending_review", process.stdout)
        self.assertIn(f"#{too_long.id} kind=too-long topic={topic.title}", process.stdout)
        self.assertIn("source=llm-seed source_quality=pending_review status=pending_review", process.stdout)
        self.assertIsNotNone(saved_generic)
        self.assertIsNotNone(saved_duplicate)
        self.assertIsNotNone(saved_too_long)
        assert saved_generic is not None
        assert saved_duplicate is not None
        assert saved_too_long is not None
        self.assertEqual(saved_generic.source_quality_status, QUESTION_SOURCE_QUALITY_ACCEPTED)
        self.assertEqual(saved_duplicate.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_REVIEW)
        self.assertEqual(saved_too_long.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_REVIEW)

    def test_questions_cleanup_archives_accepted_generic_generated_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_cleanup.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("async-backend")
            self.assertIsNotNone(topic)
            assert topic is not None

            generic_generated = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Разбери ключевой production-риск в backend-flow и какие tradeoffs важны?",
                    hint="Generic generated question should be archived.",
                    reference_answer="Cleanup only; no physical delete.",
                    source="background-llm",
                    source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
                )
            )
            canonical_generic = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Разбери ключевой production-риск для конкретного legacy scheduler.",
                    hint="Canonical sources are not generated cleanup targets.",
                    reference_answer="Canonical rows stay accepted.",
                    source="canonical-2026",
                    source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
                )
            )
            pending_generic = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Какие tradeoffs важны в backend-flow?",
                    hint="Pending rows are already out of accepted practice.",
                    reference_answer="Cleanup leaves pending review rows alone.",
                    source="llm-seed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
                )
            )
            specific_generated = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt=(
                        "Как защитить asyncio payment worker от двойного списания, если retry "
                        "после timeout может повторно вызвать внешний API?"
                    ),
                    hint="Specific accepted generated question stays available.",
                    reference_answer="Нужны idempotency key, retry budget, DLQ and observability.",
                    source="background-llm",
                    source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
                )
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-cleanup",
                    "accepted-generic",
                    "--topic",
                    str(topic.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            saved_generic = repository.get_question(generic_generated.id or 0)
            saved_canonical = repository.get_question(canonical_generic.id or 0)
            saved_pending = repository.get_question(pending_generic.id or 0)
            saved_specific = repository.get_question(specific_generated.id or 0)
            repository.close()

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("archived 1 accepted generic generated question", process.stdout)
        self.assertIn(f"#{generic_generated.id} topic={topic.title} status=archived", process.stdout)
        self.assertIsNotNone(saved_generic)
        self.assertIsNotNone(saved_canonical)
        self.assertIsNotNone(saved_pending)
        self.assertIsNotNone(saved_specific)
        assert saved_generic is not None
        assert saved_canonical is not None
        assert saved_pending is not None
        assert saved_specific is not None
        self.assertEqual(saved_generic.source_quality_status, QUESTION_SOURCE_QUALITY_ARCHIVED)
        self.assertEqual(saved_canonical.source_quality_status, QUESTION_SOURCE_QUALITY_ACCEPTED)
        self.assertEqual(saved_pending.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_REVIEW)
        self.assertEqual(saved_specific.source_quality_status, QUESTION_SOURCE_QUALITY_ACCEPTED)

    def test_questions_source_refresh_dry_run_lists_whitelist_without_creating_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_source.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            before_question_count = len(repository.list_questions())
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "refresh",
                    "--dry-run",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            after_question_count = len(repository.list_questions())
            snapshots = repository.list_question_source_snapshots()
            repository.close()

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("Question source refresh dry-run: 16 whitelisted source(s).", process.stdout)
        self.assertIn("S01 title=Python data model", process.stdout)
        self.assertIn("url=https://docs.python.org/3/reference/datamodel.html", process.stdout)
        self.assertIn("category_hints=python-core, descriptors", process.stdout)
        self.assertIn("Dry run: no source snapshots saved and no questions created.", process.stdout)
        self.assertEqual(after_question_count, before_question_count)
        self.assertEqual(snapshots, [])

    def test_questions_source_candidates_saves_pending_auto_review_questions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_source_candidates.db"
            refresh_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "refresh",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            candidates_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "candidates",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            candidates = repository.list_questions(
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW
            )
            accepted_questions = repository.list_questions(source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED)
            repository.close()

        self.assertEqual(refresh_process.returncode, 0, refresh_process.stderr)
        self.assertEqual(candidates_process.returncode, 0, candidates_process.stderr)
        self.assertIn("Question source candidates saved:", candidates_process.stdout)
        self.assertIn("status=pending_auto_review", candidates_process.stdout)
        self.assertIn("url=https://docs.python.org/3/reference/datamodel.html", candidates_process.stdout)
        self.assertIn(
            f"Created {len(SOURCE_BACKED_CANDIDATE_TEMPLATES)} source-backed candidate question(s)",
            candidates_process.stdout,
        )
        self.assertEqual(len(candidates), len(SOURCE_BACKED_CANDIDATE_TEMPLATES))
        self.assertTrue(all(question.source == "source-backed" for question in candidates))
        self.assertTrue(all(question.source_url for question in candidates))
        self.assertTrue(all(question.source_retrieved_at is not None for question in candidates))
        self.assertTrue(
            all(question.source_quality_status == QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW for question in candidates)
        )
        self.assertTrue(all(question.source_quality_status == QUESTION_SOURCE_QUALITY_ACCEPTED for question in accepted_questions))

    def test_questions_source_auto_curate_dry_run_classifies_without_status_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_source_auto_curate.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("async-backend")
            self.assertIsNotNone(topic)
            assert topic is not None
            retrieved_at = datetime(2026, 5, 27, 9, 0, 0)
            good = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt=(
                        "Async webhook worker получает burst событий и downstream API отвечает timeout. "
                        "Как ты задашь bounded concurrency, idempotency и queue lag alerts?"
                    ),
                    hint="Dry-run should mark this as high-confidence.",
                    reference_answer="Нужны bounded queue, idempotency key, retry budget и lag metrics.",
                    source="source-backed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                    source_url="https://docs.python.org/3/library/asyncio.html",
                    source_retrieved_at=retrieved_at,
                    source_category_hints=("async", "queues"),
                    source_frequency_hint="official-docs:common-async-production",
                )
            )
            generic = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Разбери ключевой production-риск в backend-flow и какие tradeoffs важны?",
                    hint="Dry-run should mark this as archive candidate.",
                    reference_answer="Generic candidate.",
                    source="source-backed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                    source_url="https://example.test/source",
                    source_retrieved_at=retrieved_at,
                    source_category_hints=("async",),
                    source_frequency_hint="interview-coverage:generic",
                )
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "auto-curate",
                    "--dry-run",
                    "--topic",
                    str(topic.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            saved_good = repository.get_question(good.id or 0)
            saved_generic = repository.get_question(generic.id or 0)
            repository.close()

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(f"Question source auto-curation dry-run for topic #{topic.id}: 2 pending candidate", process.stdout)
        self.assertIn(f"#{good.id} topic={topic.title} decision=auto_accepted", process.stdout)
        self.assertIn(f"#{generic.id} topic={topic.title} decision=auto_archived", process.stdout)
        self.assertIn("quality_flags=generic", process.stdout)
        self.assertIn("Dry run: no question statuses changed.", process.stdout)
        self.assertIsNotNone(saved_good)
        self.assertIsNotNone(saved_generic)
        assert saved_good is not None
        assert saved_generic is not None
        self.assertEqual(saved_good.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW)
        self.assertEqual(saved_generic.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW)

    def test_questions_source_auto_curate_applies_deterministic_status_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_source_auto_curate_apply.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("async-backend")
            self.assertIsNotNone(topic)
            assert topic is not None
            retrieved_at = datetime(2026, 5, 27, 9, 0, 0)
            good = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt=(
                        "Async webhook worker получает burst событий и downstream API отвечает timeout. "
                        "Как ты задашь bounded concurrency, idempotency и queue lag alerts?"
                    ),
                    hint="Apply should accept this high-confidence candidate.",
                    reference_answer="Нужны bounded queue, idempotency key, retry budget и lag metrics.",
                    source="source-backed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                    source_url="https://docs.python.org/3/library/asyncio.html",
                    source_retrieved_at=retrieved_at,
                    source_category_hints=("async", "queues"),
                    source_frequency_hint="official-docs:common-async-production",
                )
            )
            generic = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Разбери ключевой production-риск в backend-flow и какие tradeoffs важны?",
                    hint="Apply should archive this generic candidate.",
                    reference_answer="Generic candidate.",
                    source="source-backed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                    source_url="https://example.test/source",
                    source_retrieved_at=retrieved_at,
                    source_category_hints=("async",),
                    source_frequency_hint="interview-coverage:generic",
                )
            )
            missing_metadata = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt=(
                        "Async payment worker retries timeout responses. "
                        "Как ты защитишь idempotency, DLQ и user-visible consistency?"
                    ),
                    hint="Apply should leave this quarantined candidate out of practice.",
                    reference_answer="Needs source evidence before automatic acceptance.",
                    source="source-backed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                )
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "auto-curate",
                    "--topic",
                    str(topic.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            saved_good = repository.get_question(good.id or 0)
            saved_generic = repository.get_question(generic.id or 0)
            saved_missing_metadata = repository.get_question(missing_metadata.id or 0)
            repository.close()

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(f"Question source auto-curation apply for topic #{topic.id}: 3 pending candidate", process.stdout)
        self.assertIn(f"#{good.id} topic={topic.title} decision=auto_accepted", process.stdout)
        self.assertIn(f"#{generic.id} topic={topic.title} decision=auto_archived", process.stdout)
        self.assertIn("decision=quarantined", process.stdout)
        self.assertIn(
            "Applied deterministic decisions: accepted 1, archived 1, quarantined 1 left pending_auto_review.",
            process.stdout,
        )
        self.assertIsNotNone(saved_good)
        self.assertIsNotNone(saved_generic)
        self.assertIsNotNone(saved_missing_metadata)
        assert saved_good is not None
        assert saved_generic is not None
        assert saved_missing_metadata is not None
        self.assertEqual(saved_good.source_quality_status, QUESTION_SOURCE_QUALITY_ACCEPTED)
        self.assertEqual(saved_generic.source_quality_status, QUESTION_SOURCE_QUALITY_ARCHIVED)
        self.assertEqual(saved_missing_metadata.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW)

    def test_questions_source_auto_curation_audit_lists_saved_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_source_auto_curation_audit.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("async-backend")
            self.assertIsNotNone(topic)
            assert topic is not None
            retrieved_at = datetime(2026, 5, 27, 9, 0, 0)
            good = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt=(
                        "Async webhook worker получает burst событий и downstream API отвечает timeout. "
                        "Как ты задашь bounded concurrency, idempotency и queue lag alerts?"
                    ),
                    hint="Apply should accept this high-confidence candidate.",
                    reference_answer="Нужны bounded queue, idempotency key, retry budget и lag metrics.",
                    source="source-backed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                    source_url="https://docs.python.org/3/library/asyncio.html",
                    source_retrieved_at=retrieved_at,
                    source_category_hints=("async", "queues"),
                    source_frequency_hint="official-docs:common-async-production",
                )
            )
            generic = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt="Разбери ключевой production-риск в backend-flow и какие tradeoffs важны?",
                    hint="Apply should archive this generic candidate.",
                    reference_answer="Generic candidate.",
                    source="source-backed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                    source_url="https://example.test/source",
                    source_retrieved_at=retrieved_at,
                    source_category_hints=("async",),
                    source_frequency_hint="interview-coverage:generic",
                )
            )
            repository.close()

            apply_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "auto-curate",
                    "--topic",
                    str(topic.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            audit_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "audit",
                    "--topic",
                    str(topic.id),
                    "--status",
                    QUESTION_SOURCE_QUALITY_ACCEPTED,
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            saved_good = repository.get_question(good.id or 0)
            saved_generic = repository.get_question(generic.id or 0)
            repository.close()

        self.assertEqual(apply_process.returncode, 0, apply_process.stderr)
        self.assertEqual(audit_process.returncode, 0, audit_process.stderr)
        self.assertIn(
            f"Question source auto-curation audit for topic #{topic.id}, status accepted: 1 decision",
            audit_process.stdout,
        )
        self.assertIn(f"question=#{good.id} topic={topic.title} decision=auto_accepted", audit_process.stdout)
        self.assertIn("status=pending_auto_review -> accepted current=accepted", audit_process.stdout)
        self.assertIn("curator=deterministic-gates", audit_process.stdout)
        self.assertIn("url=https://docs.python.org/3/library/asyncio.html", audit_process.stdout)
        self.assertIn("category_hints=async, queues", audit_process.stdout)
        self.assertIn("frequency_hint=official-docs:common-async-production", audit_process.stdout)
        self.assertIn("quality_flags=-", audit_process.stdout)
        self.assertIn("source_evidence=-", audit_process.stdout)
        self.assertIn("rationale=Source-backed candidate has source URL", audit_process.stdout)
        self.assertNotIn(f"question=#{generic.id}", audit_process.stdout)
        self.assertIsNotNone(saved_good)
        self.assertIsNotNone(saved_generic)
        assert saved_good is not None
        assert saved_generic is not None
        self.assertEqual(saved_good.source_quality_status, QUESTION_SOURCE_QUALITY_ACCEPTED)
        self.assertEqual(saved_generic.source_quality_status, QUESTION_SOURCE_QUALITY_ARCHIVED)

    def test_questions_source_auto_curation_undo_restores_previous_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "questions_source_auto_curation_undo.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("async-backend")
            self.assertIsNotNone(topic)
            assert topic is not None
            retrieved_at = datetime(2026, 5, 27, 9, 0, 0)
            question = repository.add_question(
                Question(
                    id=None,
                    topic_id=topic.id or 0,
                    difficulty="senior",
                    prompt=(
                        "Async webhook worker получает burst событий и downstream API отвечает timeout. "
                        "Как ты задашь bounded concurrency, idempotency и queue lag alerts?"
                    ),
                    hint="Apply should accept this high-confidence candidate.",
                    reference_answer="Нужны bounded queue, idempotency key, retry budget и lag metrics.",
                    source="source-backed",
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                    source_url="https://docs.python.org/3/library/asyncio.html",
                    source_retrieved_at=retrieved_at,
                    source_category_hints=("async", "queues"),
                    source_frequency_hint="official-docs:common-async-production",
                )
            )
            repository.close()

            apply_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "auto-curate",
                    "--topic",
                    str(topic.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            undo_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "questions-source",
                    "undo",
                    "--question",
                    str(question.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

            connection = connect(db_path)
            repository = SQLiteRepository(connection)
            saved_question = repository.get_question(question.id or 0)
            audits = repository.list_question_auto_curation_audits(question_id=question.id)
            repository.close()

        self.assertEqual(apply_process.returncode, 0, apply_process.stderr)
        self.assertEqual(undo_process.returncode, 0, undo_process.stderr)
        self.assertIn("Question source auto-curation undo: audit #", undo_process.stdout)
        self.assertIn(f"question #{question.id}", undo_process.stdout)
        self.assertIn("status=accepted -> pending_auto_review", undo_process.stdout)
        self.assertIn("audit_row=kept", undo_process.stdout)
        self.assertIsNotNone(saved_question)
        assert saved_question is not None
        self.assertEqual(saved_question.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW)
        self.assertEqual(len(audits), 1)

    def test_evaluations_command_shows_saved_rubric_evaluation_for_answer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "evaluations.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            question = repository.list_questions()[0]
            session = repository.create_session(
                Session(
                    id=None,
                    topic_id=question.topic_id,
                    started_at=datetime(2026, 5, 19, 9, 0, 0),
                    ended_at=None,
                    target_minutes=60,
                )
            )
            answer = repository.add_answer(
                Answer(
                    id=None,
                    session_id=session.id or 0,
                    question_id=question.id or 0,
                    user_answer="Нужно объяснить tradeoffs, rollback, метрики и failure modes.",
                    self_score=4,
                    ai_feedback="Свободный AI feedback остается отдельно.",
                    answered_at=datetime(2026, 5, 19, 9, 10, 0),
                )
            )
            evaluation = EvaluationService(repository).evaluate_and_store_answer(
                answer,
                question,
                use_llm=False,
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "evaluations",
                    "--answer",
                    str(answer.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(f"Rubric evaluation #{evaluation.id} для ответа #{answer.id}", process.stdout)
        self.assertIn("Источник: heuristic", process.stdout)
        self.assertIn("Средний rubric score:", process.stdout)
        self.assertIn("Scores:", process.stdout)
        self.assertIn("- Correctness (correctness):", process.stdout)
        self.assertIn("Evidence:", process.stdout)
        self.assertIn("Gaps:", process.stdout)
        self.assertIn("Next drills:", process.stdout)

    def test_evaluation_override_command_updates_one_dimension_with_audit_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "evaluation_override.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            question = repository.list_questions()[0]
            session = repository.create_session(
                Session(
                    id=None,
                    topic_id=question.topic_id,
                    started_at=datetime(2026, 5, 26, 9, 0, 0),
                    ended_at=None,
                    target_minutes=60,
                )
            )
            answer = repository.add_answer(
                Answer(
                    id=None,
                    session_id=session.id or 0,
                    question_id=question.id or 0,
                    user_answer="Кандидат явно назвал tradeoffs, rollback и метрики.",
                    self_score=4,
                    ai_feedback="Feedback.",
                    answered_at=datetime(2026, 5, 26, 9, 10, 0),
                )
            )
            evaluation = EvaluationService(repository).evaluate_and_store_answer(
                answer,
                question,
                use_llm=False,
            )
            dimension_slug = evaluation.scores[0].dimension.slug
            original_score = evaluation.scores[0].score
            override_score = 5 if original_score != 5 else 4
            repository.close()

            override_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "evaluation-override",
                    "--evaluation",
                    str(evaluation.id),
                    "--dimension",
                    dimension_slug,
                    "--score",
                    str(override_score),
                    "--reason",
                    "AI недооценила конкретику ответа",
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )
            show_process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "evaluations",
                    "--answer",
                    str(answer.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(override_process.returncode, 0, override_process.stderr)
        self.assertIn(f"{dimension_slug} {override_score}/5", override_process.stdout)
        self.assertIn(f"original {original_score}/5", override_process.stdout)
        self.assertEqual(show_process.returncode, 0, show_process.stderr)
        self.assertIn("manual override", show_process.stdout)
        self.assertIn(f"original {original_score}/5", show_process.stdout)
        self.assertIn("Override reason: AI недооценила конкретику ответа", show_process.stdout)

    def test_session_summary_command_shows_saved_session_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "session_summary.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.list_topics()[0]
            session = repository.create_session(
                Session(
                    id=None,
                    topic_id=topic.id,
                    started_at=datetime(2026, 5, 20, 9, 0, 0),
                    ended_at=None,
                    target_minutes=60,
                )
            )
            repository.finish_session(session.id or 0, datetime(2026, 5, 20, 9, 45, 0))
            outcome = repository.upsert_session_outcome(
                SessionOutcome(
                    id=None,
                    session_id=session.id or 0,
                    summary="Сильный разбор очередей, но не хватило failure-mode деталей.",
                    strengths=["Связал retries с идемпотентностью."],
                    gaps=["Не описал DLQ и observability."],
                    next_drills=["Повторить retry boundaries."],
                    readiness_delta=0.12,
                    created_at=datetime(2026, 5, 20, 9, 46, 0),
                )
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "session-summary",
                    str(session.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(f"Session outcome #{outcome.id} для session #{session.id}", process.stdout)
        self.assertIn("Readiness delta: +0.12", process.stdout)
        self.assertIn("Summary: Сильный разбор очередей", process.stdout)
        self.assertIn("Strengths:", process.stdout)
        self.assertIn("- Связал retries с идемпотентностью.", process.stdout)
        self.assertIn("Gaps:", process.stdout)
        self.assertIn("- Не описал DLQ и observability.", process.stdout)
        self.assertIn("Next drills:", process.stdout)

    def test_interview_report_command_exports_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "interview_report.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.list_topics()[0]
            question = repository.list_questions(topic.id)[0]
            session = repository.create_session(
                Session(
                    id=None,
                    topic_id=topic.id,
                    started_at=datetime(2026, 5, 21, 9, 0, 0),
                    ended_at=None,
                    target_minutes=60,
                )
            )
            repository.add_answer(
                Answer(
                    id=None,
                    session_id=session.id or 0,
                    question_id=question.id or 0,
                    user_answer="Я описал retries, идемпотентность и базовый мониторинг.",
                    self_score=4,
                    ai_feedback="Хорошо: есть retries. Упущено: DLQ и SLO.",
                    answered_at=datetime(2026, 5, 21, 9, 10, 0),
                )
            )
            repository.finish_session(session.id or 0, datetime(2026, 5, 21, 9, 45, 0))
            repository.upsert_session_outcome(
                SessionOutcome(
                    id=None,
                    session_id=session.id or 0,
                    summary="Сильная практика перед интервью.",
                    strengths=["Связал retries с идемпотентностью."],
                    gaps=["Не хватило observability evidence."],
                    next_drills=["Повторить DLQ и retry boundaries."],
                    readiness_delta=0.1,
                    created_at=datetime(2026, 5, 21, 9, 46, 0),
                )
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "interview-report",
                    "--session",
                    str(session.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn("# Interview Report", process.stdout)
        self.assertIn("## Strengths", process.stdout)
        self.assertIn("- Связал retries с идемпотентностью.", process.stdout)
        self.assertIn("## Gaps", process.stdout)
        self.assertIn("- Не хватило observability evidence.", process.stdout)
        self.assertIn("## Evidence Answers", process.stdout)
        self.assertIn(f"### Answer #1", process.stdout)
        self.assertIn("Candidate evidence: Я описал retries", process.stdout)
        self.assertIn("## Next Plan", process.stdout)
        self.assertIn("- Повторить DLQ и retry boundaries.", process.stdout)

    def test_system_design_history_command_shows_feedback_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "system_design_history.db"
            connection = connect(db_path)
            init_db(connection)
            repository = SQLiteRepository(connection)
            repository.seed_defaults()
            topic = repository.find_topic_by_slug("system-design")
            self.assertIsNotNone(topic)
            assert topic is not None
            scenario = repository.add_system_design_scenario(
                SystemDesignScenario(
                    id=None,
                    topic_id=topic.id or 0,
                    title="Notification service mock",
                    scenario="Спроектируй сервис уведомлений с retries и abuse protection.",
                    focus_areas=["capacity", "retries", "observability"],
                    source="test",
                    created_at=datetime(2026, 5, 21, 9, 0, 0),
                )
            )
            service = SystemDesignService(repository, FallbackLLMClient())
            service.save_transcript_turn(
                topic.id or 0,
                "Нужно отправлять email и push через очередь, retry делать идемпотентно.",
                "Какие SLO и лимиты по throughput ты заложишь?",
                scenario_id=scenario.id,
            )
            service.add_artifact(
                topic.id or 0,
                "requirements",
                "SLO: 99.9%, p95 enqueue latency < 100 ms.",
                scenario_id=scenario.id,
            )
            service.add_artifact(
                topic.id or 0,
                "api",
                "POST /notifications с idempotency_key.",
                scenario_id=scenario.id,
            )
            service.add_artifact(
                topic.id or 0,
                "risks",
                "Provider outage: retry with backoff, DLQ and alerts.",
                scenario_id=scenario.id,
            )
            feedback = service.save_final_feedback(
                topic.id or 0,
                "Сильный фокус на retries, но нужно подробнее раскрыть data model.",
                scenario_id=scenario.id,
                source="test",
            )
            repository.close()

            process = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "interview_prep",
                    "--db",
                    str(db_path),
                    "system-design-history",
                    "--feedback",
                    str(feedback.id),
                ],
                text=True,
                capture_output=True,
                timeout=5,
                check=False,
            )

        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(f"System design feedback #{feedback.id}", process.stdout)
        self.assertIn("Scenario: #", process.stdout)
        self.assertIn("Notification service mock", process.stdout)
        self.assertIn("Scenario text:", process.stdout)
        self.assertIn("Transcript:", process.stdout)
        self.assertIn("Кандидат: Нужно отправлять email", process.stdout)
        self.assertIn("Интервьюер: Какие SLO", process.stdout)
        self.assertIn("Artifacts:", process.stdout)
        self.assertIn("requirements:", process.stdout)
        self.assertIn("POST /notifications", process.stdout)
        self.assertIn("Final feedback:", process.stdout)
        self.assertIn("Сильный фокус на retries", process.stdout)
        self.assertIn("System design rubric", process.stdout)
        self.assertIn("Average score:", process.stdout)


class FailingLLM(LLMClient):
    def generate(self, prompt: str) -> str:
        raise LLMUnavailable("test timeout")


class LLMFallbackTests(unittest.TestCase):
    def test_resilient_llm_uses_fallback_when_primary_is_unavailable(self) -> None:
        client = ResilientLLMClient(FailingLLM(), FallbackLLMClient())

        response = client.generate("feedback please")

        self.assertIn("Ollama недоступна", response)
        self.assertEqual(client.last_error, "test timeout")


if __name__ == "__main__":
    unittest.main()
