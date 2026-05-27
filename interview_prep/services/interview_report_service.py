from __future__ import annotations

from datetime import datetime

from interview_prep.domain.models import (
    AnswerEvaluation,
    AnswerEvaluationScore,
    PracticeSessionAnswerDetail,
    PracticeSessionDetail,
    SessionOutcome,
)
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.readiness_service import ReadinessService


class InterviewReportService:
    """Build a read-only Markdown report for interview readiness review."""

    def __init__(self, repository: SQLiteRepository, readiness: ReadinessService):
        self.repository = repository
        self.readiness = readiness

    def markdown(self, session_id: int | None = None, *, answer_limit: int = 5) -> str:
        selected_session_id = session_id or self._latest_completed_session_id()
        if selected_session_id is None:
            raise ValueError("Нет completed practice sessions для interview-report.")

        detail = self._completed_session_detail(selected_session_id)
        if detail is None:
            raise ValueError(f"Completed practice session #{selected_session_id} не найдена.")

        outcome = self.repository.get_session_outcome_for_session(selected_session_id)
        snapshot = self.readiness.snapshot()
        answer_cap = max(1, answer_limit)
        topic = detail.summary.topic_title or "mixed practice"
        avg_self_score = (
            f"{detail.summary.avg_self_score:.1f}/5"
            if detail.summary.avg_self_score is not None
            else "н/д"
        )
        signal = (
            f"{snapshot.overall_summary.signal_score}/100"
            if snapshot.overall_summary.signal_score is not None
            else "н/д"
        )
        lines = [
            "# Interview Report",
            "",
            f"- Generated: {datetime.now().isoformat(timespec='seconds')}",
            f"- Session: #{detail.summary.id}",
            f"- Topic: {topic}",
            f"- Finished: {detail.summary.ended_at.isoformat(timespec='minutes')}",
            f"- Answers: {detail.summary.answer_count}",
            f"- Average self-score: {avg_self_score}",
            "",
            "## Readiness Signal",
            "",
            f"- Signal: {signal}",
            f"- Label: {snapshot.overall_summary.label}",
            f"- Summary: {snapshot.overall_summary.summary}",
            f"- Caveat: {snapshot.overall_summary.caveat}",
            "",
            "## Strengths",
            "",
            *_markdown_bullets(outcome.strengths if outcome is not None else []),
            "",
            "## Gaps",
            "",
            *_markdown_bullets(outcome.gaps if outcome is not None else []),
            "",
            "## Evidence Answers",
            "",
        ]

        answers = detail.answers[:answer_cap]
        if not answers:
            lines.append("- Нет сохраненных ответов для evidence.")
        for answer in answers:
            lines.extend(
                _format_answer_evidence(
                    answer,
                    self.repository.list_answer_evaluations_for_answer(answer.answer_id),
                )
            )

        lines.extend(["", "## Next Plan", ""])
        lines.extend(_markdown_bullets(_next_plan_items(outcome, snapshot.overall_summary.top_gaps)))
        return "\n".join(lines)

    def _latest_completed_session_id(self) -> int | None:
        sessions = self.repository.list_completed_practice_sessions(limit=1)
        return sessions[0].id if sessions else None

    def _completed_session_detail(self, session_id: int) -> PracticeSessionDetail | None:
        summary = self.repository.get_completed_practice_session_summary(session_id)
        if summary is None:
            return None
        return PracticeSessionDetail(
            summary=summary,
            answers=self.repository.list_practice_session_answer_details(session_id),
        )


def _format_answer_evidence(
    answer: PracticeSessionAnswerDetail,
    evaluations: list[AnswerEvaluation],
) -> list[str]:
    lines = [
        f"### Answer #{answer.answer_id}",
        "",
        f"- Question #{answer.question_id}: {_single_line(answer.question_prompt, limit=180)}",
        f"- Difficulty: {answer.question_difficulty}",
        f"- Self-score: {answer.self_score if answer.self_score is not None else 'н/д'}",
        f"- Candidate evidence: {_single_line(answer.user_answer, limit=220)}",
    ]
    if evaluations:
        latest = evaluations[0]
        lines.append(f"- Rubric summary: {_single_line(latest.summary, limit=180)}")
        if latest.scores:
            low_scores = [
                _rubric_score_label(score)
                for score in latest.scores
                if score.effective_score <= 3
            ]
            if low_scores:
                lines.append(f"- Rubric gaps: {', '.join(low_scores[:3])}")
    if answer.ai_feedback:
        lines.append(f"- AI feedback: {_single_line(answer.ai_feedback, limit=180)}")
    lines.append("")
    return lines


def _next_plan_items(outcome: SessionOutcome | None, top_gaps) -> list[str]:
    items: list[str] = []
    if outcome is not None:
        items.extend(outcome.next_drills)
    for gap in top_gaps:
        if gap.must_fix_drill not in items:
            items.append(gap.must_fix_drill)
    return items[:5]


def _rubric_score_label(score: AnswerEvaluationScore) -> str:
    label = f"{score.dimension.title} {score.effective_score}/5"
    if score.manual_override_score is not None:
        label += f" (manual override; original {score.score}/5)"
    return label


def _markdown_bullets(items: list[str]) -> list[str]:
    normalized = [item.strip() for item in items if item.strip()]
    if not normalized:
        return ["- Нет данных."]
    return [f"- {item}" for item in normalized]


def _single_line(value: str, *, limit: int) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[: max(0, limit - 3)].rstrip()}..."
