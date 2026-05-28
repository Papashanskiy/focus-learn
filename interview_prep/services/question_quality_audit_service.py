from __future__ import annotations

from dataclasses import dataclass

from interview_prep.domain.models import (
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_ARCHIVED,
    Question,
)
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.content_generation_service import question_prompts_are_similar
from interview_prep.services.question_quality_rules import generic_prompt_detail


QUESTION_AUDIT_KIND_DUPLICATE = "duplicate"
QUESTION_AUDIT_KIND_GENERIC = "generic"
QUESTION_AUDIT_KIND_TOO_LONG = "too-long"
DEFAULT_MAX_QUESTION_PROMPT_CHARS = 280
GENERATED_QUESTION_SOURCES = frozenset({"background-llm", "llm-seed"})

@dataclass(frozen=True)
class QuestionQualityFinding:
    kind: str
    question: Question
    topic_title: str
    detail: str
    duplicate_of_id: int | None = None


@dataclass(frozen=True)
class QuestionQualityCleanupResult:
    archived_questions: tuple[Question, ...]


class QuestionQualityAuditService:
    def __init__(self, repository: SQLiteRepository):
        self.repository = repository

    def audit(
        self,
        topic_id: int | None = None,
        *,
        max_prompt_chars: int = DEFAULT_MAX_QUESTION_PROMPT_CHARS,
    ) -> list[QuestionQualityFinding]:
        if max_prompt_chars < 1:
            raise ValueError("max_prompt_chars must be positive")

        topics = {topic.id: topic.title for topic in self.repository.list_topics()}
        questions = self.repository.list_questions(topic_id)
        findings: list[QuestionQualityFinding] = []
        seen_by_topic: dict[int, list[Question]] = {}

        for question in questions:
            topic_title = topics.get(question.topic_id, f"topic #{question.topic_id}")
            generic_detail = generic_prompt_detail(question.prompt)
            if generic_detail is not None:
                findings.append(
                    QuestionQualityFinding(
                        kind=QUESTION_AUDIT_KIND_GENERIC,
                        question=question,
                        topic_title=topic_title,
                        detail=generic_detail,
                    )
                )
            if len(question.prompt) > max_prompt_chars:
                findings.append(
                    QuestionQualityFinding(
                        kind=QUESTION_AUDIT_KIND_TOO_LONG,
                        question=question,
                        topic_title=topic_title,
                        detail=f"prompt length {len(question.prompt)} exceeds {max_prompt_chars} chars",
                    )
                )

            duplicate_of = first_similar_question(seen_by_topic.get(question.topic_id, []), question)
            if duplicate_of is not None:
                findings.append(
                    QuestionQualityFinding(
                        kind=QUESTION_AUDIT_KIND_DUPLICATE,
                        question=question,
                        topic_title=topic_title,
                        detail=f"similar to question #{duplicate_of.id}",
                        duplicate_of_id=duplicate_of.id,
                    )
                )
            seen_by_topic.setdefault(question.topic_id, []).append(question)

        return sorted(
            findings,
            key=lambda item: (
                item.question.topic_id,
                item.question.id or 0,
                (QUESTION_AUDIT_KIND_GENERIC, QUESTION_AUDIT_KIND_DUPLICATE, QUESTION_AUDIT_KIND_TOO_LONG).index(
                    item.kind
                ),
            ),
        )

    def archive_accepted_generic_generated_questions(
        self,
        topic_id: int | None = None,
    ) -> QuestionQualityCleanupResult:
        archived: list[Question] = []
        seen_question_ids: set[int] = set()
        for finding in self.audit(topic_id=topic_id):
            question = finding.question
            question_id = question.id
            if question_id is None or question_id in seen_question_ids:
                continue
            if not is_accepted_generic_generated_finding(finding):
                continue
            archived.append(
                self.repository.update_question_source_quality_status(
                    question_id,
                    QUESTION_SOURCE_QUALITY_ARCHIVED,
                )
            )
            seen_question_ids.add(question_id)
        return QuestionQualityCleanupResult(archived_questions=tuple(archived))


def is_accepted_generic_generated_finding(finding: QuestionQualityFinding) -> bool:
    question = finding.question
    return (
        finding.kind == QUESTION_AUDIT_KIND_GENERIC
        and question.source_quality_status == QUESTION_SOURCE_QUALITY_ACCEPTED
        and question.source in GENERATED_QUESTION_SOURCES
    )


def first_similar_question(existing: list[Question], candidate: Question) -> Question | None:
    for question in existing:
        if question_prompts_are_similar(candidate.prompt, question.prompt):
            return question
    return None
