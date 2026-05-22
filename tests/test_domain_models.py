from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError

from datetime import datetime

from interview_prep.domain import (
    AnswerEvaluation,
    AnswerEvaluationScore,
    Competency,
    CurriculumObjective,
    CurriculumSubtopic,
    CurriculumTopic,
    ManualNote,
    NotebookEntry,
    RubricDimension,
    SessionOutcome,
    Tag,
    SystemDesignEvaluation,
)


class DomainModelTests(unittest.TestCase):
    def test_curriculum_models_describe_generated_topic_structure(self) -> None:
        topic = CurriculumTopic(
            id=1,
            topic_id=10,
            slug="python-runtime",
            title="Python runtime",
            description="Object model and production tradeoffs.",
            level="middle+",
            source="llm-seed",
            order_index=1,
        )
        subtopic = CurriculumSubtopic(
            id=2,
            curriculum_topic_id=topic.id or 0,
            slug="descriptor-protocol",
            title="Descriptor protocol",
            description="Attribute lookup, properties and ORM fields.",
            source="llm-seed",
            order_index=1,
        )
        objective = CurriculumObjective(
            id=3,
            curriculum_topic_id=topic.id or 0,
            curriculum_subtopic_id=subtopic.id,
            text="Связывать descriptor lookup с production behavior ORM.",
            source="llm-seed",
            order_index=1,
        )

        self.assertEqual(topic.topic_id, 10)
        self.assertEqual(subtopic.curriculum_topic_id, topic.id)
        self.assertEqual(objective.curriculum_subtopic_id, subtopic.id)
        self.assertEqual(objective.source, "llm-seed")

    def test_curriculum_models_are_immutable_like_other_domain_models(self) -> None:
        topic = CurriculumTopic(
            id=None,
            topic_id=None,
            slug="async-backend",
            title="Async backend",
            description="Cancellation, backpressure and worker lifecycle.",
            level="senior",
            source="manual",
            order_index=2,
        )

        with self.assertRaises(FrozenInstanceError):
            setattr(topic, "title", "Changed")

    def test_question_tag_model_describes_reusable_question_label(self) -> None:
        tag = Tag(
            id=1,
            slug="asyncio-cancellation",
            title="Asyncio cancellation",
            description="Cancellation, timeouts and cleanup in async services.",
            source="manual",
        )

        self.assertEqual(tag.slug, "asyncio-cancellation")
        self.assertEqual(tag.source, "manual")

        with self.assertRaises(FrozenInstanceError):
            setattr(tag, "title", "Changed")

    def test_competency_model_describes_senior_readiness_axis(self) -> None:
        competency = Competency(
            id=1,
            slug="distributed-systems",
            title="Distributed Systems",
            description="Consistency, retries, partitions and failure boundaries.",
            category="architecture",
            level="senior",
            order_index=40,
        )

        self.assertEqual(competency.slug, "distributed-systems")
        self.assertEqual(competency.category, "architecture")
        self.assertEqual(competency.level, "senior")
        self.assertEqual(competency.order_index, 40)

        with self.assertRaises(FrozenInstanceError):
            setattr(competency, "title", "Changed")

    def test_rubric_models_describe_structured_answer_evaluation(self) -> None:
        dimension = RubricDimension(
            id=1,
            slug="tradeoffs",
            title="Tradeoffs",
            description="Alternatives, costs and explicit conditions for choosing one approach.",
            order_index=30,
        )
        score = AnswerEvaluationScore(
            dimension=dimension,
            score=4,
            evidence="Candidate compared optimistic locking with row locks.",
            gaps="Did not mention retry/idempotency boundaries.",
            next_drill="Practice transaction isolation tradeoffs.",
        )
        evaluation = AnswerEvaluation(
            id=10,
            answer_id=20,
            session_id=30,
            question_id=40,
            summary="Strong tradeoff framing with one missing failure-mode detail.",
            scores=[score],
            next_drills=["Repeat retries and idempotency after failed writes."],
            source="llm",
            created_at=datetime(2026, 5, 19, 12, 0, 0),
            raw_payload_json='{"scores": []}',
        )

        self.assertEqual(evaluation.answer_id, 20)
        self.assertEqual(evaluation.session_id, 30)
        self.assertEqual(evaluation.question_id, 40)
        self.assertEqual(evaluation.scores[0].dimension.slug, "tradeoffs")
        self.assertEqual(evaluation.scores[0].score, 4)
        self.assertEqual(evaluation.next_drills[0], "Repeat retries and idempotency after failed writes.")
        self.assertEqual(evaluation.raw_payload_json, '{"scores": []}')

        with self.assertRaises(FrozenInstanceError):
            setattr(dimension, "title", "Changed")
        with self.assertRaises(FrozenInstanceError):
            setattr(evaluation, "summary", "Changed")

    def test_notebook_entry_model_describes_ai_explanation_note(self) -> None:
        entry = NotebookEntry(
            id=1,
            topic_id=10,
            curriculum_subtopic_id=20,
            dialog_session_id="learn-session-1",
            source_message_id=30,
            title="Descriptor lookup order",
            body="Data descriptors override instance attributes; non-data descriptors do not.",
            source="learning-ai",
            created_at=datetime(2026, 5, 13, 10, 0, 0),
        )

        self.assertEqual(entry.topic_id, 10)
        self.assertEqual(entry.curriculum_subtopic_id, 20)
        self.assertEqual(entry.dialog_session_id, "learn-session-1")
        self.assertEqual(entry.source_message_id, 30)

        with self.assertRaises(FrozenInstanceError):
            setattr(entry, "title", "Changed")

    def test_manual_note_model_describes_user_authored_note(self) -> None:
        note = ManualNote(
            id=1,
            topic_id=10,
            session_id=20,
            context_type="practice-question",
            context_id="30",
            title="Retry semantics",
            body="Retry only idempotent operations or use idempotency keys.",
            created_at=datetime(2026, 5, 21, 9, 0, 0),
            updated_at=datetime(2026, 5, 21, 9, 5, 0),
        )

        self.assertEqual(note.topic_id, 10)
        self.assertEqual(note.session_id, 20)
        self.assertEqual(note.context_type, "practice-question")
        self.assertEqual(note.context_id, "30")

        with self.assertRaises(FrozenInstanceError):
            setattr(note, "body", "Changed")

    def test_session_outcome_model_describes_completed_practice_result(self) -> None:
        outcome = SessionOutcome(
            id=1,
            session_id=10,
            summary="Уверенный разбор транзакций, но не хватило failure-mode деталей.",
            strengths=["Связал isolation level с бизнес-инвариантами."],
            gaps=["Не описал retry/idempotency после serialization failure."],
            next_drills=["Повторить transaction isolation и retry boundaries."],
            readiness_delta=0.15,
            created_at=datetime(2026, 5, 19, 13, 0, 0),
        )

        self.assertEqual(outcome.session_id, 10)
        self.assertEqual(outcome.summary, "Уверенный разбор транзакций, но не хватило failure-mode деталей.")
        self.assertEqual(outcome.strengths[0], "Связал isolation level с бизнес-инвариантами.")
        self.assertEqual(outcome.gaps[0], "Не описал retry/idempotency после serialization failure.")
        self.assertEqual(outcome.next_drills[0], "Повторить transaction isolation и retry boundaries.")
        self.assertEqual(outcome.readiness_delta, 0.15)

        with self.assertRaises(FrozenInstanceError):
            setattr(outcome, "summary", "Changed")

    def test_system_design_evaluation_model_describes_rubric_scores(self) -> None:
        dimension = RubricDimension(
            id=1,
            slug="requirements",
            title="Requirements",
            description="Scope, constraints and non-functional requirements.",
            order_index=10,
        )
        score = AnswerEvaluationScore(
            dimension=dimension,
            score=3,
            evidence='Наблюдаемое evidence из artifact section: "SLA 99.9%."',
            gaps="Добавь actors and constraints.",
            next_drill="Повтори requirements для system design.",
        )
        evaluation = SystemDesignEvaluation(
            id=1,
            feedback_artifact_id=2,
            topic_id=3,
            scenario_id=4,
            session_id=5,
            summary="Средний system design rubric score: 3.0/5.",
            scores=[score],
            next_drills=["Повтори requirements для system design."],
            source="heuristic",
            created_at=datetime(2026, 5, 21, 10, 0, 0),
            raw_payload_json=None,
        )

        self.assertEqual(evaluation.feedback_artifact_id, 2)
        self.assertEqual(evaluation.scores[0].dimension.slug, "requirements")
        self.assertEqual(evaluation.scores[0].score, 3)
        self.assertEqual(evaluation.next_drills, ["Повтори requirements для system design."])

        with self.assertRaises(FrozenInstanceError):
            setattr(evaluation, "summary", "Changed")


if __name__ == "__main__":
    unittest.main()
