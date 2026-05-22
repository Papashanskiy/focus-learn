from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
import re

from interview_prep.domain.models import (
    AnswerEvaluationScore,
    RubricDimension,
    SystemDesignArtifact,
    SystemDesignEvaluation,
    SystemDesignFeedbackArtifact,
    SystemDesignTranscriptMessage,
)
from interview_prep.infra.llm import LLMClient
from interview_prep.infra.repositories import SQLiteRepository


Transcript = Sequence[tuple[str, str]]

DEFAULT_SYSTEM_DESIGN_SCENARIO = (
    "Спроектируй сервис сокращения ссылок с публичным API, аналитикой переходов, "
    "защитой от abuse и возможностью горизонтального масштабирования."
)

SYSTEM_DESIGN_ARTIFACT_SECTIONS = {"requirements", "api", "data_model", "decisions", "risks"}

SYSTEM_DESIGN_SECTION_BY_DIMENSION = {
    "requirements": ("requirements",),
    "api": ("api",),
    "data-model": ("data_model",),
    "reliability": ("risks",),
    "tradeoffs": ("decisions",),
}

SYSTEM_DESIGN_DIMENSION_KEYWORDS = {
    "requirements": (
        "requirement",
        "requirements",
        "scope",
        "slo",
        "sla",
        "latency",
        "availability",
        "assumption",
        "constraint",
        "требован",
        "scope",
        "допущ",
        "огранич",
    ),
    "api": (
        "api",
        "endpoint",
        "request",
        "response",
        "contract",
        "status",
        "version",
        "rest",
        "grpc",
        "post",
        "get",
        "ошиб",
        "контракт",
    ),
    "data-model": (
        "data",
        "model",
        "schema",
        "table",
        "entity",
        "index",
        "storage",
        "migration",
        "postgres",
        "redis",
        "данн",
        "таблиц",
        "индекс",
    ),
    "scaling": (
        "scale",
        "scaling",
        "capacity",
        "rps",
        "qps",
        "traffic",
        "cache",
        "partition",
        "shard",
        "bottleneck",
        "queue",
        "worker",
        "hot key",
        "масштаб",
        "нагруз",
    ),
    "consistency": (
        "consistency",
        "transaction",
        "idempotency",
        "idempotent",
        "ordering",
        "dedup",
        "conflict",
        "stale",
        "isolation",
        "exactly",
        "at-least",
        "консист",
        "идемпот",
        "транзакц",
        "порядок",
    ),
    "reliability": (
        "failure",
        "retry",
        "retries",
        "timeout",
        "fallback",
        "degradation",
        "dlq",
        "circuit",
        "outage",
        "risk",
        "abuse",
        "отказ",
        "риск",
        "деград",
        "таймаут",
    ),
    "observability": (
        "observability",
        "metric",
        "metrics",
        "log",
        "logs",
        "trace",
        "traces",
        "alert",
        "dashboard",
        "telemetry",
        "correlation",
        "метрик",
        "лог",
        "трейс",
        "алерт",
    ),
    "tradeoffs": (
        "tradeoff",
        "trade-off",
        "alternative",
        "cost",
        "decision",
        "choose",
        "versus",
        "risk",
        "компромисс",
        "альтернатив",
        "стоим",
        "выбор",
        "решен",
    ),
}

SYSTEM_DESIGN_DIMENSION_GAPS = {
    "requirements": "Зафиксируй scope, actors, core flows, non-functional requirements и явные допущения.",
    "api": "Опиши API contracts: endpoints, payloads, errors, auth/rate limits and versioning.",
    "data-model": "Добавь entities, storage choices, indexes, migrations and data lifecycle.",
    "scaling": "Раскрой capacity assumptions, bottlenecks, partitioning, caching and async processing.",
    "consistency": "Назови consistency guarantees, idempotency, ordering and conflict handling.",
    "reliability": "Покрой failure modes, retries, timeouts, degradation and abuse protection.",
    "observability": "Добавь metrics, logs, traces, alerts and dashboards tied to user impact.",
    "tradeoffs": "Сравни alternatives, costs, risks and decision criteria.",
}

SYSTEM_DESIGN_DIMENSION_DRILLS = {
    slug: f"Сделай system design drill по dimension `{slug}` и явно закрой missing evidence."
    for slug in SYSTEM_DESIGN_DIMENSION_GAPS
}

SYSTEM_DESIGN_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_+-]+")


class SystemDesignService:
    def __init__(self, repository: SQLiteRepository, llm: LLMClient):
        self.repository = repository
        self.llm = llm

    def next_turn(self, scenario: str, transcript: Transcript, user_message: str) -> str:
        prompt = build_system_design_turn_prompt(scenario, transcript, user_message)
        return self.llm.generate(prompt)

    def final_feedback(self, scenario: str, transcript: Transcript) -> str:
        prompt = build_system_design_feedback_prompt(scenario, transcript)
        return self.llm.generate(prompt)

    def checkpoint(
        self,
        scenario: str,
        transcript: Transcript,
        artifacts: Mapping[str, Sequence[str]] | None = None,
    ) -> str:
        prompt = build_system_design_checkpoint_prompt(scenario, transcript, artifacts or {})
        return self.llm.generate(prompt)

    def pressure_follow_up(
        self,
        scenario: str,
        transcript: Transcript,
        artifacts: Mapping[str, Sequence[str]] | None = None,
    ) -> str:
        prompt = build_system_design_pressure_prompt(scenario, transcript, artifacts or {})
        return self.llm.generate(prompt)

    def save_transcript_turn(
        self,
        topic_id: int,
        user_message: str,
        interviewer_response: str,
        scenario_id: int | None = None,
    ) -> tuple[SystemDesignTranscriptMessage, SystemDesignTranscriptMessage]:
        candidate = self.add_transcript_message(topic_id, "candidate", user_message, scenario_id=scenario_id)
        interviewer = self.add_transcript_message(
            topic_id,
            "interviewer",
            interviewer_response,
            scenario_id=scenario_id,
        )
        return candidate, interviewer

    def add_transcript_message(
        self,
        topic_id: int,
        role: str,
        content: str,
        scenario_id: int | None = None,
    ) -> SystemDesignTranscriptMessage:
        if self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        if scenario_id is not None:
            scenario = self.repository.get_system_design_scenario(scenario_id)
            if scenario is None:
                raise ValueError(f"Unknown system design scenario id: {scenario_id}")
            if scenario.topic_id != topic_id:
                raise ValueError("System design scenario does not belong to topic")
        if role not in {"candidate", "interviewer"}:
            raise ValueError(f"Unknown system design transcript role: {role}")
        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("System design transcript message cannot be empty")
        return self.repository.add_system_design_transcript_message(
            SystemDesignTranscriptMessage(
                id=None,
                topic_id=topic_id,
                scenario_id=scenario_id,
                role=role,
                content=cleaned_content,
                created_at=datetime.now(),
            )
        )

    def list_transcript_messages(
        self,
        topic_id: int,
        scenario_id: int | None = None,
        limit: int = 50,
    ) -> list[SystemDesignTranscriptMessage]:
        if self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        return self.repository.list_system_design_transcript_messages(
            topic_id,
            scenario_id=scenario_id,
            limit=limit,
        )

    def add_artifact(
        self,
        topic_id: int,
        section: str,
        content: str,
        scenario_id: int | None = None,
    ) -> SystemDesignArtifact:
        self._validate_topic_and_scenario(topic_id, scenario_id)
        if section not in SYSTEM_DESIGN_ARTIFACT_SECTIONS:
            raise ValueError(f"Unknown system design artifact section: {section}")
        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("System design artifact cannot be empty")
        return self.repository.add_system_design_artifact(
            SystemDesignArtifact(
                id=None,
                topic_id=topic_id,
                scenario_id=scenario_id,
                section=section,
                content=cleaned_content,
                created_at=datetime.now(),
            )
        )

    def list_artifacts(
        self,
        topic_id: int,
        scenario_id: int | None = None,
        section: str | None = None,
        limit: int = 50,
    ) -> list[SystemDesignArtifact]:
        self._validate_topic_and_scenario(topic_id, scenario_id)
        if section is not None and section not in SYSTEM_DESIGN_ARTIFACT_SECTIONS:
            raise ValueError(f"Unknown system design artifact section: {section}")
        return self.repository.list_system_design_artifacts(
            topic_id,
            scenario_id=scenario_id,
            section=section,
            limit=limit,
        )

    def save_final_feedback(
        self,
        topic_id: int,
        feedback: str,
        scenario_id: int | None = None,
        session_id: int | None = None,
        source: str = "llm",
    ) -> SystemDesignFeedbackArtifact:
        self._validate_topic_and_scenario(topic_id, scenario_id)
        if session_id is not None and self.repository.get_session(session_id) is None:
            raise ValueError(f"Unknown session id: {session_id}")
        cleaned_feedback = feedback.strip()
        if not cleaned_feedback:
            raise ValueError("System design feedback artifact cannot be empty")
        saved = self.repository.add_system_design_feedback_artifact(
            SystemDesignFeedbackArtifact(
                id=None,
                topic_id=topic_id,
                scenario_id=scenario_id,
                session_id=session_id,
                content=cleaned_feedback,
                source=source,
                created_at=datetime.now(),
            )
        )
        self.evaluate_and_store_feedback(saved)
        return saved

    def evaluate_and_store_feedback(
        self,
        feedback_artifact: SystemDesignFeedbackArtifact,
    ) -> SystemDesignEvaluation | None:
        if feedback_artifact.id is None:
            raise ValueError("System design feedback artifact must be persisted before evaluation.")
        dimensions = self.repository.list_system_design_rubric_dimensions()
        if not dimensions:
            return None
        transcript = self.repository.list_system_design_transcript_messages(
            feedback_artifact.topic_id,
            scenario_id=feedback_artifact.scenario_id,
            limit=200,
        )
        artifacts = self.repository.list_system_design_artifacts(
            feedback_artifact.topic_id,
            scenario_id=feedback_artifact.scenario_id,
            limit=200,
        )
        scores = score_system_design_rubric(dimensions, transcript, artifacts)
        evaluation = SystemDesignEvaluation(
            id=None,
            feedback_artifact_id=feedback_artifact.id,
            topic_id=feedback_artifact.topic_id,
            scenario_id=feedback_artifact.scenario_id,
            session_id=feedback_artifact.session_id,
            summary=system_design_evaluation_summary(scores),
            scores=scores,
            next_drills=system_design_next_drills(scores),
            source="heuristic",
            created_at=datetime.now(),
        )
        return self.repository.add_system_design_evaluation(evaluation)

    def _validate_topic_and_scenario(self, topic_id: int, scenario_id: int | None = None) -> None:
        if self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        if scenario_id is not None:
            scenario = self.repository.get_system_design_scenario(scenario_id)
            if scenario is None:
                raise ValueError(f"Unknown system design scenario id: {scenario_id}")
            if scenario.topic_id != topic_id:
                raise ValueError("System design scenario does not belong to topic")


def build_system_design_turn_prompt(scenario: str, transcript: Transcript, user_message: str) -> str:
    return f"""
<system_design_mock_interview>
Ты проводишь mock interview по system design для middle+/senior Python backend-разработчика.
Отвечай строго на русском языке.

Твоя роль:
- быть интервьюером, а не автором полного решения;
- задавать один следующий уточняющий вопрос или давать короткий challenge;
- двигать кандидата по этапам: requirements, API, data model, storage, scaling, consistency, queues, caching, observability, failure modes;
- не приписывать кандидату то, чего он не говорил;
- не раскрывать идеальный дизайн целиком, пока кандидат сам не предложил решение.

Формат ответа:
1. Коротко зафиксируй, что кандидат уже предложил.
2. Назови один риск или пробел.
3. Задай один конкретный следующий вопрос.

<scenario>
{scenario}
</scenario>

<transcript>
{format_transcript(transcript)}
</transcript>

<candidate_message>
{user_message}
</candidate_message>
</system_design_mock_interview>
""".strip()


def build_system_design_feedback_prompt(scenario: str, transcript: Transcript) -> str:
    return f"""
<system_design_final_feedback>
Ты senior system design interviewer. Дай итоговый feedback по mock interview.
Отвечай строго на русском языке.

Оценивай только то, что есть в transcript. Не приписывай кандидату идеи из сценария или своих ожиданий.

Критерии:
- requirements и scope;
- API contracts;
- data model и storage;
- scaling и performance;
- consistency и reliability;
- queues/background jobs;
- caching;
- observability;
- security/abuse prevention;
- failure modes и operational tradeoffs.

Формат:
Уровень: middle+/senior/ниже senior.
Сильные стороны:
- ...
Пробелы:
- ...
Что улучшить в следующей попытке:
- ...
Senior checklist:
- ...

<scenario>
{scenario}
</scenario>

<transcript>
{format_transcript(transcript)}
</transcript>
</system_design_final_feedback>
""".strip()


def build_system_design_checkpoint_prompt(
    scenario: str,
    transcript: Transcript,
    artifacts: Mapping[str, Sequence[str]] | None = None,
) -> str:
    return f"""
<system_design_checkpoint>
Ты senior system design interviewer. Дай короткий checkpoint во время mock interview.
Отвечай строго на русском языке.

Это не финальный feedback и не оценка уровня кандидата.
Не ставь уровень middle/senior, не выставляй score и не завершай интервью.
Оценивай только то, что уже есть в transcript и artifacts. Не приписывай кандидату идеи из сценария.

Формат:
Checkpoint:
- Что уже понятно: ...
- Главный риск или пробел: ...
- Следующий лучший шаг: ...
Вопрос интервьюера: один конкретный follow-up вопрос.

<scenario>
{scenario}
</scenario>

<transcript>
{format_transcript(transcript)}
</transcript>

<artifacts>
{format_system_design_artifacts(artifacts or {})}
</artifacts>
</system_design_checkpoint>
""".strip()


def build_system_design_pressure_prompt(
    scenario: str,
    transcript: Transcript,
    artifacts: Mapping[str, Sequence[str]] | None = None,
) -> str:
    return f"""
<system_design_pressure_follow_up>
Ты senior system design interviewer. Дай один pressure follow-up вопрос во время mock interview.
Отвечай строго на русском языке.

Это не финальный feedback и не оценка уровня кандидата.
Не ставь уровень middle/senior, не выставляй score и не завершай интервью.
Оценивай только transcript и artifacts. Не приписывай кандидату идеи из сценария.

Выбери самый важный недокрытый pressure area:
- capacity planning: RPS/QPS, storage growth, latency budget, bottlenecks;
- hot keys и traffic skew;
- retries: backoff, jitter, DLQ, timeout boundaries;
- idempotency: keys, deduplication, exactly-once illusions;
- migrations: backward compatibility, rollout, rollback, data backfill;
- abuse protection: rate limits, quotas, fraud/spam controls.

Формат:
Pressure follow-up:
- Focus: один pressure area из списка.
- Why now: коротко почему это важно для текущего решения.
Question: один конкретный вопрос интервьюера.

<scenario>
{scenario}
</scenario>

<transcript>
{format_transcript(transcript)}
</transcript>

<artifacts>
{format_system_design_artifacts(artifacts or {})}
</artifacts>
</system_design_pressure_follow_up>
""".strip()


def format_transcript(transcript: Transcript) -> str:
    if not transcript:
        return "Диалог еще не начат."
    return "\n".join(f"{role}: {message}" for role, message in transcript)


def format_system_design_artifacts(artifacts: Mapping[str, Sequence[str]]) -> str:
    lines: list[str] = []
    for section, items in artifacts.items():
        cleaned_items = [str(item).strip() for item in items if str(item).strip()]
        if cleaned_items:
            lines.append(f"{section}:")
            lines.extend(f"- {item}" for item in cleaned_items)
    if not lines:
        return "Artifacts еще не зафиксированы."
    return "\n".join(lines)


def score_system_design_rubric(
    dimensions: Sequence[RubricDimension],
    transcript: Sequence[SystemDesignTranscriptMessage],
    artifacts: Sequence[SystemDesignArtifact],
) -> list[AnswerEvaluationScore]:
    transcript_text = "\n".join(
        f"{message.role}: {message.content}"
        for message in transcript
        if message.role == "candidate"
    )
    artifacts_by_section = _system_design_artifacts_by_section(artifacts)
    combined_text = "\n".join(
        part
        for part in [
            transcript_text,
            "\n".join(
                f"{section}: {content}"
                for section, content in artifacts_by_section.items()
                if content.strip()
            ),
        ]
        if part.strip()
    )
    return [
        _score_system_design_dimension(dimension, combined_text, artifacts_by_section)
        for dimension in dimensions
    ]


def system_design_evaluation_summary(scores: Sequence[AnswerEvaluationScore]) -> str:
    if not scores:
        return "System design evaluation не содержит rubric scores."
    average = sum(score.score for score in scores) / len(scores)
    weak = [score.dimension.title for score in scores if score.score <= 2]
    strong = [score.dimension.title for score in scores if score.score >= 4]
    parts = [f"Средний system design rubric score: {average:.1f}/5."]
    if strong:
        parts.append("Сильные dimensions: " + ", ".join(strong[:3]) + ".")
    if weak:
        parts.append("Главные gaps: " + ", ".join(weak[:3]) + ".")
    if not strong and not weak:
        parts.append("Решение частично покрывает основные design dimensions.")
    return " ".join(parts)


def system_design_next_drills(scores: Sequence[AnswerEvaluationScore]) -> list[str]:
    drills: list[str] = []
    for score in sorted(scores, key=lambda item: (item.score, item.dimension.order_index)):
        if score.score >= 4 or not score.next_drill:
            continue
        if score.next_drill not in drills:
            drills.append(score.next_drill)
        if len(drills) == 4:
            break
    return drills


def _system_design_artifacts_by_section(
    artifacts: Sequence[SystemDesignArtifact],
) -> dict[str, str]:
    by_section: dict[str, list[str]] = {section: [] for section in SYSTEM_DESIGN_ARTIFACT_SECTIONS}
    for artifact in artifacts:
        if artifact.section in by_section and artifact.content.strip():
            by_section[artifact.section].append(artifact.content.strip())
    return {section: "\n".join(items) for section, items in by_section.items()}


def _score_system_design_dimension(
    dimension: RubricDimension,
    combined_text: str,
    artifacts_by_section: dict[str, str],
) -> AnswerEvaluationScore:
    sections = SYSTEM_DESIGN_SECTION_BY_DIMENSION.get(dimension.slug, ())
    direct_text = "\n".join(
        artifacts_by_section.get(section, "")
        for section in sections
        if artifacts_by_section.get(section, "").strip()
    )
    scoring_text = "\n".join(part for part in [direct_text, combined_text] if part.strip())
    word_count = len(SYSTEM_DESIGN_TOKEN_RE.findall(scoring_text))
    direct_word_count = len(SYSTEM_DESIGN_TOKEN_RE.findall(direct_text))
    keyword_hits = _system_design_keyword_hits(dimension.slug, scoring_text)

    if word_count == 0:
        score = 1
    elif direct_text:
        score = 3
        if direct_word_count >= 20 or keyword_hits >= 3:
            score = 4
        if direct_word_count >= 45 and keyword_hits >= 5:
            score = 5
    elif keyword_hits >= 5:
        score = 4
    elif keyword_hits >= 2:
        score = 3
    elif keyword_hits >= 1 or word_count >= 40:
        score = 2
    else:
        score = 1

    evidence = _system_design_evidence(dimension, score, direct_text, combined_text)
    gap = "Нет явного gap для этого system design dimension." if score >= 4 else SYSTEM_DESIGN_DIMENSION_GAPS.get(
        dimension.slug,
        "Добавь больше конкретики по этому system design dimension.",
    )
    next_drill = None if score >= 4 else SYSTEM_DESIGN_DIMENSION_DRILLS.get(
        dimension.slug,
        "Повтори этот system design dimension на следующем mock interview.",
    )
    return AnswerEvaluationScore(
        dimension=dimension,
        score=score,
        evidence=evidence,
        gaps=gap,
        next_drill=next_drill,
    )


def _system_design_keyword_hits(slug: str, text: str) -> int:
    lowered = text.lower()
    return sum(1 for keyword in SYSTEM_DESIGN_DIMENSION_KEYWORDS.get(slug, ()) if keyword in lowered)


def _system_design_evidence(
    dimension: RubricDimension,
    score: int,
    direct_text: str,
    combined_text: str,
) -> str:
    if direct_text.strip():
        return f'Наблюдаемое evidence из artifact section: "{_snippet(direct_text)}"'
    if score >= 2 and combined_text.strip():
        return f'Наблюдаемое evidence из transcript/artifacts для {dimension.title}: "{_snippet(combined_text)}"'
    return "В transcript/artifacts нет достаточного наблюдаемого evidence для этого system design dimension."


def _snippet(text: str, limit: int = 180) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."
