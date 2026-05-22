from __future__ import annotations

import json

from interview_prep.domain.models import (
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_ARCHIVED,
    QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
    Question,
    QuestionCompetencyLink,
    Tag,
    Topic,
)
from interview_prep.domain.rules import normalize_difficulty
from interview_prep.infra.llm import LLMClient
from interview_prep.infra.repositories import SQLiteRepository


class QuestionService:
    def __init__(self, repository: SQLiteRepository, llm: LLMClient):
        self.repository = repository
        self.llm = llm

    def list_topics(self) -> list[Topic]:
        return self.repository.list_topics()

    def list_questions(
        self,
        topic_id: int | None = None,
        tag_slug: str | None = None,
        source_quality_status: str | None = None,
    ) -> list[Question]:
        tag_slug = tag_slug.strip() if tag_slug else None
        return self.repository.list_questions(
            topic_id,
            tag_slug=tag_slug,
            source_quality_status=source_quality_status,
        )

    def list_pending_review_questions(self, topic_id: int | None = None) -> list[Question]:
        return self.list_questions(
            topic_id=topic_id,
            source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
        )

    def list_question_tags(self, question_id: int) -> list[Tag]:
        return self.repository.list_question_tags(question_id)

    def list_question_competencies(self, question_id: int) -> list[QuestionCompetencyLink]:
        return self.repository.list_question_competencies(question_id)

    def accept_review_question(self, question_id: int) -> Question:
        return self._update_pending_review_question(question_id, QUESTION_SOURCE_QUALITY_ACCEPTED)

    def archive_review_question(self, question_id: int) -> Question:
        return self._update_pending_review_question(question_id, QUESTION_SOURCE_QUALITY_ARCHIVED)

    def _update_pending_review_question(self, question_id: int, status: str) -> Question:
        question = self.repository.get_question(question_id)
        if question is None:
            raise ValueError(f"Unknown question id: {question_id}")
        if question.source_quality_status != QUESTION_SOURCE_QUALITY_PENDING_REVIEW:
            raise ValueError(
                f"Question #{question_id} is not pending_review "
                f"(current: {question.source_quality_status})"
            )
        return self.repository.update_question_source_quality_status(question_id, status)

    def add_from_free_text(self, text: str, topic_id: int) -> Question:
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        prompt = f"""
Create one structured interview question for a middle+/senior Python backend developer.
Return JSON only with keys: difficulty, prompt, hint, reference_answer.
All values except difficulty must be written in Russian.
Difficulty must be one of: middle, middle+, senior.

Topic: {topic.title}
User note:
{text}
"""
        raw = self.llm.generate(prompt)
        payload = self._parse_question_json(raw, text)
        question = Question(
            id=None,
            topic_id=topic_id,
            difficulty=normalize_difficulty(payload["difficulty"]),
            prompt=payload["prompt"].strip(),
            hint=payload["hint"].strip(),
            reference_answer=payload["reference_answer"].strip(),
            source="user-llm",
        )
        return self.repository.add_question(question)

    def _parse_question_json(self, raw: str, original_text: str) -> dict[str, str]:
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            payload = json.loads(raw[start : end + 1] if start >= 0 and end >= start else raw)
        except json.JSONDecodeError:
            payload = {}
        return {
            "difficulty": str(payload.get("difficulty") or "middle+"),
            "prompt": str(payload.get("prompt") or original_text).strip(),
            "hint": str(payload.get("hint") or "Объясни механизм, tradeoffs и production implications.").strip(),
            "reference_answer": str(
                payload.get("reference_answer")
                or "Сильный ответ должен определить концепцию, объяснить tradeoffs, описать failure modes и привести backend-пример."
            ).strip(),
        }
