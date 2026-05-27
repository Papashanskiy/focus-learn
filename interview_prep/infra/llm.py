from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from interview_prep.infra.config import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT,
)


class LLMClient:
    def generate(self, prompt: str) -> str:
        raise NotImplementedError


@dataclass
class OllamaClient(LLMClient):
    model: str = DEFAULT_OLLAMA_MODEL
    base_url: str = DEFAULT_OLLAMA_BASE_URL
    timeout_seconds: float = DEFAULT_OLLAMA_TIMEOUT

    def generate(self, prompt: str) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2},
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url.rstrip('/')}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise LLMUnavailable(str(exc)) from exc
        text = body.get("response")
        if not isinstance(text, str) or not text.strip():
            raise LLMUnavailable("Ollama returned an empty response")
        return text.strip()


class LLMUnavailable(RuntimeError):
    pass


class FallbackLLMClient(LLMClient):
    def generate(self, prompt: str) -> str:
        lowered = prompt.lower()
        if "source_backed_question_curator_json" in lowered:
            return json.dumps(
                {
                    "decision": "quarantined",
                    "confidence": 0.55,
                    "score": 2,
                    "rationale": "Fallback curator cannot verify ambiguous source-backed evidence.",
                    "source_evidence": "fallback-client-no-live-model",
                    "quality_flags": ["fallback_quarantine"],
                }
            )
        if "learning curriculum starter pack" in lowered:
            return json.dumps(
                {
                    "topics": [
                        {
                            "slug": "llm-python-runtime",
                            "title": "Python runtime глубже middle+",
                            "description": "Объектная модель, descriptors, GIL, память и performance tradeoffs.",
                            "level": "middle+",
                            "objectives": [
                                "Объяснять runtime-механику без trivia",
                                "Связывать internals с backend production issues",
                            ],
                            "questions": [
                                {
                                    "difficulty": "middle+",
                                    "prompt": "Как descriptors влияют на attribute lookup и почему это важно для ORM?",
                                    "hint": "Покрой data/non-data descriptors, instance dict, class lookup и production-примеры.",
                                    "reference_answer": "Сильный ответ объясняет порядок поиска атрибутов, приоритет data descriptors, shadowing non-data descriptors, binding функций и связывает это с property, cached_property, ORM fields и validation hooks.",
                                },
                                {
                                    "difficulty": "senior",
                                    "prompt": "Как GIL влияет на дизайн Python backend-сервиса с CPU-bound и IO-bound задачами?",
                                    "hint": "Раздели threads, asyncio, multiprocessing, C extensions и измерения.",
                                    "reference_answer": "Нужно объяснить, что GIL ограничивает параллельное выполнение Python bytecode в потоках, но IO-bound код может выигрывать от concurrency. Для CPU-bound нужны процессы, extensions, workers или вынос нагрузки, а решение подтверждается profiling и нагрузочными тестами.",
                                },
                            ],
                            "mock_scenarios": [
                                "Разобрать incident с ростом latency из-за CPU-bound обработки в web workers."
                            ],
                        },
                        {
                            "slug": "llm-system-design",
                            "title": "System design для backend-сервисов",
                            "description": "Requirements, API, storage, scaling, consistency, observability и failure modes.",
                            "level": "senior",
                            "objectives": [
                                "Вести design discussion end-to-end",
                                "Называть tradeoffs и operational risks",
                            ],
                            "questions": [
                                {
                                    "difficulty": "senior",
                                    "prompt": "Спроектируй notification service с retries, preferences и analytics.",
                                    "hint": "Начни с requirements, затем API, data model, queue, idempotency, observability.",
                                    "reference_answer": "Сильный ответ фиксирует scope и SLA, предлагает API для создания уведомлений и preferences, durable storage, queue workers, idempotency keys, retries с backoff, DLQ, metrics/traces/logs и degrade strategy при сбоях провайдеров.",
                                },
                                {
                                    "difficulty": "senior",
                                    "prompt": "Как выбрать consistency model для распределенного backend-сервиса?",
                                    "hint": "Свяжи invariants, UX, latency, storage, conflicts и recovery.",
                                    "reference_answer": "Нужно начать с бизнес-инвариантов. Strong consistency нужна там, где нельзя нарушить деньги, квоты или ownership. Eventual consistency подходит для аналитики, feeds и derived state. Важно назвать latency/cost tradeoffs, conflict resolution, retries, idempotency и observability.",
                                },
                            ],
                            "mock_scenarios": [
                                "Спроектировать сервис сокращения ссылок с аналитикой и abuse protection."
                            ],
                        },
                    ]
                }
            )
        if "json" in lowered and "structured interview question" in lowered:
            return json.dumps(
                {
                    "difficulty": "middle+",
                    "prompt": "Объясни тему из заметки и свяжи ее с production Python backend-разработкой.",
                    "hint": "Покрой механизм, tradeoffs, failure modes и пример из реального сервиса.",
                    "reference_answer": "Сильный ответ объясняет концепцию, называет практические tradeoffs, приводит production-пример и говорит, как проверить поведение тестами или мониторингом.",
                }
            )
        if "regenerate the reference answer" in lowered:
            return (
                "Сильный ответ объясняет основной механизм, называет границы применимости и tradeoffs, "
                "приводит production-пример, отдельно отмечает failure modes и говорит, как проверить решение "
                "тестами, метриками или логами."
            )
        if "compact russian learning material" in lowered:
            return (
                "Короткое объяснение темы\n"
                "Тема важна для backend-разработчика, потому что влияет на надежность, latency и сопровождение сервиса.\n\n"
                "Что senior должен понимать глубже middle\n"
                "- Границы применимости подхода.\n"
                "- Tradeoffs между простотой, производительностью и надежностью.\n\n"
                "Production tradeoffs\n"
                "- Стоимость поддержки, observability, деградация и recovery важнее красивой абстракции.\n\n"
                "Типичные ошибки и failure modes\n"
                "- Нет явных timeout/retry границ.\n"
                "- Нет метрик и логов для проверки поведения.\n\n"
                "Мини-план практики на 15 минут\n"
                "1. Сформулируй механизм своими словами.\n"
                "2. Назови два tradeoff.\n"
                "3. Разбери один production incident."
            )
        if "system design mock interview scenario" in lowered and "return json only" in lowered:
            return json.dumps(
                {
                    "scenario": (
                        "Спроектируй сервис обработки фоновых задач для Python backend: прием задач через API, "
                        "очередь, workers, retries, idempotency, observability и безопасная деградация при сбоях зависимостей."
                    ),
                    "focus_areas": [
                        "requirements",
                        "API",
                        "data model",
                        "queue and workers",
                        "retries and idempotency",
                        "observability",
                        "failure modes",
                    ],
                },
                ensure_ascii=False,
            )
        if "system_design_final_feedback" in lowered:
            return (
                "Уровень: middle+.\n"
                "Сильные стороны:\n"
                "- Есть попытка двигаться по задаче.\n"
                "Пробелы:\n"
                "- Нужно явно пройти requirements, API, data model, scaling и failure modes.\n"
                "Что улучшить в следующей попытке:\n"
                "- Начни со scope и non-functional requirements, затем предложи API и storage.\n"
                "Senior checklist:\n"
                "- Называй tradeoffs, capacity assumptions, consistency model и observability."
            )
        if "system_design_mock_interview" in lowered:
            return (
                "Зафиксировал текущий ход решения. Пока не хватает явного scope и требований.\n"
                "Риск: без ограничения нагрузки и SLA сложно выбрать storage и scaling strategy.\n"
                "Следующий вопрос: какие functional и non-functional requirements ты зафиксируешь первыми?"
            )
        return (
            "Ollama недоступна или не успела ответить. Fallback-чеклист: сравни ответ с эталоном, "
            "добавь конкретные tradeoffs, назови failure modes и один production-пример."
        )


class ResilientLLMClient(LLMClient):
    def __init__(self, primary: LLMClient, fallback: LLMClient | None = None):
        self.primary = primary
        self.fallback = fallback or FallbackLLMClient()
        self.last_error: str | None = None

    def generate(self, prompt: str) -> str:
        try:
            self.last_error = None
            return self.primary.generate(prompt)
        except LLMUnavailable as exc:
            self.last_error = str(exc)
            return self.fallback.generate(prompt)
