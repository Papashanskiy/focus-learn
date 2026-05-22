from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import datetime
from typing import Any

from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.content_generation_service import ContentGenerationService
from interview_prep.services.curriculum_service import CurriculumService
from interview_prep.services.learning_service import LearningService
from interview_prep.services.question_service import QuestionService
from interview_prep.services.readiness_service import ReadinessService
from interview_prep.services.session_service import SessionService
from interview_prep.services.stats_service import StatsService


class ReadOnlyApplicationFacade:
    """JSON-safe read facade for future adapters such as a web UI."""

    def __init__(
        self,
        questions: QuestionService,
        sessions: SessionService,
        stats: StatsService,
        learning: LearningService,
        content_generation: ContentGenerationService,
        curriculum: CurriculumService,
        repository: SQLiteRepository,
        readiness: ReadinessService | None = None,
    ):
        self._questions = questions
        self._sessions = sessions
        self._stats = stats
        self._learning = learning
        self._content_generation = content_generation
        self._curriculum = curriculum
        self._repository = repository
        self._readiness = readiness or ReadinessService(repository)

    def dashboard(self, limit: int = 10) -> dict[str, Any]:
        return {
            "stats": _to_plain_data(self._stats.dashboard()),
            "topics": self.topics(),
            "competencies": self.competencies(),
            "readiness": self.readiness(),
            "suggested_next_topic": _to_plain_data(self._curriculum.suggest_next_topic()),
            "recent_sessions": self.completed_sessions(limit=limit),
            "learning_dialogs": self.learning_dialog_summaries(limit=limit),
            "content_jobs": self.content_jobs(limit=limit),
        }

    def topics(self) -> list[dict[str, Any]]:
        return _to_plain_data(self._questions.list_topics())

    def competencies(self) -> list[dict[str, Any]]:
        return _to_plain_data(self._repository.list_competencies())

    def readiness(self) -> dict[str, Any]:
        return self._readiness.snapshot().to_dict()

    def questions(
        self,
        topic_id: int | None = None,
        tag_slug: str | None = None,
        include_tags: bool = True,
        include_competencies: bool = True,
    ) -> list[dict[str, Any]]:
        questions = []
        for question in self._questions.list_questions(topic_id=topic_id, tag_slug=tag_slug):
            item = _to_plain_data(question)
            if include_tags and question.id is not None:
                item["tags"] = _to_plain_data(self._questions.list_question_tags(question.id))
            elif include_tags:
                item["tags"] = []
            if include_competencies and question.id is not None:
                item["competencies"] = _to_plain_data(self._questions.list_question_competencies(question.id))
            elif include_competencies:
                item["competencies"] = []
            questions.append(item)
        return questions

    def completed_sessions(self, limit: int = 30) -> list[dict[str, Any]]:
        return _to_plain_data(self._sessions.list_completed_sessions(limit=limit))

    def completed_session_detail(self, session_id: int) -> dict[str, Any] | None:
        return _to_plain_data(self._sessions.get_completed_session_detail(session_id))

    def learning_dialog_summaries(self, limit: int = 30) -> list[dict[str, Any]]:
        return _to_plain_data(self._learning.list_dialog_summaries(limit=limit))

    def learning_dialog_messages(self, dialog_session_id: str) -> list[dict[str, Any]]:
        return _to_plain_data(self._learning.list_dialog_messages_for_session(dialog_session_id))

    def notebook_entries(
        self,
        topic_id: int | None = None,
        curriculum_subtopic_id: int | None = None,
        dialog_session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return _to_plain_data(
            self._repository.list_notebook_entries(
                topic_id=topic_id,
                curriculum_subtopic_id=curriculum_subtopic_id,
                dialog_session_id=dialog_session_id,
                limit=limit,
            )
        )

    def generated_artifacts(
        self,
        topic_id: int | None = None,
        limit: int = 20,
    ) -> dict[str, list[dict[str, Any]]]:
        return {
            "learning_materials": _to_plain_data(
                self._repository.list_learning_materials(topic_id=topic_id, limit=limit)
            ),
            "system_design_scenarios": _to_plain_data(
                self._repository.list_system_design_scenarios(topic_id=topic_id, limit=limit)
            ),
        }

    def content_jobs(self, status: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        return _to_plain_data(self._content_generation.list_jobs(status=status, limit=limit))


def _to_plain_data(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _to_plain_data(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, dict):
        return {str(key): _to_plain_data(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_plain_data(item) for item in value]
    return value
