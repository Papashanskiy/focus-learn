from __future__ import annotations

import json
import os
import sqlite3
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta

from interview_prep.domain.models import (
    Answer,
    AnswerEvaluationScore,
    Competency,
    CurriculumObjective,
    CurriculumSubtopic,
    CurriculumTopic,
    LearningDialogMessage,
    LearningMaterial,
    ManualNote,
    NotebookEntry,
    Question,
    QuestionCompetencyLink,
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_ARCHIVED,
    QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
    QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
    RubricDimension,
    SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
    SESSION_OUTCOME_TYPE_PRACTICE,
    SESSION_STATUS_ABANDONED,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_IN_PROGRESS,
    Session,
    SessionOutcome,
    SystemDesignArtifact,
    SystemDesignEvaluation,
    SystemDesignFeedbackArtifact,
    SystemDesignScenario,
    SystemDesignTranscriptMessage,
    Tag,
)
from interview_prep.infra.database import CURRENT_SCHEMA_VERSION, MIGRATION_STEPS, init_db
from interview_prep.infra.seed import (
    BOOTSTRAP_QUESTIONS,
    RUBRIC_DIMENSIONS,
    SENIOR_COMPETENCIES,
    SYSTEM_DESIGN_RUBRIC_DIMENSIONS,
)
from interview_prep.infra.llm import FallbackLLMClient, LLMUnavailable, OllamaClient
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.calibration_service import CalibrationService
from interview_prep.services.content_generation_service import (
    ContentGenerationService,
    JOB_KIND_CURRICULUM,
    build_background_question_prompt,
)
from interview_prep.services.curriculum_service import CurriculumService, parse_curriculum
from interview_prep.services.evaluation_service import EvaluationService, build_rubric_evaluation_prompt
from interview_prep.services.learning_service import LearningService, build_learning_prompt
from interview_prep.services.question_auto_curation_service import (
    AUTO_CURATION_DECISION_AUTO_ACCEPTED,
    AUTO_CURATION_DECISION_AUTO_ARCHIVED,
    AUTO_CURATION_DECISION_QUARANTINED,
    AUTO_CURATION_FLAG_GENERIC,
    AUTO_CURATION_FLAG_INCOMPLETE_SOURCE_METADATA,
    AUTO_CURATION_FLAG_LLM_CURATOR,
    AUTO_CURATION_FLAG_LLM_PARSE_FALLBACK,
    QuestionAutoCurationService,
)
from interview_prep.services.question_service import QuestionService
from interview_prep.services.question_source_service import (
    QuestionSourceService,
    SOURCE_BACKED_CANDIDATE_TEMPLATES,
    WHITELISTED_QUESTION_SOURCES,
)
from interview_prep.services.read_facade import ReadOnlyApplicationFacade
from interview_prep.services.readiness_service import ReadinessService
from interview_prep.services.session_service import (
    FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG,
    SessionService,
    build_feedback_prompt,
    build_recheck_feedback_prompt,
)
from interview_prep.services.stats_service import StatsService
from interview_prep.services.system_design_service import (
    SystemDesignService,
    build_system_design_checkpoint_prompt,
    build_system_design_feedback_prompt,
    build_system_design_pressure_prompt,
    build_system_design_turn_prompt,
)


class StaticLLM(FallbackLLMClient):
    def generate(self, prompt: str) -> str:
        if "learning curriculum starter pack" in prompt:
            return """
            {
              "topics": [
                {
                  "slug": "generated-observability",
                  "title": "Observability для Python backend",
                  "description": "Метрики, логи, traces, SLO и incident response.",
                  "level": "senior",
                  "objectives": ["Строить telemetry plan", "Разбирать production incidents"],
                  "subtopics": [
                    {
                      "slug": "metrics-and-traces",
                      "title": "Метрики и traces",
                      "description": "SLO, RED/USE metrics, traces и correlation ids.",
                      "objectives": ["Выбирать symptoms metrics", "Связывать traces с user impact"]
                    }
                  ],
                  "questions": [
                    {
                      "difficulty": "senior",
                      "prompt": "Как спроектировать observability для async worker service?",
                      "hint": "Покрой metrics, logs, traces, queue lag, saturation и alerting.",
                      "reference_answer": "Нужно измерять latency, throughput, errors, queue lag, retry counts, saturation, provider status codes, добавлять correlation ids, traces и alerts по symptoms."
                    }
                  ],
                  "mock_scenarios": ["Разобрать incident с ростом queue lag."]
                }
              ]
            }
            """
        if "Regenerate the reference answer" in prompt:
            return (
                "Обновленный эталон: объясни механизм, production tradeoffs, failure modes, "
                "observability и regression coverage."
            )
        if "Return JSON only" in prompt:
            if "system design mock interview scenario" in prompt:
                return """
                {
                    "scenario": "Спроектируй сервис real-time notifications с preferences, очередью и provider fallback.",
                    "focus_areas": ["requirements", "API", "queue", "observability", "failure modes"]
                }
                """
            return """
            {
                "difficulty": "senior",
                "prompt": "Как расследовать async production incident?",
                "hint": "Упомяни observability, cancellation, backpressure и rollback.",
                "reference_answer": "Начни с impact и telemetry, изолируй зависимость, проверь cancellation и queue pressure, безопасно mitigage проблему и добавь regression coverage."
            }
            """
        if "compact Russian learning material" in prompt:
            return "Учебный материал: начни с механизма, затем добавь tradeoffs и failure modes."
        return "Хорошо: есть структура. Упущено: добавь failure modes. Повторить: asyncio cancellation."


class BrokenLLM(FallbackLLMClient):
    def generate(self, prompt: str) -> str:
        raise RuntimeError("test generation failed")


class UnavailableLLM(FallbackLLMClient):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        raise LLMUnavailable("test timeout")


class RecordingLLM(FallbackLLMClient):
    def __init__(self, response: str):
        self.response = response
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


@dataclass(frozen=True)
class WeakFeedbackEvalCase:
    name: str
    question: str
    weak_answer: str
    reference_answer: str
    reference_only_claims: tuple[str, ...]


WEAK_FEEDBACK_EVAL_CASES = (
    WeakFeedbackEvalCase(
        name="short-gil-answer",
        question="Как GIL влияет на Python backend с CPU-bound и IO-bound задачами?",
        weak_answer="Наверное, надо использовать async, потому что так быстрее.",
        reference_answer=(
            "Сильный ответ объясняет, что GIL ограничивает параллельное выполнение Python bytecode "
            "в потоках, но IO-bound код может выигрывать от concurrency. Для CPU-bound нужны "
            "multiprocessing, C extensions, отдельные workers и проверка через profiling."
        ),
        reference_only_claims=(
            "GIL ограничивает параллельное выполнение Python bytecode",
            "multiprocessing",
            "profiling",
        ),
    ),
    WeakFeedbackEvalCase(
        name="vague-index-answer",
        question="Как выбрать индекс для production PostgreSQL таблицы?",
        weak_answer="Индекс ускоряет запросы, я бы добавил индекс на нужное поле.",
        reference_answer=(
            "Сильный ответ связывает индекс с query plan, cardinality и selectivity, называет "
            "стоимость записи и storage overhead, проверяет EXPLAIN ANALYZE и планирует safe migration."
        ),
        reference_only_claims=(
            "query plan",
            "стоимость записи",
            "safe migration",
        ),
    ),
    WeakFeedbackEvalCase(
        name="retry-only-distributed-answer",
        question="Как сделать retries безопасными в распределенном сервисе?",
        weak_answer="Нужно добавить retries, чтобы запрос повторился при ошибке.",
        reference_answer=(
            "Сильный ответ фиксирует idempotency key, exponential backoff с jitter, retry budget, "
            "DLQ для poison messages, observability и границы, где retry усиливает инцидент."
        ),
        reference_only_claims=(
            "idempotency key",
            "backoff с jitter",
            "DLQ",
        ),
    ),
)


def make_repository() -> SQLiteRepository:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    init_db(connection)
    repository = SQLiteRepository(connection)
    repository.seed_defaults()
    return repository


class ServiceTests(unittest.TestCase):
    def test_init_db_creates_schema_version_table_with_current_version(self) -> None:
        connection = sqlite3.connect(":memory:")

        init_db(connection)
        init_db(connection)

        columns = {row[1] for row in connection.execute("PRAGMA table_info(schema_version)")}
        rows = connection.execute("SELECT id, version, applied_at FROM schema_version").fetchall()
        self.assertEqual({"id", "version", "applied_at"}, columns)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 1)
        self.assertEqual(rows[0][1], CURRENT_SCHEMA_VERSION)
        self.assertIsNotNone(rows[0][2])

    def test_init_db_runs_explicit_idempotent_migration_steps(self) -> None:
        migration_names = [migration.name for migration in MIGRATION_STEPS]
        self.assertEqual(len(migration_names), len(set(migration_names)))
        self.assertTrue(all(migration.name and migration.sql.strip() for migration in MIGRATION_STEPS))
        self.assertTrue(all("IF NOT EXISTS" in migration.sql for migration in MIGRATION_STEPS))

        connection = sqlite3.connect(":memory:")
        init_db(connection)
        init_db(connection)

        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        expected_tables = {
            "schema_version",
            "topics",
            "questions",
            "competencies",
            "question_competencies",
            "rubric_dimensions",
            "answer_evaluations",
            "answer_evaluation_scores",
            "session_outcomes",
            "tags",
            "question_tags",
            "curriculum_topics",
            "curriculum_subtopics",
            "curriculum_objectives",
            "sessions",
            "answers",
            "content_generation_jobs",
            "learning_materials",
            "learning_dialog_messages",
            "notebook_entries",
            "manual_notes",
            "system_design_scenarios",
            "system_design_transcript_messages",
            "system_design_artifacts",
            "system_design_feedback_artifacts",
            "system_design_rubric_dimensions",
            "system_design_evaluations",
            "system_design_evaluation_scores",
            "question_source_snapshots",
        }
        self.assertTrue(expected_tables.issubset(tables))

    def test_init_db_upgrades_legacy_practice_database_to_current_schema(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                level TEXT NOT NULL
            );

            CREATE TABLE questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                difficulty TEXT NOT NULL,
                prompt TEXT NOT NULL,
                hint TEXT NOT NULL,
                reference_answer TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'seed',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                target_minutes INTEGER NOT NULL
            );

            CREATE TABLE answers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                question_id INTEGER NOT NULL REFERENCES questions(id) ON DELETE CASCADE,
                user_answer TEXT NOT NULL,
                self_score INTEGER,
                ai_feedback TEXT,
                answered_at TEXT NOT NULL
            );

            INSERT INTO topics (id, slug, title, description, level)
            VALUES (1, 'legacy-python', 'Legacy Python', 'Old practice topic.', 'middle+');
            INSERT INTO questions
                (id, topic_id, difficulty, prompt, hint, reference_answer, source, created_at)
            VALUES
                (1, 1, 'middle+', 'Legacy question?', 'Legacy hint.', 'Legacy reference.', 'seed',
                 '2026-05-01T09:00:00');
            INSERT INTO sessions (id, topic_id, started_at, ended_at, target_minutes)
            VALUES (1, 1, '2026-05-01T09:00:00', '2026-05-01T10:00:00', 60);
            INSERT INTO answers
                (id, session_id, question_id, user_answer, self_score, ai_feedback, answered_at)
            VALUES
                (1, 1, 1, 'Legacy answer.', 4, 'Legacy feedback.', '2026-05-01T09:10:00');
            """
        )

        init_db(connection)
        init_db(connection)

        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        self.assertTrue(
            {
                "schema_version",
                "competencies",
                "question_competencies",
                "rubric_dimensions",
                "answer_evaluations",
                "answer_evaluation_scores",
                "session_outcomes",
                "tags",
                "question_tags",
                "curriculum_topics",
                "content_generation_jobs",
                "learning_materials",
                "notebook_entries",
                "manual_notes",
                "system_design_scenarios",
                "system_design_artifacts",
                "system_design_feedback_artifacts",
                "system_design_rubric_dimensions",
                "system_design_evaluations",
                "system_design_evaluation_scores",
                "question_source_snapshots",
            }.issubset(tables)
        )
        version = connection.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()
        self.assertEqual(version["version"], CURRENT_SCHEMA_VERSION)
        session_columns = {row["name"] for row in connection.execute("PRAGMA table_info(sessions)")}
        self.assertIn("status", session_columns)
        question_columns = {row["name"] for row in connection.execute("PRAGMA table_info(questions)")}
        self.assertIn("source_quality_status", question_columns)

        repository = SQLiteRepository(connection)
        topic = repository.find_topic_by_slug("legacy-python")
        self.assertIsNotNone(topic)
        questions = repository.list_questions(topic.id if topic else None)
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0].prompt, "Legacy question?")
        self.assertEqual(questions[0].source, "seed")
        self.assertEqual(questions[0].source_quality_status, QUESTION_SOURCE_QUALITY_ACCEPTED)
        completed_sessions = repository.list_completed_practice_sessions()
        self.assertEqual([session.id for session in completed_sessions], [1])
        self.assertEqual(completed_sessions[0].answer_count, 1)
        self.assertEqual(completed_sessions[0].avg_self_score, 4.0)
        legacy_session = repository.get_session(1)
        self.assertIsNotNone(legacy_session)
        self.assertEqual(legacy_session.status, SESSION_STATUS_COMPLETED)

        tag = repository.upsert_tag(Tag(id=None, slug="legacy", title="Legacy"))
        repository.add_question_tag(questions[0].id or 0, tag.id or 0)
        saved_tags = repository.list_question_tags(questions[0].id or 0)
        self.assertEqual([saved_tag.slug for saved_tag in saved_tags], ["legacy"])

    def test_init_db_creates_rubric_evaluation_storage(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row

        init_db(connection)

        dimension_columns = {row["name"] for row in connection.execute("PRAGMA table_info(rubric_dimensions)")}
        evaluation_columns = {row["name"] for row in connection.execute("PRAGMA table_info(answer_evaluations)")}
        score_columns = {row["name"] for row in connection.execute("PRAGMA table_info(answer_evaluation_scores)")}
        self.assertTrue(
            {
                "id",
                "slug",
                "title",
                "description",
                "order_index",
                "created_at",
            }.issubset(dimension_columns)
        )
        self.assertTrue(
            {
                "id",
                "answer_id",
                "session_id",
                "question_id",
                "summary",
                "next_drills_json",
                "source",
                "raw_payload_json",
                "created_at",
            }.issubset(evaluation_columns)
        )
        self.assertTrue(
            {
                "evaluation_id",
                "rubric_dimension_id",
                "score",
                "evidence",
                "gaps",
                "next_drill",
                "manual_override_score",
                "manual_override_reason",
                "manual_override_at",
            }.issubset(score_columns)
        )

        with connection:
            connection.execute(
                "INSERT INTO topics (id, slug, title, description, level) VALUES (1, 'rubric-topic', 'Rubric Topic', 'Storage test.', 'senior')"
            )
            connection.execute(
                """
                INSERT INTO questions (id, topic_id, difficulty, prompt, hint, reference_answer, source)
                VALUES (1, 1, 'senior', 'Explain tradeoffs.', 'Mention evidence.', 'Reference answer.', 'test')
                """
            )
            connection.execute(
                """
                INSERT INTO sessions (id, topic_id, started_at, ended_at, target_minutes)
                VALUES (1, 1, '2026-05-19T09:00:00', '2026-05-19T10:00:00', 60)
                """
            )
            connection.execute(
                """
                INSERT INTO answers
                    (id, session_id, question_id, user_answer, self_score, ai_feedback, answered_at)
                VALUES
                    (1, 1, 1, 'Candidate answer with explicit tradeoff.', 4, 'Feedback.', '2026-05-19T09:10:00')
                """
            )
            connection.execute(
                """
                INSERT INTO rubric_dimensions (id, slug, title, description, order_index)
                VALUES (1, 'tradeoffs', 'Tradeoffs', 'Explicit alternatives and costs.', 30)
                """
            )
            connection.execute(
                """
                INSERT INTO answer_evaluations
                    (id, answer_id, session_id, question_id, summary, next_drills_json, source, raw_payload_json)
                VALUES
                    (1, 1, 1, 1, 'Structured summary.', '["Compare alternatives"]', 'test', '{"score": 4}')
                """
            )
            connection.execute(
                """
                INSERT INTO answer_evaluation_scores
                    (evaluation_id, rubric_dimension_id, score, evidence, gaps, next_drill)
                VALUES
                    (1, 1, 4, 'Candidate mentioned a concrete tradeoff.', 'Needs failure mode.', 'Add retry/idempotency drill.')
                """
            )

        saved_score = connection.execute(
            """
            SELECT ae.answer_id, ae.session_id, ae.question_id, aes.score, aes.evidence
            FROM answer_evaluations ae
            JOIN answer_evaluation_scores aes ON aes.evaluation_id = ae.id
            WHERE ae.id = 1
            """
        ).fetchone()
        self.assertEqual(saved_score["answer_id"], 1)
        self.assertEqual(saved_score["session_id"], 1)
        self.assertEqual(saved_score["question_id"], 1)
        self.assertEqual(saved_score["score"], 4)
        self.assertIn("tradeoff", saved_score["evidence"])

        with self.assertRaises(sqlite3.IntegrityError):
            with connection:
                connection.execute(
                    """
                    INSERT INTO answer_evaluation_scores
                        (evaluation_id, rubric_dimension_id, score, evidence, gaps)
                    VALUES (1, 1, 6, 'Impossible score.', 'Invalid.')
                    """
                )

        with self.assertRaises(sqlite3.IntegrityError):
            with connection:
                connection.execute(
                    """
                    INSERT INTO answer_evaluations
                        (answer_id, session_id, question_id, summary, next_drills_json, source)
                    VALUES (999, 1, 1, 'Missing answer.', '[]', 'test')
                    """
                )

    def test_init_db_creates_session_outcome_storage(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row

        init_db(connection)

        columns = {row["name"] for row in connection.execute("PRAGMA table_info(session_outcomes)")}
        self.assertTrue(
            {
                "id",
                "session_id",
                "summary",
                "strengths_json",
                "gaps_json",
                "next_drills_json",
                "readiness_delta",
                "created_at",
                "outcome_type",
            }.issubset(columns)
        )

        with connection:
            connection.execute(
                """
                INSERT INTO topics (id, slug, title, description, level)
                VALUES (1, 'outcome-topic', 'Outcome Topic', 'Storage test.', 'senior')
                """
            )
            connection.execute(
                """
                INSERT INTO sessions (id, topic_id, started_at, ended_at, status, target_minutes)
                VALUES (1, 1, '2026-05-19T09:00:00', '2026-05-19T10:00:00', 'completed', 60)
                """
            )
            connection.execute(
                """
                INSERT INTO session_outcomes
                    (
                        id,
                        session_id,
                        summary,
                        strengths_json,
                        gaps_json,
                        next_drills_json,
                        readiness_delta,
                        created_at
                    )
                VALUES
                    (
                        1,
                        1,
                        'Session summary.',
                        '["Clear tradeoff"]',
                        '["Missing failure mode"]',
                        '["Retry/idempotency drill"]',
                        0.25,
                        '2026-05-19T10:01:00'
                    )
                """
            )

        row = connection.execute(
            """
            SELECT
                session_id,
                summary,
                strengths_json,
                gaps_json,
                next_drills_json,
                readiness_delta,
                outcome_type
            FROM session_outcomes
            WHERE id = 1
            """
        ).fetchone()
        self.assertEqual(row["session_id"], 1)
        self.assertEqual(row["outcome_type"], SESSION_OUTCOME_TYPE_PRACTICE)
        self.assertEqual(json.loads(row["strengths_json"]), ["Clear tradeoff"])
        self.assertEqual(json.loads(row["gaps_json"]), ["Missing failure mode"])
        self.assertEqual(json.loads(row["next_drills_json"]), ["Retry/idempotency drill"])
        self.assertEqual(row["readiness_delta"], 0.25)

        with self.assertRaises(sqlite3.IntegrityError):
            with connection:
                connection.execute(
                    """
                    INSERT INTO session_outcomes
                        (session_id, summary, strengths_json, gaps_json, next_drills_json, readiness_delta)
                    VALUES (999, 'Missing session.', '[]', '[]', '[]', 0.0)
                    """
                )

        with self.assertRaises(sqlite3.IntegrityError):
            with connection:
                connection.execute(
                    """
                    INSERT INTO session_outcomes
                        (session_id, summary, strengths_json, gaps_json, next_drills_json, readiness_delta)
                    VALUES (1, 'Duplicate session.', '[]', '[]', '[]', 0.0)
                    """
                )

    def test_init_db_creates_system_design_evaluation_storage(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row

        init_db(connection)

        evaluation_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(system_design_evaluations)")
        }
        score_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(system_design_evaluation_scores)")
        }
        self.assertTrue(
            {
                "id",
                "feedback_artifact_id",
                "topic_id",
                "scenario_id",
                "session_id",
                "summary",
                "next_drills_json",
                "source",
                "raw_payload_json",
                "created_at",
            }.issubset(evaluation_columns)
        )
        self.assertTrue(
            {
                "evaluation_id",
                "system_design_rubric_dimension_id",
                "score",
                "evidence",
                "gaps",
                "next_drill",
            }.issubset(score_columns)
        )

        with connection:
            connection.execute(
                """
                INSERT INTO topics (id, slug, title, description, level)
                VALUES (1, 'sd-eval-topic', 'System Design Eval', 'Storage test.', 'senior')
                """
            )
            connection.execute(
                """
                INSERT INTO sessions (id, topic_id, started_at, ended_at, status, target_minutes)
                VALUES (1, 1, '2026-05-21T09:00:00', NULL, 'in_progress', 60)
                """
            )
            connection.execute(
                """
                INSERT INTO system_design_scenarios
                    (id, topic_id, title, scenario, focus_areas_json, source, created_at)
                VALUES
                    (1, 1, 'Notifications', 'Design notifications.', '["requirements"]', 'test',
                     '2026-05-21T09:01:00')
                """
            )
            connection.execute(
                """
                INSERT INTO system_design_feedback_artifacts
                    (id, topic_id, scenario_id, session_id, content, source, created_at)
                VALUES
                    (1, 1, 1, 1, 'Final feedback.', 'test', '2026-05-21T09:20:00')
                """
            )
            connection.execute(
                """
                INSERT INTO system_design_rubric_dimensions
                    (id, slug, title, description, order_index)
                VALUES (1, 'requirements', 'Requirements', 'Scope and constraints.', 10)
                """
            )
            connection.execute(
                """
                INSERT INTO system_design_evaluations
                    (
                        id,
                        feedback_artifact_id,
                        topic_id,
                        scenario_id,
                        session_id,
                        summary,
                        next_drills_json,
                        source,
                        raw_payload_json,
                        created_at
                    )
                VALUES
                    (
                        1,
                        1,
                        1,
                        1,
                        1,
                        'Structured system design summary.',
                        '["Add NFRs"]',
                        'test',
                        '{"score": 3}',
                        '2026-05-21T09:21:00'
                    )
                """
            )
            connection.execute(
                """
                INSERT INTO system_design_evaluation_scores
                    (evaluation_id, system_design_rubric_dimension_id, score, evidence, gaps, next_drill)
                VALUES
                    (1, 1, 3, 'Candidate wrote SLA.', 'Add constraints.', 'Practice NFRs.')
                """
            )

        row = connection.execute(
            """
            SELECT sde.feedback_artifact_id, sde.topic_id, sdes.score, sdes.evidence
            FROM system_design_evaluations sde
            JOIN system_design_evaluation_scores sdes ON sdes.evaluation_id = sde.id
            WHERE sde.id = 1
            """
        ).fetchone()
        self.assertEqual(row["feedback_artifact_id"], 1)
        self.assertEqual(row["topic_id"], 1)
        self.assertEqual(row["score"], 3)
        self.assertIn("SLA", row["evidence"])

        with self.assertRaises(sqlite3.IntegrityError):
            with connection:
                connection.execute(
                    """
                    INSERT INTO system_design_evaluation_scores
                        (evaluation_id, system_design_rubric_dimension_id, score, evidence, gaps)
                    VALUES (1, 1, 6, 'Impossible score.', 'Invalid.')
                    """
                )

        with self.assertRaises(sqlite3.IntegrityError):
            with connection:
                connection.execute(
                    """
                    INSERT INTO system_design_evaluations
                        (feedback_artifact_id, topic_id, summary, next_drills_json, source)
                    VALUES (999, 1, 'Missing feedback.', '[]', 'test')
                    """
                )

    def test_init_db_adds_learning_material_archive_column_to_existing_database(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE learning_materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        init_db(connection)

        columns = {row[1] for row in connection.execute("PRAGMA table_info(learning_materials)")}
        self.assertIn("archived_at", columns)
        self.assertIn("archive_reason", columns)

    def test_init_db_adds_learning_dialog_metadata_columns_to_existing_database(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE learning_dialog_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        init_db(connection)

        columns = {row[1] for row in connection.execute("PRAGMA table_info(learning_dialog_messages)")}
        self.assertIn("dialog_session_id", columns)
        self.assertIn("context_type", columns)
        self.assertIn("context_id", columns)

    def test_init_db_creates_notebook_entries_storage(self) -> None:
        connection = sqlite3.connect(":memory:")

        init_db(connection)

        columns = {row[1] for row in connection.execute("PRAGMA table_info(notebook_entries)")}
        self.assertIn("topic_id", columns)
        self.assertIn("curriculum_subtopic_id", columns)
        self.assertIn("dialog_session_id", columns)
        self.assertIn("source_message_id", columns)
        self.assertIn("body", columns)

    def test_init_db_creates_manual_notes_storage(self) -> None:
        connection = sqlite3.connect(":memory:")

        init_db(connection)

        columns = {row[1] for row in connection.execute("PRAGMA table_info(manual_notes)")}
        self.assertIn("topic_id", columns)
        self.assertIn("session_id", columns)
        self.assertIn("context_type", columns)
        self.assertIn("context_id", columns)
        self.assertIn("title", columns)
        self.assertIn("body", columns)
        self.assertIn("updated_at", columns)

    def test_init_db_adds_system_design_scenario_archive_column_to_existing_database(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.execute(
            """
            CREATE TABLE system_design_scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                scenario TEXT NOT NULL,
                focus_areas_json TEXT NOT NULL,
                source TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        init_db(connection)

        columns = {row[1] for row in connection.execute("PRAGMA table_info(system_design_scenarios)")}
        self.assertIn("archived_at", columns)
        self.assertIn("archive_reason", columns)

    def test_seed_defaults_adds_minimal_bootstrap_topics_and_questions(self) -> None:
        repository = make_repository()

        self.assertEqual(len(repository.list_topics()), 5)
        self.assertEqual(len(repository.list_questions()), 5)
        self.assertTrue(all(question.source == "bootstrap" for question in repository.list_questions()))
        self.assertTrue(
            all(
                question.source_quality_status == QUESTION_SOURCE_QUALITY_ACCEPTED
                for question in repository.list_questions()
            )
        )

    def test_repository_tracks_question_source_quality_status(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("async-backend")
        self.assertIsNotNone(topic)

        saved = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Как проверить качество сгенерированного вопроса?",
                hint="Смотри на уникальность, практичность и senior coverage.",
                reference_answer="Нужны критерии review, дублей, coverage и archive path.",
                source="background-llm",
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
            )
        )
        pending = repository.list_questions(
            topic.id,
            source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
        )
        archived = repository.update_question_source_quality_status(
            saved.id or 0,
            QUESTION_SOURCE_QUALITY_ARCHIVED,
        )

        self.assertEqual([question.id for question in pending], [saved.id])
        self.assertEqual(archived.source_quality_status, QUESTION_SOURCE_QUALITY_ARCHIVED)
        self.assertEqual(repository.get_question(saved.id or 0).source_quality_status, QUESTION_SOURCE_QUALITY_ARCHIVED)

    def test_practice_selection_skips_archived_questions(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("async-backend")
        self.assertIsNotNone(topic)
        assert topic is not None

        archived = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="middle",
                prompt="Archived generated question should not appear in practice.",
                hint="Archived rows stay in SQLite but are not practice candidates.",
                reference_answer="Practice selection only uses accepted questions.",
                source="background-llm",
                source_quality_status=QUESTION_SOURCE_QUALITY_ARCHIVED,
            )
        )
        pending = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="middle",
                prompt="Pending generated question should not appear in practice.",
                hint="Pending rows need review before practice.",
                reference_answer="Practice selection only uses accepted questions.",
                source="llm-seed",
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
            )
        )
        accepted = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Accepted generated question should remain a practice candidate.",
                hint="Accepted rows are eligible for practice.",
                reference_answer="Accepted questions remain selectable.",
                source="background-llm",
                source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
            )
        )

        sessions = SessionService(repository, StaticLLM())
        session = sessions.start_session(topic_id=topic.id)
        candidate_ids = [question.id for question in sessions.candidate_questions(session.id or 0)]

        self.assertIn(accepted.id, candidate_ids)
        self.assertNotIn(archived.id, candidate_ids)
        self.assertNotIn(pending.id, candidate_ids)
        self.assertTrue(
            all(
                question.source_quality_status == QUESTION_SOURCE_QUALITY_ACCEPTED
                for question in sessions.candidate_questions(session.id or 0)
            )
        )

    def test_question_source_refresh_persists_metadata_without_creating_questions(self) -> None:
        repository = make_repository()
        before_question_count = len(repository.list_questions())
        service = QuestionSourceService(repository)

        result = service.refresh(now=datetime(2026, 5, 27, 9, 0, 0))
        repeat_result = service.refresh(now=datetime(2026, 5, 28, 9, 0, 0))
        snapshots = repository.list_question_source_snapshots()

        self.assertFalse(result.dry_run)
        self.assertEqual(result.saved_count, len(WHITELISTED_QUESTION_SOURCES))
        self.assertEqual(repeat_result.saved_count, len(WHITELISTED_QUESTION_SOURCES))
        self.assertEqual(len(snapshots), len(WHITELISTED_QUESTION_SOURCES))
        self.assertEqual(len(repository.list_questions()), before_question_count)
        self.assertEqual(snapshots[0].source_id, "S01")
        self.assertEqual(snapshots[0].title, "Python data model")
        self.assertEqual(snapshots[0].retrieved_at, datetime(2026, 5, 28, 9, 0, 0))
        self.assertIn("python-core", snapshots[0].category_hints)
        self.assertEqual(len(snapshots[0].checksum), 64)

    def test_question_source_candidates_create_pending_auto_review_questions_with_metadata(self) -> None:
        repository = make_repository()
        service = QuestionSourceService(repository)
        service.refresh(now=datetime(2026, 5, 27, 9, 0, 0))

        result = service.create_source_backed_candidates()
        repeat_result = service.create_source_backed_candidates()
        candidates = repository.list_questions(source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW)
        sessions = SessionService(repository, StaticLLM())
        session = sessions.start_session(topic_id=None)
        practice_question_ids = {question.id for question in sessions.candidate_questions(session.id or 0)}

        self.assertEqual(result.created_count, len(SOURCE_BACKED_CANDIDATE_TEMPLATES))
        self.assertEqual(result.skipped_count, 0)
        self.assertEqual(repeat_result.created_count, 0)
        self.assertEqual(repeat_result.skipped_count, len(SOURCE_BACKED_CANDIDATE_TEMPLATES))
        self.assertEqual(len(candidates), len(SOURCE_BACKED_CANDIDATE_TEMPLATES))
        first = next(
            question
            for question in candidates
            if question.source_url == "https://docs.python.org/3/reference/datamodel.html"
        )
        self.assertEqual(first.source, "source-backed")
        self.assertEqual(first.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW)
        self.assertEqual(first.source_url, "https://docs.python.org/3/reference/datamodel.html")
        self.assertEqual(first.source_retrieved_at, datetime(2026, 5, 27, 9, 0, 0))
        self.assertIn("python-core", first.source_category_hints)
        self.assertEqual(first.source_frequency_hint, "official-docs:common-python-core")
        self.assertNotIn(first.id, practice_question_ids)

    def test_question_auto_curation_preview_classifies_source_backed_candidates_without_mutation(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("async-backend")
        self.assertIsNotNone(topic)
        assert topic is not None
        retrieved_at = datetime(2026, 5, 27, 9, 0, 0)
        accepted_duplicate_base = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Как защитить webhook worker от двойной обработки, если retry приходит после timeout?",
                hint="Accepted base для duplicate gate.",
                reference_answer="Нужны idempotency key, bounded retry и observability.",
                source="canonical-2026",
                source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
            )
        )
        good = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt=(
                    "Async worker получает burst webhooks и downstream API отвечает timeout. "
                    "Как ты задашь bounded concurrency, idempotency и queue lag alerts?"
                ),
                hint="High-confidence source-backed candidate.",
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
                hint="Generic candidate.",
                reference_answer="Should be auto-archived by dry-run decision only.",
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
                hint="Missing source evidence should quarantine.",
                reference_answer="Needs source evidence before automatic acceptance.",
                source="source-backed",
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
            )
        )
        duplicate = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt=accepted_duplicate_base.prompt,
                hint="Duplicate candidate.",
                reference_answer="Should be auto-archived by dry-run decision only.",
                source="source-backed",
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                source_url="https://example.test/source",
                source_retrieved_at=retrieved_at,
                source_category_hints=("async",),
                source_frequency_hint="interview-coverage:duplicate",
            )
        )
        service = QuestionAutoCurationService(repository)

        result = service.preview_pending_source_backed_candidates(topic_id=topic.id)
        decisions_by_id = {decision.question.id: decision for decision in result.decisions}

        self.assertTrue(result.dry_run)
        self.assertEqual(decisions_by_id[good.id].decision, AUTO_CURATION_DECISION_AUTO_ACCEPTED)
        self.assertEqual(decisions_by_id[generic.id].decision, AUTO_CURATION_DECISION_AUTO_ARCHIVED)
        self.assertIn(AUTO_CURATION_FLAG_GENERIC, decisions_by_id[generic.id].quality_flags)
        self.assertEqual(decisions_by_id[missing_metadata.id].decision, AUTO_CURATION_DECISION_QUARANTINED)
        self.assertIn(
            AUTO_CURATION_FLAG_INCOMPLETE_SOURCE_METADATA,
            decisions_by_id[missing_metadata.id].quality_flags,
        )
        self.assertEqual(decisions_by_id[duplicate.id].decision, AUTO_CURATION_DECISION_AUTO_ARCHIVED)
        self.assertEqual(decisions_by_id[duplicate.id].duplicate_of_id, accepted_duplicate_base.id)
        self.assertEqual(
            repository.get_question(good.id or 0).source_quality_status,
            QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
        )
        self.assertEqual(
            repository.get_question(generic.id or 0).source_quality_status,
            QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
        )

    def test_question_auto_curation_apply_updates_deterministic_statuses_and_leaves_quarantine(self) -> None:
        repository = make_repository()
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
                hint="High-confidence source-backed candidate.",
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
                hint="Generic candidate.",
                reference_answer="Should be auto-archived by deterministic apply.",
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
                hint="Missing source evidence should quarantine.",
                reference_answer="Needs source evidence before automatic acceptance.",
                source="source-backed",
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
            )
        )
        service = QuestionAutoCurationService(repository)

        result = service.apply_pending_source_backed_candidates(topic_id=topic.id)

        self.assertFalse(result.dry_run)
        self.assertEqual(result.applied_count, 2)
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(result.archived_count, 1)
        self.assertEqual(result.quarantined_count, 1)
        self.assertEqual(
            repository.get_question(good.id or 0).source_quality_status,
            QUESTION_SOURCE_QUALITY_ACCEPTED,
        )
        self.assertEqual(
            repository.get_question(generic.id or 0).source_quality_status,
            QUESTION_SOURCE_QUALITY_ARCHIVED,
        )
        self.assertEqual(
            repository.get_question(missing_metadata.id or 0).source_quality_status,
            QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
        )

    def test_question_auto_curation_llm_curator_accepts_ambiguous_candidate_before_apply(self) -> None:
        class AcceptingCuratorLLM(FallbackLLMClient):
            def generate(self, prompt: str) -> str:
                self.last_prompt = prompt
                return json.dumps(
                    {
                        "decision": "auto_accepted",
                        "confidence": 0.91,
                        "score": 4,
                        "rationale": "Concrete worker retry and idempotency signal is interview-useful.",
                        "source_evidence": "asyncio docs snapshot and common-async-production frequency hint",
                        "quality_flags": ["specific_scenario"],
                    }
                )

        repository = make_repository()
        topic = repository.find_topic_by_slug("async-backend")
        self.assertIsNotNone(topic)
        assert topic is not None
        retrieved_at = datetime(2026, 5, 27, 9, 0, 0)
        ambiguous = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Как защитить asyncio worker retries и idempotency?",
                hint="Short prompt needs curator review before automatic acceptance.",
                reference_answer="Нужны idempotency key, bounded retries, DLQ и queue lag alerts.",
                source="source-backed",
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                source_url="https://docs.python.org/3/library/asyncio-queue.html",
                source_retrieved_at=retrieved_at,
                source_category_hints=("async", "queues"),
                source_frequency_hint="official-docs:common-async-production",
            )
        )
        llm = AcceptingCuratorLLM()
        service = QuestionAutoCurationService(repository, llm)

        deterministic = service.preview_pending_source_backed_candidates(topic_id=topic.id)
        deterministic_by_id = {decision.question.id: decision for decision in deterministic.decisions}
        result = service.apply_pending_source_backed_candidates(topic_id=topic.id, use_llm_curator=True)
        decisions_by_id = {decision.question.id: decision for decision in result.decisions}

        self.assertEqual(deterministic_by_id[ambiguous.id].decision, AUTO_CURATION_DECISION_QUARANTINED)
        self.assertIn("<source_backed_question_curator_json>", llm.last_prompt)
        self.assertFalse(result.dry_run)
        self.assertEqual(result.accepted_count, 1)
        self.assertEqual(decisions_by_id[ambiguous.id].decision, AUTO_CURATION_DECISION_AUTO_ACCEPTED)
        self.assertEqual(decisions_by_id[ambiguous.id].curator_score, 4)
        self.assertIn(AUTO_CURATION_FLAG_LLM_CURATOR, decisions_by_id[ambiguous.id].quality_flags)
        self.assertEqual(
            repository.get_question(ambiguous.id or 0).source_quality_status,
            QUESTION_SOURCE_QUALITY_ACCEPTED,
        )

    def test_question_auto_curation_llm_curator_parse_fallback_keeps_quarantine(self) -> None:
        class InvalidCuratorLLM(FallbackLLMClient):
            def generate(self, prompt: str) -> str:
                return "not json"

        repository = make_repository()
        topic = repository.find_topic_by_slug("async-backend")
        self.assertIsNotNone(topic)
        assert topic is not None
        retrieved_at = datetime(2026, 5, 27, 9, 0, 0)
        ambiguous = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Как проверить queue retry budget в asyncio worker?",
                hint="Short prompt needs safe fallback when curator output is invalid.",
                reference_answer="Нужны retry budget, idempotency, DLQ и observability.",
                source="source-backed",
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                source_url="https://docs.python.org/3/library/asyncio-queue.html",
                source_retrieved_at=retrieved_at,
                source_category_hints=("async", "queues"),
                source_frequency_hint="official-docs:common-async-production",
            )
        )
        service = QuestionAutoCurationService(repository, InvalidCuratorLLM())

        result = service.apply_pending_source_backed_candidates(topic_id=topic.id, use_llm_curator=True)
        decisions_by_id = {decision.question.id: decision for decision in result.decisions}

        self.assertEqual(result.accepted_count, 0)
        self.assertEqual(result.quarantined_count, 1)
        self.assertEqual(decisions_by_id[ambiguous.id].decision, AUTO_CURATION_DECISION_QUARANTINED)
        self.assertIn(AUTO_CURATION_FLAG_LLM_PARSE_FALLBACK, decisions_by_id[ambiguous.id].quality_flags)
        self.assertEqual(
            repository.get_question(ambiguous.id or 0).source_quality_status,
            QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
        )

    def test_seed_defaults_adds_idempotent_senior_competencies(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        init_db(connection)
        repository = SQLiteRepository(connection)

        repository.seed_defaults()
        repository.seed_defaults()

        rows = connection.execute(
            """
            SELECT slug, title, description, category, level, order_index
            FROM competencies
            ORDER BY order_index ASC
            """
        ).fetchall()

        self.assertEqual([row["slug"] for row in rows], [item.slug for item in SENIOR_COMPETENCIES])
        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0]["slug"], "python-runtime")
        self.assertEqual(rows[0]["category"], "language-runtime")
        self.assertEqual(rows[0]["level"], "senior")
        self.assertEqual(rows[-1]["slug"], "communication-tradeoffs")

    def test_seed_defaults_adds_idempotent_rubric_dimensions(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        init_db(connection)
        repository = SQLiteRepository(connection)

        repository.seed_defaults()
        repository.seed_defaults()

        rows = connection.execute(
            """
            SELECT slug, title, description, order_index
            FROM rubric_dimensions
            ORDER BY order_index ASC
            """
        ).fetchall()

        self.assertEqual([row["slug"] for row in rows], [item.slug for item in RUBRIC_DIMENSIONS])
        self.assertEqual(len(rows), 7)
        self.assertEqual(rows[0]["slug"], "correctness")
        self.assertEqual(rows[0]["title"], "Correctness")
        self.assertEqual(rows[-1]["slug"], "evidence")
        self.assertIn("observable candidate text", rows[-1]["description"])

    def test_seed_defaults_adds_idempotent_system_design_rubric_dimensions(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        init_db(connection)
        repository = SQLiteRepository(connection)

        repository.seed_defaults()
        repository.seed_defaults()

        rows = connection.execute(
            """
            SELECT slug, title, description, order_index
            FROM system_design_rubric_dimensions
            ORDER BY order_index ASC
            """
        ).fetchall()

        self.assertEqual(
            [row["slug"] for row in rows],
            [item.slug for item in SYSTEM_DESIGN_RUBRIC_DIMENSIONS],
        )
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0]["slug"], "requirements")
        self.assertEqual(rows[0]["title"], "Requirements")
        self.assertEqual(rows[-1]["slug"], "tradeoffs")
        self.assertIn("explicit reasoning", rows[-1]["description"])

    def test_seed_defaults_links_bootstrap_questions_to_senior_competencies(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        init_db(connection)
        repository = SQLiteRepository(connection)

        repository.seed_defaults()
        with connection:
            connection.execute("DELETE FROM question_competencies")
        repository.seed_defaults()
        repository.seed_defaults()

        expected_by_topic_slug = {question.topic_slug: question.competency_links for question in BOOTSTRAP_QUESTIONS}
        for question in repository.list_questions():
            topic = repository.get_topic(question.topic_id)
            self.assertIsNotNone(topic)
            self.assertIsNotNone(question.id)
            assert topic is not None
            expected_links = expected_by_topic_slug[topic.slug]
            links = repository.list_question_competencies(question.id or 0)

            actual = {link.competency.slug: (link.is_primary, link.weight) for link in links}
            expected = {link.slug: (link.is_primary, link.weight) for link in expected_links}
            self.assertEqual(actual, expected)
            self.assertEqual(sum(1 for link in links if link.is_primary), 1)

        link_count = connection.execute("SELECT COUNT(*) AS c FROM question_competencies").fetchone()["c"]
        self.assertEqual(link_count, sum(len(question.competency_links) for question in BOOTSTRAP_QUESTIONS))

    def test_init_db_creates_question_competency_link_storage(self) -> None:
        repository = make_repository()
        topic = repository.list_topics()[0]
        self.assertIsNotNone(topic.id)
        question = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Проверочный вопрос для явного теста связи с competency.",
                hint="Свяжи вопрос с несколькими competencies.",
                reference_answer="Ответ должен быть привязан к primary и secondary competencies.",
                source="test",
            )
        )
        python_runtime = repository.find_competency_by_slug("python-runtime")
        async_concurrency = repository.find_competency_by_slug("async-concurrency")
        self.assertIsNotNone(question.id)
        self.assertIsNotNone(python_runtime)
        self.assertIsNotNone(async_concurrency)

        with repository.connection:
            repository.connection.execute(
                """
                INSERT INTO question_competencies
                    (question_id, competency_id, is_primary, weight)
                VALUES (?, ?, 1, 0.75)
                """,
                (question.id, python_runtime.id if python_runtime else 0),
            )
            repository.connection.execute(
                """
                INSERT INTO question_competencies
                    (question_id, competency_id, weight)
                VALUES (?, ?, 0.25)
                """,
                (question.id, async_concurrency.id if async_concurrency else 0),
            )

        rows = repository.connection.execute(
            """
            SELECT competency_id, is_primary, weight
            FROM question_competencies
            WHERE question_id = ?
            ORDER BY is_primary DESC, competency_id
            """,
            (question.id,),
        ).fetchall()

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["is_primary"], 1)
        self.assertAlmostEqual(rows[0]["weight"], 0.75)
        self.assertEqual(rows[1]["is_primary"], 0)
        self.assertAlmostEqual(rows[1]["weight"], 0.25)

        with self.assertRaises(sqlite3.IntegrityError):
            with repository.connection:
                repository.connection.execute(
                    """
                    UPDATE question_competencies
                    SET is_primary = 1
                    WHERE question_id = ? AND competency_id = ?
                    """,
                    (question.id, async_concurrency.id if async_concurrency else 0),
                )

    def test_repository_lists_gets_and_upserts_competencies(self) -> None:
        repository = make_repository()

        seeded = repository.list_competencies()
        first = seeded[0]
        saved = repository.upsert_competency(
            Competency(
                id=None,
                slug=first.slug,
                title="Python Runtime Updated",
                description="Updated runtime evidence contract.",
                category="language-runtime",
                level="senior",
                order_index=15,
            )
        )
        custom = repository.upsert_competency(
            Competency(
                id=None,
                slug="architecture-tradeoffs",
                title="Architecture Tradeoffs",
                description="Reason about explicit alternatives and costs.",
                category="architecture",
                level="senior",
                order_index=45,
            )
        )

        self.assertEqual(len(seeded), len(SENIOR_COMPETENCIES))
        self.assertEqual(first.slug, "python-runtime")
        self.assertEqual(saved.id, first.id)
        self.assertEqual(saved.title, "Python Runtime Updated")
        self.assertEqual(repository.get_competency(first.id or 0), saved)
        self.assertEqual(repository.find_competency_by_slug("architecture-tradeoffs"), custom)
        self.assertIsNone(repository.get_competency(9999))
        self.assertIsNone(repository.find_competency_by_slug("missing-competency"))
        self.assertEqual(
            [competency.slug for competency in repository.list_competencies()[:3]],
            ["python-runtime", "async-concurrency", "databases"],
        )

    def test_repository_lists_gets_and_upserts_rubric_dimensions(self) -> None:
        repository = make_repository()

        seeded = repository.list_rubric_dimensions()
        first = seeded[0]
        saved = repository.upsert_rubric_dimension(
            RubricDimension(
                id=None,
                slug=first.slug,
                title="Correctness Updated",
                description="Updated technical correctness contract.",
                order_index=15,
            )
        )
        custom = repository.upsert_rubric_dimension(
            RubricDimension(
                id=None,
                slug="security",
                title="Security",
                description="Authentication, authorization, data handling and abuse risks.",
                order_index=45,
            )
        )

        self.assertEqual(len(seeded), len(RUBRIC_DIMENSIONS))
        self.assertEqual(first.slug, "correctness")
        self.assertEqual(saved.id, first.id)
        self.assertEqual(saved.title, "Correctness Updated")
        self.assertEqual(repository.get_rubric_dimension(first.id or 0), saved)
        self.assertEqual(repository.find_rubric_dimension_by_slug("security"), custom)
        self.assertIsNone(repository.get_rubric_dimension(9999))
        self.assertIsNone(repository.find_rubric_dimension_by_slug("missing-dimension"))
        self.assertEqual(
            [dimension.slug for dimension in repository.list_rubric_dimensions()[:3]],
            ["correctness", "depth", "tradeoffs"],
        )

    def test_repository_lists_gets_and_upserts_system_design_rubric_dimensions(self) -> None:
        repository = make_repository()

        seeded = repository.list_system_design_rubric_dimensions()
        first = seeded[0]
        saved = repository.upsert_system_design_rubric_dimension(
            RubricDimension(
                id=None,
                slug=first.slug,
                title="Requirements Updated",
                description="Updated system design requirements contract.",
                order_index=25,
            )
        )
        custom = repository.upsert_system_design_rubric_dimension(
            RubricDimension(
                id=None,
                slug="security-abuse",
                title="Security and Abuse",
                description="Authentication, authorization, rate limits and abuse prevention.",
                order_index=75,
            )
        )

        self.assertEqual(len(seeded), len(SYSTEM_DESIGN_RUBRIC_DIMENSIONS))
        self.assertEqual(first.slug, "requirements")
        self.assertEqual(saved.id, first.id)
        self.assertEqual(saved.title, "Requirements Updated")
        self.assertEqual(repository.get_system_design_rubric_dimension(first.id or 0), saved)
        self.assertEqual(
            repository.find_system_design_rubric_dimension_by_slug("security-abuse"),
            custom,
        )
        self.assertIsNone(repository.get_system_design_rubric_dimension(9999))
        self.assertIsNone(repository.find_system_design_rubric_dimension_by_slug("missing-dimension"))
        self.assertEqual(
            [dimension.slug for dimension in repository.list_system_design_rubric_dimensions()[:3]],
            ["api", "requirements", "data-model"],
        )

    def test_evaluation_service_returns_structured_scores_for_all_rubric_dimensions(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        service = EvaluationService(repository)

        evaluation = service.evaluate_answer(
            question,
            user_answer=(
                "Сначала фиксирую production impact и observability: метрики, логи и alerts. "
                "Потом объясняю механизм и tradeoff: индекс ускоряет чтение, но замедляет запись "
                "и требует safe migration. Риск отказа закрываю rollback, retry/idempotency и "
                "regression test."
            ),
            reference_answer=question.reference_answer,
        )

        self.assertEqual(evaluation.question_id, question.id)
        self.assertEqual(evaluation.source, "heuristic")
        self.assertIsNone(evaluation.raw_payload_json)
        self.assertEqual(
            [score.dimension.slug for score in evaluation.scores],
            [dimension.slug for dimension in repository.list_rubric_dimensions()],
        )
        self.assertTrue(all(1 <= score.score <= 5 for score in evaluation.scores))
        scores_by_slug = {score.dimension.slug: score for score in evaluation.scores}
        self.assertGreaterEqual(scores_by_slug["tradeoffs"].score, 3)
        self.assertGreaterEqual(scores_by_slug["production-realism"].score, 3)
        self.assertGreaterEqual(scores_by_slug["failure-modes"].score, 3)
        self.assertIn("tradeoff", scores_by_slug["tradeoffs"].evidence)
        self.assertTrue(evaluation.summary)
        self.assertTrue(evaluation.next_drills)

    def test_evaluation_service_keeps_short_unknown_answer_low_and_evidence_bound(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        service = EvaluationService(repository)

        evaluation = service.evaluate_answer(
            question,
            user_answer="не знаю",
            reference_answer=question.reference_answer,
        )

        scores_by_slug = {score.dimension.slug: score for score in evaluation.scores}
        self.assertLessEqual(scores_by_slug["correctness"].score, 2)
        self.assertLessEqual(scores_by_slug["depth"].score, 2)
        self.assertLessEqual(scores_by_slug["evidence"].score, 2)
        self.assertIn("нет достаточного", scores_by_slug["correctness"].evidence)
        self.assertIn("слабый", evaluation.summary)
        self.assertTrue(evaluation.next_drills)

    def test_evaluation_service_manual_override_keeps_original_score_metadata(self) -> None:
        repository = make_repository()
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
                user_answer="Ответ содержит tradeoffs, rollback и observability.",
                self_score=3,
                ai_feedback=None,
                answered_at=datetime(2026, 5, 26, 9, 10, 0),
            )
        )
        service = EvaluationService(repository)
        evaluation = service.evaluate_and_store_answer(answer, question, use_llm=False)
        original = evaluation.scores[0]
        override_score = 5 if original.score != 5 else 4
        overridden_at = datetime(2026, 5, 26, 9, 30, 0)

        updated = service.override_score(
            evaluation.id or 0,
            dimension_slug=original.dimension.slug,
            score=override_score,
            reason="AI пропустила конкретный production evidence.",
            overridden_at=overridden_at,
        )

        updated_score = next(
            score for score in updated.scores if score.dimension.slug == original.dimension.slug
        )
        self.assertEqual(updated_score.score, original.score)
        self.assertEqual(updated_score.manual_override_score, override_score)
        self.assertEqual(updated_score.effective_score, override_score)
        self.assertEqual(
            updated_score.manual_override_reason,
            "AI пропустила конкретный production evidence.",
        )
        self.assertEqual(updated_score.manual_override_at, overridden_at)
        repository.close()

    def test_rubric_evaluation_prompt_requires_json_scores_and_evidence(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        dimensions = repository.list_rubric_dimensions()

        prompt = build_rubric_evaluation_prompt(
            question,
            "не знаю",
            question.reference_answer,
            dimensions,
        )

        self.assertIn("<rubric_answer_evaluation_json>", prompt)
        self.assertIn('"dimension_slug"', prompt)
        self.assertIn('"score": 1', prompt)
        self.assertIn("<candidate_answer>\nне знаю\n</candidate_answer>", prompt)
        self.assertIn("<reference_answer>", prompt)
        self.assertLess(prompt.index("<candidate_answer>"), prompt.index("<reference_answer>"))
        self.assertIn("evidence должно ссылаться только на наблюдаемый текст кандидата", prompt)
        self.assertIn("не засчитывай кандидату пункты", prompt)
        self.assertIn("correctness", prompt)
        self.assertIn("failure-modes", prompt)

    def test_evaluation_service_parses_valid_llm_json_rubric_response(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        dimensions = repository.list_rubric_dimensions()
        response = json.dumps(
            {
                "summary": "Ответ частично закрывает вопрос, но требует глубины.",
                "scores": [
                    {
                        "dimension_slug": dimension.slug,
                        "score": 2 if dimension.slug == "evidence" else 3,
                        "evidence": "Наблюдаемое evidence из ответа кандидата: упомянуты метрики и rollback.",
                        "gaps": f"Нужно подробнее раскрыть {dimension.slug}.",
                        "next_drill": f"Повтори {dimension.slug}.",
                    }
                    for dimension in dimensions
                ],
                "next_drills": ["Повтори evidence.", "Добавь tradeoffs."],
            },
            ensure_ascii=False,
        )
        llm = RecordingLLM(response)
        service = EvaluationService(repository, llm)

        evaluation = service.evaluate_answer_with_llm(
            question,
            user_answer="Нужно смотреть метрики и иметь rollback.",
            reference_answer=question.reference_answer,
        )

        self.assertEqual(evaluation.question_id, question.id)
        self.assertEqual(evaluation.source, "llm-json")
        self.assertEqual(evaluation.raw_payload_json, response)
        self.assertEqual(evaluation.summary, "Ответ частично закрывает вопрос, но требует глубины.")
        self.assertEqual(
            [score.dimension.slug for score in evaluation.scores],
            [dimension.slug for dimension in dimensions],
        )
        self.assertEqual(evaluation.scores[-1].score, 2)
        self.assertEqual(evaluation.next_drills, ["Повтори evidence.", "Добавь tradeoffs."])
        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("<rubric_answer_evaluation_json>", llm.prompts[0])
        self.assertIn("<candidate_answer>\nНужно смотреть метрики и иметь rollback.\n</candidate_answer>", llm.prompts[0])

    def test_evaluation_service_falls_back_when_llm_json_is_invalid(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        dimensions = repository.list_rubric_dimensions()
        llm = RecordingLLM("Ollama недоступна, используй fallback checklist.")
        service = EvaluationService(repository, llm)

        evaluation = service.evaluate_answer_with_llm(
            question,
            user_answer="не знаю",
            reference_answer=question.reference_answer,
        )

        self.assertEqual(evaluation.source, "fallback-heuristic")
        self.assertIsNone(evaluation.raw_payload_json)
        self.assertEqual(
            [score.dimension.slug for score in evaluation.scores],
            [dimension.slug for dimension in dimensions],
        )
        self.assertLessEqual(max(score.score for score in evaluation.scores), 2)
        self.assertIn("слабый", evaluation.summary)
        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("<rubric_answer_evaluation_json>", llm.prompts[0])

    def test_evaluation_service_falls_back_when_llm_is_unavailable(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        dimensions = repository.list_rubric_dimensions()
        llm = UnavailableLLM()
        service = EvaluationService(repository, llm)

        evaluation = service.evaluate_answer_with_llm(
            question,
            user_answer="Нужно смотреть метрики, делать rollback и проверять retry.",
            reference_answer=question.reference_answer,
        )

        self.assertEqual(evaluation.source, "fallback-heuristic")
        self.assertIsNone(evaluation.raw_payload_json)
        self.assertEqual(
            [score.dimension.slug for score in evaluation.scores],
            [dimension.slug for dimension in dimensions],
        )
        self.assertTrue(all(1 <= score.score <= 5 for score in evaluation.scores))
        self.assertTrue(evaluation.next_drills)
        self.assertEqual(len(llm.prompts), 1)

    def test_evaluation_service_persists_answer_evaluation_without_overwriting_textual_feedback(self) -> None:
        repository = make_repository()
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
                user_answer="Нужно назвать tradeoffs, rollback, метрики и failure modes.",
                self_score=4,
                ai_feedback="Старый текстовый AI feedback остается в answers.",
                answered_at=datetime(2026, 5, 19, 9, 10, 0),
            )
        )
        service = EvaluationService(repository)

        saved = service.evaluate_and_store_answer(answer, question, use_llm=False)

        self.assertIsNotNone(saved.id)
        self.assertEqual(saved.answer_id, answer.id)
        self.assertEqual(saved.session_id, session.id)
        self.assertEqual(saved.question_id, question.id)
        self.assertEqual(saved.source, "heuristic")
        self.assertEqual(
            [score.dimension.slug for score in saved.scores],
            [dimension.slug for dimension in repository.list_rubric_dimensions()],
        )
        self.assertTrue(saved.next_drills)
        evaluations = repository.list_answer_evaluations_for_answer(answer.id or 0)
        self.assertEqual(len(evaluations), 1)
        self.assertEqual(evaluations[0], saved)
        row = repository.connection.execute(
            "SELECT ai_feedback FROM answers WHERE id = ?",
            (answer.id,),
        ).fetchone()
        self.assertEqual(row["ai_feedback"], "Старый текстовый AI feedback остается в answers.")

    def test_repository_replaces_question_competencies_with_primary_and_weights(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        python_runtime = repository.find_competency_by_slug("python-runtime")
        async_concurrency = repository.find_competency_by_slug("async-concurrency")
        databases = repository.find_competency_by_slug("databases")
        self.assertIsNotNone(question.id)
        self.assertIsNotNone(python_runtime)
        self.assertIsNotNone(async_concurrency)
        self.assertIsNotNone(databases)

        assert python_runtime is not None
        assert async_concurrency is not None
        assert databases is not None
        repository.set_question_competencies(
            question.id or 0,
            [
                QuestionCompetencyLink(competency=async_concurrency, weight=0.25),
                QuestionCompetencyLink(competency=python_runtime, is_primary=True, weight=0.75),
                QuestionCompetencyLink(competency=async_concurrency, weight=0.25),
            ],
        )

        initial_links = repository.list_question_competencies(question.id or 0)

        self.assertEqual([link.competency.slug for link in initial_links], ["python-runtime", "async-concurrency"])
        self.assertEqual([link.is_primary for link in initial_links], [True, False])
        self.assertEqual([link.weight for link in initial_links], [0.75, 0.25])

        repository.set_question_competencies(
            question.id or 0,
            [QuestionCompetencyLink(competency=databases, is_primary=True, weight=1.0)],
        )

        replaced_links = repository.list_question_competencies(question.id or 0)

        self.assertEqual([link.competency.slug for link in replaced_links], ["databases"])
        self.assertEqual(replaced_links[0].is_primary, True)
        self.assertEqual(replaced_links[0].weight, 1.0)

    def test_repository_add_question_competency_updates_existing_primary_link(self) -> None:
        repository = make_repository()
        topic = repository.list_topics()[0]
        self.assertIsNotNone(topic.id)
        question = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Проверочный вопрос для обновления primary competency.",
                hint="Смени primary link.",
                reference_answer="У вопроса должен остаться один primary competency.",
                source="test",
            )
        )
        python_runtime = repository.find_competency_by_slug("python-runtime")
        async_concurrency = repository.find_competency_by_slug("async-concurrency")
        self.assertIsNotNone(question.id)
        self.assertIsNotNone(python_runtime)
        self.assertIsNotNone(async_concurrency)

        assert python_runtime is not None
        assert async_concurrency is not None
        repository.add_question_competency(question.id or 0, python_runtime.id or 0, is_primary=True, weight=0.8)
        repository.add_question_competency(question.id or 0, async_concurrency.id or 0, is_primary=True, weight=0.6)
        repository.add_question_competency(question.id or 0, python_runtime.id or 0, weight=0.4)

        links = repository.list_question_competencies(question.id or 0)

        self.assertEqual([link.competency.slug for link in links], ["async-concurrency", "python-runtime"])
        self.assertEqual([link.is_primary for link in links], [True, False])
        self.assertEqual([link.weight for link in links], [0.6, 0.4])

    def test_repository_rejects_invalid_question_competency_links(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        python_runtime = repository.find_competency_by_slug("python-runtime")
        async_concurrency = repository.find_competency_by_slug("async-concurrency")
        self.assertIsNotNone(question.id)
        self.assertIsNotNone(python_runtime)
        self.assertIsNotNone(async_concurrency)

        assert python_runtime is not None
        assert async_concurrency is not None
        with self.assertRaises(ValueError):
            repository.set_question_competencies(
                question.id or 0,
                [
                    QuestionCompetencyLink(competency=python_runtime, is_primary=True),
                    QuestionCompetencyLink(competency=async_concurrency, is_primary=True),
                ],
            )

        with self.assertRaises(ValueError):
            repository.add_question_competency(question.id or 0, python_runtime.id or 0, weight=0)

    def test_repository_persists_reusable_question_tags(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        self.assertIsNotNone(question.id)

        concurrency = repository.upsert_tag(
            Tag(
                id=None,
                slug="concurrency",
                title="Concurrency",
                description="Threads, async and shared state.",
                source="manual",
            )
        )
        python_runtime = repository.upsert_tag(
            Tag(
                id=None,
                slug="python-runtime",
                title="Python runtime",
                description="Interpreter mechanics.",
                source="manual",
            )
        )

        repository.add_question_tag(question.id or 0, concurrency.id or 0)
        repository.add_question_tag(question.id or 0, concurrency.id or 0)
        repository.add_question_tag(question.id or 0, python_runtime.id or 0)

        tags = repository.list_question_tags(question.id or 0)

        self.assertEqual([tag.slug for tag in tags], ["concurrency", "python-runtime"])
        self.assertEqual([tag.slug for tag in repository.list_tags()], ["concurrency", "python-runtime"])

    def test_repository_replaces_question_tags_without_duplicates(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]
        first = repository.upsert_tag(Tag(id=None, slug="asyncio", title="Asyncio"))
        second = repository.upsert_tag(Tag(id=None, slug="queues", title="Queues"))

        repository.set_question_tags(question.id or 0, [first.id or 0, second.id or 0, first.id or 0])
        repository.set_question_tags(question.id or 0, [second.id or 0])

        self.assertEqual([tag.slug for tag in repository.list_question_tags(question.id or 0)], ["queues"])

    def test_repository_filters_questions_by_tag_slug(self) -> None:
        repository = make_repository()
        first_question, second_question = repository.list_questions()[:2]
        concurrency = repository.upsert_tag(Tag(id=None, slug="concurrency", title="Concurrency"))
        databases = repository.upsert_tag(Tag(id=None, slug="databases", title="Databases"))
        repository.set_question_tags(first_question.id or 0, [concurrency.id or 0])
        repository.set_question_tags(second_question.id or 0, [databases.id or 0])

        filtered = repository.list_questions(tag_slug="concurrency")
        same_topic_filtered = repository.list_questions(first_question.topic_id, tag_slug="concurrency")
        other_topic_filtered = repository.list_questions(second_question.topic_id, tag_slug="concurrency")

        self.assertEqual([question.id for question in filtered], [first_question.id])
        self.assertEqual([question.id for question in same_topic_filtered], [first_question.id])
        self.assertEqual(other_topic_filtered, [])
        self.assertEqual(repository.list_questions(tag_slug="missing-tag"), [])

    def test_repository_persists_notebook_entries_with_context_links(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("python-runtime")
        other_topic = repository.find_topic_by_slug("async-backend")
        curriculum_topic = repository.add_curriculum_topic(
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
        subtopic = repository.add_curriculum_subtopic(
            CurriculumSubtopic(
                id=None,
                curriculum_topic_id=curriculum_topic.id or 0,
                slug="descriptor-protocol",
                title="Descriptor protocol",
                description="Attribute lookup order.",
                source="test",
                order_index=1,
            )
        )
        source_message = repository.add_learning_dialog_message(
            LearningDialogMessage(
                id=None,
                topic_id=topic.id,
                role="assistant",
                content="Data descriptors override instance attributes.",
                created_at=datetime(2026, 5, 13, 10, 0, 0),
                dialog_session_id="learn-session-1",
            )
        )

        first = repository.add_notebook_entry(
            NotebookEntry(
                id=None,
                topic_id=topic.id,
                curriculum_subtopic_id=subtopic.id,
                dialog_session_id="learn-session-1",
                source_message_id=source_message.id,
                title="Descriptor lookup order",
                body="Data descriptors override instance attributes; non-data descriptors do not.",
                source="learning-ai",
                created_at=datetime(2026, 5, 13, 10, 1, 0),
            )
        )
        repository.add_notebook_entry(
            NotebookEntry(
                id=None,
                topic_id=other_topic.id,
                curriculum_subtopic_id=None,
                dialog_session_id="learn-session-2",
                source_message_id=None,
                title="Backpressure",
                body="Bound queues and propagate overload.",
                source="learning-ai",
                created_at=datetime(2026, 5, 13, 10, 2, 0),
            )
        )

        topic_entries = repository.list_notebook_entries(topic_id=topic.id)
        subtopic_entries = repository.list_notebook_entries(curriculum_subtopic_id=subtopic.id)
        session_entries = repository.list_notebook_entries(dialog_session_id="learn-session-1")
        source_entries = repository.list_notebook_entries(source_message_id=source_message.id)

        self.assertIsNotNone(first.id)
        self.assertEqual([entry.title for entry in topic_entries], ["Descriptor lookup order"])
        self.assertEqual([entry.id for entry in subtopic_entries], [first.id])
        self.assertEqual([entry.id for entry in session_entries], [first.id])
        self.assertEqual([entry.id for entry in source_entries], [first.id])
        self.assertEqual(topic_entries[0].source_message_id, source_message.id)

    def test_repository_persists_manual_notes_with_context_links(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("python-runtime")
        other_topic = repository.find_topic_by_slug("async-backend")
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=datetime(2026, 5, 21, 9, 0, 0),
                ended_at=None,
                target_minutes=60,
            )
        )

        first = repository.add_manual_note(
            ManualNote(
                id=None,
                topic_id=topic.id,
                session_id=session.id,
                context_type="practice-question",
                context_id="question:1",
                title="Retry semantics",
                body="Retry only idempotent operations or use idempotency keys.",
                created_at=datetime(2026, 5, 21, 9, 10, 0),
                updated_at=datetime(2026, 5, 21, 9, 10, 0),
            )
        )
        repository.add_manual_note(
            ManualNote(
                id=None,
                topic_id=other_topic.id,
                session_id=None,
                context_type="learning-dialog",
                context_id="learn-session-2",
                title="Backpressure",
                body="Bound queues and propagate overload.",
                created_at=datetime(2026, 5, 21, 9, 15, 0),
                updated_at=datetime(2026, 5, 21, 9, 15, 0),
            )
        )

        topic_notes = repository.list_manual_notes(topic_id=topic.id)
        session_notes = repository.list_manual_notes(session_id=session.id)
        context_notes = repository.list_manual_notes(
            context_type="practice-question",
            context_id="question:1",
        )
        fetched = repository.get_manual_note(first.id or 0)
        updated = repository.upsert_manual_note_by_context(
            ManualNote(
                id=None,
                topic_id=topic.id,
                session_id=session.id,
                context_type="practice-question",
                context_id="question:1",
                title="Retry semantics",
                body="Updated draft with concrete retry caveats.",
                created_at=datetime(2026, 5, 21, 9, 20, 0),
                updated_at=datetime(2026, 5, 21, 9, 20, 0),
            )
        )
        updated_context_notes = repository.list_manual_notes(
            context_type="practice-question",
            context_id="question:1",
        )

        self.assertIsNotNone(first.id)
        self.assertEqual([note.title for note in topic_notes], ["Retry semantics"])
        self.assertEqual([note.id for note in session_notes], [first.id])
        self.assertEqual([note.id for note in context_notes], [first.id])
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.body if fetched else None, first.body)
        self.assertEqual(updated.id, first.id)
        self.assertEqual([note.id for note in updated_context_notes], [first.id])
        self.assertEqual(updated_context_notes[0].body, "Updated draft with concrete retry caveats.")

    def test_session_answer_is_saved_and_reflected_in_stats(self) -> None:
        repository = make_repository()
        llm = StaticLLM()
        sessions = SessionService(repository, llm)
        stats = StatsService(repository)

        topic_id = repository.list_topics()[0].id
        session = sessions.start_session(topic_id=topic_id)
        question = sessions.next_question(session.id or 0)
        self.assertIsNotNone(question)

        answer = sessions.answer_question(
            session.id or 0,
            question.id or 0,
            "Descriptors customize attribute access and are used by properties and ORMs.",
            4,
        )
        sessions.finish_session(session.id or 0)
        dashboard = stats.dashboard()

        self.assertIsNotNone(answer.id)
        self.assertEqual(dashboard["session_count"], 1)
        self.assertEqual(dashboard["answered_count"], 1)
        self.assertEqual(dashboard["avg_score"], 4.0)
        self.assertTrue(dashboard["weak_topics"])

    def test_stats_excludes_abandoned_sessions_but_keeps_recent_history(self) -> None:
        repository = make_repository()
        stats = StatsService(repository)
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None
        question = repository.list_questions(topic.id)[0]
        started_at = datetime(2026, 5, 20, 9, 0, 0)

        completed = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=started_at,
                ended_at=None,
                target_minutes=60,
            )
        )
        repository.add_answer(
            Answer(
                id=None,
                session_id=completed.id or 0,
                question_id=question.id or 0,
                user_answer="Descriptors define controlled attribute access.",
                self_score=4,
                ai_feedback=None,
                answered_at=started_at + timedelta(minutes=5),
            )
        )
        repository.finish_session(completed.id or 0, started_at + timedelta(minutes=20))

        abandoned = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=started_at + timedelta(hours=1),
                ended_at=started_at + timedelta(hours=1, minutes=3),
                target_minutes=60,
                status=SESSION_STATUS_ABANDONED,
            )
        )
        repository.add_answer(
            Answer(
                id=None,
                session_id=abandoned.id or 0,
                question_id=question.id or 0,
                user_answer="Too short.",
                self_score=1,
                ai_feedback=None,
                answered_at=started_at + timedelta(hours=1, minutes=2),
            )
        )

        dashboard = stats.dashboard()

        self.assertEqual(dashboard["session_count"], 1)
        self.assertEqual(dashboard["answered_count"], 1)
        self.assertEqual(dashboard["avg_score"], 4.0)
        topic_row = next(item for item in dashboard["topic_dynamics"] if item["title"] == topic.title)
        self.assertEqual(topic_row["answers"], 1)
        self.assertEqual(topic_row["avg_score"], 4.0)
        self.assertEqual(
            topic_row["last_answered_at"],
            (started_at + timedelta(minutes=5)).isoformat(timespec="seconds"),
        )
        question_metrics = repository.question_practice_metrics()[question.id]
        self.assertEqual(question_metrics["answers"], 1)
        self.assertEqual(question_metrics["avg_self_score"], 4.0)
        self.assertEqual(question_metrics["last_self_score"], 4)
        recent_sessions = {item["id"]: item for item in dashboard["recent_sessions"]}
        self.assertEqual(recent_sessions[completed.id or 0]["status"], SESSION_STATUS_COMPLETED)
        self.assertEqual(recent_sessions[abandoned.id or 0]["status"], SESSION_STATUS_ABANDONED)

    def test_session_status_tracks_in_progress_completed_and_abandoned_rows(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        started_at = datetime(2026, 5, 19, 9, 0, 0)

        active = sessions.start_session(topic_id=topic.id)
        self.assertEqual(active.status, SESSION_STATUS_IN_PROGRESS)
        self.assertEqual(repository.get_session(active.id or 0).status, SESSION_STATUS_IN_PROGRESS)

        sessions.finish_session(active.id or 0)
        self.assertEqual(repository.get_session(active.id or 0).status, SESSION_STATUS_COMPLETED)

        empty = sessions.start_session(topic_id=topic.id)
        finished_empty = sessions.finish_session(empty.id or 0, abandon_if_empty=True)
        self.assertEqual(finished_empty.status, SESSION_STATUS_ABANDONED)
        self.assertEqual(repository.get_session(empty.id or 0).status, SESSION_STATUS_ABANDONED)

        answered = sessions.start_session(topic_id=topic.id)
        question = repository.list_questions(topic.id)[0]
        sessions.answer_question(
            answered.id or 0,
            question.id or 0,
            "Есть наблюдаемый ответ.",
            None,
            with_feedback=False,
        )
        finished_answered = sessions.finish_session(answered.id or 0, abandon_if_empty=True)
        self.assertEqual(finished_answered.status, SESSION_STATUS_COMPLETED)

        abandoned = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=started_at,
                ended_at=started_at + timedelta(minutes=3),
                target_minutes=60,
                status=SESSION_STATUS_ABANDONED,
            )
        )

        history_ids = [item.id for item in sessions.list_completed_sessions()]
        self.assertIn(active.id, history_ids)
        self.assertIn(answered.id, history_ids)
        self.assertNotIn(empty.id, history_ids)
        self.assertNotIn(abandoned.id, history_ids)

    def test_repository_upserts_and_reads_session_outcome(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=datetime(2026, 5, 19, 9, 0, 0),
                ended_at=datetime(2026, 5, 19, 10, 0, 0),
                target_minutes=60,
                status=SESSION_STATUS_COMPLETED,
            )
        )

        saved = repository.upsert_session_outcome(
            SessionOutcome(
                id=None,
                session_id=session.id or 0,
                summary="Уверенный разбор транзакций, но не хватило failure modes.",
                strengths=["Связал isolation level с бизнес-инвариантами."],
                gaps=["Не описал retry/idempotency после serialization failure."],
                next_drills=["Повторить transaction isolation и retry boundaries."],
                readiness_delta=0.15,
                created_at=datetime(2026, 5, 19, 10, 1, 0),
            )
        )

        self.assertIsNotNone(saved.id)
        self.assertEqual(saved.session_id, session.id)
        self.assertEqual(saved.strengths, ["Связал isolation level с бизнес-инвариантами."])
        self.assertEqual(saved.gaps, ["Не описал retry/idempotency после serialization failure."])
        self.assertEqual(saved.next_drills, ["Повторить transaction isolation и retry boundaries."])
        self.assertEqual(saved.readiness_delta, 0.15)
        self.assertEqual(saved.outcome_type, SESSION_OUTCOME_TYPE_PRACTICE)
        self.assertEqual(repository.get_session_outcome(saved.id or 0), saved)
        self.assertEqual(repository.get_session_outcome_for_session(session.id or 0), saved)

        updated = repository.upsert_session_outcome(
            SessionOutcome(
                id=None,
                session_id=session.id or 0,
                summary="Обновленный outcome после пересчета.",
                strengths=["Сильная структура ответа."],
                gaps=["Добавить production observability."],
                next_drills=["Короткий drill по metrics/traces."],
                readiness_delta=-0.05,
                created_at=datetime(2026, 5, 19, 10, 5, 0),
            )
        )

        self.assertEqual(updated.id, saved.id)
        self.assertEqual(updated.summary, "Обновленный outcome после пересчета.")
        self.assertEqual(updated.strengths, ["Сильная структура ответа."])
        self.assertEqual(updated.gaps, ["Добавить production observability."])
        self.assertEqual(updated.next_drills, ["Короткий drill по metrics/traces."])
        self.assertEqual(updated.readiness_delta, -0.05)
        self.assertIsNone(repository.get_session_outcome_for_session(999))

    def test_finish_session_generates_session_outcome_from_scores_and_evaluations(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        evaluations = EvaluationService(repository)
        question = repository.list_questions()[0]
        session = sessions.start_session(topic_id=question.topic_id)
        answer = sessions.answer_question(
            session.id or 0,
            question.id or 0,
            "не знаю",
            2,
            with_feedback=False,
        )
        evaluations.evaluate_and_store_answer(answer, question, use_llm=False)

        finished = sessions.finish_session(session.id or 0)
        outcome = repository.get_session_outcome_for_session(session.id or 0)

        self.assertEqual(finished.status, SESSION_STATUS_COMPLETED)
        self.assertIsNotNone(outcome)
        assert outcome is not None
        self.assertIn("1 ответ", outcome.summary)
        self.assertIn("Средняя самооценка: 2.0/5.", outcome.summary)
        self.assertIn("Средний rubric score:", outcome.summary)
        self.assertTrue(any("Низкие rubric dimensions" in gap for gap in outcome.gaps))
        self.assertTrue(outcome.next_drills)
        self.assertLess(outcome.readiness_delta, 0)

    def test_calibration_marks_baseline_session_outcome(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        evaluations = EvaluationService(repository)
        calibration = CalibrationService(repository)
        plan = calibration.start_baseline_session(target_minutes=25)
        first_question = plan.picks[0].question
        answer = sessions.answer_question(
            plan.session.id or 0,
            first_question.id or 0,
            "Baseline answer with a small amount of evidence.",
            3,
            with_feedback=False,
        )
        evaluations.evaluate_and_store_answer(answer, first_question, use_llm=False)
        sessions.finish_session(plan.session.id or 0)

        marked = calibration.mark_baseline_session_outcome(
            plan.session.id or 0,
            planned_questions=len(plan.picks),
        )

        self.assertIsNotNone(marked)
        assert marked is not None
        self.assertEqual(marked.outcome_type, SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE)
        self.assertIn("Baseline calibration.", marked.summary)
        self.assertIn("Planned questions:", marked.summary)
        self.assertTrue(any("baseline practice session" in item for item in marked.strengths))

    def test_calibration_repeat_outcome_compares_delta_to_previous_baseline(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        calibration = CalibrationService(repository)
        previous_completed_at = datetime(2026, 5, 1, 10, 0, 0)
        previous_session = repository.create_session(
            Session(
                id=None,
                topic_id=None,
                started_at=previous_completed_at - timedelta(minutes=25),
                ended_at=None,
                target_minutes=25,
            )
        )
        repository.finish_session(previous_session.id or 0, previous_completed_at)
        repository.upsert_session_outcome(
            SessionOutcome(
                id=None,
                session_id=previous_session.id or 0,
                summary="Baseline calibration. Previous baseline.",
                strengths=[],
                gaps=[],
                next_drills=[],
                readiness_delta=0.02,
                created_at=previous_completed_at,
                outcome_type=SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
            )
        )

        plan = calibration.start_baseline_session(target_minutes=25)
        first_question = plan.picks[0].question
        sessions.answer_question(
            plan.session.id or 0,
            first_question.id or 0,
            "Repeat baseline answer with clearer evidence.",
            4,
            with_feedback=False,
        )
        sessions.finish_session(plan.session.id or 0)

        comparison = calibration.baseline_delta_comparison(plan.session.id or 0)
        marked = calibration.mark_baseline_session_outcome(
            plan.session.id or 0,
            planned_questions=len(plan.picks),
        )

        self.assertIsNotNone(comparison)
        assert comparison is not None
        self.assertEqual(comparison.previous_session_id, previous_session.id)
        self.assertEqual(comparison.previous_readiness_delta, 0.02)
        self.assertEqual(comparison.current_readiness_delta, 0.10)
        self.assertEqual(comparison.delta_change, 0.08)
        self.assertIsNotNone(marked)
        assert marked is not None
        self.assertIn("Baseline delta comparison:", marked.summary)
        self.assertIn(f"previous session #{previous_session.id}", marked.summary)
        self.assertIn("change +0.08", marked.summary)
        self.assertTrue(any("delta comparison" in item for item in marked.strengths))
        self.assertEqual(
            calibration.baseline_delta_comparison(plan.session.id or 0),
            comparison,
        )

    def test_finish_abandoned_empty_session_does_not_generate_session_outcome(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None
        session = sessions.start_session(topic_id=topic.id)

        finished = sessions.finish_session(session.id or 0, abandon_if_empty=True)

        self.assertEqual(finished.status, SESSION_STATUS_ABANDONED)
        self.assertIsNone(repository.get_session_outcome_for_session(session.id or 0))

    def test_session_service_lists_completed_practice_sessions(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        question = repository.list_questions(topic.id)[0]
        started_at = datetime(2026, 5, 13, 9, 0, 0)
        completed = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=started_at,
                ended_at=None,
                target_minutes=60,
            )
        )
        repository.add_answer(
            Answer(
                id=None,
                session_id=completed.id or 0,
                question_id=question.id or 0,
                user_answer="Descriptors define attribute access.",
                self_score=4,
                ai_feedback=None,
                answered_at=started_at + timedelta(minutes=5),
            )
        )
        repository.finish_session(completed.id or 0, started_at + timedelta(minutes=20))
        repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=started_at + timedelta(hours=1),
                ended_at=None,
                target_minutes=60,
            )
        )

        history = sessions.list_completed_sessions()

        self.assertEqual([item.id for item in history], [completed.id])
        self.assertEqual(history[0].topic_title, topic.title)
        self.assertEqual(history[0].answer_count, 1)
        self.assertEqual(history[0].avg_self_score, 4.0)

    def test_session_service_returns_completed_practice_session_detail(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        question = repository.list_questions(topic.id)[0]
        started_at = datetime(2026, 5, 13, 9, 0, 0)
        completed = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=started_at,
                ended_at=None,
                target_minutes=60,
            )
        )
        repository.add_answer(
            Answer(
                id=None,
                session_id=completed.id or 0,
                question_id=question.id or 0,
                user_answer="Descriptors define attribute access.",
                self_score=4,
                ai_feedback="Feedback text.",
                answered_at=started_at + timedelta(minutes=5),
            )
        )
        repository.finish_session(completed.id or 0, started_at + timedelta(minutes=20))

        detail = sessions.get_completed_session_detail(completed.id or 0)

        self.assertIsNotNone(detail)
        self.assertEqual(detail.summary.id, completed.id)
        self.assertEqual(detail.summary.topic_title, topic.title)
        self.assertEqual(len(detail.answers), 1)
        self.assertEqual(detail.answers[0].question_id, question.id)
        self.assertEqual(detail.answers[0].question_prompt, question.prompt)
        self.assertEqual(detail.answers[0].user_answer, "Descriptors define attribute access.")
        self.assertEqual(detail.answers[0].self_score, 4)
        self.assertEqual(detail.answers[0].reference_answer, question.reference_answer)
        self.assertEqual(detail.answers[0].ai_feedback, "Feedback text.")

    def test_read_only_facade_exposes_serializable_snapshot_without_writes(self) -> None:
        repository = make_repository()
        llm = StaticLLM()
        questions = QuestionService(repository, llm)
        sessions = SessionService(repository, llm)
        stats = StatsService(repository)
        learning = LearningService(repository, llm)
        content_generation = ContentGenerationService(repository, llm)
        curriculum = CurriculumService(repository, llm)
        facade = ReadOnlyApplicationFacade(
            questions=questions,
            sessions=sessions,
            stats=stats,
            learning=learning,
            content_generation=content_generation,
            curriculum=curriculum,
            repository=repository,
            readiness=ReadinessService(repository),
        )
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        question = repository.list_questions(topic.id)[0]
        tag = repository.upsert_tag(Tag(id=None, slug="runtime", title="Runtime"))
        repository.add_question_tag(question.id or 0, tag.id or 0)
        competency = repository.find_competency_by_slug("python-runtime")
        self.assertIsNotNone(competency)
        repository.set_question_competencies(
            question.id or 0,
            [QuestionCompetencyLink(competency=competency, is_primary=True, weight=1.5)],
        )
        started_at = datetime(2026, 5, 19, 9, 0, 0)
        completed = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=started_at,
                ended_at=None,
                target_minutes=60,
            )
        )
        repository.add_answer(
            Answer(
                id=None,
                session_id=completed.id or 0,
                question_id=question.id or 0,
                user_answer="Descriptors customize attribute access.",
                self_score=4,
                ai_feedback="Feedback text.",
                answered_at=started_at + timedelta(minutes=5),
            )
        )
        repository.finish_session(completed.id or 0, started_at + timedelta(minutes=20))
        learning.add_dialog_message(
            topic.id or 0,
            "user",
            "Как работают descriptors?",
            dialog_session_id="learn-web-1",
        )
        notebook = repository.add_notebook_entry(
            NotebookEntry(
                id=None,
                topic_id=topic.id or 0,
                curriculum_subtopic_id=None,
                dialog_session_id="learn-web-1",
                source_message_id=None,
                title="Descriptors",
                body="Descriptors define attribute access protocol.",
                source="learning-ai",
                created_at=started_at + timedelta(minutes=10),
            )
        )
        material = repository.add_learning_material(
            LearningMaterial(
                id=None,
                topic_id=topic.id or 0,
                title="Runtime material",
                body="Learning body.",
                source="test",
                created_at=started_at + timedelta(minutes=11),
            )
        )
        scenario = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic.id or 0,
                title="Runtime scenario",
                scenario="Design an import cache.",
                focus_areas=["requirements", "cache"],
                source="test",
                created_at=started_at + timedelta(minutes=12),
            )
        )
        content_generation.enqueue_question(topic.id or 0, "Read facade queued job")

        before_stats = repository.stats()
        before_job_ids = [job.id for job in repository.list_content_generation_jobs(limit=100)]

        snapshot = facade.dashboard(limit=5)
        detail = facade.completed_session_detail(completed.id or 0)
        topic_questions = facade.questions(topic_id=topic.id)
        notebook_entries = facade.notebook_entries(topic_id=topic.id)
        artifacts = facade.generated_artifacts(topic_id=topic.id)

        json.dumps(
            {
                "snapshot": snapshot,
                "detail": detail,
                "topic_questions": topic_questions,
                "notebook_entries": notebook_entries,
                "artifacts": artifacts,
            },
            ensure_ascii=False,
        )
        after_stats = repository.stats()
        after_job_ids = [job.id for job in repository.list_content_generation_jobs(limit=100)]
        self.assertEqual(before_stats["session_count"], after_stats["session_count"])
        self.assertEqual(before_stats["answered_count"], after_stats["answered_count"])
        self.assertEqual(before_job_ids, after_job_ids)
        self.assertEqual(snapshot["stats"]["answered_count"], 1)
        self.assertTrue(snapshot["topics"])
        self.assertEqual(snapshot["competencies"][0]["slug"], "python-runtime")
        self.assertIn("overall_summary", snapshot["readiness"])
        self.assertIn("competencies", snapshot["readiness"])
        self.assertGreater(snapshot["readiness"]["competency_count"], 0)
        self.assertEqual(snapshot["recent_sessions"][0]["id"], completed.id)
        self.assertEqual(snapshot["learning_dialogs"][0]["dialog_session_id"], "learn-web-1")
        self.assertEqual(snapshot["content_jobs"][0]["status"], "queued")
        self.assertEqual(detail["answers"][0]["user_answer"], "Descriptors customize attribute access.")
        saved_question = next(item for item in topic_questions if item["id"] == question.id)
        self.assertEqual(saved_question["tags"][0]["slug"], "runtime")
        self.assertEqual(saved_question["competencies"][0]["competency"]["slug"], "python-runtime")
        self.assertTrue(saved_question["competencies"][0]["is_primary"])
        self.assertEqual(saved_question["competencies"][0]["weight"], 1.5)
        self.assertEqual(notebook_entries[0]["id"], notebook.id)
        self.assertEqual(artifacts["learning_materials"][0]["id"], material.id)
        self.assertEqual(artifacts["system_design_scenarios"][0]["id"], scenario.id)

    def test_stats_service_ranks_weak_topics_by_score_count_and_recency(self) -> None:
        repository = make_repository()
        stats = StatsService(repository)
        now = datetime(2026, 5, 13, 12, 0, 0)
        python_topic = repository.find_topic_by_slug("python-runtime")
        async_topic = repository.find_topic_by_slug("async-backend")
        db_topic = repository.find_topic_by_slug("databases")
        system_design_topic = repository.find_topic_by_slug("system-design")
        testing_topic = repository.find_topic_by_slug("testing-quality")
        self.assertIsNotNone(python_topic)
        self.assertIsNotNone(async_topic)
        self.assertIsNotNone(db_topic)
        self.assertIsNotNone(system_design_topic)
        self.assertIsNotNone(testing_topic)

        for _ in range(3):
            self._save_answer(repository, python_topic.id or 0, 2, now - timedelta(days=1))
            self._save_answer(repository, db_topic.id or 0, 5, now - timedelta(days=45))
            self._save_answer(repository, system_design_topic.id or 0, 5, now - timedelta(days=1))
            self._save_answer(repository, testing_topic.id or 0, 5, now - timedelta(days=1))
        self._save_answer(repository, async_topic.id or 0, 5, now - timedelta(days=1))

        weak_topics = stats.weak_topics(now=now)

        self.assertEqual([item.topic.id for item in weak_topics[:3]], [python_topic.id, db_topic.id, async_topic.id])
        self.assertEqual(weak_topics[0].avg_self_score, 2.0)
        self.assertIn("низкая самооценка: 2.0/5", weak_topics[0].reasons)
        self.assertIn("давно не повторялась: 45 дн.", weak_topics[1].reasons)
        self.assertIn("мало ответов: 1/3", weak_topics[2].reasons)

    def test_readiness_service_aggregates_competency_practice_signals(self) -> None:
        repository = make_repository()
        readiness = ReadinessService(repository)
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None
        competency = repository.upsert_competency(
            Competency(
                id=None,
                slug="readiness-custom",
                title="Readiness Custom",
                description="Synthetic competency for readiness aggregation tests.",
                category="readiness",
                level="senior",
                order_index=999,
            )
        )
        answered_question = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Как проверить readiness aggregation?",
                hint="Свяжи question coverage, rubric score и recency.",
                reference_answer="Нужны competency links, rubric evidence, coverage и свежесть практики.",
                source="test",
            )
        )
        untouched_question = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Как проверить отсутствие coverage?",
                hint="Второй вопрос остается без completed answer.",
                reference_answer="Coverage должна учитывать только completed/non-abandoned answers.",
                source="test",
            )
        )
        repository.set_question_competencies(
            answered_question.id or 0,
            [QuestionCompetencyLink(competency=competency, is_primary=True)],
        )
        repository.set_question_competencies(
            untouched_question.id or 0,
            [QuestionCompetencyLink(competency=competency)],
        )

        answered_at = datetime(2026, 5, 20, 9, 10, 0)
        completed = repository.create_session(
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
                session_id=completed.id or 0,
                question_id=answered_question.id or 0,
                user_answer="Coverage связывает question links, rubric scores, recency и self-score.",
                self_score=2,
                ai_feedback=None,
                answered_at=answered_at,
            )
        )
        repository.finish_session(completed.id or 0, answered_at + timedelta(minutes=20))
        evaluation = EvaluationService(repository).evaluate_and_store_answer(
            answer,
            answered_question,
            use_llm=False,
        )

        abandoned = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=answered_at + timedelta(hours=1),
                ended_at=answered_at + timedelta(hours=1, minutes=3),
                target_minutes=60,
                status=SESSION_STATUS_ABANDONED,
            )
        )
        repository.add_answer(
            Answer(
                id=None,
                session_id=abandoned.id or 0,
                question_id=untouched_question.id or 0,
                user_answer="Abandoned answer must not count.",
                self_score=1,
                ai_feedback=None,
                answered_at=answered_at + timedelta(hours=1, minutes=1),
            )
        )

        snapshot = readiness.snapshot(now=datetime(2026, 5, 20, 12, 0, 0))
        aggregate = next(
            item for item in snapshot.competencies if item.competency.slug == "readiness-custom"
        )
        expected_rubric_score = sum(score.score for score in evaluation.scores) / len(evaluation.scores)

        self.assertGreaterEqual(snapshot.competency_count, 1)
        self.assertIn(aggregate, snapshot.competencies)
        self.assertEqual(aggregate.linked_questions, 2)
        self.assertEqual(aggregate.primary_questions, 1)
        self.assertEqual(aggregate.answered_questions, 1)
        self.assertEqual(aggregate.answer_count, 1)
        self.assertEqual(aggregate.evaluated_answer_count, 1)
        self.assertEqual(aggregate.avg_self_score, 2.0)
        self.assertAlmostEqual(aggregate.avg_rubric_score or 0, expected_rubric_score)
        self.assertEqual(aggregate.last_answered_at, answered_at)
        self.assertEqual(aggregate.answer_coverage, 0.5)
        self.assertIsInstance(aggregate.readiness_score, int)
        self.assertIn("readiness_score", aggregate.to_dict())
        self.assertIn("readiness_reasons", aggregate.to_dict())
        self.assertEqual(snapshot.to_dict()["evaluated_competency_count"], snapshot.evaluated_competency_count)
        self.assertEqual(aggregate.to_dict()["competency"]["slug"], "readiness-custom")

    def test_readiness_uses_manual_override_scores_while_preserving_original_audit(
        self,
    ) -> None:
        repository = make_repository()
        readiness = ReadinessService(repository)
        now = datetime(2026, 5, 26, 12, 0, 0)
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None
        competency = repository.upsert_competency(
            Competency(
                id=None,
                slug="readiness-override-audit",
                title="Readiness Override Audit",
                description="Synthetic competency for manual override readiness tests.",
                category="readiness",
                level="senior",
                order_index=1001,
            )
        )
        question = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Как проверить manual override readiness?",
                hint="Ответ должен дать enough evidence для rubric readiness.",
                reference_answer="Нужны tradeoffs, failure modes, production details и evidence.",
                source="test",
            )
        )
        repository.set_question_competencies(
            question.id or 0,
            [QuestionCompetencyLink(competency=competency, is_primary=True)],
        )
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=now - timedelta(minutes=30),
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
                self_score=2,
                ai_feedback=None,
                answered_at=now - timedelta(minutes=20),
            )
        )
        repository.finish_session(session.id or 0, now - timedelta(minutes=5))
        evaluation_service = EvaluationService(repository)
        evaluation = evaluation_service.evaluate_and_store_answer(answer, question, use_llm=False)
        original_scores = {score.dimension.slug: score.score for score in evaluation.scores}

        before = next(
            item
            for item in readiness.snapshot(now=now).competencies
            if item.competency.slug == "readiness-override-audit"
        )
        self.assertLess(before.avg_rubric_score or 0, 3.5)
        self.assertTrue(
            any(reason.startswith("низкая rubric оценка:") for reason in before.readiness_reasons)
        )

        for score in evaluation.scores:
            evaluation_service.override_score(
                evaluation.id or 0,
                dimension_slug=score.dimension.slug,
                score=5,
                reason="Manual audit correction for readiness.",
                overridden_at=now,
            )

        after = next(
            item
            for item in readiness.snapshot(now=now).competencies
            if item.competency.slug == "readiness-override-audit"
        )
        updated = repository.get_answer_evaluation(evaluation.id or 0)
        self.assertIsNotNone(updated)
        assert updated is not None

        self.assertAlmostEqual(after.avg_rubric_score or 0, 5.0)
        self.assertGreater(after.readiness_score, before.readiness_score)
        self.assertFalse(
            any(reason.startswith("низкая rubric оценка:") for reason in after.readiness_reasons)
        )
        for score in updated.scores:
            self.assertEqual(score.score, original_scores[score.dimension.slug])
            self.assertEqual(score.manual_override_score, 5)
            self.assertEqual(score.effective_score, 5)
            self.assertEqual(score.manual_override_reason, "Manual audit correction for readiness.")
            self.assertEqual(score.manual_override_at, now)
        repository.close()

    def test_readiness_service_scores_competencies_with_gap_reasons(self) -> None:
        repository = make_repository()
        readiness = ReadinessService(repository)
        now = datetime(2026, 5, 20, 12, 0, 0)
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None
        competency = repository.upsert_competency(
            Competency(
                id=None,
                slug="readiness-score-custom",
                title="Readiness Score Custom",
                description="Synthetic competency for readiness scoring tests.",
                category="readiness",
                level="senior",
                order_index=1000,
            )
        )
        question = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Как проверить readiness scoring?",
                hint="Ответ должен дать enough evidence для senior scoring.",
                reference_answer="Нужны tradeoffs, failure modes, production details и evidence.",
                source="test",
            )
        )
        repository.set_question_competencies(
            question.id or 0,
            [QuestionCompetencyLink(competency=competency, is_primary=True)],
        )
        answered_at = now - timedelta(days=45)
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
                self_score=2,
                ai_feedback=None,
                answered_at=answered_at,
            )
        )
        repository.finish_session(session.id or 0, answered_at + timedelta(minutes=15))
        EvaluationService(repository).evaluate_and_store_answer(answer, question, use_llm=False)

        snapshot = readiness.snapshot(now=now)
        aggregate = next(
            item for item in snapshot.competencies if item.competency.slug == "readiness-score-custom"
        )
        system_design = next(
            item for item in snapshot.competencies if item.competency.slug == "system-design"
        )

        self.assertLess(aggregate.readiness_score, 70)
        self.assertIn("мало ответов: 1/3", aggregate.readiness_reasons)
        self.assertTrue(
            any(reason.startswith("низкая rubric оценка:") for reason in aggregate.readiness_reasons)
        )
        self.assertIn("давно не повторялось: 45 дн.", aggregate.readiness_reasons)
        self.assertIn("нет system design практики", system_design.readiness_reasons)

        system_design_topic = repository.find_topic_by_slug("system-design")
        self.assertIsNotNone(system_design_topic)
        assert system_design_topic is not None
        repository.add_system_design_transcript_message(
            SystemDesignTranscriptMessage(
                id=None,
                topic_id=system_design_topic.id or 0,
                scenario_id=None,
                role="candidate",
                content="Начну с требований, API и failure modes.",
                created_at=now,
            )
        )
        refreshed = readiness.snapshot(now=now)
        refreshed_system_design = next(
            item for item in refreshed.competencies if item.competency.slug == "system-design"
        )
        self.assertNotIn("нет system design практики", refreshed_system_design.readiness_reasons)

    def test_readiness_service_builds_overall_summary_without_absolute_claim(self) -> None:
        repository = make_repository()
        readiness = ReadinessService(repository)
        now = datetime(2026, 5, 20, 12, 0, 0)
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None
        question = repository.list_questions(topic.id or 0)[0]
        answered_at = now - timedelta(days=2)
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
                user_answer=(
                    "Я объясню runtime механизм, tradeoffs, observability и failure modes "
                    "через production пример."
                ),
                self_score=4,
                ai_feedback=None,
                answered_at=answered_at,
            )
        )
        repository.finish_session(session.id or 0, answered_at + timedelta(minutes=20))
        EvaluationService(repository).evaluate_and_store_answer(answer, question, use_llm=False)

        snapshot = readiness.snapshot(now=now)
        overall = snapshot.overall_summary
        data = snapshot.to_dict()["overall_summary"]

        self.assertIsNotNone(overall.signal_score)
        self.assertGreater(snapshot.covered_competency_count, 0)
        self.assertGreater(snapshot.evaluated_competency_count, 0)
        self.assertTrue(overall.top_gaps)
        self.assertEqual(overall.recommended_drill, overall.top_gaps[0])
        self.assertIn("Evidence покрывает", overall.summary)
        self.assertIn("не абсолютная оценка кандидата", overall.caveat)
        self.assertEqual(data["recommended_drill"], data["top_gaps"][0])
        self.assertIn("why_this_drill", data["recommended_drill"])
        self.assertIn("must_fix_drill", data["recommended_drill"])
        self.assertTrue(data["recommended_drill"]["must_fix_drill"])
        self.assertIn("top readiness gap", data["recommended_drill"]["why_this_drill"])
        self.assertNotIn("готов к senior", data["summary"].lower())

    def test_readiness_service_builds_weekly_trend_from_completed_session_outcomes(self) -> None:
        repository = make_repository()
        readiness = ReadinessService(repository)
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None

        def save_outcome(
            ended_at: datetime,
            readiness_delta: float,
            *,
            outcome_type: str = SESSION_OUTCOME_TYPE_PRACTICE,
        ) -> None:
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
                    outcome_type=outcome_type,
                )
            )

        save_outcome(datetime(2026, 5, 5, 10, 0, 0), 0.10)
        save_outcome(
            datetime(2026, 5, 6, 10, 0, 0),
            0.20,
            outcome_type=SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
        )
        save_outcome(datetime(2026, 5, 13, 10, 0, 0), -0.10)
        abandoned = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=datetime(2026, 5, 14, 9, 0, 0),
                ended_at=datetime(2026, 5, 14, 9, 5, 0),
                target_minutes=60,
                status=SESSION_STATUS_ABANDONED,
            )
        )
        repository.upsert_session_outcome(
            SessionOutcome(
                id=None,
                session_id=abandoned.id or 0,
                summary="Abandoned sessions do not affect readiness trend.",
                strengths=[],
                gaps=[],
                next_drills=[],
                readiness_delta=0.99,
                created_at=datetime(2026, 5, 14, 9, 5, 0),
            )
        )

        snapshot = readiness.snapshot(now=datetime(2026, 5, 20, 12, 0, 0))
        trend = snapshot.weekly_trend

        self.assertEqual(len(trend), 2)
        self.assertEqual(trend[0].week_start.isoformat(), "2026-05-04")
        self.assertEqual(trend[0].week_end.isoformat(), "2026-05-10")
        self.assertEqual(trend[0].session_count, 2)
        self.assertEqual(trend[0].baseline_session_count, 1)
        self.assertEqual(trend[0].avg_readiness_delta, 0.15)
        self.assertEqual(trend[0].total_readiness_delta, 0.3)
        self.assertEqual(trend[1].week_start.isoformat(), "2026-05-11")
        self.assertEqual(trend[1].session_count, 1)
        self.assertEqual(trend[1].baseline_session_count, 0)
        self.assertEqual(trend[1].avg_readiness_delta, -0.1)
        self.assertEqual(snapshot.to_dict()["weekly_trend"][0]["baseline_session_count"], 1)
        self.assertEqual(snapshot.to_dict()["weekly_trend"][0]["avg_readiness_delta"], 0.15)

    def test_readiness_recommends_low_rubric_topic_as_first_drill(self) -> None:
        repository = make_repository()
        readiness = ReadinessService(repository)
        now = datetime(2026, 5, 20, 12, 0, 0)
        topic = repository.find_topic_by_slug("databases")
        self.assertIsNotNone(topic)
        assert topic is not None
        question = repository.list_questions(topic.id or 0)[0]
        answered_at = now - timedelta(days=1)
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
        EvaluationService(repository).evaluate_and_store_answer(answer, question, use_llm=False)

        snapshot = readiness.snapshot(now=now)
        recommended = snapshot.overall_summary.recommended_drill

        self.assertIsNotNone(recommended)
        assert recommended is not None
        self.assertEqual(recommended.competency.slug, "databases")
        self.assertTrue(
            any(reason.startswith("низкая rubric оценка:") for reason in recommended.reasons)
        )
        self.assertIn("Перерешать слабый ответ", recommended.next_action)
        self.assertIn("production tradeoffs", recommended.must_fix_drill)
        self.assertEqual(
            snapshot.to_dict()["overall_summary"]["recommended_drill"]["competency"]["slug"],
            "databases",
        )

    def test_mixed_session_next_question_prioritizes_weak_topic(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        now = datetime(2026, 5, 13, 12, 0, 0)
        weak_topic = repository.find_topic_by_slug("databases")
        self.assertIsNotNone(weak_topic)

        for topic in repository.list_topics():
            score = 2 if topic.id == weak_topic.id else 5
            for _ in range(3):
                self._save_answer(repository, topic.id or 0, score, now - timedelta(days=1))

        session = sessions.start_session(topic_id=None)
        question = sessions.next_question(session.id or 0)
        candidates = sessions.candidate_questions(session.id or 0)

        self.assertIsNotNone(question)
        self.assertEqual(question.topic_id, weak_topic.id)
        self.assertEqual(candidates[0].topic_id, weak_topic.id)

    def test_topic_session_repeats_weak_question_after_interval(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        now = datetime(2026, 5, 13, 12, 0, 0)
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        stable_question = repository.list_questions(topic.id or 0)[0]
        recent_weak_question = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Недавний слабый вопрос.",
                hint="Проверь interval.",
                reference_answer="Эталон.",
                source="test",
            )
        )
        due_weak_question = repository.add_question(
            Question(
                id=None,
                topic_id=topic.id or 0,
                difficulty="senior",
                prompt="Старый слабый вопрос.",
                hint="Проверь repeat.",
                reference_answer="Эталон.",
                source="test",
            )
        )
        self._save_answer_for_question(repository, stable_question.id or 0, topic.id or 0, 5, now - timedelta(days=10))
        self._save_answer_for_question(
            repository,
            recent_weak_question.id or 0,
            topic.id or 0,
            2,
            now - timedelta(days=1),
        )
        self._save_answer_for_question(
            repository,
            due_weak_question.id or 0,
            topic.id or 0,
            2,
            now - timedelta(days=8),
        )

        session = sessions.start_session(topic_id=topic.id)
        candidates = sessions.candidate_questions(session.id or 0, now=now)

        self.assertEqual(candidates[0].id, due_weak_question.id)
        self.assertGreater(
            [question.id for question in candidates].index(recent_weak_question.id),
            [question.id for question in candidates].index(due_weak_question.id),
        )

    def test_calibration_baseline_plan_picks_five_distinct_competencies(self) -> None:
        repository = make_repository()
        service = CalibrationService(repository)

        picks = service.baseline_question_plan()

        self.assertEqual(len(picks), 5)
        self.assertEqual(
            [pick.competency.slug for pick in picks],
            [
                "python-runtime",
                "async-concurrency",
                "databases",
                "system-design",
                "testing-quality",
            ],
        )
        self.assertEqual(len({pick.question.id for pick in picks}), 5)
        self.assertTrue(all(pick.link.is_primary for pick in picks))

    def test_calibration_baseline_plan_prefers_unanswered_questions(self) -> None:
        repository = make_repository()
        now = datetime(2026, 5, 25, 10, 0, 0)
        python_topic = repository.find_topic_by_slug("python-runtime")
        python_runtime = repository.find_competency_by_slug("python-runtime")
        self.assertIsNotNone(python_topic)
        self.assertIsNotNone(python_runtime)
        assert python_topic is not None
        assert python_runtime is not None
        bootstrap_question = repository.list_questions(python_topic.id or 0)[0]
        unanswered_question = repository.add_question(
            Question(
                id=None,
                topic_id=python_topic.id or 0,
                difficulty="senior",
                prompt="Новый baseline-вопрос по Python runtime.",
                hint="Проверь, что unanswered идет раньше.",
                reference_answer="Эталон.",
                source="test",
            )
        )
        repository.set_question_competencies(
            unanswered_question.id or 0,
            [QuestionCompetencyLink(competency=python_runtime, is_primary=True)],
        )
        self._save_answer_for_question(
            repository,
            bootstrap_question.id or 0,
            python_topic.id or 0,
            5,
            now,
        )

        picks = CalibrationService(repository).baseline_question_plan(limit=1)

        self.assertEqual(picks[0].competency.slug, "python-runtime")
        self.assertEqual(picks[0].question.id, unanswered_question.id)

    def test_calibration_starts_mixed_baseline_session_from_plan(self) -> None:
        repository = make_repository()
        service = CalibrationService(repository)

        plan = service.start_baseline_session(target_minutes=25)

        self.assertIsNotNone(plan.session.id)
        self.assertIsNone(plan.session.topic_id)
        self.assertEqual(plan.session.target_minutes, 25)
        self.assertEqual(len(plan.picks), 5)
        self.assertEqual(
            plan.question_ids,
            tuple(pick.question.id for pick in service.baseline_question_plan()),
        )

    def test_calibration_baseline_repeat_status_uses_seven_day_interval(self) -> None:
        repository = make_repository()
        service = CalibrationService(repository)
        topic = repository.find_topic_by_slug("python-runtime")
        self.assertIsNotNone(topic)
        assert topic is not None
        completed_at = datetime(2026, 5, 1, 10, 0, 0)
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic.id,
                started_at=completed_at - timedelta(minutes=30),
                ended_at=None,
                target_minutes=60,
            )
        )
        repository.finish_session(session.id or 0, completed_at)
        repository.upsert_session_outcome(
            SessionOutcome(
                id=None,
                session_id=session.id or 0,
                summary="Baseline outcome.",
                strengths=[],
                gaps=[],
                next_drills=[],
                readiness_delta=0.12,
                created_at=completed_at,
                outcome_type=SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
            )
        )

        early = service.baseline_repeat_status(now=datetime(2026, 5, 7, 9, 0, 0))
        due = service.baseline_repeat_status(now=datetime(2026, 5, 8, 10, 0, 0))

        self.assertEqual(early.last_session_id, session.id)
        self.assertEqual(early.last_completed_at, completed_at)
        self.assertEqual(early.last_readiness_delta, 0.12)
        self.assertEqual(early.next_due_at, datetime(2026, 5, 8, 10, 0, 0))
        self.assertFalse(early.is_due)
        self.assertEqual(early.days_until_due, 2)
        self.assertTrue(due.is_due)
        self.assertEqual(due.days_until_due, 0)

    def test_mock_senior_interview_plan_mixes_interview_sections(self) -> None:
        repository = make_repository()
        service = CalibrationService(repository)

        plan = service.mock_senior_interview_plan()

        self.assertEqual(plan.sections, ("coding", "theory", "system_design", "debugging"))
        self.assertEqual(len(plan.question_ids), 4)
        self.assertEqual(len(set(plan.question_ids)), 4)
        self.assertEqual(
            [pick.competency.slug for pick in plan.picks],
            ["python-runtime", "databases", "system-design", "observability"],
        )

    def test_calibration_starts_mixed_mock_senior_interview_session_from_plan(self) -> None:
        repository = make_repository()
        service = CalibrationService(repository)

        plan = service.start_mock_senior_interview_session(target_minutes=45)

        self.assertIsNotNone(plan.session.id)
        self.assertIsNone(plan.session.topic_id)
        self.assertEqual(plan.session.target_minutes, 45)
        self.assertEqual(plan.sections, ("coding", "theory", "system_design", "debugging"))
        self.assertEqual(len(plan.question_ids), 4)
        self.assertEqual(
            plan.question_ids,
            tuple(pick.question.id for pick in service.mock_senior_interview_plan().picks),
        )

    def test_add_question_from_free_text_uses_structured_llm_output(self) -> None:
        repository = make_repository()
        service = QuestionService(repository, StaticLLM())

        topic_id = repository.find_topic_by_slug("async-backend").id
        question = service.add_from_free_text("Добавь вопрос про async incidents", topic_id)

        self.assertEqual(question.difficulty, "senior")
        self.assertIn("async production incident", question.prompt)
        self.assertEqual(question.source, "user-llm")

    def test_invalid_self_score_is_rejected(self) -> None:
        repository = make_repository()
        sessions = SessionService(repository, StaticLLM())
        session = sessions.start_session()
        question = sessions.next_question(session.id or 0)

        with self.assertRaises(ValueError):
            sessions.answer_question(session.id or 0, question.id or 0, "answer", 6)

    def test_feedback_prompt_forbids_attributing_reference_to_candidate(self) -> None:
        repository = make_repository()
        question = repository.list_questions()[0]

        prompt = build_feedback_prompt(question, "эта тузла для мета программирования")

        self.assertIn("<candidate_answer>\nэта тузла для мета программирования\n</candidate_answer>", prompt)
        self.assertIn("Оценивай ТОЛЬКО текст между тегами", prompt)
        self.assertIn("Нельзя писать", prompt)
        self.assertIn("не переноси пункты из эталона", prompt)
        self.assertLess(prompt.index("<candidate_answer>"), prompt.index("<reference_answer>"))

    def test_feedback_prompt_requires_evidence_only_rules_and_answer_tags(self) -> None:
        question = Question(
            id=1,
            topic_id=1,
            difficulty="senior",
            prompt="Как оценить ответ про database indexes?",
            hint="",
            reference_answer=(
                "Сильный ответ объясняет B-tree, selectivity, write amplification, "
                "covering indexes и query plans."
            ),
            source="test",
        )

        prompt = build_feedback_prompt(question, "Индексы ускоряют чтение, но замедляют запись.")

        self.assertEqual(prompt.count("<candidate_answer>\n"), 1)
        self.assertEqual(prompt.count("\n</candidate_answer>"), 1)
        self.assertEqual(prompt.count("<reference_answer>\n"), 1)
        self.assertEqual(prompt.count("\n</reference_answer>"), 1)
        self.assertIn(
            "Любая похвала и любые положительные утверждения должны опираться на evidence "
            "из <candidate_answer>, а не на <reference_answer>.",
            prompt,
        )
        self.assertIn("Эталонный ответ используй только как чеклист", prompt)
        self.assertIn(
            "<candidate_answer>\nИндексы ускоряют чтение, но замедляют запись.\n</candidate_answer>",
            prompt,
        )
        self.assertIn(
            "<reference_answer>\n"
            "Сильный ответ объясняет B-tree, selectivity, write amplification, "
            "covering indexes и query plans.\n"
            "</reference_answer>",
            prompt,
        )
        self.assertLess(prompt.rindex("<candidate_answer>"), prompt.rindex("<reference_answer>"))

    def test_recheck_feedback_prompt_is_stricter_and_includes_previous_feedback(self) -> None:
        question = Question(
            id=1,
            topic_id=1,
            difficulty="senior",
            prompt="Как оценить ответ про retries и idempotency?",
            hint="",
            reference_answer="Сильный ответ покрывает idempotency key, backoff, DLQ и observability.",
            source="test",
        )

        prompt = build_recheck_feedback_prompt(
            question,
            "не знаю",
            "Хорошо:\n- Хорошо раскрыл idempotency key и DLQ.",
        )

        self.assertEqual(prompt.count("<candidate_answer>\n"), 1)
        self.assertEqual(prompt.count("<previous_feedback>\n"), 1)
        self.assertEqual(prompt.count("<reference_answer>\n"), 1)
        self.assertIn("проверяешь AI feedback повторно", prompt)
        self.assertIn("<candidate_answer>\nне знаю\n</candidate_answer>", prompt)
        self.assertIn("может содержать завышенную похвалу", prompt)
        self.assertIn("Пока нет подтвержденных сильных сторон", prompt)
        self.assertIn("Хорошо раскрыл idempotency key и DLQ", prompt)
        self.assertLess(prompt.index("<candidate_answer>"), prompt.index("<previous_feedback>"))
        self.assertLess(prompt.index("<previous_feedback>"), prompt.index("<reference_answer>"))

    def test_recheck_feedback_with_quality_uses_strict_prompt(self) -> None:
        question = Question(
            id=1,
            topic_id=1,
            difficulty="senior",
            prompt="Как оценить ответ про retries и idempotency?",
            hint="",
            reference_answer="Сильный ответ покрывает idempotency key, backoff, DLQ и observability.",
            source="test",
        )
        llm = RecordingLLM(
            "Понял твой ответ:\n"
            "- Кандидат ответил, что не знает.\n\n"
            "Хорошо:\n"
            "- Пока нет подтвержденных сильных сторон в ответе.\n\n"
            "Упущено:\n"
            "- Idempotency key, backoff и DLQ.\n\n"
            "Повторить:\n"
            "- Reliable retries."
        )
        service = SessionService(make_repository(), llm)

        feedback = service.recheck_feedback_with_quality(
            question,
            "не знаю",
            previous_feedback="Хорошо:\n- Отлично раскрыл retries.",
        )

        self.assertEqual(len(llm.prompts), 1)
        self.assertIn("<previous_feedback>\nХорошо:\n- Отлично раскрыл retries.", llm.prompts[0])
        self.assertIn("Единственный источник фактов о кандидате", llm.prompts[0])
        self.assertEqual(feedback.quality.flags, ())

    def test_feedback_service_marks_good_section_without_candidate_evidence_as_suspicious(self) -> None:
        question = Question(
            id=1,
            topic_id=1,
            difficulty="senior",
            prompt="Как оценить ответ про database indexes?",
            hint="",
            reference_answer=(
                "Сильный ответ объясняет B-tree, selectivity, write amplification, "
                "covering indexes и query plans."
            ),
            source="test",
        )
        suspicious_response = (
            "Понял твой ответ:\n"
            "- Кандидат ответил коротко.\n\n"
            "Хорошо:\n"
            "- Хорошо раскрыты B-tree, selectivity и write amplification.\n\n"
            "Упущено:\n"
            "- Нужно добавить детали.\n\n"
            "Повторить:\n"
            "- Индексы."
        )
        suspicious_service = SessionService(make_repository(), RecordingLLM(suspicious_response))

        suspicious_feedback = suspicious_service.feedback_with_quality(question, "не знаю")

        self.assertEqual(suspicious_feedback.text, suspicious_response)
        self.assertTrue(suspicious_feedback.quality.suspicious)
        self.assertIn(FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG, suspicious_feedback.quality.flags)

        grounded_response = (
            "Понял твой ответ:\n"
            "- Кандидат связал индексы с чтением и записью.\n\n"
            "Хорошо:\n"
            "- Ты отметил, что индексы ускоряют чтение и замедляют запись.\n\n"
            "Упущено:\n"
            "- Добавь selectivity и query plan.\n\n"
            "Повторить:\n"
            "- B-tree."
        )
        grounded_service = SessionService(make_repository(), RecordingLLM(grounded_response))

        grounded_feedback = grounded_service.feedback_with_quality(
            question,
            "Индексы ускоряют чтение, но замедляют запись.",
        )

        self.assertFalse(grounded_feedback.quality.suspicious)
        self.assertIn("индексы", grounded_feedback.quality.evidence_terms)

    def test_feedback_quality_flags_are_saved_in_latest_evaluation_payload(self) -> None:
        repository = make_repository()
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
                user_answer="не знаю",
                self_score=1,
                ai_feedback="Старый feedback text.",
                answered_at=datetime(2026, 5, 19, 9, 10, 0),
            )
        )
        EvaluationService(repository).evaluate_and_store_answer(answer, question, use_llm=False)
        suspicious_response = (
            "Понял твой ответ:\n"
            "- Кандидат ответил коротко.\n\n"
            "Хорошо:\n"
            "- Хорошо раскрыты tradeoffs, failure modes и observability.\n\n"
            "Упущено:\n"
            "- Нужно добавить детали.\n\n"
            "Повторить:\n"
            "- Production readiness."
        )
        service = SessionService(repository, RecordingLLM(suspicious_response))

        updated = service.add_feedback_to_answer(answer, question, answer.user_answer)

        self.assertEqual(updated.ai_feedback, suspicious_response)
        feedback_row = repository.connection.execute(
            "SELECT ai_feedback FROM answers WHERE id = ?",
            (answer.id,),
        ).fetchone()
        self.assertEqual(feedback_row["ai_feedback"], suspicious_response)

        evaluations = repository.list_answer_evaluations_for_answer(answer.id or 0)
        self.assertEqual(len(evaluations), 1)
        payload = json.loads(evaluations[0].raw_payload_json or "{}")
        self.assertEqual(payload["feedback_quality_flags"], [FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG])
        self.assertTrue(payload["feedback_quality"]["suspicious"])
        self.assertFalse(payload["feedback_quality"]["fallback"])

    def test_short_unknown_answer_stays_low_and_reference_only_praise_is_suspicious(self) -> None:
        repository = make_repository()
        question = Question(
            id=1,
            topic_id=1,
            difficulty="senior",
            prompt="Как сделать retries безопасными в распределенном сервисе?",
            hint="",
            reference_answer=(
                "Сильный ответ фиксирует idempotency key, exponential backoff с jitter, "
                "retry budget, DLQ для poison messages и observability."
            ),
            source="feedback-eval",
        )
        user_answer = "не знаю"
        evaluation = EvaluationService(repository).evaluate_answer(
            question,
            user_answer=user_answer,
            reference_answer=question.reference_answer,
        )

        self.assertLessEqual(max(score.score for score in evaluation.scores), 2)
        self.assertTrue(
            all("нет достаточного" in score.evidence for score in evaluation.scores),
            [score.evidence for score in evaluation.scores],
        )
        self.assertIn("слабый", evaluation.summary)

        reference_only_praise = (
            "Понял твой ответ:\n"
            "- Кандидат ответил, что не знает.\n\n"
            "Хорошо:\n"
            "- Хорошо раскрыты idempotency key, backoff с jitter, DLQ и observability.\n\n"
            "Упущено:\n"
            "- Нужно добавить детали безопасных retries.\n\n"
            "Повторить:\n"
            "- Reliable retries."
        )
        feedback = SessionService(repository, RecordingLLM(reference_only_praise)).feedback_with_quality(
            question,
            user_answer,
        )

        self.assertTrue(feedback.quality.suspicious)
        self.assertIn(FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG, feedback.quality.flags)

    def test_feedback_eval_weak_answer_cases_cover_reference_only_claims(self) -> None:
        self.assertGreaterEqual(len(WEAK_FEEDBACK_EVAL_CASES), 3)

        for case in WEAK_FEEDBACK_EVAL_CASES:
            with self.subTest(case=case.name):
                question = Question(
                    id=1,
                    topic_id=1,
                    difficulty="senior",
                    prompt=case.question,
                    hint="",
                    reference_answer=case.reference_answer,
                    source="feedback-eval",
                )

                prompt = build_feedback_prompt(question, case.weak_answer)
                candidate_block = prompt.split("<candidate_answer>\n", 1)[1].split(
                    "\n</candidate_answer>",
                    1,
                )[0]
                reference_block = prompt.split("<reference_answer>\n", 1)[1].split(
                    "\n</reference_answer>",
                    1,
                )[0]

                self.assertEqual(candidate_block, case.weak_answer)
                self.assertEqual(reference_block, case.reference_answer)
                self.assertTrue(case.reference_only_claims)
                for claim in case.reference_only_claims:
                    self.assertIn(claim, reference_block)
                    self.assertNotIn(claim.lower(), candidate_block.lower())

    def test_learning_prompt_is_not_interview_evaluation(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("python-runtime")
        question = repository.list_questions(topic.id)[0]

        prompt = build_learning_prompt("Не понимаю data descriptor", topic, question)

        self.assertIn("Помоги разобраться в теме, а не проводи интервью", prompt)
        self.assertIn("Не оценивай пользователя", prompt)
        self.assertIn("<user_message>\nНе понимаю data descriptor\n</user_message>", prompt)

    def test_repository_persists_learning_dialog_messages_by_topic(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("python-runtime")
        other_topic = repository.find_topic_by_slug("async-backend")
        now = datetime(2026, 5, 12, 10, 0, 0)

        repository.add_learning_dialog_message(
            LearningDialogMessage(
                id=None,
                topic_id=topic.id,
                role="user",
                content="Не понимаю descriptor protocol.",
                created_at=now,
            )
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(
                id=None,
                topic_id=topic.id,
                role="assistant",
                content="Начни с __get__, __set__ и lookup order.",
                created_at=now + timedelta(seconds=1),
            )
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(
                id=None,
                topic_id=other_topic.id,
                role="user",
                content="Как работает backpressure?",
                created_at=now + timedelta(seconds=2),
            )
        )

        messages = repository.list_learning_dialog_messages(topic.id)

        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertEqual(messages[0].content, "Не понимаю descriptor protocol.")
        self.assertEqual(messages[1].content, "Начни с __get__, __set__ и lookup order.")

    def test_repository_lists_recent_learning_dialog_messages_in_reading_order(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("python-runtime")
        now = datetime(2026, 5, 12, 10, 0, 0)

        for index in range(3):
            repository.add_learning_dialog_message(
                LearningDialogMessage(
                    id=None,
                    topic_id=topic.id,
                    role="user" if index % 2 == 0 else "assistant",
                    content=f"message {index}",
                    created_at=now + timedelta(seconds=index),
                )
            )

        messages = repository.list_learning_dialog_messages(topic.id, limit=2)

        self.assertEqual([message.content for message in messages], ["message 1", "message 2"])

    def test_learning_service_saves_user_and_assistant_messages(self) -> None:
        repository = make_repository()
        service = LearningService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")
        question = repository.list_questions(topic.id)[0]

        explanation = service.explain_and_save(
            topic.id,
            "  Не понимаю descriptor lookup.  ",
            topic=topic,
            question=question,
        )
        messages = repository.list_learning_dialog_messages(topic.id)

        self.assertIn("Хорошо", explanation)
        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertEqual(messages[0].content, "Не понимаю descriptor lookup.")
        self.assertEqual(messages[1].content, explanation)

        notebook_entries = repository.list_notebook_entries(topic_id=topic.id)
        self.assertEqual(len(notebook_entries), 1)
        self.assertEqual(notebook_entries[0].title, "Не понимаю descriptor lookup.")
        self.assertEqual(notebook_entries[0].body, explanation)
        self.assertEqual(notebook_entries[0].source, "learning-ai")
        self.assertEqual(notebook_entries[0].source_message_id, messages[1].id)

    def test_learning_service_saves_dialog_session_context_metadata(self) -> None:
        repository = make_repository()
        service = LearningService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")

        service.add_dialog_message(
            topic.id,
            "user",
            "Разбери descriptor lookup.",
            dialog_session_id="learn-session-1",
            context_type="practice_session",
            context_id="42",
        )

        messages = repository.list_learning_dialog_messages(topic.id)

        self.assertEqual(messages[0].dialog_session_id, "learn-session-1")
        self.assertEqual(messages[0].context_type, "practice_session")
        self.assertEqual(messages[0].context_id, "42")

    def test_learning_service_lists_recent_dialog_messages(self) -> None:
        repository = make_repository()
        service = LearningService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")

        service.add_dialog_message(topic.id, "user", "Первый вопрос.")
        service.add_dialog_message(topic.id, "assistant", "Первый ответ.")
        service.add_dialog_message(topic.id, "user", "Второй вопрос.")

        messages = service.list_dialog_messages(topic.id, limit=2)

        self.assertEqual([message.role for message in messages], ["assistant", "user"])
        self.assertEqual([message.content for message in messages], ["Первый ответ.", "Второй вопрос."])

    def test_learning_service_lists_dialog_summaries_by_topic_and_date(self) -> None:
        repository = make_repository()
        service = LearningService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")
        other_topic = repository.find_topic_by_slug("async-backend")
        first_day = datetime(2026, 5, 12, 10, 0, 0)
        second_day = datetime(2026, 5, 13, 9, 0, 0)

        repository.add_learning_dialog_message(
            LearningDialogMessage(None, topic.id, "user", "Первый вопрос.", first_day)
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(None, topic.id, "assistant", "Первый ответ.", first_day + timedelta(minutes=2))
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(None, other_topic.id, "user", "Свежий вопрос.", second_day)
        )

        summaries = service.list_dialog_summaries()

        self.assertEqual([(item.topic_id, item.dialog_date) for item in summaries], [(other_topic.id, "2026-05-13"), (topic.id, "2026-05-12")])
        self.assertEqual(summaries[0].topic_title, other_topic.title)
        self.assertEqual(summaries[0].message_count, 1)
        self.assertEqual(summaries[1].message_count, 2)
        self.assertEqual(summaries[1].first_message_at, first_day)
        self.assertEqual(summaries[1].last_message_at, first_day + timedelta(minutes=2))

    def test_learning_service_distinguishes_dialog_summaries_by_session_id(self) -> None:
        repository = make_repository()
        service = LearningService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")
        now = datetime(2026, 5, 13, 10, 0, 0)

        repository.add_learning_dialog_message(
            LearningDialogMessage(
                None,
                topic.id,
                "user",
                "Первый учебный вопрос.",
                now,
                dialog_session_id="learn-session-a",
                context_type="practice_session",
                context_id="1",
            )
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(
                None,
                topic.id,
                "assistant",
                "Первый ответ.",
                now + timedelta(minutes=1),
                dialog_session_id="learn-session-a",
                context_type="practice_session",
                context_id="1",
            )
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(
                None,
                topic.id,
                "user",
                "Второй учебный вопрос той же темы и даты.",
                now + timedelta(hours=2),
                dialog_session_id="learn-session-b",
                context_type="practice_session",
                context_id="2",
            )
        )

        summaries = service.list_dialog_summaries()
        second_session_messages = service.list_dialog_messages_for_session("learn-session-b")

        self.assertEqual([summary.dialog_session_id for summary in summaries], ["learn-session-b", "learn-session-a"])
        self.assertEqual([summary.message_count for summary in summaries], [1, 2])
        self.assertEqual(summaries[0].context_type, "practice_session")
        self.assertEqual(summaries[0].context_id, "2")
        self.assertEqual([message.content for message in second_session_messages], ["Второй учебный вопрос той же темы и даты."])

    def test_learning_service_lists_dialog_messages_for_selected_date(self) -> None:
        repository = make_repository()
        service = LearningService(repository, StaticLLM())
        topic = repository.find_topic_by_slug("python-runtime")
        other_topic = repository.find_topic_by_slug("async-backend")
        first_day = datetime(2026, 5, 12, 10, 0, 0)
        second_day = datetime(2026, 5, 13, 9, 0, 0)

        repository.add_learning_dialog_message(
            LearningDialogMessage(None, topic.id, "user", "Первый вопрос.", first_day)
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(None, topic.id, "assistant", "Первый ответ.", first_day + timedelta(minutes=2))
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(None, topic.id, "user", "Свежий вопрос той же темы.", second_day)
        )
        repository.add_learning_dialog_message(
            LearningDialogMessage(None, other_topic.id, "user", "Другой topic.", first_day)
        )

        messages = service.list_dialog_messages_for_date(topic.id, "2026-05-12")

        self.assertEqual([message.role for message in messages], ["user", "assistant"])
        self.assertEqual([message.content for message in messages], ["Первый вопрос.", "Первый ответ."])

    def test_curriculum_service_generates_and_saves_llm_seed_questions(self) -> None:
        repository = make_repository()
        service = CurriculumService(repository, StaticLLM())

        result = service.generate_and_save(topic_count=1, questions_per_topic=1)
        second_result = service.generate_and_save(topic_count=1, questions_per_topic=1)

        topic = repository.find_topic_by_slug("generated-observability")
        self.assertIsNotNone(topic)
        self.assertEqual(result.topics_saved, 1)
        self.assertEqual(result.questions_saved, 1)
        self.assertEqual(second_result.questions_saved, 0)
        questions = repository.list_questions(topic.id)
        self.assertEqual(len([question for question in questions if question.source == "llm-seed"]), 1)
        llm_seed_question = next(question for question in questions if question.source == "llm-seed")
        self.assertEqual(llm_seed_question.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_REVIEW)

    def test_curriculum_service_saves_generated_structure_from_seed(self) -> None:
        repository = make_repository()
        service = CurriculumService(repository, StaticLLM())

        result = service.generate_and_save(topic_count=1, questions_per_topic=1)

        topic = repository.find_topic_by_slug("generated-observability")
        curriculum_topics = repository.list_curriculum_topics(source="llm-seed", topic_id=topic.id)
        self.assertEqual(result.curriculum_topics_saved, 1)
        self.assertEqual(result.subtopics_saved, 1)
        self.assertEqual(result.objectives_saved, 4)
        self.assertEqual(len(curriculum_topics), 1)

        curriculum_topic = curriculum_topics[0]
        topic_objectives = repository.list_curriculum_objectives(curriculum_topic.id or 0)
        subtopics = repository.list_curriculum_subtopics(curriculum_topic.id or 0)
        self.assertEqual([objective.text for objective in topic_objectives], [
            "Строить telemetry plan",
            "Разбирать production incidents",
        ])
        self.assertEqual([subtopic.slug for subtopic in subtopics], ["metrics-and-traces"])

        subtopic_objectives = repository.list_curriculum_objectives(
            curriculum_topic.id or 0,
            subtopics[0].id,
        )
        self.assertEqual([objective.text for objective in subtopic_objectives], [
            "Выбирать symptoms metrics",
            "Связывать traces с user impact",
        ])

    def test_curriculum_service_does_not_duplicate_generated_structure(self) -> None:
        repository = make_repository()
        service = CurriculumService(repository, StaticLLM())

        first_result = service.generate_and_save(topic_count=1, questions_per_topic=1)
        second_result = service.generate_and_save(topic_count=1, questions_per_topic=1)

        topic = repository.find_topic_by_slug("generated-observability")
        curriculum_topics = repository.list_curriculum_topics(source="llm-seed", topic_id=topic.id)
        curriculum_topic = curriculum_topics[0]
        subtopics = repository.list_curriculum_subtopics(curriculum_topic.id or 0)
        topic_objectives = repository.list_curriculum_objectives(curriculum_topic.id or 0)
        subtopic_objectives = repository.list_curriculum_objectives(
            curriculum_topic.id or 0,
            subtopics[0].id,
        )

        self.assertEqual(first_result.curriculum_topics_saved, 1)
        self.assertEqual(first_result.subtopics_saved, 1)
        self.assertEqual(first_result.objectives_saved, 4)
        self.assertEqual(second_result.curriculum_topics_saved, 0)
        self.assertEqual(second_result.subtopics_saved, 0)
        self.assertEqual(second_result.objectives_saved, 0)
        self.assertEqual(len(curriculum_topics), 1)
        self.assertEqual(len(subtopics), 1)
        self.assertEqual(len(topic_objectives), 2)
        self.assertEqual(len(subtopic_objectives), 2)

    def test_curriculum_service_status_reports_counts_and_empty_zones(self) -> None:
        repository = make_repository()
        service = CurriculumService(repository, StaticLLM())

        empty_status = service.status()
        self.assertEqual(empty_status.curriculum_topic_count, 0)
        self.assertIn("bootstrap/fallback", empty_status.empty_zones[0])

        service.generate_and_save(topic_count=1, questions_per_topic=1)

        status = service.status()
        self.assertEqual(status.curriculum_topic_count, 1)
        self.assertEqual(status.subtopic_count, 1)
        self.assertEqual(status.objective_count, 4)
        self.assertEqual(status.question_count, 1)
        self.assertEqual(status.empty_zones, ())
        self.assertEqual(status.topics[0].curriculum_topic.slug, "generated-observability")

    def test_curriculum_service_suggests_first_unvisited_topic_by_curriculum_order(self) -> None:
        repository = make_repository()
        service = CurriculumService(repository, StaticLLM())
        python_topic = repository.find_topic_by_slug("python-runtime")
        async_topic = repository.find_topic_by_slug("async-backend")
        db_topic = repository.find_topic_by_slug("databases")
        self.assertIsNotNone(python_topic)
        self.assertIsNotNone(async_topic)
        self.assertIsNotNone(db_topic)
        repository.add_curriculum_topic(
            CurriculumTopic(
                id=None,
                topic_id=python_topic.id,
                slug="python-runtime",
                title="Python runtime",
                description="Runtime internals.",
                level="middle+",
                source="llm-seed",
                order_index=1,
            )
        )
        repository.add_curriculum_topic(
            CurriculumTopic(
                id=None,
                topic_id=async_topic.id,
                slug="async-backend",
                title="Async backend",
                description="Async backend.",
                level="middle+",
                source="llm-seed",
                order_index=2,
            )
        )
        repository.add_curriculum_topic(
            CurriculumTopic(
                id=None,
                topic_id=db_topic.id,
                slug="databases",
                title="Databases",
                description="DB internals.",
                level="middle+",
                source="llm-seed",
                order_index=3,
            )
        )
        self._save_answer(repository, python_topic.id or 0, 5, datetime(2026, 5, 10, 10, 0, 0))

        recommendation = service.suggest_next_topic()

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.topic.id, async_topic.id)
        self.assertEqual(recommendation.answers, 0)
        self.assertIn("curriculum order", recommendation.reason)

    def test_curriculum_service_suggests_weak_topic_before_stale_strong_topic(self) -> None:
        repository = make_repository()
        service = CurriculumService(repository, StaticLLM())
        python_topic = repository.find_topic_by_slug("python-runtime")
        async_topic = repository.find_topic_by_slug("async-backend")
        self.assertIsNotNone(python_topic)
        self.assertIsNotNone(async_topic)
        for order_index, topic in enumerate([python_topic, async_topic], start=1):
            repository.add_curriculum_topic(
                CurriculumTopic(
                    id=None,
                    topic_id=topic.id,
                    slug=f"{topic.slug}-curriculum",
                    title=topic.title,
                    description=topic.description,
                    level=topic.level,
                    source="llm-seed",
                    order_index=order_index,
                )
            )
        self._save_answer(repository, python_topic.id or 0, 5, datetime(2026, 5, 1, 10, 0, 0))
        self._save_answer(repository, async_topic.id or 0, 2, datetime(2026, 5, 12, 10, 0, 0))

        recommendation = service.suggest_next_topic()

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.topic.id, async_topic.id)
        self.assertEqual(recommendation.avg_self_score, 2.0)
        self.assertIn("self-score", recommendation.reason)

    def test_curriculum_service_suggests_stalest_topic_when_scores_are_strong(self) -> None:
        repository = make_repository()
        service = CurriculumService(repository, StaticLLM())
        python_topic = repository.find_topic_by_slug("python-runtime")
        async_topic = repository.find_topic_by_slug("async-backend")
        self.assertIsNotNone(python_topic)
        self.assertIsNotNone(async_topic)
        for order_index, topic in enumerate([python_topic, async_topic], start=1):
            repository.add_curriculum_topic(
                CurriculumTopic(
                    id=None,
                    topic_id=topic.id,
                    slug=f"{topic.slug}-curriculum",
                    title=topic.title,
                    description=topic.description,
                    level=topic.level,
                    source="llm-seed",
                    order_index=order_index,
                )
            )
        self._save_answer(repository, python_topic.id or 0, 5, datetime(2026, 5, 1, 10, 0, 0))
        self._save_answer(repository, async_topic.id or 0, 4, datetime(2026, 5, 12, 10, 0, 0))

        recommendation = service.suggest_next_topic()

        self.assertIsNotNone(recommendation)
        self.assertEqual(recommendation.topic.id, python_topic.id)
        self.assertEqual(recommendation.last_answered_at, datetime(2026, 5, 1, 10, 0, 0))
        self.assertIn("давно", recommendation.reason)

    def test_repository_persists_curriculum_structure_over_topics(self) -> None:
        repository = make_repository()
        topic = repository.find_topic_by_slug("python-runtime")
        other_topic = repository.find_topic_by_slug("async-backend")

        saved_topic = repository.add_curriculum_topic(
            CurriculumTopic(
                id=None,
                topic_id=topic.id,
                slug="python-runtime-deep-dive",
                title="Python runtime deep dive",
                description="Runtime internals for production backend work.",
                level="senior",
                source="llm-seed",
                order_index=2,
            )
        )
        repository.add_curriculum_topic(
            CurriculumTopic(
                id=None,
                topic_id=other_topic.id,
                slug="async-backend-deep-dive",
                title="Async backend deep dive",
                description="Async production behavior.",
                level="senior",
                source="manual",
                order_index=1,
            )
        )
        subtopic = repository.add_curriculum_subtopic(
            CurriculumSubtopic(
                id=None,
                curriculum_topic_id=saved_topic.id or 0,
                slug="descriptors",
                title="Descriptors",
                description="Descriptor protocol and lookup order.",
                source="llm-seed",
                order_index=1,
            )
        )
        topic_objective = repository.add_curriculum_objective(
            CurriculumObjective(
                id=None,
                curriculum_topic_id=saved_topic.id or 0,
                curriculum_subtopic_id=None,
                text="Связывать Python internals с production debugging.",
                source="llm-seed",
                order_index=1,
            )
        )
        subtopic_objective = repository.add_curriculum_objective(
            CurriculumObjective(
                id=None,
                curriculum_topic_id=saved_topic.id or 0,
                curriculum_subtopic_id=subtopic.id,
                text="Объяснять descriptor lookup order.",
                source="llm-seed",
                order_index=1,
            )
        )

        llm_topics = repository.list_curriculum_topics(source="llm-seed")
        topic_subtopics = repository.list_curriculum_subtopics(saved_topic.id or 0)
        topic_objectives = repository.list_curriculum_objectives(saved_topic.id or 0)
        subtopic_objectives = repository.list_curriculum_objectives(saved_topic.id or 0, subtopic.id)

        self.assertEqual([curriculum_topic.id for curriculum_topic in llm_topics], [saved_topic.id])
        self.assertEqual(llm_topics[0].topic_id, topic.id)
        self.assertEqual([item.id for item in topic_subtopics], [subtopic.id])
        self.assertEqual([item.id for item in topic_objectives], [topic_objective.id])
        self.assertEqual([item.id for item in subtopic_objectives], [subtopic_objective.id])
        self.assertEqual(subtopic_objectives[0].text, "Объяснять descriptor lookup order.")

    def test_parse_curriculum_falls_back_on_invalid_json(self) -> None:
        curriculum = parse_curriculum("not json", topic_count=2, questions_per_topic=2)

        self.assertEqual(len(curriculum.topics), 2)
        self.assertEqual(len(curriculum.topics[0].questions), 2)

    def test_background_question_prompt_requests_tags_and_known_competencies(self) -> None:
        prompt = build_background_question_prompt(
            "Async backend и concurrency",
            "asyncio, cancellation, backpressure, workers, reliability patterns.",
            "Сгенерируй вопрос про backpressure",
            ["async-concurrency", "observability", "distributed-systems"],
        )

        self.assertIn("tag_slugs", prompt)
        self.assertIn("competency_slugs", prompt)
        self.assertIn("kebab-case English tags", prompt)
        self.assertIn("async-concurrency, observability, distributed-systems", prompt)
        self.assertIn("ordered from primary to secondary", prompt)

    def test_content_generation_queue_creates_background_question(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("async-backend").id

        job = service.enqueue_question(topic_id, "Сгенерируй вопрос про backpressure")
        queued_jobs = service.list_jobs(status="queued")
        result = service.process_next_job()

        self.assertEqual(job.status, "queued")
        self.assertEqual(len(queued_jobs), 1)
        self.assertIsNotNone(result)
        self.assertEqual(result.job.status, "done")
        self.assertIsNotNone(result.created_question)
        self.assertEqual(result.created_question.source, "background-llm")
        self.assertEqual(result.created_question.source_quality_status, QUESTION_SOURCE_QUALITY_PENDING_REVIEW)
        self.assertIn("async production incident", result.created_question.prompt)
        self.assertEqual(result.artifact["source_quality_status"], QUESTION_SOURCE_QUALITY_PENDING_REVIEW)
        self.assertEqual(service.list_jobs(status="queued"), [])

    def test_content_generation_links_llm_tags_and_competencies_to_generated_question(self) -> None:
        repository = make_repository()
        llm = RecordingLLM(
            """
            {
                "difficulty": "senior",
                "prompt": "Как настроить bounded concurrency для async worker?",
                "hint": "Покрой queue pressure, semaphores, cancellation и telemetry.",
                "reference_answer": "Нужно ограничить параллелизм, измерять queue lag, корректно обрабатывать cancellation и держать rollback plan.",
                "tag_slugs": ["asyncio", "backpressure", "asyncio"],
                "competency_slugs": ["async-concurrency", "observability", "unknown-competency"]
            }
            """
        )
        service = ContentGenerationService(repository, llm)
        topic_id = repository.find_topic_by_slug("async-backend").id

        service.enqueue_question(topic_id, "Сгенерируй вопрос про bounded concurrency")
        result = service.process_next_job()

        self.assertIsNotNone(result)
        assert result is not None
        self.assertIsNotNone(result.created_question)
        question = result.created_question
        assert question is not None
        tags = repository.list_question_tags(question.id or 0)
        competencies = repository.list_question_competencies(question.id or 0)

        self.assertEqual([tag.slug for tag in tags], ["asyncio", "backpressure"])
        self.assertEqual([tag.source for tag in tags], ["background-llm", "background-llm"])
        self.assertEqual(
            [link.competency.slug for link in competencies],
            ["async-concurrency", "observability"],
        )
        self.assertEqual([link.is_primary for link in competencies], [True, False])
        self.assertEqual(result.artifact["tag_slugs"], ["asyncio", "backpressure"])
        self.assertEqual(
            result.artifact["competency_slugs"],
            ["async-concurrency", "observability"],
        )
        self.assertIn("tag_slugs", llm.prompts[0])
        self.assertIn("async-concurrency", llm.prompts[0])

    def test_content_generation_skips_similar_question_in_same_topic(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("async-backend").id
        existing = repository.add_question(
            Question(
                id=None,
                topic_id=topic_id,
                difficulty="senior",
                prompt="Как расследовать async production incident в backend-сервисе?",
                hint="Сфокусируйся на telemetry и mitigation.",
                reference_answer="Нужно начать с impact, telemetry, mitigation и regression coverage.",
                source="manual",
            )
        )

        before_topic_count = len(repository.list_questions(topic_id))
        before_total_count = len(repository.list_questions())
        job = service.enqueue_question(topic_id, "Сгенерируй похожий вопрос про incident")
        result = service.process_next_job()
        saved_job = repository.get_content_generation_job(job.id or 0)
        self.assertIsNotNone(saved_job)
        artifact = json.loads(saved_job.result_json or "{}")

        self.assertIsNotNone(result)
        self.assertEqual(result.job.status, "done")
        self.assertIsNotNone(result.created_question)
        self.assertEqual(result.created_question.id, existing.id)
        self.assertEqual(len(repository.list_questions(topic_id)), before_topic_count)
        self.assertEqual(len(repository.list_questions()), before_total_count)
        self.assertEqual(artifact["question_id"], existing.id)

    def test_content_generation_job_payload_has_retry_metadata(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("async-backend").id

        job = service.enqueue_question(topic_id, "Сгенерируй вопрос про backpressure")

        payload = json.loads(job.payload_json)
        self.assertEqual(payload["topic_id"], topic_id)
        self.assertEqual(payload["note"], "Сгенерируй вопрос про backpressure")
        self.assertEqual(
            payload["retry"],
            {
                "attempt": 0,
                "max_attempts": 3,
                "backoff_seconds": 60,
                "next_attempt_at": None,
                "last_error": None,
            },
        )

    def test_content_generation_failure_records_retry_backoff_metadata(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, BrokenLLM())
        topic_id = repository.find_topic_by_slug("async-backend").id
        job = service.enqueue_question(topic_id, "will fail")
        before = datetime.now()

        result = service.process_next_job()
        failed = repository.get_content_generation_job(job.id or 0)

        self.assertIsNotNone(result)
        self.assertEqual(result.job.status, "failed")
        self.assertIsNotNone(failed)
        payload = json.loads(failed.payload_json)
        retry = payload["retry"]
        self.assertEqual(retry["attempt"], 1)
        self.assertEqual(retry["max_attempts"], 3)
        self.assertEqual(retry["backoff_seconds"], 60)
        self.assertEqual(retry["last_error"], "test generation failed")
        self.assertGreaterEqual(datetime.fromisoformat(retry["next_attempt_at"]), before + timedelta(seconds=55))
        self.assertLessEqual(datetime.fromisoformat(retry["next_attempt_at"]), datetime.now() + timedelta(seconds=65))

    def test_content_generation_worker_skips_jobs_until_backoff_expires(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        delayed_topic_id = repository.find_topic_by_slug("async-backend").id
        ready_topic_id = repository.find_topic_by_slug("python-runtime").id

        delayed_job = service.enqueue_question(delayed_topic_id, "delayed by backoff")
        ready_job = service.enqueue_question(ready_topic_id, "ready now")
        delayed_payload = json.loads(delayed_job.payload_json)
        delayed_payload["retry"]["attempt"] = 1
        delayed_payload["retry"]["next_attempt_at"] = (datetime.now() + timedelta(minutes=5)).isoformat(
            timespec="seconds"
        )
        repository.update_content_generation_job_payload(
            delayed_job.id or 0,
            json.dumps(delayed_payload, ensure_ascii=False),
        )

        first_result = service.process_next_job()
        delayed_after_skip = repository.get_content_generation_job(delayed_job.id or 0)

        self.assertIsNotNone(first_result)
        self.assertEqual(first_result.job.id, ready_job.id)
        self.assertEqual(first_result.job.status, "done")
        self.assertIsNotNone(delayed_after_skip)
        self.assertEqual(delayed_after_skip.status, "queued")

        delayed_payload["retry"]["next_attempt_at"] = (datetime.now() - timedelta(seconds=1)).isoformat(
            timespec="seconds"
        )
        repository.update_content_generation_job_payload(
            delayed_job.id or 0,
            json.dumps(delayed_payload, ensure_ascii=False),
        )
        second_result = service.process_next_job()

        self.assertIsNotNone(second_result)
        self.assertEqual(second_result.job.id, delayed_job.id)
        self.assertEqual(second_result.job.status, "done")

    def test_content_generation_limits_active_jobs_by_topic_and_kind(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("async-backend").id
        other_topic_id = repository.find_topic_by_slug("python-runtime").id

        first_job = service.enqueue_question(topic_id, "auto")
        learning_job = service.enqueue_learning_material(topic_id, "auto")
        other_topic_job = service.enqueue_question(other_topic_id, "auto")

        with self.assertRaisesRegex(ValueError, "Active generation job limit reached"):
            service.enqueue_question(topic_id, "duplicate")

        repository.update_content_generation_job(first_job.id or 0, "running")
        with self.assertRaisesRegex(ValueError, "Active generation job limit reached"):
            service.enqueue_question(topic_id, "duplicate running")

        repository.update_content_generation_job(first_job.id or 0, "done")
        next_question_job = service.enqueue_question(topic_id, "after done")

        self.assertEqual(learning_job.kind, "learning-material")
        self.assertEqual(other_topic_job.kind, "question")
        self.assertEqual(next_question_job.kind, "question")

    def test_content_generation_regenerates_reference_answers_for_topic_questions(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("async-backend").id
        question_before = repository.list_questions(topic_id)[0]

        job = service.enqueue_reference_answer_regeneration(topic_id, "Освежи senior эталон")
        result = service.process_next_job()
        question_after = repository.get_question(question_before.id or 0)

        self.assertEqual(job.kind, "reference-answer")
        self.assertIsNotNone(result)
        self.assertEqual(result.job.status, "done")
        self.assertIsNone(result.created_question)
        self.assertIsNotNone(result.artifact)
        self.assertEqual(result.artifact["kind"], "reference-answer")
        self.assertEqual(result.artifact["updated_count"], 1)
        self.assertEqual(result.artifact["question_ids"], [question_before.id])
        self.assertIsNotNone(question_after)
        self.assertNotEqual(question_after.reference_answer, question_before.reference_answer)
        self.assertIn("Обновленный эталон", question_after.reference_answer)

    def test_content_generation_worker_processes_curriculum_job(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())

        job = service.enqueue_curriculum(
            "Подготовь starter pack из TUI.",
            topic_count=1,
            questions_per_topic=1,
        )
        result = service.process_next_job()
        status = CurriculumService(repository, StaticLLM()).status()

        self.assertEqual(job.kind, JOB_KIND_CURRICULUM)
        self.assertIsNotNone(result)
        self.assertEqual(result.job.status, "done")
        self.assertIsNone(result.created_question)
        self.assertIsNotNone(result.artifact)
        self.assertEqual(result.artifact["kind"], JOB_KIND_CURRICULUM)
        self.assertEqual(result.artifact["topic_count"], 1)
        self.assertEqual(result.artifact["curriculum_topics_saved"], 1)
        self.assertEqual(result.artifact["subtopics_saved"], 1)
        self.assertEqual(result.artifact["objectives_saved"], 4)
        self.assertEqual(result.artifact["questions_saved"], 1)
        self.assertEqual(result.artifact["topic_slugs"], ["generated-observability"])
        self.assertEqual(status.curriculum_topic_count, 1)
        self.assertEqual(status.question_count, 1)

    def test_content_generation_retry_respects_active_job_limit(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("async-backend").id

        failed_job = service.enqueue_question(topic_id, "failed")
        repository.update_content_generation_job(failed_job.id or 0, "failed")
        active_job = service.enqueue_question(topic_id, "active")

        with self.assertRaisesRegex(ValueError, "Active generation job limit reached"):
            service.retry_job(failed_job.id or 0)

        retried = repository.get_content_generation_job(failed_job.id or 0)
        self.assertIsNotNone(retried)
        self.assertEqual(retried.status, "failed")
        self.assertEqual(active_job.status, "queued")

    def test_content_generation_creates_learning_material_artifact(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("python-runtime").id

        job = service.enqueue_learning_material(topic_id, "Разъясни descriptors перед практикой")
        result = service.process_next_job()

        self.assertEqual(job.kind, "learning-material")
        self.assertIsNotNone(result)
        self.assertEqual(result.job.status, "done")
        self.assertIsNone(result.created_question)
        self.assertIsNotNone(result.artifact)
        self.assertEqual(result.artifact["kind"], "learning-material")
        self.assertIsNotNone(result.artifact["material_id"])
        self.assertIn("Учебный материал", result.artifact["material"])
        saved = repository.latest_learning_material(topic_id)
        self.assertIsNotNone(saved)
        self.assertIn("Учебный материал", saved.body)

    def test_repository_archives_learning_materials_without_deleting_rows(self) -> None:
        repository = make_repository()
        topic_id = repository.find_topic_by_slug("python-runtime").id
        older = repository.add_learning_material(
            LearningMaterial(
                id=None,
                topic_id=topic_id,
                title="Older material",
                body="Полезный материал.",
                source="test",
                created_at=datetime(2026, 5, 12, 10, 0, 0),
            )
        )
        newer = repository.add_learning_material(
            LearningMaterial(
                id=None,
                topic_id=topic_id,
                title="Bad material",
                body="Неудачный материал.",
                source="test",
                created_at=datetime(2026, 5, 12, 11, 0, 0),
            )
        )

        archived = repository.archive_learning_material(newer.id or 0, reason="Слишком общий материал")

        self.assertTrue(archived)
        self.assertEqual(repository.latest_learning_material(topic_id).id, older.id)
        self.assertEqual([material.id for material in repository.list_learning_materials(topic_id)], [older.id])
        self.assertIsNone(repository.get_learning_material(newer.id or 0))
        archived_row = repository.get_learning_material(newer.id or 0, include_archived=True)
        self.assertIsNotNone(archived_row)
        self.assertIsNotNone(archived_row.archived_at)
        self.assertEqual(archived_row.archive_reason, "Слишком общий материал")

    def test_content_generation_creates_system_design_scenario_artifact(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("system-design").id

        service.enqueue_system_design_scenario(topic_id, "Сценарий про notifications")
        result = service.process_next_job()

        self.assertIsNotNone(result)
        self.assertEqual(result.job.status, "done")
        self.assertIsNone(result.created_question)
        self.assertIsNotNone(result.artifact)
        self.assertEqual(result.artifact["kind"], "system-design-scenario")
        self.assertIsNotNone(result.artifact["scenario_id"])
        self.assertIn("real-time notifications", result.artifact["scenario"])
        self.assertIn("observability", result.artifact["focus_areas"])
        saved = repository.latest_system_design_scenario(topic_id)
        self.assertIsNotNone(saved)
        self.assertIn("real-time notifications", saved.scenario)
        self.assertIn("observability", saved.focus_areas)

    def test_repository_archives_system_design_scenarios_without_deleting_rows(self) -> None:
        repository = make_repository()
        topic_id = repository.find_topic_by_slug("system-design").id
        older = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Older scenario",
                scenario="Спроектируй сервис коротких ссылок.",
                focus_areas=["api"],
                source="test",
                created_at=datetime(2026, 5, 12, 10, 0, 0),
            )
        )
        newer = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Bad scenario",
                scenario="Неудачный scenario.",
                focus_areas=["unclear"],
                source="test",
                created_at=datetime(2026, 5, 12, 11, 0, 0),
            )
        )

        archived = repository.archive_system_design_scenario(newer.id or 0, reason="Нет capacity planning")

        self.assertTrue(archived)
        self.assertEqual(repository.latest_system_design_scenario(topic_id).id, older.id)
        self.assertEqual([scenario.id for scenario in repository.list_system_design_scenarios(topic_id)], [older.id])
        self.assertIsNone(repository.get_system_design_scenario(newer.id or 0))
        archived_row = repository.get_system_design_scenario(newer.id or 0, include_archived=True)
        self.assertIsNotNone(archived_row)
        self.assertIsNotNone(archived_row.archived_at)
        self.assertEqual(archived_row.archive_reason, "Нет capacity planning")

    def test_repository_persists_system_design_transcript_by_topic_and_scenario(self) -> None:
        repository = make_repository()
        topic_id = repository.find_topic_by_slug("system-design").id
        other_topic_id = repository.find_topic_by_slug("async-backend").id
        now = datetime(2026, 5, 12, 10, 0, 0)
        scenario = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Notifications",
                scenario="Спроектируй сервис уведомлений.",
                focus_areas=["api", "queues"],
                source="test",
                created_at=now,
            )
        )
        other_scenario = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Billing",
                scenario="Спроектируй billing service.",
                focus_areas=["data"],
                source="test",
                created_at=now,
            )
        )

        repository.add_system_design_transcript_message(
            SystemDesignTranscriptMessage(
                id=None,
                topic_id=topic_id,
                scenario_id=scenario.id,
                role="candidate",
                content="Начну с требований.",
                created_at=now + timedelta(seconds=1),
            )
        )
        repository.add_system_design_transcript_message(
            SystemDesignTranscriptMessage(
                id=None,
                topic_id=topic_id,
                scenario_id=scenario.id,
                role="interviewer",
                content="Какие API нужны?",
                created_at=now + timedelta(seconds=2),
            )
        )
        repository.add_system_design_transcript_message(
            SystemDesignTranscriptMessage(
                id=None,
                topic_id=topic_id,
                scenario_id=other_scenario.id,
                role="candidate",
                content="Billing transcript.",
                created_at=now + timedelta(seconds=3),
            )
        )
        repository.add_system_design_transcript_message(
            SystemDesignTranscriptMessage(
                id=None,
                topic_id=other_topic_id,
                scenario_id=None,
                role="candidate",
                content="Unrelated custom scenario transcript.",
                created_at=now + timedelta(seconds=4),
            )
        )

        messages = repository.list_system_design_transcript_messages(topic_id, scenario_id=scenario.id)

        self.assertEqual([message.role for message in messages], ["candidate", "interviewer"])
        self.assertEqual([message.content for message in messages], ["Начну с требований.", "Какие API нужны?"])
        self.assertEqual([message.scenario_id for message in messages], [scenario.id, scenario.id])

    def test_system_design_service_saves_transcript_turn(self) -> None:
        repository = make_repository()
        service = SystemDesignService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("system-design").id
        scenario = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Notifications",
                scenario="Спроектируй сервис уведомлений.",
                focus_areas=["api", "queues"],
                source="test",
                created_at=datetime(2026, 5, 12, 10, 0, 0),
            )
        )

        service.save_transcript_turn(
            topic_id,
            "Начну с требований и API.",
            "Какие SLO и rate limits нужны?",
            scenario_id=scenario.id,
        )

        messages = service.list_transcript_messages(topic_id, scenario_id=scenario.id)
        self.assertEqual([message.role for message in messages], ["candidate", "interviewer"])
        self.assertEqual(
            [message.content for message in messages],
            ["Начну с требований и API.", "Какие SLO и rate limits нужны?"],
        )

    def test_repository_persists_system_design_artifacts_by_section(self) -> None:
        repository = make_repository()
        topic_id = repository.find_topic_by_slug("system-design").id
        now = datetime(2026, 5, 12, 10, 0, 0)
        scenario = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Notifications",
                scenario="Спроектируй сервис уведомлений.",
                focus_areas=["requirements", "risks"],
                source="test",
                created_at=now,
            )
        )

        repository.add_system_design_artifact(
            SystemDesignArtifact(
                id=None,
                topic_id=topic_id,
                scenario_id=scenario.id,
                section="requirements",
                content="Нужны transactional и marketing уведомления.",
                created_at=now + timedelta(seconds=1),
            )
        )
        repository.add_system_design_artifact(
            SystemDesignArtifact(
                id=None,
                topic_id=topic_id,
                scenario_id=scenario.id,
                section="risks",
                content="Provider outage и дубли доставки.",
                created_at=now + timedelta(seconds=2),
            )
        )
        repository.add_system_design_artifact(
            SystemDesignArtifact(
                id=None,
                topic_id=topic_id,
                scenario_id=None,
                section="requirements",
                content="Custom scenario requirement.",
                created_at=now + timedelta(seconds=3),
            )
        )

        artifacts = repository.list_system_design_artifacts(topic_id, scenario_id=scenario.id)
        requirements = repository.list_system_design_artifacts(
            topic_id,
            scenario_id=scenario.id,
            section="requirements",
        )
        custom_artifacts = repository.list_system_design_artifacts(topic_id)

        self.assertEqual([artifact.section for artifact in artifacts], ["requirements", "risks"])
        self.assertEqual([artifact.content for artifact in requirements], ["Нужны transactional и marketing уведомления."])
        self.assertEqual([artifact.content for artifact in custom_artifacts], ["Custom scenario requirement."])

    def test_system_design_service_saves_and_lists_artifacts(self) -> None:
        repository = make_repository()
        service = SystemDesignService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("system-design").id
        scenario = repository.add_system_design_scenario(
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

        saved = service.add_artifact(
            topic_id,
            "requirements",
            "  Нужны transactional уведомления и unsubscribe.  ",
            scenario_id=scenario.id,
        )
        artifacts = service.list_artifacts(topic_id, scenario_id=scenario.id)

        self.assertEqual(saved.content, "Нужны transactional уведомления и unsubscribe.")
        self.assertEqual([artifact.section for artifact in artifacts], ["requirements"])
        self.assertEqual([artifact.content for artifact in artifacts], [saved.content])

    def test_system_design_service_saves_final_feedback_artifact_with_metadata(self) -> None:
        repository = make_repository()
        service = SystemDesignService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("system-design").id
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic_id,
                started_at=datetime(2026, 5, 12, 10, 0, 0),
                target_minutes=60,
            )
        )
        scenario = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Notifications",
                scenario="Спроектируй сервис уведомлений.",
                focus_areas=["requirements", "risks"],
                source="test",
                created_at=datetime(2026, 5, 12, 10, 1, 0),
            )
        )

        saved = service.save_final_feedback(
            topic_id,
            "  Уровень: senior. Пробелы: добавь observability.  ",
            scenario_id=scenario.id,
            session_id=session.id,
            source="llm",
        )
        artifacts = repository.list_system_design_feedback_artifacts(
            topic_id,
            scenario_id=scenario.id,
            session_id=session.id,
        )

        self.assertEqual(saved.content, "Уровень: senior. Пробелы: добавь observability.")
        self.assertEqual(saved.scenario_id, scenario.id)
        self.assertEqual(saved.session_id, session.id)
        self.assertEqual(saved.source, "llm")
        self.assertEqual([artifact.id for artifact in artifacts], [saved.id])
        self.assertEqual([artifact.content for artifact in artifacts], [saved.content])

    def test_repository_persists_system_design_evaluation_scores(self) -> None:
        repository = make_repository()
        topic_id = repository.find_topic_by_slug("system-design").id
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic_id,
                started_at=datetime(2026, 5, 21, 9, 0, 0),
                target_minutes=60,
            )
        )
        scenario = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Notifications",
                scenario="Спроектируй сервис уведомлений.",
                focus_areas=["requirements", "observability"],
                source="test",
                created_at=datetime(2026, 5, 21, 9, 1, 0),
            )
        )
        feedback = repository.add_system_design_feedback_artifact(
            SystemDesignFeedbackArtifact(
                id=None,
                topic_id=topic_id,
                scenario_id=scenario.id,
                session_id=session.id,
                content="Уровень: middle+. Добавь observability.",
                source="test",
                created_at=datetime(2026, 5, 21, 9, 20, 0),
            )
        )
        dimensions = repository.list_system_design_rubric_dimensions()
        scores = [
            AnswerEvaluationScore(
                dimension=dimension,
                score=3,
                evidence=f"Evidence for {dimension.slug}.",
                gaps=f"Gap for {dimension.slug}.",
                next_drill=f"Drill for {dimension.slug}.",
            )
            for dimension in dimensions
        ]

        saved = repository.add_system_design_evaluation(
            SystemDesignEvaluation(
                id=None,
                feedback_artifact_id=feedback.id or 0,
                topic_id=topic_id,
                scenario_id=scenario.id,
                session_id=session.id,
                summary="Средний system design rubric score: 3.0/5.",
                scores=scores,
                next_drills=["Drill for requirements."],
                source="heuristic",
                created_at=datetime(2026, 5, 21, 9, 21, 0),
                raw_payload_json=None,
            )
        )

        by_id = repository.get_system_design_evaluation(saved.id or 0)
        by_feedback = repository.get_system_design_evaluation_for_feedback(feedback.id or 0)
        listed = repository.list_system_design_evaluations(
            topic_id=topic_id,
            scenario_id=scenario.id,
            session_id=session.id,
        )

        self.assertIsNotNone(saved.id)
        self.assertEqual(by_id, saved)
        self.assertEqual(by_feedback, saved)
        self.assertEqual([item.id for item in listed], [saved.id])
        self.assertEqual(
            [score.dimension.slug for score in saved.scores],
            [dimension.slug for dimension in dimensions],
        )
        self.assertEqual(saved.next_drills, ["Drill for requirements."])

    def test_system_design_service_stores_rubric_evaluation_after_final_feedback(self) -> None:
        repository = make_repository()
        service = SystemDesignService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("system-design").id
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic_id,
                started_at=datetime(2026, 5, 21, 10, 0, 0),
                target_minutes=60,
            )
        )
        scenario = repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title="Link shortener",
                scenario="Спроектируй сервис коротких ссылок.",
                focus_areas=["requirements", "api", "data", "risks"],
                source="test",
                created_at=datetime(2026, 5, 21, 10, 1, 0),
            )
        )
        service.save_transcript_turn(
            topic_id,
            (
                "Сначала фиксирую SLA 99.9%, публичный API, таблицу links, Redis cache, "
                "hot key risk и retries с idempotency."
            ),
            "Какие метрики и алерты нужны для user impact?",
            scenario_id=scenario.id,
        )
        service.add_artifact(topic_id, "requirements", "SLA 99.9%, публичные short links.", scenario_id=scenario.id)
        service.add_artifact(topic_id, "api", "POST /links, GET /{code}, ошибки 400/404/429.", scenario_id=scenario.id)
        service.add_artifact(topic_id, "data_model", "links(id, code, target_url), индекс по code.", scenario_id=scenario.id)
        service.add_artifact(topic_id, "risks", "Hot keys, provider outage, retries and abuse.", scenario_id=scenario.id)

        feedback = service.save_final_feedback(
            topic_id,
            "Уровень: middle+. Добавь observability dashboard.",
            scenario_id=scenario.id,
            session_id=session.id,
            source="llm",
        )

        evaluation = repository.get_system_design_evaluation_for_feedback(feedback.id or 0)
        self.assertIsNotNone(evaluation)
        assert evaluation is not None
        self.assertEqual(evaluation.topic_id, topic_id)
        self.assertEqual(evaluation.scenario_id, scenario.id)
        self.assertEqual(evaluation.session_id, session.id)
        self.assertEqual(evaluation.source, "heuristic")
        self.assertEqual(
            [score.dimension.slug for score in evaluation.scores],
            [dimension.slug for dimension in repository.list_system_design_rubric_dimensions()],
        )
        scores_by_slug = {score.dimension.slug: score for score in evaluation.scores}
        self.assertGreaterEqual(scores_by_slug["requirements"].score, 3)
        self.assertGreaterEqual(scores_by_slug["api"].score, 3)
        self.assertGreaterEqual(scores_by_slug["data-model"].score, 3)
        self.assertGreaterEqual(scores_by_slug["reliability"].score, 3)
        self.assertLessEqual(scores_by_slug["observability"].score, 2)
        self.assertIn("Средний system design rubric score", evaluation.summary)
        self.assertTrue(evaluation.next_drills)

    def test_content_generation_ensure_question_backlog_avoids_duplicate_active_jobs(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("async-backend").id

        first_job = service.ensure_question_backlog(topic_id, min_questions=4, note="auto")
        second_job = service.ensure_question_backlog(topic_id, min_questions=4, note="auto")
        no_job_when_enough_questions = service.ensure_question_backlog(topic_id, min_questions=2, note="auto")

        self.assertIsNotNone(first_job)
        self.assertIsNone(second_job)
        self.assertIsNone(no_job_when_enough_questions)

    def test_content_generation_ensure_artifacts_avoids_duplicate_jobs(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        topic_id = repository.find_topic_by_slug("python-runtime").id

        first_learning = service.ensure_learning_material(topic_id, note="auto")
        second_learning = service.ensure_learning_material(topic_id, note="auto")
        first_scenario = service.ensure_system_design_scenario(topic_id, note="auto")
        second_scenario = service.ensure_system_design_scenario(topic_id, note="auto")

        self.assertIsNotNone(first_learning)
        self.assertIsNone(second_learning)
        self.assertIsNotNone(first_scenario)
        self.assertIsNone(second_scenario)

        service.process_next_job()
        service.process_next_job()

        self.assertIsNone(service.ensure_learning_material(topic_id, note="auto"))
        self.assertIsNone(service.ensure_system_design_scenario(topic_id, note="auto"))

    def test_content_generation_retry_moves_failed_job_to_queue(self) -> None:
        repository = make_repository()
        service = ContentGenerationService(repository, StaticLLM())
        job = repository.create_content_generation_job("unknown", "{}")

        result = service.process_next_job()
        service.retry_job(job.id or 0)
        retried = repository.get_content_generation_job(job.id or 0)

        self.assertEqual(result.job.status, "failed")
        self.assertIsNotNone(retried)
        self.assertEqual(retried.status, "queued")
        retry = json.loads(retried.payload_json)["retry"]
        self.assertIsNone(retry["next_attempt_at"])
        self.assertIsNone(retry["last_error"])

    def test_system_design_prompts_use_interviewer_flow_and_senior_criteria(self) -> None:
        transcript = [("Кандидат", "Нужно начать с требований и API.")]

        turn_prompt = build_system_design_turn_prompt(
            "Спроектируй сервис доставки уведомлений.",
            transcript,
            "Предлагаю POST /notifications и worker с очередью.",
        )
        feedback_prompt = build_system_design_feedback_prompt(
            "Спроектируй сервис доставки уведомлений.",
            transcript,
        )

        self.assertIn("быть интервьюером, а не автором полного решения", turn_prompt)
        self.assertIn("requirements, API, data model", turn_prompt)
        self.assertIn("<candidate_message>\nПредлагаю POST /notifications", turn_prompt)
        self.assertIn("Оценивай только то, что есть в transcript", feedback_prompt)
        self.assertIn("observability", feedback_prompt)
        self.assertIn("failure modes", feedback_prompt)

    def test_system_design_checkpoint_prompt_is_not_final_evaluation(self) -> None:
        transcript = [("Кандидат", "Зафиксировал SLA и POST /notifications.")]

        checkpoint_prompt = build_system_design_checkpoint_prompt(
            "Спроектируй сервис доставки уведомлений.",
            transcript,
            {
                "requirements": ["SLA 99.9%, transactional и marketing notifications"],
                "api": ["POST /notifications"],
            },
        )

        self.assertIn("<system_design_checkpoint>", checkpoint_prompt)
        self.assertIn("Это не финальный feedback и не оценка уровня кандидата", checkpoint_prompt)
        self.assertIn("Не ставь уровень middle/senior", checkpoint_prompt)
        self.assertIn("Вопрос интервьюера: один конкретный follow-up вопрос", checkpoint_prompt)
        self.assertIn("requirements:\n- SLA 99.9%", checkpoint_prompt)
        self.assertIn("api:\n- POST /notifications", checkpoint_prompt)
        self.assertIn("Зафиксировал SLA", checkpoint_prompt)

    def test_system_design_pressure_prompt_targets_senior_failure_modes_without_final_score(self) -> None:
        transcript = [("Кандидат", "Нужен worker и очередь для доставки уведомлений.")]

        pressure_prompt = build_system_design_pressure_prompt(
            "Спроектируй сервис доставки уведомлений.",
            transcript,
            {
                "decisions": ["Kafka для фоновой доставки"],
                "risks": ["provider outage"],
            },
        )

        self.assertIn("<system_design_pressure_follow_up>", pressure_prompt)
        self.assertIn("Это не финальный feedback и не оценка уровня кандидата", pressure_prompt)
        self.assertIn("Не ставь уровень middle/senior", pressure_prompt)
        self.assertIn("capacity planning", pressure_prompt)
        self.assertIn("hot keys", pressure_prompt)
        self.assertIn("retries", pressure_prompt)
        self.assertIn("idempotency", pressure_prompt)
        self.assertIn("migrations", pressure_prompt)
        self.assertIn("abuse protection", pressure_prompt)
        self.assertIn("Question: один конкретный вопрос интервьюера", pressure_prompt)
        self.assertIn("decisions:\n- Kafka", pressure_prompt)
        self.assertIn("provider outage", pressure_prompt)

    def _save_answer(
        self,
        repository: SQLiteRepository,
        topic_id: int,
        self_score: int,
        answered_at: datetime,
    ) -> None:
        question = repository.list_questions(topic_id)[0]
        self._save_answer_for_question(repository, question.id or 0, topic_id, self_score, answered_at)

    def _save_answer_for_question(
        self,
        repository: SQLiteRepository,
        question_id: int,
        topic_id: int,
        self_score: int,
        answered_at: datetime,
    ) -> None:
        session = repository.create_session(
            Session(
                id=None,
                topic_id=topic_id,
                started_at=answered_at - timedelta(minutes=10),
                ended_at=None,
                target_minutes=60,
            )
        )
        repository.add_answer(
            Answer(
                id=None,
                session_id=session.id or 0,
                question_id=question_id,
                user_answer="Ответ для метрик curriculum recommendation.",
                self_score=self_score,
                ai_feedback=None,
                answered_at=answered_at,
            )
        )


@unittest.skipUnless(os.getenv("RUN_OLLAMA_TESTS") == "1", "optional live Ollama test")
class LiveOllamaTests(unittest.TestCase):
    def test_ollama_generate(self) -> None:
        client = OllamaClient(timeout_seconds=180)
        response = client.generate("Ответь одним словом: ok.")
        self.assertTrue(response)


if __name__ == "__main__":
    unittest.main()
