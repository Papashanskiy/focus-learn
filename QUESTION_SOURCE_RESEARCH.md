# Question Source Research

Retrieved: 2026-05-27

Purpose: create a small, repeatable source note for the upcoming source refresh, source-backed candidates and canonical question pack work. This file is research input only; it does not add questions to SQLite and does not copy external question lists verbatim.

## Source Policy

- Use external sources to identify coverage areas, repeated interview patterns and current terminology.
- Write all future candidate questions in our own words, grounded in production scenarios and expected mechanisms.
- Prefer primary technical references for correctness and use interview-market pages only as weak evidence of frequency.
- Do not import external question text directly into seed data, prompts or generated candidates.

## Source Inventory

| ID | Source | Retrieved at | Category hints | Notes for future refresh |
| --- | --- | --- | --- | --- |
| S01 | [Python data model](https://docs.python.org/3/reference/datamodel.html) | 2026-05-27 | python-core, descriptors, context-managers, generators, object-model | Primary reference for precise Python semantics. |
| S02 | [Python asyncio](https://docs.python.org/3/library/asyncio.html) | 2026-05-27 | async, tasks, event-loop, queues, cancellation, synchronization | Primary reference for async interview mechanics. |
| S03 | [Python GIL glossary entry](https://docs.python.org/3/glossary.html#term-global-interpreter-lock) | 2026-05-27 | concurrency, gil, threads, cpu-bound | Use with `asyncio` and executor/process questions. |
| S04 | [Python unittest](https://docs.python.org/3/library/unittest.html) | 2026-05-27 | testing, fixtures, discovery, isolation | Primary reference for baseline test vocabulary. |
| S05 | [HackerRank Interview Preparation Kit](https://www.hackerrank.com/interview/interview-preparation-kit) | 2026-05-27 | coding-screen, arrays, hashmaps, sorting, strings, greedy, search, dp, stacks, queues, graphs, trees | Frequency signal for coding categories, not a source for copied prompts. |
| S06 | [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) | 2026-05-27 | api, dependency-injection, validation, composition, testability | Useful for Python web/API scenario framing. |
| S07 | [FastAPI security](https://fastapi.tiangolo.com/tutorial/security/) | 2026-05-27 | api-security, authn, authz, oauth2, bearer-tokens | Use with OWASP for concrete backend API security scenarios. |
| S08 | [OWASP API Security Top 10 2023](https://owasp.org/API-Security/editions/2023/en/0x11-t10/) | 2026-05-27 | api-security, bola, authentication, authorization, resource-consumption, ssrf, misconfiguration | Primary security taxonomy for API/web questions. |
| S09 | [PostgreSQL indexes](https://www.postgresql.org/docs/current/indexes.html) | 2026-05-27 | sql, postgres, indexes, query-performance | Primary reference for indexing tradeoffs. |
| S10 | [PostgreSQL EXPLAIN](https://www.postgresql.org/docs/current/using-explain.html) | 2026-05-27 | sql, query-plans, performance-debugging | Basis for slow-query diagnosis prompts. |
| S11 | [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html) | 2026-05-27 | sql, transactions, isolation, anomalies, locking | Basis for race condition and consistency prompts. |
| S12 | [System Design Primer](https://github.com/donnemartin/system-design-primer) | 2026-05-27 | system-design, caching, queues, databases, consistency, scaling | Broad interview preparation map; paraphrase heavily. |
| S13 | [AWS Well-Architected Framework definitions](https://docs.aws.amazon.com/wellarchitected/latest/framework/definitions.html) | 2026-05-27 | architecture, reliability, security, operations, performance, cost | Useful rubric language for system design and ops tradeoffs. |
| S14 | [Google SRE: Embracing Risk](https://sre.google/sre-book/embracing-risk/) | 2026-05-27 | sre, slo, error-budget, reliability, operations | Basis for readiness questions about reliability judgment. |
| S15 | [Treegarden backend developer interview questions 2026](https://treegarden.io/interview-questions/backend-developer/) | 2026-05-27 | backend-interview, data-modeling, api-evolution, resilience, auth, queues, caching, incidents, observability, idempotency | Secondary market signal only; do not copy questions. |
| S16 | [KORE1 Python developer interview questions 2026](https://www.kore1.com/python-developer-interview-questions/) | 2026-05-27 | python-interview, python-core, async, frameworks, live-coding, system-design | Secondary market signal only; staffing-page claims need corroboration. |

## Synthesized Coverage Map

| Coverage area | Priority | Source signals | What canonical questions should test |
| --- | --- | --- | --- |
| Python core/runtime | P0 | S01, S03, S16 | Object model, mutability, descriptors/properties, decorators, generators, context managers, exceptions, memory/runtime implications. |
| Python concurrency and async | P0 | S02, S03, S15, S16 | Event loop reasoning, cancellation/timeouts, queues/backpressure, GIL-aware workload classification, async vs threads/processes. |
| Coding screen patterns | P0 | S05 | Arrays/strings, hash maps, sorting/search, stacks/queues, graph/tree traversal, dynamic programming and complexity explanation. |
| API/web design | P0 | S06, S07, S08, S15 | Versioning, validation, dependency boundaries, auth/authz, rate limits, idempotency, error handling and OpenAPI contracts. |
| SQL/Postgres | P0 | S09, S10, S11, S15 | Index choice, EXPLAIN-based diagnosis, isolation anomalies, locking, schema evolution, pagination and idempotent writes. |
| System design | P0 | S12, S13, S15 | Requirements, non-functional constraints, scaling, data model, caching, queues, consistency, partial failure and tradeoffs. |
| Testing and engineering quality | P1 | S04, S06, S15 | Test scope, fixtures, integration seams, failure-case tests, migration tests, CI signal and regression prevention. |
| Ops/reliability | P1 | S13, S14, S15 | Observability, SLO/error budget reasoning, alert quality, incident response, deployment rollback and operational ownership. |
| Security fundamentals | P1 | S07, S08, S15 | Object/function-level authorization, authentication mistakes, injection prevention, resource limits, SSRF and secure defaults. |

## Paraphrased Candidate Themes

These are not final seed prompts. They are canonical-style themes to convert into original questions later.

### Python Core/Runtime

- Explain why a mutable default argument leaks state across calls, then rewrite a small function safely.
- Predict attribute lookup when an instance attribute, property and descriptor-like object compete for the same name.
- Design a retry decorator for a flaky dependency call while preserving function metadata and exception behavior.
- Use a context manager to protect a resource or transaction and explain how cleanup behaves on exceptions.
- Choose between list, iterator and generator for streaming a large response through a backend pipeline.
- Compare `@staticmethod`, `@classmethod` and instance methods in a class used by a service layer.

### Python Async/Concurrency

- Diagnose why an `asyncio` service handles many slow HTTP calls well but stalls on CPU-heavy work.
- Add cancellation, timeout and cleanup handling to an async workflow that fans out to several downstream APIs.
- Design backpressure for a worker that accepts tasks faster than it can process them.
- Decide when to use threads, a process pool or async I/O for a mixed workload.
- Explain failure behavior for retries around a non-idempotent async operation.

### Coding Screen

- Solve a frequency-count problem with a hash map and justify time/space complexity.
- Use two pointers or a sliding window on a string/array problem without falling back to quadratic scans.
- Pick a stack, queue or heap for a stream-processing problem and explain the invariant.
- Traverse a dependency graph and detect cycles or unreachable nodes.
- Choose between greedy and dynamic programming for an optimization problem and identify the subproblem state.

### API/Web

- Evolve a public API endpoint while keeping older clients working and documenting deprecation.
- Separate authentication from authorization for a resource endpoint that exposes user-owned objects.
- Make a webhook handler idempotent when the provider can retry the same event concurrently.
- Add rate limits and request validation to an expensive endpoint without hiding product errors.
- Use dependency injection to share database/session/auth logic while keeping handlers testable.

### SQL/Postgres

- Choose indexes from concrete query patterns and explain read/write costs.
- Read an `EXPLAIN` plan to diagnose a slow endpoint and validate the fix after deployment.
- Explain what can go wrong when two requests update the same logical record under different isolation levels.
- Design a zero-downtime migration for a column used by a high-traffic endpoint.
- Use `INSERT ... ON CONFLICT` or a deduplication table to make event processing safe under retries.
- Compare offset pagination and keyset pagination for large tables with changing data.

### System Design

- Start from requirements and non-functional constraints before drawing components for a backend service.
- Design caching for a read-heavy endpoint and handle stale data, stampedes and invalidation.
- Handle partial failure across multiple downstream services with timeouts, retries, fallbacks and user-visible behavior.
- Decide between synchronous API calls and queue-based processing for a workflow with latency and reliability constraints.
- Choose storage and partitioning strategy for an entity with skewed access patterns.
- Explain observability for a new service using request rate, errors, latency and business-level signals.

### Testing/Quality/Ops

- Draw the boundary between unit, integration and end-to-end tests for a service method plus API endpoint.
- Add regression coverage for a production bug without coupling the test to incidental implementation details.
- Test a migration or data backfill before it runs on production-scale data.
- Define an SLO and explain what an error budget changes about release decisions.
- Improve an alert that pages too often but misses real user impact.
- Walk through an incident with mitigation, blast radius, rollback and a concrete process change.

## Initial Canonical Pack Shape

For the future `canonical-2026` seed pack, start with 40 questions distributed as:

- Python core/runtime: 6
- Python async/concurrency: 5
- Coding screen: 5
- API/web/security: 6
- SQL/Postgres: 6
- System design: 6
- Testing/quality: 3
- Ops/reliability: 3

Question style should be scenario-first: include a small production constraint, ask for mechanisms and tradeoffs, and avoid prompts that can be answered with only vocabulary. Every canonical question should map to existing tags/competencies first; add schema only if tags cannot express frequency/type metadata.

## Open Follow-ups

- Convert this source inventory into the whitelist for `questions-source refresh --dry-run`.
- Store per-source checksum and title metadata before generating any candidates.
- Add source-backed candidate fields only after the refresh snapshot contract is explicit.
- Keep the canonical pack non-LLM-authored and reviewed in repo so first-run coverage is deterministic.
