from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


SESSION_STATUS_IN_PROGRESS = "in_progress"
SESSION_STATUS_COMPLETED = "completed"
SESSION_STATUS_ABANDONED = "abandoned"
SESSION_STATUSES = (
    SESSION_STATUS_IN_PROGRESS,
    SESSION_STATUS_COMPLETED,
    SESSION_STATUS_ABANDONED,
)

SESSION_OUTCOME_TYPE_PRACTICE = "practice"
SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE = "calibration_baseline"
SESSION_OUTCOME_TYPES = (
    SESSION_OUTCOME_TYPE_PRACTICE,
    SESSION_OUTCOME_TYPE_CALIBRATION_BASELINE,
)

QUESTION_SOURCE_QUALITY_PENDING_REVIEW = "pending_review"
QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW = "pending_auto_review"
QUESTION_SOURCE_QUALITY_ACCEPTED = "accepted"
QUESTION_SOURCE_QUALITY_ARCHIVED = "archived"
QUESTION_SOURCE_QUALITY_STATUSES = (
    QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
    QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_ARCHIVED,
)


@dataclass(frozen=True)
class Topic:
    id: int | None
    slug: str
    title: str
    description: str
    level: str


@dataclass(frozen=True)
class CurriculumTopic:
    id: int | None
    topic_id: int | None
    slug: str
    title: str
    description: str
    level: str
    source: str
    order_index: int


@dataclass(frozen=True)
class CurriculumSubtopic:
    id: int | None
    curriculum_topic_id: int
    slug: str
    title: str
    description: str
    source: str
    order_index: int


@dataclass(frozen=True)
class CurriculumObjective:
    id: int | None
    curriculum_topic_id: int
    curriculum_subtopic_id: int | None
    text: str
    source: str
    order_index: int


@dataclass(frozen=True)
class Question:
    id: int | None
    topic_id: int
    difficulty: str
    prompt: str
    hint: str
    reference_answer: str
    source: str = "bootstrap"
    source_quality_status: str = QUESTION_SOURCE_QUALITY_ACCEPTED
    source_url: str | None = None
    source_retrieved_at: datetime | None = None
    source_category_hints: tuple[str, ...] = ()
    source_frequency_hint: str | None = None


@dataclass(frozen=True)
class Tag:
    id: int | None
    slug: str
    title: str
    description: str = ""
    source: str = "manual"


@dataclass(frozen=True)
class Competency:
    id: int | None
    slug: str
    title: str
    description: str
    category: str
    level: str
    order_index: int


@dataclass(frozen=True)
class QuestionCompetencyLink:
    competency: Competency
    is_primary: bool = False
    weight: float = 1.0


@dataclass(frozen=True)
class RubricDimension:
    id: int | None
    slug: str
    title: str
    description: str
    order_index: int


@dataclass(frozen=True)
class AnswerEvaluationScore:
    dimension: RubricDimension
    score: int
    evidence: str
    gaps: str
    next_drill: str | None = None
    manual_override_score: int | None = None
    manual_override_reason: str | None = None
    manual_override_at: datetime | None = None

    @property
    def effective_score(self) -> int:
        return self.manual_override_score if self.manual_override_score is not None else self.score


@dataclass(frozen=True)
class AnswerEvaluation:
    id: int | None
    answer_id: int
    session_id: int
    question_id: int
    summary: str
    scores: list[AnswerEvaluationScore]
    next_drills: list[str]
    source: str
    created_at: datetime
    raw_payload_json: str | None = None


@dataclass(frozen=True)
class Session:
    id: int | None
    started_at: datetime
    target_minutes: int
    topic_id: int | None = None
    ended_at: datetime | None = None
    status: str = SESSION_STATUS_IN_PROGRESS


@dataclass(frozen=True)
class SessionOutcome:
    id: int | None
    session_id: int
    summary: str
    strengths: list[str]
    gaps: list[str]
    next_drills: list[str]
    readiness_delta: float
    created_at: datetime
    outcome_type: str = SESSION_OUTCOME_TYPE_PRACTICE


@dataclass(frozen=True)
class PracticeSessionSummary:
    id: int
    topic_id: int | None
    topic_title: str | None
    started_at: datetime
    ended_at: datetime
    target_minutes: int
    answer_count: int
    avg_self_score: float | None


@dataclass(frozen=True)
class PracticeSessionAnswerDetail:
    answer_id: int
    question_id: int
    question_difficulty: str
    question_prompt: str
    user_answer: str
    self_score: int | None
    reference_answer: str
    ai_feedback: str | None
    answered_at: datetime


@dataclass(frozen=True)
class PracticeSessionDetail:
    summary: PracticeSessionSummary
    answers: list[PracticeSessionAnswerDetail]


@dataclass(frozen=True)
class Answer:
    id: int | None
    session_id: int
    question_id: int
    user_answer: str
    self_score: int | None
    ai_feedback: str | None
    answered_at: datetime


@dataclass(frozen=True)
class ContentGenerationJob:
    id: int | None
    kind: str
    status: str
    payload_json: str
    result_json: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class QuestionSourceSnapshot:
    id: int | None
    source_id: str
    url: str
    title: str
    retrieved_at: datetime
    checksum: str
    category_hints: list[str]
    created_at: datetime


@dataclass(frozen=True)
class LearningMaterial:
    id: int | None
    topic_id: int
    title: str
    body: str
    source: str
    created_at: datetime
    archived_at: datetime | None = None
    archive_reason: str | None = None


@dataclass(frozen=True)
class LearningDialogMessage:
    id: int | None
    topic_id: int
    role: str
    content: str
    created_at: datetime
    dialog_session_id: str | None = None
    context_type: str | None = None
    context_id: str | None = None


@dataclass(frozen=True)
class LearningDialogSummary:
    topic_id: int
    topic_title: str
    dialog_date: str
    first_message_at: datetime
    last_message_at: datetime
    message_count: int
    dialog_session_id: str | None = None
    context_type: str | None = None
    context_id: str | None = None


@dataclass(frozen=True)
class NotebookEntry:
    id: int | None
    topic_id: int
    curriculum_subtopic_id: int | None
    dialog_session_id: str | None
    source_message_id: int | None
    title: str
    body: str
    source: str
    created_at: datetime


@dataclass(frozen=True)
class ManualNote:
    id: int | None
    topic_id: int | None
    session_id: int | None
    context_type: str | None
    context_id: str | None
    title: str
    body: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class SystemDesignScenario:
    id: int | None
    topic_id: int
    title: str
    scenario: str
    focus_areas: list[str]
    source: str
    created_at: datetime
    archived_at: datetime | None = None
    archive_reason: str | None = None


@dataclass(frozen=True)
class SystemDesignTranscriptMessage:
    id: int | None
    topic_id: int
    scenario_id: int | None
    role: str
    content: str
    created_at: datetime


@dataclass(frozen=True)
class SystemDesignArtifact:
    id: int | None
    topic_id: int
    scenario_id: int | None
    section: str
    content: str
    created_at: datetime


@dataclass(frozen=True)
class SystemDesignFeedbackArtifact:
    id: int | None
    topic_id: int
    scenario_id: int | None
    session_id: int | None
    content: str
    source: str
    created_at: datetime


@dataclass(frozen=True)
class SystemDesignEvaluation:
    id: int | None
    feedback_artifact_id: int
    topic_id: int
    scenario_id: int | None
    session_id: int | None
    summary: str
    scores: list[AnswerEvaluationScore]
    next_drills: list[str]
    source: str
    created_at: datetime
    raw_payload_json: str | None = None
