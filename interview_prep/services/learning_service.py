from __future__ import annotations

import re
from datetime import datetime

from interview_prep.domain.models import LearningDialogMessage, LearningDialogSummary, NotebookEntry, Question, Topic
from interview_prep.infra.llm import LLMClient
from interview_prep.infra.repositories import SQLiteRepository


class LearningService:
    def __init__(self, repository: SQLiteRepository, llm: LLMClient):
        self.repository = repository
        self.llm = llm

    def explain(
        self,
        user_message: str,
        topic: Topic | None = None,
        question: Question | None = None,
    ) -> str:
        return self.llm.generate(build_learning_prompt(user_message, topic, question))

    def explain_and_save(
        self,
        topic_id: int,
        user_message: str,
        topic: Topic | None = None,
        question: Question | None = None,
        dialog_session_id: str | None = None,
        context_type: str | None = None,
        context_id: str | None = None,
    ) -> str:
        cleaned_message = user_message.strip()
        self.add_dialog_message(
            topic_id,
            "user",
            cleaned_message,
            dialog_session_id=dialog_session_id,
            context_type=context_type,
            context_id=context_id,
        )
        explanation = self.explain(cleaned_message, topic=topic, question=question).strip()
        assistant_message = self.add_dialog_message(
            topic_id,
            "assistant",
            explanation,
            dialog_session_id=dialog_session_id,
            context_type=context_type,
            context_id=context_id,
        )
        self.add_notebook_entry_from_learning_reply(
            topic_id,
            explanation,
            title=cleaned_message,
            dialog_session_id=dialog_session_id,
            source_message_id=assistant_message.id,
        )
        return explanation

    def add_dialog_message(
        self,
        topic_id: int,
        role: str,
        content: str,
        dialog_session_id: str | None = None,
        context_type: str | None = None,
        context_id: str | None = None,
    ) -> LearningDialogMessage:
        if self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        if role not in {"user", "assistant"}:
            raise ValueError(f"Unknown learning dialog role: {role}")
        cleaned_content = content.strip()
        if not cleaned_content:
            raise ValueError("Learning dialog message cannot be empty")
        return self.repository.add_learning_dialog_message(
            LearningDialogMessage(
                id=None,
                topic_id=topic_id,
                role=role,
                content=cleaned_content,
                created_at=datetime.now(),
                dialog_session_id=dialog_session_id.strip() if dialog_session_id else None,
                context_type=context_type.strip() if context_type else None,
                context_id=context_id.strip() if context_id else None,
            )
        )

    def add_notebook_entry_from_learning_reply(
        self,
        topic_id: int,
        explanation: str,
        title: str | None = None,
        dialog_session_id: str | None = None,
        source_message_id: int | None = None,
    ) -> NotebookEntry:
        if self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        cleaned_body = explanation.strip()
        if not cleaned_body:
            raise ValueError("Notebook entry body cannot be empty")
        cleaned_title = notebook_title(title or cleaned_body)
        return self.repository.add_notebook_entry(
            NotebookEntry(
                id=None,
                topic_id=topic_id,
                curriculum_subtopic_id=None,
                dialog_session_id=dialog_session_id.strip() if dialog_session_id else None,
                source_message_id=source_message_id,
                title=cleaned_title,
                body=cleaned_body,
                source="learning-ai",
                created_at=datetime.now(),
            )
        )

    def list_dialog_messages(self, topic_id: int, limit: int = 20) -> list[LearningDialogMessage]:
        if self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        return self.repository.list_learning_dialog_messages(topic_id, limit=limit)

    def list_dialog_messages_for_date(self, topic_id: int, dialog_date: str) -> list[LearningDialogMessage]:
        if self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", dialog_date):
            raise ValueError("Learning dialog date must use YYYY-MM-DD")
        return self.repository.list_learning_dialog_messages_for_date(topic_id, dialog_date)

    def list_dialog_messages_for_session(self, dialog_session_id: str) -> list[LearningDialogMessage]:
        cleaned_session_id = dialog_session_id.strip()
        if not cleaned_session_id:
            raise ValueError("Learning dialog session id cannot be empty")
        return self.repository.list_learning_dialog_messages_for_session(cleaned_session_id)

    def list_dialog_summaries(self, limit: int = 30) -> list[LearningDialogSummary]:
        return self.repository.list_learning_dialog_summaries(limit=limit)


def build_learning_prompt(
    user_message: str,
    topic: Topic | None = None,
    question: Question | None = None,
) -> str:
    topic_text = "Без выбранной темы"
    if topic is not None:
        topic_text = f"{topic.title}: {topic.description}"
    question_text = "Нет текущего вопроса"
    reference_text = "Нет эталонного ответа"
    if question is not None:
        question_text = question.prompt
        reference_text = question.reference_answer

    return f"""
Ты senior Python backend mentor. Помоги разобраться в теме, а не проводи интервью.
Отвечай строго на русском языке.

Правила:
- Объясняй пошагово и простыми словами, но без упрощений, которые ломают смысл.
- Если пользователь явно не понимает базу, начни с механики и минимального примера.
- Дай 1-2 backend-примера и 1 короткий mini-drill для самопроверки.
- Не оценивай пользователя и не сохраняй ответ как interview answer.
- Если вопрос пользователя расплывчатый, сначала сформулируй, как ты его понял.
- В конце задай один уточняющий вопрос или предложи следующий шаг.

<topic>
{topic_text}
</topic>

<current_interview_question>
{question_text}
</current_interview_question>

<reference_answer_for_context>
{reference_text}
</reference_answer_for_context>

<user_message>
{user_message}
</user_message>
""".strip()


def notebook_title(text: str, max_length: int = 80) -> str:
    title = " ".join(text.strip().split())
    if not title:
        return "Учебное объяснение"
    if len(title) <= max_length:
        return title
    return f"{title[: max_length - 1].rstrip()}..."
