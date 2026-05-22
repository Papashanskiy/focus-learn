from __future__ import annotations


MIN_SELF_SCORE = 1
MAX_SELF_SCORE = 5
DEFAULT_SESSION_MINUTES = 60


def normalize_self_score(value: int | None) -> int | None:
    if value is None:
        return None
    if not MIN_SELF_SCORE <= value <= MAX_SELF_SCORE:
        raise ValueError(f"self_score must be between {MIN_SELF_SCORE} and {MAX_SELF_SCORE}")
    return value


def normalize_difficulty(value: str) -> str:
    normalized = value.strip().lower()
    allowed = {"middle", "middle+", "senior"}
    if normalized not in allowed:
        raise ValueError(f"difficulty must be one of: {', '.join(sorted(allowed))}")
    return normalized
