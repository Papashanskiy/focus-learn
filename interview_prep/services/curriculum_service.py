from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from interview_prep.domain.models import (
    CurriculumObjective,
    CurriculumSubtopic,
    CurriculumTopic,
    Question,
    Topic,
)
from interview_prep.domain.rules import normalize_difficulty
from interview_prep.infra.llm import LLMClient
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.question_quality_rules import generated_question_source_quality_status


@dataclass(frozen=True)
class GeneratedQuestion:
    difficulty: str
    prompt: str
    hint: str
    reference_answer: str


@dataclass(frozen=True)
class GeneratedSubtopic:
    slug: str
    title: str
    description: str
    objectives: list[str]


@dataclass(frozen=True)
class GeneratedTopic:
    slug: str
    title: str
    description: str
    level: str
    objectives: list[str]
    subtopics: list[GeneratedSubtopic]
    questions: list[GeneratedQuestion]
    mock_scenarios: list[str]


@dataclass(frozen=True)
class GeneratedCurriculum:
    topics: list[GeneratedTopic]


@dataclass(frozen=True)
class CurriculumImportResult:
    topics_saved: int
    questions_saved: int
    curriculum: GeneratedCurriculum
    curriculum_topics_saved: int = 0
    subtopics_saved: int = 0
    objectives_saved: int = 0


@dataclass(frozen=True)
class TopicRecommendation:
    topic: Topic
    curriculum_topic: CurriculumTopic | None
    reason: str
    answers: int
    avg_self_score: float | None
    last_answered_at: datetime | None


@dataclass(frozen=True)
class CurriculumTopicStatus:
    curriculum_topic: CurriculumTopic
    topic_title: str | None
    subtopic_count: int
    objective_count: int
    question_count: int
    empty_zones: tuple[str, ...]


@dataclass(frozen=True)
class CurriculumStatus:
    source: str
    app_topic_count: int
    curriculum_topic_count: int
    subtopic_count: int
    objective_count: int
    question_count: int
    empty_zones: tuple[str, ...]
    topics: tuple[CurriculumTopicStatus, ...]


class CurriculumService:
    def __init__(self, repository: SQLiteRepository, llm: LLMClient):
        self.repository = repository
        self.llm = llm

    def generate(self, topic_count: int = 3, questions_per_topic: int = 3) -> GeneratedCurriculum:
        topic_count = max(1, min(topic_count, 12))
        questions_per_topic = max(1, min(questions_per_topic, 10))
        raw = self.llm.generate(build_curriculum_prompt(topic_count, questions_per_topic))
        return parse_curriculum(raw, topic_count, questions_per_topic)

    def generate_and_save(
        self,
        topic_count: int = 3,
        questions_per_topic: int = 3,
        dry_run: bool = False,
    ) -> CurriculumImportResult:
        curriculum = self.generate(topic_count, questions_per_topic)
        if dry_run:
            return CurriculumImportResult(0, 0, curriculum)

        topics_saved = 0
        questions_saved = 0
        curriculum_topics_saved = 0
        subtopics_saved = 0
        objectives_saved = 0
        for topic_index, generated_topic in enumerate(curriculum.topics):
            topic = self.repository.upsert_topic(
                Topic(
                    id=None,
                    slug=generated_topic.slug,
                    title=generated_topic.title,
                    description=generated_topic.description,
                    level=generated_topic.level,
                )
            )
            topics_saved += 1
            existing_curriculum_topic = self.repository.find_curriculum_topic_by_slug_source(
                generated_topic.slug,
                "llm-seed",
            )
            saved_curriculum_topic = self.repository.add_curriculum_topic(
                CurriculumTopic(
                    id=None,
                    topic_id=topic.id,
                    slug=generated_topic.slug,
                    title=generated_topic.title,
                    description=generated_topic.description,
                    level=generated_topic.level,
                    source="llm-seed",
                    order_index=topic_index + 1,
                )
            )
            if existing_curriculum_topic is None:
                curriculum_topics_saved += 1
            curriculum_topic_id = saved_curriculum_topic.id or 0
            for objective_index, objective in enumerate(generated_topic.objectives):
                existing_objective = self.repository.find_curriculum_objective_by_text_source(
                    curriculum_topic_id,
                    None,
                    objective,
                    "llm-seed",
                )
                self.repository.add_curriculum_objective(
                    CurriculumObjective(
                        id=None,
                        curriculum_topic_id=curriculum_topic_id,
                        curriculum_subtopic_id=None,
                        text=objective,
                        source="llm-seed",
                        order_index=objective_index + 1,
                    )
                )
                if existing_objective is None:
                    objectives_saved += 1
            for subtopic_index, generated_subtopic in enumerate(generated_topic.subtopics):
                existing_subtopic = self.repository.find_curriculum_subtopic_by_slug_source(
                    curriculum_topic_id,
                    generated_subtopic.slug,
                    "llm-seed",
                )
                saved_subtopic = self.repository.add_curriculum_subtopic(
                    CurriculumSubtopic(
                        id=None,
                        curriculum_topic_id=curriculum_topic_id,
                        slug=generated_subtopic.slug,
                        title=generated_subtopic.title,
                        description=generated_subtopic.description,
                        source="llm-seed",
                        order_index=subtopic_index + 1,
                    )
                )
                if existing_subtopic is None:
                    subtopics_saved += 1
                for objective_index, objective in enumerate(generated_subtopic.objectives):
                    existing_objective = self.repository.find_curriculum_objective_by_text_source(
                        curriculum_topic_id,
                        saved_subtopic.id,
                        objective,
                        "llm-seed",
                    )
                    self.repository.add_curriculum_objective(
                        CurriculumObjective(
                            id=None,
                            curriculum_topic_id=curriculum_topic_id,
                            curriculum_subtopic_id=saved_subtopic.id,
                            text=objective,
                            source="llm-seed",
                            order_index=objective_index + 1,
                        )
                    )
                    if existing_objective is None:
                        objectives_saved += 1
            for generated_question in generated_topic.questions:
                already_exists = self.repository.question_exists(
                    topic.id or 0,
                    generated_question.prompt,
                    "llm-seed",
                )
                saved = self.repository.add_question_once(
                    Question(
                        id=None,
                        topic_id=topic.id or 0,
                        difficulty=normalize_difficulty(generated_question.difficulty),
                        prompt=generated_question.prompt,
                        hint=generated_question.hint,
                        reference_answer=generated_question.reference_answer,
                        source="llm-seed",
                        source_quality_status=generated_question_source_quality_status(
                            generated_question.prompt
                        ),
                    )
                )
                if saved.id is not None and not already_exists:
                    questions_saved += 1
        return CurriculumImportResult(
            topics_saved=topics_saved,
            questions_saved=questions_saved,
            curriculum=curriculum,
            curriculum_topics_saved=curriculum_topics_saved,
            subtopics_saved=subtopics_saved,
            objectives_saved=objectives_saved,
        )

    def status(self, source: str = "llm-seed") -> CurriculumStatus:
        curriculum_topics = self.repository.list_curriculum_topics(source=source)
        topic_statuses: list[CurriculumTopicStatus] = []
        empty_zones: list[str] = []
        subtopic_count = 0
        objective_count = 0
        question_count = 0

        if not curriculum_topics:
            empty_zones.append("generated curriculum отсутствует; база работает только на bootstrap/fallback")

        for curriculum_topic in curriculum_topics:
            curriculum_topic_id = curriculum_topic.id or 0
            subtopics = self.repository.list_curriculum_subtopics(curriculum_topic_id)
            topic_objectives = self.repository.list_curriculum_objectives(curriculum_topic_id)
            subtopic_objective_count = 0
            topic_empty_zones: list[str] = []

            for subtopic in subtopics:
                objectives = self.repository.list_curriculum_objectives(curriculum_topic_id, subtopic.id)
                subtopic_objective_count += len(objectives)
                if not objectives:
                    topic_empty_zones.append(f"subtopic {subtopic.slug}: нет objectives")

            current_subtopic_count = len(subtopics)
            current_objective_count = len(topic_objectives) + subtopic_objective_count
            current_question_count = 0
            topic_title: str | None = None
            if curriculum_topic.topic_id is None:
                topic_empty_zones.append("нет связанной app topic")
            else:
                topic = self.repository.get_topic(curriculum_topic.topic_id)
                topic_title = topic.title if topic is not None else None
                if topic is None:
                    topic_empty_zones.append("связанная app topic не найдена")
                questions = self.repository.list_questions(curriculum_topic.topic_id)
                current_question_count = len([question for question in questions if question.source == source])

            if not subtopics:
                topic_empty_zones.append("нет subtopics")
            if current_objective_count == 0:
                topic_empty_zones.append("нет objectives")
            if current_question_count == 0:
                topic_empty_zones.append("нет generated questions")

            if topic_empty_zones:
                empty_zones.append(f"{curriculum_topic.slug}: {', '.join(topic_empty_zones)}")

            subtopic_count += current_subtopic_count
            objective_count += current_objective_count
            question_count += current_question_count
            topic_statuses.append(
                CurriculumTopicStatus(
                    curriculum_topic=curriculum_topic,
                    topic_title=topic_title,
                    subtopic_count=current_subtopic_count,
                    objective_count=current_objective_count,
                    question_count=current_question_count,
                    empty_zones=tuple(topic_empty_zones),
                )
            )

        return CurriculumStatus(
            source=source,
            app_topic_count=len(self.repository.list_topics()),
            curriculum_topic_count=len(curriculum_topics),
            subtopic_count=subtopic_count,
            objective_count=objective_count,
            question_count=question_count,
            empty_zones=tuple(empty_zones),
            topics=tuple(topic_statuses),
        )

    def suggest_next_topic(
        self,
        source: str = "llm-seed",
        weak_score_threshold: int = 3,
    ) -> TopicRecommendation | None:
        curriculum_topics = [
            item for item in self.repository.list_curriculum_topics(source=source) if item.topic_id is not None
        ]
        candidates = self._recommendation_candidates(curriculum_topics)
        if not candidates:
            fallback_topics = self.repository.list_topics()
            candidates = self._recommendation_candidates([None] * len(fallback_topics), fallback_topics)
        if not candidates:
            return None

        unanswered = [candidate for candidate in candidates if candidate.answers == 0]
        if unanswered:
            selected = min(unanswered, key=lambda candidate: candidate.order_index)
            return selected.to_recommendation("Следующая новая тема по curriculum order.")

        weak = [
            candidate
            for candidate in candidates
            if candidate.avg_self_score is not None and candidate.avg_self_score <= weak_score_threshold
        ]
        if weak:
            selected = min(
                weak,
                key=lambda candidate: (
                    candidate.avg_self_score if candidate.avg_self_score is not None else 0.0,
                    candidate.last_answered_at or datetime.min,
                    candidate.order_index,
                ),
            )
            return selected.to_recommendation("Слабая тема по self-score; стоит повторить.")

        selected = min(
            candidates,
            key=lambda candidate: (
                candidate.last_answered_at or datetime.min,
                candidate.avg_self_score if candidate.avg_self_score is not None else 0.0,
                candidate.order_index,
            ),
        )
        return selected.to_recommendation("Самая давно отвеченная тема в curriculum.")

    def _recommendation_candidates(
        self,
        curriculum_topics: list[CurriculumTopic | None],
        fallback_topics: list[Topic] | None = None,
    ) -> list["_TopicRecommendationCandidate"]:
        metrics = self.repository.topic_practice_metrics()
        candidates: list[_TopicRecommendationCandidate] = []
        if fallback_topics is not None:
            for index, topic in enumerate(fallback_topics):
                candidates.append(_TopicRecommendationCandidate.from_topic(topic, None, index + 1, metrics))
            return candidates

        for index, curriculum_topic in enumerate(curriculum_topics):
            if curriculum_topic is None or curriculum_topic.topic_id is None:
                continue
            topic = self.repository.get_topic(curriculum_topic.topic_id)
            if topic is None:
                continue
            candidates.append(
                _TopicRecommendationCandidate.from_topic(
                    topic,
                    curriculum_topic,
                    curriculum_topic.order_index or index + 1,
                    metrics,
                )
            )
        return candidates


@dataclass(frozen=True)
class _TopicRecommendationCandidate:
    topic: Topic
    curriculum_topic: CurriculumTopic | None
    order_index: int
    answers: int
    avg_self_score: float | None
    last_answered_at: datetime | None

    @classmethod
    def from_topic(
        cls,
        topic: Topic,
        curriculum_topic: CurriculumTopic | None,
        order_index: int,
        metrics: dict[int, dict[str, Any]],
    ) -> "_TopicRecommendationCandidate":
        item = metrics.get(topic.id or 0, {})
        last_answered_at = item.get("last_answered_at")
        if isinstance(last_answered_at, str):
            last_answered_at = datetime.fromisoformat(last_answered_at)
        return cls(
            topic=topic,
            curriculum_topic=curriculum_topic,
            order_index=order_index,
            answers=int(item.get("answers") or 0),
            avg_self_score=item.get("avg_self_score"),
            last_answered_at=last_answered_at,
        )

    def to_recommendation(self, reason: str) -> TopicRecommendation:
        return TopicRecommendation(
            topic=self.topic,
            curriculum_topic=self.curriculum_topic,
            reason=reason,
            answers=self.answers,
            avg_self_score=self.avg_self_score,
            last_answered_at=self.last_answered_at,
        )


def build_curriculum_prompt(topic_count: int, questions_per_topic: int) -> str:
    return f"""
Generate a Russian learning curriculum starter pack for a middle+ Python backend developer moving toward senior.
Return JSON only. No Markdown.

The JSON shape must be:
{{
  "topics": [
    {{
      "slug": "short-kebab-case",
      "title": "Русское название темы",
      "description": "Короткое описание",
      "level": "middle+ or senior",
      "objectives": ["learning objective 1", "learning objective 2"],
      "subtopics": [
        {{
          "slug": "short-kebab-case",
          "title": "Русское название подтемы",
          "description": "Короткое описание подтемы",
          "objectives": ["subtopic objective 1", "subtopic objective 2"]
        }}
      ],
      "questions": [
        {{
          "difficulty": "middle|middle+|senior",
          "prompt": "Вопрос на русском",
          "hint": "Подсказка на русском",
          "reference_answer": "Эталонный ответ на русском"
        }}
      ],
      "mock_scenarios": ["Короткий system design или production scenario на русском"]
    }}
  ]
}}

Requirements:
- Generate exactly {topic_count} topics.
- Generate exactly {questions_per_topic} questions per topic.
- Generate 2-4 subtopics per topic, with 1-3 learning objectives per subtopic.
- Cover Python internals, async backend, databases, distributed systems, system design, testing, observability and operational tradeoffs.
- Questions must be interview-grade, practical, and suitable for 60-minute daily practice.
- Reference answers must mention mechanisms, tradeoffs, failure modes and production examples.
- Do not include generic trivia.
""".strip()


def parse_curriculum(raw: str, topic_count: int = 3, questions_per_topic: int = 3) -> GeneratedCurriculum:
    payload = extract_json_object(raw)
    topics_payload = payload.get("topics") if isinstance(payload, dict) else None
    if not isinstance(topics_payload, list):
        return fallback_curriculum(topic_count, questions_per_topic)

    topics: list[GeneratedTopic] = []
    for index, item in enumerate(topics_payload):
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("title")) or f"LLM topic {index + 1}"
        slug = slugify(clean_text(item.get("slug")) or title)
        description = clean_text(item.get("description")) or "Сгенерированная тема подготовки."
        level = clean_text(item.get("level")) or "middle+"
        objectives = parse_string_list(item.get("objectives"))
        subtopics = parse_subtopics(item.get("subtopics"))
        scenarios = parse_string_list(item.get("mock_scenarios"))
        questions = parse_questions(item.get("questions"), questions_per_topic)
        topics.append(
            GeneratedTopic(
                slug=slug,
                title=title,
                description=description,
                level=level,
                objectives=objectives,
                subtopics=subtopics,
                questions=questions,
                mock_scenarios=scenarios,
            )
        )

    if not topics:
        return fallback_curriculum(topic_count, questions_per_topic)
    return GeneratedCurriculum(topics=topics[:topic_count])


def extract_json_object(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end >= start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def parse_questions(raw_questions: Any, questions_per_topic: int) -> list[GeneratedQuestion]:
    if not isinstance(raw_questions, list):
        return fallback_questions("сгенерированной теме", questions_per_topic)
    questions: list[GeneratedQuestion] = []
    for item in raw_questions:
        if not isinstance(item, dict):
            continue
        prompt = clean_text(item.get("prompt"))
        if not prompt:
            continue
        questions.append(
            GeneratedQuestion(
                difficulty=clean_text(item.get("difficulty")) or "middle+",
                prompt=prompt,
                hint=clean_text(item.get("hint")) or "Покрой механизм, tradeoffs и production failure modes.",
                reference_answer=clean_text(item.get("reference_answer"))
                or "Сильный ответ объясняет механизм, tradeoffs, failure modes и production-пример.",
            )
        )
    return questions[:questions_per_topic] or fallback_questions("сгенерированной теме", questions_per_topic)


def parse_subtopics(raw_subtopics: Any) -> list[GeneratedSubtopic]:
    if not isinstance(raw_subtopics, list):
        return []
    subtopics: list[GeneratedSubtopic] = []
    for index, item in enumerate(raw_subtopics):
        if not isinstance(item, dict):
            continue
        title = clean_text(item.get("title")) or f"Подтема {index + 1}"
        slug = slugify(clean_text(item.get("slug")) or title)
        description = clean_text(item.get("description")) or "Сгенерированная подтема curriculum."
        subtopics.append(
            GeneratedSubtopic(
                slug=slug,
                title=title,
                description=description,
                objectives=parse_string_list(item.get("objectives")),
            )
        )
    return subtopics


def fallback_curriculum(topic_count: int, questions_per_topic: int) -> GeneratedCurriculum:
    base_topics = [
        GeneratedTopic(
            slug="llm-python-runtime",
            title="Python runtime глубже middle+",
            description="Объектная модель, память, descriptors, import system, GIL и performance tradeoffs.",
            level="middle+",
            objectives=["Объяснять runtime-механику", "Связывать internals с backend production issues"],
            subtopics=[
                GeneratedSubtopic(
                    slug="descriptors-lookup",
                    title="Descriptors и lookup order",
                    description="Data/non-data descriptors, properties, methods и ORM patterns.",
                    objectives=["Объяснять порядок поиска атрибутов", "Связывать descriptors с production bugs"],
                )
            ],
            questions=fallback_questions("Python runtime", questions_per_topic),
            mock_scenarios=["Разобрать production incident из-за memory leak и blocking CPU-bound обработки."],
        ),
        GeneratedTopic(
            slug="llm-async-production",
            title="Async backend в production",
            description="Cancellation, backpressure, worker pools, очереди, retries и graceful shutdown.",
            level="senior",
            objectives=["Проектировать устойчивые async flows", "Диагностировать saturation и latency"],
            subtopics=[
                GeneratedSubtopic(
                    slug="backpressure-cancellation",
                    title="Backpressure и cancellation",
                    description="Bounded queues, cancellation propagation, retries и graceful shutdown.",
                    objectives=["Проектировать bounded async pipeline", "Диагностировать queue saturation"],
                )
            ],
            questions=fallback_questions("async backend", questions_per_topic),
            mock_scenarios=["Спроектировать worker service с external API limits и DLQ."],
        ),
        GeneratedTopic(
            slug="llm-system-design",
            title="System design для backend-сервисов",
            description="Requirements, API, storage, scaling, consistency, observability и failure modes.",
            level="senior",
            objectives=["Вести design discussion end-to-end", "Называть tradeoffs и operational risks"],
            subtopics=[
                GeneratedSubtopic(
                    slug="requirements-tradeoffs",
                    title="Requirements и tradeoffs",
                    description="Functional/non-functional requirements, constraints и design alternatives.",
                    objectives=["Формулировать assumptions", "Сравнивать alternatives через constraints"],
                )
            ],
            questions=fallback_questions("system design", questions_per_topic),
            mock_scenarios=["Спроектировать notification platform с retry, preferences и analytics."],
        ),
    ]
    return GeneratedCurriculum(topics=base_topics[:topic_count])


def fallback_questions(topic_title: str, count: int) -> list[GeneratedQuestion]:
    templates = fallback_question_bank(topic_title)
    if count <= len(templates):
        return templates[:count]
    return [templates[index % len(templates)] for index in range(count)]


def fallback_question_bank(topic_title: str) -> list[GeneratedQuestion]:
    normalized_title = topic_title.casefold()
    if "runtime" in normalized_title or "python" in normalized_title:
        return [
            GeneratedQuestion(
                "middle+",
                "FastAPI endpoint использует аргумент функции `payload={}` и иногда возвращает данные из предыдущего запроса. Как объяснить mutable default bug и безопасно исправить его?",
                "Покрой binding default arguments, shared state между вызовами, request-scoped данные и regression-тест на два последовательных запроса.",
                "Сильный ответ объясняет, что mutable default создается один раз при определении функции и переиспользуется. Исправление: `None` sentinel или factory внутри функции, изоляция request state, проверка module-level cache, regression-тест на отсутствие протечки и метрики/логи для похожих incidents.",
            ),
            GeneratedQuestion(
                "senior",
                "SQLAlchemy-модель делает N+1 запросы при чтении `user.profile.name`, хотя в коде это выглядит как обычный attribute access. Как descriptor protocol участвует в таком поведении?",
                "Разбери data/non-data descriptors, lookup order, lazy loading, скрытый IO в property/getter и диагностику числа SQL-запросов.",
                "Сильный ответ описывает порядок поиска атрибутов и то, что ORM descriptors могут запускать lazy load. Нужно заметить риск скрытого IO и N+1, предложить query logging, eager loading/selectinload, запрет side effects в property и тесты на число запросов.",
            ),
            GeneratedQuestion(
                "senior",
                "JSON normalization в Python API грузит один worker на 100% CPU, latency растет, а threads почти не помогают. Как GIL влияет на выбор исправления?",
                "Отдели CPU-bound и IO-bound работу, сравни process workers, process pool, native libraries, queue offload и operational limits.",
                "Сильный ответ объясняет, что GIL ограничивает параллельное выполнение CPU-bound Python bytecode в threads. Варианты: process workers, отдельный worker service, native/vectorized library, лимиты payload, backpressure и load-test с метриками CPU, latency и memory.",
            ),
        ]
    if "async" in normalized_title:
        return [
            GeneratedQuestion(
                "middle+",
                "Async worker обрабатывает webhooks, во время deploy получает cancellation и часть задач остается в статусе `processing`. Как спроектировать graceful shutdown?",
                "Покрой cancellation propagation, ack после commit, idempotency key, timeout на drain и recovery зависших задач.",
                "Сильный ответ переносит ack после durable commit, делает обработку идемпотентной, ловит cancellation только в безопасных границах, задает drain timeout, возвращает незавершенные задачи в очередь и добавляет метрики stuck jobs, retry count и shutdown duration.",
            ),
            GeneratedQuestion(
                "senior",
                "Сервис fan-out отправляет уведомления через provider API, получает 429, а Redis queue lag растет быстрее, чем workers успевают читать. Как добавить backpressure и retry budget?",
                "Разбери bounded concurrency, rate limits, exponential backoff с jitter, DLQ, приоритеты и alerts по queue lag.",
                "Сильный ответ ограничивает concurrency per provider, уважает rate-limit headers, вводит retry budget и backoff с jitter, отделяет retry/DLQ, приоритизирует важные события, показывает degrade mode и метрики queue lag, provider errors, saturation и age oldest job.",
            ),
            GeneratedQuestion(
                "senior",
                "Async endpoint параллельно запрашивает inventory, pricing и recommendations; одна зависимость висит 20 секунд и держит весь response. Как задать timeout и partial failure policy?",
                "Покрой `asyncio.wait_for`/task groups, cancellation дочерних задач, fallback response, tracing и contract с клиентом.",
                "Сильный ответ задает per-dependency timeout и общий request deadline, отменяет дочерние задачи при истечении бюджета, явно выбирает partial response или fail-fast по contract, логирует dependency latency/errors, добавляет traces и тесты на timeout/cancellation.",
            ),
        ]
    if "system" in normalized_title or "design" in normalized_title:
        return [
            GeneratedQuestion(
                "senior",
                "Спроектируй notification service для email/push/SMS: есть user preferences, quiet hours, provider fallback и всплеск событий после marketing campaign. С чего начнешь?",
                "Покрой requirements, API для enqueue/status/preferences, durable queue, idempotency, provider adapters и delivery observability.",
                "Сильный ответ начинает с scope, traffic и SLA, проектирует enqueue/status/preferences API, data model, durable queue/outbox, idempotency/deduplication, provider fallback с rate limits, quiet hours/time zones, retry/DLQ и dashboards по delivery, lag и provider health.",
            ),
            GeneratedQuestion(
                "senior",
                "Activity feed стал медленным для популярных аккаунтов: cache hit rate высокий, но иногда пользователи видят чужие приватные события. Как redesign cache policy?",
                "Разбери cache key с tenant/user/permissions, invalidation, TTL, hot keys, stampede protection и privacy regression tests.",
                "Сильный ответ фиксирует consistency и privacy constraints, включает user/tenant/permission scope в cache key, выбирает TTL/invalidation, защищает hot keys через single-flight/jitter/stale-while-revalidate, добавляет тесты на permission leaks и метрики hit rate, stale age и latency.",
            ),
            GeneratedQuestion(
                "senior",
                "Endpoint `/export` должен выгружать миллион строк из Postgres без OOM и без долгой блокировки транзакций. Как спроектировать streaming export?",
                "Покрой cursor/chunking, transaction lifetime, client disconnect, backpressure, limits, retries и memory metrics.",
                "Сильный ответ читает данные chunk-by-chunk, контролирует transaction/cursor lifetime, закрывает ресурсы при client disconnect, ограничивает размер выгрузки и concurrency, вводит timeout/backpressure, показывает retry semantics и проверяет bounded memory нагрузочным тестом.",
            ),
        ]
    return [
        GeneratedQuestion(
            "middle+",
            "Checkout endpoint иногда дважды списывает оплату, когда payment provider отвечает timeout после успешного charge. Как спроектировать idempotency и расследовать текущие дубли?",
            "Покрой idempotency key, уникальный constraint, provider reconciliation, retry policy, audit trail и customer impact.",
            "Сильный ответ связывает timeout с uncertain outcome, вводит idempotency key и unique constraint, сохраняет request/charge audit trail, делает reconciliation с provider, ограничивает retries, добавляет алерты по duplicate charge и regression-тесты на повтор запроса.",
        ),
        GeneratedQuestion(
            "senior",
            "Postgres migration добавляет `NOT NULL` колонку к таблице `orders` на 80M строк, и deploy нельзя останавливать. Как провести изменение без долгих locks?",
            "Разбери expand/contract, backfill batches, defaults, constraint validation, rollback и мониторинг lock waits.",
            "Сильный ответ предлагает multi-step migration: nullable column, batched backfill, code writing both versions, check constraint `NOT VALID`, validation отдельно, затем `NOT NULL`/cleanup. Нужно мониторить locks, replication lag, batch duration и иметь rollback plan.",
        ),
        GeneratedQuestion(
            "senior",
            "Queue worker пишет результаты в S3 и Postgres, но после retry появляются дубли файлов и разные статусы job. Как сделать обработку идемпотентной?",
            "Покрой deterministic object keys, transaction boundaries, status machine, retry safety, DLQ и reconciliation.",
            "Сильный ответ выбирает deterministic key или content hash, фиксирует state transitions, делает writes идемпотентными, разделяет external side effects и DB commit, добавляет reconciliation job, DLQ, метрики duplicate attempts и тесты на повтор после crash.",
        ),
    ]


def parse_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [clean_text(item) for item in value if clean_text(item)]


def clean_text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def slugify(value: str) -> str:
    lowered = value.strip().lower()
    translit = lowered.translate(
        str.maketrans(
            {
                "а": "a",
                "б": "b",
                "в": "v",
                "г": "g",
                "д": "d",
                "е": "e",
                "ё": "e",
                "ж": "zh",
                "з": "z",
                "и": "i",
                "й": "y",
                "к": "k",
                "л": "l",
                "м": "m",
                "н": "n",
                "о": "o",
                "п": "p",
                "р": "r",
                "с": "s",
                "т": "t",
                "у": "u",
                "ф": "f",
                "х": "h",
                "ц": "c",
                "ч": "ch",
                "ш": "sh",
                "щ": "sch",
                "ъ": "",
                "ы": "y",
                "ь": "",
                "э": "e",
                "ю": "yu",
                "я": "ya",
            }
        )
    )
    slug = re.sub(r"[^a-z0-9]+", "-", translit).strip("-")
    return slug or "llm-generated-topic"
