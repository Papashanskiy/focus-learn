from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from interview_prep.domain.models import Answer, Question, Topic
from interview_prep.services.system_design_service import DEFAULT_SYSTEM_DESIGN_SCENARIO


SYSTEM_DESIGN_MODES = frozenset(
    {
        "system_design",
        "loading_system_design",
        "loading_system_design_checkpoint",
        "loading_system_design_pressure",
        "loading_system_design_feedback",
    }
)

SYSTEM_DESIGN_ENTRY_FEEDBACK = (
    "System Design Mock Interview.\n"
    "Ты проектируешь сервис end-to-end, ИИ играет интервьюера.\n"
    "Пиши следующий шаг решения в composer. /sd-checkpoint даст короткую проверку, "
    "/sd-pressure даст pressure follow-up, /sd-feedback даст итоговую оценку, "
    "/practice вернет к вопросам."
)


@dataclass(frozen=True)
class SystemDesignEntrySnapshot:
    system_design_return_mode: str
    system_design_saved_topic: Topic | None
    system_design_saved_question: Question | None
    system_design_saved_answer: Answer | None
    system_design_saved_pending_answer: str | None
    system_design_saved_showing_hint: bool
    system_design_saved_showing_reference: bool
    system_design_scenario: str
    system_design_scenario_id: int | None
    system_design_transcript: tuple[tuple[str, str], ...]
    should_reset_artifacts: bool
    showing_hint: bool
    showing_reference: bool
    mode: Literal["system_design"]
    last_feedback: str


def build_system_design_entry_snapshot(
    *,
    current_mode: str,
    current_topic: Topic | None,
    current_question: Question | None,
    current_answer: Answer | None,
    current_pending_answer: str | None,
    current_showing_hint: bool,
    current_showing_reference: bool,
    current_system_design_return_mode: str,
    current_system_design_saved_topic: Topic | None,
    current_system_design_saved_question: Question | None,
    current_system_design_saved_answer: Answer | None,
    current_system_design_saved_pending_answer: str | None,
    current_system_design_saved_showing_hint: bool,
    current_system_design_saved_showing_reference: bool,
    current_system_design_scenario: str,
    current_system_design_scenario_id: int | None,
    current_system_design_transcript: list[tuple[str, str]] | tuple[tuple[str, str], ...],
    scenario: str,
    scenario_id: int | None,
) -> SystemDesignEntrySnapshot:
    """State values for entering system design mode before storage/background side effects."""
    already_system_design = current_mode in SYSTEM_DESIGN_MODES
    system_design_return_mode = (
        current_system_design_return_mode if already_system_design else current_mode
    )
    saved_topic = current_system_design_saved_topic if already_system_design else current_topic
    saved_question = current_system_design_saved_question if already_system_design else current_question
    saved_answer = current_system_design_saved_answer if already_system_design else current_answer
    saved_pending_answer = (
        current_system_design_saved_pending_answer if already_system_design else current_pending_answer
    )
    saved_showing_hint = (
        current_system_design_saved_showing_hint if already_system_design else current_showing_hint
    )
    saved_showing_reference = (
        current_system_design_saved_showing_reference
        if already_system_design
        else current_showing_reference
    )

    should_reset_artifacts = bool(scenario)
    if scenario:
        next_scenario = scenario
        next_scenario_id = scenario_id
        transcript: tuple[tuple[str, str], ...] = ()
    elif current_system_design_transcript:
        next_scenario = current_system_design_scenario
        next_scenario_id = current_system_design_scenario_id
        transcript = tuple(current_system_design_transcript)
    else:
        next_scenario = DEFAULT_SYSTEM_DESIGN_SCENARIO
        next_scenario_id = None
        transcript = ()

    return SystemDesignEntrySnapshot(
        system_design_return_mode=system_design_return_mode,
        system_design_saved_topic=saved_topic,
        system_design_saved_question=saved_question,
        system_design_saved_answer=saved_answer,
        system_design_saved_pending_answer=saved_pending_answer,
        system_design_saved_showing_hint=saved_showing_hint,
        system_design_saved_showing_reference=saved_showing_reference,
        system_design_scenario=next_scenario,
        system_design_scenario_id=next_scenario_id,
        system_design_transcript=transcript,
        should_reset_artifacts=should_reset_artifacts,
        showing_hint=False,
        showing_reference=False,
        mode="system_design",
        last_feedback=SYSTEM_DESIGN_ENTRY_FEEDBACK,
    )
