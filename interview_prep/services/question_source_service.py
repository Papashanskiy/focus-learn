from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from interview_prep.domain.models import (
    QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
    Question,
    QuestionSourceSnapshot,
)
from interview_prep.infra.repositories import SQLiteRepository


@dataclass(frozen=True)
class QuestionSourceDefinition:
    source_id: str
    title: str
    url: str
    category_hints: tuple[str, ...]


@dataclass(frozen=True)
class QuestionSourceRefreshResult:
    snapshots: tuple[QuestionSourceSnapshot, ...]
    saved_count: int
    dry_run: bool


@dataclass(frozen=True)
class SourceBackedCandidateTemplate:
    source_id: str
    topic_slug: str
    difficulty: str
    prompt: str
    hint: str
    reference_answer: str
    frequency_hint: str


@dataclass(frozen=True)
class SourceBackedCandidateResult:
    candidates: tuple[Question, ...]
    created_count: int
    skipped_count: int
    dry_run: bool


WHITELISTED_QUESTION_SOURCES: tuple[QuestionSourceDefinition, ...] = (
    QuestionSourceDefinition(
        "S01",
        "Python data model",
        "https://docs.python.org/3/reference/datamodel.html",
        ("python-core", "descriptors", "context-managers", "generators", "object-model"),
    ),
    QuestionSourceDefinition(
        "S02",
        "Python asyncio",
        "https://docs.python.org/3/library/asyncio.html",
        ("async", "tasks", "event-loop", "queues", "cancellation", "synchronization"),
    ),
    QuestionSourceDefinition(
        "S03",
        "Python GIL glossary entry",
        "https://docs.python.org/3/glossary.html#term-global-interpreter-lock",
        ("concurrency", "gil", "threads", "cpu-bound"),
    ),
    QuestionSourceDefinition(
        "S04",
        "Python unittest",
        "https://docs.python.org/3/library/unittest.html",
        ("testing", "fixtures", "discovery", "isolation"),
    ),
    QuestionSourceDefinition(
        "S05",
        "HackerRank Interview Preparation Kit",
        "https://www.hackerrank.com/interview/interview-preparation-kit",
        ("coding-screen", "arrays", "hashmaps", "sorting", "strings", "graphs", "trees"),
    ),
    QuestionSourceDefinition(
        "S06",
        "FastAPI dependencies",
        "https://fastapi.tiangolo.com/tutorial/dependencies/",
        ("api", "dependency-injection", "validation", "composition", "testability"),
    ),
    QuestionSourceDefinition(
        "S07",
        "FastAPI security",
        "https://fastapi.tiangolo.com/tutorial/security/",
        ("api-security", "authn", "authz", "oauth2", "bearer-tokens"),
    ),
    QuestionSourceDefinition(
        "S08",
        "OWASP API Security Top 10 2023",
        "https://owasp.org/API-Security/editions/2023/en/0x11-t10/",
        ("api-security", "bola", "authentication", "authorization", "resource-consumption", "ssrf"),
    ),
    QuestionSourceDefinition(
        "S09",
        "PostgreSQL indexes",
        "https://www.postgresql.org/docs/current/indexes.html",
        ("sql", "postgres", "indexes", "query-performance"),
    ),
    QuestionSourceDefinition(
        "S10",
        "PostgreSQL EXPLAIN",
        "https://www.postgresql.org/docs/current/using-explain.html",
        ("sql", "query-plans", "performance-debugging"),
    ),
    QuestionSourceDefinition(
        "S11",
        "PostgreSQL transaction isolation",
        "https://www.postgresql.org/docs/current/transaction-iso.html",
        ("sql", "transactions", "isolation", "anomalies", "locking"),
    ),
    QuestionSourceDefinition(
        "S12",
        "System Design Primer",
        "https://github.com/donnemartin/system-design-primer",
        ("system-design", "caching", "queues", "databases", "consistency", "scaling"),
    ),
    QuestionSourceDefinition(
        "S13",
        "AWS Well-Architected Framework definitions",
        "https://docs.aws.amazon.com/wellarchitected/latest/framework/definitions.html",
        ("architecture", "reliability", "security", "operations", "performance", "cost"),
    ),
    QuestionSourceDefinition(
        "S14",
        "Google SRE: Embracing Risk",
        "https://sre.google/sre-book/embracing-risk/",
        ("sre", "slo", "error-budget", "reliability", "operations"),
    ),
    QuestionSourceDefinition(
        "S15",
        "Treegarden backend developer interview questions 2026",
        "https://treegarden.io/interview-questions/backend-developer/",
        ("backend-interview", "data-modeling", "api-evolution", "resilience", "auth", "queues"),
    ),
    QuestionSourceDefinition(
        "S16",
        "KORE1 Python developer interview questions 2026",
        "https://www.kore1.com/python-developer-interview-questions/",
        ("python-interview", "python-core", "async", "frameworks", "live-coding", "system-design"),
    ),
)


SOURCE_BACKED_CANDIDATE_TEMPLATES: tuple[SourceBackedCandidateTemplate, ...] = (
    SourceBackedCandidateTemplate(
        "S01",
        "python-runtime",
        "senior",
        "В ORM-модели поле реализовано через descriptor. Как ты объяснишь порядок вызовов descriptor protocol, где могут появиться скрытые I/O или cache side effects, и как это проверить тестами?",
        "Покрой data/non-data descriptors, lookup order, __get__/__set__, lazy loading, invalidation и наблюдаемость.",
        "Сильный ответ связывает lookup order с data descriptor priority, показывает риск lazy I/O в property/descriptor, предлагает явную границу загрузки, cache invalidation и regression tests вокруг доступа к полю.",
        "official-docs:common-python-core",
    ),
    SourceBackedCandidateTemplate(
        "S02",
        "async-backend",
        "senior",
        "Async worker обрабатывает webhooks пачками и иногда зависает при shutdown. Как ты спроектируешь cancellation, bounded concurrency и backpressure, чтобы не потерять события?",
        "Покрой task lifecycle, timeouts, queues, graceful shutdown, idempotency и метрики queue lag.",
        "Сильный ответ задает bounded queue/concurrency, propagates cancellation, добавляет deadlines, idempotent processing, drain policy, retry/DLQ и metrics для queue lag/in-flight/error rates.",
        "official-docs:common-async-production",
    ),
    SourceBackedCandidateTemplate(
        "S03",
        "python-runtime",
        "middle+",
        "API endpoint выполняет CPU-heavy JSON normalization в threads и не ускоряется под нагрузкой. Как GIL влияет на это решение и какие варианты ты предложишь?",
        "Сравни threads, processes, native extensions, async offload, queue workers и profiling.",
        "Сильный ответ объясняет, что GIL ограничивает parallel Python bytecode, предлагает profiling, process pool или отдельный worker, batching, native/vectorized path и backpressure для тяжелых задач.",
        "official-docs:high-frequency-runtime",
    ),
    SourceBackedCandidateTemplate(
        "S04",
        "testing-quality",
        "middle+",
        "Тесты сервиса проходят по отдельности, но flaky при полном запуске suite. Как ты через unittest fixtures и isolation найдешь shared state leak?",
        "Покрой setUp/tearDown, временную БД, monkeypatch cleanup, order dependency и deterministic test data.",
        "Сильный ответ изолирует БД/clock/env/network, сбрасывает global state в fixtures, запускает random/order-focused диагностику и добавляет regression test на найденный shared state leak.",
        "official-docs:common-testing",
    ),
    SourceBackedCandidateTemplate(
        "S05",
        "python-runtime",
        "middle+",
        "На coding screen нужно найти частые элементы в stream-like input без загрузки всего набора в память. Как ты выберешь структуру данных и оценишь сложность?",
        "Покрой hash map/counter, memory bound, sorting tradeoff, edge cases и тесты на большие входы.",
        "Сильный ответ выбирает hash-based counting для bounded key space, объясняет O(n) time/O(k) memory, обсуждает streaming limits, ties, empty input и property/regression tests.",
        "interview-kit:frequent-coding-screen",
    ),
    SourceBackedCandidateTemplate(
        "S06",
        "system-design",
        "middle+",
        "FastAPI endpoint зависит от tenant context, auth user и repository. Как ты построишь dependency graph, чтобы код оставался тестируемым и не прятал business rules в DI?",
        "Покрой request scope, overrides in tests, validation boundaries, repository lifetime и observability.",
        "Сильный ответ отделяет transport dependencies от use-case layer, использует scoped dependencies, явные interfaces, dependency overrides в тестах и tracing/log context без business logic в DI.",
        "framework-docs:common-api-testability",
    ),
    SourceBackedCandidateTemplate(
        "S07",
        "system-design",
        "senior",
        "В API есть bearer-token auth, но часть операций требует object-level authorization. Где ты проверишь права и как избежишь смешивания authentication и authorization?",
        "Покрой identity, scopes/roles, object ownership, policy layer, audit log и negative tests.",
        "Сильный ответ разделяет token validation и policy checks, проверяет object ownership рядом с use case/data access, добавляет deny-by-default, audit events и тесты на cross-tenant доступ.",
        "framework-docs:common-api-security",
    ),
    SourceBackedCandidateTemplate(
        "S08",
        "system-design",
        "senior",
        "Multi-tenant API возвращает resource по id. Как ты защитишь endpoint от broken object level authorization и resource exhaustion?",
        "Покрой tenant scoping, authorization policy, pagination/rate limits, expensive filters и security logging.",
        "Сильный ответ включает tenant-bound queries, explicit policy checks, pagination and rate limits, query cost guards, alerting on denied access и tests на чужие ids.",
        "security-top10:high-frequency-api",
    ),
    SourceBackedCandidateTemplate(
        "S09",
        "databases",
        "middle+",
        "PostgreSQL query по статусу и created_at замедлился после роста таблицы. Как ты выберешь индекс и проверишь, что он реально помогает production workload?",
        "Покрой selectivity, composite/partial indexes, write cost, EXPLAIN и rollback plan.",
        "Сильный ответ смотрит predicates/order, выбирает composite или partial index по workload, проверяет EXPLAIN ANALYZE, учитывает write amplification и выкатывает миграцию с rollback/monitoring.",
        "official-docs:common-db-performance",
    ),
    SourceBackedCandidateTemplate(
        "S10",
        "databases",
        "senior",
        "EXPLAIN показывает sequential scan там, где команда ожидала index scan. Как ты разберешь, это проблема или нормальный план?",
        "Покрой cardinality estimates, stale statistics, selectivity, buffers, parameterized queries и realistic data.",
        "Сильный ответ сравнивает estimated/actual rows, проверяет statistics and data distribution, смотрит buffers/timing, тестирует realistic parameters и не форсит index без доказанного latency impact.",
        "official-docs:common-query-debugging",
    ),
    SourceBackedCandidateTemplate(
        "S11",
        "databases",
        "senior",
        "Два concurrent workflow иногда создают конфликтующие записи несмотря на транзакции. Как ты объяснишь возможную anomaly и выберешь isolation/locking strategy?",
        "Покрой read committed vs serializable, unique constraints, SELECT FOR UPDATE, retries и idempotency keys.",
        "Сильный ответ формулирует invariant, показывает race under weaker isolation, добавляет database constraint, row/advisory locks or serializable transaction с retry и idempotency key.",
        "official-docs:high-frequency-transactions",
    ),
    SourceBackedCandidateTemplate(
        "S12",
        "system-design",
        "senior",
        "Спроектируй notification service, который отправляет email/push с retry, rate limits и user preferences. Где будут queues, idempotency и consistency boundaries?",
        "Покрой API, data model, outbox, provider failures, dedupe, backoff, observability и abuse controls.",
        "Сильный ответ задает API and preferences model, uses outbox/queue workers, idempotency keys, provider-specific retry/backoff, rate limits, dead letters, metrics and audit trail.",
        "system-design:common-backend-scenario",
    ),
    SourceBackedCandidateTemplate(
        "S13",
        "system-design",
        "senior",
        "Перед запуском нового backend-сервиса тебя просят пройти architecture review. Какие reliability, security, cost и operational risks ты проверишь до production?",
        "Покрой SLO, failure modes, least privilege, capacity, deployment, rollback, runbooks и cost guardrails.",
        "Сильный ответ связывает requirements with SLOs, reviews failure modes, auth/secrets, capacity/cost, deployment rollback, observability, runbooks and ownership.",
        "architecture-framework:common-review",
    ),
    SourceBackedCandidateTemplate(
        "S14",
        "system-design",
        "senior",
        "Команда хочет поднять availability target с 99.5% до 99.95%. Как ты обсудишь error budget, стоимость и инженерные tradeoffs?",
        "Покрой user impact, SLO math, dependency limits, toil, redundancy, incident process и product decision.",
        "Сильный ответ переводит target в downtime/error budget, оценивает dependencies and cost, предлагает concrete reliability work, показывает tradeoff with feature velocity and gets product alignment.",
        "sre:common-reliability-tradeoff",
    ),
    SourceBackedCandidateTemplate(
        "S15",
        "system-design",
        "senior",
        "Backend API меняет контракт для мобильных клиентов с разными версиями. Как ты спланируешь rollout, backward compatibility и rollback?",
        "Покрой versioning, additive changes, migrations, feature flags, client adoption metrics и deprecation policy.",
        "Сильный ответ выбирает backward-compatible API evolution, staged rollout with flags, dual-read/write if needed, migration telemetry, rollback path and clear deprecation window.",
        "interview-coverage:common-backend-api",
    ),
    SourceBackedCandidateTemplate(
        "S16",
        "python-runtime",
        "senior",
        "В Python service растет memory usage после каждого batch job. Как ты отличишь reference leak, cache growth и allocator behavior?",
        "Покрой object references, tracemalloc, weakrefs, cache bounds, gc, native memory и production-safe profiling.",
        "Сильный ответ starts with reproducible workload, uses tracemalloc/heap snapshots, checks unbounded caches and reference cycles, separates Python vs native memory and adds bounded cache/regression monitoring.",
        "interview-coverage:common-python-debugging",
    ),
)


class QuestionSourceService:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def refresh(self, *, dry_run: bool = False, now: datetime | None = None) -> QuestionSourceRefreshResult:
        retrieved_at = (now or datetime.now()).replace(microsecond=0)
        snapshots = tuple(build_source_snapshot(source, retrieved_at) for source in WHITELISTED_QUESTION_SOURCES)
        if dry_run:
            return QuestionSourceRefreshResult(snapshots=snapshots, saved_count=0, dry_run=True)

        saved = tuple(self.repository.upsert_question_source_snapshot(snapshot) for snapshot in snapshots)
        return QuestionSourceRefreshResult(snapshots=saved, saved_count=len(saved), dry_run=False)

    def create_source_backed_candidates(self, *, dry_run: bool = False) -> SourceBackedCandidateResult:
        snapshots_by_source_id: dict[str, QuestionSourceSnapshot] = {}
        for snapshot in self.repository.list_question_source_snapshots():
            snapshots_by_source_id.setdefault(snapshot.source_id, snapshot)
        topics_by_slug = {topic.slug: topic for topic in self.repository.list_topics()}
        candidates: list[Question] = []
        created_count = 0
        skipped_count = 0

        for template in SOURCE_BACKED_CANDIDATE_TEMPLATES:
            snapshot = snapshots_by_source_id.get(template.source_id)
            topic = topics_by_slug.get(template.topic_slug)
            if snapshot is None or topic is None or topic.id is None:
                skipped_count += 1
                continue
            candidate = build_source_backed_candidate(template, snapshot, topic.id)
            if dry_run:
                candidates.append(candidate)
                continue
            if self.repository.question_exists(candidate.topic_id, candidate.prompt, candidate.source):
                existing = self._existing_candidate(candidate)
                if existing is not None:
                    candidates.append(existing)
                skipped_count += 1
                continue
            candidates.append(self.repository.add_question(candidate))
            created_count += 1

        return SourceBackedCandidateResult(
            candidates=tuple(candidates),
            created_count=created_count,
            skipped_count=skipped_count,
            dry_run=dry_run,
        )

    def _existing_candidate(self, candidate: Question) -> Question | None:
        for question in self.repository.list_questions(topic_id=candidate.topic_id):
            if question.source == candidate.source and question.prompt == candidate.prompt:
                return question
        return None


def build_source_snapshot(
    source: QuestionSourceDefinition,
    retrieved_at: datetime,
) -> QuestionSourceSnapshot:
    return QuestionSourceSnapshot(
        id=None,
        source_id=source.source_id,
        url=source.url,
        title=source.title,
        retrieved_at=retrieved_at,
        checksum=source_checksum(source),
        category_hints=list(source.category_hints),
        created_at=retrieved_at,
    )


def source_checksum(source: QuestionSourceDefinition) -> str:
    payload = {
        "source_id": source.source_id,
        "url": source.url,
        "title": source.title,
        "category_hints": list(source.category_hints),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_source_backed_candidate(
    template: SourceBackedCandidateTemplate,
    snapshot: QuestionSourceSnapshot,
    topic_id: int,
) -> Question:
    return Question(
        id=None,
        topic_id=topic_id,
        difficulty=template.difficulty,
        prompt=template.prompt,
        hint=template.hint,
        reference_answer=template.reference_answer,
        source="source-backed",
        source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
        source_url=snapshot.url,
        source_retrieved_at=snapshot.retrieved_at,
        source_category_hints=tuple(snapshot.category_hints),
        source_frequency_hint=template.frequency_hint,
    )
