from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import datetime

from interview_prep.domain.models import (
    Answer,
    AnswerEvaluation,
    AnswerEvaluationScore,
    Competency,
    ContentGenerationJob,
    CurriculumObjective,
    CurriculumSubtopic,
    CurriculumTopic,
    LearningDialogMessage,
    LearningDialogSummary,
    LearningMaterial,
    ManualNote,
    NotebookEntry,
    PracticeSessionAnswerDetail,
    PracticeSessionSummary,
    Question,
    QuestionAutoCurationAudit,
    QuestionCompetencyLink,
    QuestionSourceSnapshot,
    QUESTION_SOURCE_QUALITY_STATUSES,
    RubricDimension,
    SESSION_STATUS_ABANDONED,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_IN_PROGRESS,
    SESSION_STATUSES,
    Session,
    SessionOutcome,
    SystemDesignArtifact,
    SystemDesignEvaluation,
    SystemDesignFeedbackArtifact,
    SystemDesignScenario,
    SystemDesignTranscriptMessage,
    Tag,
    Topic,
)
from interview_prep.infra.seed import (
    BOOTSTRAP_TOPICS,
    CANONICAL_2026_SOURCE,
    RUBRIC_DIMENSIONS,
    SENIOR_COMPETENCIES,
    SeedQuestion,
    SEED_QUESTIONS,
    SYSTEM_DESIGN_RUBRIC_DIMENSIONS,
)


CANONICAL_METADATA_TAGS = {
    "api": Tag(
        id=None,
        slug="api",
        title="API",
        description="Canonical API and web backend interview coverage.",
        source=CANONICAL_2026_SOURCE,
    ),
    "async": Tag(
        id=None,
        slug="async",
        title="Async",
        description="Canonical async worker, queue and concurrency interview coverage.",
        source=CANONICAL_2026_SOURCE,
    ),
    "coding": Tag(
        id=None,
        slug="coding",
        title="Coding",
        description="Canonical coding screen interview coverage.",
        source=CANONICAL_2026_SOURCE,
    ),
    "db": Tag(
        id=None,
        slug="db",
        title="Database",
        description="Canonical database and Postgres interview coverage.",
        source=CANONICAL_2026_SOURCE,
    ),
    "frequency-high": Tag(
        id=None,
        slug="frequency-high",
        title="High frequency",
        description="High-frequency interview signal from canonical source research.",
        source=CANONICAL_2026_SOURCE,
    ),
    "must-know": Tag(
        id=None,
        slug="must-know",
        title="Must know",
        description="Canonical must-know interview question.",
        source=CANONICAL_2026_SOURCE,
    ),
    "ops": Tag(
        id=None,
        slug="ops",
        title="Ops",
        description="Canonical operations, reliability and incident interview coverage.",
        source=CANONICAL_2026_SOURCE,
    ),
    "python-core": Tag(
        id=None,
        slug="python-core",
        title="Python core",
        description="Canonical Python runtime and language internals interview coverage.",
        source=CANONICAL_2026_SOURCE,
    ),
    "system-design": Tag(
        id=None,
        slug="system-design",
        title="System design",
        description="Canonical system design interview coverage.",
        source=CANONICAL_2026_SOURCE,
    ),
    "testing": Tag(
        id=None,
        slug="testing",
        title="Testing",
        description="Canonical testing and quality interview coverage.",
        source=CANONICAL_2026_SOURCE,
    ),
}

CANONICAL_CATEGORY_TAGS = {
    "api-web": "api",
    "async-queues": "async",
    "coding-screen": "coding",
    "ops-reliability": "ops",
    "python-core": "python-core",
    "sql-postgres": "db",
    "system-design": "system-design",
    "testing-quality": "testing",
}


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _session_status(row: sqlite3.Row) -> str:
    status = row["status"] if "status" in row.keys() else None
    if status in SESSION_STATUSES:
        return status
    return SESSION_STATUS_COMPLETED if row["ended_at"] else SESSION_STATUS_IN_PROGRESS


def _job(row: sqlite3.Row) -> ContentGenerationJob:
    return ContentGenerationJob(
        id=row["id"],
        kind=row["kind"],
        status=row["status"],
        payload_json=row["payload_json"],
        result_json=row["result_json"],
        error=row["error"],
        created_at=_dt(row["created_at"]),
        updated_at=_dt(row["updated_at"]),
    )


def _question(row: sqlite3.Row) -> Question:
    values = dict(row)
    values.setdefault("source_quality_status", "accepted")
    values.setdefault("source_url", None)
    values.setdefault("source_retrieved_at", None)
    values.setdefault("source_frequency_hint", None)
    source_retrieved_at = values["source_retrieved_at"]
    values["source_retrieved_at"] = _dt(source_retrieved_at) if source_retrieved_at else None
    source_category_hints_json = values.pop("source_category_hints_json", "[]")
    values["source_category_hints"] = tuple(_json_string_list(source_category_hints_json or "[]"))
    return Question(**values)


def _question_source_snapshot(row: sqlite3.Row) -> QuestionSourceSnapshot:
    return QuestionSourceSnapshot(
        id=row["id"],
        source_id=row["source_id"],
        url=row["url"],
        title=row["title"],
        retrieved_at=_dt(row["retrieved_at"]),
        checksum=row["checksum"],
        category_hints=_json_string_list(row["category_hints_json"]),
        created_at=_dt(row["created_at"]),
    )


def _question_auto_curation_audit(row: sqlite3.Row) -> QuestionAutoCurationAudit:
    source_retrieved_at = row["source_retrieved_at"]
    return QuestionAutoCurationAudit(
        id=row["id"],
        question_id=row["question_id"],
        previous_status=row["previous_status"],
        decision=row["decision"],
        resulting_status=row["resulting_status"],
        confidence=float(row["confidence"]),
        curator_score=row["curator_score"],
        rationale=row["rationale"],
        quality_flags=_json_string_list(row["quality_flags_json"]),
        duplicate_of_id=row["duplicate_of_id"],
        curator_source_evidence=row["curator_source_evidence"],
        curator_model=row["curator_model"],
        curator_version=row["curator_version"],
        source_url=row["source_url"],
        source_retrieved_at=_dt(source_retrieved_at) if source_retrieved_at else None,
        source_category_hints=_json_string_list(row["source_category_hints_json"]),
        source_frequency_hint=row["source_frequency_hint"],
        created_at=_dt(row["created_at"]),
    )


def _learning_material(row: sqlite3.Row) -> LearningMaterial:
    archived_at = row["archived_at"] if "archived_at" in row.keys() else None
    archive_reason = row["archive_reason"] if "archive_reason" in row.keys() else None
    return LearningMaterial(
        id=row["id"],
        topic_id=row["topic_id"],
        title=row["title"],
        body=row["body"],
        source=row["source"],
        created_at=_dt(row["created_at"]),
        archived_at=_dt(archived_at) if archived_at else None,
        archive_reason=archive_reason,
    )


def _curriculum_topic(row: sqlite3.Row) -> CurriculumTopic:
    return CurriculumTopic(
        id=row["id"],
        topic_id=row["topic_id"],
        slug=row["slug"],
        title=row["title"],
        description=row["description"],
        level=row["level"],
        source=row["source"],
        order_index=row["order_index"],
    )


def _curriculum_subtopic(row: sqlite3.Row) -> CurriculumSubtopic:
    return CurriculumSubtopic(
        id=row["id"],
        curriculum_topic_id=row["curriculum_topic_id"],
        slug=row["slug"],
        title=row["title"],
        description=row["description"],
        source=row["source"],
        order_index=row["order_index"],
    )


def _curriculum_objective(row: sqlite3.Row) -> CurriculumObjective:
    return CurriculumObjective(
        id=row["id"],
        curriculum_topic_id=row["curriculum_topic_id"],
        curriculum_subtopic_id=row["curriculum_subtopic_id"],
        text=row["text"],
        source=row["source"],
        order_index=row["order_index"],
    )


def _tag(row: sqlite3.Row) -> Tag:
    return Tag(
        id=row["id"],
        slug=row["slug"],
        title=row["title"],
        description=row["description"],
        source=row["source"],
    )


def _competency(row: sqlite3.Row) -> Competency:
    return Competency(
        id=row["id"],
        slug=row["slug"],
        title=row["title"],
        description=row["description"],
        category=row["category"],
        level=row["level"],
        order_index=row["order_index"],
    )


def _rubric_dimension(row: sqlite3.Row) -> RubricDimension:
    return RubricDimension(
        id=row["id"],
        slug=row["slug"],
        title=row["title"],
        description=row["description"],
        order_index=row["order_index"],
    )


def _answer_evaluation_score(row: sqlite3.Row) -> AnswerEvaluationScore:
    manual_override_at = row["manual_override_at"] if "manual_override_at" in row.keys() else None
    return AnswerEvaluationScore(
        dimension=_rubric_dimension(row),
        score=row["score"],
        evidence=row["evidence"],
        gaps=row["gaps"],
        next_drill=row["next_drill"],
        manual_override_score=row["manual_override_score"]
        if "manual_override_score" in row.keys()
        else None,
        manual_override_reason=row["manual_override_reason"]
        if "manual_override_reason" in row.keys()
        else None,
        manual_override_at=_dt(manual_override_at) if manual_override_at else None,
    )


def _answer_evaluation(row: sqlite3.Row, scores: list[AnswerEvaluationScore]) -> AnswerEvaluation:
    return AnswerEvaluation(
        id=row["id"],
        answer_id=row["answer_id"],
        session_id=row["session_id"],
        question_id=row["question_id"],
        summary=row["summary"],
        scores=scores,
        next_drills=list(json.loads(row["next_drills_json"])),
        source=row["source"],
        created_at=_dt(row["created_at"]),
        raw_payload_json=row["raw_payload_json"],
    )


def _json_string_list(value: str) -> list[str]:
    try:
        decoded = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(decoded, list):
        return []
    return [str(item) for item in decoded]


def _session_outcome(row: sqlite3.Row) -> SessionOutcome:
    outcome_type = row["outcome_type"] if "outcome_type" in row.keys() else "practice"
    return SessionOutcome(
        id=row["id"],
        session_id=row["session_id"],
        summary=row["summary"],
        strengths=_json_string_list(row["strengths_json"]),
        gaps=_json_string_list(row["gaps_json"]),
        next_drills=_json_string_list(row["next_drills_json"]),
        readiness_delta=float(row["readiness_delta"]),
        created_at=_dt(row["created_at"]),
        outcome_type=outcome_type,
    )


def _evaluation_payload_with_feedback_quality(
    raw_payload_json: str | None,
    *,
    flags: Sequence[str],
    evidence_terms: Sequence[str] = (),
    fallback_error: str | None = None,
) -> str:
    payload: dict[str, object]
    if raw_payload_json:
        try:
            decoded = json.loads(raw_payload_json)
        except json.JSONDecodeError:
            payload = {"rubric_raw_payload": raw_payload_json}
        else:
            payload = decoded if isinstance(decoded, dict) else {"rubric_raw_payload": decoded}
    else:
        payload = {}

    normalized_flags = list(dict.fromkeys(str(flag) for flag in flags if str(flag).strip()))
    suspicious_flags = [flag for flag in normalized_flags if flag != "fallback_feedback"]
    payload["feedback_quality_flags"] = normalized_flags
    payload["feedback_quality"] = {
        "flags": normalized_flags,
        "suspicious": bool(suspicious_flags),
        "evidence_terms": list(dict.fromkeys(str(term) for term in evidence_terms if str(term).strip())),
        "fallback": bool(fallback_error),
        "fallback_error": fallback_error,
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _question_competency_link(row: sqlite3.Row) -> QuestionCompetencyLink:
    return QuestionCompetencyLink(
        competency=_competency(row),
        is_primary=bool(row["is_primary"]),
        weight=float(row["weight"]),
    )


def _practice_session_summary(row: sqlite3.Row) -> PracticeSessionSummary:
    return PracticeSessionSummary(
        id=row["id"],
        topic_id=row["topic_id"],
        topic_title=row["topic_title"],
        started_at=_dt(row["started_at"]),
        ended_at=_dt(row["ended_at"]),
        target_minutes=row["target_minutes"],
        answer_count=row["answer_count"],
        avg_self_score=row["avg_self_score"],
    )


def _practice_session_answer_detail(row: sqlite3.Row) -> PracticeSessionAnswerDetail:
    return PracticeSessionAnswerDetail(
        answer_id=row["answer_id"],
        question_id=row["question_id"],
        question_difficulty=row["question_difficulty"],
        question_prompt=row["question_prompt"],
        user_answer=row["user_answer"],
        self_score=row["self_score"],
        reference_answer=row["reference_answer"],
        ai_feedback=row["ai_feedback"],
        answered_at=_dt(row["answered_at"]),
    )


def _learning_dialog_message(row: sqlite3.Row) -> LearningDialogMessage:
    keys = row.keys()
    return LearningDialogMessage(
        id=row["id"],
        topic_id=row["topic_id"],
        role=row["role"],
        content=row["content"],
        created_at=_dt(row["created_at"]),
        dialog_session_id=row["dialog_session_id"] if "dialog_session_id" in keys else None,
        context_type=row["context_type"] if "context_type" in keys else None,
        context_id=row["context_id"] if "context_id" in keys else None,
    )


def _learning_dialog_summary(row: sqlite3.Row) -> LearningDialogSummary:
    keys = row.keys()
    return LearningDialogSummary(
        topic_id=row["topic_id"],
        topic_title=row["topic_title"] or f"Topic #{row['topic_id']}",
        dialog_date=row["dialog_date"],
        first_message_at=_dt(row["first_message_at"]),
        last_message_at=_dt(row["last_message_at"]),
        message_count=row["message_count"],
        dialog_session_id=row["dialog_session_id"] if "dialog_session_id" in keys else None,
        context_type=row["context_type"] if "context_type" in keys else None,
        context_id=row["context_id"] if "context_id" in keys else None,
    )


def _notebook_entry(row: sqlite3.Row) -> NotebookEntry:
    return NotebookEntry(
        id=row["id"],
        topic_id=row["topic_id"],
        curriculum_subtopic_id=row["curriculum_subtopic_id"],
        dialog_session_id=row["dialog_session_id"],
        source_message_id=row["source_message_id"],
        title=row["title"],
        body=row["body"],
        source=row["source"],
        created_at=_dt(row["created_at"]),
    )


def _manual_note(row: sqlite3.Row) -> ManualNote:
    return ManualNote(
        id=row["id"],
        topic_id=row["topic_id"],
        session_id=row["session_id"],
        context_type=row["context_type"],
        context_id=row["context_id"],
        title=row["title"],
        body=row["body"],
        created_at=_dt(row["created_at"]),
        updated_at=_dt(row["updated_at"]),
    )


def _system_design_scenario(row: sqlite3.Row) -> SystemDesignScenario:
    archived_at = row["archived_at"] if "archived_at" in row.keys() else None
    archive_reason = row["archive_reason"] if "archive_reason" in row.keys() else None
    try:
        focus_areas = json.loads(row["focus_areas_json"])
    except json.JSONDecodeError:
        focus_areas = []
    if not isinstance(focus_areas, list):
        focus_areas = []
    return SystemDesignScenario(
        id=row["id"],
        topic_id=row["topic_id"],
        title=row["title"],
        scenario=row["scenario"],
        focus_areas=[str(item) for item in focus_areas],
        source=row["source"],
        created_at=_dt(row["created_at"]),
        archived_at=_dt(archived_at) if archived_at else None,
        archive_reason=archive_reason,
    )


def _system_design_transcript_message(row: sqlite3.Row) -> SystemDesignTranscriptMessage:
    return SystemDesignTranscriptMessage(
        id=row["id"],
        topic_id=row["topic_id"],
        scenario_id=row["scenario_id"],
        role=row["role"],
        content=row["content"],
        created_at=_dt(row["created_at"]),
    )


def _system_design_artifact(row: sqlite3.Row) -> SystemDesignArtifact:
    return SystemDesignArtifact(
        id=row["id"],
        topic_id=row["topic_id"],
        scenario_id=row["scenario_id"],
        section=row["section"],
        content=row["content"],
        created_at=_dt(row["created_at"]),
    )


def _system_design_feedback_artifact(row: sqlite3.Row) -> SystemDesignFeedbackArtifact:
    return SystemDesignFeedbackArtifact(
        id=row["id"],
        topic_id=row["topic_id"],
        scenario_id=row["scenario_id"],
        session_id=row["session_id"],
        content=row["content"],
        source=row["source"],
        created_at=_dt(row["created_at"]),
    )


def _system_design_evaluation(
    row: sqlite3.Row,
    scores: list[AnswerEvaluationScore],
) -> SystemDesignEvaluation:
    return SystemDesignEvaluation(
        id=row["id"],
        feedback_artifact_id=row["feedback_artifact_id"],
        topic_id=row["topic_id"],
        scenario_id=row["scenario_id"],
        session_id=row["session_id"],
        summary=row["summary"],
        scores=scores,
        next_drills=_json_string_list(row["next_drills_json"]),
        source=row["source"],
        created_at=_dt(row["created_at"]),
        raw_payload_json=row["raw_payload_json"],
    )


class SQLiteRepository:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        self.connection.close()
        self._closed = True

    def __del__(self) -> None:
        self.close()

    def seed_defaults(self) -> None:
        with self.connection:
            for dimension in RUBRIC_DIMENSIONS:
                self.connection.execute(
                    """
                    INSERT INTO rubric_dimensions
                        (slug, title, description, order_index)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        title = excluded.title,
                        description = excluded.description,
                        order_index = excluded.order_index
                    """,
                    (
                        dimension.slug,
                        dimension.title,
                        dimension.description,
                        dimension.order_index,
                    ),
                )

            for dimension in SYSTEM_DESIGN_RUBRIC_DIMENSIONS:
                self.connection.execute(
                    """
                    INSERT INTO system_design_rubric_dimensions
                        (slug, title, description, order_index)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        title = excluded.title,
                        description = excluded.description,
                        order_index = excluded.order_index
                    """,
                    (
                        dimension.slug,
                        dimension.title,
                        dimension.description,
                        dimension.order_index,
                    ),
                )

            for competency in SENIOR_COMPETENCIES:
                self.connection.execute(
                    """
                    INSERT INTO competencies
                        (slug, title, description, category, level, order_index)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(slug) DO UPDATE SET
                        title = excluded.title,
                        description = excluded.description,
                        category = excluded.category,
                        level = excluded.level,
                        order_index = excluded.order_index
                    """,
                    (
                        competency.slug,
                        competency.title,
                        competency.description,
                        competency.category,
                        competency.level,
                        competency.order_index,
                    ),
                )

            for topic in BOOTSTRAP_TOPICS:
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO topics (slug, title, description, level)
                    VALUES (?, ?, ?, ?)
                    """,
                    (topic.slug, topic.title, topic.description, topic.level),
                )
                self.connection.execute(
                    """
                    UPDATE topics
                    SET title = ?, description = ?, level = ?
                    WHERE slug = ?
                    """,
                    (topic.title, topic.description, topic.level, topic.slug),
                )

            topic_ids = {
                row["slug"]: row["id"]
                for row in self.connection.execute("SELECT id, slug FROM topics")
            }
            competency_ids = {
                row["slug"]: row["id"]
                for row in self.connection.execute("SELECT id, slug FROM competencies")
            }

            for question in SEED_QUESTIONS:
                self._upsert_seed_question(question, topic_ids)
            self._seed_question_competencies(SEED_QUESTIONS, topic_ids, competency_ids)
            self._seed_question_tags(SEED_QUESTIONS, topic_ids)

    def _upsert_seed_question(self, question: SeedQuestion, topic_ids: dict[str, int]) -> int:
        topic_id = topic_ids.get(question.topic_slug)
        if topic_id is None:
            raise RuntimeError(f"Unknown seed topic slug: {question.topic_slug}")
        existing_id = self._find_seed_question_id(question, topic_id)
        category_hints_json = json.dumps(list(question.source_category_hints), ensure_ascii=False)
        if existing_id is not None:
            self.connection.execute(
                """
                UPDATE questions
                SET
                    difficulty = ?,
                    prompt = ?,
                    hint = ?,
                    reference_answer = ?,
                    source_category_hints_json = ?,
                    source_frequency_hint = ?
                WHERE id = ?
                """,
                (
                    question.difficulty,
                    question.prompt,
                    question.hint,
                    question.reference_answer,
                    category_hints_json,
                    question.source_frequency_hint,
                    existing_id,
                ),
            )
            return existing_id

        cursor = self.connection.execute(
            """
            INSERT INTO questions
                (
                    topic_id,
                    difficulty,
                    prompt,
                    hint,
                    reference_answer,
                    source,
                    source_quality_status,
                    source_category_hints_json,
                    source_frequency_hint
                )
            VALUES (?, ?, ?, ?, ?, ?, 'accepted', ?, ?)
            """,
            (
                topic_id,
                question.difficulty,
                question.prompt,
                question.hint,
                question.reference_answer,
                question.source,
                category_hints_json,
                question.source_frequency_hint,
            ),
        )
        return int(cursor.lastrowid)

    def _find_seed_question_id(self, question: SeedQuestion, topic_id: int) -> int | None:
        if question.source == "bootstrap":
            row = self.connection.execute(
                """
                SELECT id
                FROM questions
                WHERE topic_id = ? AND difficulty = ? AND source = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (topic_id, question.difficulty, question.source),
            ).fetchone()
        else:
            row = self.connection.execute(
                """
                SELECT id
                FROM questions
                WHERE topic_id = ? AND source = ? AND prompt = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (topic_id, question.source, question.prompt),
            ).fetchone()
        return int(row["id"]) if row else None

    def _seed_question_competencies(
        self,
        questions: Sequence[SeedQuestion],
        topic_ids: dict[str, int],
        competency_ids: dict[str, int],
    ) -> None:
        for question in questions:
            if not question.competency_links:
                continue
            primary_count = sum(1 for link in question.competency_links if link.is_primary)
            if primary_count > 1:
                raise RuntimeError(f"Seed question has multiple primary competencies: {question.topic_slug}")

            topic_id = topic_ids.get(question.topic_slug)
            if topic_id is None:
                raise RuntimeError(f"Unknown seed topic slug: {question.topic_slug}")
            question_id = self._find_seed_question_id(question, topic_id)
            if question_id is None:
                continue

            existing_links = self.connection.execute(
                """
                SELECT COUNT(*) AS c
                FROM question_competencies
                WHERE question_id = ?
                """,
                (question_id,),
            ).fetchone()["c"]
            if existing_links:
                continue

            for link in question.competency_links:
                competency_id = competency_ids.get(link.slug)
                if competency_id is None:
                    raise RuntimeError(f"Unknown seed competency slug: {link.slug}")
                self._validate_question_competency_weight(link.weight)
                self.connection.execute(
                    """
                    INSERT INTO question_competencies
                        (question_id, competency_id, is_primary, weight)
                    VALUES (?, ?, ?, ?)
                    """,
                    (question_id, competency_id, 1 if link.is_primary else 0, link.weight),
                )

    def _seed_question_tags(
        self,
        questions: Sequence[SeedQuestion],
        topic_ids: dict[str, int],
    ) -> None:
        for tag in CANONICAL_METADATA_TAGS.values():
            self.connection.execute(
                """
                INSERT OR IGNORE INTO tags (slug, title, description, source)
                VALUES (?, ?, ?, ?)
                """,
                (tag.slug, tag.title, tag.description, tag.source),
            )

        tag_ids = {
            row["slug"]: row["id"]
            for row in self.connection.execute("SELECT id, slug FROM tags")
            if row["slug"] in CANONICAL_METADATA_TAGS
        }

        for question in questions:
            metadata_tag_slugs = self._canonical_metadata_tag_slugs(question)
            if not metadata_tag_slugs:
                continue
            topic_id = topic_ids.get(question.topic_slug)
            if topic_id is None:
                raise RuntimeError(f"Unknown seed topic slug: {question.topic_slug}")
            question_id = self._find_seed_question_id(question, topic_id)
            if question_id is None:
                continue
            for slug in metadata_tag_slugs:
                tag_id = tag_ids.get(slug)
                if tag_id is None:
                    raise RuntimeError(f"Unknown seed tag slug: {slug}")
                self.connection.execute(
                    """
                    INSERT OR IGNORE INTO question_tags (question_id, tag_id)
                    VALUES (?, ?)
                    """,
                    (question_id, tag_id),
                )

    def _canonical_metadata_tag_slugs(self, question: SeedQuestion) -> list[str]:
        if question.source != CANONICAL_2026_SOURCE:
            return []
        slugs: list[str] = []
        if "must-know" in question.source_category_hints:
            slugs.append("must-know")
        if question.source_frequency_hint == "high":
            slugs.append("frequency-high")
        for category_hint, tag_slug in CANONICAL_CATEGORY_TAGS.items():
            if category_hint in question.source_category_hints:
                slugs.append(tag_slug)
        return list(dict.fromkeys(slugs))

    def list_topics(self) -> list[Topic]:
        rows = self.connection.execute(
            "SELECT id, slug, title, description, level FROM topics ORDER BY title"
        ).fetchall()
        return [Topic(**dict(row)) for row in rows]

    def get_topic(self, topic_id: int) -> Topic | None:
        row = self.connection.execute(
            "SELECT id, slug, title, description, level FROM topics WHERE id = ?",
            (topic_id,),
        ).fetchone()
        return Topic(**dict(row)) if row else None

    def find_topic_by_slug(self, slug: str) -> Topic | None:
        row = self.connection.execute(
            "SELECT id, slug, title, description, level FROM topics WHERE slug = ?",
            (slug,),
        ).fetchone()
        return Topic(**dict(row)) if row else None

    def upsert_topic(self, topic: Topic) -> Topic:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO topics (slug, title, description, level)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    level = excluded.level
                """,
                (topic.slug, topic.title, topic.description, topic.level),
            )
        saved = self.find_topic_by_slug(topic.slug)
        if saved is None:
            raise RuntimeError(f"Topic was not saved: {topic.slug}")
        return saved

    def add_curriculum_topic(self, curriculum_topic: CurriculumTopic) -> CurriculumTopic:
        existing = self.find_curriculum_topic_by_slug_source(
            curriculum_topic.slug,
            curriculum_topic.source,
        )
        if existing is not None:
            with self.connection:
                self.connection.execute(
                    """
                    UPDATE curriculum_topics
                    SET topic_id = ?, title = ?, description = ?, level = ?, order_index = ?
                    WHERE id = ?
                    """,
                    (
                        curriculum_topic.topic_id,
                        curriculum_topic.title,
                        curriculum_topic.description,
                        curriculum_topic.level,
                        curriculum_topic.order_index,
                        existing.id,
                    ),
                )
            return CurriculumTopic(
                id=existing.id,
                topic_id=curriculum_topic.topic_id,
                slug=curriculum_topic.slug,
                title=curriculum_topic.title,
                description=curriculum_topic.description,
                level=curriculum_topic.level,
                source=curriculum_topic.source,
                order_index=curriculum_topic.order_index,
            )

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO curriculum_topics
                    (topic_id, slug, title, description, level, source, order_index)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    curriculum_topic.topic_id,
                    curriculum_topic.slug,
                    curriculum_topic.title,
                    curriculum_topic.description,
                    curriculum_topic.level,
                    curriculum_topic.source,
                    curriculum_topic.order_index,
                ),
            )
        return CurriculumTopic(
            id=cursor.lastrowid,
            topic_id=curriculum_topic.topic_id,
            slug=curriculum_topic.slug,
            title=curriculum_topic.title,
            description=curriculum_topic.description,
            level=curriculum_topic.level,
            source=curriculum_topic.source,
            order_index=curriculum_topic.order_index,
        )

    def find_curriculum_topic_by_slug_source(self, slug: str, source: str) -> CurriculumTopic | None:
        row = self.connection.execute(
            """
            SELECT id, topic_id, slug, title, description, level, source, order_index
            FROM curriculum_topics
            WHERE slug = ? AND source = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (slug, source),
        ).fetchone()
        return _curriculum_topic(row) if row else None

    def list_curriculum_topics(
        self,
        source: str | None = None,
        topic_id: int | None = None,
    ) -> list[CurriculumTopic]:
        filters = []
        params: list[object] = []
        if source is not None:
            filters.append("source = ?")
            params.append(source)
        if topic_id is not None:
            filters.append("topic_id = ?")
            params.append(topic_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.connection.execute(
            f"""
            SELECT id, topic_id, slug, title, description, level, source, order_index
            FROM curriculum_topics
            {where}
            ORDER BY order_index ASC, id ASC
            """,
            params,
        ).fetchall()
        return [_curriculum_topic(row) for row in rows]

    def add_curriculum_subtopic(self, subtopic: CurriculumSubtopic) -> CurriculumSubtopic:
        existing = self.find_curriculum_subtopic_by_slug_source(
            subtopic.curriculum_topic_id,
            subtopic.slug,
            subtopic.source,
        )
        if existing is not None:
            with self.connection:
                self.connection.execute(
                    """
                    UPDATE curriculum_subtopics
                    SET title = ?, description = ?, order_index = ?
                    WHERE id = ?
                    """,
                    (
                        subtopic.title,
                        subtopic.description,
                        subtopic.order_index,
                        existing.id,
                    ),
                )
            return CurriculumSubtopic(
                id=existing.id,
                curriculum_topic_id=subtopic.curriculum_topic_id,
                slug=subtopic.slug,
                title=subtopic.title,
                description=subtopic.description,
                source=subtopic.source,
                order_index=subtopic.order_index,
            )

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO curriculum_subtopics
                    (curriculum_topic_id, slug, title, description, source, order_index)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    subtopic.curriculum_topic_id,
                    subtopic.slug,
                    subtopic.title,
                    subtopic.description,
                    subtopic.source,
                    subtopic.order_index,
                ),
            )
        return CurriculumSubtopic(
            id=cursor.lastrowid,
            curriculum_topic_id=subtopic.curriculum_topic_id,
            slug=subtopic.slug,
            title=subtopic.title,
            description=subtopic.description,
            source=subtopic.source,
            order_index=subtopic.order_index,
        )

    def find_curriculum_subtopic_by_slug_source(
        self,
        curriculum_topic_id: int,
        slug: str,
        source: str,
    ) -> CurriculumSubtopic | None:
        row = self.connection.execute(
            """
            SELECT id, curriculum_topic_id, slug, title, description, source, order_index
            FROM curriculum_subtopics
            WHERE curriculum_topic_id = ? AND slug = ? AND source = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (curriculum_topic_id, slug, source),
        ).fetchone()
        return _curriculum_subtopic(row) if row else None

    def get_curriculum_subtopic(self, subtopic_id: int) -> CurriculumSubtopic | None:
        row = self.connection.execute(
            """
            SELECT id, curriculum_topic_id, slug, title, description, source, order_index
            FROM curriculum_subtopics
            WHERE id = ?
            """,
            (subtopic_id,),
        ).fetchone()
        return _curriculum_subtopic(row) if row else None

    def list_curriculum_subtopics(self, curriculum_topic_id: int) -> list[CurriculumSubtopic]:
        rows = self.connection.execute(
            """
            SELECT id, curriculum_topic_id, slug, title, description, source, order_index
            FROM curriculum_subtopics
            WHERE curriculum_topic_id = ?
            ORDER BY order_index ASC, id ASC
            """,
            (curriculum_topic_id,),
        ).fetchall()
        return [_curriculum_subtopic(row) for row in rows]

    def add_curriculum_objective(self, objective: CurriculumObjective) -> CurriculumObjective:
        existing = self.find_curriculum_objective_by_text_source(
            objective.curriculum_topic_id,
            objective.curriculum_subtopic_id,
            objective.text,
            objective.source,
        )
        if existing is not None:
            with self.connection:
                self.connection.execute(
                    """
                    UPDATE curriculum_objectives
                    SET order_index = ?
                    WHERE id = ?
                    """,
                    (objective.order_index, existing.id),
                )
            return CurriculumObjective(
                id=existing.id,
                curriculum_topic_id=objective.curriculum_topic_id,
                curriculum_subtopic_id=objective.curriculum_subtopic_id,
                text=objective.text,
                source=objective.source,
                order_index=objective.order_index,
            )

        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO curriculum_objectives
                    (curriculum_topic_id, curriculum_subtopic_id, text, source, order_index)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    objective.curriculum_topic_id,
                    objective.curriculum_subtopic_id,
                    objective.text,
                    objective.source,
                    objective.order_index,
                ),
            )
        return CurriculumObjective(
            id=cursor.lastrowid,
            curriculum_topic_id=objective.curriculum_topic_id,
            curriculum_subtopic_id=objective.curriculum_subtopic_id,
            text=objective.text,
            source=objective.source,
            order_index=objective.order_index,
        )

    def find_curriculum_objective_by_text_source(
        self,
        curriculum_topic_id: int,
        curriculum_subtopic_id: int | None,
        text: str,
        source: str,
    ) -> CurriculumObjective | None:
        if curriculum_subtopic_id is None:
            row = self.connection.execute(
                """
                SELECT id, curriculum_topic_id, curriculum_subtopic_id, text, source, order_index
                FROM curriculum_objectives
                WHERE curriculum_topic_id = ?
                    AND curriculum_subtopic_id IS NULL
                    AND text = ?
                    AND source = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (curriculum_topic_id, text, source),
            ).fetchone()
        else:
            row = self.connection.execute(
                """
                SELECT id, curriculum_topic_id, curriculum_subtopic_id, text, source, order_index
                FROM curriculum_objectives
                WHERE curriculum_topic_id = ?
                    AND curriculum_subtopic_id = ?
                    AND text = ?
                    AND source = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (curriculum_topic_id, curriculum_subtopic_id, text, source),
            ).fetchone()
        return _curriculum_objective(row) if row else None

    def list_curriculum_objectives(
        self,
        curriculum_topic_id: int,
        curriculum_subtopic_id: int | None = None,
    ) -> list[CurriculumObjective]:
        if curriculum_subtopic_id is None:
            rows = self.connection.execute(
                """
                SELECT id, curriculum_topic_id, curriculum_subtopic_id, text, source, order_index
                FROM curriculum_objectives
                WHERE curriculum_topic_id = ? AND curriculum_subtopic_id IS NULL
                ORDER BY order_index ASC, id ASC
                """,
                (curriculum_topic_id,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT id, curriculum_topic_id, curriculum_subtopic_id, text, source, order_index
                FROM curriculum_objectives
                WHERE curriculum_topic_id = ? AND curriculum_subtopic_id = ?
                ORDER BY order_index ASC, id ASC
                """,
                (curriculum_topic_id, curriculum_subtopic_id),
            ).fetchall()
        return [_curriculum_objective(row) for row in rows]

    def list_questions(
        self,
        topic_id: int | None = None,
        tag_slug: str | None = None,
        source_quality_status: str | None = None,
    ) -> list[Question]:
        joins = ""
        conditions = []
        params: list[object] = []
        if source_quality_status is not None:
            self._validate_question_source_quality_status(source_quality_status)
            conditions.append("q.source_quality_status = ?")
            params.append(source_quality_status)
        if tag_slug:
            joins = """
                JOIN question_tags qt ON qt.question_id = q.id
                JOIN tags t ON t.id = qt.tag_id
            """
            conditions.append("t.slug = ?")
            params.append(tag_slug)
        if topic_id is not None:
            conditions.append("q.topic_id = ?")
            params.append(topic_id)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        order = "q.topic_id, q.difficulty, q.id" if topic_id is None else "q.difficulty, q.id"
        rows = self.connection.execute(
            f"""
            SELECT
                q.id,
                q.topic_id,
                q.difficulty,
                q.prompt,
                q.hint,
                q.reference_answer,
                q.source,
                q.source_quality_status,
                q.source_url,
                q.source_retrieved_at,
                q.source_category_hints_json,
                q.source_frequency_hint
            FROM questions q
            {joins}
            {where}
            ORDER BY {order}
            """,
            tuple(params),
        ).fetchall()
        return [_question(row) for row in rows]

    def get_question(self, question_id: int) -> Question | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                topic_id,
                difficulty,
                prompt,
                hint,
                reference_answer,
                source,
                source_quality_status,
                source_url,
                source_retrieved_at,
                source_category_hints_json,
                source_frequency_hint
            FROM questions WHERE id = ?
            """,
            (question_id,),
        ).fetchone()
        return _question(row) if row else None

    def update_question_source_quality_status(self, question_id: int, status: str) -> Question:
        self._validate_question_source_quality_status(status)
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE questions
                SET source_quality_status = ?
                WHERE id = ?
                """,
                (status, question_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(f"Unknown question id: {question_id}")
        saved = self.get_question(question_id)
        if saved is None:
            raise ValueError(f"Unknown question id: {question_id}")
        return saved

    def update_question_reference_answer(self, question_id: int, reference_answer: str) -> Question:
        saved = self.update_question_reference_answers([(question_id, reference_answer)])
        return saved[0]

    def update_question_reference_answers(self, updates: list[tuple[int, str]]) -> list[Question]:
        if not updates:
            return []
        with self.connection:
            for question_id, reference_answer in updates:
                cursor = self.connection.execute(
                    """
                    UPDATE questions
                    SET reference_answer = ?
                    WHERE id = ?
                    """,
                    (reference_answer, question_id),
                )
                if cursor.rowcount != 1:
                    raise ValueError(f"Unknown question id: {question_id}")
        saved_questions = []
        for question_id, _ in updates:
            saved = self.get_question(question_id)
            if saved is None:
                raise ValueError(f"Unknown question id: {question_id}")
            saved_questions.append(saved)
        return saved_questions

    def add_question(self, question: Question) -> Question:
        self._validate_question_source_quality_status(question.source_quality_status)
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO questions
                    (
                        topic_id,
                        difficulty,
                        prompt,
                        hint,
                        reference_answer,
                        source,
                        source_quality_status,
                        source_url,
                        source_retrieved_at,
                        source_category_hints_json,
                        source_frequency_hint
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question.topic_id,
                    question.difficulty,
                    question.prompt,
                    question.hint,
                    question.reference_answer,
                    question.source,
                    question.source_quality_status,
                    question.source_url,
                    question.source_retrieved_at.isoformat(timespec="seconds")
                    if question.source_retrieved_at
                    else None,
                    json.dumps(list(question.source_category_hints), ensure_ascii=False),
                    question.source_frequency_hint,
                ),
            )
        return Question(
            id=cursor.lastrowid,
            topic_id=question.topic_id,
            difficulty=question.difficulty,
            prompt=question.prompt,
            hint=question.hint,
            reference_answer=question.reference_answer,
            source=question.source,
            source_quality_status=question.source_quality_status,
            source_url=question.source_url,
            source_retrieved_at=question.source_retrieved_at,
            source_category_hints=question.source_category_hints,
            source_frequency_hint=question.source_frequency_hint,
        )

    def add_question_once(self, question: Question) -> Question:
        existing = self.connection.execute(
            """
            SELECT
                id,
                topic_id,
                difficulty,
                prompt,
                hint,
                reference_answer,
                source,
                source_quality_status,
                source_url,
                source_retrieved_at,
                source_category_hints_json,
                source_frequency_hint
            FROM questions
            WHERE topic_id = ? AND source = ? AND prompt = ?
            """,
            (question.topic_id, question.source, question.prompt),
        ).fetchone()
        if existing:
            return _question(existing)
        return self.add_question(question)

    def question_exists(self, topic_id: int, prompt: str, source: str) -> bool:
        row = self.connection.execute(
            """
            SELECT 1 FROM questions
            WHERE topic_id = ? AND source = ? AND prompt = ?
            """,
            (topic_id, source, prompt),
        ).fetchone()
        return row is not None

    def _validate_question_source_quality_status(self, status: str) -> None:
        if status not in QUESTION_SOURCE_QUALITY_STATUSES:
            raise ValueError(f"Unknown question source quality status: {status}")

    def upsert_question_source_snapshot(
        self,
        snapshot: QuestionSourceSnapshot,
    ) -> QuestionSourceSnapshot:
        category_hints_json = json.dumps(snapshot.category_hints, ensure_ascii=False)
        retrieved_at = snapshot.retrieved_at.isoformat(timespec="seconds")
        created_at = snapshot.created_at.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO question_source_snapshots
                    (source_id, url, title, retrieved_at, checksum, category_hints_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id, checksum) DO UPDATE SET
                    url = excluded.url,
                    title = excluded.title,
                    retrieved_at = excluded.retrieved_at,
                    category_hints_json = excluded.category_hints_json
                RETURNING
                    id, source_id, url, title, retrieved_at, checksum, category_hints_json, created_at
                """,
                (
                    snapshot.source_id,
                    snapshot.url,
                    snapshot.title,
                    retrieved_at,
                    snapshot.checksum,
                    category_hints_json,
                    created_at,
                ),
            )
            row = cursor.fetchone()
        if row is None:
            raise RuntimeError(f"Question source snapshot was not saved: {snapshot.source_id}")
        return _question_source_snapshot(row)

    def list_question_source_snapshots(self) -> list[QuestionSourceSnapshot]:
        rows = self.connection.execute(
            """
            SELECT id, source_id, url, title, retrieved_at, checksum, category_hints_json, created_at
            FROM question_source_snapshots
            ORDER BY source_id ASC, retrieved_at DESC, id DESC
            """
        ).fetchall()
        return [_question_source_snapshot(row) for row in rows]

    def add_question_auto_curation_audit(
        self,
        audit: QuestionAutoCurationAudit,
    ) -> QuestionAutoCurationAudit:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO question_auto_curation_audits
                    (
                        question_id,
                        previous_status,
                        decision,
                        resulting_status,
                        confidence,
                        curator_score,
                        rationale,
                        quality_flags_json,
                        duplicate_of_id,
                        curator_source_evidence,
                        curator_model,
                        curator_version,
                        source_url,
                        source_retrieved_at,
                        source_category_hints_json,
                        source_frequency_hint,
                        created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit.question_id,
                    audit.previous_status,
                    audit.decision,
                    audit.resulting_status,
                    audit.confidence,
                    audit.curator_score,
                    audit.rationale,
                    json.dumps(audit.quality_flags, ensure_ascii=False),
                    audit.duplicate_of_id,
                    audit.curator_source_evidence,
                    audit.curator_model,
                    audit.curator_version,
                    audit.source_url,
                    audit.source_retrieved_at.isoformat(timespec="seconds")
                    if audit.source_retrieved_at
                    else None,
                    json.dumps(audit.source_category_hints, ensure_ascii=False),
                    audit.source_frequency_hint,
                    audit.created_at.isoformat(timespec="seconds"),
                ),
            )
        saved = self.get_question_auto_curation_audit(cursor.lastrowid)
        if saved is None:
            raise RuntimeError("Question auto-curation audit was not saved.")
        return saved

    def get_question_auto_curation_audit(self, audit_id: int) -> QuestionAutoCurationAudit | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                question_id,
                previous_status,
                decision,
                resulting_status,
                confidence,
                curator_score,
                rationale,
                quality_flags_json,
                duplicate_of_id,
                curator_source_evidence,
                curator_model,
                curator_version,
                source_url,
                source_retrieved_at,
                source_category_hints_json,
                source_frequency_hint,
                created_at
            FROM question_auto_curation_audits
            WHERE id = ?
            """,
            (audit_id,),
        ).fetchone()
        return _question_auto_curation_audit(row) if row else None

    def list_question_auto_curation_audits(
        self,
        question_id: int | None = None,
        *,
        topic_id: int | None = None,
        resulting_status: str | None = None,
        limit: int | None = None,
    ) -> list[QuestionAutoCurationAudit]:
        conditions = []
        params: list[object] = []
        if question_id is not None:
            conditions.append("a.question_id = ?")
            params.append(question_id)
        if topic_id is not None:
            conditions.append("q.topic_id = ?")
            params.append(topic_id)
        if resulting_status is not None:
            self._validate_question_source_quality_status(resulting_status)
            conditions.append("a.resulting_status = ?")
            params.append(resulting_status)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        limit_sql = ""
        if limit is not None:
            if limit < 1:
                raise ValueError("limit must be positive")
            limit_sql = "LIMIT ?"
            params.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT
                a.id,
                a.question_id,
                a.previous_status,
                a.decision,
                a.resulting_status,
                a.confidence,
                a.curator_score,
                a.rationale,
                a.quality_flags_json,
                a.duplicate_of_id,
                a.curator_source_evidence,
                a.curator_model,
                a.curator_version,
                a.source_url,
                a.source_retrieved_at,
                a.source_category_hints_json,
                a.source_frequency_hint,
                a.created_at
            FROM question_auto_curation_audits a
            JOIN questions q ON q.id = a.question_id
            {where}
            ORDER BY a.created_at DESC, a.id DESC
            {limit_sql}
            """,
            tuple(params),
        ).fetchall()
        return [_question_auto_curation_audit(row) for row in rows]

    def upsert_tag(self, tag: Tag) -> Tag:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO tags (slug, title, description, source)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    source = excluded.source
                """,
                (tag.slug, tag.title, tag.description, tag.source),
            )
        saved = self.find_tag_by_slug(tag.slug)
        if saved is None:
            raise RuntimeError(f"Tag was not saved: {tag.slug}")
        return saved

    def find_tag_by_slug(self, slug: str) -> Tag | None:
        row = self.connection.execute(
            """
            SELECT id, slug, title, description, source
            FROM tags
            WHERE slug = ?
            """,
            (slug,),
        ).fetchone()
        return _tag(row) if row else None

    def list_tags(self) -> list[Tag]:
        rows = self.connection.execute(
            """
            SELECT id, slug, title, description, source
            FROM tags
            ORDER BY title ASC, id ASC
            """
        ).fetchall()
        return [_tag(row) for row in rows]

    def upsert_competency(self, competency: Competency) -> Competency:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO competencies
                    (slug, title, description, category, level, order_index)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    category = excluded.category,
                    level = excluded.level,
                    order_index = excluded.order_index
                """,
                (
                    competency.slug,
                    competency.title,
                    competency.description,
                    competency.category,
                    competency.level,
                    competency.order_index,
                ),
            )
        saved = self.find_competency_by_slug(competency.slug)
        if saved is None:
            raise RuntimeError(f"Competency was not saved: {competency.slug}")
        return saved

    def get_competency(self, competency_id: int) -> Competency | None:
        row = self.connection.execute(
            """
            SELECT id, slug, title, description, category, level, order_index
            FROM competencies
            WHERE id = ?
            """,
            (competency_id,),
        ).fetchone()
        return _competency(row) if row else None

    def find_competency_by_slug(self, slug: str) -> Competency | None:
        row = self.connection.execute(
            """
            SELECT id, slug, title, description, category, level, order_index
            FROM competencies
            WHERE slug = ?
            """,
            (slug,),
        ).fetchone()
        return _competency(row) if row else None

    def list_competencies(self) -> list[Competency]:
        rows = self.connection.execute(
            """
            SELECT id, slug, title, description, category, level, order_index
            FROM competencies
            ORDER BY order_index ASC, id ASC
            """
        ).fetchall()
        return [_competency(row) for row in rows]

    def list_topic_ids_for_competency(self, competency_slug: str) -> list[int]:
        rows = self.connection.execute(
            """
            SELECT DISTINCT q.topic_id
            FROM questions q
            JOIN question_competencies qc ON qc.question_id = q.id
            JOIN competencies c ON c.id = qc.competency_id
            WHERE c.slug = ?
            ORDER BY q.topic_id ASC
            """,
            (competency_slug,),
        ).fetchall()
        return [row["topic_id"] for row in rows]

    def upsert_rubric_dimension(self, dimension: RubricDimension) -> RubricDimension:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO rubric_dimensions
                    (slug, title, description, order_index)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    order_index = excluded.order_index
                """,
                (
                    dimension.slug,
                    dimension.title,
                    dimension.description,
                    dimension.order_index,
                ),
            )
        saved = self.find_rubric_dimension_by_slug(dimension.slug)
        if saved is None:
            raise RuntimeError(f"Rubric dimension was not saved: {dimension.slug}")
        return saved

    def get_rubric_dimension(self, dimension_id: int) -> RubricDimension | None:
        row = self.connection.execute(
            """
            SELECT id, slug, title, description, order_index
            FROM rubric_dimensions
            WHERE id = ?
            """,
            (dimension_id,),
        ).fetchone()
        return _rubric_dimension(row) if row else None

    def find_rubric_dimension_by_slug(self, slug: str) -> RubricDimension | None:
        row = self.connection.execute(
            """
            SELECT id, slug, title, description, order_index
            FROM rubric_dimensions
            WHERE slug = ?
            """,
            (slug,),
        ).fetchone()
        return _rubric_dimension(row) if row else None

    def list_rubric_dimensions(self) -> list[RubricDimension]:
        rows = self.connection.execute(
            """
            SELECT id, slug, title, description, order_index
            FROM rubric_dimensions
            ORDER BY order_index ASC, id ASC
            """
        ).fetchall()
        return [_rubric_dimension(row) for row in rows]

    def upsert_system_design_rubric_dimension(self, dimension: RubricDimension) -> RubricDimension:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO system_design_rubric_dimensions
                    (slug, title, description, order_index)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slug) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    order_index = excluded.order_index
                """,
                (
                    dimension.slug,
                    dimension.title,
                    dimension.description,
                    dimension.order_index,
                ),
            )
        saved = self.find_system_design_rubric_dimension_by_slug(dimension.slug)
        if saved is None:
            raise RuntimeError(f"System design rubric dimension was not saved: {dimension.slug}")
        return saved

    def get_system_design_rubric_dimension(self, dimension_id: int) -> RubricDimension | None:
        row = self.connection.execute(
            """
            SELECT id, slug, title, description, order_index
            FROM system_design_rubric_dimensions
            WHERE id = ?
            """,
            (dimension_id,),
        ).fetchone()
        return _rubric_dimension(row) if row else None

    def find_system_design_rubric_dimension_by_slug(self, slug: str) -> RubricDimension | None:
        row = self.connection.execute(
            """
            SELECT id, slug, title, description, order_index
            FROM system_design_rubric_dimensions
            WHERE slug = ?
            """,
            (slug,),
        ).fetchone()
        return _rubric_dimension(row) if row else None

    def list_system_design_rubric_dimensions(self) -> list[RubricDimension]:
        rows = self.connection.execute(
            """
            SELECT id, slug, title, description, order_index
            FROM system_design_rubric_dimensions
            ORDER BY order_index ASC, id ASC
            """
        ).fetchall()
        return [_rubric_dimension(row) for row in rows]

    def add_answer_evaluation(self, evaluation: AnswerEvaluation) -> AnswerEvaluation:
        for score in evaluation.scores:
            if score.dimension.id is None:
                raise ValueError(
                    f"Rubric dimension must be persisted before scoring: {score.dimension.slug}"
                )
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO answer_evaluations
                    (
                        answer_id,
                        session_id,
                        question_id,
                        summary,
                        next_drills_json,
                        source,
                        raw_payload_json,
                        created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation.answer_id,
                    evaluation.session_id,
                    evaluation.question_id,
                    evaluation.summary,
                    json.dumps(evaluation.next_drills, ensure_ascii=False),
                    evaluation.source,
                    evaluation.raw_payload_json,
                    evaluation.created_at.isoformat(timespec="seconds"),
                ),
            )
            evaluation_id = cursor.lastrowid
            self.connection.executemany(
                """
                INSERT INTO answer_evaluation_scores
                    (evaluation_id, rubric_dimension_id, score, evidence, gaps, next_drill)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        evaluation_id,
                        score.dimension.id,
                        score.score,
                        score.evidence,
                        score.gaps,
                        score.next_drill,
                    )
                    for score in evaluation.scores
                ],
            )
        saved = self.get_answer_evaluation(evaluation_id)
        if saved is None:
            raise RuntimeError(f"Answer evaluation was not saved: {evaluation_id}")
        return saved

    def get_answer_evaluation(self, evaluation_id: int) -> AnswerEvaluation | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                answer_id,
                session_id,
                question_id,
                summary,
                next_drills_json,
                source,
                raw_payload_json,
                created_at
            FROM answer_evaluations
            WHERE id = ?
            """,
            (evaluation_id,),
        ).fetchone()
        if row is None:
            return None
        return _answer_evaluation(row, self._list_answer_evaluation_scores(evaluation_id))

    def list_answer_evaluations_for_answer(self, answer_id: int) -> list[AnswerEvaluation]:
        rows = self.connection.execute(
            """
            SELECT
                id,
                answer_id,
                session_id,
                question_id,
                summary,
                next_drills_json,
                source,
                raw_payload_json,
                created_at
            FROM answer_evaluations
            WHERE answer_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (answer_id,),
        ).fetchall()
        return [_answer_evaluation(row, self._list_answer_evaluation_scores(row["id"])) for row in rows]

    def update_latest_answer_evaluation_feedback_quality(
        self,
        answer_id: int,
        *,
        flags: Sequence[str],
        evidence_terms: Sequence[str] = (),
        fallback_error: str | None = None,
    ) -> AnswerEvaluation | None:
        row = self.connection.execute(
            """
            SELECT id, raw_payload_json
            FROM answer_evaluations
            WHERE answer_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (answer_id,),
        ).fetchone()
        if row is None:
            return None

        payload_json = _evaluation_payload_with_feedback_quality(
            row["raw_payload_json"],
            flags=flags,
            evidence_terms=evidence_terms,
            fallback_error=fallback_error,
        )
        with self.connection:
            self.connection.execute(
                """
                UPDATE answer_evaluations
                SET raw_payload_json = ?
                WHERE id = ?
                """,
                (payload_json, row["id"]),
            )
        return self.get_answer_evaluation(row["id"])

    def override_answer_evaluation_score(
        self,
        evaluation_id: int,
        dimension_slug: str,
        score: int,
        *,
        reason: str | None = None,
        overridden_at: datetime | None = None,
    ) -> AnswerEvaluation | None:
        if score < 1 or score > 5:
            raise ValueError("Manual rubric override score must be between 1 and 5.")
        row = self.connection.execute(
            """
            SELECT aes.evaluation_id, aes.rubric_dimension_id
            FROM answer_evaluation_scores aes
            JOIN rubric_dimensions rd ON rd.id = aes.rubric_dimension_id
            WHERE aes.evaluation_id = ?
              AND rd.slug = ?
            """,
            (evaluation_id, dimension_slug),
        ).fetchone()
        if row is None:
            return None

        override_time = overridden_at or datetime.now()
        clean_reason = reason.strip() if reason else None
        with self.connection:
            self.connection.execute(
                """
                UPDATE answer_evaluation_scores
                SET manual_override_score = ?,
                    manual_override_reason = ?,
                    manual_override_at = ?
                WHERE evaluation_id = ?
                  AND rubric_dimension_id = ?
                """,
                (
                    score,
                    clean_reason,
                    override_time.isoformat(timespec="seconds"),
                    row["evaluation_id"],
                    row["rubric_dimension_id"],
                ),
            )
        return self.get_answer_evaluation(evaluation_id)

    def _list_answer_evaluation_scores(self, evaluation_id: int) -> list[AnswerEvaluationScore]:
        rows = self.connection.execute(
            """
            SELECT
                rd.id,
                rd.slug,
                rd.title,
                rd.description,
                rd.order_index,
                aes.score,
                aes.evidence,
                aes.gaps,
                aes.next_drill,
                aes.manual_override_score,
                aes.manual_override_reason,
                aes.manual_override_at
            FROM answer_evaluation_scores aes
            JOIN rubric_dimensions rd ON rd.id = aes.rubric_dimension_id
            WHERE aes.evaluation_id = ?
            ORDER BY rd.order_index ASC, rd.id ASC
            """,
            (evaluation_id,),
        ).fetchall()
        return [_answer_evaluation_score(row) for row in rows]

    def add_question_competency(
        self,
        question_id: int,
        competency_id: int,
        *,
        is_primary: bool = False,
        weight: float = 1.0,
    ) -> None:
        self._validate_question_competency_weight(weight)
        with self.connection:
            if is_primary:
                self.connection.execute(
                    """
                    UPDATE question_competencies
                    SET is_primary = 0
                    WHERE question_id = ? AND competency_id != ?
                    """,
                    (question_id, competency_id),
                )
            self.connection.execute(
                """
                INSERT INTO question_competencies
                    (question_id, competency_id, is_primary, weight)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(question_id, competency_id) DO UPDATE SET
                    is_primary = excluded.is_primary,
                    weight = excluded.weight
                """,
                (question_id, competency_id, 1 if is_primary else 0, weight),
            )

    def set_question_competencies(self, question_id: int, links: list[QuestionCompetencyLink]) -> None:
        normalized: list[QuestionCompetencyLink] = []
        seen_competency_ids: set[int] = set()
        primary_count = 0
        for link in links:
            competency_id = link.competency.id
            if competency_id is None:
                raise ValueError("Question competency link requires a saved competency id")
            if competency_id in seen_competency_ids:
                continue
            self._validate_question_competency_weight(link.weight)
            if link.is_primary:
                primary_count += 1
            normalized.append(link)
            seen_competency_ids.add(competency_id)

        if primary_count > 1:
            raise ValueError("Only one primary competency can be linked to a question")

        with self.connection:
            self.connection.execute("DELETE FROM question_competencies WHERE question_id = ?", (question_id,))
            for link in normalized:
                self.connection.execute(
                    """
                    INSERT INTO question_competencies
                        (question_id, competency_id, is_primary, weight)
                    VALUES (?, ?, ?, ?)
                    """,
                    (question_id, link.competency.id, 1 if link.is_primary else 0, link.weight),
                )

    def list_question_competencies(self, question_id: int) -> list[QuestionCompetencyLink]:
        rows = self.connection.execute(
            """
            SELECT c.id, c.slug, c.title, c.description, c.category, c.level, c.order_index,
                   qc.is_primary, qc.weight
            FROM competencies c
            JOIN question_competencies qc ON qc.competency_id = c.id
            WHERE qc.question_id = ?
            ORDER BY qc.is_primary DESC, c.order_index ASC, c.id ASC
            """,
            (question_id,),
        ).fetchall()
        return [_question_competency_link(row) for row in rows]

    def competency_practice_metrics(self) -> dict[int, dict]:
        rows = self.connection.execute(
            """
            WITH latest_evaluations AS (
                SELECT ae.id, ae.answer_id
                FROM answer_evaluations ae
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM answer_evaluations newer
                    WHERE newer.answer_id = ae.answer_id
                      AND (
                        newer.created_at > ae.created_at
                        OR (newer.created_at = ae.created_at AND newer.id > ae.id)
                      )
                )
            ),
            rubric_by_answer AS (
                SELECT le.answer_id, AVG(COALESCE(aes.manual_override_score, aes.score)) AS avg_rubric_score
                FROM latest_evaluations le
                JOIN answer_evaluation_scores aes ON aes.evaluation_id = le.id
                GROUP BY le.answer_id
            )
            SELECT
                c.id AS competency_id,
                COUNT(DISTINCT q.id) AS linked_questions,
                COUNT(DISTINCT CASE WHEN qc.is_primary = 1 THEN q.id END) AS primary_questions,
                COUNT(DISTINCT CASE WHEN s.id IS NOT NULL THEN q.id END) AS answered_questions,
                COUNT(DISTINCT CASE WHEN s.id IS NOT NULL THEN a.id END) AS answer_count,
                COUNT(DISTINCT CASE WHEN s.id IS NOT NULL AND rba.answer_id IS NOT NULL THEN a.id END)
                    AS evaluated_answer_count,
                AVG(CASE WHEN s.id IS NOT NULL THEN a.self_score END) AS avg_self_score,
                AVG(CASE WHEN s.id IS NOT NULL THEN rba.avg_rubric_score END) AS avg_rubric_score,
                MAX(CASE WHEN s.id IS NOT NULL THEN a.answered_at END) AS last_answered_at
            FROM competencies c
            LEFT JOIN question_competencies qc ON qc.competency_id = c.id
            LEFT JOIN questions q ON q.id = qc.question_id
            LEFT JOIN answers a ON a.question_id = q.id
            LEFT JOIN sessions s
              ON s.id = a.session_id
             AND COALESCE(s.status, 'completed') <> 'abandoned'
            LEFT JOIN rubric_by_answer rba ON rba.answer_id = a.id
            GROUP BY c.id
            """
        ).fetchall()
        return {row["competency_id"]: dict(row) for row in rows}

    def system_design_practice_metrics(self) -> dict[int, dict]:
        rows = self.connection.execute(
            """
            SELECT
                topic_id,
                COUNT(*) AS transcript_message_count,
                COUNT(CASE WHEN role = 'candidate' THEN 1 END) AS candidate_turn_count,
                COUNT(DISTINCT scenario_id) AS scenario_count,
                MAX(created_at) AS last_practiced_at
            FROM system_design_transcript_messages
            GROUP BY topic_id
            """
        ).fetchall()
        return {row["topic_id"]: dict(row) for row in rows}

    def _validate_question_competency_weight(self, weight: float) -> None:
        if weight <= 0:
            raise ValueError("Question competency link weight must be positive")

    def add_question_tag(self, question_id: int, tag_id: int) -> None:
        with self.connection:
            self.connection.execute(
                """
                INSERT OR IGNORE INTO question_tags (question_id, tag_id)
                VALUES (?, ?)
                """,
                (question_id, tag_id),
            )

    def set_question_tags(self, question_id: int, tag_ids: list[int]) -> None:
        with self.connection:
            self.connection.execute("DELETE FROM question_tags WHERE question_id = ?", (question_id,))
            for tag_id in dict.fromkeys(tag_ids):
                self.connection.execute(
                    """
                    INSERT INTO question_tags (question_id, tag_id)
                    VALUES (?, ?)
                    """,
                    (question_id, tag_id),
                )

    def list_question_tags(self, question_id: int) -> list[Tag]:
        rows = self.connection.execute(
            """
            SELECT t.id, t.slug, t.title, t.description, t.source
            FROM tags t
            JOIN question_tags qt ON qt.tag_id = t.id
            WHERE qt.question_id = ?
            ORDER BY t.title ASC, t.id ASC
            """,
            (question_id,),
        ).fetchall()
        return [_tag(row) for row in rows]

    def create_session(self, session: Session) -> Session:
        if session.status not in SESSION_STATUSES:
            raise ValueError(f"Unknown session status: {session.status}")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO sessions (topic_id, started_at, ended_at, status, target_minutes)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session.topic_id,
                    session.started_at.isoformat(timespec="seconds"),
                    session.ended_at.isoformat(timespec="seconds") if session.ended_at else None,
                    session.status,
                    session.target_minutes,
                ),
            )
        return Session(
            id=cursor.lastrowid,
            topic_id=session.topic_id,
            started_at=session.started_at,
            ended_at=session.ended_at,
            target_minutes=session.target_minutes,
            status=session.status,
        )

    def finish_session(self, session_id: int, ended_at: datetime) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE sessions SET ended_at = ?, status = ? WHERE id = ?",
                (ended_at.isoformat(timespec="seconds"), SESSION_STATUS_COMPLETED, session_id),
            )

    def abandon_session(self, session_id: int, ended_at: datetime) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE sessions SET ended_at = ?, status = ? WHERE id = ?",
                (ended_at.isoformat(timespec="seconds"), SESSION_STATUS_ABANDONED, session_id),
            )

    def get_session(self, session_id: int) -> Session | None:
        row = self.connection.execute(
            "SELECT id, topic_id, started_at, ended_at, status, target_minutes FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return None
        return Session(
            id=row["id"],
            topic_id=row["topic_id"],
            started_at=_dt(row["started_at"]),
            ended_at=_dt(row["ended_at"]) if row["ended_at"] else None,
            target_minutes=row["target_minutes"],
            status=_session_status(row),
        )

    def upsert_session_outcome(self, outcome: SessionOutcome) -> SessionOutcome:
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO session_outcomes
                    (
                        session_id,
                        outcome_type,
                        summary,
                        strengths_json,
                        gaps_json,
                        next_drills_json,
                        readiness_delta,
                        created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    outcome_type = excluded.outcome_type,
                    summary = excluded.summary,
                    strengths_json = excluded.strengths_json,
                    gaps_json = excluded.gaps_json,
                    next_drills_json = excluded.next_drills_json,
                    readiness_delta = excluded.readiness_delta,
                    created_at = excluded.created_at
                """,
                (
                    outcome.session_id,
                    outcome.outcome_type,
                    outcome.summary,
                    json.dumps(outcome.strengths, ensure_ascii=False),
                    json.dumps(outcome.gaps, ensure_ascii=False),
                    json.dumps(outcome.next_drills, ensure_ascii=False),
                    outcome.readiness_delta,
                    outcome.created_at.isoformat(timespec="seconds"),
                ),
            )
        saved = self.get_session_outcome_for_session(outcome.session_id)
        if saved is None:
            raise RuntimeError(f"Session outcome was not saved for session: {outcome.session_id}")
        return saved

    def get_session_outcome(self, outcome_id: int) -> SessionOutcome | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                session_id,
                outcome_type,
                summary,
                strengths_json,
                gaps_json,
                next_drills_json,
                readiness_delta,
                created_at
            FROM session_outcomes
            WHERE id = ?
            """,
            (outcome_id,),
        ).fetchone()
        return _session_outcome(row) if row else None

    def get_session_outcome_for_session(self, session_id: int) -> SessionOutcome | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                session_id,
                outcome_type,
                summary,
                strengths_json,
                gaps_json,
                next_drills_json,
                readiness_delta,
                created_at
            FROM session_outcomes
            WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        return _session_outcome(row) if row else None

    def get_latest_completed_session_outcome_by_type(self, outcome_type: str) -> dict | None:
        row = self.connection.execute(
            """
            SELECT
                so.id,
                so.session_id,
                so.outcome_type,
                so.summary,
                so.strengths_json,
                so.gaps_json,
                so.next_drills_json,
                so.readiness_delta,
                so.created_at,
                s.started_at,
                s.ended_at
            FROM session_outcomes so
            JOIN sessions s ON s.id = so.session_id
            WHERE s.ended_at IS NOT NULL
              AND s.status = 'completed'
              AND so.outcome_type = ?
            ORDER BY s.ended_at DESC, s.id DESC
            LIMIT 1
            """,
            (outcome_type,),
        ).fetchone()
        return dict(row) if row else None

    def list_completed_session_outcomes_for_readiness_trend(self, limit: int = 200) -> list[dict]:
        if limit <= 0:
            return []
        rows = self.connection.execute(
            """
            SELECT
                so.session_id,
                so.outcome_type,
                so.readiness_delta,
                so.created_at AS outcome_created_at,
                s.started_at,
                s.ended_at
            FROM session_outcomes so
            JOIN sessions s ON s.id = so.session_id
            WHERE s.ended_at IS NOT NULL
              AND s.status = 'completed'
            ORDER BY s.ended_at DESC, s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def list_completed_practice_sessions(self, limit: int = 30) -> list[PracticeSessionSummary]:
        rows = self.connection.execute(
            """
            SELECT
                s.id,
                s.topic_id,
                t.title AS topic_title,
                s.started_at,
                s.ended_at,
                s.target_minutes,
                COUNT(a.id) AS answer_count,
                AVG(a.self_score) AS avg_self_score
            FROM sessions s
            LEFT JOIN topics t ON t.id = s.topic_id
            LEFT JOIN answers a ON a.session_id = s.id
            WHERE s.ended_at IS NOT NULL
              AND s.status = 'completed'
            GROUP BY s.id
            ORDER BY s.started_at DESC, s.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_practice_session_summary(row) for row in rows]

    def get_completed_practice_session_summary(self, session_id: int) -> PracticeSessionSummary | None:
        row = self.connection.execute(
            """
            SELECT
                s.id,
                s.topic_id,
                t.title AS topic_title,
                s.started_at,
                s.ended_at,
                s.target_minutes,
                COUNT(a.id) AS answer_count,
                AVG(a.self_score) AS avg_self_score
            FROM sessions s
            LEFT JOIN topics t ON t.id = s.topic_id
            LEFT JOIN answers a ON a.session_id = s.id
            WHERE s.id = ? AND s.ended_at IS NOT NULL AND s.status = 'completed'
            GROUP BY s.id
            """,
            (session_id,),
        ).fetchone()
        return _practice_session_summary(row) if row else None

    def list_practice_session_answer_details(self, session_id: int) -> list[PracticeSessionAnswerDetail]:
        rows = self.connection.execute(
            """
            SELECT
                a.id AS answer_id,
                q.id AS question_id,
                q.difficulty AS question_difficulty,
                q.prompt AS question_prompt,
                a.user_answer,
                a.self_score,
                q.reference_answer,
                a.ai_feedback,
                a.answered_at
            FROM answers a
            JOIN questions q ON q.id = a.question_id
            WHERE a.session_id = ?
            ORDER BY a.answered_at ASC, a.id ASC
            """,
            (session_id,),
        ).fetchall()
        return [_practice_session_answer_detail(row) for row in rows]

    def add_answer(self, answer: Answer) -> Answer:
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO answers (session_id, question_id, user_answer, self_score, ai_feedback, answered_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    answer.session_id,
                    answer.question_id,
                    answer.user_answer,
                    answer.self_score,
                    answer.ai_feedback,
                    answer.answered_at.isoformat(timespec="seconds"),
                ),
            )
        return Answer(
            id=cursor.lastrowid,
            session_id=answer.session_id,
            question_id=answer.question_id,
            user_answer=answer.user_answer,
            self_score=answer.self_score,
            ai_feedback=answer.ai_feedback,
            answered_at=answer.answered_at,
        )

    def update_answer_feedback(self, answer_id: int, ai_feedback: str) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE answers SET ai_feedback = ? WHERE id = ?",
                (ai_feedback, answer_id),
            )

    def update_answer_score(self, answer_id: int, self_score: int | None) -> None:
        with self.connection:
            self.connection.execute(
                "UPDATE answers SET self_score = ? WHERE id = ?",
                (self_score, answer_id),
            )

    def answered_question_ids_for_session(self, session_id: int) -> set[int]:
        rows = self.connection.execute(
            "SELECT question_id FROM answers WHERE session_id = ?",
            (session_id,),
        ).fetchall()
        return {row["question_id"] for row in rows}

    def count_answers_for_session(self, session_id: int) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) AS c FROM answers WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        return int(row["c"])

    def create_content_generation_job(self, kind: str, payload_json: str) -> ContentGenerationJob:
        now = datetime.now().isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO content_generation_jobs
                    (kind, status, payload_json, result_json, error, created_at, updated_at)
                VALUES (?, 'queued', ?, NULL, NULL, ?, ?)
                """,
                (kind, payload_json, now, now),
            )
        job = self.get_content_generation_job(cursor.lastrowid)
        if job is None:
            raise RuntimeError("Content generation job was not saved")
        return job

    def get_content_generation_job(self, job_id: int) -> ContentGenerationJob | None:
        row = self.connection.execute(
            """
            SELECT id, kind, status, payload_json, result_json, error, created_at, updated_at
            FROM content_generation_jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()
        return _job(row) if row else None

    def list_content_generation_jobs(
        self,
        status: str | None = None,
        limit: int = 20,
    ) -> list[ContentGenerationJob]:
        if status:
            rows = self.connection.execute(
                """
                SELECT id, kind, status, payload_json, result_json, error, created_at, updated_at
                FROM content_generation_jobs
                WHERE status = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (status, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT id, kind, status, payload_json, result_json, error, created_at, updated_at
                FROM content_generation_jobs
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_job(row) for row in rows]

    def next_queued_content_generation_job(self) -> ContentGenerationJob | None:
        row = self.connection.execute(
            """
            SELECT id, kind, status, payload_json, result_json, error, created_at, updated_at
            FROM content_generation_jobs
            WHERE status = 'queued'
            ORDER BY created_at ASC, id ASC
            LIMIT 1
            """
        ).fetchone()
        return _job(row) if row else None

    def list_queued_content_generation_jobs(self, limit: int = 100) -> list[ContentGenerationJob]:
        rows = self.connection.execute(
            """
            SELECT id, kind, status, payload_json, result_json, error, created_at, updated_at
            FROM content_generation_jobs
            WHERE status = 'queued'
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_job(row) for row in rows]

    def update_content_generation_job(
        self,
        job_id: int,
        status: str,
        result_json: str | None = None,
        error: str | None = None,
    ) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE content_generation_jobs
                SET status = ?, result_json = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, result_json, error, datetime.now().isoformat(timespec="seconds"), job_id),
            )

    def update_content_generation_job_payload(self, job_id: int, payload_json: str) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE content_generation_jobs
                SET payload_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (payload_json, datetime.now().isoformat(timespec="seconds"), job_id),
            )

    def retry_content_generation_job(self, job_id: int) -> None:
        with self.connection:
            self.connection.execute(
                """
                UPDATE content_generation_jobs
                SET status = 'queued', result_json = NULL, error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (datetime.now().isoformat(timespec="seconds"), job_id),
            )

    def add_learning_material(self, material: LearningMaterial) -> LearningMaterial:
        created_at = material.created_at.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO learning_materials (topic_id, title, body, source, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (material.topic_id, material.title, material.body, material.source, created_at),
            )
        return LearningMaterial(
            id=cursor.lastrowid,
            topic_id=material.topic_id,
            title=material.title,
            body=material.body,
            source=material.source,
            created_at=material.created_at,
            archived_at=None,
            archive_reason=None,
        )

    def latest_learning_material(self, topic_id: int) -> LearningMaterial | None:
        row = self.connection.execute(
            """
            SELECT id, topic_id, title, body, source, created_at, archived_at, archive_reason
            FROM learning_materials
            WHERE topic_id = ? AND archived_at IS NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (topic_id,),
        ).fetchone()
        return _learning_material(row) if row else None

    def get_learning_material(self, material_id: int, include_archived: bool = False) -> LearningMaterial | None:
        archived_filter = "" if include_archived else "AND archived_at IS NULL"
        row = self.connection.execute(
            f"""
            SELECT id, topic_id, title, body, source, created_at, archived_at, archive_reason
            FROM learning_materials
            WHERE id = ? {archived_filter}
            """,
            (material_id,),
        ).fetchone()
        return _learning_material(row) if row else None

    def list_learning_materials(
        self,
        topic_id: int | None = None,
        limit: int = 20,
    ) -> list[LearningMaterial]:
        if topic_id is None:
            rows = self.connection.execute(
                """
                SELECT id, topic_id, title, body, source, created_at, archived_at, archive_reason
                FROM learning_materials
                WHERE archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT id, topic_id, title, body, source, created_at, archived_at, archive_reason
                FROM learning_materials
                WHERE topic_id = ? AND archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (topic_id, limit),
            ).fetchall()
        return [_learning_material(row) for row in rows]

    def archive_learning_material(self, material_id: int, reason: str | None = None) -> bool:
        archived_at = datetime.now().isoformat(timespec="seconds")
        archive_reason = reason.strip() if reason and reason.strip() else None
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE learning_materials
                SET archived_at = ?, archive_reason = ?
                WHERE id = ? AND archived_at IS NULL
                """,
                (archived_at, archive_reason, material_id),
            )
        return cursor.rowcount > 0

    def add_learning_dialog_message(self, message: LearningDialogMessage) -> LearningDialogMessage:
        created_at = message.created_at.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO learning_dialog_messages
                    (topic_id, dialog_session_id, context_type, context_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.topic_id,
                    message.dialog_session_id,
                    message.context_type,
                    message.context_id,
                    message.role,
                    message.content,
                    created_at,
                ),
            )
        return LearningDialogMessage(
            id=cursor.lastrowid,
            topic_id=message.topic_id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
            dialog_session_id=message.dialog_session_id,
            context_type=message.context_type,
            context_id=message.context_id,
        )

    def list_learning_dialog_messages(
        self,
        topic_id: int,
        limit: int = 20,
    ) -> list[LearningDialogMessage]:
        rows = self.connection.execute(
            """
            SELECT id, topic_id, dialog_session_id, context_type, context_id, role, content, created_at
            FROM learning_dialog_messages
            WHERE topic_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (topic_id, limit),
        ).fetchall()
        return [_learning_dialog_message(row) for row in reversed(rows)]

    def list_learning_dialog_messages_for_date(
        self,
        topic_id: int,
        dialog_date: str,
    ) -> list[LearningDialogMessage]:
        rows = self.connection.execute(
            """
            SELECT id, topic_id, dialog_session_id, context_type, context_id, role, content, created_at
            FROM learning_dialog_messages
            WHERE topic_id = ? AND date(created_at) = ?
            ORDER BY created_at ASC, id ASC
            """,
            (topic_id, dialog_date),
        ).fetchall()
        return [_learning_dialog_message(row) for row in rows]

    def list_learning_dialog_messages_for_session(self, dialog_session_id: str) -> list[LearningDialogMessage]:
        rows = self.connection.execute(
            """
            SELECT id, topic_id, dialog_session_id, context_type, context_id, role, content, created_at
            FROM learning_dialog_messages
            WHERE dialog_session_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (dialog_session_id,),
        ).fetchall()
        return [_learning_dialog_message(row) for row in rows]

    def list_learning_dialog_summaries(self, limit: int = 30) -> list[LearningDialogSummary]:
        rows = self.connection.execute(
            """
            SELECT
                messages.topic_id,
                COALESCE(topics.title, '') AS topic_title,
                COALESCE(
                    messages.dialog_session_id,
                    'legacy:' || messages.topic_id || ':' || date(messages.created_at)
                ) AS dialog_session_id,
                MAX(messages.context_type) AS context_type,
                MAX(messages.context_id) AS context_id,
                date(messages.created_at) AS dialog_date,
                MIN(messages.created_at) AS first_message_at,
                MAX(messages.created_at) AS last_message_at,
                COUNT(*) AS message_count
            FROM learning_dialog_messages AS messages
            LEFT JOIN topics ON topics.id = messages.topic_id
            GROUP BY
                messages.topic_id,
                date(messages.created_at),
                COALESCE(
                    messages.dialog_session_id,
                    'legacy:' || messages.topic_id || ':' || date(messages.created_at)
                )
            ORDER BY last_message_at DESC, topic_title ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [_learning_dialog_summary(row) for row in rows]

    def add_notebook_entry(self, entry: NotebookEntry) -> NotebookEntry:
        created_at = entry.created_at.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO notebook_entries
                    (
                        topic_id,
                        curriculum_subtopic_id,
                        dialog_session_id,
                        source_message_id,
                        title,
                        body,
                        source,
                        created_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.topic_id,
                    entry.curriculum_subtopic_id,
                    entry.dialog_session_id,
                    entry.source_message_id,
                    entry.title,
                    entry.body,
                    entry.source,
                    created_at,
                ),
            )
        return NotebookEntry(
            id=cursor.lastrowid,
            topic_id=entry.topic_id,
            curriculum_subtopic_id=entry.curriculum_subtopic_id,
            dialog_session_id=entry.dialog_session_id,
            source_message_id=entry.source_message_id,
            title=entry.title,
            body=entry.body,
            source=entry.source,
            created_at=entry.created_at,
        )

    def list_notebook_entries(
        self,
        topic_id: int | None = None,
        curriculum_subtopic_id: int | None = None,
        dialog_session_id: str | None = None,
        source_message_id: int | None = None,
        limit: int = 50,
    ) -> list[NotebookEntry]:
        filters: list[str] = []
        params: list[object] = []
        if topic_id is not None:
            filters.append("topic_id = ?")
            params.append(topic_id)
        if curriculum_subtopic_id is not None:
            filters.append("curriculum_subtopic_id = ?")
            params.append(curriculum_subtopic_id)
        if dialog_session_id is not None:
            filters.append("dialog_session_id = ?")
            params.append(dialog_session_id)
        if source_message_id is not None:
            filters.append("source_message_id = ?")
            params.append(source_message_id)
        params.append(limit)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.connection.execute(
            f"""
            SELECT
                id,
                topic_id,
                curriculum_subtopic_id,
                dialog_session_id,
                source_message_id,
                title,
                body,
                source,
                created_at
            FROM notebook_entries
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_notebook_entry(row) for row in rows]

    def add_manual_note(self, note: ManualNote) -> ManualNote:
        created_at = note.created_at.isoformat(timespec="seconds")
        updated_at = note.updated_at.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO manual_notes
                    (
                        topic_id,
                        session_id,
                        context_type,
                        context_id,
                        title,
                        body,
                        created_at,
                        updated_at
                    )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    note.topic_id,
                    note.session_id,
                    note.context_type,
                    note.context_id,
                    note.title,
                    note.body,
                    created_at,
                    updated_at,
                ),
            )
        return ManualNote(
            id=cursor.lastrowid,
            topic_id=note.topic_id,
            session_id=note.session_id,
            context_type=note.context_type,
            context_id=note.context_id,
            title=note.title,
            body=note.body,
            created_at=note.created_at,
            updated_at=note.updated_at,
        )

    def upsert_manual_note_by_context(self, note: ManualNote) -> ManualNote:
        if note.context_type is None or note.context_id is None:
            return self.add_manual_note(note)
        existing = self.connection.execute(
            """
            SELECT
                id,
                topic_id,
                session_id,
                context_type,
                context_id,
                title,
                body,
                created_at,
                updated_at
            FROM manual_notes
            WHERE context_type = ?
              AND context_id = ?
              AND title = ?
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (note.context_type, note.context_id, note.title),
        ).fetchone()
        if existing is None:
            return self.add_manual_note(note)

        updated_at = note.updated_at.isoformat(timespec="seconds")
        with self.connection:
            self.connection.execute(
                """
                UPDATE manual_notes
                SET
                    topic_id = ?,
                    session_id = ?,
                    body = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    note.topic_id,
                    note.session_id,
                    note.body,
                    updated_at,
                    existing["id"],
                ),
            )
        return ManualNote(
            id=existing["id"],
            topic_id=note.topic_id,
            session_id=note.session_id,
            context_type=note.context_type,
            context_id=note.context_id,
            title=note.title,
            body=note.body,
            created_at=_dt(existing["created_at"]),
            updated_at=note.updated_at,
        )

    def get_manual_note(self, note_id: int) -> ManualNote | None:
        row = self.connection.execute(
            """
            SELECT
                id,
                topic_id,
                session_id,
                context_type,
                context_id,
                title,
                body,
                created_at,
                updated_at
            FROM manual_notes
            WHERE id = ?
            """,
            (note_id,),
        ).fetchone()
        return _manual_note(row) if row else None

    def list_manual_notes(
        self,
        topic_id: int | None = None,
        session_id: int | None = None,
        context_type: str | None = None,
        context_id: str | None = None,
        limit: int = 50,
    ) -> list[ManualNote]:
        filters: list[str] = []
        params: list[object] = []
        if topic_id is not None:
            filters.append("topic_id = ?")
            params.append(topic_id)
        if session_id is not None:
            filters.append("session_id = ?")
            params.append(session_id)
        if context_type is not None:
            filters.append("context_type = ?")
            params.append(context_type)
        if context_id is not None:
            filters.append("context_id = ?")
            params.append(context_id)
        params.append(limit)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.connection.execute(
            f"""
            SELECT
                id,
                topic_id,
                session_id,
                context_type,
                context_id,
                title,
                body,
                created_at,
                updated_at
            FROM manual_notes
            {where}
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_manual_note(row) for row in rows]

    def add_system_design_scenario(self, scenario: SystemDesignScenario) -> SystemDesignScenario:
        created_at = scenario.created_at.isoformat(timespec="seconds")
        focus_areas_json = json.dumps(scenario.focus_areas, ensure_ascii=False)
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO system_design_scenarios
                    (topic_id, title, scenario, focus_areas_json, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    scenario.topic_id,
                    scenario.title,
                    scenario.scenario,
                    focus_areas_json,
                    scenario.source,
                    created_at,
                ),
            )
        return SystemDesignScenario(
            id=cursor.lastrowid,
            topic_id=scenario.topic_id,
            title=scenario.title,
            scenario=scenario.scenario,
            focus_areas=scenario.focus_areas,
            source=scenario.source,
            created_at=scenario.created_at,
            archived_at=None,
            archive_reason=None,
        )

    def latest_system_design_scenario(self, topic_id: int) -> SystemDesignScenario | None:
        row = self.connection.execute(
            """
            SELECT id, topic_id, title, scenario, focus_areas_json, source, created_at, archived_at, archive_reason
            FROM system_design_scenarios
            WHERE topic_id = ? AND archived_at IS NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (topic_id,),
        ).fetchone()
        return _system_design_scenario(row) if row else None

    def get_system_design_scenario(
        self,
        scenario_id: int,
        include_archived: bool = False,
    ) -> SystemDesignScenario | None:
        archived_filter = "" if include_archived else "AND archived_at IS NULL"
        row = self.connection.execute(
            f"""
            SELECT id, topic_id, title, scenario, focus_areas_json, source, created_at, archived_at, archive_reason
            FROM system_design_scenarios
            WHERE id = ? {archived_filter}
            """,
            (scenario_id,),
        ).fetchone()
        return _system_design_scenario(row) if row else None

    def list_system_design_scenarios(
        self,
        topic_id: int | None = None,
        limit: int = 20,
    ) -> list[SystemDesignScenario]:
        if topic_id is None:
            rows = self.connection.execute(
                """
                SELECT id, topic_id, title, scenario, focus_areas_json, source, created_at, archived_at, archive_reason
                FROM system_design_scenarios
                WHERE archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT id, topic_id, title, scenario, focus_areas_json, source, created_at, archived_at, archive_reason
                FROM system_design_scenarios
                WHERE topic_id = ? AND archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (topic_id, limit),
            ).fetchall()
        return [_system_design_scenario(row) for row in rows]

    def archive_system_design_scenario(self, scenario_id: int, reason: str | None = None) -> bool:
        archived_at = datetime.now().isoformat(timespec="seconds")
        archive_reason = reason.strip() if reason and reason.strip() else None
        with self.connection:
            cursor = self.connection.execute(
                """
                UPDATE system_design_scenarios
                SET archived_at = ?, archive_reason = ?
                WHERE id = ? AND archived_at IS NULL
                """,
                (archived_at, archive_reason, scenario_id),
            )
        return cursor.rowcount > 0

    def add_system_design_transcript_message(
        self,
        message: SystemDesignTranscriptMessage,
    ) -> SystemDesignTranscriptMessage:
        created_at = message.created_at.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO system_design_transcript_messages
                    (topic_id, scenario_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message.topic_id,
                    message.scenario_id,
                    message.role,
                    message.content,
                    created_at,
                ),
            )
        return SystemDesignTranscriptMessage(
            id=cursor.lastrowid,
            topic_id=message.topic_id,
            scenario_id=message.scenario_id,
            role=message.role,
            content=message.content,
            created_at=message.created_at,
        )

    def list_system_design_transcript_messages(
        self,
        topic_id: int,
        scenario_id: int | None = None,
        limit: int = 50,
    ) -> list[SystemDesignTranscriptMessage]:
        if scenario_id is None:
            rows = self.connection.execute(
                """
                SELECT id, topic_id, scenario_id, role, content, created_at
                FROM system_design_transcript_messages
                WHERE topic_id = ? AND scenario_id IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (topic_id, limit),
            ).fetchall()
        else:
            rows = self.connection.execute(
                """
                SELECT id, topic_id, scenario_id, role, content, created_at
                FROM system_design_transcript_messages
                WHERE topic_id = ? AND scenario_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (topic_id, scenario_id, limit),
            ).fetchall()
        return [_system_design_transcript_message(row) for row in reversed(rows)]

    def add_system_design_artifact(self, artifact: SystemDesignArtifact) -> SystemDesignArtifact:
        created_at = artifact.created_at.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO system_design_artifacts
                    (topic_id, scenario_id, section, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    artifact.topic_id,
                    artifact.scenario_id,
                    artifact.section,
                    artifact.content,
                    created_at,
                ),
            )
        return SystemDesignArtifact(
            id=cursor.lastrowid,
            topic_id=artifact.topic_id,
            scenario_id=artifact.scenario_id,
            section=artifact.section,
            content=artifact.content,
            created_at=artifact.created_at,
        )

    def list_system_design_artifacts(
        self,
        topic_id: int,
        scenario_id: int | None = None,
        section: str | None = None,
        limit: int = 50,
    ) -> list[SystemDesignArtifact]:
        filters = ["topic_id = ?"]
        params: list[object] = [topic_id]
        if scenario_id is None:
            filters.append("scenario_id IS NULL")
        else:
            filters.append("scenario_id = ?")
            params.append(scenario_id)
        if section is not None:
            filters.append("section = ?")
            params.append(section)
        params.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT id, topic_id, scenario_id, section, content, created_at
            FROM system_design_artifacts
            WHERE {" AND ".join(filters)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_system_design_artifact(row) for row in reversed(rows)]

    def add_system_design_feedback_artifact(
        self,
        artifact: SystemDesignFeedbackArtifact,
    ) -> SystemDesignFeedbackArtifact:
        created_at = artifact.created_at.isoformat(timespec="seconds")
        with self.connection:
            cursor = self.connection.execute(
                """
                INSERT INTO system_design_feedback_artifacts
                    (topic_id, scenario_id, session_id, content, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.topic_id,
                    artifact.scenario_id,
                    artifact.session_id,
                    artifact.content,
                    artifact.source,
                    created_at,
                ),
            )
        return SystemDesignFeedbackArtifact(
            id=cursor.lastrowid,
            topic_id=artifact.topic_id,
            scenario_id=artifact.scenario_id,
            session_id=artifact.session_id,
            content=artifact.content,
            source=artifact.source,
            created_at=artifact.created_at,
        )

    def get_system_design_feedback_artifact(
        self,
        feedback_artifact_id: int,
    ) -> SystemDesignFeedbackArtifact | None:
        row = self.connection.execute(
            """
            SELECT id, topic_id, scenario_id, session_id, content, source, created_at
            FROM system_design_feedback_artifacts
            WHERE id = ?
            """,
            (feedback_artifact_id,),
        ).fetchone()
        return _system_design_feedback_artifact(row) if row else None

    def list_system_design_feedback_artifacts(
        self,
        topic_id: int,
        scenario_id: int | None = None,
        session_id: int | None = None,
        limit: int = 20,
    ) -> list[SystemDesignFeedbackArtifact]:
        filters = ["topic_id = ?"]
        params: list[object] = [topic_id]
        if scenario_id is not None:
            filters.append("scenario_id = ?")
            params.append(scenario_id)
        if session_id is not None:
            filters.append("session_id = ?")
            params.append(session_id)
        params.append(limit)
        rows = self.connection.execute(
            f"""
            SELECT id, topic_id, scenario_id, session_id, content, source, created_at
            FROM system_design_feedback_artifacts
            WHERE {" AND ".join(filters)}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [_system_design_feedback_artifact(row) for row in reversed(rows)]

    def add_system_design_evaluation(
        self,
        evaluation: SystemDesignEvaluation,
    ) -> SystemDesignEvaluation:
        for score in evaluation.scores:
            if score.dimension.id is None:
                raise ValueError(
                    f"System design rubric dimension must be persisted before scoring: {score.dimension.slug}"
                )

        existing = self.get_system_design_evaluation_for_feedback(evaluation.feedback_artifact_id)
        with self.connection:
            if existing is None:
                cursor = self.connection.execute(
                    """
                    INSERT INTO system_design_evaluations
                        (
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
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evaluation.feedback_artifact_id,
                        evaluation.topic_id,
                        evaluation.scenario_id,
                        evaluation.session_id,
                        evaluation.summary,
                        json.dumps(evaluation.next_drills, ensure_ascii=False),
                        evaluation.source,
                        evaluation.raw_payload_json,
                        evaluation.created_at.isoformat(timespec="seconds"),
                    ),
                )
                evaluation_id = cursor.lastrowid
            else:
                evaluation_id = existing.id or 0
                self.connection.execute(
                    """
                    UPDATE system_design_evaluations
                    SET topic_id = ?,
                        scenario_id = ?,
                        session_id = ?,
                        summary = ?,
                        next_drills_json = ?,
                        source = ?,
                        raw_payload_json = ?,
                        created_at = ?
                    WHERE id = ?
                    """,
                    (
                        evaluation.topic_id,
                        evaluation.scenario_id,
                        evaluation.session_id,
                        evaluation.summary,
                        json.dumps(evaluation.next_drills, ensure_ascii=False),
                        evaluation.source,
                        evaluation.raw_payload_json,
                        evaluation.created_at.isoformat(timespec="seconds"),
                        evaluation_id,
                    ),
                )
                self.connection.execute(
                    "DELETE FROM system_design_evaluation_scores WHERE evaluation_id = ?",
                    (evaluation_id,),
                )

            self.connection.executemany(
                """
                INSERT INTO system_design_evaluation_scores
                    (
                        evaluation_id,
                        system_design_rubric_dimension_id,
                        score,
                        evidence,
                        gaps,
                        next_drill
                    )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        evaluation_id,
                        score.dimension.id,
                        score.score,
                        score.evidence,
                        score.gaps,
                        score.next_drill,
                    )
                    for score in evaluation.scores
                ],
            )
        saved = self.get_system_design_evaluation(evaluation_id)
        if saved is None:
            raise RuntimeError(f"System design evaluation was not saved: {evaluation_id}")
        return saved

    def get_system_design_evaluation(self, evaluation_id: int) -> SystemDesignEvaluation | None:
        row = self.connection.execute(
            """
            SELECT
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
            FROM system_design_evaluations
            WHERE id = ?
            """,
            (evaluation_id,),
        ).fetchone()
        if row is None:
            return None
        return _system_design_evaluation(row, self._list_system_design_evaluation_scores(evaluation_id))

    def get_system_design_evaluation_for_feedback(
        self,
        feedback_artifact_id: int,
    ) -> SystemDesignEvaluation | None:
        row = self.connection.execute(
            """
            SELECT
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
            FROM system_design_evaluations
            WHERE feedback_artifact_id = ?
            """,
            (feedback_artifact_id,),
        ).fetchone()
        if row is None:
            return None
        return _system_design_evaluation(row, self._list_system_design_evaluation_scores(row["id"]))

    def list_system_design_evaluations(
        self,
        topic_id: int | None = None,
        scenario_id: int | None = None,
        session_id: int | None = None,
        limit: int = 20,
    ) -> list[SystemDesignEvaluation]:
        filters: list[str] = []
        params: list[object] = []
        if topic_id is not None:
            filters.append("topic_id = ?")
            params.append(topic_id)
        if scenario_id is not None:
            filters.append("scenario_id = ?")
            params.append(scenario_id)
        if session_id is not None:
            filters.append("session_id = ?")
            params.append(session_id)
        params.append(limit)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        rows = self.connection.execute(
            f"""
            SELECT
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
            FROM system_design_evaluations
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [
            _system_design_evaluation(row, self._list_system_design_evaluation_scores(row["id"]))
            for row in rows
        ]

    def _list_system_design_evaluation_scores(
        self,
        evaluation_id: int,
    ) -> list[AnswerEvaluationScore]:
        rows = self.connection.execute(
            """
            SELECT
                rd.id,
                rd.slug,
                rd.title,
                rd.description,
                rd.order_index,
                sdes.score,
                sdes.evidence,
                sdes.gaps,
                sdes.next_drill,
                NULL AS manual_override_score,
                NULL AS manual_override_reason,
                NULL AS manual_override_at
            FROM system_design_evaluation_scores sdes
            JOIN system_design_rubric_dimensions rd
              ON rd.id = sdes.system_design_rubric_dimension_id
            WHERE sdes.evaluation_id = ?
            ORDER BY rd.order_index ASC, rd.id ASC
            """,
            (evaluation_id,),
        ).fetchall()
        return [_answer_evaluation_score(row) for row in rows]

    def stats(self) -> dict:
        session_count = self.connection.execute(
            """
            SELECT COUNT(*) AS c
            FROM sessions
            WHERE COALESCE(status, 'completed') <> 'abandoned'
            """
        ).fetchone()["c"]
        answered_count = self.connection.execute(
            """
            SELECT COUNT(*) AS c
            FROM answers a
            JOIN sessions s ON s.id = a.session_id
            WHERE COALESCE(s.status, 'completed') <> 'abandoned'
            """
        ).fetchone()["c"]
        avg_score = self.connection.execute(
            """
            SELECT AVG(a.self_score) AS v
            FROM answers a
            JOIN sessions s ON s.id = a.session_id
            WHERE COALESCE(s.status, 'completed') <> 'abandoned'
            """
        ).fetchone()["v"]
        weak_topics = self.connection.execute(
            """
            SELECT t.title, COUNT(a.id) AS answers, AVG(a.self_score) AS avg_score
            FROM answers a
            JOIN sessions s ON s.id = a.session_id
            JOIN questions q ON q.id = a.question_id
            JOIN topics t ON t.id = q.topic_id
            WHERE a.self_score IS NOT NULL
              AND COALESCE(s.status, 'completed') <> 'abandoned'
            GROUP BY t.id
            ORDER BY avg_score ASC, answers DESC, t.title ASC
            LIMIT 5
            """
        ).fetchall()
        recent_sessions = self.connection.execute(
            """
            SELECT
                s.id,
                s.started_at,
                s.ended_at,
                s.status,
                s.target_minutes,
                t.title AS topic_title,
                COUNT(a.id) AS answers
            FROM sessions s
            LEFT JOIN topics t ON t.id = s.topic_id
            LEFT JOIN answers a ON a.session_id = s.id
            GROUP BY s.id
            ORDER BY s.started_at DESC
            LIMIT 5
            """
        ).fetchall()
        topic_dynamics = self.connection.execute(
            """
            SELECT
                t.title,
                COUNT(s.id) AS answers,
                AVG(CASE WHEN s.id IS NOT NULL THEN a.self_score END) AS avg_score,
                MAX(CASE WHEN s.id IS NOT NULL THEN a.answered_at END) AS last_answered_at
            FROM topics t
            LEFT JOIN questions q ON q.topic_id = t.id
            LEFT JOIN answers a ON a.question_id = q.id
            LEFT JOIN sessions s
              ON s.id = a.session_id
             AND COALESCE(s.status, 'completed') <> 'abandoned'
            GROUP BY t.id
            ORDER BY COALESCE(last_answered_at, '') DESC, t.title ASC
            """
        ).fetchall()
        return {
            "session_count": session_count,
            "answered_count": answered_count,
            "avg_score": avg_score,
            "weak_topics": [dict(row) for row in weak_topics],
            "recent_sessions": [dict(row) for row in recent_sessions],
            "topic_dynamics": [dict(row) for row in topic_dynamics],
        }

    def topic_practice_metrics(self) -> dict[int, dict]:
        rows = self.connection.execute(
            """
            SELECT
                t.id AS topic_id,
                COUNT(s.id) AS answers,
                AVG(CASE WHEN s.id IS NOT NULL THEN a.self_score END) AS avg_self_score,
                MAX(CASE WHEN s.id IS NOT NULL THEN a.answered_at END) AS last_answered_at
            FROM topics t
            LEFT JOIN questions q ON q.topic_id = t.id
            LEFT JOIN answers a ON a.question_id = q.id
            LEFT JOIN sessions s
              ON s.id = a.session_id
             AND COALESCE(s.status, 'completed') <> 'abandoned'
            GROUP BY t.id
            """
        ).fetchall()
        return {row["topic_id"]: dict(row) for row in rows}

    def question_practice_metrics(self) -> dict[int, dict]:
        rows = self.connection.execute(
            """
            SELECT
                q.id AS question_id,
                COUNT(s.id) AS answers,
                AVG(CASE WHEN s.id IS NOT NULL THEN a.self_score END) AS avg_self_score,
                MAX(CASE WHEN s.id IS NOT NULL THEN a.answered_at END) AS last_answered_at,
                (
                    SELECT latest.self_score
                    FROM answers latest
                    JOIN sessions latest_session ON latest_session.id = latest.session_id
                    WHERE latest.question_id = q.id
                      AND COALESCE(latest_session.status, 'completed') <> 'abandoned'
                    ORDER BY latest.answered_at DESC, latest.id DESC
                    LIMIT 1
                ) AS last_self_score
            FROM questions q
            LEFT JOIN answers a ON a.question_id = q.id
            LEFT JOIN sessions s
              ON s.id = a.session_id
             AND COALESCE(s.status, 'completed') <> 'abandoned'
            GROUP BY q.id
            """
        ).fetchall()
        return {row["question_id"]: dict(row) for row in rows}
