from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from interview_prep.domain.models import Answer, Question, Session, Topic


PracticeSubmitAction = Literal[
    "start_today_drill",
    "start_topic_session",
    "capture_score",
    "next_question",
    "empty_answer",
    "capture_answer",
]
PracticeMode = Literal["select_topic", "answering", "scoring", "answered"]


@dataclass(frozen=True)
class PracticeSubmitDecision:
    action: PracticeSubmitAction
    value: str = ""


@dataclass(frozen=True)
class PracticeSessionStartSnapshot:
    session: Session
    topic: Topic | None
    question: Question | None
    current_answer: Answer | None
    pending_answer_text: str | None
    started_at: datetime
    answered_count: int
    skipped_count: int
    skipped_question_ids: frozenset[int]
    showing_hint: bool
    showing_reference: bool
    mode: PracticeMode
    generated_learning_material: str | None
    generated_learning_material_topic_id: int | None


@dataclass(frozen=True)
class PracticeSessionResetSnapshot:
    session: Session | None
    topic: Topic | None
    question: Question | None
    current_answer: Answer | None
    pending_answer_text: str | None
    started_at: datetime | None
    answered_count: int
    skipped_count: int
    skipped_question_ids: frozenset[int]
    showing_hint: bool
    showing_reference: bool
    command_palette_visible: bool
    mode: PracticeMode


@dataclass(frozen=True)
class PracticeAnswerScoringSnapshot:
    current_answer: Answer
    pending_answer_text: str
    answered_count: int
    showing_reference: bool
    mode: PracticeMode


@dataclass(frozen=True)
class PracticeSelfScoreParseResult:
    score: int | None
    error: str | None = None


@dataclass(frozen=True)
class PracticeAnsweredSnapshot:
    current_answer: Answer
    showing_reference: bool
    mode: PracticeMode


@dataclass(frozen=True)
class PracticeNextQuestionSnapshot:
    question: Question | None
    current_answer: Answer | None
    pending_answer_text: str | None
    last_feedback: str
    showing_hint: bool
    showing_reference: bool
    mode: PracticeMode


def decide_practice_submit(mode: str, raw: str) -> PracticeSubmitDecision | None:
    """Route composer submits for practice-owned modes without touching TUI state."""
    if mode == "select_topic":
        if raw:
            return PracticeSubmitDecision("start_topic_session", raw)
        return PracticeSubmitDecision("start_today_drill")
    if mode == "scoring":
        return PracticeSubmitDecision("capture_score", raw)
    if mode == "answered":
        if raw:
            return PracticeSubmitDecision("capture_answer", raw)
        return PracticeSubmitDecision("next_question")
    if mode == "answering":
        if raw:
            return PracticeSubmitDecision("capture_answer", raw)
        return PracticeSubmitDecision("empty_answer")
    return None


def build_practice_session_start_snapshot(
    session: Session,
    topic: Topic | None,
) -> PracticeSessionStartSnapshot:
    """State values for a newly started practice session, before UI side effects."""
    return PracticeSessionStartSnapshot(
        session=session,
        topic=topic,
        question=None,
        current_answer=None,
        pending_answer_text=None,
        started_at=session.started_at,
        answered_count=0,
        skipped_count=0,
        skipped_question_ids=frozenset(),
        showing_hint=False,
        showing_reference=False,
        mode="answering",
        generated_learning_material=None,
        generated_learning_material_topic_id=None,
    )


def build_practice_session_reset_snapshot() -> PracticeSessionResetSnapshot:
    """State values for returning to the topic-selection practice screen."""
    return PracticeSessionResetSnapshot(
        session=None,
        topic=None,
        question=None,
        current_answer=None,
        pending_answer_text=None,
        started_at=None,
        answered_count=0,
        skipped_count=0,
        skipped_question_ids=frozenset(),
        showing_hint=False,
        showing_reference=False,
        command_palette_visible=False,
        mode="select_topic",
    )


def build_practice_answer_scoring_snapshot(
    answer: Answer,
    answered_count: int,
) -> PracticeAnswerScoringSnapshot:
    """State values after an answer has been persisted and is ready for self-score."""
    return PracticeAnswerScoringSnapshot(
        current_answer=answer,
        pending_answer_text=answer.user_answer,
        answered_count=answered_count,
        showing_reference=True,
        mode="scoring",
    )


def parse_practice_self_score(raw: str) -> PracticeSelfScoreParseResult:
    """Parse the optional 1-5 practice self-score submitted from the composer."""
    if not raw:
        return PracticeSelfScoreParseResult(score=None)
    try:
        score = int(raw)
    except ValueError:
        return PracticeSelfScoreParseResult(
            score=None,
            error="Самооценка должна быть числом 1-5 или пустой строкой.",
        )
    if not 1 <= score <= 5:
        return PracticeSelfScoreParseResult(
            score=None,
            error="Самооценка должна быть от 1 до 5.",
        )
    return PracticeSelfScoreParseResult(score=score)


def build_practice_answered_snapshot(answer: Answer) -> PracticeAnsweredSnapshot:
    """State values after the self-score step is complete."""
    return PracticeAnsweredSnapshot(
        current_answer=answer,
        showing_reference=True,
        mode="answered",
    )


def build_practice_next_question_snapshot(question: Question | None) -> PracticeNextQuestionSnapshot:
    """State values for moving from an answered question to the next prompt."""
    return PracticeNextQuestionSnapshot(
        question=question,
        current_answer=None,
        pending_answer_text=None,
        last_feedback="",
        showing_hint=False,
        showing_reference=False,
        mode="answering",
    )
