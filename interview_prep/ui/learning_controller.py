from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


LearningMode = Literal["learning", "loading_learning"]

LEARNING_ENTRY_FEEDBACK = (
    "Режим обучения.\n"
    "Напиши, что непонятно по текущей теме или вопросу.\n"
    "Команда /practice вернет к интервью-сессии."
)


@dataclass(frozen=True)
class LearningEntrySnapshot:
    learning_return_mode: str
    learning_dialog_session_id: str
    learning_topic_id: int | None
    clear_current_practice_context: bool
    mode: Literal["learning"]
    command_palette_visible: bool
    last_feedback: str
    should_clear_generated_learning_material: bool
    should_ensure_learning_material: bool


@dataclass(frozen=True)
class LearningRequestSnapshot:
    learning_topic_id: int | None
    learning_dialog_session_id: str
    learning_question: str
    learning_pending_message: str
    learning_dialog_offset: int
    command_palette_visible: bool
    mode: Literal["loading_learning"]
    ollama_status: str
    last_feedback: str
    history_message: str


@dataclass(frozen=True)
class LearningFinishSnapshot:
    ollama_status: str
    history_message: str
    transcript_entries: tuple[tuple[str, str], ...]
    learning_pending_message: str
    learning_dialog_offset: int
    last_feedback: str
    mode: Literal["learning"]


def resolve_learning_context_topic_id(
    *,
    source_mode: str,
    current_topic_id: int | None,
    session_topic_id: int | None,
    has_session: bool,
) -> int | None:
    """Choose the topic that /learn should attach to without touching TUI state."""
    if source_mode == "select_topic" and not has_session:
        return None
    if current_topic_id is not None:
        return current_topic_id
    if has_session:
        return session_topic_id
    return None


def build_learning_entry_snapshot(
    *,
    current_mode: str,
    current_topic_id: int | None,
    session_topic_id: int | None,
    has_session: bool,
    current_learning_return_mode: str,
    current_learning_dialog_session_id: str | None,
    generated_learning_material: str | None,
    generated_learning_material_topic_id: int | None,
    new_dialog_session_id: str,
) -> LearningEntrySnapshot:
    """State values for entering focused learning mode before UI/storage side effects."""
    topic_id = resolve_learning_context_topic_id(
        source_mode=current_mode,
        current_topic_id=current_topic_id,
        session_topic_id=session_topic_id,
        has_session=has_session,
    )
    already_learning = current_mode in {"learning", "loading_learning"}
    learning_return_mode = current_learning_return_mode if already_learning else current_mode
    learning_dialog_session_id = (
        current_learning_dialog_session_id
        if already_learning and current_learning_dialog_session_id is not None
        else new_dialog_session_id
    )
    should_clear_generated_learning_material = topic_id is None
    should_ensure_learning_material = (
        topic_id is not None
        and (not generated_learning_material or generated_learning_material_topic_id != topic_id)
    )
    return LearningEntrySnapshot(
        learning_return_mode=learning_return_mode,
        learning_dialog_session_id=learning_dialog_session_id,
        learning_topic_id=topic_id,
        clear_current_practice_context=topic_id is None and current_mode == "select_topic" and not has_session,
        mode="learning",
        command_palette_visible=False,
        last_feedback=LEARNING_ENTRY_FEEDBACK,
        should_clear_generated_learning_material=should_clear_generated_learning_material,
        should_ensure_learning_material=should_ensure_learning_material,
    )


def build_learning_request_snapshot(
    *,
    user_message: str,
    current_learning_topic_id: int | None,
    current_learning_dialog_session_id: str | None,
    new_dialog_session_id: str,
) -> LearningRequestSnapshot:
    """State values after submitting a learning question, before async LLM work."""
    return LearningRequestSnapshot(
        learning_topic_id=current_learning_topic_id,
        learning_dialog_session_id=current_learning_dialog_session_id or new_dialog_session_id,
        learning_question=user_message,
        learning_pending_message=user_message,
        learning_dialog_offset=0,
        command_palette_visible=False,
        mode="loading_learning",
        ollama_status="разбирает тему...",
        last_feedback="",
        history_message="Готовлю учебное объяснение через Ollama...",
    )


def build_learning_finish_snapshot(
    *,
    explanation: str,
    learning_question: str,
    last_error: str | None,
) -> LearningFinishSnapshot:
    """State values after a learning reply arrives, before storage side effects."""
    title = f"Учебный разбор\nВопрос: {learning_question}"
    transcript_entries = (
        (("Ты", learning_question), ("ИИ", explanation))
        if learning_question
        else (("ИИ", explanation),)
    )
    return LearningFinishSnapshot(
        ollama_status="fallback" if last_error else "ok",
        history_message=f"Учебный fallback: {last_error}" if last_error else "Учебный разбор готов.",
        transcript_entries=transcript_entries,
        learning_pending_message="",
        learning_dialog_offset=0,
        last_feedback=f"{title}\n\n{explanation}",
        mode="learning",
    )
