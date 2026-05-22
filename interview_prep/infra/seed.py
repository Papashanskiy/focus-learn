from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SeedTopic:
    slug: str
    title: str
    description: str
    level: str


@dataclass(frozen=True)
class SeedQuestionCompetency:
    slug: str
    is_primary: bool = False
    weight: float = 1.0


@dataclass(frozen=True)
class SeedQuestion:
    topic_slug: str
    difficulty: str
    prompt: str
    hint: str
    reference_answer: str
    competency_links: tuple[SeedQuestionCompetency, ...] = ()


@dataclass(frozen=True)
class SeedCompetency:
    slug: str
    title: str
    description: str
    category: str
    level: str
    order_index: int


@dataclass(frozen=True)
class SeedRubricDimension:
    slug: str
    title: str
    description: str
    order_index: int


BOOTSTRAP_TOPICS = [
    SeedTopic(
        "python-runtime",
        "Python runtime и internals",
        "GIL, модель памяти, дескрипторы, imports, итераторы, async runtime.",
        "middle+",
    ),
    SeedTopic(
        "async-backend",
        "Async backend и concurrency",
        "asyncio, cancellation, backpressure, workers, reliability patterns.",
        "middle+",
    ),
    SeedTopic(
        "databases",
        "Базы данных и persistence",
        "Транзакции, уровни изоляции, индексы, query plans, миграции.",
        "middle+",
    ),
    SeedTopic(
        "system-design",
        "Backend system design",
        "API design, caching, очереди, consistency, observability, failure modes.",
        "senior",
    ),
    SeedTopic(
        "testing-quality",
        "Тестирование и engineering quality",
        "Стратегия тестирования, testability, CI, refactoring, code review.",
        "senior",
    ),
]


BOOTSTRAP_QUESTIONS = [
    SeedQuestion(
        "python-runtime",
        "middle+",
        "Объясни одну важную механику Python runtime и покажи, как она влияет на backend production-код.",
        "Можно выбрать descriptors, GIL, import system, память или iteration protocol. Обязательно свяжи механизм с tradeoffs и failure modes.",
        "Сильный ответ выбирает конкретный runtime-механизм, объясняет его поведение, показывает backend-пример, называет tradeoffs, failure modes и способ проверить гипотезу profiling, тестом или наблюдаемостью.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.7),
            SeedQuestionCompetency("observability", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
    ),
    SeedQuestion(
        "async-backend",
        "middle+",
        "Разбери production-риск в async backend flow и предложи надежный способ обработки.",
        "Покрой cancellation, timeouts, backpressure, retries, idempotency, observability или graceful shutdown.",
        "Сильный ответ фиксирует границы async flow, называет конкретный риск, объясняет механизм, добавляет bounded concurrency/timeouts/retry policy, idempotency, metrics/logs/traces и безопасный shutdown или degrade strategy.",
        (
            SeedQuestionCompetency("async-concurrency", is_primary=True, weight=0.65),
            SeedQuestionCompetency("distributed-systems", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.15),
        ),
    ),
    SeedQuestion(
        "databases",
        "middle+",
        "Как бы ты расследовал и исправил database problem в backend-сервисе?",
        "Выбери slow query, transaction anomaly, lock contention, migration risk или data integrity issue. Дай план диагностики и mitigation.",
        "Сильный ответ начинает с impact и конкретных симптомов, проверяет query plans/locks/isolation/indexes/data invariants, предлагает минимальный safe mitigation, затем добавляет monitoring и regression coverage.",
        (
            SeedQuestionCompetency("databases", is_primary=True, weight=0.65),
            SeedQuestionCompetency("debugging-incidents", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.15),
        ),
    ),
    SeedQuestion(
        "system-design",
        "middle+",
        "Спроектируй backend-сервис end-to-end и пройди основные design dimensions.",
        "Покрой requirements, API, data model, storage, scaling, consistency, queues, caching, observability и failure modes.",
        "Сильный ответ сначала фиксирует scope и non-functional requirements, затем предлагает API contracts, data model, storage и scaling strategy, объясняет consistency tradeoffs, async/background flows, cache policy, observability и failure handling.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.5),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("observability", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.1),
        ),
    ),
    SeedQuestion(
        "testing-quality",
        "middle+",
        "Как senior-инженер принимает решение о тестировании и качестве изменения в backend-коде?",
        "Свяжи risk, contract boundaries, unit/integration tests, migrations, observability и code review.",
        "Сильный ответ оценивает риск и blast radius, выбирает test scope по boundaries, не фиксирует low-value implementation details, проверяет migrations/external contracts, добавляет observability для production behavior и делает review focused on correctness, maintainability and failure modes.",
        (
            SeedQuestionCompetency("testing-quality", is_primary=True, weight=0.65),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.15),
        ),
    ),
]


SENIOR_COMPETENCIES = [
    SeedCompetency(
        "python-runtime",
        "Python Runtime",
        "Object model, memory, GIL, garbage collection, imports, packaging and performance tradeoffs.",
        "language-runtime",
        "senior",
        10,
    ),
    SeedCompetency(
        "async-concurrency",
        "Async and Concurrency",
        "Asyncio lifecycle, cancellation, backpressure, threads, processes and race conditions.",
        "concurrency",
        "senior",
        20,
    ),
    SeedCompetency(
        "databases",
        "Databases",
        "Data modeling, indexes, transactions, isolation, migrations and query tuning.",
        "data",
        "senior",
        30,
    ),
    SeedCompetency(
        "distributed-systems",
        "Distributed Systems",
        "Consistency, messaging, idempotency, retries, partitions and failure boundaries.",
        "architecture",
        "senior",
        40,
    ),
    SeedCompetency(
        "system-design",
        "System Design",
        "Requirements, API, data model, scaling, reliability and explicit tradeoffs.",
        "architecture",
        "senior",
        50,
    ),
    SeedCompetency(
        "observability",
        "Observability",
        "Logs, metrics, traces, SLOs, alerting and production diagnostics.",
        "operations",
        "senior",
        60,
    ),
    SeedCompetency(
        "testing-quality",
        "Testing and Quality",
        "Test strategy, CI, code review, maintainability and refactoring discipline.",
        "quality",
        "senior",
        70,
    ),
    SeedCompetency(
        "debugging-incidents",
        "Debugging and Incidents",
        "Triage, mitigation, root cause analysis, postmortems and follow-up prevention.",
        "operations",
        "senior",
        80,
    ),
    SeedCompetency(
        "communication-tradeoffs",
        "Communication and Tradeoffs",
        "Clarifying constraints, explaining options, communicating risk and scope.",
        "communication",
        "senior",
        90,
    ),
]


RUBRIC_DIMENSIONS = [
    SeedRubricDimension(
        "correctness",
        "Correctness",
        "Technical correctness, direct relevance to the question and absence of critical mistakes.",
        10,
    ),
    SeedRubricDimension(
        "depth",
        "Depth",
        "Reasons, mechanisms, constraints and senior-level details beyond surface facts.",
        20,
    ),
    SeedRubricDimension(
        "tradeoffs",
        "Tradeoffs",
        "Explicit alternatives, costs, compromises and conditions for choosing one approach.",
        30,
    ),
    SeedRubricDimension(
        "production-realism",
        "Production Realism",
        "Practical service concerns: operations, performance, security, data, migrations and maintenance.",
        40,
    ),
    SeedRubricDimension(
        "failure-modes",
        "Failure Modes",
        "Edge cases, degradation, retries, idempotency, consistency risks and failure boundaries.",
        50,
    ),
    SeedRubricDimension(
        "communication",
        "Communication",
        "Answer structure, clear assumptions, clarifying questions, prioritization and risk explanation.",
        60,
    ),
    SeedRubricDimension(
        "evidence",
        "Evidence",
        "Evaluation is grounded in observable candidate text, not points that appear only in the reference answer.",
        70,
    ),
]


SYSTEM_DESIGN_RUBRIC_DIMENSIONS = [
    SeedRubricDimension(
        "requirements",
        "Requirements",
        "Problem scope, functional and non-functional requirements, constraints and explicit assumptions.",
        10,
    ),
    SeedRubricDimension(
        "api",
        "API",
        "External contracts, request/response shapes, error handling, versioning and client-facing behavior.",
        20,
    ),
    SeedRubricDimension(
        "data-model",
        "Data Model",
        "Entities, relationships, storage choices, indexes, migrations and data lifecycle.",
        30,
    ),
    SeedRubricDimension(
        "scaling",
        "Scaling",
        "Capacity planning, traffic shape, bottlenecks, partitioning, caching and background processing.",
        40,
    ),
    SeedRubricDimension(
        "consistency",
        "Consistency",
        "Consistency guarantees, transactions, ordering, idempotency, conflict handling and stale reads.",
        50,
    ),
    SeedRubricDimension(
        "reliability",
        "Reliability",
        "Failure modes, retries, timeouts, degradation, disaster recovery and operational safeguards.",
        60,
    ),
    SeedRubricDimension(
        "observability",
        "Observability",
        "Logs, metrics, traces, alerts, dashboards and incident diagnostics tied to user impact.",
        70,
    ),
    SeedRubricDimension(
        "tradeoffs",
        "Tradeoffs",
        "Clear alternatives, decision criteria, risks, costs and explicit reasoning under constraints.",
        80,
    ),
]


SEED_TOPICS = BOOTSTRAP_TOPICS
SEED_QUESTIONS = BOOTSTRAP_QUESTIONS
