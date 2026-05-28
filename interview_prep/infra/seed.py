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
    source: str = "bootstrap"
    source_category_hints: tuple[str, ...] = ()
    source_frequency_hint: str | None = None


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

CANONICAL_2026_SOURCE = "canonical-2026"


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


CANONICAL_2026_QUESTIONS = [
    SeedQuestion(
        "python-runtime",
        "senior",
        "В FastAPI-сервисе после релиза часть пользователей начала видеть данные из чужого запроса. В коде нашли аргумент функции `payload={}` и общий cache dict на уровне модуля. Как объяснить причину бага и безопасно исправить его?",
        "Разбери binding default arguments при определении функции, shared mutable state, thread/async interleaving и migration path без потери совместимости.",
        "Сильный ответ объясняет, что изменяемый default создается один раз при определении функции и переиспользуется между вызовами, поэтому состояние может протекать между запросами. Исправление: использовать `None` sentinel или `default_factory`, явно создавать новый dict/list внутри функции, изолировать request-scoped state, добавить regression-тест на два последовательных запроса и проверить module-level cache на race conditions, TTL/locks и bounded size.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.65),
            SeedQuestionCompetency("testing-quality", weight=0.2),
            SeedQuestionCompetency("debugging-incidents", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("python-core", "mutable-state", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "ORM-модель в production неожиданно делает дополнительные SQL-запросы при чтении атрибута `user.profile.name`, а property с валидацией ломает bulk update. Как работают descriptor protocol и `@property`, и где здесь риск?",
        "Покрой data/non-data descriptors, attribute lookup order, lazy loading в ORM, side effects в getters и стратегию диагностики.",
        "Сильный ответ описывает порядок поиска атрибутов: data descriptors имеют приоритет над instance dict, затем instance attribute, non-data descriptor и class attribute. `property` является data descriptor, а ORM descriptors могут запускать lazy load или tracking. Риск в скрытых IO/side effects при обычном чтении атрибута, N+1 queries и несовместимости bulk operations. Диагностика: query logging, explicit eager loading/selectinload, запрет IO в property, тесты на число запросов и ясные domain methods для изменений.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.7),
            SeedQuestionCompetency("databases", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("python-core", "descriptors", "orm", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "CPU-bound обработчик JSON в Python API держит один worker на 100% CPU, latency растет, а добавление threads почти не помогает. Как GIL влияет на это решение и какие варианты исправления ты выберешь?",
        "Отдели IO-bound и CPU-bound работу, объясни GIL, multiprocessing/process workers, native extensions, async boundaries и operational tradeoffs.",
        "Сильный ответ объясняет, что GIL не дает нескольким Python threads параллельно исполнять CPU-bound bytecode в одном процессе, хотя threads полезны для IO. Варианты: вынести CPU-bound часть в process pool, отдельный worker service, больше process workers, оптимизированную native/library реализацию, streaming/limits для payload и backpressure. Нужно обсудить overhead сериализации, memory footprint, timeout/cancellation, capacity metrics и load-test до и после изменения.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.55),
            SeedQuestionCompetency("async-concurrency", weight=0.25),
            SeedQuestionCompetency("observability", weight=0.2),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("python-core", "gil", "performance", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "После добавления нового settings-модуля приложение иногда падает на старте с circular import, а в тестах это не воспроизводится. Как устроен import system Python и как ты стабилизируешь такой production startup?",
        "Покрой module cache `sys.modules`, частично инициализированные модули, side effects при import, dependency direction и smoke checks.",
        "Сильный ответ объясняет, что Python кладет module object в `sys.modules` до завершения выполнения файла, поэтому circular import может увидеть частично инициализированный модуль. Исправление: убрать import-time side effects, выделить чистые config/data contracts, перенести heavy imports внутрь функций только как временный mitigation, разорвать циклы через dependency inversion, добавить startup smoke test, проверку import graph и observability для boot failures.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.65),
            SeedQuestionCompetency("testing-quality", weight=0.2),
            SeedQuestionCompetency("debugging-incidents", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("python-core", "imports", "startup", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "Endpoint выгружает миллион строк из Postgres и иногда падает по памяти. Как использовать iterator/generator protocol в Python, чтобы сделать streaming безопасным, и какие failure modes нужно учесть?",
        "Свяжи lazy iteration, generator cleanup, chunk size, DB cursor lifetime, client disconnect, backpressure и observability.",
        "Сильный ответ предлагает не материализовать весь результат в list, а читать данные chunk-by-chunk через cursor/iterator и отдавать streaming response. Нужно контролировать размер chunk, lifetime transaction/cursor, cleanup генератора через `finally`/context manager, поведение при client disconnect, backpressure, timeout и retry semantics. В production нужны memory/latency metrics, лимиты экспорта, тест на bounded memory и понятный fallback для долгих выгрузок.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.45),
            SeedQuestionCompetency("databases", weight=0.3),
            SeedQuestionCompetency("distributed-systems", weight=0.15),
            SeedQuestionCompetency("observability", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("python-core", "generators", "streaming", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "На live coding нужно найти первый `user_id`, который повторился в потоке событий, и объяснить сложность решения. Какую структуру данных выберешь и какие edge cases проверишь?",
        "Сфокусируйся на hash set/hash map, порядке обработки, памяти, пустом input, больших потоках и том, как объяснить complexity без лишней оптимизации.",
        "Сильный ответ идет по событиям один раз, хранит уже seen `user_id` в set или счетчик в dict, возвращает первый повтор в порядке входного потока и явно называет O(n) time и O(k) memory, где k - число уникальных id до повтора. Нужно обсудить пустой поток, `None`/невалидные id, очень большой input, bounded memory вариант для настоящего стрима и тесты на повтор в начале, в конце и отсутствие повтора.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.45),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.3),
            SeedQuestionCompetency("testing-quality", weight=0.25),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("coding-screen", "hashmaps", "complexity", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "В coding screen дан список зависимостей задач вида `A -> B`, где B нельзя запускать до A. Как найти допустимый порядок запуска и обнаружить цикл?",
        "Покрой graph representation, indegree/topological sort или DFS colors, disconnected components, cycle reporting и complexity.",
        "Сильный ответ строит directed graph и либо запускает Kahn topological sort через indegree queue, либо DFS с состояниями visiting/visited. Если обработано меньше вершин, чем всего задач, или DFS встречает visiting node, есть цикл. Нужно учитывать disconnected components, duplicate edges, missing nodes, deterministic ordering при равных вариантах, O(V+E) complexity и тесты на простой DAG, несколько компонентов и цикл.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.4),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.2),
            SeedQuestionCompetency("testing-quality", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("coding-screen", "graphs", "topological-sort", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Public API endpoint `/orders/{id}` меняет response contract, но старые mobile clients еще живут несколько месяцев. Как бы ты спроектировал versioning, validation и deprecation plan?",
        "Разбери backward compatibility, request/response schemas, OpenAPI/docs, feature flags, telemetry по версиям clients и migration rollout.",
        "Сильный ответ сначала фиксирует совместимость и client population, затем выбирает contract strategy: additive changes by default, explicit versioning для breaking changes, stable error envelope, schema validation и documented deprecation window. Rollout должен включать OpenAPI/docs, telemetry по client/app versions, feature flag или dual-read/dual-write при необходимости, regression/contract tests и план удаления старого поведения только после подтвержденного adoption.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.45),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.25),
            SeedQuestionCompetency("testing-quality", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("api-web", "versioning", "validation", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "В FastAPI endpoint `GET /users/{user_id}/invoices` найден баг: авторизованный пользователь может подставить чужой `user_id` и увидеть счета. Как исправить authn/authz boundary и не сломать API?",
        "Покрой authentication vs authorization, object-level checks, dependency boundaries, audit logging, tests and safe rollout.",
        "Сильный ответ отделяет authentication от authorization: токен подтверждает identity, но каждое чтение user-owned resource должно проверять право доступа к конкретному object или tenant. Исправление: централизовать dependency/policy check, не доверять path parameter как principal, фильтровать запросы по current user/tenant, возвращать корректные 403/404 semantics, добавить audit logs и regression tests на чужой id, admin/service role и tenant boundary. Rollout требует проверки existing clients и monitoring denied attempts.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.4),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("testing-quality", weight=0.2),
            SeedQuestionCompetency("debugging-incidents", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("api-web", "api-security", "authorization", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "databases",
        "senior",
        "Endpoint поиска заказов стал медленным после роста таблицы до 50M rows. Запрос фильтрует по `tenant_id`, `status`, диапазону `created_at` и сортирует по `created_at DESC`. Как выберешь индекс и проверишь fix?",
        "Свяжи query pattern, selectivity/cardinality, composite index order, EXPLAIN ANALYZE, write/storage cost и rollout.",
        "Сильный ответ начинает с реального query shape и `EXPLAIN (ANALYZE, BUFFERS)`, смотрит selectivity `tenant_id/status`, диапазон и sort. Возможный индекс обсуждается как composite, например `(tenant_id, status, created_at DESC)` или вариант под самый частый фильтр, с учетом left-prefix, range condition и covering columns. Нужно назвать стоимость writes/storage, проверку на production-like data, rollout через concurrent index creation, monitoring latency/locks и rollback plan.",
        (
            SeedQuestionCompetency("databases", is_primary=True, weight=0.6),
            SeedQuestionCompetency("observability", weight=0.2),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.2),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("sql-postgres", "indexes", "query-plans", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "databases",
        "senior",
        "Webhook provider может прислать одно событие несколько раз и параллельно. Как в Postgres сделать обработку идемпотентной и какие transaction/isolation риски нужно учесть?",
        "Покрой unique constraint, `INSERT ... ON CONFLICT`, deduplication table, transaction boundary, side effects and retry safety.",
        "Сильный ответ выделяет stable event id/idempotency key, ставит unique constraint или отдельную deduplication table и выполняет claim события в одной transaction через `INSERT ... ON CONFLICT DO NOTHING` или equivalent lock-safe pattern. Side effects должны происходить после успешного claim или быть themselves idempotent. Нужно обсудить race conditions, isolation, deadlocks/lock wait, retries, outbox pattern для внешних эффектов, metrics по duplicate/failed events и тесты на concurrent duplicate delivery.",
        (
            SeedQuestionCompetency("databases", is_primary=True, weight=0.45),
            SeedQuestionCompetency("distributed-systems", weight=0.3),
            SeedQuestionCompetency("debugging-incidents", weight=0.15),
            SeedQuestionCompetency("observability", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("sql-postgres", "transactions", "idempotency", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "async-backend",
        "senior",
        "Async endpoint делает fan-out к 20 downstream API, пользователь отменяет запрос, а часть задач продолжает работать и держит соединения. Как спроектировать cancellation, timeout и cleanup?",
        "Покрой structured concurrency, task lifecycle, per-call/global timeout, cleanup resources, partial results и telemetry.",
        "Сильный ответ объясняет, что cancellation должна быть частью контракта async workflow: группировать child tasks, задавать per-call и общий deadline, корректно пробрасывать `CancelledError`, закрывать clients/cursors в `finally` или async context manager и не оставлять orphan tasks. Нужно определить политику partial results, bounded fan-out, retry только для безопасных операций, метрики по timeout/cancelled/downstream latency и regression-тесты на отмену запроса.",
        (
            SeedQuestionCompetency("async-concurrency", is_primary=True, weight=0.55),
            SeedQuestionCompetency("distributed-systems", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.15),
            SeedQuestionCompetency("testing-quality", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("async-queues", "cancellation", "timeouts", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "async-backend",
        "senior",
        "Async worker читает задачи из очереди быстрее, чем downstream payment API успевает отвечать; queue lag растет, retries усиливают нагрузку. Как задать backpressure и retry budget?",
        "Свяжи bounded queue/concurrency, rate limits, idempotency, exponential backoff with jitter, DLQ и observability.",
        "Сильный ответ ограничивает concurrency через semaphore/worker pool и очередь конечного размера, вводит rate limit под downstream capacity, retry budget с exponential backoff и jitter, DLQ или quarantine для poison messages и idempotency key для безопасных повторов. Нужно обсудить shutdown без потери in-flight задач, lag/age metrics, saturation alerts, circuit breaker или graceful degrade и нагрузочные тесты на burst.",
        (
            SeedQuestionCompetency("async-concurrency", is_primary=True, weight=0.45),
            SeedQuestionCompetency("distributed-systems", weight=0.3),
            SeedQuestionCompetency("observability", weight=0.15),
            SeedQuestionCompetency("debugging-incidents", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("async-queues", "backpressure", "retries", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Спроектируй notification service для email/push/SMS: есть user preferences, provider fallback, quiet hours и всплески событий после marketing campaign. С чего начнешь design?",
        "Покрой requirements, API, data model, queueing, deduplication, provider failures, rate limits and observability.",
        "Сильный ответ начинает с functional и non-functional requirements: каналы, preferences, latency/SLA, compliance и expected traffic. Design включает API для enqueue/status/preferences, normalized data model, durable queue/outbox, idempotency/deduplication, provider adapters с rate limits и fallback, retry/DLQ policy, quiet hours/time zones, template/versioning, metrics по delivery/failure/lag и dashboards по provider health.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.45),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("observability", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("system-design", "queues", "notifications", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Read-heavy endpoint отдает персональную ленту, p95 latency выросла, а данные могут быть слегка stale. Как выберешь caching strategy и защитишь систему от stampede?",
        "Разбери cache key, TTL, invalidation, consistency, hot keys, stampede protection, fallback и measurement.",
        "Сильный ответ фиксирует freshness tolerance и traffic shape, выбирает cache key с учетом user/tenant/permissions, TTL и invalidation strategy, защищает hot keys через single-flight/lock, jittered TTL, stale-while-revalidate или request coalescing. Нужно обсудить cache-aside vs write-through, consistency tradeoffs, permission leaks, fallback при cache outage, metrics hit rate/latency/stale age и load test на hot entities.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.4),
            SeedQuestionCompetency("distributed-systems", weight=0.3),
            SeedQuestionCompetency("observability", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("system-design", "caching", "consistency", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "Production bug: endpoint разрешил пользователю скачать чужой invoice из-за пропущенной object-level authorization проверки. Какой regression test suite ты добавишь?",
        "Покрой unit/service/API boundaries, fixtures, negative cases, tenant/user roles, audit logs и CI signal.",
        "Сильный ответ начинает с воспроизводящего failing test на конкретный authz boundary: чужой user_id/tenant, admin/service role, missing scope и archived/deleted resource. Unit tests проверяют policy/service, integration/API tests проверяют dependency wiring и DB filters, contract tests фиксируют 403/404 semantics. Важно не мокать саму проверку авторизации, добавить audit log assertions при необходимости и сделать тесты читаемыми для code review.",
        (
            SeedQuestionCompetency("testing-quality", is_primary=True, weight=0.45),
            SeedQuestionCompetency("system-design", weight=0.25),
            SeedQuestionCompetency("debugging-incidents", weight=0.2),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("testing-quality", "regression-tests", "api-security", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "Команда готовит zero-downtime migration: добавить non-null колонку, заполнить 200M rows и переключить код. Как протестировать migration/backfill до production?",
        "Свяжи expand/contract rollout, production-like data, batches, locks, rollback, metrics and verification queries.",
        "Сильный ответ предлагает expand/contract: nullable column или default-safe schema change, dual-write/read compatibility, backfill batches с limit и sleep, verification queries и только потом constraint/switch. Тесты включают migration on realistic volume sample, lock/timeout checks, idempotent resume after failure, old/new code compatibility, rollback plan, metrics rows/sec/error/lag и rehearsal на staging с production-like indexes.",
        (
            SeedQuestionCompetency("testing-quality", is_primary=True, weight=0.4),
            SeedQuestionCompetency("databases", weight=0.3),
            SeedQuestionCompetency("observability", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("testing-quality", "migrations", "backfill", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Сервис оформляет заказы, и бизнес просит SLO. Как определить SLI/SLO, error budget и правила релизов, чтобы это помогало принимать engineering decisions?",
        "Покрой user journey, latency/availability/error SLIs, burn rate alerts, release gating и tradeoffs.",
        "Сильный ответ выбирает SLIs вокруг пользовательского результата: successful checkout rate, latency p95/p99, availability и correctness для критичного пути. SLO должен быть измеримым и привязанным к business impact, error budget задает допустимый риск и влияет на release policy: при быстром burn rate замедлить релизы и фокусироваться на reliability work. Нужны dashboards, multi-window burn alerts, исключения для planned maintenance и регулярный review SLO против реального user impact.",
        (
            SeedQuestionCompetency("observability", is_primary=True, weight=0.45),
            SeedQuestionCompetency("system-design", weight=0.25),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.2),
            SeedQuestionCompetency("debugging-incidents", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("ops-reliability", "slo", "error-budget", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "После deploy выросли 500 errors только у части tenants, alert сработал поздно, rollback не сразу помог. Как проведешь incident response и какие follow-ups ожидаешь от senior-инженера?",
        "Покрой triage, blast radius, mitigation, rollback/feature flag, timeline, root cause, alerts and prevention.",
        "Сильный ответ сначала оценивает user impact и blast radius по tenants/endpoints/versions, назначает incident owner и делает быструю mitigation: rollback, feature flag, traffic shift или disable risky path. Затем фиксирует timeline, проверяет telemetry и deploy diff, подтверждает rollback результат и коммуницирует статус. Follow-ups: root cause без blame, regression tests, safer rollout/canary, better alert по symptom, dashboard gaps, runbook update и owner/date для preventive actions.",
        (
            SeedQuestionCompetency("debugging-incidents", is_primary=True, weight=0.45),
            SeedQuestionCompetency("observability", weight=0.25),
            SeedQuestionCompetency("testing-quality", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("ops-reliability", "incident-response", "deployments", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "На coding screen приходит отсортированный список availability windows `(start, end)` и новый interval. Как вставить его, слить пересечения и объяснить сложность?",
        "Покрой boundary conditions, inclusive/exclusive endpoints, один проход, пустой input, adjacent intervals и тесты.",
        "Сильный ответ проходит интервалы один раз: добавляет все окна до нового, затем расширяет новый interval пока есть overlap или допустимое adjacency rule, после чего добавляет хвост. Нужно явно договориться о семантике границ, обработать пустой список, полное покрытие, вставку в начало/конец, вложенный interval и несортированный input как invalid или precondition. Complexity: O(n) time, O(n) output memory.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.4),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.3),
            SeedQuestionCompetency("testing-quality", weight=0.3),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("coding-screen", "intervals", "complexity", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "Нужно найти longest substring without repeating characters в строке user input. Как построишь sliding-window решение и какие Unicode/edge cases уточнишь?",
        "Сфокусируйся на two pointers, last seen index, O(n), пустой строке, повторе в окне и definition of character.",
        "Сильный ответ держит левую границу окна и map символ -> последний index. При повторе внутри текущего окна двигает left на `last_seen[ch] + 1`, обновляет максимум и last_seen. Нужно назвать O(n) time, O(k) memory, проверить пустую строку, все одинаковые символы, повтор до текущего окна, длинный input и уточнить, считаем ли Unicode code points, grapheme clusters или normalized text.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.45),
            SeedQuestionCompetency("testing-quality", weight=0.25),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.3),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("coding-screen", "sliding-window", "strings", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "python-runtime",
        "senior",
        "Реализуй in-memory LRU cache для expensive lookups: `get`, `put`, capacity и eviction oldest recently used. Какие структуры данных выберешь?",
        "Покрой hash map + doubly linked list или OrderedDict, update recency, overwrite, capacity zero, thread safety и complexity.",
        "Сильный ответ использует dict для O(1) lookup и doubly linked list или `OrderedDict` для O(1) move-to-end/eviction. `get` возвращает значение и обновляет recency, `put` обновляет существующий ключ или вставляет новый, при превышении capacity удаляет least recently used. Нужно обсудить capacity 0/1, overwrite без роста размера, memory overhead, thread safety для shared cache, TTL если требуется и тесты на eviction order.",
        (
            SeedQuestionCompetency("python-runtime", is_primary=True, weight=0.45),
            SeedQuestionCompetency("system-design", weight=0.2),
            SeedQuestionCompetency("testing-quality", weight=0.2),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("coding-screen", "lru-cache", "data-structures", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Публичный login API начал получать burst credential-stuffing traffic. Как спроектировать rate limiting, lockout и abuse protection без DoS легитимных пользователей?",
        "Покрой dimensions ключа, sliding/token bucket, distributed counters, bypass risks, UX, observability and rollout.",
        "Сильный ответ разделяет лимиты по IP, account, device/session fingerprint и endpoint, выбирает token bucket или sliding window с distributed storage, добавляет progressive friction: CAPTCHA/step-up auth, temporary lockout с осторожностью к account-lockout DoS, denylist/allowlist и provider reputation. Нужно обсудить privacy, NAT/shared IP, consistent error semantics, telemetry по attempts/blocks/false positives, feature flags и нагрузочные тесты.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.35),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("observability", weight=0.2),
            SeedQuestionCompetency("debugging-incidents", weight=0.2),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("api-web", "rate-limiting", "abuse-protection", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "API `GET /events` возвращает миллионы rows и клиенты жалуются на пропуски при page/offset pagination. Как перейти на cursor pagination и сохранить backward compatibility?",
        "Покрой stable ordering, cursor contents, filters, deleted rows, old clients, response contract and tests.",
        "Сильный ответ выбирает стабильный порядок, например `(created_at, id)`, и opaque cursor с последним seen key, direction и filter hash. Cursor pagination избегает смещения при inserts/deletes и лучше для больших таблиц. Нужно сохранить старый offset endpoint на deprecation window или добавить новый параметр, зафиксировать response contract, валидировать cursor/filter mismatch, покрыть deleted rows/duplicate timestamps, добавить telemetry adoption и contract tests.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.35),
            SeedQuestionCompetency("databases", weight=0.3),
            SeedQuestionCompetency("testing-quality", weight=0.2),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("api-web", "pagination", "compatibility", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Сервис принимает payment callbacks от внешнего provider через webhook. Как спроектировать endpoint validation, replay protection и безопасную обработку ошибок?",
        "Покрой signature verification, timestamp tolerance, idempotency, raw body, secret rotation, retries and observability.",
        "Сильный ответ проверяет подпись по raw body и trusted secret до parsing side effects, валидирует timestamp tolerance для replay protection, сохраняет provider event id/idempotency key, быстро отвечает 2xx только после durable claim или ставит событие в очередь. Нужно обсудить secret rotation, duplicate/out-of-order events, 4xx vs 5xx retry semantics provider, audit logs, metrics по invalid signatures/duplicates/processing latency и тесты на tampered body.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.35),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("databases", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.2),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("api-web", "webhooks", "security", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "databases",
        "senior",
        "В checkout flow два параллельных запроса иногда продают последний item дважды. Какой transaction/isolation strategy выберешь в Postgres?",
        "Покрой row locks, optimistic concurrency, constraints, isolation levels, retry loop and user-facing errors.",
        "Сильный ответ фиксирует invariant inventory >= 0 и переносит проверку в transaction boundary. Варианты: `SELECT ... FOR UPDATE` на row inventory, atomic `UPDATE ... WHERE stock > 0 RETURNING`, optimistic version column с retry или constraint. Нужно обсудить READ COMMITTED vs SERIALIZABLE, deadlock/retry handling, timeout, idempotency checkout request, user-facing sold-out response и concurrency tests.",
        (
            SeedQuestionCompetency("databases", is_primary=True, weight=0.45),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("debugging-incidents", weight=0.15),
            SeedQuestionCompetency("testing-quality", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("sql-postgres", "transactions", "isolation", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "databases",
        "senior",
        "Нужно удалить 80M устаревших rows из Postgres без долгих locks и деградации latency. Как спланируешь cleanup job?",
        "Покрой batch deletes, indexes, vacuum/bloat, throttling, observability, pause/resume and rollback.",
        "Сильный ответ не запускает один большой delete, а делает batches по indexed predicate или primary key range, ограничивает batch size, добавляет sleep/throttle и pause/resume marker. Нужно оценить locks, replication lag, vacuum/bloat, autovacuum pressure, partition drop как альтернативу, метрики rows/sec/latency/lag/errors, dry-run count, canary batch и rollback/restore strategy для ошибочного predicate.",
        (
            SeedQuestionCompetency("databases", is_primary=True, weight=0.45),
            SeedQuestionCompetency("observability", weight=0.25),
            SeedQuestionCompetency("debugging-incidents", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("sql-postgres", "maintenance", "cleanup", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "databases",
        "senior",
        "После релиза иногда появляются deadlocks между update orders и insert order_events. Как найти причину и изменить transaction design?",
        "Покрой lock graph, consistent lock order, transaction duration, indexes, retry policy and observability.",
        "Сильный ответ собирает deadlock logs, lock wait events, query text и порядок операций, строит lock graph и ищет разные transaction paths с несовместимым порядком locks. Fix: единый порядок обновления ресурсов, короткие transactions, нужные indexes для foreign key/predicate checks, перенос внешних side effects наружу, idempotent retry на deadlock, alerts по lock waits/deadlocks и regression test с concurrent workers.",
        (
            SeedQuestionCompetency("databases", is_primary=True, weight=0.4),
            SeedQuestionCompetency("debugging-incidents", weight=0.25),
            SeedQuestionCompetency("testing-quality", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("sql-postgres", "deadlocks", "locks", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "async-backend",
        "senior",
        "Async worker получает SIGTERM во время deploy, часть задач уже взята из очереди. Как реализовать graceful shutdown без потери и двойной обработки?",
        "Покрой signal handling, stop accepting, in-flight deadline, ack/nack, idempotency, visibility timeout and metrics.",
        "Сильный ответ при SIGTERM останавливает прием новых задач, дает ограниченное время in-flight задачам завершиться, корректно делает ack только после durable success, а незавершенные задачи возвращает через nack/visibility timeout. Нужны idempotency keys для повторной доставки, cancellation-aware code, shutdown deadline, health/readiness switch, metrics in-flight/acks/nacks/shutdown timeout и тест с прерыванием worker.",
        (
            SeedQuestionCompetency("async-concurrency", is_primary=True, weight=0.4),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("observability", weight=0.2),
            SeedQuestionCompetency("testing-quality", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("async-queues", "graceful-shutdown", "workers", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "async-backend",
        "senior",
        "В asyncio-сервисе несколько coroutines обновляют общий in-memory rate-limit state, и иногда лимит обходится. Как расследовать race condition и исправить дизайн?",
        "Покрой atomicity, locks, single owner actor, external store, tests under concurrency and process boundaries.",
        "Сильный ответ объясняет, что `await` между read/modify/write может interleave coroutines, поэтому общий mutable state небезопасен без синхронизации. Fix зависит от scope: `asyncio.Lock` для одного process, actor/single-writer queue, atomic operation во внешнем store вроде Redis или перенос лимита в gateway. Нужно покрыть multi-process workers, lock contention, fairness, metrics rejected/allowed и stress test с concurrent requests.",
        (
            SeedQuestionCompetency("async-concurrency", is_primary=True, weight=0.45),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("testing-quality", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("async-queues", "race-conditions", "shared-state", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "async-backend",
        "senior",
        "Background task скачивает файлы из S3-like storage и пишет metadata в Postgres. Как ограничить concurrency, memory и retry behavior при больших файлах?",
        "Покрой streaming IO, bounded semaphore, chunk size, timeout, checksum, partial failure and cleanup.",
        "Сильный ответ стримит файлы chunks, не держит весь payload в памяти, ограничивает concurrency semaphore/worker pool, задает per-file timeout и retry budget только для безопасных операций. Нужно валидировать checksum/size, писать metadata в transaction после успешной загрузки или использовать staged state, очищать partial files, контролировать disk/memory, metrics bytes/sec/errors/retries и backpressure от Postgres/storage.",
        (
            SeedQuestionCompetency("async-concurrency", is_primary=True, weight=0.4),
            SeedQuestionCompetency("databases", weight=0.2),
            SeedQuestionCompetency("distributed-systems", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.2),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("async-queues", "streaming", "backpressure", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Спроектируй upload pipeline для больших CSV-файлов: validation, preview, async processing, error report и повторный запуск исправленного файла.",
        "Покрой API, object storage, job state machine, chunking, idempotency, data validation, partial failures and observability.",
        "Сильный ответ выделяет upload API с pre-signed URL или streaming endpoint, object storage для raw file, job state machine queued/validating/failed/succeeded, async workers, schema validation и error report по строкам. Нужно обсудить chunking, limits, malware/PII checks, idempotent retry по file checksum/job id, transactional apply после validation, progress API, metrics queue lag/rows processed/errors и cleanup policy.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.45),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("databases", weight=0.15),
            SeedQuestionCompetency("observability", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("system-design", "file-processing", "async-jobs", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Спроектируй feature flag service для backend-команд: targeting, gradual rollout, kill switch, audit log и low-latency evaluation.",
        "Покрой data model, SDK/cache, consistency, rollout safety, permissions, audit and failure mode.",
        "Сильный ответ описывает flags, environments, rules, segments и audit log, выбирает low-latency evaluation через SDK/cache с periodic refresh или push updates, а control plane хранит изменения durable. Нужно обсудить eventual consistency, default values при outage, kill switch, permission model, gradual rollout/canary, metrics exposure/evaluation errors, audit trail и тесты правил targeting.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.45),
            SeedQuestionCompetency("distributed-systems", weight=0.25),
            SeedQuestionCompetency("debugging-incidents", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("system-design", "feature-flags", "rollout-safety", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "system-design",
        "senior",
        "Спроектируй read model для dashboard, который агрегирует events из нескольких сервисов и должен быть быстрым, но допускает минутную задержку.",
        "Покрой event ingestion, denormalized projections, backfill, consistency, rebuild, API and monitoring.",
        "Сильный ответ выбирает asynchronous ingestion из events/CDC/queues, строит denormalized projection/read model под dashboard queries, задает watermark/lag и replay/backfill strategy. Нужно обсудить schema evolution, duplicate/out-of-order events, idempotent projection updates, rebuild from source of truth, API cache, stale data indicator, metrics lag/failures/rebuild duration и reconciliation checks.",
        (
            SeedQuestionCompetency("system-design", is_primary=True, weight=0.4),
            SeedQuestionCompetency("distributed-systems", weight=0.3),
            SeedQuestionCompetency("databases", weight=0.15),
            SeedQuestionCompetency("observability", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("system-design", "read-models", "event-driven", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "Внешний billing provider меняет JSON contract, а sandbox нестабилен. Как построить contract testing strategy, чтобы не ловить regressions в production?",
        "Покрой consumer contract, provider stubs, schema validation, golden payloads, sandbox smoke, versioning and alerting.",
        "Сильный ответ отделяет быстрые deterministic contract tests от нестабильного sandbox: хранит golden payloads/schema, валидирует required fields, error cases и signature behavior, использует provider stubs/fakes для CI и отдельный scheduled sandbox smoke. Нужно следить за provider changelog/versioning, backward compatibility, alert на contract drift, manual verification для breaking changes и не мокать собственную parsing logic в consumer tests.",
        (
            SeedQuestionCompetency("testing-quality", is_primary=True, weight=0.45),
            SeedQuestionCompetency("system-design", weight=0.2),
            SeedQuestionCompetency("distributed-systems", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("testing-quality", "contract-tests", "external-providers", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "CI периодически падает на flaky test async worker-а, команда привыкла rerun. Как найти root cause и стабилизировать test suite?",
        "Покрой nondeterminism, time control, queues, isolation, retries as smell, quarantine policy and ownership.",
        "Сильный ответ не нормализует rerun как решение: собирает failure frequency, seed/logs/timing, проверяет реальные sleeps, shared state, race conditions, unordered assertions и внешние зависимости. Fix: fake clock, deterministic queues/events, proper await conditions, isolated DB/temp resources, removal of order assumptions, stress repeat locally и временная quarantine только с owner/date. Метрика flaky rate должна быть видна команде.",
        (
            SeedQuestionCompetency("testing-quality", is_primary=True, weight=0.5),
            SeedQuestionCompetency("async-concurrency", weight=0.2),
            SeedQuestionCompetency("debugging-incidents", weight=0.2),
            SeedQuestionCompetency("observability", weight=0.1),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("testing-quality", "flaky-tests", "async-tests", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "Нужно безопасно рефакторить legacy service method на 400 строк, который трогает payments, emails и database writes. Какой test and rollout plan предложишь?",
        "Покрой characterization tests, seams, side effects, golden behavior, incremental extraction, feature flag and review strategy.",
        "Сильный ответ сначала фиксирует текущее observable behavior characterization tests/golden cases, выделяет side effects behind interfaces, покрывает critical paths и edge cases, затем делает маленькие extractions без изменения behavior. Для risky changes нужны feature flag, dual-run/shadow compare если возможно, metrics на divergence/errors, code review по contracts и rollback path. Не стоит переписывать все сразу без safety net.",
        (
            SeedQuestionCompetency("testing-quality", is_primary=True, weight=0.45),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.25),
            SeedQuestionCompetency("system-design", weight=0.15),
            SeedQuestionCompetency("debugging-incidents", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("testing-quality", "legacy-refactor", "safe-change", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "После инцидента выяснилось, что alerts были на CPU, а user impact заметили клиенты. Как перепроектировать monitoring и alerting?",
        "Покрой symptoms vs causes, SLI, alert thresholds, burn rate, dashboards, ownership and runbook.",
        "Сильный ответ переносит primary alerts на user-visible symptoms: availability, latency, error rate, correctness и queue lag для критичных journeys. Cause metrics CPU/memory остаются dashboards/debug сигналами. Нужны SLO/burn-rate alerts, thresholds с учетом noise, labels по tenant/endpoint/version, on-call ownership, runbook с first checks, synthetic checks где полезно и post-incident review alert gaps.",
        (
            SeedQuestionCompetency("observability", is_primary=True, weight=0.45),
            SeedQuestionCompetency("debugging-incidents", weight=0.25),
            SeedQuestionCompetency("system-design", weight=0.15),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("ops-reliability", "alerting", "sli-slo", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "Новый релиз дал рост latency только в одном region. Как проведешь canary analysis, rollback decision и коммуникацию с бизнесом?",
        "Покрой release metrics, regional blast radius, feature flags, error budget, rollback criteria, timeline and follow-ups.",
        "Сильный ответ сравнивает canary и baseline по latency/error/correctness/business metrics, сегментирует по region/version/tenant и оценивает blast radius. Если критерии rollback нарушены или error budget burn высок, нужно rollback/disable flag без ожидания полного root cause. Коммуникация включает impact, mitigation ETA и next update. Follow-ups: safer canary gates, regional dashboards, synthetic checks и regression coverage.",
        (
            SeedQuestionCompetency("debugging-incidents", is_primary=True, weight=0.4),
            SeedQuestionCompetency("observability", weight=0.25),
            SeedQuestionCompetency("communication-tradeoffs", weight=0.2),
            SeedQuestionCompetency("testing-quality", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("ops-reliability", "canary", "rollback", "must-know"),
        source_frequency_hint="high",
    ),
    SeedQuestion(
        "testing-quality",
        "senior",
        "Python service постепенно растет по памяти после каждого batch job run. Как расследовать memory leak и какие production safeguards поставишь?",
        "Покрой reproduction, heap profiling, object retention, caches, generators/resources, limits and deploy safety.",
        "Сильный ответ сначала подтверждает leak метриками RSS/heap/gc/object counts и воспроизводит на меньшем workload. Затем использует tracemalloc/heap profiler, смотрит retention paths, unbounded caches, global lists, циклы с finalizers, не закрытые cursors/files/clients и generator cleanup. Safeguards: bounded cache, resource context managers, memory limit/restart policy, batch size limits, alerts по slope и regression test или load test.",
        (
            SeedQuestionCompetency("debugging-incidents", is_primary=True, weight=0.35),
            SeedQuestionCompetency("python-runtime", weight=0.25),
            SeedQuestionCompetency("observability", weight=0.25),
            SeedQuestionCompetency("testing-quality", weight=0.15),
        ),
        source=CANONICAL_2026_SOURCE,
        source_category_hints=("ops-reliability", "memory-leak", "python-runtime", "must-know"),
        source_frequency_hint="high",
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
SEED_QUESTIONS = BOOTSTRAP_QUESTIONS + CANONICAL_2026_QUESTIONS
