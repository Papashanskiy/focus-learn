from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from interview_prep.domain.models import (
    Competency,
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    Question,
    QuestionCompetencyLink,
    Session,
    SessionOutcome,
    SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
)
from interview_prep.domain.rules import DEFAULT_SESSION_MINUTES
from interview_prep.infra.repositories import SQLiteRepository


DEFAULT_BASELINE_QUESTION_COUNT = 5
DEFAULT_BASELINE_REPEAT_INTERVAL_DAYS = 7
DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT = 4
MOCK_INTERVIEW_SECTIONS = ("coding", "theory", "system_design", "debugging")
MOCK_INTERVIEW_COMPETENCY_SLUGS = {
    "coding": ("python-runtime", "async-concurrency", "testing-quality"),
    "theory": ("databases", "distributed-systems", "communication-tradeoffs"),
    "system_design": ("system-design", "distributed-systems"),
    "debugging": ("debugging-incidents", "observability", "databases"),
}


@dataclass(frozen=True)
class BaselineQuestionPick:
    competency: Competency
    question: Question
    link: QuestionCompetencyLink


@dataclass(frozen=True)
class BaselineSessionPlan:
    session: Session
    picks: tuple[BaselineQuestionPick, ...]

    @property
    def question_ids(self) -> tuple[int, ...]:
        return tuple(pick.question.id or 0 for pick in self.picks if pick.question.id is not None)


@dataclass(frozen=True)
class BaselineRepeatStatus:
    last_session_id: int | None
    last_completed_at: datetime | None
    last_readiness_delta: float | None
    next_due_at: datetime | None
    is_due: bool
    days_until_due: int
    reason: str


@dataclass(frozen=True)
class MockSeniorInterviewPick:
    section: str
    competency: Competency
    question: Question
    link: QuestionCompetencyLink


@dataclass(frozen=True)
class MockSeniorInterviewPlan:
    picks: tuple[MockSeniorInterviewPick, ...]

    @property
    def sections(self) -> tuple[str, ...]:
        return tuple(pick.section for pick in self.picks)

    @property
    def question_ids(self) -> tuple[int, ...]:
        return tuple(pick.question.id or 0 for pick in self.picks if pick.question.id is not None)


@dataclass(frozen=True)
class MockSeniorInterviewSessionPlan:
    session: Session
    picks: tuple[MockSeniorInterviewPick, ...]

    @property
    def sections(self) -> tuple[str, ...]:
        return tuple(pick.section for pick in self.picks)

    @property
    def question_ids(self) -> tuple[int, ...]:
        return tuple(pick.question.id or 0 for pick in self.picks if pick.question.id is not None)


class CalibrationService:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def start_baseline_session(
        self,
        *,
        target_minutes: int = DEFAULT_SESSION_MINUTES,
        limit: int = DEFAULT_BASELINE_QUESTION_COUNT,
    ) -> BaselineSessionPlan:
        picks = tuple(self.baseline_question_plan(limit=limit))
        if not picks:
            raise ValueError("No accepted questions available for baseline session.")
        session = self.repository.create_session(
            Session(
                id=None,
                topic_id=None,
                started_at=datetime.now(),
                ended_at=None,
                target_minutes=target_minutes,
            )
        )
        return BaselineSessionPlan(session=session, picks=picks)

    def start_mock_senior_interview_session(
        self,
        *,
        target_minutes: int = DEFAULT_SESSION_MINUTES,
        limit: int = DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT,
    ) -> MockSeniorInterviewSessionPlan:
        plan = self.mock_senior_interview_plan(limit=limit)
        if not plan.picks:
            raise ValueError("No accepted questions available for mock senior interview session.")
        session = self.repository.create_session(
            Session(
                id=None,
                topic_id=None,
                started_at=datetime.now(),
                ended_at=None,
                target_minutes=target_minutes,
            )
        )
        return MockSeniorInterviewSessionPlan(session=session, picks=plan.picks)

    def mark_baseline_session_outcome(self, session_id: int, *, planned_questions: int) -> SessionOutcome | None:
        outcome = self.repository.get_session_outcome_for_session(session_id)
        if outcome is None:
            return None
        summary = outcome.summary
        if not summary.startswith("Baseline calibration."):
            summary = f"Baseline calibration. Planned questions: {planned_questions}. {summary}"
        strengths = list(outcome.strengths)
        marker = "Первичная baseline practice session сохранена как calibration signal."
        if marker not in strengths:
            strengths.insert(0, marker)
        return self.repository.upsert_session_outcome(
            SessionOutcome(
                id=outcome.id,
                session_id=outcome.session_id,
                summary=summary,
                strengths=strengths,
                gaps=outcome.gaps,
                next_drills=outcome.next_drills,
                readiness_delta=outcome.readiness_delta,
                created_at=outcome.created_at,
                outcome_type=SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
            )
        )

    def baseline_repeat_status(
        self,
        *,
        now: datetime | None = None,
        interval_days: int = DEFAULT_BASELINE_REPEAT_INTERVAL_DAYS,
    ) -> BaselineRepeatStatus:
        current_time = now or datetime.now()
        latest = self.repository.get_latest_completed_session_outcome_by_type(
            SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE
        )
        if latest is None:
            return BaselineRepeatStatus(
                last_session_id=None,
                last_completed_at=None,
                last_readiness_delta=None,
                next_due_at=None,
                is_due=True,
                days_until_due=0,
                reason="Нет завершенной baseline session; нужна первичная baseline practice session.",
            )

        completed_at = datetime.fromisoformat(str(latest["ended_at"]))
        next_due_at = completed_at + timedelta(days=max(0, interval_days))
        remaining = next_due_at - current_time
        days_until_due = max(0, (remaining.days + (1 if remaining.seconds or remaining.microseconds else 0)))
        is_due = current_time >= next_due_at
        reason = (
            "Повторная baseline session уже доступна."
            if is_due
            else f"Повторная baseline session будет доступна через {days_until_due} дн."
        )
        return BaselineRepeatStatus(
            last_session_id=int(latest["session_id"]),
            last_completed_at=completed_at,
            last_readiness_delta=float(latest["readiness_delta"]),
            next_due_at=next_due_at,
            is_due=is_due,
            days_until_due=days_until_due,
            reason=reason,
        )

    def baseline_question_plan(
        self,
        limit: int = DEFAULT_BASELINE_QUESTION_COUNT,
    ) -> list[BaselineQuestionPick]:
        if limit <= 0:
            return []

        questions = self.repository.list_questions(source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED)
        question_by_id = {question.id: question for question in questions if question.id is not None}
        links_by_question_id = {
            question_id: self.repository.list_question_competencies(question_id)
            for question_id in question_by_id
        }
        metrics = self.repository.question_practice_metrics()

        selected_question_ids: set[int] = set()
        selected_competency_ids: set[int] = set()
        picks: list[BaselineQuestionPick] = []

        for require_primary in (True, False):
            for competency in self.repository.list_competencies():
                if competency.id in selected_competency_ids:
                    continue
                candidate = self._best_question_for_competency(
                    competency,
                    question_by_id,
                    links_by_question_id,
                    metrics,
                    selected_question_ids=selected_question_ids,
                    require_primary=require_primary,
                )
                if candidate is None:
                    continue

                question, link = candidate
                picks.append(BaselineQuestionPick(competency=competency, question=question, link=link))
                selected_competency_ids.add(competency.id or 0)
                selected_question_ids.add(question.id or 0)
                if len(picks) >= limit:
                    return picks

        return picks

    def mock_senior_interview_plan(
        self,
        limit: int = DEFAULT_MOCK_INTERVIEW_QUESTION_COUNT,
    ) -> MockSeniorInterviewPlan:
        if limit <= 0:
            return MockSeniorInterviewPlan(picks=())

        questions = self.repository.list_questions(source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED)
        question_by_id = {question.id: question for question in questions if question.id is not None}
        links_by_question_id = {
            question_id: self.repository.list_question_competencies(question_id)
            for question_id in question_by_id
        }
        metrics = self.repository.question_practice_metrics()
        competencies_by_slug = {competency.slug: competency for competency in self.repository.list_competencies()}

        selected_question_ids: set[int] = set()
        picks: list[MockSeniorInterviewPick] = []
        for section in MOCK_INTERVIEW_SECTIONS:
            pick = self._best_question_for_mock_section(
                section,
                competencies_by_slug,
                question_by_id,
                links_by_question_id,
                metrics,
                selected_question_ids=selected_question_ids,
            )
            if pick is None:
                continue

            picks.append(pick)
            selected_question_ids.add(pick.question.id or 0)
            if len(picks) >= limit:
                break

        return MockSeniorInterviewPlan(picks=tuple(picks))

    def _best_question_for_mock_section(
        self,
        section: str,
        competencies_by_slug: dict[str, Competency],
        questions: dict[int | None, Question],
        links_by_question_id: dict[int, list[QuestionCompetencyLink]],
        metrics: dict[int, dict],
        *,
        selected_question_ids: set[int],
    ) -> MockSeniorInterviewPick | None:
        for slug in MOCK_INTERVIEW_COMPETENCY_SLUGS.get(section, ()):
            competency = competencies_by_slug.get(slug)
            if competency is None:
                continue
            candidate = self._best_question_for_competency(
                competency,
                questions,
                links_by_question_id,
                metrics,
                selected_question_ids=selected_question_ids,
                require_primary=True,
            )
            if candidate is None:
                candidate = self._best_question_for_competency(
                    competency,
                    questions,
                    links_by_question_id,
                    metrics,
                    selected_question_ids=selected_question_ids,
                    require_primary=False,
                )
            if candidate is not None:
                question, link = candidate
                return MockSeniorInterviewPick(
                    section=section,
                    competency=competency,
                    question=question,
                    link=link,
                )
        return None

    def _best_question_for_competency(
        self,
        competency: Competency,
        questions: dict[int | None, Question],
        links_by_question_id: dict[int, list[QuestionCompetencyLink]],
        metrics: dict[int, dict],
        *,
        selected_question_ids: set[int],
        require_primary: bool,
    ) -> tuple[Question, QuestionCompetencyLink] | None:
        candidates: list[tuple[Question, QuestionCompetencyLink]] = []
        for question_id, question in questions.items():
            if question_id is None or question_id in selected_question_ids:
                continue
            for link in links_by_question_id.get(question_id, []):
                if link.competency.id != competency.id:
                    continue
                if require_primary and not link.is_primary:
                    continue
                candidates.append((question, link))

        if not candidates:
            return None

        return min(
            candidates,
            key=lambda candidate: self._baseline_candidate_rank(candidate[0], candidate[1], metrics),
        )

    def _baseline_candidate_rank(
        self,
        question: Question,
        link: QuestionCompetencyLink,
        metrics: dict[int, dict],
    ) -> tuple[int, int, int, str, int]:
        question_metrics = metrics.get(question.id or 0, {})
        return (
            0 if link.is_primary else 1,
            int(question_metrics.get("answers") or 0),
            question.topic_id,
            question.difficulty,
            question.id or 0,
        )
