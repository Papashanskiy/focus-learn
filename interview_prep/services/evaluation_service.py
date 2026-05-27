from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from interview_prep.domain.models import (
    Answer,
    AnswerEvaluation,
    AnswerEvaluationScore,
    Question,
    RubricDimension,
)
from interview_prep.infra.llm import LLMClient, LLMUnavailable
from interview_prep.infra.repositories import SQLiteRepository


TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_+-]+")

STOP_WORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
    "а",
    "без",
    "бы",
    "в",
    "во",
    "для",
    "до",
    "и",
    "из",
    "или",
    "как",
    "к",
    "на",
    "не",
    "но",
    "о",
    "об",
    "от",
    "по",
    "при",
    "с",
    "со",
    "то",
    "что",
    "это",
}

DIMENSION_KEYWORDS = {
    "depth": (
        "механизм",
        "причин",
        "почему",
        "огранич",
        "детал",
        "lifecycle",
        "mechanism",
        "because",
        "constraints",
    ),
    "tradeoffs": (
        "tradeoff",
        "trade-off",
        "компромисс",
        "альтернатив",
        "стоим",
        "cost",
        "выбор",
        "плюс",
        "минус",
        "замедл",
        "ускор",
    ),
    "production-realism": (
        "production",
        "прод",
        "метрик",
        "лог",
        "trace",
        "observability",
        "monitor",
        "alert",
        "slo",
        "performance",
        "security",
        "миграц",
        "rollback",
        "deploy",
    ),
    "failure-modes": (
        "failure",
        "ошиб",
        "отказ",
        "timeout",
        "retry",
        "retries",
        "идемпот",
        "деград",
        "edge",
        "race",
        "lock",
        "cancellation",
        "backpressure",
        "risk",
        "риск",
    ),
    "communication": (
        "сначала",
        "затем",
        "потом",
        "во-первых",
        "допущ",
        "scope",
        "impact",
        "plan",
        "шаг",
    ),
}

DIMENSION_GAPS = {
    "correctness": "Сверь ответ с эталоном и явно закрой ключевые пункты вопроса.",
    "depth": "Добавь механизмы, причины, ограничения и senior-level детали.",
    "tradeoffs": "Назови альтернативы, стоимость решений и условия выбора.",
    "production-realism": "Свяжи ответ с production: observability, performance, security, данные, миграции.",
    "failure-modes": "Разбери edge cases, отказы, retries, идемпотентность и деградацию.",
    "communication": "Структурируй ответ: scope, план, приоритеты, вывод.",
    "evidence": "Добавь конкретные утверждения, на которые можно сослаться при оценке.",
}

DIMENSION_DRILLS = {
    "correctness": "Перепиши ответ как checklist по эталону без лишних допущений.",
    "depth": "Разбери один механизм глубже: как работает, где ломается, как проверить.",
    "tradeoffs": "Потренируй сравнение двух подходов с условиями выбора.",
    "production-realism": "Добавь production drill: метрики, rollout, rollback и operational risks.",
    "failure-modes": "Сделай failure-mode drill: timeout, retry, idempotency, degradation.",
    "communication": "Дай ответ в формате scope -> approach -> risks -> verification.",
    "evidence": "Подчеркни конкретные фразы ответа, которые доказывают каждый score.",
}


@dataclass(frozen=True)
class StructuredEvaluation:
    question_id: int | None
    summary: str
    scores: list[AnswerEvaluationScore]
    next_drills: list[str]
    source: str
    raw_payload_json: str | None = None


@dataclass(frozen=True)
class _AnswerProfile:
    candidate_text: str
    reference_text: str
    tokens: tuple[str, ...]
    reference_tokens: tuple[str, ...]
    overlap_ratio: float
    evidence_snippet: str

    @property
    def word_count(self) -> int:
        return len(self.tokens)

    @property
    def is_empty(self) -> bool:
        return not self.candidate_text.strip()

    @classmethod
    def from_texts(cls, candidate_text: str, reference_text: str) -> "_AnswerProfile":
        tokens = tuple(_important_tokens(candidate_text))
        reference_tokens = tuple(_important_tokens(reference_text))
        overlap = set(tokens) & set(reference_tokens)
        overlap_ratio = len(overlap) / len(set(reference_tokens)) if reference_tokens else 0.0
        return cls(
            candidate_text=candidate_text.strip(),
            reference_text=reference_text.strip(),
            tokens=tokens,
            reference_tokens=reference_tokens,
            overlap_ratio=overlap_ratio,
            evidence_snippet=_evidence_snippet(candidate_text),
        )

    def keyword_hits(self, slug: str) -> int:
        keywords = DIMENSION_KEYWORDS.get(slug, ())
        lowered = self.candidate_text.lower()
        return sum(1 for keyword in keywords if keyword in lowered)


class EvaluationService:
    def __init__(self, repository: SQLiteRepository, llm: LLMClient | None = None):
        self.repository = repository
        self.llm = llm

    def evaluate_answer(
        self,
        question: Question,
        user_answer: str,
        reference_answer: str,
    ) -> StructuredEvaluation:
        return self._evaluate_answer_heuristically(
            question,
            user_answer,
            reference_answer,
            source="heuristic",
        )

    def evaluate_answer_with_llm(
        self,
        question: Question,
        user_answer: str,
        reference_answer: str,
    ) -> StructuredEvaluation:
        if self.llm is None:
            raise ValueError("No LLM client configured for rubric evaluation.")
        dimensions = self.repository.list_rubric_dimensions()
        if not dimensions:
            raise ValueError("No rubric dimensions are configured.")

        prompt = build_rubric_evaluation_prompt(question, user_answer, reference_answer, dimensions)
        try:
            raw_response = self.llm.generate(prompt)
            return parse_rubric_evaluation_response(raw_response, question, dimensions)
        except (LLMUnavailable, ValueError):
            return self._evaluate_answer_heuristically(
                question,
                user_answer,
                reference_answer,
                source="fallback-heuristic",
            )

    def evaluate_and_store_answer(
        self,
        answer: Answer,
        question: Question,
        *,
        use_llm: bool = True,
    ) -> AnswerEvaluation:
        if answer.id is None:
            raise ValueError("Answer must be persisted before rubric evaluation.")
        structured = (
            self.evaluate_answer_with_llm(question, answer.user_answer, question.reference_answer)
            if use_llm and self.llm is not None
            else self.evaluate_answer(question, answer.user_answer, question.reference_answer)
        )
        evaluation = AnswerEvaluation(
            id=None,
            answer_id=answer.id,
            session_id=answer.session_id,
            question_id=answer.question_id,
            summary=structured.summary,
            scores=structured.scores,
            next_drills=structured.next_drills,
            source=structured.source,
            created_at=datetime.now(),
            raw_payload_json=structured.raw_payload_json,
        )
        return self.repository.add_answer_evaluation(evaluation)

    def list_answer_evaluations(self, answer_id: int) -> list[AnswerEvaluation]:
        return self.repository.list_answer_evaluations_for_answer(answer_id)

    def override_score(
        self,
        evaluation_id: int,
        *,
        dimension_slug: str,
        score: int,
        reason: str | None = None,
        overridden_at: datetime | None = None,
    ) -> AnswerEvaluation:
        dimension = dimension_slug.strip()
        if not dimension:
            raise ValueError("Rubric dimension slug is required.")
        if score < 1 or score > 5:
            raise ValueError("Manual rubric override score must be between 1 and 5.")
        evaluation = self.repository.override_answer_evaluation_score(
            evaluation_id,
            dimension,
            score,
            reason=reason,
            overridden_at=overridden_at,
        )
        if evaluation is None:
            raise ValueError(
                f"Rubric score not found for evaluation #{evaluation_id} and dimension '{dimension}'."
            )
        return evaluation

    def _evaluate_answer_heuristically(
        self,
        question: Question,
        user_answer: str,
        reference_answer: str,
        *,
        source: str,
    ) -> StructuredEvaluation:
        dimensions = self.repository.list_rubric_dimensions()
        if not dimensions:
            raise ValueError("No rubric dimensions are configured.")

        profile = _AnswerProfile.from_texts(user_answer, reference_answer.strip() or question.reference_answer)
        scores = [self._score_dimension(dimension, profile) for dimension in dimensions]
        next_drills = self._next_drills(scores)
        return StructuredEvaluation(
            question_id=question.id,
            summary=self._summary(scores, profile),
            scores=scores,
            next_drills=next_drills,
            source=source,
        )

    def _score_dimension(
        self,
        dimension: RubricDimension,
        profile: _AnswerProfile,
    ) -> AnswerEvaluationScore:
        score = self._dimension_score(dimension.slug, profile)
        evidence = self._evidence_for_score(score, profile)
        gap = "Нет явного gap для этого измерения." if score >= 4 else DIMENSION_GAPS.get(
            dimension.slug,
            "Добавь больше конкретики по этому измерению.",
        )
        next_drill = None if score >= 4 else DIMENSION_DRILLS.get(
            dimension.slug,
            "Повтори это измерение на следующем ответе.",
        )
        return AnswerEvaluationScore(
            dimension=dimension,
            score=score,
            evidence=evidence,
            gaps=gap,
            next_drill=next_drill,
        )

    def _dimension_score(self, slug: str, profile: _AnswerProfile) -> int:
        if profile.is_empty or profile.word_count <= 2:
            return 1
        if profile.word_count <= 5:
            return 2

        if slug == "correctness":
            return _score_from_ratio(profile.overlap_ratio)
        if slug == "evidence":
            if profile.word_count >= 35 and profile.overlap_ratio >= 0.12:
                return 4
            if profile.word_count >= 15:
                return 3
            return 2
        if slug == "communication":
            structure_bonus = 1 if _has_structure(profile.candidate_text) else 0
            return _clamp_score(_length_score(profile.word_count) + structure_bonus)

        hits = profile.keyword_hits(slug)
        if slug == "depth":
            return _clamp_score(min(3, _length_score(profile.word_count)) + min(2, hits))
        if slug in {"tradeoffs", "production-realism", "failure-modes"}:
            return _clamp_score(2 + min(3, hits))

        return _clamp_score(max(_score_from_ratio(profile.overlap_ratio), _length_score(profile.word_count)))

    def _evidence_for_score(self, score: int, profile: _AnswerProfile) -> str:
        if score <= 1 or not profile.evidence_snippet:
            return "В ответе кандидата нет достаточного наблюдаемого evidence для этого измерения."
        return f'Наблюдаемое evidence из ответа кандидата: "{profile.evidence_snippet}"'

    def _summary(self, scores: list[AnswerEvaluationScore], profile: _AnswerProfile) -> str:
        average_score = sum(score.score for score in scores) / len(scores)
        if profile.is_empty:
            return "Ответ пустой; rubric evaluation показывает отсутствие проверяемого evidence."
        if average_score >= 4:
            return "Ответ хорошо закрывает rubric dimensions и содержит проверяемое evidence."
        if average_score >= 3:
            return "Ответ частично закрывает вопрос; основные gaps видны в низких rubric dimensions."
        return "Ответ пока слабый: мало конкретики и проверяемого evidence по rubric dimensions."

    def _next_drills(self, scores: list[AnswerEvaluationScore]) -> list[str]:
        drills: list[str] = []
        for score in sorted(scores, key=lambda item: (item.score, item.dimension.order_index)):
            if score.score >= 4 or not score.next_drill:
                continue
            if score.next_drill not in drills:
                drills.append(score.next_drill)
            if len(drills) == 4:
                break
        return drills


def _important_tokens(text: str) -> list[str]:
    tokens = []
    for token in TOKEN_RE.findall(text.lower()):
        if len(token) < 3 or token in STOP_WORDS:
            continue
        tokens.append(token)
    return tokens


def _evidence_snippet(text: str, limit: int = 160) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3].rstrip() + "..."


def _score_from_ratio(value: float) -> int:
    if value >= 0.45:
        return 5
    if value >= 0.30:
        return 4
    if value >= 0.18:
        return 3
    if value >= 0.08:
        return 2
    return 1


def _length_score(word_count: int) -> int:
    if word_count >= 90:
        return 5
    if word_count >= 45:
        return 4
    if word_count >= 18:
        return 3
    if word_count >= 6:
        return 2
    return 1


def _has_structure(text: str) -> bool:
    return (
        "\n" in text
        or ";" in text
        or ":" in text
        or bool(re.search(r"\b(сначала|затем|потом|first|then)\b", text.lower()))
    )


def _clamp_score(value: int) -> int:
    return max(1, min(5, value))


def build_rubric_evaluation_prompt(
    question: Question,
    user_answer: str,
    reference_answer: str,
    dimensions: list[RubricDimension],
) -> str:
    dimension_payload = [
        {
            "slug": dimension.slug,
            "title": dimension.title,
            "description": dimension.description,
            "order_index": dimension.order_index,
        }
        for dimension in dimensions
    ]
    reference_text = reference_answer.strip() or question.reference_answer
    return f"""
<rubric_answer_evaluation_json>
Ты senior Python backend interviewer. Оцени ответ кандидата по rubric dimensions.
Верни строго JSON object без Markdown fences, комментариев и текста вокруг JSON.

Критически важные правила:
- Оценивай только текст внутри <candidate_answer>.
- <reference_answer> используй только как чеклист gaps; не засчитывай кандидату пункты, которых нет в <candidate_answer>.
- Поле evidence должно ссылаться только на наблюдаемый текст кандидата. Если evidence нет, напиши: "В ответе кандидата нет достаточного наблюдаемого evidence для этого измерения."
- Все строки ответа должны быть на русском языке.
- Для каждого dimension из <rubric_dimensions_json> верни ровно один score.
- score всегда целое число от 1 до 5.

JSON schema:
{{
  "summary": "краткий общий вывод по ответу",
  "scores": [
    {{
      "dimension_slug": "slug из rubric_dimensions_json",
      "score": 1,
      "evidence": "evidence только из candidate_answer",
      "gaps": "что не хватает по этому dimension",
      "next_drill": "короткий следующий drill или null"
    }}
  ],
  "next_drills": ["2-4 конкретных drill на основе самых слабых dimensions"]
}}

<rubric_dimensions_json>
{json.dumps(dimension_payload, ensure_ascii=False, indent=2)}
</rubric_dimensions_json>

<question>
{question.prompt}
</question>

<candidate_answer>
{user_answer}
</candidate_answer>

<reference_answer>
{reference_text}
</reference_answer>
</rubric_answer_evaluation_json>
""".strip()


def parse_rubric_evaluation_response(
    raw_response: str,
    question: Question,
    dimensions: list[RubricDimension],
) -> StructuredEvaluation:
    payload = _load_json_object(raw_response)
    summary = _required_text(payload, "summary")
    raw_scores = payload.get("scores")
    if not isinstance(raw_scores, list):
        raise ValueError("Rubric evaluation JSON must contain a scores list.")

    dimensions_by_slug = {dimension.slug: dimension for dimension in dimensions}
    scores_by_slug: dict[str, AnswerEvaluationScore] = {}
    for raw_score in raw_scores:
        if not isinstance(raw_score, dict):
            raise ValueError("Rubric evaluation score entries must be objects.")
        slug = _required_text(raw_score, "dimension_slug")
        if slug not in dimensions_by_slug:
            raise ValueError(f"Unknown rubric dimension slug: {slug}")
        score_value = _required_score(raw_score.get("score"), slug)
        next_drill = raw_score.get("next_drill")
        if next_drill is not None and not isinstance(next_drill, str):
            raise ValueError(f"Rubric next_drill for {slug} must be a string or null.")
        scores_by_slug[slug] = AnswerEvaluationScore(
            dimension=dimensions_by_slug[slug],
            score=score_value,
            evidence=_required_text(raw_score, "evidence"),
            gaps=_required_text(raw_score, "gaps"),
            next_drill=next_drill.strip() if isinstance(next_drill, str) and next_drill.strip() else None,
        )

    missing_slugs = [dimension.slug for dimension in dimensions if dimension.slug not in scores_by_slug]
    if missing_slugs:
        raise ValueError(f"Rubric evaluation JSON missing scores for: {', '.join(missing_slugs)}")

    next_drills = _text_list(payload.get("next_drills"))
    return StructuredEvaluation(
        question_id=question.id,
        summary=summary,
        scores=[scores_by_slug[dimension.slug] for dimension in dimensions],
        next_drills=next_drills,
        source="llm-json",
        raw_payload_json=raw_response.strip(),
    )


def _load_json_object(raw_response: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise ValueError("Rubric evaluation response is not valid JSON.") from exc
    if not isinstance(payload, dict):
        raise ValueError("Rubric evaluation response must be a JSON object.")
    return payload


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Rubric evaluation JSON must contain non-empty string field: {key}")
    return value.strip()


def _required_score(value: Any, slug: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 5:
        raise ValueError(f"Rubric score for {slug} must be an integer from 1 to 5.")
    return value


def _text_list(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("Rubric evaluation next_drills must be a list.")
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]
