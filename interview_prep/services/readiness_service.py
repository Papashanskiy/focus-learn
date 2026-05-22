from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from interview_prep.domain.models import Competency
from interview_prep.infra.repositories import SQLiteRepository

MIN_COMPETENCY_ANSWERS = 3
STALE_AFTER_DAYS = 21


@dataclass(frozen=True)
class ReadinessGap:
    competency: Competency
    readiness_score: int
    reasons: tuple[str, ...]
    next_action: str

    @property
    def why_this_drill(self) -> str:
        reasons = "; ".join(self.reasons)
        return (
            f"{self.competency.title} ({self.competency.slug}) is the top readiness gap: "
            f"readiness {self.readiness_score}/100; {reasons}"
        )

    def to_dict(self) -> dict:
        return {
            "competency": {
                "id": self.competency.id,
                "slug": self.competency.slug,
                "title": self.competency.title,
                "category": self.competency.category,
            },
            "readiness_score": self.readiness_score,
            "reasons": list(self.reasons),
            "next_action": self.next_action,
            "why_this_drill": self.why_this_drill,
        }


@dataclass(frozen=True)
class OverallReadinessSummary:
    signal_score: int | None
    label: str
    summary: str
    caveat: str
    top_gaps: tuple[ReadinessGap, ...]
    recommended_drill: ReadinessGap | None

    def to_dict(self) -> dict:
        return {
            "signal_score": self.signal_score,
            "label": self.label,
            "summary": self.summary,
            "caveat": self.caveat,
            "top_gaps": [gap.to_dict() for gap in self.top_gaps],
            "recommended_drill": self.recommended_drill.to_dict()
            if self.recommended_drill
            else None,
        }


@dataclass(frozen=True)
class ReadinessWeeklyTrendPoint:
    week_start: date
    week_end: date
    session_count: int
    avg_readiness_delta: float
    total_readiness_delta: float

    def to_dict(self) -> dict:
        return {
            "week_start": self.week_start.isoformat(),
            "week_end": self.week_end.isoformat(),
            "session_count": self.session_count,
            "avg_readiness_delta": self.avg_readiness_delta,
            "total_readiness_delta": self.total_readiness_delta,
        }


@dataclass(frozen=True)
class CompetencyReadinessAggregate:
    competency: Competency
    linked_questions: int
    primary_questions: int
    answered_questions: int
    answer_count: int
    evaluated_answer_count: int
    avg_self_score: float | None
    avg_rubric_score: float | None
    last_answered_at: datetime | None
    answer_coverage: float
    readiness_score: int
    readiness_reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "competency": {
                "id": self.competency.id,
                "slug": self.competency.slug,
                "title": self.competency.title,
                "description": self.competency.description,
                "category": self.competency.category,
                "level": self.competency.level,
                "order_index": self.competency.order_index,
            },
            "linked_questions": self.linked_questions,
            "primary_questions": self.primary_questions,
            "answered_questions": self.answered_questions,
            "answer_count": self.answer_count,
            "evaluated_answer_count": self.evaluated_answer_count,
            "avg_self_score": self.avg_self_score,
            "avg_rubric_score": self.avg_rubric_score,
            "last_answered_at": self.last_answered_at.isoformat(timespec="seconds")
            if self.last_answered_at
            else None,
            "answer_coverage": self.answer_coverage,
            "readiness_score": self.readiness_score,
            "readiness_reasons": list(self.readiness_reasons),
        }


@dataclass(frozen=True)
class ReadinessSnapshot:
    generated_at: datetime
    competencies: list[CompetencyReadinessAggregate]
    competency_count: int
    covered_competency_count: int
    evaluated_competency_count: int
    overall_summary: OverallReadinessSummary
    weekly_trend: tuple[ReadinessWeeklyTrendPoint, ...]

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at.isoformat(timespec="seconds"),
            "competency_count": self.competency_count,
            "covered_competency_count": self.covered_competency_count,
            "evaluated_competency_count": self.evaluated_competency_count,
            "overall_summary": self.overall_summary.to_dict(),
            "weekly_trend": [item.to_dict() for item in self.weekly_trend],
            "competencies": [item.to_dict() for item in self.competencies],
        }


class ReadinessService:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def snapshot(self, now: datetime | None = None) -> ReadinessSnapshot:
        reference_now = now or datetime.now()
        competencies = self.competency_aggregates(now=reference_now)
        covered_count = sum(1 for item in competencies if item.answer_count > 0)
        evaluated_count = sum(1 for item in competencies if item.evaluated_answer_count > 0)
        return ReadinessSnapshot(
            generated_at=reference_now,
            competencies=competencies,
            competency_count=len(competencies),
            covered_competency_count=covered_count,
            evaluated_competency_count=evaluated_count,
            overall_summary=_build_overall_summary(
                competencies=competencies,
                covered_competency_count=covered_count,
                evaluated_competency_count=evaluated_count,
            ),
            weekly_trend=self.weekly_trend(),
        )

    def competency_aggregates(self, now: datetime | None = None) -> list[CompetencyReadinessAggregate]:
        reference_now = now or datetime.now()
        metrics = self.repository.competency_practice_metrics()
        system_design_metrics = self.repository.system_design_practice_metrics()
        system_design_topic = self.repository.find_topic_by_slug("system-design")
        system_design_topic_metrics = (
            system_design_metrics.get(system_design_topic.id or 0, {})
            if system_design_topic is not None
            else {}
        )
        aggregates = [
            self._aggregate_from_metrics(
                competency,
                metrics.get(competency.id or 0, {}),
                reference_now,
                system_design_topic_metrics,
            )
            for competency in self.repository.list_competencies()
        ]
        aggregates.sort(key=lambda item: (item.competency.order_index, item.competency.id or 0))
        return aggregates

    def weekly_trend(
        self,
        *,
        min_weeks: int = 2,
        max_weeks: int = 8,
    ) -> tuple[ReadinessWeeklyTrendPoint, ...]:
        rows = self.repository.list_completed_session_outcomes_for_readiness_trend()
        buckets: dict[date, list[float]] = {}
        for row in rows:
            ended_at = _parse_datetime(row.get("ended_at"))
            readiness_delta = _optional_float(row.get("readiness_delta"))
            if ended_at is None or readiness_delta is None:
                continue
            week_start = ended_at.date() - timedelta(days=ended_at.weekday())
            buckets.setdefault(week_start, []).append(readiness_delta)

        if len(buckets) < min_weeks:
            return tuple()

        points: list[ReadinessWeeklyTrendPoint] = []
        for week_start in sorted(buckets)[-max_weeks:]:
            deltas = buckets[week_start]
            total = sum(deltas)
            points.append(
                ReadinessWeeklyTrendPoint(
                    week_start=week_start,
                    week_end=week_start + timedelta(days=6),
                    session_count=len(deltas),
                    avg_readiness_delta=round(total / len(deltas), 3),
                    total_readiness_delta=round(total, 3),
                )
            )
        return tuple(points)

    def _aggregate_from_metrics(
        self,
        competency: Competency,
        metrics: dict,
        now: datetime,
        system_design_topic_metrics: dict,
    ) -> CompetencyReadinessAggregate:
        linked_questions = int(metrics.get("linked_questions") or 0)
        answered_questions = int(metrics.get("answered_questions") or 0)
        coverage = answered_questions / linked_questions if linked_questions else 0.0
        avg_rubric_score = _optional_float(metrics.get("avg_rubric_score"))
        last_answered_at = _parse_datetime(metrics.get("last_answered_at"))
        score, reasons = _score_competency_readiness(
            competency=competency,
            linked_questions=linked_questions,
            answer_count=int(metrics.get("answer_count") or 0),
            evaluated_answer_count=int(metrics.get("evaluated_answer_count") or 0),
            avg_rubric_score=avg_rubric_score,
            last_answered_at=last_answered_at,
            now=now,
            system_design_candidate_turns=int(
                system_design_topic_metrics.get("candidate_turn_count") or 0
            ),
        )
        return CompetencyReadinessAggregate(
            competency=competency,
            linked_questions=linked_questions,
            primary_questions=int(metrics.get("primary_questions") or 0),
            answered_questions=answered_questions,
            answer_count=int(metrics.get("answer_count") or 0),
            evaluated_answer_count=int(metrics.get("evaluated_answer_count") or 0),
            avg_self_score=_optional_float(metrics.get("avg_self_score")),
            avg_rubric_score=avg_rubric_score,
            last_answered_at=last_answered_at,
            answer_coverage=round(coverage, 3),
            readiness_score=score,
            readiness_reasons=reasons,
        )


def _optional_float(value: object) -> float | None:
    return float(value) if value is not None else None


def _parse_datetime(value: object) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return None


def _score_competency_readiness(
    *,
    competency: Competency,
    linked_questions: int,
    answer_count: int,
    evaluated_answer_count: int,
    avg_rubric_score: float | None,
    last_answered_at: datetime | None,
    now: datetime,
    system_design_candidate_turns: int,
) -> tuple[int, tuple[str, ...]]:
    penalty = 0.0
    reasons: list[str] = []

    if linked_questions == 0:
        penalty += 25.0
        reasons.append("нет связанных вопросов")

    missing_answers = max(0, MIN_COMPETENCY_ANSWERS - answer_count)
    if missing_answers:
        penalty += min(30.0, missing_answers * 10.0)
        reasons.append(f"мало ответов: {answer_count}/{MIN_COMPETENCY_ANSWERS}")

    if evaluated_answer_count == 0:
        penalty += 20.0
        reasons.append("нет rubric оценки")
    elif avg_rubric_score is not None and avg_rubric_score < 3.5:
        penalty += min(30.0, (3.5 - avg_rubric_score) * 15.0)
        reasons.append(f"низкая rubric оценка: {avg_rubric_score:.1f}/5")

    if last_answered_at is None:
        penalty += 15.0
        reasons.append("нет свежей практики")
    else:
        days_since_answer = max(0, (now - last_answered_at).days)
        if days_since_answer >= STALE_AFTER_DAYS:
            penalty += min(20.0, days_since_answer / STALE_AFTER_DAYS * 10.0)
            reasons.append(f"давно не повторялось: {days_since_answer} дн.")

    if competency.slug == "system-design" and system_design_candidate_turns == 0:
        penalty += 20.0
        reasons.append("нет system design практики")

    if not reasons:
        reasons.append("достаточно свежих evidence signals")

    score = max(0, min(100, round(100 - penalty)))
    return score, tuple(reasons)


def _build_overall_summary(
    *,
    competencies: list[CompetencyReadinessAggregate],
    covered_competency_count: int,
    evaluated_competency_count: int,
) -> OverallReadinessSummary:
    signal_score = (
        round(sum(item.readiness_score for item in competencies) / len(competencies))
        if competencies
        else None
    )
    top_gaps = tuple(
        _gap_from_aggregate(item)
        for item in sorted(
            (item for item in competencies if _has_gap_reasons(item)),
            key=_recommended_gap_sort_key,
        )[:3]
    )
    label = _overall_readiness_label(
        signal_score=signal_score,
        covered_competency_count=covered_competency_count,
        evaluated_competency_count=evaluated_competency_count,
    )
    summary = _overall_readiness_text(
        signal_score=signal_score,
        covered_competency_count=covered_competency_count,
        evaluated_competency_count=evaluated_competency_count,
        competency_count=len(competencies),
        top_gap=top_gaps[0] if top_gaps else None,
    )
    return OverallReadinessSummary(
        signal_score=signal_score,
        label=label,
        summary=summary,
        caveat=(
            "Это тренировочный сигнал по сохраненным ответам, rubric evaluations и свежести "
            "практики, а не абсолютная оценка кандидата."
        ),
        top_gaps=top_gaps,
        recommended_drill=top_gaps[0] if top_gaps else None,
    )


def _has_gap_reasons(item: CompetencyReadinessAggregate) -> bool:
    return any(reason != "достаточно свежих evidence signals" for reason in item.readiness_reasons)


def _gap_from_aggregate(item: CompetencyReadinessAggregate) -> ReadinessGap:
    return ReadinessGap(
        competency=item.competency,
        readiness_score=item.readiness_score,
        reasons=item.readiness_reasons,
        next_action=_next_action_for_gap(item),
    )


def _recommended_gap_sort_key(item: CompetencyReadinessAggregate) -> tuple[int, int, int, int]:
    return (
        _recommended_gap_priority(item),
        item.readiness_score,
        item.competency.order_index,
        item.competency.id or 0,
    )


def _recommended_gap_priority(item: CompetencyReadinessAggregate) -> int:
    reasons = item.readiness_reasons
    if any(reason.startswith("низкая rubric оценка:") for reason in reasons):
        return 0
    if "нет system design практики" in reasons:
        return 1
    return 2


def _next_action_for_gap(item: CompetencyReadinessAggregate) -> str:
    reasons = item.readiness_reasons
    title = item.competency.title
    if "нет system design практики" in reasons:
        return "Провести system design mock и сохранить transcript."
    if "нет связанных вопросов" in reasons:
        return f"Сгенерировать или добавить вопросы по competency: {title}."
    if any(reason.startswith("низкая rubric оценка:") for reason in reasons):
        return f"Перерешать слабый ответ по competency: {title} и закрыть rubric gaps."
    if any(reason.startswith("мало ответов:") for reason in reasons):
        return f"Ответить на 2-3 вопроса по competency: {title}."
    if "нет rubric оценки" in reasons:
        return f"Ответить в TUI по competency: {title}, чтобы сохранить rubric evaluation."
    if any(reason.startswith("давно не повторялось:") for reason in reasons):
        return f"Повторить competency сегодня: {title}."
    if "нет свежей практики" in reasons:
        return f"Начать baseline drill по competency: {title}."
    return f"Выбрать следующий короткий drill по competency: {title}."


def _overall_readiness_label(
    *,
    signal_score: int | None,
    covered_competency_count: int,
    evaluated_competency_count: int,
) -> str:
    if signal_score is None:
        return "Нет competency данных"
    if covered_competency_count == 0:
        return "Нужна baseline-практика"
    if evaluated_competency_count == 0:
        return "Нужны rubric evaluations"
    if signal_score >= 80:
        return "Стабильный evidence signal"
    if signal_score >= 60:
        return "Рабочая база с заметными gaps"
    return "Недостаточно evidence по senior competencies"


def _overall_readiness_text(
    *,
    signal_score: int | None,
    covered_competency_count: int,
    evaluated_competency_count: int,
    competency_count: int,
    top_gap: ReadinessGap | None,
) -> str:
    if signal_score is None or competency_count == 0:
        return "Senior readiness summary пока не построен: в базе нет competency taxonomy."
    evidence = (
        f"Evidence покрывает {covered_competency_count}/{competency_count} competencies; "
        f"rubric evaluations есть по {evaluated_competency_count}/{competency_count}."
    )
    if top_gap is None:
        return (
            f"{evidence} Средний readiness signal {signal_score}/100; явных top gaps "
            "по текущим правилам нет."
        )
    return (
        f"{evidence} Средний readiness signal {signal_score}/100; первый практический gap: "
        f"{top_gap.competency.title}."
    )
