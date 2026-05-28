from __future__ import annotations

import json
from typing import Any
from dataclasses import dataclass
from datetime import datetime

from interview_prep.domain.models import (
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_ARCHIVED,
    QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
    Question,
    QuestionAutoCurationAudit,
)
from interview_prep.infra.llm import LLMClient, LLMUnavailable
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.question_quality_audit_service import (
    DEFAULT_MAX_QUESTION_PROMPT_CHARS,
    first_similar_question,
    generic_prompt_detail,
)


AUTO_CURATION_DECISION_AUTO_ACCEPTED = "auto_accepted"
AUTO_CURATION_DECISION_AUTO_ARCHIVED = "auto_archived"
AUTO_CURATION_DECISION_QUARANTINED = "quarantined"

AUTO_CURATION_FLAG_DUPLICATE = "duplicate"
AUTO_CURATION_FLAG_GENERIC = "generic"
AUTO_CURATION_FLAG_INCOMPLETE_SOURCE_METADATA = "incomplete_source_metadata"
AUTO_CURATION_FLAG_LLM_CURATOR = "llm_curator"
AUTO_CURATION_FLAG_LLM_LOW_CONFIDENCE = "llm_low_confidence"
AUTO_CURATION_FLAG_LLM_PARSE_FALLBACK = "llm_parse_fallback"
AUTO_CURATION_FLAG_SHORT_PROMPT = "short_prompt"
AUTO_CURATION_FLAG_TOO_LONG = "too_long"

SOURCE_BACKED_QUESTION_SOURCE = "source-backed"
MIN_HIGH_CONFIDENCE_PROMPT_CHARS = 80
LLM_AUTO_ACCEPT_MIN_CONFIDENCE = 0.85
LLM_AUTO_ACCEPT_MIN_SCORE = 4
LLM_AUTO_ARCHIVE_MIN_CONFIDENCE = 0.75
AUTO_CURATION_AUDIT_VERSION = "source-backed-auto-curation-v1"
DETERMINISTIC_CURATOR_MODEL = "deterministic-gates"


@dataclass(frozen=True)
class QuestionAutoCurationDecision:
    question: Question
    topic_title: str
    decision: str
    confidence: float
    rationale: str
    quality_flags: tuple[str, ...] = ()
    duplicate_of_id: int | None = None
    curator_score: int | None = None
    curator_source_evidence: str | None = None


@dataclass(frozen=True)
class QuestionAutoCurationPreviewResult:
    decisions: tuple[QuestionAutoCurationDecision, ...]
    dry_run: bool = True
    applied_count: int = 0
    accepted_count: int = 0
    archived_count: int = 0
    quarantined_count: int = 0


@dataclass(frozen=True)
class QuestionAutoCurationUndoResult:
    audit: QuestionAutoCurationAudit
    question_before: Question
    question_after: Question
    dry_run: bool = False
    changed: bool = False


class QuestionAutoCurationService:
    def __init__(self, repository: SQLiteRepository, llm: LLMClient | None = None):
        self.repository = repository
        self.llm = llm

    def preview_pending_source_backed_candidates(
        self,
        topic_id: int | None = None,
        *,
        max_prompt_chars: int = DEFAULT_MAX_QUESTION_PROMPT_CHARS,
        use_llm_curator: bool = False,
    ) -> QuestionAutoCurationPreviewResult:
        if max_prompt_chars < 1:
            raise ValueError("max_prompt_chars must be positive")

        topics = {topic.id: topic.title for topic in self.repository.list_topics()}
        pending = [
            question
            for question in self.repository.list_questions(
                topic_id=topic_id,
                source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
            )
            if question.source == SOURCE_BACKED_QUESTION_SOURCE
        ]
        accepted_by_topic: dict[int, list[Question]] = {}
        seen_candidates_by_topic: dict[int, list[Question]] = {}
        decisions: list[QuestionAutoCurationDecision] = []

        for question in pending:
            accepted = accepted_by_topic.setdefault(
                question.topic_id,
                self.repository.list_questions(
                    topic_id=question.topic_id,
                    source_quality_status=QUESTION_SOURCE_QUALITY_ACCEPTED,
                ),
            )
            duplicate_pool = accepted + seen_candidates_by_topic.get(question.topic_id, [])
            decision = classify_source_backed_candidate(
                question,
                topics.get(question.topic_id, f"topic #{question.topic_id}"),
                duplicate_pool,
                max_prompt_chars=max_prompt_chars,
            )
            if use_llm_curator and self.llm is not None and decision.decision == AUTO_CURATION_DECISION_QUARANTINED:
                decision = curate_quarantined_candidate_with_llm(decision, self.llm)
            decisions.append(decision)
            seen_candidates_by_topic.setdefault(question.topic_id, []).append(question)

        return QuestionAutoCurationPreviewResult(decisions=tuple(decisions))

    def apply_pending_source_backed_candidates(
        self,
        topic_id: int | None = None,
        *,
        max_prompt_chars: int = DEFAULT_MAX_QUESTION_PROMPT_CHARS,
        use_llm_curator: bool = False,
    ) -> QuestionAutoCurationPreviewResult:
        result = self.preview_pending_source_backed_candidates(
            topic_id=topic_id,
            max_prompt_chars=max_prompt_chars,
            use_llm_curator=use_llm_curator,
        )
        accepted_count = 0
        archived_count = 0
        quarantined_count = 0

        for decision in result.decisions:
            if decision.question.id is None:
                raise ValueError("Cannot apply auto-curation to an unsaved question")
            resulting_status = QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW
            if decision.decision == AUTO_CURATION_DECISION_AUTO_ACCEPTED:
                resulting_status = QUESTION_SOURCE_QUALITY_ACCEPTED
                self.repository.update_question_source_quality_status(
                    decision.question.id,
                    resulting_status,
                )
                accepted_count += 1
            elif decision.decision == AUTO_CURATION_DECISION_AUTO_ARCHIVED:
                resulting_status = QUESTION_SOURCE_QUALITY_ARCHIVED
                self.repository.update_question_source_quality_status(
                    decision.question.id,
                    resulting_status,
                )
                archived_count += 1
            elif decision.decision == AUTO_CURATION_DECISION_QUARANTINED:
                quarantined_count += 1
            else:
                raise ValueError(f"Unknown auto-curation decision: {decision.decision}")
            self.repository.add_question_auto_curation_audit(
                build_auto_curation_audit_entry(
                    decision,
                    previous_status=decision.question.source_quality_status,
                    resulting_status=resulting_status,
                    curator_model=curator_model_label(decision, self.llm),
                )
            )

        return QuestionAutoCurationPreviewResult(
            decisions=result.decisions,
            dry_run=False,
            applied_count=accepted_count + archived_count,
            accepted_count=accepted_count,
            archived_count=archived_count,
            quarantined_count=quarantined_count,
        )

    def undo_latest_decision(
        self,
        question_id: int | None = None,
        *,
        topic_id: int | None = None,
        resulting_status: str | None = None,
        dry_run: bool = False,
    ) -> QuestionAutoCurationUndoResult:
        if question_id is not None and question_id < 1:
            raise ValueError("question_id must be positive")
        if topic_id is not None and topic_id < 1:
            raise ValueError("topic_id must be positive")

        audits = self.repository.list_question_auto_curation_audits(
            question_id=question_id,
            topic_id=topic_id,
            resulting_status=resulting_status,
            limit=1,
        )
        if not audits:
            raise ValueError("No auto-curation audit decisions found to undo.")
        audit = audits[0]
        question = self.repository.get_question(audit.question_id)
        if question is None:
            raise ValueError(f"Cannot undo audit #{audit.id or '-'}: question #{audit.question_id} is missing.")
        if question.source_quality_status != audit.resulting_status:
            raise ValueError(
                f"Cannot undo audit #{audit.id or '-'} for question #{audit.question_id}: "
                f"current status is {question.source_quality_status}, expected {audit.resulting_status}."
            )

        changed = question.source_quality_status != audit.previous_status
        if dry_run:
            return QuestionAutoCurationUndoResult(
                audit=audit,
                question_before=question,
                question_after=question,
                dry_run=True,
                changed=changed,
            )

        updated = self.repository.update_question_source_quality_status(
            audit.question_id,
            audit.previous_status,
        )
        return QuestionAutoCurationUndoResult(
            audit=audit,
            question_before=question,
            question_after=updated,
            changed=changed,
        )


def build_auto_curation_audit_entry(
    decision: QuestionAutoCurationDecision,
    *,
    previous_status: str,
    resulting_status: str,
    curator_model: str,
) -> QuestionAutoCurationAudit:
    question = decision.question
    if question.id is None:
        raise ValueError("Cannot audit auto-curation for an unsaved question")
    return QuestionAutoCurationAudit(
        id=None,
        question_id=question.id,
        previous_status=previous_status,
        decision=decision.decision,
        resulting_status=resulting_status,
        confidence=decision.confidence,
        rationale=decision.rationale,
        quality_flags=list(decision.quality_flags),
        duplicate_of_id=decision.duplicate_of_id,
        curator_score=decision.curator_score,
        curator_source_evidence=decision.curator_source_evidence,
        curator_model=curator_model,
        curator_version=AUTO_CURATION_AUDIT_VERSION,
        source_url=question.source_url,
        source_retrieved_at=question.source_retrieved_at,
        source_category_hints=list(question.source_category_hints),
        source_frequency_hint=question.source_frequency_hint,
        created_at=datetime.now(),
    )


def curator_model_label(decision: QuestionAutoCurationDecision, llm: LLMClient | None) -> str:
    if AUTO_CURATION_FLAG_LLM_CURATOR not in decision.quality_flags:
        return DETERMINISTIC_CURATOR_MODEL
    if llm is None:
        return "llm-unavailable"
    candidate = llm
    if getattr(llm, "last_error", None) and hasattr(llm, "fallback"):
        candidate = getattr(llm, "fallback")
    elif hasattr(llm, "primary"):
        candidate = getattr(llm, "primary")
    model = getattr(candidate, "model", None)
    class_name = type(candidate).__name__
    return f"{class_name}:{model}" if model else class_name


def classify_source_backed_candidate(
    question: Question,
    topic_title: str,
    duplicate_pool: list[Question],
    *,
    max_prompt_chars: int = DEFAULT_MAX_QUESTION_PROMPT_CHARS,
) -> QuestionAutoCurationDecision:
    generic_detail = generic_prompt_detail(question.prompt)
    if generic_detail is not None:
        return QuestionAutoCurationDecision(
            question=question,
            topic_title=topic_title,
            decision=AUTO_CURATION_DECISION_AUTO_ARCHIVED,
            confidence=0.96,
            rationale=f"Deterministic generic wording gate: {generic_detail}.",
            quality_flags=(AUTO_CURATION_FLAG_GENERIC,),
        )

    duplicate_of = first_similar_question(duplicate_pool, question)
    if duplicate_of is not None:
        return QuestionAutoCurationDecision(
            question=question,
            topic_title=topic_title,
            decision=AUTO_CURATION_DECISION_AUTO_ARCHIVED,
            confidence=0.95,
            rationale=f"Deterministic duplicate gate: similar to question #{duplicate_of.id}.",
            quality_flags=(AUTO_CURATION_FLAG_DUPLICATE,),
            duplicate_of_id=duplicate_of.id,
        )

    if len(question.prompt) > max_prompt_chars:
        return QuestionAutoCurationDecision(
            question=question,
            topic_title=topic_title,
            decision=AUTO_CURATION_DECISION_QUARANTINED,
            confidence=0.70,
            rationale=f"Prompt length {len(question.prompt)} exceeds {max_prompt_chars} chars.",
            quality_flags=(AUTO_CURATION_FLAG_TOO_LONG,),
        )

    if not has_complete_source_metadata(question):
        return QuestionAutoCurationDecision(
            question=question,
            topic_title=topic_title,
            decision=AUTO_CURATION_DECISION_QUARANTINED,
            confidence=0.72,
            rationale="Source evidence is incomplete, so the candidate needs human or LLM curator review.",
            quality_flags=(AUTO_CURATION_FLAG_INCOMPLETE_SOURCE_METADATA,),
        )

    if len(question.prompt.strip()) < MIN_HIGH_CONFIDENCE_PROMPT_CHARS:
        return QuestionAutoCurationDecision(
            question=question,
            topic_title=topic_title,
            decision=AUTO_CURATION_DECISION_QUARANTINED,
            confidence=0.68,
            rationale="Prompt is too short to prove a concrete interview scenario deterministically.",
            quality_flags=(AUTO_CURATION_FLAG_SHORT_PROMPT,),
        )

    return QuestionAutoCurationDecision(
        question=question,
        topic_title=topic_title,
        decision=AUTO_CURATION_DECISION_AUTO_ACCEPTED,
        confidence=0.90,
        rationale=(
            "Source-backed candidate has source URL, retrieved timestamp, category/frequency metadata, "
            "a concrete prompt, and no deterministic generic/duplicate/length flags."
        ),
    )


def has_complete_source_metadata(question: Question) -> bool:
    return bool(
        question.source_url
        and question.source_retrieved_at
        and question.source_category_hints
        and question.source_frequency_hint
    )


def curate_quarantined_candidate_with_llm(
    deterministic_decision: QuestionAutoCurationDecision,
    llm: LLMClient,
) -> QuestionAutoCurationDecision:
    prompt = build_llm_curator_prompt(deterministic_decision)
    try:
        raw_response = llm.generate(prompt)
        proposed = parse_llm_curator_response(raw_response, deterministic_decision)
    except (LLMUnavailable, ValueError) as exc:
        return QuestionAutoCurationDecision(
            question=deterministic_decision.question,
            topic_title=deterministic_decision.topic_title,
            decision=AUTO_CURATION_DECISION_QUARANTINED,
            confidence=min(deterministic_decision.confidence, 0.55),
            rationale=f"LLM curator fallback kept quarantine: {exc}",
            quality_flags=dedupe_flags(
                deterministic_decision.quality_flags
                + (AUTO_CURATION_FLAG_LLM_CURATOR, AUTO_CURATION_FLAG_LLM_PARSE_FALLBACK)
            ),
            duplicate_of_id=deterministic_decision.duplicate_of_id,
        )
    return enforce_llm_curator_safety(deterministic_decision, proposed)


def build_llm_curator_prompt(deterministic_decision: QuestionAutoCurationDecision) -> str:
    question = deterministic_decision.question
    retrieved_at = question.source_retrieved_at.isoformat(timespec="seconds") if question.source_retrieved_at else ""
    payload = {
        "question_id": question.id,
        "topic": deterministic_decision.topic_title,
        "difficulty": question.difficulty,
        "prompt": question.prompt,
        "hint": question.hint,
        "reference_answer": question.reference_answer,
        "source_url": question.source_url or "",
        "source_retrieved_at": retrieved_at,
        "source_category_hints": list(question.source_category_hints),
        "source_frequency_hint": question.source_frequency_hint or "",
        "deterministic_flags": list(deterministic_decision.quality_flags),
        "deterministic_rationale": deterministic_decision.rationale,
    }
    return f"""
<source_backed_question_curator_json>
You are a strict curator for source-backed senior Python/backend interview questions.
Return JSON only, with no markdown and no commentary.

Allowed decisions:
- "auto_accepted": only for concrete, source-backed interview questions with enough evidence, explicit scenario/constraints, and expected senior mechanisms.
- "auto_archived": for generic, duplicated, unusable, misleading, or non-interview questions.
- "quarantined": for ambiguous cases, missing source evidence, low confidence, or prompts that need human audit.

Required JSON schema:
{{
  "decision": "auto_accepted|auto_archived|quarantined",
  "confidence": 0.0,
  "score": 1,
  "rationale": "one concise sentence",
  "source_evidence": "which supplied source metadata supports the decision",
  "quality_flags": ["short lowercase flags"]
}}

Safety rules:
- Do not accept a question only because the reference answer is strong.
- If source evidence is missing or weak, prefer "quarantined".
- If confidence is below 0.85 for acceptance, choose "quarantined".
- If the prompt is generic and lacks concrete mechanisms, choose "auto_archived" or "quarantined".

<candidate_json>
{json.dumps(payload, ensure_ascii=False, indent=2)}
</candidate_json>
</source_backed_question_curator_json>
""".strip()


def parse_llm_curator_response(
    raw_response: str,
    deterministic_decision: QuestionAutoCurationDecision,
) -> QuestionAutoCurationDecision:
    payload = json.loads(raw_response.strip())
    if not isinstance(payload, dict):
        raise ValueError("LLM curator response must be a JSON object.")

    decision = _required_curator_decision(payload.get("decision"))
    confidence = _required_confidence(payload.get("confidence"))
    score = _required_score(payload.get("score"))
    rationale = _required_text(payload, "rationale")
    source_evidence = _required_text(payload, "source_evidence")
    llm_flags = _curator_quality_flags(payload.get("quality_flags"))
    return QuestionAutoCurationDecision(
        question=deterministic_decision.question,
        topic_title=deterministic_decision.topic_title,
        decision=decision,
        confidence=confidence,
        rationale=f"LLM curator score {score}/5: {rationale}",
        quality_flags=dedupe_flags(
            deterministic_decision.quality_flags + (AUTO_CURATION_FLAG_LLM_CURATOR,) + llm_flags
        ),
        duplicate_of_id=deterministic_decision.duplicate_of_id,
        curator_score=score,
        curator_source_evidence=source_evidence,
    )


def enforce_llm_curator_safety(
    deterministic_decision: QuestionAutoCurationDecision,
    proposed_decision: QuestionAutoCurationDecision,
) -> QuestionAutoCurationDecision:
    if proposed_decision.decision == AUTO_CURATION_DECISION_AUTO_ACCEPTED:
        if (
            proposed_decision.confidence < LLM_AUTO_ACCEPT_MIN_CONFIDENCE
            or (proposed_decision.curator_score or 0) < LLM_AUTO_ACCEPT_MIN_SCORE
            or not has_complete_source_metadata(proposed_decision.question)
        ):
            return QuestionAutoCurationDecision(
                question=proposed_decision.question,
                topic_title=proposed_decision.topic_title,
                decision=AUTO_CURATION_DECISION_QUARANTINED,
                confidence=min(proposed_decision.confidence, 0.74),
                rationale=(
                    f"{proposed_decision.rationale} Safety fallback kept quarantine because acceptance "
                    "requires complete source metadata, score >= 4, and confidence >= 0.85."
                ),
                quality_flags=dedupe_flags(
                    proposed_decision.quality_flags + (AUTO_CURATION_FLAG_LLM_LOW_CONFIDENCE,)
                ),
                duplicate_of_id=proposed_decision.duplicate_of_id,
                curator_score=proposed_decision.curator_score,
                curator_source_evidence=proposed_decision.curator_source_evidence,
            )
    if (
        proposed_decision.decision == AUTO_CURATION_DECISION_AUTO_ARCHIVED
        and proposed_decision.confidence < LLM_AUTO_ARCHIVE_MIN_CONFIDENCE
    ):
        return QuestionAutoCurationDecision(
            question=proposed_decision.question,
            topic_title=proposed_decision.topic_title,
            decision=AUTO_CURATION_DECISION_QUARANTINED,
            confidence=proposed_decision.confidence,
            rationale=(
                f"{proposed_decision.rationale} Safety fallback kept quarantine because archive "
                "confidence is below 0.75."
            ),
            quality_flags=dedupe_flags(proposed_decision.quality_flags + (AUTO_CURATION_FLAG_LLM_LOW_CONFIDENCE,)),
            duplicate_of_id=proposed_decision.duplicate_of_id,
            curator_score=proposed_decision.curator_score,
            curator_source_evidence=proposed_decision.curator_source_evidence,
        )
    return proposed_decision


def dedupe_flags(flags: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for flag in flags:
        normalized = flag.strip().lower().replace(" ", "_")
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return tuple(result)


def _required_curator_decision(value: Any) -> str:
    if value not in {
        AUTO_CURATION_DECISION_AUTO_ACCEPTED,
        AUTO_CURATION_DECISION_AUTO_ARCHIVED,
        AUTO_CURATION_DECISION_QUARANTINED,
    }:
        raise ValueError("LLM curator decision must be auto_accepted, auto_archived, or quarantined.")
    return value


def _required_confidence(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("LLM curator confidence must be a number from 0.0 to 1.0.")
    confidence = float(value)
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("LLM curator confidence must be between 0.0 and 1.0.")
    return confidence


def _required_score(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 5:
        raise ValueError("LLM curator score must be an integer from 1 to 5.")
    return value


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"LLM curator JSON must contain non-empty string field: {key}.")
    return value.strip()


def _curator_quality_flags(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("LLM curator quality_flags must be a list of strings.")
    flags: list[str] = []
    for flag in value:
        if not isinstance(flag, str):
            raise ValueError("LLM curator quality_flags entries must be strings.")
        flags.append(flag)
    return dedupe_flags(tuple(flags))
