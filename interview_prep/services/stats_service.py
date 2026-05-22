from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from interview_prep.domain.models import Topic
from interview_prep.infra.repositories import SQLiteRepository


@dataclass(frozen=True)
class WeakTopic:
    topic: Topic
    answers: int
    avg_self_score: float | None
    last_answered_at: datetime | None
    weakness_score: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        return {
            "topic_id": self.topic.id,
            "slug": self.topic.slug,
            "title": self.topic.title,
            "answers": self.answers,
            "avg_score": self.avg_self_score,
            "avg_self_score": self.avg_self_score,
            "last_answered_at": self.last_answered_at.isoformat() if self.last_answered_at else None,
            "weakness_score": self.weakness_score,
            "reasons": list(self.reasons),
        }


class StatsService:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def dashboard(self) -> dict:
        stats = self.repository.stats()
        stats["weak_topics"] = [item.to_dict() for item in self.weak_topics()]
        stats["suggested_topic"] = self.suggest_topic(stats)
        return stats

    def suggest_topic(self, stats: dict | None = None) -> str | None:
        data = stats or {"weak_topics": [item.to_dict() for item in self.weak_topics(limit=1)]}
        weak_topics = data.get("weak_topics") or []
        if weak_topics:
            return weak_topics[0]["title"]
        if stats is None:
            data = self.repository.stats()
        dynamics = data.get("topic_dynamics") or []
        for item in dynamics:
            if item.get("answers") == 0:
                return item["title"]
        return dynamics[0]["title"] if dynamics else None

    def weak_topics(
        self,
        limit: int = 5,
        min_answers: int = 3,
        stale_after_days: int = 14,
        now: datetime | None = None,
    ) -> list[WeakTopic]:
        metrics = self.repository.topic_practice_metrics()
        reference_now = now or datetime.now()
        candidates = [
            self._weak_topic_from_metrics(
                topic,
                metrics.get(topic.id or 0, {}),
                min_answers,
                stale_after_days,
                reference_now,
            )
            for topic in self.repository.list_topics()
        ]
        candidates.sort(
            key=lambda item: (
                -item.weakness_score,
                item.avg_self_score if item.avg_self_score is not None else 0.0,
                item.last_answered_at or datetime.min,
                item.topic.title,
            )
        )
        return candidates[: max(0, limit)]

    def _weak_topic_from_metrics(
        self,
        topic: Topic,
        metrics: dict,
        min_answers: int,
        stale_after_days: int,
        now: datetime,
    ) -> WeakTopic:
        answers = int(metrics.get("answers") or 0)
        avg_self_score = metrics.get("avg_self_score")
        last_answered_at = self._parse_datetime(metrics.get("last_answered_at"))
        reasons: list[str] = []

        if avg_self_score is None:
            score_component = 2.5
            reasons.append("нет самооценок")
        else:
            score_component = max(0.0, 5.0 - float(avg_self_score))
            if avg_self_score <= 3:
                reasons.append(f"низкая самооценка: {avg_self_score:.1f}/5")

        missing_answers = max(0, min_answers - answers)
        count_component = missing_answers * 0.75
        if missing_answers:
            reasons.append(f"мало ответов: {answers}/{min_answers}")

        recency_component = 0.0
        if last_answered_at is None:
            recency_component = 1.5
            reasons.append("нет свежей практики")
        else:
            days_since_answer = max(0, (now - last_answered_at).days)
            if days_since_answer >= stale_after_days:
                recency_component = min(2.0, days_since_answer / max(1, stale_after_days))
                reasons.append(f"давно не повторялась: {days_since_answer} дн.")

        if not reasons:
            reasons.append("поддерживающее повторение")

        weakness_score = round(score_component + count_component + recency_component, 3)
        return WeakTopic(
            topic=topic,
            answers=answers,
            avg_self_score=avg_self_score,
            last_answered_at=last_answered_at,
            weakness_score=weakness_score,
            reasons=tuple(reasons),
        )

    def _parse_datetime(self, value: object) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return None
