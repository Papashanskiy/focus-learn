from __future__ import annotations

from interview_prep.domain.models import Question
from interview_prep.infra.seed import CANONICAL_2026_SOURCE


def canonical_must_know_rank(question: Question) -> int:
    if question.source == CANONICAL_2026_SOURCE and "must-know" in question.source_category_hints:
        return 0
    return 1
