from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from interview_prep.domain.models import (
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
    QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
    Competency,
    Question,
    Topic,
)
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.readiness_service import ReadinessService

CONTENT_DEMAND_ACCEPTED_QUESTIONS = "accepted-questions"
CONTENT_DEMAND_CANDIDATE_QUESTIONS = "candidate-questions"
CONTENT_DEMAND_LEARNING_MATERIALS = "learning-materials"
CONTENT_DEMAND_SYSTEM_DESIGN_SCENARIOS = "system-design-scenarios"

CONTENT_DEMAND_MODE_PRACTICE = "practice"
CONTENT_DEMAND_MODE_LEARN = "learn"
CONTENT_DEMAND_MODE_SYSTEM_DESIGN = "system-design"
DEFAULT_CONTENT_DEMAND_MODES = (
    CONTENT_DEMAND_MODE_PRACTICE,
    CONTENT_DEMAND_MODE_LEARN,
    CONTENT_DEMAND_MODE_SYSTEM_DESIGN,
)


@dataclass(frozen=True)
class ContentDemandPolicy:
    accepted_questions_per_topic: int = 4
    candidate_questions_per_topic: int = 2
    accepted_questions_per_gap_competency: int = 3
    candidate_questions_per_gap_competency: int = 1
    learning_materials_per_topic: int = 1
    system_design_scenarios_per_topic: int = 1
    readiness_gap_limit: int = 3


@dataclass(frozen=True)
class ContentDemandTarget:
    kind: str
    target_count: int
    current_count: int
    reason: str
    priority: int
    topic_id: int | None = None
    topic_slug: str | None = None
    topic_title: str | None = None
    competency_id: int | None = None
    competency_slug: str | None = None
    competency_title: str | None = None
    upcoming_mode: str | None = None

    @property
    def deficit(self) -> int:
        return max(0, self.target_count - self.current_count)

    @property
    def has_deficit(self) -> bool:
        return self.deficit > 0

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "target_count": self.target_count,
            "current_count": self.current_count,
            "deficit": self.deficit,
            "reason": self.reason,
            "priority": self.priority,
            "topic_id": self.topic_id,
            "topic_slug": self.topic_slug,
            "topic_title": self.topic_title,
            "competency_id": self.competency_id,
            "competency_slug": self.competency_slug,
            "competency_title": self.competency_title,
            "upcoming_mode": self.upcoming_mode,
        }


@dataclass(frozen=True)
class ContentDemandSnapshot:
    generated_at: datetime
    targets: tuple[ContentDemandTarget, ...]

    @property
    def deficits(self) -> tuple[ContentDemandTarget, ...]:
        return tuple(target for target in self.targets if target.has_deficit)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(timespec="seconds"),
            "targets": [target.to_dict() for target in self.targets],
            "deficits": [target.to_dict() for target in self.deficits],
        }


class ContentDemandService:
    def __init__(
        self,
        repository: SQLiteRepository,
        readiness: ReadinessService | None = None,
        policy: ContentDemandPolicy | None = None,
    ):
        self.repository = repository
        self.readiness = readiness or ReadinessService(repository)
        self.policy = policy or ContentDemandPolicy()

    def snapshot(
        self,
        *,
        upcoming_modes: Iterable[str] | None = None,
        now: datetime | None = None,
    ) -> ContentDemandSnapshot:
        reference_now = now or datetime.now()
        modes = normalize_content_demand_modes(upcoming_modes)
        targets: list[ContentDemandTarget] = []
        topics = self.repository.list_topics()
        accepted_by_topic = _questions_by_topic(
            self.repository.list_questions(source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED)
        )
        candidate_by_topic = _questions_by_topic(
            [
                *self.repository.list_questions(
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW
                ),
                *self.repository.list_questions(
                    source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW
                ),
            ]
        )

        if CONTENT_DEMAND_MODE_PRACTICE in modes:
            for topic in topics:
                targets.extend(self._topic_question_targets(topic, accepted_by_topic, candidate_by_topic))
            targets.extend(
                self._readiness_gap_question_targets(
                    accepted_questions=[
                        question
                        for questions in accepted_by_topic.values()
                        for question in questions
                    ],
                    candidate_questions=[
                        question
                        for questions in candidate_by_topic.values()
                        for question in questions
                    ],
                    now=reference_now,
                )
            )

        if CONTENT_DEMAND_MODE_LEARN in modes:
            for topic in topics:
                count = len(self.repository.list_learning_materials(topic_id=topic.id, limit=1000))
                targets.append(
                    self._topic_target(
                        topic,
                        kind=CONTENT_DEMAND_LEARNING_MATERIALS,
                        target_count=self.policy.learning_materials_per_topic,
                        current_count=count,
                        reason="learn mode stock",
                        upcoming_mode=CONTENT_DEMAND_MODE_LEARN,
                        priority=300,
                    )
                )

        if CONTENT_DEMAND_MODE_SYSTEM_DESIGN in modes:
            for topic in topics:
                count = len(self.repository.list_system_design_scenarios(topic_id=topic.id, limit=1000))
                targets.append(
                    self._topic_target(
                        topic,
                        kind=CONTENT_DEMAND_SYSTEM_DESIGN_SCENARIOS,
                        target_count=self.policy.system_design_scenarios_per_topic,
                        current_count=count,
                        reason="system design mode stock",
                        upcoming_mode=CONTENT_DEMAND_MODE_SYSTEM_DESIGN,
                        priority=400,
                    )
                )

        targets.sort(key=lambda target: (target.priority, target.topic_id or 0, target.kind))
        return ContentDemandSnapshot(generated_at=reference_now, targets=tuple(targets))

    def _topic_question_targets(
        self,
        topic: Topic,
        accepted_by_topic: dict[int, list[Question]],
        candidate_by_topic: dict[int, list[Question]],
    ) -> list[ContentDemandTarget]:
        topic_id = topic.id or 0
        return [
            self._topic_target(
                topic,
                kind=CONTENT_DEMAND_ACCEPTED_QUESTIONS,
                target_count=self.policy.accepted_questions_per_topic,
                current_count=len(accepted_by_topic.get(topic_id, [])),
                reason="practice topic stock",
                upcoming_mode=CONTENT_DEMAND_MODE_PRACTICE,
                priority=100,
            ),
            self._topic_target(
                topic,
                kind=CONTENT_DEMAND_CANDIDATE_QUESTIONS,
                target_count=self.policy.candidate_questions_per_topic,
                current_count=len(candidate_by_topic.get(topic_id, [])),
                reason="curation candidate stock",
                upcoming_mode=CONTENT_DEMAND_MODE_PRACTICE,
                priority=120,
            ),
        ]

    def _readiness_gap_question_targets(
        self,
        *,
        accepted_questions: list[Question],
        candidate_questions: list[Question],
        now: datetime,
    ) -> list[ContentDemandTarget]:
        gaps = self.readiness.snapshot(now=now).overall_summary.top_gaps[: self.policy.readiness_gap_limit]
        accepted_by_competency = self._questions_by_competency(accepted_questions)
        candidate_by_competency = self._questions_by_competency(candidate_questions)
        targets: list[ContentDemandTarget] = []
        for index, gap in enumerate(gaps):
            competency = gap.competency
            competency_id = competency.id or 0
            reason = f"readiness gap: {competency.slug}"
            targets.extend(
                [
                    self._competency_target(
                        competency,
                        kind=CONTENT_DEMAND_ACCEPTED_QUESTIONS,
                        target_count=self.policy.accepted_questions_per_gap_competency,
                        current_count=len(accepted_by_competency.get(competency_id, set())),
                        reason=reason,
                        priority=10 + index,
                    ),
                    self._competency_target(
                        competency,
                        kind=CONTENT_DEMAND_CANDIDATE_QUESTIONS,
                        target_count=self.policy.candidate_questions_per_gap_competency,
                        current_count=len(candidate_by_competency.get(competency_id, set())),
                        reason=reason,
                        priority=30 + index,
                    ),
                ]
            )
        return targets

    def _questions_by_competency(self, questions: list[Question]) -> dict[int, set[int]]:
        question_ids_by_competency: dict[int, set[int]] = {}
        for question in questions:
            if question.id is None:
                continue
            for link in self.repository.list_question_competencies(question.id):
                competency_id = link.competency.id
                if competency_id is None:
                    continue
                question_ids_by_competency.setdefault(competency_id, set()).add(question.id)
        return question_ids_by_competency

    def _topic_target(
        self,
        topic: Topic,
        *,
        kind: str,
        target_count: int,
        current_count: int,
        reason: str,
        priority: int,
        upcoming_mode: str,
    ) -> ContentDemandTarget:
        return ContentDemandTarget(
            kind=kind,
            topic_id=topic.id,
            topic_slug=topic.slug,
            topic_title=topic.title,
            target_count=target_count,
            current_count=current_count,
            reason=reason,
            priority=priority,
            upcoming_mode=upcoming_mode,
        )

    def _competency_target(
        self,
        competency: Competency,
        *,
        kind: str,
        target_count: int,
        current_count: int,
        reason: str,
        priority: int,
    ) -> ContentDemandTarget:
        return ContentDemandTarget(
            kind=kind,
            competency_id=competency.id,
            competency_slug=competency.slug,
            competency_title=competency.title,
            target_count=target_count,
            current_count=current_count,
            reason=reason,
            priority=priority,
            upcoming_mode=CONTENT_DEMAND_MODE_PRACTICE,
        )


def normalize_content_demand_modes(upcoming_modes: Iterable[str] | None) -> tuple[str, ...]:
    if upcoming_modes is None:
        return DEFAULT_CONTENT_DEMAND_MODES
    normalized = []
    for mode in upcoming_modes:
        value = str(mode).strip().lower()
        if value in {"learning", "learn"}:
            value = CONTENT_DEMAND_MODE_LEARN
        elif value in {"system_design", "system design", "mock-interview", "mock"}:
            value = CONTENT_DEMAND_MODE_SYSTEM_DESIGN
        elif value in {"practice", "today", "mock senior interview"}:
            value = CONTENT_DEMAND_MODE_PRACTICE
        if value in DEFAULT_CONTENT_DEMAND_MODES and value not in normalized:
            normalized.append(value)
    return tuple(normalized) if normalized else DEFAULT_CONTENT_DEMAND_MODES


def _questions_by_topic(questions: list[Question]) -> dict[int, list[Question]]:
    by_topic: dict[int, list[Question]] = {}
    for question in questions:
        by_topic.setdefault(question.topic_id, []).append(question)
    return by_topic
