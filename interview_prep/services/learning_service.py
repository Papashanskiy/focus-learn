from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import datetime

from interview_prep.domain.models import (
    LearningDialogContextSummary,
    LearningDialogMessage,
    LearningDialogSummary,
    NotebookEntry,
    Question,
    Topic,
)
from interview_prep.infra.llm import LLMClient
from interview_prep.infra.repositories import SQLiteRepository

RECENT_LEARNING_CONTEXT_MESSAGES = 6
RECENT_LEARNING_CONTEXT_CHARS = 2400
RECENT_LEARNING_CONTEXT_MESSAGE_CHARS = 700
LEARNING_DIALOG_SUMMARY_CHARS = 1200
_CONTEXT_TRUNCATION_MARKER = "\n...[сокращено]"


class LearningService:
    def __init__(self, repository: SQLiteRepository, llm: LLMClient):
        self.repository = repository
        self.llm = llm

    def explain(
        self,
        user_message: str,
        topic: Topic | None = None,
        question: Question | None = None,
        dialog_session_id: str | None = None,
        recent_messages: Sequence[LearningDialogMessage] | None = None,
        context_summary: str | None = None,
    ) -> str:
        if recent_messages is None:
            recent_messages = self.recent_dialog_context(topic, question, dialog_session_id)
        if context_summary is None:
            summary = self.dialog_context_summary(topic, question, dialog_session_id)
            context_summary = summary.summary if summary is not None else ""
        return self.llm.generate(
            build_learning_prompt(
                user_message,
                topic,
                question,
                recent_messages=recent_messages,
                context_summary=context_summary,
            )
        )

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
        recent_messages = self.recent_dialog_context(topic, question, dialog_session_id)
        summary = self.dialog_context_summary(topic, question, dialog_session_id)
        context_summary = summary.summary if summary is not None else ""
        self.add_dialog_message(
            topic_id,
            "user",
            cleaned_message,
            dialog_session_id=dialog_session_id,
            context_type=context_type,
            context_id=context_id,
        )
        explanation = self.llm.generate(
            build_learning_prompt(
                cleaned_message,
                topic,
                question,
                recent_messages=recent_messages,
                context_summary=context_summary,
            )
        ).strip()
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
        self.refresh_dialog_context_summary(topic_id, dialog_session_id)
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

    def recent_dialog_context(
        self,
        topic: Topic | None,
        question: Question | None,
        dialog_session_id: str | None,
        limit: int = RECENT_LEARNING_CONTEXT_MESSAGES,
    ) -> list[LearningDialogMessage]:
        cleaned_session_id = dialog_session_id.strip() if dialog_session_id else ""
        if not cleaned_session_id or limit <= 0:
            return []
        topic_id = topic.id if topic is not None else question.topic_id if question is not None else None
        if topic_id is None:
            return []
        messages = self.repository.list_learning_dialog_messages_for_session(cleaned_session_id)
        messages = [message for message in messages if message.topic_id == topic_id]
        return messages[-limit:]

    def dialog_context_summary(
        self,
        topic: Topic | None,
        question: Question | None,
        dialog_session_id: str | None,
    ) -> LearningDialogContextSummary | None:
        cleaned_session_id = dialog_session_id.strip() if dialog_session_id else ""
        topic_id = learning_context_topic_id(topic, question)
        if not cleaned_session_id or topic_id is None:
            return None
        return self.repository.get_learning_dialog_context_summary(cleaned_session_id, topic_id)

    def refresh_dialog_context_summary(
        self,
        topic_id: int,
        dialog_session_id: str | None,
    ) -> LearningDialogContextSummary | None:
        cleaned_session_id = dialog_session_id.strip() if dialog_session_id else ""
        if not cleaned_session_id:
            return None
        if self.repository.get_topic(topic_id) is None:
            raise ValueError(f"Unknown topic id: {topic_id}")

        messages = [
            message
            for message in self.repository.list_learning_dialog_messages_for_session(cleaned_session_id)
            if message.topic_id == topic_id
        ]
        older_messages = messages[:-RECENT_LEARNING_CONTEXT_MESSAGES]
        previous = self.repository.get_learning_dialog_context_summary(cleaned_session_id, topic_id)
        if not older_messages:
            return previous

        covered_message_id = older_messages[-1].id
        covered_message_count = len(older_messages)
        if (
            previous is not None
            and previous.covered_message_id == covered_message_id
            and previous.covered_message_count == covered_message_count
        ):
            return previous

        if previous is not None and previous.covered_message_id is not None:
            new_messages = [
                message
                for message in older_messages
                if message.id is None or message.id > previous.covered_message_id
            ]
        else:
            new_messages = older_messages
        if previous is not None and not new_messages:
            return previous

        now = datetime.now()
        summary_text = compact_learning_dialog_summary(
            new_messages,
            previous_summary=previous.summary if previous is not None else None,
        )
        return self.repository.upsert_learning_dialog_context_summary(
            LearningDialogContextSummary(
                id=None,
                topic_id=topic_id,
                dialog_session_id=cleaned_session_id,
                summary=summary_text,
                covered_message_id=covered_message_id,
                covered_message_count=covered_message_count,
                created_at=now,
                updated_at=now,
            )
        )


def build_learning_prompt(
    user_message: str,
    topic: Topic | None = None,
    question: Question | None = None,
    recent_messages: Sequence[LearningDialogMessage] | None = None,
    context_summary: str | None = None,
) -> str:
    topic_text = "Без выбранной темы"
    if topic is not None:
        topic_text = f"{topic.title}: {topic.description}"
    question_text = "Нет текущего вопроса"
    reference_text = "Нет эталонного ответа"
    if question is not None:
        question_text = question.prompt
        reference_text = question.reference_answer
    summary_text = format_learning_dialog_context_summary(context_summary)
    recent_dialog_text = format_recent_learning_dialog(recent_messages or [])

    return f"""
Ты senior Python backend mentor. Помоги разобраться в теме, а не проводи интервью.
Отвечай строго на русском языке.

Правила:
- Объясняй пошагово и простыми словами, но без упрощений, которые ломают смысл.
- Если пользователь явно не понимает базу, начни с механики и минимального примера.
- Дай 1-2 backend-примера и 1 короткий mini-drill для самопроверки.
- Не оценивай пользователя и не сохраняй ответ как interview answer.
- Если вопрос пользователя расплывчатый, сначала сформулируй, как ты его понял.
- Учитывай learning_dialog_summary как сжатую старую часть этой же учебной сессии.
- Учитывай recent_learning_dialog как предыдущие реплики этой же учебной сессии; если пользователь задает follow-up, связывай его с последними репликами.
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

<learning_dialog_summary>
{summary_text}
</learning_dialog_summary>

<recent_learning_dialog>
{recent_dialog_text}
</recent_learning_dialog>

<user_message>
{user_message}
</user_message>
""".strip()


def learning_context_topic_id(topic: Topic | None, question: Question | None) -> int | None:
    if topic is not None:
        return topic.id
    if question is not None:
        return question.topic_id
    return None


def format_learning_dialog_context_summary(
    summary: str | None,
    max_chars: int = LEARNING_DIALOG_SUMMARY_CHARS,
) -> str:
    cleaned = summary.strip() if summary else ""
    if not cleaned or max_chars <= 0:
        return "Нет сжатой истории старой части learning dialog."
    return truncate_learning_context_text(cleaned, max_chars)


def compact_learning_dialog_summary(
    messages: Sequence[LearningDialogMessage],
    previous_summary: str | None = None,
    max_chars: int = LEARNING_DIALOG_SUMMARY_CHARS,
) -> str:
    cleaned_previous = previous_summary.strip() if previous_summary else ""
    new_dialog_text = format_recent_learning_dialog(
        messages,
        max_messages=max(1, len(messages)),
        max_chars=max_chars,
        max_message_chars=240,
    )
    if new_dialog_text == "Нет предыдущих реплик в текущем learning dialog.":
        return truncate_learning_context_text(cleaned_previous, max_chars) if cleaned_previous else ""

    new_section = f"Свернутые старые реплики:\n{new_dialog_text}"
    if not cleaned_previous:
        return truncate_learning_context_text(new_section, max_chars)

    summary_text = f"{cleaned_previous}\n{new_section}"
    if len(summary_text) <= max_chars:
        return summary_text

    previous_budget = max_chars - len(new_section) - 1
    if previous_budget <= 0:
        return truncate_learning_context_text(new_section, max_chars)
    return f"{truncate_learning_context_text(cleaned_previous, previous_budget)}\n{new_section}"


def format_recent_learning_dialog(
    messages: Sequence[LearningDialogMessage],
    max_messages: int = RECENT_LEARNING_CONTEXT_MESSAGES,
    max_chars: int = RECENT_LEARNING_CONTEXT_CHARS,
    max_message_chars: int = RECENT_LEARNING_CONTEXT_MESSAGE_CHARS,
) -> str:
    if not messages or max_messages <= 0 or max_chars <= 0:
        return "Нет предыдущих реплик в текущем learning dialog."
    selected: list[str] = []
    remaining_chars = max_chars
    bounded_messages = list(messages)[-max_messages:]
    for message in reversed(bounded_messages):
        role = "user" if message.role == "user" else "assistant"
        prefix = f"{role}: "
        separator_chars = 1 if selected else 0
        available_content_chars = min(
            max_message_chars,
            remaining_chars - separator_chars - len(prefix),
        )
        if available_content_chars <= 0:
            break
        content = truncate_learning_context_text(message.content, available_content_chars)
        line = f"{prefix}{content}"
        selected.append(line)
        remaining_chars -= separator_chars + len(line)
    if not selected:
        return "Нет предыдущих реплик в текущем learning dialog."
    return "\n".join(reversed(selected))


def truncate_learning_context_text(text: str, max_chars: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= max_chars:
        return cleaned
    if max_chars <= len(_CONTEXT_TRUNCATION_MARKER):
        return cleaned[:max_chars].rstrip()
    return f"{cleaned[: max_chars - len(_CONTEXT_TRUNCATION_MARKER)].rstrip()}{_CONTEXT_TRUNCATION_MARKER}"


def notebook_title(text: str, max_length: int = 80) -> str:
    title = " ".join(text.strip().split())
    if not title:
        return "Учебное объяснение"
    if len(title) <= max_length:
        return title
    return f"{title[: max_length - 1].rstrip()}..."
