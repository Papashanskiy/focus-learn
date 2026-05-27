from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from interview_prep.domain.models import (
    Answer,
    AnswerEvaluation,
    PracticeSessionAnswerDetail,
    PracticeSessionDetail,
    PracticeSessionSummary,
    Question,
    SESSION_STATUS_COMPLETED,
    Session,
    SessionOutcome,
)
from interview_prep.domain.rules import DEFAULT_SESSION_MINUTES, normalize_self_score
from interview_prep.infra.llm import LLMClient
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.stats_service import StatsService


WEAK_QUESTION_REPEAT_INTERVAL_DAYS = 7
WEAK_QUESTION_SELF_SCORE_THRESHOLD = 3
FEEDBACK_FALLBACK_FLAG = "fallback_feedback"
FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG = "praise_without_candidate_evidence"
_FEEDBACK_TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_+-]+")
_FEEDBACK_HEADINGS = {
    "понял твой ответ",
    "хорошо",
    "упущено",
    "повторить",
}
_FEEDBACK_STOP_WORDS = {
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
_NO_PRAISE_MARKERS = (
    "нечего отметить",
    "нет сильных",
    "нет достаточного",
    "нет подтвержденных сильных",
    "пока нечего",
    "пока нет подтвержденных",
    "сильных сторон нет",
    "не вижу",
)


@dataclass(frozen=True)
class FeedbackQuality:
    flags: tuple[str, ...]
    evidence_terms: tuple[str, ...] = ()

    @property
    def suspicious(self) -> bool:
        return bool(self.flags)


@dataclass(frozen=True)
class GeneratedFeedback:
    text: str
    quality: FeedbackQuality


class SessionService:
    def __init__(self, repository: SQLiteRepository, llm: LLMClient):
        self.repository = repository
        self.llm = llm

    def start_session(
        self,
        topic_id: int | None = None,
        target_minutes: int = DEFAULT_SESSION_MINUTES,
    ) -> Session:
        if topic_id is not None and self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        return self.repository.create_session(
            Session(
                id=None,
                topic_id=topic_id,
                started_at=datetime.now(),
                ended_at=None,
                target_minutes=target_minutes,
            )
        )

    def finish_session(self, session_id: int, abandon_if_empty: bool = False) -> Session:
        if self.repository.get_session(session_id) is None:
            raise ValueError(f"Unknown session id: {session_id}")
        ended_at = datetime.now()
        if abandon_if_empty and self.repository.count_answers_for_session(session_id) == 0:
            self.repository.abandon_session(session_id, ended_at)
        else:
            self.repository.finish_session(session_id, ended_at)
        finished = self.repository.get_session(session_id)
        if finished is None:
            raise ValueError(f"Unknown session id: {session_id}")
        if finished.status == SESSION_STATUS_COMPLETED:
            self.generate_session_outcome(session_id)
        return finished

    def generate_session_outcome(self, session_id: int) -> SessionOutcome | None:
        if self.repository.get_session(session_id) is None:
            raise ValueError(f"Unknown session id: {session_id}")
        answers = self.repository.list_practice_session_answer_details(session_id)
        if not answers:
            return None

        evaluations = self._latest_evaluations_for_answers(answers)
        outcome = SessionOutcome(
            id=None,
            session_id=session_id,
            summary=self._session_outcome_summary(answers, evaluations),
            strengths=self._session_outcome_strengths(answers, evaluations),
            gaps=self._session_outcome_gaps(answers, evaluations),
            next_drills=self._session_outcome_next_drills(evaluations),
            readiness_delta=self._session_outcome_readiness_delta(answers, evaluations),
            created_at=datetime.now(),
        )
        return self.repository.upsert_session_outcome(outcome)

    def list_completed_sessions(self, limit: int = 30) -> list[PracticeSessionSummary]:
        return self.repository.list_completed_practice_sessions(limit=limit)

    def get_completed_session_detail(self, session_id: int) -> PracticeSessionDetail | None:
        summary = self.repository.get_completed_practice_session_summary(session_id)
        if summary is None:
            return None
        answers = self.repository.list_practice_session_answer_details(session_id)
        return PracticeSessionDetail(summary=summary, answers=answers)

    def get_session_outcome(self, session_id: int) -> SessionOutcome | None:
        if self.repository.get_session(session_id) is None:
            raise ValueError(f"Unknown session id: {session_id}")
        return self.repository.get_session_outcome_for_session(session_id)

    def next_question(self, session_id: int) -> Question | None:
        questions = self.candidate_questions(session_id)
        answered_ids = self.repository.answered_question_ids_for_session(session_id)
        for question in questions:
            if question.id not in answered_ids:
                return question
        return questions[0] if questions else None

    def candidate_questions(self, session_id: int, now: datetime | None = None) -> list[Question]:
        session = self.repository.get_session(session_id)
        if session is None:
            raise ValueError(f"Unknown session id: {session_id}")
        questions = self.repository.list_questions(session.topic_id)
        if session.topic_id is not None:
            return self._prioritize_questions_for_practice(questions, now=now)
        return self._prioritize_questions_by_weak_topics(questions, now=now)

    def _prioritize_questions_by_weak_topics(
        self,
        questions: list[Question],
        now: datetime | None = None,
    ) -> list[Question]:
        weak_topics = StatsService(self.repository).weak_topics(limit=len(self.repository.list_topics()))
        topic_rank = {
            weak_topic.topic.id: index
            for index, weak_topic in enumerate(weak_topics)
            if weak_topic.topic.id is not None
        }
        return self._prioritize_questions_for_practice(questions, topic_rank=topic_rank, now=now)

    def _prioritize_questions_for_practice(
        self,
        questions: list[Question],
        topic_rank: dict[int, int] | None = None,
        now: datetime | None = None,
    ) -> list[Question]:
        topic_rank = topic_rank or {}
        fallback_rank = len(topic_rank)
        question_metrics = self.repository.question_practice_metrics()
        reference_now = now or datetime.now()

        return sorted(
            questions,
            key=lambda question: (
                topic_rank.get(question.topic_id, fallback_rank),
                self._weak_question_repeat_rank(
                    question_metrics.get(question.id or 0, {}),
                    reference_now,
                ),
                question.topic_id,
                question.difficulty,
                question.id or 0,
            ),
        )

    def _weak_question_repeat_rank(self, metrics: dict, now: datetime) -> tuple[int, int, int]:
        last_self_score = metrics.get("last_self_score")
        last_answered_at = self._parse_datetime(metrics.get("last_answered_at"))
        if last_self_score is None or last_answered_at is None:
            return (1, 0, 0)
        if int(last_self_score) > WEAK_QUESTION_SELF_SCORE_THRESHOLD:
            return (1, 0, 0)

        days_since_answer = max(0, (now - last_answered_at).days)
        if days_since_answer < WEAK_QUESTION_REPEAT_INTERVAL_DAYS:
            return (1, 0, 0)

        return (0, -days_since_answer, int(last_self_score))

    def _parse_datetime(self, value: object) -> datetime | None:
        if value is None or isinstance(value, datetime):
            return value
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return None

    def answer_question(
        self,
        session_id: int,
        question_id: int,
        user_answer: str,
        self_score: int | None,
        with_feedback: bool = True,
    ) -> Answer:
        if self.repository.get_session(session_id) is None:
            raise ValueError(f"Unknown session id: {session_id}")
        question = self.repository.get_question(question_id)
        if question is None:
            raise ValueError(f"Unknown question id: {question_id}")
        score = normalize_self_score(self_score)
        answer = self.repository.add_answer(
            Answer(
                id=None,
                session_id=session_id,
                question_id=question_id,
                user_answer=user_answer.strip(),
                self_score=score,
                ai_feedback=None,
                answered_at=datetime.now(),
            )
        )
        if not with_feedback:
            return answer
        return self.add_feedback_to_answer(answer, question, user_answer)

    def add_feedback_to_answer(self, answer: Answer, question: Question, user_answer: str) -> Answer:
        generated_feedback = self.feedback_with_quality(question, user_answer)
        feedback = generated_feedback.text
        self.repository.update_answer_feedback(answer.id or 0, feedback)
        self.record_feedback_quality_for_answer(
            answer.id or 0,
            generated_feedback.quality,
            fallback_error=getattr(self.llm, "last_error", None),
        )
        return Answer(
            id=answer.id,
            session_id=answer.session_id,
            question_id=answer.question_id,
            user_answer=answer.user_answer,
            self_score=answer.self_score,
            ai_feedback=feedback,
            answered_at=answer.answered_at,
        )

    def update_self_score(self, answer: Answer, self_score: int | None) -> Answer:
        score = normalize_self_score(self_score)
        self.repository.update_answer_score(answer.id or 0, score)
        return Answer(
            id=answer.id,
            session_id=answer.session_id,
            question_id=answer.question_id,
            user_answer=answer.user_answer,
            self_score=score,
            ai_feedback=answer.ai_feedback,
            answered_at=answer.answered_at,
        )

    def feedback(self, question: Question, user_answer: str) -> str:
        return self.feedback_with_quality(question, user_answer).text

    def feedback_with_quality(self, question: Question, user_answer: str) -> GeneratedFeedback:
        feedback = self.llm.generate(build_feedback_prompt(question, user_answer))
        return GeneratedFeedback(
            text=feedback,
            quality=inspect_feedback_quality(feedback, user_answer),
        )

    def recheck_feedback_with_quality(
        self,
        question: Question,
        user_answer: str,
        previous_feedback: str | None = None,
    ) -> GeneratedFeedback:
        feedback = self.llm.generate(build_recheck_feedback_prompt(question, user_answer, previous_feedback))
        return GeneratedFeedback(
            text=feedback,
            quality=inspect_feedback_quality(feedback, user_answer),
        )

    def record_feedback_quality_for_answer(
        self,
        answer_id: int,
        quality: FeedbackQuality,
        *,
        fallback_error: str | None = None,
    ) -> None:
        self.repository.update_latest_answer_evaluation_feedback_quality(
            answer_id,
            flags=feedback_quality_flags(quality, fallback_error=fallback_error),
            evidence_terms=quality.evidence_terms,
            fallback_error=fallback_error,
        )

    def _latest_evaluations_for_answers(
        self,
        answers: list[PracticeSessionAnswerDetail],
    ) -> list[AnswerEvaluation]:
        evaluations: list[AnswerEvaluation] = []
        for answer in answers:
            answer_evaluations = self.repository.list_answer_evaluations_for_answer(answer.answer_id)
            if answer_evaluations:
                evaluations.append(answer_evaluations[0])
        return evaluations

    def _session_outcome_summary(
        self,
        answers: list[PracticeSessionAnswerDetail],
        evaluations: list[AnswerEvaluation],
    ) -> str:
        parts = [f"Завершена practice session: {len(answers)} ответ(ов)."]
        average_self_score = _average(answer.self_score for answer in answers)
        average_rubric_score = _average_evaluation_score(evaluations)
        if average_self_score is None:
            parts.append("Самооценка пока не заполнена.")
        else:
            parts.append(f"Средняя самооценка: {average_self_score:.1f}/5.")
        if average_rubric_score is None:
            parts.append("Rubric evaluations пока отсутствуют.")
        else:
            parts.append(f"Средний rubric score: {average_rubric_score:.1f}/5.")
        return " ".join(parts)

    def _session_outcome_strengths(
        self,
        answers: list[PracticeSessionAnswerDetail],
        evaluations: list[AnswerEvaluation],
    ) -> list[str]:
        strengths: list[str] = []
        average_self_score = _average(answer.self_score for answer in answers)
        if average_self_score is not None and average_self_score >= 4:
            strengths.append(f"Высокая средняя самооценка: {average_self_score:.1f}/5.")

        strong_dimensions = [
            f"{title} {score:.1f}/5"
            for title, score in _dimension_average_scores(evaluations)
            if score >= 4
        ]
        if strong_dimensions:
            strengths.append("Сильные rubric dimensions: " + ", ".join(strong_dimensions[:3]) + ".")

        if not strengths:
            strengths.append(f"Сессия содержит {len(answers)} сохраненных ответ(ов) для дальнейшего разбора.")
        return strengths

    def _session_outcome_gaps(
        self,
        answers: list[PracticeSessionAnswerDetail],
        evaluations: list[AnswerEvaluation],
    ) -> list[str]:
        gaps: list[str] = []
        missing_self_scores = sum(1 for answer in answers if answer.self_score is None)
        if missing_self_scores:
            gaps.append(f"{missing_self_scores} ответ(ов) без самооценки; readiness signal неполный.")

        low_dimensions = [
            f"{title} {score:.1f}/5"
            for title, score in _dimension_average_scores(evaluations)
            if score < 3
        ]
        if low_dimensions:
            gaps.append("Низкие rubric dimensions: " + ", ".join(low_dimensions[:3]) + ".")

        if not evaluations:
            gaps.append("Нет rubric evaluations для ответов; outcome опирается только на ответы и самооценку.")

        if not gaps:
            gaps.append("Явных критичных gaps по сохраненным self-score/rubric signals нет.")
        return gaps

    def _session_outcome_next_drills(self, evaluations: list[AnswerEvaluation]) -> list[str]:
        drills: list[str] = []
        for evaluation in evaluations:
            for drill in _effective_evaluation_next_drills(evaluation):
                normalized = drill.strip()
                if normalized and normalized not in drills:
                    drills.append(normalized)
                if len(drills) == 4:
                    return drills
        if not drills:
            drills.append("Выбрать следующий practice вопрос и закрыть один самый слабый rubric dimension глубже.")
        return drills

    def _session_outcome_readiness_delta(
        self,
        answers: list[PracticeSessionAnswerDetail],
        evaluations: list[AnswerEvaluation],
    ) -> float:
        signals = [
            signal
            for signal in (
                _average(answer.self_score for answer in answers),
                _average_evaluation_score(evaluations),
            )
            if signal is not None
        ]
        if not signals:
            return 0.0
        return round((_average(signals) - 3.0) / 10.0, 2)


def build_feedback_prompt(question: Question, user_answer: str) -> str:
    return f"""
Ты senior Python backend interviewer.
Дай feedback строго на русском языке.

Критически важное правило:
- Оценивай ТОЛЬКО текст между тегами <candidate_answer> и </candidate_answer>.
- Эталонный ответ используй только как чеклист того, что кандидат мог упустить.
- Нельзя писать "кандидат упомянул", "правильно описано" или "хорошо раскрыто" про то, чего нет в <candidate_answer>.
- Любая похвала и любые положительные утверждения должны опираться на evidence из <candidate_answer>, а не на <reference_answer>.
- Если ответ короткий, неточный или общий, прямо так и скажи.
- Не додумывай за кандидата и не переноси пункты из эталона в раздел "Хорошо".

Формат ответа:
Понял твой ответ:
- Коротко перескажи только то, что реально есть в <candidate_answer>.

Хорошо:
- Только то, что действительно есть в ответе кандидата.

Упущено:
- Самые важные отличия от эталона.

Повторить:
- 2-4 конкретные темы для повторения.

<question>
{question.prompt}
</question>

<candidate_answer>
{user_answer}
</candidate_answer>

<reference_answer>
{question.reference_answer}
</reference_answer>
""".strip()


def _average(values: Iterable[int | float | None]) -> float | None:
    numeric_values = [float(value) for value in values if value is not None]
    if not numeric_values:
        return None
    return sum(numeric_values) / len(numeric_values)


def _average_evaluation_score(evaluations: list[AnswerEvaluation]) -> float | None:
    scores = [score.effective_score for evaluation in evaluations for score in evaluation.scores]
    return _average(scores)


def _dimension_average_scores(evaluations: list[AnswerEvaluation]) -> list[tuple[str, float]]:
    totals: dict[str, tuple[str, float, int, int]] = {}
    for evaluation in evaluations:
        for score in evaluation.scores:
            slug = score.dimension.slug
            title, total, count, order_index = totals.get(
                slug,
                (score.dimension.title, 0.0, 0, score.dimension.order_index),
            )
            totals[slug] = (title, total + score.effective_score, count + 1, order_index)
    return [
        (title, total / count)
        for title, total, count, _order_index in sorted(
            totals.values(),
            key=lambda item: (item[3], item[0]),
        )
        if count
    ]


def _effective_evaluation_next_drills(evaluation: AnswerEvaluation) -> list[str]:
    drills: list[str] = []
    low_scores = [
        score
        for score in sorted(
            evaluation.scores,
            key=lambda item: (item.effective_score, item.dimension.order_index),
        )
        if score.effective_score < 4
    ]
    for score in low_scores:
        if not score.next_drill:
            continue
        if score.next_drill not in drills:
            drills.append(score.next_drill)
    if drills:
        return drills
    if low_scores:
        return evaluation.next_drills
    return []


def build_recheck_feedback_prompt(
    question: Question,
    user_answer: str,
    previous_feedback: str | None = None,
) -> str:
    return f"""
Ты senior Python backend interviewer и проверяешь AI feedback повторно.
Дай новый feedback строго на русском языке.

Более строгие правила recheck:
- Единственный источник фактов о кандидате — текст между <candidate_answer> и </candidate_answer>.
- <previous_feedback> может содержать завышенную похвалу; используй его только как список claim'ов для проверки.
- Не сохраняй похвалу из <previous_feedback>, если она не подтверждена прямым evidence из <candidate_answer>.
- Если в <candidate_answer> короткий ответ вроде "не знаю", "не уверен" или общий комментарий без деталей, раздел "Хорошо" должен прямо сказать, что подтвержденных сильных сторон нет.
- Любой пункт в "Хорошо" должен цитировать или явно называть evidence из <candidate_answer>.
- Эталонный ответ используй только для разделов "Упущено" и "Повторить".

Формат ответа:
Понял твой ответ:
- Коротко перескажи только то, что реально есть в <candidate_answer>.

Хорошо:
- Только подтвержденные сильные стороны. Если их нет, напиши: "Пока нет подтвержденных сильных сторон в ответе."

Упущено:
- Самые важные отличия от эталона.

Повторить:
- 2-4 конкретные темы для повторения.

<question>
{question.prompt}
</question>

<candidate_answer>
{user_answer}
</candidate_answer>

<previous_feedback>
{previous_feedback or ""}
</previous_feedback>

<reference_answer>
{question.reference_answer}
</reference_answer>
""".strip()


def inspect_feedback_quality(feedback: str, candidate_answer: str) -> FeedbackQuality:
    good_section = _extract_feedback_section(feedback, "хорошо")
    if not good_section.strip() or _is_explicit_no_praise(good_section):
        return FeedbackQuality(flags=())

    evidence_terms = _feedback_evidence_terms(candidate_answer, good_section)
    if evidence_terms:
        return FeedbackQuality(flags=(), evidence_terms=tuple(sorted(evidence_terms)))
    return FeedbackQuality(flags=(FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG,))


def feedback_quality_flags(
    quality: FeedbackQuality,
    *,
    fallback_error: str | None = None,
) -> tuple[str, ...]:
    flags = list(quality.flags)
    if fallback_error:
        flags.append(FEEDBACK_FALLBACK_FLAG)
    return tuple(dict.fromkeys(flags))


def _extract_feedback_section(feedback: str, heading: str) -> str:
    section_lines: list[str] = []
    in_section = False
    for line in feedback.splitlines():
        parsed_heading = _parse_feedback_heading(line)
        if parsed_heading is not None:
            current_heading, rest = parsed_heading
            if current_heading == heading:
                in_section = True
                if rest:
                    section_lines.append(rest)
                continue
            if in_section:
                break
        elif in_section:
            section_lines.append(line)
    return "\n".join(section_lines).strip()


def _parse_feedback_heading(line: str) -> tuple[str, str] | None:
    normalized = line.strip().lstrip("#").strip()
    normalized = normalized.lstrip("-*• ").strip()
    normalized = normalized.strip("*_` ").strip()
    if not normalized:
        return None
    title, separator, rest = normalized.partition(":")
    heading = title.strip("*_` ").strip().lower()
    if heading in _FEEDBACK_HEADINGS:
        return heading, rest.strip() if separator else ""
    return None


def _feedback_evidence_terms(candidate_answer: str, feedback_section: str) -> set[str]:
    candidate_tokens = set(_feedback_tokens(candidate_answer))
    section_tokens = set(_feedback_tokens(feedback_section))
    evidence_terms = candidate_tokens & section_tokens
    if evidence_terms:
        return evidence_terms

    stemmed_evidence: set[str] = set()
    for candidate_token in candidate_tokens:
        for section_token in section_tokens:
            if _tokens_share_stem(candidate_token, section_token):
                stemmed_evidence.add(candidate_token)
    return stemmed_evidence


def _feedback_tokens(text: str) -> list[str]:
    tokens = []
    for token in _FEEDBACK_TOKEN_RE.findall(text.lower()):
        if len(token) < 3 or token in _FEEDBACK_STOP_WORDS:
            continue
        tokens.append(token)
    return tokens


def _tokens_share_stem(left: str, right: str) -> bool:
    if len(left) < 5 or len(right) < 5:
        return False
    prefix_length = min(5, len(left), len(right))
    return left[:prefix_length] == right[:prefix_length]


def _is_explicit_no_praise(section: str) -> bool:
    lowered = " ".join(section.lower().split())
    return any(marker in lowered for marker in _NO_PRAISE_MARKERS)
