from __future__ import annotations

from interview_prep.domain.models import (
    QUESTION_SOURCE_QUALITY_ARCHIVED,
    QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
)


QUESTION_QUALITY_FLAG_GENERIC = "generic"

GENERIC_PROMPT_PHRASES = (
    ("ключевой production-риск", "generic production risk wording"),
    ("production-риск", "generic production risk wording"),
    ("backend flow", "generic backend flow wording"),
    ("backend-flow", "generic backend flow wording"),
    ("какие tradeoffs", "generic tradeoffs wording"),
    ("одну важную механику", "generic runtime mechanism wording"),
    ("database problem", "generic database problem wording"),
    ("основные design dimensions", "generic system design dimensions wording"),
)


def generic_prompt_detail(prompt: str) -> str | None:
    normalized = prompt.casefold().replace("ё", "е")
    for phrase, detail in GENERIC_PROMPT_PHRASES:
        if phrase in normalized:
            return detail
    return None


def generated_question_quality_flags(prompt: str) -> tuple[str, ...]:
    if generic_prompt_detail(prompt) is not None:
        return (QUESTION_QUALITY_FLAG_GENERIC,)
    return ()


def generated_question_source_quality_status(prompt: str) -> str:
    if generic_prompt_detail(prompt) is not None:
        return QUESTION_SOURCE_QUALITY_ARCHIVED
    return QUESTION_SOURCE_QUALITY_PENDING_REVIEW
