from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Callable, Literal
from uuid import uuid4

from rich.markup import escape
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.widgets import Button, Footer, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from interview_prep.domain.models import (
    Answer,
    AnswerEvaluation,
    ContentGenerationJob,
    LearningMaterial,
    ManualNote,
    NotebookEntry,
    QUESTION_SOURCE_QUALITY_ACCEPTED,
    QUESTION_SOURCE_QUALITY_ARCHIVED,
    QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
    Question,
    QuestionAutoCurationAudit,
    Session,
    SystemDesignArtifact,
    SystemDesignFeedbackArtifact,
    SystemDesignScenario,
    Topic,
)
from interview_prep.domain.rules import DEFAULT_SESSION_MINUTES
from interview_prep.infra.config import DEFAULT_CONFIG_PATH
from interview_prep.infra.database import DEFAULT_DB_PATH
from interview_prep.services.app_factory import AppServices
from interview_prep.services.content_generation_service import (
    JOB_KIND_CURRICULUM,
    JOB_KIND_LEARNING_MATERIAL,
    JOB_KIND_REFERENCE_ANSWER,
    JOB_KIND_SYSTEM_DESIGN_SCENARIO,
)
from interview_prep.services.curriculum_service import TopicRecommendation
from interview_prep.services.question_quality_rules import generated_question_quality_flags
from interview_prep.services.session_service import FeedbackQuality
from interview_prep.services.system_design_service import DEFAULT_SYSTEM_DESIGN_SCENARIO
from interview_prep.ui.content_worker_controller import ContentWorkerOrchestrator
from interview_prep.ui.learning_controller import (
    LearningEntrySnapshot,
    LearningFinishSnapshot,
    LearningRequestSnapshot,
    build_learning_finish_snapshot,
    build_learning_entry_snapshot,
    build_learning_request_snapshot,
)
from interview_prep.ui.practice_controller import (
    PracticeAnsweredSnapshot,
    PracticeAnswerScoringSnapshot,
    PracticeNextQuestionSnapshot,
    PracticeSessionResetSnapshot,
    PracticeSessionStartSnapshot,
    PracticeSubmitDecision,
    build_practice_answer_scoring_snapshot,
    build_practice_answered_snapshot,
    build_practice_next_question_snapshot,
    build_practice_session_reset_snapshot,
    build_practice_session_start_snapshot,
    decide_practice_submit,
    parse_practice_self_score,
)
from interview_prep.ui.system_design_controller import (
    SystemDesignAuxiliaryFinishSnapshot,
    SystemDesignEntrySnapshot,
    SystemDesignFeedbackFinishSnapshot,
    SystemDesignFinishTurnSnapshot,
    SystemDesignLoadingSnapshot,
    SystemDesignRequestSnapshot,
    build_system_design_checkpoint_finish_snapshot,
    build_system_design_checkpoint_loading_snapshot,
    build_system_design_entry_snapshot,
    build_system_design_feedback_finish_snapshot,
    build_system_design_feedback_loading_snapshot,
    build_system_design_finish_turn_snapshot,
    build_system_design_pressure_finish_snapshot,
    build_system_design_pressure_loading_snapshot,
    build_system_design_request_snapshot,
)
from interview_prep.ui.tui_render import (
    NOTES_DRAFT_CONTEXT_TYPE,
    NOTES_DRAFT_TITLE,
    SAVED_NOTE_CONTEXT_TYPE,
    SYSTEM_DESIGN_ARTIFACT_LABELS,
    SYSTEM_DESIGN_FEEDBACK_REQUIRED_SECTIONS,
    answer_evaluation_drill_lines,
    answer_evaluation_gap_lines,
    artifact_version_text,
    command_palette_text,
    content_artifact_id_label,
    content_job_retry_text,
    extract_feedback_gap_section,
    extract_system_design_artifact_commands,
    feedback_gap_notebook_body,
    format_answer_evaluation,
    format_duration,
    format_feedback_quality_warning,
    format_question_competencies,
    format_question_tags,
    format_session_outcome,
    format_system_design_evaluation,
    is_feedback_gap_heading,
    is_feedback_section_heading,
    notes_line_count,
    one_line_preview,
    parse_content_payload,
    parse_content_result,
    readiness_next_action_for_aggregate,
    render_chat_message,
    render_llm_markdown,
    system_design_evaluation_score_label,
)


Mode = Literal[
    "select_topic",
    "answering",
    "scoring",
    "answered",
    "learning",
    "system_design",
    "loading_feedback",
    "loading_learning",
    "loading_system_design",
    "loading_system_design_checkpoint",
    "loading_system_design_pressure",
    "loading_system_design_feedback",
    "artifacts",
    "content",
    "questions_review",
    "auto_curation_audit",
    "history",
    "notebook",
    "readiness",
    "session_finished",
    "ended",
]

class Composer(TextArea):
    """Multiline message composer with the old input-bar submit contract."""

    BINDINGS = [*TextArea.BINDINGS, Binding("enter", "submit", "Submit", show=False)]
    MIN_HEIGHT = 5
    MAX_HEIGHT = 12

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    @property
    def value(self) -> str:
        return self.text

    @value.setter
    def value(self, text: str) -> None:
        self.text = text
        self.adjust_height()

    def _on_key(self, event: events.Key) -> None:
        if event.key == "shift+enter":
            event.prevent_default()
            event.stop()
            start, end = self.selection
            self._replace_via_keyboard("\n", start, end)
            self.adjust_height()
            return
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            self.action_submit()
            return
        super()._on_key(event)

    def on_mount(self) -> None:
        self.adjust_height()

    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        self.adjust_height()

    def adjust_height(self) -> None:
        visible_lines = max(1, self.text.count("\n") + 1)
        self.styles.height = min(
            self.MAX_HEIGHT,
            max(self.MIN_HEIGHT, visible_lines + 2),
        )

    def action_submit(self) -> None:
        self.post_message(self.Submitted(self.text))


class InterviewPrepTUI(App[None]):
    CSS = """
    Screen {
        background: #101418;
        color: #eef2f6;
    }

    #topbar {
        height: 3;
        padding: 0 1;
        background: #17202a;
        border-bottom: solid #2f4052;
    }

    #mode_actions {
        height: 3;
        padding: 0 1;
        background: #121a22;
        border-bottom: solid #2f4052;
    }

    #today_actions {
        height: 3;
        padding: 0 1;
        background: #14202a;
        border-bottom: solid #2f4052;
    }

    .mode_action {
        margin: 0 1 0 0;
        min-width: 16;
    }

    .today_action {
        margin: 0 1 0 0;
        min-width: 18;
    }

    #workspace {
        height: 1fr;
    }

    #left_panel {
        width: 26%;
        min-width: 26;
        border-right: solid #2f4052;
        padding: 1;
    }

    #center_panel {
        width: 1fr;
        padding: 1 2;
    }

    #right_panel {
        width: 30%;
        min-width: 30;
        border-left: solid #2f4052;
    }

    #history_scroll {
        height: 2fr;
        padding: 1;
    }

    #notes_editor {
        height: 10;
        border-top: solid #2f4052;
        padding: 0 1;
    }

    #input_bar {
        height: 5;
        border-top: solid #2f4052;
        padding: 0 1;
    }

    Static {
        height: auto;
    }
    """

    BINDINGS = [
        ("ctrl+q", "request_quit", "Quit"),
        ("ctrl+s", "show_stats", "Stats"),
        ("ctrl+h", "show_hint", "Hint"),
        ("ctrl+a", "show_answer", "Answer"),
        ("ctrl+p", "show_commands", "Commands"),
        ("ctrl+n", "focus_notes", "Notes"),
        ("escape", "focus_input", "Input"),
    ]

    def __init__(
        self,
        db_path: str = str(DEFAULT_DB_PATH),
        config_path: str = str(DEFAULT_CONFIG_PATH),
    ):
        super().__init__()
        self.db_path = db_path
        self.config_path = config_path
        self.services = AppServices(db_path, config_path)
        self.mode: Mode = "select_topic"
        self.session: Session | None = None
        self.topic: Topic | None = None
        self.question: Question | None = None
        self.current_answer: Answer | None = None
        self.pending_answer_text: str | None = None
        self.started_at: datetime | None = None
        self.baseline_session_id: int | None = None
        self.baseline_question_ids: tuple[int, ...] = ()
        self.mock_interview_session_id: int | None = None
        self.mock_interview_question_ids: tuple[int, ...] = ()
        self.mock_interview_sections: tuple[str, ...] = ()
        self.answered_count = 0
        self.skipped_count = 0
        self.last_feedback = ""
        self.history: list[str] = []
        self.skipped_question_ids: set[int] = set()
        self.showing_hint = False
        self.showing_reference = False
        self.ollama_status = "не проверялась"
        self.content_worker = ContentWorkerOrchestrator()
        self.content_status = "idle"
        self.content_worker_running = False
        self.content_worker_paused = False
        self.learning_return_mode: Mode = "answering"
        self.learning_question = ""
        self.learning_pending_message = ""
        self.learning_topic_id: int | None = None
        self.learning_dialog_session_id: str | None = None
        self.learning_transcript: list[tuple[str, str]] = []
        self.learning_dialog_window_size = 10
        self.learning_dialog_offset = 0
        self.generated_learning_material: str | None = None
        self.generated_learning_material_topic_id: int | None = None
        self.command_palette_visible = False
        self.artifacts_return_mode: Mode = "answering"
        self.content_return_mode: Mode = "answering"
        self.questions_review_return_mode: Mode = "answering"
        self.auto_curation_audit_return_mode: Mode = "answering"
        self.auto_curation_audit_question_filter: int | None = None
        self.auto_curation_audit_topic_filter: int | None = None
        self.auto_curation_audit_status_filter: str | None = None
        self.history_return_mode: Mode = "answering"
        self.notebook_return_mode: Mode = "answering"
        self.readiness_return_mode: Mode = "answering"
        self.history_browser_view: Literal["practice", "learning", "system_design"] = "practice"
        self.history_selected_session_id: int | None = None
        self.history_selected_learning_topic_id: int | None = None
        self.history_selected_learning_date: str | None = None
        self.history_selected_learning_dialog_session_id: str | None = None
        self.history_selected_system_design_feedback_id: int | None = None
        self.notebook_topic_filter: int | None = None
        self.notebook_subtopic_filter: int | None = None
        self.notebook_competency_filter: str | None = None
        self.notebook_selected_entry_id: int | None = None
        self.materials_learning_filter: Literal["current", "all"] = "current"
        self.materials_scenario_filter: Literal["current", "all"] = "current"
        self.materials_preview: str | None = None
        self.system_design_return_mode: Mode = "answering"
        self.system_design_scenario = DEFAULT_SYSTEM_DESIGN_SCENARIO
        self.system_design_scenario_id: int | None = None
        self.system_design_transcript: list[tuple[str, str]] = []
        self.system_design_pending_message = ""
        self.generated_system_design_scenario: str | None = None
        self.generated_system_design_scenario_topic_id: int | None = None
        self.generated_system_design_focus_areas: list[str] = []
        self.system_design_artifacts: dict[str, list[str]] = {
            "requirements": [],
            "api": [],
            "data_model": [],
            "decisions": [],
            "risks": [],
        }
        self.system_design_saved_topic: Topic | None = None
        self.system_design_saved_question: Question | None = None
        self.system_design_saved_answer: Answer | None = None
        self.system_design_saved_pending_answer: str | None = None
        self.system_design_saved_showing_hint = False
        self.system_design_saved_showing_reference = False
        self._active_notes_context_key: tuple[int | None, int | None, str, str] | None = None
        self._last_saved_notes_signature: tuple[tuple[int | None, int | None, str, str], str] | None = None
        self._notes_editor_widget: TextArea | None = None
        self._notes_editor_text_cache = ""

    @property
    def content_status(self) -> str:
        return self.content_worker.status

    @content_status.setter
    def content_status(self, value: str) -> None:
        self.content_worker.status = value

    @property
    def content_worker_running(self) -> bool:
        return self.content_worker.running

    @content_worker_running.setter
    def content_worker_running(self, value: bool) -> None:
        self.content_worker.running = value

    @property
    def content_worker_paused(self) -> bool:
        return self.content_worker.paused

    @content_worker_paused.setter
    def content_worker_paused(self, value: bool) -> None:
        self.content_worker.paused = value

    def dispatch_from_worker_thread(self, callback: Callable[..., None], *args: object) -> None:
        """Queue a UI callback from a background thread without waiting on the app loop."""
        try:
            self.call_later(callback, *args)
        except RuntimeError:
            return

    def compose(self) -> ComposeResult:
        yield Static("", id="topbar")
        with Horizontal(id="mode_actions"):
            yield Button("Practice", id="action-practice", classes="mode_action")
            yield Button("Learn", id="action-learn", classes="mode_action")
            yield Button("System Design", id="action-system-design", classes="mode_action")
            yield Button("Конспект обучения", id="action-notebook", classes="mode_action")
        with Horizontal(id="today_actions"):
            yield Button("Start Drill", id="today-start-drill", classes="today_action")
            yield Button("Review Weak Answer", id="today-review-weak-answer", classes="today_action")
            yield Button("Mock Senior Interview", id="today-system-design", classes="today_action")
            yield Button("Open Readiness", id="today-open-readiness", classes="today_action")
            yield Button("Notebook", id="today-notebook", classes="today_action")
        with Horizontal(id="workspace"):
            with VerticalScroll(id="left_panel"):
                yield OptionList(id="topics")
            with VerticalScroll(id="center_panel"):
                yield Static("", id="question")
            with Vertical(id="right_panel"):
                with VerticalScroll(id="history_scroll"):
                    yield Static("", id="history")
                yield TextArea(
                    "",
                    id="notes_editor",
                    show_line_numbers=False,
                    soft_wrap=True,
                    tab_behavior="focus",
                    placeholder="Заметки по сессии. Ctrl+N - фокус сюда, Esc - назад к input.",
                )
        yield Composer(
            "",
            id="input_bar",
            show_line_numbers=False,
            soft_wrap=True,
            tab_behavior="focus",
            placeholder="Enter - Start Drill, ID темы - ручной выбор",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1, self.refresh_topbar)
        self._notes_editor_widget = self.query_one("#notes_editor", TextArea)
        self.render_all()
        self.query_one("#input_bar", Composer).focus()

    def on_unmount(self) -> None:
        self.content_worker.mark_unmounted()
        self.persist_notes_draft()
        self.finish_session_if_needed()
        self.services.close()

    def action_request_quit(self) -> None:
        self.end_session()

    def action_show_stats(self) -> None:
        self.show_stats()

    def action_show_hint(self) -> None:
        self.show_hint()

    def action_show_answer(self) -> None:
        self.show_reference()

    def action_show_commands(self) -> None:
        self.show_commands()

    def action_focus_notes(self) -> None:
        self.focus_notes()

    def action_focus_input(self) -> None:
        self.focus_input()

    def on_composer_submitted(self, event: Composer.Submitted) -> None:
        raw = event.value.strip()
        self.query_one("#input_bar", Composer).value = ""
        if self.mode == "ended":
            self.exit()
            return
        if raw.startswith("/"):
            self.handle_command(raw)
            return
        practice_submit = decide_practice_submit(self.mode, raw)
        if practice_submit is not None:
            self.apply_practice_submit_decision(practice_submit)
            return
        if self.mode == "artifacts":
            self.add_history(
                "Выбери команду: /preview-material <id|latest>, /preview-scenario <id|latest>, "
                "/material <id|latest>, /scenario <id|latest>, /archive-material <id> confirm [reason], "
                "/archive-scenario <id> confirm [reason], /notebook topic <id>, /regen-material, "
                "/regen-scenario или /practice."
            )
            self.render_all()
            return
        if self.mode == "content":
            self.add_history(
                "Экран content принимает slash commands: /pause-content, /resume-content, "
                "/retry-job <id> или /practice."
            )
            self.render_all()
            return
        if self.mode == "questions_review":
            self.add_history(
                "Questions audit queue. Auto-curation is primary; "
                "/questions-review accept <id> and archive <id> are manual audit overrides."
            )
            self.render_all()
            return
        if self.mode == "auto_curation_audit":
            self.add_history(
                "Auto-curation audit read-only. Используй /curation-audit topic <id>, "
                "/curation-audit status <status>, /curation-audit question <id> или /practice."
            )
            self.render_all()
            return
        if self.mode == "history":
            if raw.isdigit():
                if self.history_browser_view == "learning":
                    self.add_history("Используй /history learning <session-id> для открытия learning dialog.")
                    self.render_all()
                elif self.history_browser_view == "system_design":
                    self.open_system_design_history_feedback(raw)
                else:
                    self.open_history_session(raw)
                return
            self.add_history(
                "History browser read-only. Используй /history <session-id>, "
                "/history learning <session-id>, /history system-design <feedback-id> или /practice."
            )
            self.render_all()
            return
        if self.mode == "notebook":
            self.add_history(
                "Конспект обучения read-only. Используй /notebook topic <id>, /notebook subtopic <id>, "
                "/notebook competency <slug>, /notebook entry <id>, /notebook all или /practice."
            )
            self.render_all()
            return
        if self.mode == "readiness":
            self.add_history("Readiness dashboard read-only. Используй /mock-interview, /readiness, /practice или /stats.")
            self.render_all()
            return
        if self.mode in {
            "loading_feedback",
            "loading_learning",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            self.add_history("ИИ еще отвечает. Подожди или используй /quit.")
            self.render_all()
            return
        if self.mode == "learning":
            if not raw:
                self.add_history("Напиши учебный вопрос или /practice для возврата к сессии.")
                self.render_all()
                return
            self.request_learning(raw)
            return
        if self.mode == "system_design":
            if not raw:
                self.add_history(
                    "Напиши ответ интервьюеру или используй /sd-checkpoint, /sd-pressure, "
                    "/sd-feedback, /practice, /quit."
                )
                self.render_all()
                return
            self.request_system_design_turn(raw)
            return
        if not raw:
            self.add_history("Пустой ввод. Напиши ответ или slash command.")
            self.render_all()
            return
        self.capture_answer(raw)

    def apply_practice_submit_decision(self, decision: PracticeSubmitDecision) -> None:
        if decision.action == "start_today_drill":
            self.activate_today_start_drill_action()
            return
        if decision.action == "start_topic_session":
            self.start_session_from_input(decision.value)
            return
        if decision.action == "capture_score":
            self.capture_score(decision.value)
            return
        if decision.action == "next_question":
            self.load_next_question()
            return
        if decision.action == "empty_answer":
            self.add_history("Пустой ввод. Напиши ответ или slash command.")
            self.render_all()
            return
        if decision.action == "capture_answer":
            self.capture_answer(decision.value)
            return
        raise ValueError(f"Unknown practice submit action: {decision.action}")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "topics":
            return
        option_id = event.option.id or ""
        if not option_id.startswith("topic-"):
            return
        if self.mode != "select_topic":
            self.add_history("Выбор темы кликом доступен на стартовом экране practice.")
            self.render_all()
            return
        self.start_session_from_input(option_id.removeprefix("topic-"))
        self.focus_input()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.persist_notes_draft()
        button_id = event.button.id or ""
        if button_id == "action-practice":
            self.activate_practice_action()
        elif button_id == "action-learn":
            self.activate_learning_action()
        elif button_id == "action-system-design":
            self.activate_system_design_action()
        elif button_id == "action-notebook":
            self.activate_notebook_action()
        elif button_id == "today-start-drill":
            self.activate_today_start_drill_action()
        elif button_id == "today-review-weak-answer":
            self.activate_today_review_weak_answer_action()
        elif button_id == "today-system-design":
            self.start_mock_senior_interview()
        elif button_id == "today-open-readiness":
            self.activate_readiness_action()
        elif button_id == "today-notebook":
            self.activate_notebook_action()
        self.focus_input()

    def mode_switch_is_waiting_for_ai(self) -> bool:
        return self.mode in {
            "loading_feedback",
            "loading_learning",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }

    def block_mode_switch_while_loading(self) -> bool:
        if not self.mode_switch_is_waiting_for_ai():
            return False
        self.add_history("ИИ еще отвечает. Дождись ответа перед сменой режима.")
        self.render_all()
        return True

    def exit_other_focused_modes(self, target_modes: set[Mode]) -> None:
        seen: set[Mode] = set()
        while self.is_focused_mode() and self.mode not in target_modes and self.mode not in seen:
            seen.add(self.mode)
            self.exit_special_mode()

    def activate_learning_action(self, initial_question: str = "") -> None:
        if self.block_mode_switch_while_loading():
            return
        self.exit_other_focused_modes({"learning"})
        self.enter_learning(initial_question)

    def activate_system_design_action(self, scenario: str = "", scenario_id: int | None = None) -> None:
        if self.block_mode_switch_while_loading():
            return
        self.exit_other_focused_modes({"system_design"})
        self.enter_system_design(scenario, scenario_id=scenario_id)

    def activate_notebook_action(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        topic_id = self.current_topic_id()
        selection = f"topic {topic_id}" if topic_id is not None else "all"
        self.enter_notebook(selection)

    def activate_readiness_action(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        self.enter_readiness()

    def activate_practice_action(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        if self.mode == "session_finished":
            self.prepare_new_practice_session()
            return
        if self.mode in {
            "content",
            "questions_review",
            "artifacts",
            "history",
            "notebook",
            "readiness",
            "learning",
            "system_design",
        }:
            self.exit_other_focused_modes(set())
            return
        if self.mode == "select_topic":
            self.start_session_from_input("")
            return
        self.add_history("Practice уже открыт.")
        self.render_all()

    def activate_today_start_drill_action(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        repeat_status = self.baseline_repeat_due_status()
        if repeat_status is not None:
            self.start_baseline_session()
            return
        empty_state_action = self.today_empty_state_action()
        if empty_state_action == "generate_curriculum":
            self.generate_curriculum_command()
            return
        if empty_state_action == "baseline_session":
            self.start_baseline_session()
            return
        drill = self.today_recommended_drill()
        if drill is not None:
            reasons = getattr(drill, "reasons", [])
            if "нет system design практики" in reasons:
                self.start_mock_senior_interview()
                return
            if "нет связанных вопросов" in reasons:
                self.generate_curriculum_command()
                return
        self.activate_practice_action()

    def activate_today_review_weak_answer_action(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        drill = self.today_recommended_drill()
        reasons = getattr(drill, "reasons", []) if drill is not None else []
        if any(reason.startswith("низкая rubric оценка:") for reason in reasons):
            topic_id = self.today_topic_id_for_competency(getattr(drill.competency, "slug", ""))
            if topic_id is not None:
                self.start_session_from_input(str(topic_id))
                return
            self.activate_practice_action()
            return
        self.add_history("Слабый answer-drill не найден; открыт readiness dashboard с текущими gaps.")
        self.enter_readiness()

    def today_recommended_drill(self):
        try:
            return self.services.readiness.snapshot().overall_summary.recommended_drill
        except Exception:
            return None

    def today_topic_id_for_competency(self, competency_slug: str) -> int | None:
        if not competency_slug:
            return None
        try:
            topic_ids = self.services.repository.list_topic_ids_for_competency(competency_slug)
        except Exception:
            return None
        if not topic_ids:
            return None
        topic_id_set = set(topic_ids)
        try:
            weak_topics = self.services.stats.weak_topics(limit=len(topic_ids))
        except Exception:
            weak_topics = []
        for weak_topic in weak_topics:
            topic_id = weak_topic.topic.id
            if topic_id in topic_id_set:
                return topic_id
        return topic_ids[0]

    def return_to_practice_command(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        if self.mode == "session_finished":
            self.prepare_new_practice_session()
            return
        if self.is_focused_mode():
            self.exit_other_focused_modes(set())
            return
        self.exit_special_mode()

    def handle_command(self, command: str) -> None:
        self.persist_notes_draft()
        if command == "/hint":
            self.show_hint()
        elif command == "/answer":
            self.show_reference()
        elif command == "/feedback":
            self.request_feedback()
        elif command == "/recheck-feedback":
            self.request_feedback(recheck=True)
        elif command == "/skip":
            self.skip_question()
        elif command == "/stats":
            self.show_stats()
        elif command in {"/commands", "/help"}:
            self.show_commands()
        elif command == "/accept-topic":
            self.accept_suggested_topic()
        elif command == "/notes":
            self.focus_notes()
        elif command == "/save-note" or command.startswith(("/save-note ", "/save-note\n")):
            self.save_composer_note(command)
        elif command == "/note-from-answer":
            self.save_feedback_gap_to_notebook()
        elif command == "/content":
            self.enter_content()
        elif command == "/generate-curriculum":
            self.generate_curriculum_command()
        elif command == "/questions-review":
            self.enter_questions_review()
        elif command.startswith("/questions-review "):
            self.questions_review_command(command.removeprefix("/questions-review").strip())
        elif command == "/curation-audit":
            self.enter_auto_curation_audit()
        elif command.startswith("/curation-audit "):
            self.enter_auto_curation_audit(command.removeprefix("/curation-audit").strip())
        elif command == "/questions-source audit":
            self.enter_auto_curation_audit()
        elif command.startswith("/questions-source audit "):
            self.enter_auto_curation_audit(command.removeprefix("/questions-source audit").strip())
        elif command == "/history":
            self.enter_history()
        elif command.startswith("/history "):
            self.enter_history(command.removeprefix("/history").strip())
        elif command == "/notebook":
            self.enter_notebook()
        elif command.startswith("/notebook "):
            self.enter_notebook(command.removeprefix("/notebook").strip())
        elif command == "/readiness":
            self.enter_readiness()
        elif command == "/baseline-repeat":
            self.start_due_baseline_repeat()
        elif command == "/mock-interview":
            self.start_mock_senior_interview()
        elif command == "/pause-content":
            self.pause_content_worker()
        elif command == "/resume-content":
            self.resume_content_worker()
        elif command == "/retry-job":
            self.retry_content_job("")
        elif command.startswith("/retry-job "):
            self.retry_content_job(command.removeprefix("/retry-job").strip())
        elif command == "/materials":
            self.enter_artifacts()
        elif command.startswith("/materials "):
            self.enter_artifacts(command.removeprefix("/materials").strip())
        elif command.startswith("/material "):
            self.use_learning_material(command.removeprefix("/material").strip())
        elif command.startswith("/preview-material "):
            self.preview_learning_material(command.removeprefix("/preview-material").strip())
        elif command.startswith("/archive-material "):
            self.archive_learning_material(command.removeprefix("/archive-material").strip())
        elif command.startswith("/archive-scenario "):
            self.archive_system_design_scenario(command.removeprefix("/archive-scenario").strip())
        elif command.startswith("/scenario "):
            self.use_system_design_scenario(command.removeprefix("/scenario").strip())
        elif command.startswith("/preview-scenario "):
            self.preview_system_design_scenario(command.removeprefix("/preview-scenario").strip())
        elif command == "/regen-material":
            self.regenerate_learning_material()
        elif command == "/regen-scenario":
            self.regenerate_system_design_scenario()
        elif command == "/learn-older":
            self.show_older_learning_messages()
        elif command == "/learn-newer":
            self.show_newer_learning_messages()
        elif command.startswith("/learn"):
            self.activate_learning_action(command.removeprefix("/learn").strip())
        elif command.startswith("/system-design"):
            self.activate_system_design_action(command.removeprefix("/system-design").strip())
        elif command.startswith("/sd "):
            self.activate_system_design_action(command.removeprefix("/sd").strip())
        elif command == "/sd":
            self.activate_system_design_action()
        elif command == "/sd-feedback":
            self.request_system_design_feedback()
        elif command == "/sd-checkpoint":
            self.request_system_design_checkpoint()
        elif command == "/sd-pressure":
            self.request_system_design_pressure()
        elif command.startswith("/req "):
            self.add_system_design_artifact("requirements", command.removeprefix("/req").strip())
        elif command.startswith("/requirement "):
            self.add_system_design_artifact("requirements", command.removeprefix("/requirement").strip())
        elif command.startswith("/api "):
            self.add_system_design_artifact("api", command.removeprefix("/api").strip())
        elif command.startswith("/data "):
            self.add_system_design_artifact("data_model", command.removeprefix("/data").strip())
        elif command.startswith("/decision "):
            self.add_system_design_artifact("decisions", command.removeprefix("/decision").strip())
        elif command.startswith("/risk "):
            self.add_system_design_artifact("risks", command.removeprefix("/risk").strip())
        elif command == "/practice":
            self.return_to_practice_command()
        elif command == "/finish-session":
            self.finish_session_command()
        elif command == "/quit":
            self.end_session()
        elif command == "/next":
            self.load_next_question()
        else:
            self.add_history(f"Неизвестная команда: {command}")
            self.render_all()

    def enter_history(self, selection: str = "") -> None:
        if self.mode != "history":
            self.history_return_mode = self.mode
        self.mode = "history"
        self.command_palette_visible = False
        cleaned_selection = selection.strip()
        self.last_feedback = "Read-only history browser."
        if cleaned_selection.startswith(("system-design", "system_design", "sd")):
            self.history_browser_view = "system_design"
            self.history_selected_session_id = None
            self.history_selected_learning_topic_id = None
            self.history_selected_learning_date = None
            self.history_selected_learning_dialog_session_id = None
            remainder = self.system_design_history_selection(cleaned_selection)
            if not remainder:
                self.history_selected_system_design_feedback_id = None
                self.add_history("Открыт history browser: system design feedback.")
            else:
                self.open_system_design_history_feedback(remainder, render=False)
        elif cleaned_selection.startswith("learning"):
            self.history_browser_view = "learning"
            self.history_selected_session_id = None
            self.history_selected_system_design_feedback_id = None
            if cleaned_selection == "learning":
                self.history_selected_learning_topic_id = None
                self.history_selected_learning_date = None
                self.history_selected_learning_dialog_session_id = None
                self.add_history("Открыт history browser: learning dialogs.")
            else:
                self.open_learning_history_group(cleaned_selection.removeprefix("learning").strip(), render=False)
        elif cleaned_selection:
            self.history_browser_view = "practice"
            self.history_selected_system_design_feedback_id = None
            self.history_selected_learning_topic_id = None
            self.history_selected_learning_date = None
            self.history_selected_learning_dialog_session_id = None
            self.open_history_session(selection, render=False)
        else:
            self.history_browser_view = "practice"
            self.history_selected_session_id = None
            self.history_selected_system_design_feedback_id = None
            self.history_selected_learning_topic_id = None
            self.history_selected_learning_date = None
            self.history_selected_learning_dialog_session_id = None
            self.add_history("Открыт history browser.")
        self.render_all()

    def exit_history(self) -> None:
        if self.mode != "history":
            return
        self.mode = self.history_return_mode if self.history_return_mode != "history" else "answering"
        if self.mode == "select_topic" and self.session is not None:
            self.mode = "answering"
        self.add_history("Возврат из history browser.")
        self.render_all()

    def open_history_session(self, selection: str, render: bool = True) -> None:
        try:
            session_id = int(selection)
        except ValueError:
            self.add_history("Использование: /history <session-id>, /history learning или /history system-design.")
            if render:
                self.render_all()
            return
        detail = self.services.sessions.get_completed_session_detail(session_id)
        if detail is None:
            self.add_history(f"Session #{session_id} не найдена среди завершенных practice sessions.")
            if render:
                self.render_all()
            return
        self.history_selected_session_id = session_id
        self.history_selected_system_design_feedback_id = None
        self.add_history(f"Открыта practice session #{session_id} в read-only режиме.")
        if render:
            self.render_all()

    def system_design_history_selection(self, selection: str) -> str:
        for prefix in ("system-design", "system_design", "sd"):
            if selection == prefix:
                return ""
            if selection.startswith(f"{prefix} "):
                return selection.removeprefix(prefix).strip()
        return selection.strip()

    def open_system_design_history_feedback(self, selection: str, render: bool = True) -> None:
        try:
            feedback_id = int(selection)
        except ValueError:
            self.add_history("Использование: /history system-design <feedback-id>.")
            if render:
                self.render_all()
            return
        feedback = self.services.repository.get_system_design_feedback_artifact(feedback_id)
        if feedback is None:
            self.add_history(f"System design feedback #{feedback_id} не найден.")
            if render:
                self.render_all()
            return
        self.history_selected_session_id = None
        self.history_selected_learning_topic_id = None
        self.history_selected_learning_date = None
        self.history_selected_learning_dialog_session_id = None
        self.history_selected_system_design_feedback_id = feedback_id
        self.add_history(f"Открыт system design feedback #{feedback_id} в read-only режиме.")
        if render:
            self.render_all()

    def open_learning_history_group(self, selection: str, render: bool = True) -> None:
        parts = selection.replace(":", " ").split()
        if len(parts) == 1:
            dialog_session_id = parts[0]
            try:
                messages = self.services.learning.list_dialog_messages_for_session(dialog_session_id)
            except ValueError as exc:
                self.add_history(str(exc))
                if render:
                    self.render_all()
                return
            if not messages:
                self.add_history(f"Learning dialog session {dialog_session_id} не найден.")
                if render:
                    self.render_all()
                return
            self.history_selected_session_id = None
            self.history_selected_system_design_feedback_id = None
            self.history_selected_learning_topic_id = messages[0].topic_id
            self.history_selected_learning_date = messages[0].created_at.date().isoformat()
            self.history_selected_learning_dialog_session_id = dialog_session_id
            self.add_history(f"Открыт learning dialog session {dialog_session_id} в read-only режиме.")
            if render:
                self.render_all()
            return
        if len(parts) != 2:
            self.add_history("Использование: /history learning <session-id> или /history learning <topic-id> <YYYY-MM-DD>.")
            if render:
                self.render_all()
            return
        topic_raw, dialog_date = parts
        try:
            topic_id = int(topic_raw)
        except ValueError:
            self.add_history("Для learning dialog нужен numeric topic id.")
            if render:
                self.render_all()
            return
        try:
            messages = self.services.learning.list_dialog_messages_for_date(topic_id, dialog_date)
        except ValueError as exc:
            self.add_history(str(exc))
            if render:
                self.render_all()
            return
        if not messages:
            self.add_history(f"Learning dialog topic #{topic_id} за {dialog_date} не найден.")
            if render:
                self.render_all()
            return
        self.history_selected_session_id = None
        self.history_selected_system_design_feedback_id = None
        self.history_selected_learning_topic_id = topic_id
        self.history_selected_learning_date = dialog_date
        self.history_selected_learning_dialog_session_id = None
        self.add_history(f"Открыт learning dialog topic #{topic_id} за {dialog_date} в read-only режиме.")
        if render:
            self.render_all()

    def enter_content(self) -> None:
        if self.mode != "content":
            self.content_return_mode = self.mode
        self.mode = "content"
        self.command_palette_visible = False
        self.last_feedback = "Очередь фоновой генерации контента."
        self.add_history("Открыт экран content jobs.")
        self.render_all()

    def exit_content(self) -> None:
        if self.mode != "content":
            return
        self.mode = self.content_return_mode if self.content_return_mode != "content" else "answering"
        if self.mode == "select_topic" and self.session is not None:
            self.mode = "answering"
        self.add_history("Возврат из content jobs.")
        self.render_all()

    def enter_questions_review(self) -> None:
        self.open_questions_review_screen()
        self.add_history("Открыта audit queue для pending generated questions.")
        self.render_all()

    def open_questions_review_screen(self) -> None:
        if self.mode != "questions_review":
            self.questions_review_return_mode = self.mode
        self.mode = "questions_review"
        self.command_palette_visible = False
        self.last_feedback = "Auto-curation is primary; pending generated questions are audit exceptions."

    def exit_questions_review(self) -> None:
        if self.mode != "questions_review":
            return
        self.mode = (
            self.questions_review_return_mode
            if self.questions_review_return_mode != "questions_review"
            else "answering"
        )
        if self.mode == "select_topic" and self.session is not None:
            self.mode = "answering"
        self.add_history("Возврат из questions review.")
        self.render_all()

    def enter_auto_curation_audit(self, selection: str = "") -> None:
        try:
            self.apply_auto_curation_audit_filters(selection)
        except ValueError as exc:
            self.add_history(str(exc))
            self.render_all()
            return
        self.open_auto_curation_audit_screen()
        self.add_history("Открыт auto-curation audit.")
        self.render_all()

    def apply_auto_curation_audit_filters(self, selection: str) -> None:
        args = selection.strip()
        if not args or args in {"list", "all"}:
            self.auto_curation_audit_question_filter = None
            self.auto_curation_audit_topic_filter = None
            self.auto_curation_audit_status_filter = None
            return
        parts = args.split()
        question_id: int | None = None
        topic_id: int | None = None
        status: str | None = None
        index = 0
        while index < len(parts):
            key = parts[index].removeprefix("--")
            if key not in {"question", "topic", "status"} or index + 1 >= len(parts):
                raise ValueError(
                    "Использование: /curation-audit [question <id>] [topic <id>] "
                    "[status accepted|archived|pending_auto_review]."
                )
            value = parts[index + 1]
            if key in {"question", "topic"}:
                try:
                    numeric_value = int(value)
                except ValueError as exc:
                    raise ValueError(f"Auto-curation audit принимает numeric {key} id.") from exc
                if numeric_value < 1:
                    raise ValueError(f"Auto-curation audit принимает positive {key} id.")
                if key == "question":
                    question_id = numeric_value
                else:
                    topic_id = numeric_value
            else:
                if value not in {
                    QUESTION_SOURCE_QUALITY_ACCEPTED,
                    QUESTION_SOURCE_QUALITY_ARCHIVED,
                    QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW,
                }:
                    raise ValueError(
                        "status должен быть accepted, archived или pending_auto_review."
                    )
                status = value
            index += 2
        self.auto_curation_audit_question_filter = question_id
        self.auto_curation_audit_topic_filter = topic_id
        self.auto_curation_audit_status_filter = status

    def open_auto_curation_audit_screen(self) -> None:
        if self.mode != "auto_curation_audit":
            self.auto_curation_audit_return_mode = self.mode
        self.mode = "auto_curation_audit"
        self.command_palette_visible = False
        self.last_feedback = "Read-only audit auto-curation decisions."

    def exit_auto_curation_audit(self) -> None:
        if self.mode != "auto_curation_audit":
            return
        self.mode = (
            self.auto_curation_audit_return_mode
            if self.auto_curation_audit_return_mode != "auto_curation_audit"
            else "answering"
        )
        if self.mode == "select_topic" and self.session is not None:
            self.mode = "answering"
        self.add_history("Возврат из auto-curation audit.")
        self.render_all()

    def enter_notebook(self, selection: str = "") -> None:
        if self.mode != "notebook":
            self.notebook_return_mode = self.mode
        self.mode = "notebook"
        self.command_palette_visible = False
        self.last_feedback = "Конспект обучения: read-only AI explanations."
        cleaned_selection = selection.strip()
        if cleaned_selection:
            self.apply_notebook_selection(cleaned_selection)
        elif self.notebook_selected_entry_id is not None:
            self.notebook_selected_entry_id = None
        elif (
            self.notebook_topic_filter is None
            and self.notebook_subtopic_filter is None
            and self.notebook_competency_filter is None
        ):
            self.notebook_topic_filter = self.current_topic_id()
            self.notebook_selected_entry_id = None
        self.add_history("Открыт конспект обучения.")
        self.render_all()

    def enter_readiness(self) -> None:
        if self.mode != "readiness":
            self.readiness_return_mode = self.mode
        self.mode = "readiness"
        self.command_palette_visible = False
        self.last_feedback = "Readiness dashboard по senior competencies."
        self.add_history("Открыт readiness dashboard.")
        self.render_all()

    def apply_notebook_selection(self, selection: str) -> None:
        parts = selection.split()
        if parts == ["all"]:
            self.notebook_topic_filter = None
            self.notebook_subtopic_filter = None
            self.notebook_competency_filter = None
            self.notebook_selected_entry_id = None
            return
        if len(parts) == 1 and parts[0].isdigit():
            parts = ["entry", parts[0]]
        if len(parts) != 2 or parts[0] not in {"topic", "subtopic", "entry", "competency"}:
            self.add_history(
                "Использование: /notebook, /notebook all, /notebook topic <id>, "
                "/notebook subtopic <id>, /notebook competency <slug> или /notebook entry <id>."
            )
            return
        if parts[0] == "competency":
            competency_slug = parts[1].strip()
            competency = self.services.repository.find_competency_by_slug(competency_slug)
            if competency is None:
                self.add_history(f"Competency {competency_slug!r} не найдена.")
                return
            self.notebook_topic_filter = None
            self.notebook_subtopic_filter = None
            self.notebook_competency_filter = competency.slug
            self.notebook_selected_entry_id = None
            return
        try:
            selected_id = int(parts[1])
        except ValueError:
            self.add_history("/notebook принимает numeric id.")
            return
        if parts[0] == "topic":
            if self.services.repository.get_topic(selected_id) is None:
                self.add_history(f"Topic #{selected_id} не найден.")
                return
            self.notebook_topic_filter = selected_id
            self.notebook_subtopic_filter = None
            self.notebook_competency_filter = None
            self.notebook_selected_entry_id = None
            return
        if parts[0] == "subtopic":
            if self.services.repository.get_curriculum_subtopic(selected_id) is None:
                self.add_history(f"Curriculum subtopic #{selected_id} не найден.")
                return
            self.notebook_topic_filter = None
            self.notebook_subtopic_filter = selected_id
            self.notebook_competency_filter = None
            self.notebook_selected_entry_id = None
            return
        entry = self.find_notebook_entry(selected_id)
        if entry is None:
            self.add_history(f"Запись конспекта #{selected_id} не найдена.")
            return
        self.notebook_topic_filter = entry.topic_id
        self.notebook_subtopic_filter = entry.curriculum_subtopic_id
        self.notebook_competency_filter = None
        self.notebook_selected_entry_id = selected_id

    def exit_notebook(self) -> None:
        if self.mode != "notebook":
            return
        self.mode = self.notebook_return_mode if self.notebook_return_mode != "notebook" else "answering"
        if self.mode == "select_topic" and self.session is not None:
            self.mode = "answering"
        self.add_history("Возврат из конспекта обучения.")
        self.render_all()

    def exit_readiness(self) -> None:
        if self.mode != "readiness":
            return
        self.mode = self.readiness_return_mode if self.readiness_return_mode != "readiness" else "answering"
        if self.mode == "select_topic" and self.session is not None:
            self.mode = "answering"
        self.add_history("Возврат из readiness dashboard.")
        self.render_all()

    def retry_content_job(self, raw_id: str) -> None:
        try:
            job_id = int(raw_id.strip())
        except ValueError:
            self.add_history("Использование: /retry-job <failed-job-id>.")
            self.render_all()
            return
        job = self.services.repository.get_content_generation_job(job_id)
        if job is None:
            self.add_history(f"Content job #{job_id} не найден.")
            self.render_all()
            return
        if job.status != "failed":
            self.add_history(f"/retry-job работает только с failed jobs. Job #{job_id}: {job.status}.")
            self.render_all()
            return
        try:
            self.services.content_generation.retry_job(job_id)
        except ValueError as exc:
            self.add_history(f"Не удалось retry job #{job_id}: {exc}")
            self.render_all()
            return
        self.content_status = f"retry queued #{job_id}"
        self.add_history(f"Content job #{job_id} возвращен в queued.")
        self.start_background_content_worker()

    def generate_curriculum_command(self) -> None:
        try:
            job = self.services.content_generation.enqueue_curriculum(
                note="TUI /generate-curriculum"
            )
        except ValueError as exc:
            self.add_history(f"Не удалось поставить curriculum job: {exc}")
            self.render_all()
            return
        self.content_status = f"queued {JOB_KIND_CURRICULUM} #{job.id}"
        self.add_history(f"Curriculum generation job #{job.id} поставлен в queued.")
        self.start_background_content_worker()

    def pause_content_worker(self) -> None:
        action = self.content_worker.pause()
        if action.history_message:
            self.add_history(action.history_message)
        self.render_all()

    def resume_content_worker(self) -> None:
        action = self.content_worker.resume()
        if action.history_message:
            self.add_history(action.history_message)
        if not action.should_start_thread:
            self.render_all()
            return
        self.start_background_content_worker()

    def questions_review_command(self, raw_args: str) -> None:
        args = raw_args.strip()
        if not args or args == "list":
            self.enter_questions_review()
            return
        parts = args.split()
        if len(parts) != 2 or parts[0] not in {"accept", "archive"}:
            self.add_history(
                "Использование: /questions-review, /questions-review accept <id> "
                "или /questions-review archive <id> как manual audit override."
            )
            self.render_all()
            return
        action, raw_question_id = parts
        try:
            question_id = int(raw_question_id)
        except ValueError:
            self.add_history("Questions review принимает numeric question id.")
            self.render_all()
            return
        self.open_questions_review_screen()
        try:
            if action == "accept":
                question = self.services.questions.accept_review_question(question_id)
            else:
                question = self.services.questions.archive_review_question(question_id)
        except ValueError as exc:
            self.add_history(str(exc))
            self.render_all()
            return
        self.add_history(f"Manual audit override: Question #{question.id} {question.source_quality_status}.")
        self.render_all()

    def enter_artifacts(self, filter_arg: str | None = None) -> None:
        if filter_arg:
            parts = filter_arg.split()
            if len(parts) == 1 and parts[0] in {"current", "all"}:
                self.materials_learning_filter = parts[0]
            elif len(parts) == 2 and parts[0] in {"learning", "materials"} and parts[1] in {"current", "all"}:
                self.materials_learning_filter = parts[1]
            elif len(parts) == 2 and parts[0] in {"scenario", "scenarios", "system-design"} and parts[1] in {"current", "all"}:
                self.materials_scenario_filter = parts[1]
            else:
                self.add_history(
                    "Использование: /materials current|all или /materials scenarios current|all."
                )
                self.render_all()
                return
        if self.mode != "artifacts":
            self.artifacts_return_mode = self.mode
        self.mode = "artifacts"
        self.command_palette_visible = False
        self.last_feedback = "Сохраненные материалы и scenarios."
        self.add_history(
            "Открыт экран materials: "
            f"learning materials {self.materials_learning_filter}, "
            f"system design scenarios {self.materials_scenario_filter}."
        )
        self.render_all()

    def exit_artifacts(self) -> None:
        if self.mode != "artifacts":
            return
        self.mode = self.artifacts_return_mode if self.artifacts_return_mode != "artifacts" else "answering"
        if self.mode == "select_topic" and self.session is not None:
            self.mode = "answering"
        self.add_history("Возврат из materials.")
        self.render_all()

    def preview_learning_material(self, raw_id: str) -> None:
        material = self.resolve_learning_material(raw_id)
        if material is None:
            self.render_all()
            return
        version = self.learning_material_version_text(material)
        topic = self.learning_material_topic_label(material.topic_id)
        self.materials_preview = "\n".join(
            [
                "[bold]Preview: learning material[/bold]",
                f"#{material.id} {material.title}",
                f"Версия: {version}",
                f"Тема: {topic}",
                f"Источник: {material.source}",
                f"Создан: {material.created_at.isoformat(timespec='minutes')}",
                "",
                render_llm_markdown(material.body),
            ]
        )
        if self.mode != "artifacts":
            self.enter_artifacts()
            return
        self.add_history(f"Preview learning material #{material.id}.")
        self.render_all()

    def use_learning_material(self, raw_id: str) -> None:
        material = self.resolve_learning_material(raw_id)
        if material is None:
            self.render_all()
            return
        self.topic = self.services.repository.get_topic(material.topic_id) or self.topic
        self.generated_learning_material = material.body
        self.generated_learning_material_topic_id = material.topic_id
        self.add_history(f"Загружен учебный материал #{material.id}.")
        self.enter_learning()

    def archive_learning_material(self, raw_reference: str) -> None:
        parts = raw_reference.strip().split(maxsplit=2)
        if len(parts) < 2 or parts[1].lower() != "confirm":
            self.add_history("Для архивации используй: /archive-material <id> confirm [reason].")
            self.render_all()
            return
        reason = parts[2].strip() if len(parts) == 3 else None
        if reason == "":
            reason = None
        try:
            material_id = int(parts[0])
        except ValueError:
            self.add_history("Для архивации используй numeric id: /archive-material <id> confirm [reason].")
            self.render_all()
            return
        material = self.services.repository.get_learning_material(material_id)
        if material is None:
            self.add_history(f"Учебный материал #{material_id} не найден или уже archived.")
            self.render_all()
            return
        archived = self.services.repository.archive_learning_material(material_id, reason=reason)
        if not archived:
            self.add_history(f"Учебный материал #{material_id} уже archived.")
            self.render_all()
            return
        if self.materials_preview and f"#{material_id} " in self.materials_preview:
            self.materials_preview = None
        reason_suffix = f" Reason: {reason}" if reason else ""
        self.add_history(f"Учебный материал #{material_id} archived и скрыт из /materials.{reason_suffix}")
        if self.mode != "artifacts":
            self.enter_artifacts()
            return
        self.render_all()

    def preview_system_design_scenario(self, raw_id: str) -> None:
        scenario = self.resolve_system_design_scenario(raw_id)
        if scenario is None:
            self.render_all()
            return
        version = self.system_design_scenario_version_text(scenario)
        topic = self.learning_material_topic_label(scenario.topic_id)
        focus = "\n".join(f"- {item}" for item in scenario.focus_areas) or "- focus areas не указаны"
        self.materials_preview = "\n".join(
            [
                "[bold]Preview: system design scenario[/bold]",
                f"#{scenario.id} {scenario.title}",
                f"Версия: {version}",
                f"Тема: {topic}",
                f"Источник: {scenario.source}",
                f"Создан: {scenario.created_at.isoformat(timespec='minutes')}",
                "",
                "[bold]Scenario[/bold]",
                render_llm_markdown(scenario.scenario),
                "",
                "[bold]Focus areas[/bold]",
                focus,
            ]
        )
        if self.mode != "artifacts":
            self.enter_artifacts()
            return
        self.add_history(f"Preview system design scenario #{scenario.id}.")
        self.render_all()

    def use_system_design_scenario(self, raw_id: str) -> None:
        scenario = self.resolve_system_design_scenario(raw_id)
        if scenario is None:
            self.render_all()
            return
        self.generated_system_design_scenario = scenario.scenario
        self.generated_system_design_scenario_topic_id = scenario.topic_id
        self.generated_system_design_focus_areas = scenario.focus_areas
        self.add_history(f"Загружен system design scenario #{scenario.id}.")
        self.enter_system_design(scenario.scenario, scenario_id=scenario.id)

    def archive_system_design_scenario(self, raw_reference: str) -> None:
        parts = raw_reference.strip().split(maxsplit=2)
        if len(parts) < 2 or parts[1].lower() != "confirm":
            self.add_history("Для архивации используй: /archive-scenario <id> confirm [reason].")
            self.render_all()
            return
        reason = parts[2].strip() if len(parts) == 3 else None
        if reason == "":
            reason = None
        try:
            scenario_id = int(parts[0])
        except ValueError:
            self.add_history("Для архивации используй numeric id: /archive-scenario <id> confirm [reason].")
            self.render_all()
            return
        scenario = self.services.repository.get_system_design_scenario(scenario_id)
        if scenario is None:
            self.add_history(f"System design scenario #{scenario_id} не найден или уже archived.")
            self.render_all()
            return
        archived = self.services.repository.archive_system_design_scenario(scenario_id, reason=reason)
        if not archived:
            self.add_history(f"System design scenario #{scenario_id} уже archived.")
            self.render_all()
            return
        if self.materials_preview and f"#{scenario_id} " in self.materials_preview:
            self.materials_preview = None
        if self.system_design_scenario_id == scenario_id:
            self.system_design_scenario_id = None
            self.generated_system_design_scenario = None
            self.generated_system_design_scenario_topic_id = None
            self.generated_system_design_focus_areas = []
        reason_suffix = f" Reason: {reason}" if reason else ""
        self.add_history(f"System design scenario #{scenario_id} archived и скрыт из /materials.{reason_suffix}")
        if self.mode != "artifacts":
            self.enter_artifacts()
            return
        self.render_all()

    def resolve_learning_material(self, raw_reference: str) -> LearningMaterial | None:
        reference = raw_reference.strip().lower()
        if reference == "latest":
            topic_id = self.current_topic_id()
            if topic_id is None:
                self.add_history("Для /material latest сначала выбери текущую тему.")
                return None
            material = self.services.repository.latest_learning_material(topic_id)
            if material is None:
                self.add_history("Для текущей темы еще нет learning material.")
            return material
        try:
            material_id = int(reference)
        except ValueError:
            self.add_history("Использование: /material <id|latest> или /preview-material <id|latest>.")
            return None
        material = self.services.repository.get_learning_material(material_id)
        if material is None:
            self.add_history(f"Учебный материал #{material_id} не найден.")
        return material

    def resolve_system_design_scenario(self, raw_reference: str) -> SystemDesignScenario | None:
        reference = raw_reference.strip().lower()
        if reference == "latest":
            topic_id = self.materials_scenario_topic_id(self.current_topic_id())
            if topic_id is None:
                self.add_history("Нет темы system design для /scenario latest.")
                return None
            scenario = self.services.repository.latest_system_design_scenario(topic_id)
            if scenario is None:
                self.add_history("Для текущего system design контекста еще нет scenario.")
            return scenario
        try:
            scenario_id = int(reference)
        except ValueError:
            self.add_history("Использование: /scenario <id|latest> или /preview-scenario <id|latest>.")
            return None
        scenario = self.services.repository.get_system_design_scenario(scenario_id)
        if scenario is None:
            self.add_history(f"System design scenario #{scenario_id} не найден.")
        return scenario

    def current_topic_id(self) -> int | None:
        if self.topic is not None:
            return self.topic.id
        if self.session is not None:
            return self.session.topic_id
        return None

    def regenerate_learning_material(self) -> None:
        topic_id = self.topic.id if self.topic is not None else self.session.topic_id if self.session else None
        if topic_id is None:
            self.add_history("Сначала выбери тему, чтобы сгенерировать learning material.")
            self.render_all()
            return
        try:
            job = self.services.content_generation.enqueue_learning_material(
                topic_id,
                "Ручная регенерация учебного материала из TUI.",
            )
        except Exception as exc:
            self.add_history(f"Не удалось поставить learning-material job: {exc}")
            self.render_all()
            return
        self.content_status = f"queued {JOB_KIND_LEARNING_MATERIAL} #{job.id}"
        self.add_history(f"Регенерация learning material поставлена в очередь: job #{job.id}.")
        self.start_background_content_worker()

    def regenerate_system_design_scenario(self) -> None:
        topic = self.services.repository.find_topic_by_slug("system-design")
        topic_id = topic.id if topic is not None else self.session.topic_id if self.session else None
        if topic_id is None:
            self.add_history("Нет темы system design для генерации scenario.")
            self.render_all()
            return
        try:
            job = self.services.content_generation.enqueue_system_design_scenario(
                topic_id,
                "Ручная регенерация system design scenario из TUI.",
            )
        except Exception as exc:
            self.add_history(f"Не удалось поставить system-design-scenario job: {exc}")
            self.render_all()
            return
        self.content_status = f"queued {JOB_KIND_SYSTEM_DESIGN_SCENARIO} #{job.id}"
        self.add_history(f"Регенерация system design scenario поставлена в очередь: job #{job.id}.")
        self.start_background_content_worker()

    def start_session_from_input(self, raw: str) -> None:
        self.baseline_session_id = None
        self.baseline_question_ids = ()
        self.mock_interview_session_id = None
        self.mock_interview_question_ids = ()
        self.mock_interview_sections = ()
        topic_id: int | None = None
        topics = self.services.questions.list_topics()
        suggested = self.suggested_practice_topic(topics)
        if raw:
            try:
                topic_id = int(raw)
            except ValueError:
                self.add_history("Введи ID темы или Enter для рекомендованной.")
                self.render_all()
                return
            if self.services.repository.get_topic(topic_id) is None:
                self.add_history("Такой темы нет. Выбери ID из левой панели.")
                self.render_all()
                return
        elif suggested:
            topic_id = suggested.id

        session = self.services.sessions.start_session(
            topic_id=topic_id,
            target_minutes=DEFAULT_SESSION_MINUTES,
        )
        topic = self.services.repository.get_topic(topic_id) if topic_id else None
        self.apply_practice_session_start_snapshot(
            build_practice_session_start_snapshot(session, topic)
        )
        self.add_history(f"Сессия #{self.session.id} начата.")
        self.persist_notes_draft()
        self.ensure_background_content_for_current_topic()
        self.load_next_question()

    def start_baseline_session(self) -> None:
        self.mock_interview_session_id = None
        self.mock_interview_question_ids = ()
        self.mock_interview_sections = ()
        try:
            plan = self.services.calibration.start_baseline_session(
                target_minutes=DEFAULT_SESSION_MINUTES,
            )
        except Exception as exc:
            self.add_history(f"Не удалось начать baseline session: {exc}")
            self.render_all()
            return
        self.baseline_session_id = plan.session.id
        self.baseline_question_ids = plan.question_ids
        self.apply_practice_session_start_snapshot(
            build_practice_session_start_snapshot(plan.session, None)
        )
        self.add_history(
            f"Baseline session #{self.session.id} начата: {len(self.baseline_question_ids)} вопросов по разным competencies."
        )
        self.persist_notes_draft()
        self.load_next_question()

    def start_mock_senior_interview(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        self.exit_other_focused_modes(set())
        self.baseline_session_id = None
        self.baseline_question_ids = ()
        try:
            plan = self.services.calibration.start_mock_senior_interview_session(
                target_minutes=DEFAULT_SESSION_MINUTES,
            )
        except Exception as exc:
            self.add_history(f"Не удалось начать mock senior interview: {exc}")
            self.render_all()
            return
        self.mock_interview_session_id = plan.session.id
        self.mock_interview_question_ids = plan.question_ids
        self.mock_interview_sections = plan.sections
        self.apply_practice_session_start_snapshot(
            build_practice_session_start_snapshot(plan.session, None)
        )
        self.add_history(
            f"Mock senior interview #{self.session.id} начат: {len(self.mock_interview_question_ids)} секций."
        )
        self.persist_notes_draft()
        self.load_next_question()

    def apply_practice_session_start_snapshot(self, snapshot: PracticeSessionStartSnapshot) -> None:
        self.session = snapshot.session
        self.started_at = snapshot.started_at
        self.topic = snapshot.topic
        self.question = snapshot.question
        self.current_answer = snapshot.current_answer
        self.pending_answer_text = snapshot.pending_answer_text
        self.answered_count = snapshot.answered_count
        self.skipped_count = snapshot.skipped_count
        self.skipped_question_ids = set(snapshot.skipped_question_ids)
        self.showing_hint = snapshot.showing_hint
        self.showing_reference = snapshot.showing_reference
        self.mode = snapshot.mode
        self.generated_learning_material = snapshot.generated_learning_material
        self.generated_learning_material_topic_id = snapshot.generated_learning_material_topic_id

    def accept_suggested_topic(self) -> None:
        if self.mode != "select_topic":
            self.add_history("/accept-topic доступна только на экране выбора темы.")
            self.render_all()
            return
        suggested = self.suggested_practice_topic()
        if suggested is None or suggested.id is None:
            self.add_history("Нет предложенной темы для принятия.")
            self.render_all()
            return
        self.start_session_from_input(str(suggested.id))

    def practice_topic_recommendation(self) -> TopicRecommendation | None:
        try:
            return self.services.curriculum.suggest_next_topic()
        except Exception:
            return None

    def suggested_practice_topic(self, topics: list[Topic] | None = None) -> Topic | None:
        recommendation = self.practice_topic_recommendation()
        if recommendation is not None and recommendation.topic.id is not None:
            return recommendation.topic
        topics = topics if topics is not None else self.services.questions.list_topics()
        suggested_title = self.services.stats.dashboard().get("suggested_topic")
        return next((topic for topic in topics if topic.title == suggested_title), None)

    def load_next_question(self) -> None:
        if self.session is None:
            return
        if self.topic is None and self.session.topic_id is not None:
            self.topic = self.services.repository.get_topic(self.session.topic_id)
        self.apply_practice_next_question_snapshot(
            build_practice_next_question_snapshot(self.next_available_question())
        )
        if self.question is None:
            self.add_history("Вопросы закончились.")
            self.end_session()
            return
        self.add_history(f"Вопрос #{self.question.id}: {self.question.difficulty}")
        self.render_all()

    def apply_practice_next_question_snapshot(self, snapshot: PracticeNextQuestionSnapshot) -> None:
        self.question = snapshot.question
        self.current_answer = snapshot.current_answer
        self.pending_answer_text = snapshot.pending_answer_text
        self.last_feedback = snapshot.last_feedback
        self.showing_hint = snapshot.showing_hint
        self.showing_reference = snapshot.showing_reference
        self.mode = snapshot.mode

    def next_available_question(self) -> Question | None:
        if self.session is None:
            return None
        if self.baseline_session_id == self.session.id and self.baseline_question_ids:
            planned_questions = [
                self.services.repository.get_question(question_id)
                for question_id in self.baseline_question_ids
            ]
            questions = [question for question in planned_questions if question is not None]
        elif self.mock_interview_session_id == self.session.id and self.mock_interview_question_ids:
            planned_questions = [
                self.services.repository.get_question(question_id)
                for question_id in self.mock_interview_question_ids
            ]
            questions = [question for question in planned_questions if question is not None]
        else:
            questions = self.services.sessions.candidate_questions(self.session.id or 0)
        answered_ids = self.services.repository.answered_question_ids_for_session(self.session.id or 0)
        blocked_ids = answered_ids | self.skipped_question_ids
        for question in questions:
            if question.id not in blocked_ids:
                return question
        for question in questions:
            if question.id not in answered_ids:
                return question
        return questions[0] if questions else None

    def capture_answer(self, text: str) -> None:
        if self.session is None or self.question is None:
            self.add_history("Сначала выбери тему и начни сессию.")
            self.render_all()
            return
        answer = self.services.sessions.answer_question(
            self.session.id or 0,
            self.question.id or 0,
            text,
            None,
            with_feedback=False,
        )
        self.apply_practice_answer_scoring_snapshot(
            build_practice_answer_scoring_snapshot(answer, self.answered_count + 1)
        )
        self.add_history(f"Ответ сохранен как #{self.current_answer.id}. Введи самооценку 1-5 или Enter.")
        self.render_all()

    def apply_practice_answer_scoring_snapshot(self, snapshot: PracticeAnswerScoringSnapshot) -> None:
        self.current_answer = snapshot.current_answer
        self.pending_answer_text = snapshot.pending_answer_text
        self.answered_count = snapshot.answered_count
        self.showing_reference = snapshot.showing_reference
        self.mode = snapshot.mode

    def capture_score(self, raw: str) -> None:
        if self.current_answer is None:
            self.mode = "answering"
            self.render_all()
            return
        score_result = parse_practice_self_score(raw)
        if score_result.error is not None:
            self.add_history(score_result.error)
            self.render_all()
            return
        updated_answer = self.services.sessions.update_self_score(self.current_answer, score_result.score)
        self.current_answer = updated_answer
        self.persist_current_rubric_evaluation()
        self.apply_practice_answered_snapshot(build_practice_answered_snapshot(updated_answer))
        score_text = score_result.score if score_result.score is not None else "без оценки"
        self.add_history(f"Самооценка сохранена: {score_text}. Enter - следующий вопрос.")
        self.render_all()

    def apply_practice_answered_snapshot(self, snapshot: PracticeAnsweredSnapshot) -> None:
        self.current_answer = snapshot.current_answer
        self.showing_reference = snapshot.showing_reference
        self.mode = snapshot.mode

    def persist_current_rubric_evaluation(self) -> None:
        if self.current_answer is None or self.question is None:
            return
        try:
            self.services.evaluations.evaluate_and_store_answer(
                self.current_answer,
                self.question,
                use_llm=False,
            )
        except Exception as exc:
            self.add_history(f"Rubric evaluation не сохранена: {exc}")

    def show_hint(self) -> None:
        if self.question is None:
            self.add_history("Сначала начни сессию.")
        else:
            self.showing_hint = True
            self.add_history("Подсказка показана.")
        self.render_all()

    def show_reference(self) -> None:
        if self.question is None:
            self.add_history("Сначала начни сессию.")
        else:
            self.showing_reference = True
            self.add_history("Эталонный ответ показан.")
        self.render_all()

    def request_feedback(self, *, recheck: bool = False) -> None:
        if self.question is None or self.current_answer is None or not self.pending_answer_text:
            self.add_history("Сначала напиши ответ. Потом используй /feedback.")
            self.render_all()
            return
        if recheck and not self.current_answer.ai_feedback:
            self.add_history("Сначала запроси /feedback, потом используй /recheck-feedback.")
            self.render_all()
            return
        if self.mode == "loading_feedback":
            return
        self.mode = "loading_feedback"
        self.ollama_status = "генерирует feedback..."
        if recheck:
            self.add_history("Перепроверяю AI feedback более строгим prompt...")
        else:
            self.add_history("Генерирую AI feedback через Ollama...")
        self.render_all()

        def work() -> None:
            quality = FeedbackQuality(flags=())
            try:
                if recheck:
                    generated_feedback = self.services.sessions.recheck_feedback_with_quality(
                        self.question,
                        self.pending_answer_text or self.current_answer.user_answer,
                        previous_feedback=self.current_answer.ai_feedback,
                    )
                else:
                    generated_feedback = self.services.sessions.feedback_with_quality(
                        self.question,
                        self.pending_answer_text or "",
                    )
                feedback = generated_feedback.text
                quality = generated_feedback.quality
                last_error = getattr(self.services.llm, "last_error", None)
            except Exception as exc:
                feedback = f"Fallback: AI feedback не получен. Деталь: {exc}"
                last_error = str(exc)
            self.call_from_thread(self.finish_feedback, feedback, last_error, quality, recheck)

        threading.Thread(target=work, daemon=True).start()

    def finish_feedback(
        self,
        feedback: str,
        last_error: str | None,
        quality: FeedbackQuality | None = None,
        recheck: bool = False,
    ) -> None:
        if self.current_answer is not None:
            self.services.repository.update_answer_feedback(self.current_answer.id or 0, feedback)
            if quality is not None:
                self.services.sessions.record_feedback_quality_for_answer(
                    self.current_answer.id or 0,
                    quality,
                    fallback_error=last_error,
                )
            self.current_answer = Answer(
                id=self.current_answer.id,
                session_id=self.current_answer.session_id,
                question_id=self.current_answer.question_id,
                user_answer=self.current_answer.user_answer,
                self_score=self.current_answer.self_score,
                ai_feedback=feedback,
                answered_at=self.current_answer.answered_at,
            )
        self.last_feedback = feedback
        self.ollama_status = "fallback" if last_error else "ok"
        if last_error:
            self.add_history(f"Ollama fallback: {last_error}")
        elif recheck:
            self.add_history("AI feedback перепроверен строгим prompt.")
        else:
            self.add_history("AI feedback готов.")
        self.mode = "answered"
        self.render_all()

    def enter_learning(self, initial_question: str = "") -> None:
        snapshot = build_learning_entry_snapshot(
            current_mode=self.mode,
            current_topic_id=self.topic.id if self.topic is not None else None,
            session_topic_id=self.session.topic_id if self.session is not None else None,
            has_session=self.session is not None,
            current_learning_return_mode=self.learning_return_mode,
            current_learning_dialog_session_id=self.learning_dialog_session_id,
            generated_learning_material=self.generated_learning_material,
            generated_learning_material_topic_id=self.generated_learning_material_topic_id,
            new_dialog_session_id=f"learn-{uuid4().hex[:12]}",
        )
        self.apply_learning_entry_snapshot(snapshot)
        self.add_history("Открыт режим обучения.")
        self.load_learning_transcript_for_topic(snapshot.learning_topic_id)
        if snapshot.should_clear_generated_learning_material:
            self.generated_learning_material = None
            self.generated_learning_material_topic_id = None
        elif snapshot.should_ensure_learning_material:
            self.ensure_background_learning_material_for_topic(snapshot.learning_topic_id)
        self.render_all()
        if initial_question:
            self.request_learning(initial_question)

    def apply_learning_entry_snapshot(self, snapshot: LearningEntrySnapshot) -> None:
        self.learning_return_mode = snapshot.learning_return_mode
        self.learning_dialog_session_id = snapshot.learning_dialog_session_id
        self.learning_topic_id = snapshot.learning_topic_id
        if snapshot.clear_current_practice_context:
            self.topic = None
            self.question = None
        self.mode = snapshot.mode
        self.command_palette_visible = snapshot.command_palette_visible
        self.last_feedback = snapshot.last_feedback

    def learning_context_topic_id(self, source_mode: Mode | None = None) -> int | None:
        if source_mode == "select_topic" and self.session is None:
            return None
        if self.topic is not None:
            return self.topic.id
        if self.session is not None:
            return self.session.topic_id
        return None

    def load_learning_transcript_for_topic(self, topic_id: int | None) -> None:
        self.learning_topic_id = topic_id
        self.learning_pending_message = ""
        self.learning_dialog_offset = 0
        if topic_id is None:
            self.learning_transcript = []
            return
        try:
            if hasattr(self.services.learning, "list_dialog_messages"):
                messages = self.services.learning.list_dialog_messages(topic_id, limit=50)
            else:
                messages = self.services.repository.list_learning_dialog_messages(topic_id, limit=50)
        except Exception as exc:
            self.add_history(f"Не удалось загрузить учебный диалог: {exc}")
            return
        self.learning_transcript = [
            ("Ты" if message.role == "user" else "ИИ", message.content)
            for message in messages
        ]
        if messages:
            self.add_history(f"Загружены последние учебные реплики: {len(messages)}.")

    def show_older_learning_messages(self) -> None:
        if self.mode not in {"learning", "loading_learning"}:
            self.add_history("Открой /learn, чтобы листать учебный диалог.")
            self.render_all()
            return
        max_offset = max(0, len(self.learning_transcript) - self.learning_dialog_window_size)
        next_offset = min(max_offset, self.learning_dialog_offset + self.learning_dialog_window_size)
        if next_offset == self.learning_dialog_offset:
            self.add_history("Более старых учебных реплик в загруженном окне нет.")
        else:
            self.learning_dialog_offset = next_offset
            self.add_history("Показаны более старые учебные реплики.")
        self.render_all()

    def show_newer_learning_messages(self) -> None:
        if self.mode not in {"learning", "loading_learning"}:
            self.add_history("Открой /learn, чтобы листать учебный диалог.")
            self.render_all()
            return
        next_offset = max(0, self.learning_dialog_offset - self.learning_dialog_window_size)
        if next_offset == self.learning_dialog_offset:
            self.add_history("Ты уже смотришь самые новые учебные реплики.")
        else:
            self.learning_dialog_offset = next_offset
            self.add_history("Показаны более новые учебные реплики.")
        self.render_all()

    def exit_learning(self) -> None:
        if self.mode not in {"learning", "loading_learning"}:
            self.add_history("Сейчас не режим обучения.")
            self.render_all()
            return
        self.mode = self.learning_return_mode if self.learning_return_mode != "loading_learning" else "answering"
        if self.mode == "select_topic" and self.session is not None:
            self.mode = "answering"
        self.add_history("Возврат к interview practice.")
        self.render_all()

    def enter_system_design(self, scenario: str = "", scenario_id: int | None = None) -> None:
        snapshot = build_system_design_entry_snapshot(
            current_mode=self.mode,
            current_topic=self.topic,
            current_question=self.question,
            current_answer=self.current_answer,
            current_pending_answer=self.pending_answer_text,
            current_showing_hint=self.showing_hint,
            current_showing_reference=self.showing_reference,
            current_system_design_return_mode=self.system_design_return_mode,
            current_system_design_saved_topic=self.system_design_saved_topic,
            current_system_design_saved_question=self.system_design_saved_question,
            current_system_design_saved_answer=self.system_design_saved_answer,
            current_system_design_saved_pending_answer=self.system_design_saved_pending_answer,
            current_system_design_saved_showing_hint=self.system_design_saved_showing_hint,
            current_system_design_saved_showing_reference=self.system_design_saved_showing_reference,
            current_system_design_scenario=self.system_design_scenario,
            current_system_design_scenario_id=self.system_design_scenario_id,
            current_system_design_transcript=self.system_design_transcript,
            scenario=scenario,
            scenario_id=scenario_id,
        )
        self.apply_system_design_entry_snapshot(snapshot)

        if self.session is None:
            topic = self.services.repository.find_topic_by_slug("system-design")
            self.topic = topic
            self.session = self.services.sessions.start_session(
                topic_id=topic.id if topic else None,
                target_minutes=DEFAULT_SESSION_MINUTES,
            )
            self.started_at = self.session.started_at
            self.add_history(f"Сессия #{self.session.id} начата для system design mock interview.")
        elif self.topic is None:
            self.topic = self.services.repository.find_topic_by_slug("system-design")
        else:
            system_topic = self.services.repository.find_topic_by_slug("system-design")
            if system_topic is not None:
                self.topic = system_topic

        self.add_history("Открыт system design mock interview.")
        self.ensure_background_content_for_current_topic()
        self.ensure_background_system_design_scenario()
        self.restore_system_design_artifacts()
        self.render_all()

    def apply_system_design_entry_snapshot(self, snapshot: SystemDesignEntrySnapshot) -> None:
        self.system_design_return_mode = snapshot.system_design_return_mode
        self.system_design_saved_topic = snapshot.system_design_saved_topic
        self.system_design_saved_question = snapshot.system_design_saved_question
        self.system_design_saved_answer = snapshot.system_design_saved_answer
        self.system_design_saved_pending_answer = snapshot.system_design_saved_pending_answer
        self.system_design_saved_showing_hint = snapshot.system_design_saved_showing_hint
        self.system_design_saved_showing_reference = snapshot.system_design_saved_showing_reference
        self.system_design_scenario = snapshot.system_design_scenario
        self.system_design_scenario_id = snapshot.system_design_scenario_id
        self.system_design_transcript = list(snapshot.system_design_transcript)
        if snapshot.should_reset_artifacts:
            self.reset_system_design_artifacts()
        self.showing_hint = snapshot.showing_hint
        self.showing_reference = snapshot.showing_reference
        self.mode = snapshot.mode
        self.last_feedback = snapshot.last_feedback

    def ensure_background_content_for_current_topic(self) -> None:
        if self.session is None or self.session.topic_id is None:
            return
        try:
            job = self.services.content_generation.ensure_question_backlog(
                self.session.topic_id,
                min_questions=4,
                note="Автоматически подготовь дополнительный практический вопрос для текущей темы.",
            )
        except Exception as exc:
            self.content_status = "auto queue failed"
            self.add_history(f"Автогенерация контента не поставлена в очередь: {exc}")
            return
        if job is None:
            self.content_status = "enough content"
            return
        self.content_status = f"queued #{job.id}"
        self.add_history(f"Автогенерация контента поставлена в очередь: job #{job.id}.")
        self.start_background_content_worker()

    def ensure_background_learning_material_for_current_topic(self) -> None:
        topic_id = self.topic.id if self.topic is not None else self.session.topic_id if self.session else None
        self.ensure_background_learning_material_for_topic(topic_id)

    def ensure_background_learning_material_for_topic(self, topic_id: int | None) -> None:
        if topic_id is None:
            return
        material = self.services.repository.latest_learning_material(topic_id)
        if material is not None:
            self.generated_learning_material = material.body
            self.generated_learning_material_topic_id = topic_id
            self.add_history(f"Загружен учебный материал #{material.id}.")
            return
        try:
            job = self.services.content_generation.ensure_learning_material(
                topic_id,
                note="Автоматически подготовь краткий учебный разбор для focused learning mode.",
            )
        except Exception as exc:
            self.content_status = "learning queue failed"
            self.add_history(f"Учебный материал не поставлен в очередь: {exc}")
            return
        if job is None:
            return
        self.content_status = f"queued {JOB_KIND_LEARNING_MATERIAL} #{job.id}"
        self.add_history(f"Учебный материал поставлен в очередь: job #{job.id}.")
        self.start_background_content_worker()

    def ensure_background_system_design_scenario(self) -> None:
        topic = self.services.repository.find_topic_by_slug("system-design")
        topic_id = topic.id if topic is not None else self.session.topic_id if self.session else None
        if topic_id is None:
            return
        saved_scenario = self.services.repository.latest_system_design_scenario(topic_id)
        if saved_scenario is not None:
            self.generated_system_design_scenario = saved_scenario.scenario
            self.generated_system_design_scenario_topic_id = topic_id
            self.generated_system_design_focus_areas = saved_scenario.focus_areas
            if not self.system_design_transcript and self.system_design_scenario == DEFAULT_SYSTEM_DESIGN_SCENARIO:
                self.system_design_scenario = saved_scenario.scenario
                self.system_design_scenario_id = saved_scenario.id
            self.add_history(f"Загружен system design scenario #{saved_scenario.id}.")
            return
        try:
            job = self.services.content_generation.ensure_system_design_scenario(
                topic_id,
                note="Автоматически подготовь mock interview scenario для system design mode.",
            )
        except Exception as exc:
            self.content_status = "scenario queue failed"
            self.add_history(f"System design scenario не поставлен в очередь: {exc}")
            return
        if job is None:
            return
        self.content_status = f"queued {JOB_KIND_SYSTEM_DESIGN_SCENARIO} #{job.id}"
        self.add_history(f"System design scenario поставлен в очередь: job #{job.id}.")
        self.start_background_content_worker()

    def start_background_content_worker(self) -> None:
        action = self.content_worker.request_start(
            paused_message_already_visible=bool(
                self.history and self.history[-1] == "TUI content worker на паузе; queued jobs сохранены."
            )
        )
        if action.history_message:
            self.add_history(action.history_message)
        if not action.should_start_thread:
            if action.should_render:
                self.render_all()
            return
        self.render_all()

        def work() -> None:
            services = AppServices(self.db_path, self.config_path)
            try:
                run = self.content_worker.process_available_jobs(
                    services.content_generation,
                    services.llm,
                )
            finally:
                services.close()
            self.dispatch_from_worker_thread(
                self.finish_background_content_worker,
                list(run.results),
                run.last_error,
            )

        threading.Thread(target=work, daemon=True).start()

    def finish_background_content_worker(self, result, last_error: str | None) -> None:
        finish = self.content_worker.finish_run(result)
        if finish.history_message:
            self.add_history(finish.history_message)
        else:
            for item in finish.results:
                self.apply_background_content_result(item, last_error)
            self.content_status = finish.status
        self.render_all()

    def apply_background_content_result(self, result, last_error: str | None) -> None:
        if result.created_question is not None:
            if last_error:
                self.add_history(f"Автогенерация использовала fallback: {last_error}")
            self.add_history(f"Автогенерация добавила вопрос #{result.created_question.id}.")
            return
        if result.job.status != "done" or not result.artifact:
            self.content_status = "failed"
            self.add_history(f"Автогенерация контента не удалась: {result.job.error}")
            return
        kind = result.artifact.get("kind")
        if kind == JOB_KIND_LEARNING_MATERIAL:
            self.generated_learning_material = str(result.artifact.get("material") or "").strip()
            self.generated_learning_material_topic_id = int(result.artifact.get("topic_id") or 0) or None
            self.add_history("Автогенерация подготовила учебный материал.")
            if self.mode in {"learning", "loading_learning"} and self.generated_learning_material:
                self.last_feedback = f"Учебный материал готов.\n\n{self.generated_learning_material}"
            return
        if kind == JOB_KIND_SYSTEM_DESIGN_SCENARIO:
            scenario = str(result.artifact.get("scenario") or "").strip()
            focus_areas = result.artifact.get("focus_areas") or []
            self.generated_system_design_scenario = scenario or None
            self.generated_system_design_scenario_topic_id = int(result.artifact.get("topic_id") or 0) or None
            self.generated_system_design_focus_areas = [str(item).strip() for item in focus_areas if str(item).strip()]
            if (
                self.mode
                in {
                    "system_design",
                    "loading_system_design",
                    "loading_system_design_checkpoint",
                    "loading_system_design_pressure",
                    "loading_system_design_feedback",
                }
                and scenario
                and not self.system_design_transcript
                and self.system_design_scenario == DEFAULT_SYSTEM_DESIGN_SCENARIO
            ):
                self.system_design_scenario = scenario
                scenario_id = result.artifact.get("scenario_id")
                self.system_design_scenario_id = int(scenario_id) if scenario_id else None
                self.restore_system_design_artifacts()
            self.add_history("Автогенерация подготовила system design scenario.")
            return
        if kind == JOB_KIND_REFERENCE_ANSWER:
            updated_count = int(result.artifact.get("updated_count") or 0)
            question_ids = result.artifact.get("question_ids") or []
            if self.question and self.question.id in question_ids:
                refreshed = self.services.repository.get_question(self.question.id)
                if refreshed is not None:
                    self.question = refreshed
            self.add_history(f"Автогенерация обновила эталонные ответы: {updated_count}.")
            return
        self.add_history(f"Автогенерация завершила job #{result.job.id}: {kind}.")

    def reset_system_design_artifacts(self) -> None:
        self.system_design_artifacts = {
            "requirements": [],
            "api": [],
            "data_model": [],
            "decisions": [],
            "risks": [],
        }

    def restore_system_design_artifacts(
        self,
        topic_id: int | None = None,
        scenario_id: int | None = None,
    ) -> None:
        topic_id = topic_id or self.system_design_topic_id()
        scenario_id = self.system_design_scenario_id if scenario_id is None else scenario_id
        if topic_id is None:
            return
        list_artifacts = getattr(self.services.system_design, "list_artifacts", None)
        try:
            if list_artifacts is not None:
                artifacts = list_artifacts(topic_id, scenario_id=scenario_id)
            else:
                artifacts = self.services.repository.list_system_design_artifacts(
                    topic_id,
                    scenario_id=scenario_id,
                )
        except Exception as exc:
            self.add_history(f"System design artifacts не загружены: {exc}")
            return
        self.reset_system_design_artifacts()
        for artifact in artifacts:
            if artifact.section in self.system_design_artifacts:
                self.system_design_artifacts[artifact.section].append(artifact.content)
        if artifacts:
            self.add_history(f"Загружены system design artifacts: {len(artifacts)}.")

    def system_design_topic_id(self) -> int | None:
        return self.topic.id if self.topic is not None else self.session.topic_id if self.session else None

    def add_system_design_artifact(self, section: str, text: str) -> None:
        if self.mode not in {
            "system_design",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            self.add_history("System design заметки доступны только в /system-design.")
            self.render_all()
            return
        if not text:
            self.add_history("Добавь текст после команды system design заметки.")
            self.render_all()
            return
        if section not in self.system_design_artifacts:
            self.add_history(f"Неизвестная секция system design: {section}")
            self.render_all()
            return
        topic_id = self.system_design_topic_id()
        if topic_id is None:
            self.add_history("System design artifact не сохранен: нет активной темы.")
            self.render_all()
            return
        cleaned_text = text.strip()
        try:
            add_artifact = getattr(self.services.system_design, "add_artifact", None)
            if add_artifact is not None:
                saved = add_artifact(
                    topic_id,
                    section,
                    cleaned_text,
                    scenario_id=self.system_design_scenario_id,
                )
            else:
                saved = self.services.repository.add_system_design_artifact(
                    SystemDesignArtifact(
                        id=None,
                        topic_id=topic_id,
                        scenario_id=self.system_design_scenario_id,
                        section=section,
                        content=cleaned_text,
                        created_at=datetime.now(),
                    )
                )
        except Exception as exc:
            self.add_history(f"System design artifact не сохранен: {exc}")
            self.render_all()
            return
        self.system_design_artifacts[section].append(saved.content)
        self.add_history(f"System design artifact сохранен: {section}.")
        self.render_all()

    def request_system_design_turn(self, user_message: str) -> None:
        snapshot = build_system_design_request_snapshot(user_message)
        self.apply_system_design_request_snapshot(snapshot)
        self.render_all()

        def work() -> None:
            try:
                response = self.services.system_design.next_turn(
                    self.system_design_scenario,
                    self.system_design_transcript,
                    user_message,
                )
                last_error = getattr(self.services.llm, "last_error", None)
            except Exception as exc:
                response = (
                    "Fallback interviewer: зафиксируй requirements, API, storage и failure modes. "
                    "Какие non-functional requirements ты считаешь ключевыми?"
                )
                last_error = str(exc)
            self.dispatch_from_worker_thread(
                self.finish_system_design_turn,
                user_message,
                response,
                last_error,
            )

        threading.Thread(target=work, daemon=True).start()

    def apply_system_design_request_snapshot(self, snapshot: SystemDesignRequestSnapshot) -> None:
        self.system_design_pending_message = snapshot.system_design_pending_message
        self.mode = snapshot.mode
        self.ollama_status = snapshot.ollama_status
        self.last_feedback = snapshot.last_feedback
        self.add_history(snapshot.history_message)

    def finish_system_design_turn(self, user_message: str, response: str, last_error: str | None) -> None:
        snapshot = build_system_design_finish_turn_snapshot(
            user_message=user_message,
            response=response,
            last_error=last_error,
        )
        self.apply_system_design_finish_turn_snapshot(snapshot)
        self.save_system_design_transcript_turn(user_message, response)
        self.save_system_design_artifacts_from_transcript(user_message)
        self.add_history(snapshot.history_message)
        self.render_all()

    def apply_system_design_finish_turn_snapshot(self, snapshot: SystemDesignFinishTurnSnapshot) -> None:
        self.system_design_transcript.extend(snapshot.transcript_entries)
        self.system_design_pending_message = snapshot.system_design_pending_message
        self.ollama_status = snapshot.ollama_status
        self.last_feedback = snapshot.last_feedback
        self.mode = snapshot.mode

    def save_system_design_transcript_turn(self, user_message: str, response: str) -> None:
        topic_id = self.system_design_topic_id()
        save_turn = getattr(self.services.system_design, "save_transcript_turn", None)
        if topic_id is None or save_turn is None:
            return
        try:
            save_turn(
                topic_id,
                user_message,
                response,
                scenario_id=self.system_design_scenario_id,
            )
        except Exception as exc:
            self.add_history(f"System design transcript не сохранен: {exc}")

    def save_system_design_artifacts_from_transcript(self, user_message: str) -> None:
        artifacts = extract_system_design_artifact_commands(user_message)
        for section, text in artifacts:
            self.add_system_design_artifact(section, text)
        if artifacts:
            self.add_history(f"Автоперенос artifact-команд из transcript: {len(artifacts)}.")

    def request_system_design_checkpoint(self) -> None:
        if self.mode in {
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            self.add_history("ИИ еще отвечает. Дождись ответа перед checkpoint.")
            self.render_all()
            return
        if self.mode != "system_design":
            self.add_history("/sd-checkpoint доступен только в system design mode.")
            self.render_all()
            return
        if not self.system_design_transcript and not self.has_system_design_artifacts():
            self.add_history("Сначала добавь часть решения или artifact перед /sd-checkpoint.")
            self.render_all()
            return
        snapshot = build_system_design_checkpoint_loading_snapshot()
        self.apply_system_design_loading_snapshot(snapshot)
        self.render_all()

        def work() -> None:
            try:
                checkpoint = self.services.system_design.checkpoint(
                    self.system_design_scenario,
                    self.system_design_transcript,
                    self.system_design_artifacts,
                )
                last_error = getattr(self.services.llm, "last_error", None)
            except Exception as exc:
                checkpoint = (
                    "Checkpoint:\n"
                    "- Что уже понятно: решение начато, но evidence пока неполное.\n"
                    "- Главный риск или пробел: проверь requirements, API, data model и failure modes.\n"
                    "- Следующий лучший шаг: зафиксируй один missing artifact.\n"
                    "Вопрос интервьюера: какой самый важный tradeoff ты хочешь закрыть дальше?"
                )
                last_error = str(exc)
            self.dispatch_from_worker_thread(
                self.finish_system_design_checkpoint,
                checkpoint,
                last_error,
            )

        threading.Thread(target=work, daemon=True).start()

    def finish_system_design_checkpoint(self, checkpoint: str, last_error: str | None) -> None:
        snapshot = build_system_design_checkpoint_finish_snapshot(
            checkpoint=checkpoint,
            last_error=last_error,
        )
        self.apply_system_design_auxiliary_finish_snapshot(snapshot)
        self.save_system_design_checkpoint(checkpoint)
        self.add_history(snapshot.history_message)
        self.render_all()

    def save_system_design_checkpoint(self, checkpoint: str) -> None:
        topic_id = self.system_design_topic_id()
        add_message = getattr(self.services.system_design, "add_transcript_message", None)
        if topic_id is None or add_message is None:
            return
        try:
            add_message(
                topic_id,
                "interviewer",
                checkpoint,
                scenario_id=self.system_design_scenario_id,
            )
        except Exception as exc:
            self.add_history(f"System design checkpoint не сохранен: {exc}")

    def request_system_design_pressure(self) -> None:
        if self.mode in {
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            self.add_history("ИИ еще отвечает. Дождись ответа перед pressure follow-up.")
            self.render_all()
            return
        if self.mode != "system_design":
            self.add_history("/sd-pressure доступен только в system design mode.")
            self.render_all()
            return
        if not self.system_design_transcript and not self.has_system_design_artifacts():
            self.add_history("Сначала добавь часть решения или artifact перед /sd-pressure.")
            self.render_all()
            return
        snapshot = build_system_design_pressure_loading_snapshot()
        self.apply_system_design_loading_snapshot(snapshot)
        self.render_all()

        def work() -> None:
            try:
                pressure = self.services.system_design.pressure_follow_up(
                    self.system_design_scenario,
                    self.system_design_transcript,
                    self.system_design_artifacts,
                )
                last_error = getattr(self.services.llm, "last_error", None)
            except Exception as exc:
                pressure = (
                    "Pressure follow-up:\n"
                    "- Focus: idempotency и retries.\n"
                    "- Why now: решение должно выдерживать повторы, таймауты и дубли без порчи данных.\n"
                    "Question: как ты задашь idempotency key, retry policy и DLQ для этого flow?"
                )
                last_error = str(exc)
            self.dispatch_from_worker_thread(
                self.finish_system_design_pressure,
                pressure,
                last_error,
            )

        threading.Thread(target=work, daemon=True).start()

    def finish_system_design_pressure(self, pressure: str, last_error: str | None) -> None:
        snapshot = build_system_design_pressure_finish_snapshot(
            pressure=pressure,
            last_error=last_error,
        )
        self.apply_system_design_auxiliary_finish_snapshot(snapshot)
        self.save_system_design_pressure(pressure)
        self.add_history(snapshot.history_message)
        self.render_all()

    def save_system_design_pressure(self, pressure: str) -> None:
        topic_id = self.system_design_topic_id()
        add_message = getattr(self.services.system_design, "add_transcript_message", None)
        if topic_id is None or add_message is None:
            return
        try:
            add_message(
                topic_id,
                "interviewer",
                pressure,
                scenario_id=self.system_design_scenario_id,
            )
        except Exception as exc:
            self.add_history(f"System design pressure follow-up не сохранен: {exc}")

    def has_system_design_artifacts(self) -> bool:
        return any(any(item.strip() for item in items) for items in self.system_design_artifacts.values())

    def request_system_design_feedback(self) -> None:
        if not self.system_design_transcript:
            self.add_history("Сначала начни system design диалог и предложи часть решения.")
            self.render_all()
            return
        missing_sections = self.missing_system_design_feedback_sections()
        if missing_sections:
            labels = ", ".join(SYSTEM_DESIGN_ARTIFACT_LABELS[section] for section in missing_sections)
            self.add_history(f"Перед /sd-feedback пустые system design секции: {labels}.")
        snapshot = build_system_design_feedback_loading_snapshot()
        self.apply_system_design_loading_snapshot(snapshot)
        self.render_all()

        def work() -> None:
            try:
                feedback = self.services.system_design.final_feedback(
                    self.system_design_scenario,
                    self.system_design_transcript,
                )
                last_error = getattr(self.services.llm, "last_error", None)
            except Exception as exc:
                feedback = (
                    "Fallback feedback: в следующей попытке явно пройди requirements, API, data model, "
                    "storage, scaling, consistency, observability и failure modes."
                )
                last_error = str(exc)
            self.dispatch_from_worker_thread(
                self.finish_system_design_feedback,
                feedback,
                last_error,
            )

        threading.Thread(target=work, daemon=True).start()

    def finish_system_design_feedback(self, feedback: str, last_error: str | None) -> None:
        snapshot = build_system_design_feedback_finish_snapshot(
            feedback=feedback,
            last_error=last_error,
        )
        self.apply_system_design_feedback_finish_snapshot(snapshot)
        self.save_system_design_final_feedback(feedback, source=snapshot.source)
        self.add_history(snapshot.history_message)
        self.render_all()

    def apply_system_design_loading_snapshot(self, snapshot: SystemDesignLoadingSnapshot) -> None:
        self.mode = snapshot.mode
        self.ollama_status = snapshot.ollama_status
        self.last_feedback = snapshot.last_feedback
        self.add_history(snapshot.history_message)

    def apply_system_design_auxiliary_finish_snapshot(
        self,
        snapshot: SystemDesignAuxiliaryFinishSnapshot,
    ) -> None:
        self.system_design_transcript.extend(snapshot.transcript_entries)
        self.ollama_status = snapshot.ollama_status
        self.last_feedback = snapshot.last_feedback
        self.mode = snapshot.mode

    def apply_system_design_feedback_finish_snapshot(
        self,
        snapshot: SystemDesignFeedbackFinishSnapshot,
    ) -> None:
        self.ollama_status = snapshot.ollama_status
        self.last_feedback = snapshot.last_feedback
        self.mode = snapshot.mode

    def save_system_design_final_feedback(self, feedback: str, source: str) -> None:
        topic_id = self.system_design_topic_id()
        save_feedback = getattr(self.services.system_design, "save_final_feedback", None)
        if topic_id is None or save_feedback is None:
            return
        session_id = self.session.id if self.session is not None else None
        try:
            saved = save_feedback(
                topic_id,
                feedback,
                scenario_id=self.system_design_scenario_id,
                session_id=session_id,
                source=source,
            )
        except Exception as exc:
            self.add_history(f"System design feedback artifact не сохранен: {exc}")
            return
        self.add_history(f"System design feedback artifact сохранен: #{saved.id}.")

    def exit_system_design(self) -> None:
        if self.mode not in {
            "system_design",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            self.add_history("Сейчас не system design mode.")
            self.render_all()
            return
        self.mode = self.system_design_return_mode
        self.topic = self.system_design_saved_topic
        self.question = self.system_design_saved_question
        self.current_answer = self.system_design_saved_answer
        self.pending_answer_text = self.system_design_saved_pending_answer
        self.showing_hint = self.system_design_saved_showing_hint
        self.showing_reference = self.system_design_saved_showing_reference
        if (
            self.mode
            in {
                "select_topic",
                "loading_system_design",
                "loading_system_design_checkpoint",
                "loading_system_design_pressure",
                "loading_system_design_feedback",
            }
            and self.session is not None
        ):
            self.mode = "answering"
            self.load_next_question()
            return
        self.add_history("Возврат к interview practice.")
        self.render_all()

    def exit_special_mode(self) -> None:
        if self.mode == "content":
            self.exit_content()
            return
        if self.mode == "questions_review":
            self.exit_questions_review()
            return
        if self.mode == "auto_curation_audit":
            self.exit_auto_curation_audit()
            return
        if self.mode == "artifacts":
            self.exit_artifacts()
            return
        if self.mode == "history":
            self.exit_history()
            return
        if self.mode == "notebook":
            self.exit_notebook()
            return
        if self.mode == "readiness":
            self.exit_readiness()
            return
        if self.mode in {"learning", "loading_learning"}:
            self.exit_learning()
            return
        if self.mode in {
            "system_design",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            self.exit_system_design()
            return
        self.add_history("Сейчас нет отдельного режима. Ты уже в interview practice.")
        self.render_all()

    def request_learning(self, user_message: str) -> None:
        snapshot = build_learning_request_snapshot(
            user_message=user_message,
            current_learning_topic_id=self.learning_topic_id,
            current_learning_dialog_session_id=self.learning_dialog_session_id,
            new_dialog_session_id=f"learn-{uuid4().hex[:12]}",
        )
        self.apply_learning_request_snapshot(snapshot)
        topic_id = snapshot.learning_topic_id
        topic = self.topic if self.topic is not None and self.topic.id == topic_id else None
        if topic is None and topic_id is not None:
            topic = self.services.repository.get_topic(topic_id)
        question = self.question if self.question is not None and self.question.topic_id == topic_id else None
        self.add_history(snapshot.history_message)
        self.render_all()

        def work() -> None:
            try:
                explanation = self.services.learning.explain(
                    user_message,
                    topic=topic,
                    question=question,
                )
                last_error = getattr(self.services.llm, "last_error", None)
            except Exception as exc:
                explanation = (
                    "ИИ-разбор недоступен. Быстрый fallback: сформулируй, какой термин непонятен, "
                    "сравни его с эталонным ответом и попробуй привести один backend-пример.\n"
                    f"Деталь: {exc}"
                )
                last_error = str(exc)
            self.call_from_thread(self.finish_learning, explanation, last_error)

        threading.Thread(target=work, daemon=True).start()

    def apply_learning_request_snapshot(self, snapshot: LearningRequestSnapshot) -> None:
        self.learning_topic_id = snapshot.learning_topic_id
        self.learning_dialog_session_id = snapshot.learning_dialog_session_id
        self.learning_question = snapshot.learning_question
        self.learning_pending_message = snapshot.learning_pending_message
        self.learning_dialog_offset = snapshot.learning_dialog_offset
        self.command_palette_visible = snapshot.command_palette_visible
        self.mode = snapshot.mode
        self.ollama_status = snapshot.ollama_status
        self.last_feedback = snapshot.last_feedback

    def finish_learning(self, explanation: str, last_error: str | None) -> None:
        snapshot = build_learning_finish_snapshot(
            explanation=explanation,
            learning_question=self.learning_question,
            last_error=last_error,
        )
        self.ollama_status = snapshot.ollama_status
        self.add_history(snapshot.history_message)
        self.save_learning_exchange(explanation)
        self.apply_learning_finish_snapshot(snapshot)
        self.render_all()

    def apply_learning_finish_snapshot(self, snapshot: LearningFinishSnapshot) -> None:
        self.ollama_status = snapshot.ollama_status
        self.learning_transcript.extend(snapshot.transcript_entries)
        self.learning_pending_message = snapshot.learning_pending_message
        self.learning_dialog_offset = snapshot.learning_dialog_offset
        self.last_feedback = snapshot.last_feedback
        self.mode = snapshot.mode

    def save_learning_exchange(self, explanation: str) -> None:
        if self.learning_topic_id is None or not hasattr(self.services.learning, "add_dialog_message"):
            return
        if self.learning_dialog_session_id is None:
            self.learning_dialog_session_id = f"learn-{uuid4().hex[:12]}"
        context_type = "practice_session" if self.session is not None and self.session.id is not None else "topic"
        context_id = str(self.session.id) if context_type == "practice_session" else str(self.learning_topic_id)
        try:
            self.services.learning.add_dialog_message(
                self.learning_topic_id,
                "user",
                self.learning_question,
                dialog_session_id=self.learning_dialog_session_id,
                context_type=context_type,
                context_id=context_id,
            )
            assistant_message = self.services.learning.add_dialog_message(
                self.learning_topic_id,
                "assistant",
                explanation,
                dialog_session_id=self.learning_dialog_session_id,
                context_type=context_type,
                context_id=context_id,
            )
            if hasattr(self.services.learning, "add_notebook_entry_from_learning_reply"):
                self.services.learning.add_notebook_entry_from_learning_reply(
                    self.learning_topic_id,
                    explanation,
                    title=self.learning_question,
                    dialog_session_id=self.learning_dialog_session_id,
                    source_message_id=assistant_message.id,
                )
        except Exception as exc:
            self.add_history(f"Не удалось сохранить учебный диалог: {exc}")

    def skip_question(self) -> None:
        if self.question is None:
            self.add_history("Нет текущего вопроса.")
            self.render_all()
            return
        self.skipped_count += 1
        if self.question.id is not None:
            self.skipped_question_ids.add(self.question.id)
        self.add_history(f"Вопрос #{self.question.id} пропущен.")
        self.load_next_question()

    def show_stats(self) -> None:
        self.command_palette_visible = False
        stats = self.services.stats.dashboard()
        lines = [
            "Статистика:",
            f"- сессий: {stats['session_count']}",
            f"- ответов: {stats['answered_count']}",
            f"- предложенная тема: {stats['suggested_topic'] or 'н/д'}",
        ]
        self.last_feedback = "\n".join(lines)
        self.add_history("Статистика показана в правой панели.")
        self.render_all()

    def show_commands(self) -> None:
        self.command_palette_visible = True
        self.last_feedback = command_palette_text()
        self.add_history("Command palette показана в правой панели.")
        self.render_all()

    def focus_notes(self) -> None:
        self.add_history("Фокус в notes editor. Esc вернет фокус в composer.")
        self.render_all()
        self.query_one("#notes_editor", TextArea).focus()

    def save_composer_note(self, command: str) -> None:
        command_line, _, body = command.partition("\n")
        title = command_line.removeprefix("/save-note").strip()
        note_body = body.strip()
        if not title or not note_body:
            self.add_history(
                "Использование: /save-note <title>, затем Shift+Enter и текст заметки в composer."
            )
            self.render_all()
            return

        topic_id, session_id, context_id = self.saved_note_context()
        now = datetime.now()
        try:
            note = self.services.repository.add_manual_note(
                ManualNote(
                    id=None,
                    topic_id=topic_id,
                    session_id=session_id,
                    context_type=SAVED_NOTE_CONTEXT_TYPE,
                    context_id=context_id,
                    title=title,
                    body=note_body,
                    created_at=now,
                    updated_at=now,
                )
            )
        except Exception as exc:
            self.add_history(f"Не удалось сохранить note: {exc}")
            self.render_all()
            return

        note_id = f"#{note.id}" if note.id is not None else ""
        self.last_feedback = "\n".join(
            [
                "Manual note сохранена",
                f"ID: {note.id if note.id is not None else 'н/д'}",
                f"Title: {title}",
                f"Context: {context_id}",
            ]
        )
        self.add_history(f"Manual note {note_id} сохранена: {one_line_preview(title, limit=60)}")
        self.render_all()

    def save_feedback_gap_to_notebook(self) -> None:
        if self.question is None or self.current_answer is None:
            self.add_history("Нет последнего ответа для /note-from-answer.")
            self.render_all()
            return
        if not self.current_answer.ai_feedback:
            self.add_history("Сначала запроси /feedback, потом используй /note-from-answer.")
            self.render_all()
            return

        answer_id = self.current_answer.id
        title = f"Gap from answer #{answer_id}: {one_line_preview(self.question.prompt, limit=70)}"
        body = feedback_gap_notebook_body(
            question=self.question,
            answer=self.current_answer,
            feedback=self.current_answer.ai_feedback,
            evaluation=self.latest_current_answer_evaluation(),
        )
        try:
            entry = self.services.repository.add_notebook_entry(
                NotebookEntry(
                    id=None,
                    topic_id=self.question.topic_id,
                    curriculum_subtopic_id=None,
                    dialog_session_id=f"answer:{answer_id}" if answer_id is not None else None,
                    source_message_id=None,
                    title=title,
                    body=body,
                    source="answer-feedback",
                    created_at=datetime.now(),
                )
            )
        except Exception as exc:
            self.add_history(f"Не удалось сохранить gap в notebook: {exc}")
            self.render_all()
            return
        self.add_history(f"Gap из последнего feedback сохранен в notebook: entry #{entry.id}.")
        self.render_all()

    def focus_input(self) -> None:
        self.query_one("#input_bar", Composer).focus()

    def end_session(self, reason: Literal["manual", "target_time"] = "manual") -> None:
        self.persist_notes_draft()
        self.finish_session_if_needed()
        self.mode = "ended"
        self.last_feedback = self.session_summary_text("Нажми Enter, чтобы закрыть TUI.")
        if reason == "target_time":
            self.add_history("Target time истек; сессия завершена.")
        else:
            self.add_history("Сессия завершена.")
        self.render_all()

    def finish_session_command(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        if self.session is None:
            self.add_history("Нет активной practice session для завершения.")
            self.render_all()
            return
        self.finish_session_if_needed()
        self.mode = "session_finished"
        self.last_feedback = self.session_summary_text(
            "Используй /practice для новой сессии, /history для просмотра истории или /quit для выхода."
        )
        self.add_history("Practice session завершена; outcome показан без выхода из TUI.")
        self.render_all()

    def prepare_new_practice_session(self) -> None:
        self.apply_practice_session_reset_snapshot(build_practice_session_reset_snapshot())
        self.add_history("Готов к новой practice session.")
        self.render_all()

    def apply_practice_session_reset_snapshot(self, snapshot: PracticeSessionResetSnapshot) -> None:
        self.baseline_session_id = None
        self.baseline_question_ids = ()
        self.mock_interview_session_id = None
        self.mock_interview_question_ids = ()
        self.mock_interview_sections = ()
        self.session = snapshot.session
        self.topic = snapshot.topic
        self.question = snapshot.question
        self.current_answer = snapshot.current_answer
        self.pending_answer_text = snapshot.pending_answer_text
        self.started_at = snapshot.started_at
        self.answered_count = snapshot.answered_count
        self.skipped_count = snapshot.skipped_count
        self.skipped_question_ids = set(snapshot.skipped_question_ids)
        self.showing_hint = snapshot.showing_hint
        self.showing_reference = snapshot.showing_reference
        self.command_palette_visible = snapshot.command_palette_visible
        self.mode = snapshot.mode

    def session_summary_text(self, next_step: str) -> str:
        elapsed = self.elapsed()
        outcome_text = self.session_outcome_text()
        return (
            f"Summary сессии\n"
            f"Ответов: {self.answered_count}\n"
            f"Пропущено: {self.skipped_count}\n"
            f"System design реплик: {len(self.system_design_transcript)}\n"
            f"Время: {format_duration(elapsed)}\n"
            f"Заметок: {notes_line_count(self.notes_text())}\n\n"
            f"{outcome_text}\n\n"
            f"{next_step}"
        )

    def finish_session_if_needed(self) -> Session | None:
        if self.session is not None and self.session.ended_at is None:
            is_baseline_session = self.baseline_session_id == self.session.id
            planned_baseline_questions = len(self.baseline_question_ids)
            finished = self.services.sessions.finish_session(self.session.id or 0, abandon_if_empty=True)
            self.session = Session(
                id=self.session.id,
                topic_id=self.session.topic_id,
                started_at=self.session.started_at,
                ended_at=finished.ended_at,
                target_minutes=self.session.target_minutes,
                status=finished.status,
            )
            if is_baseline_session and planned_baseline_questions:
                self.services.calibration.mark_baseline_session_outcome(
                    self.session.id or 0,
                    planned_questions=planned_baseline_questions,
                )
        return self.session

    def session_outcome_text(self) -> str:
        if self.session is None or self.session.id is None:
            return "\n".join(
                [
                    "[bold]Итог сессии[/bold]",
                    "Outcome не создан: session не была начата.",
                ]
            )
        outcome = self.services.repository.get_session_outcome_for_session(self.session.id)
        return format_session_outcome(outcome)

    def elapsed(self) -> timedelta:
        if self.started_at is None:
            return timedelta()
        return datetime.now() - self.started_at

    def refresh_topbar(self) -> None:
        if not self.is_mounted:
            return
        try:
            if self.should_finish_for_target_time():
                self.end_session(reason="target_time")
                return
            self.query_one("#topbar", Static).update(self.topbar_text())
        except Exception:
            return

    def should_finish_for_target_time(self) -> bool:
        if self.session is None or self.session.ended_at is not None or self.mode in {"ended", "session_finished"}:
            return False
        if self.mode in {
            "loading_feedback",
            "loading_learning",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            return False
        return self.elapsed() >= timedelta(minutes=max(0, self.session.target_minutes))

    def render_all(self) -> None:
        self.restore_notes_draft()
        self.apply_layout_mode()
        self.query_one("#topbar", Static).update(self.topbar_text())
        self.refresh_topics()
        self.query_one("#question", Static).update(self.question_text())
        self.query_one("#history", Static).update(self.history_text())
        input_widget = self.query_one("#input_bar", Composer)
        input_widget.placeholder = self.placeholder()

    def refresh_topics(self) -> None:
        topics = self.query_one("#topics", OptionList)
        topics.set_options(self.topic_options())

    def apply_layout_mode(self) -> None:
        focused = self.is_focused_mode()
        today_actions = self.query_one("#today_actions", Horizontal)
        left_panel = self.query_one("#left_panel", VerticalScroll)
        right_panel = self.query_one("#right_panel", Vertical)
        today_actions.styles.display = "block" if self.mode == "select_topic" else "none"
        left_panel.styles.display = "none" if focused else "block"
        right_panel.styles.display = "block" if self.has_right_panel() else "none"

    def has_right_panel(self) -> bool:
        if self.mode == "content":
            return True
        if self.mode == "questions_review":
            return True
        if self.mode == "auto_curation_audit":
            return True
        if self.mode == "artifacts":
            return True
        if self.mode == "history":
            return True
        if self.mode == "notebook":
            return True
        if self.mode == "readiness":
            return True
        if self.mode in {"learning", "loading_learning"}:
            return True
        if self.mode in {
            "system_design",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            return True
        return not self.is_focused_mode()

    def is_focused_mode(self) -> bool:
        return self.mode in {
            "content",
            "questions_review",
            "auto_curation_audit",
            "artifacts",
            "history",
            "notebook",
            "readiness",
            "learning",
            "loading_learning",
            "system_design",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }

    def topbar_text(self) -> str:
        topic = self.topic.title if self.topic else "выбор темы"
        if self.mode in {"learning", "loading_learning"}:
            topic = self.learning_topic_title()
        question = f"#{self.question.id}" if self.question else "нет вопроса"
        if self.mode in {
            "system_design",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            question = "system design"
        if self.mode == "history":
            question = "history"
        if self.mode == "questions_review":
            question = "questions review"
        if self.mode == "auto_curation_audit":
            question = "curation audit"
        if self.mode == "notebook":
            question = "notebook"
        if self.mode == "readiness":
            question = "readiness"
        elapsed = self.elapsed()
        target_minutes = self.session.target_minutes if self.session is not None else DEFAULT_SESSION_MINUTES
        remaining = timedelta(minutes=target_minutes) - elapsed
        if remaining.total_seconds() < 0:
            remaining = timedelta()
        return (
            f"Тема: {topic} | Вопрос: {question} | "
            f"Прошло: {format_duration(elapsed)} | Осталось: {format_duration(remaining)} | "
            f"Ollama: {self.ollama_status} | Content: {self.content_status_text()}"
        )

    def content_status_text(self) -> str:
        jobs = self.content_generation_jobs_snapshot()
        parts = [self.content_status]
        queue = self.content_queue_counts_text(jobs)
        if queue:
            parts.append(queue)
        latest = self.latest_content_result_text(jobs)
        if latest:
            parts.append(f"last {latest}")
        return "; ".join(parts)

    def content_generation_jobs_snapshot(self) -> list:
        list_jobs = getattr(self.services.content_generation, "list_jobs", None)
        if list_jobs is None:
            return []
        try:
            return list_jobs(limit=100)
        except Exception:
            return []

    def content_queue_counts_text(self, jobs: list) -> str:
        if not jobs:
            return ""
        queued = sum(1 for job in jobs if getattr(job, "status", "") == "queued")
        running = sum(1 for job in jobs if getattr(job, "status", "") == "running")
        failed = sum(1 for job in jobs if getattr(job, "status", "") == "failed")
        return f"queue q{queued}/r{running}/f{failed}"

    def latest_content_result_text(self, jobs: list) -> str:
        for job in jobs:
            status = getattr(job, "status", "")
            if status not in {"done", "failed"}:
                continue
            job_id = getattr(job, "id", None)
            kind = getattr(job, "kind", "job")
            if status == "failed":
                return f"failed #{job_id} {kind}"
            artifact = parse_content_result(getattr(job, "result_json", None))
            artifact_id = content_artifact_id_label(kind, artifact)
            if artifact_id:
                return f"done #{job_id} {kind} -> {artifact_id}"
            return f"done #{job_id} {kind}"
        return ""

    def topic_options(self) -> list[Option]:
        stats = self.services.stats.dashboard()
        counts = {item["title"]: item["answers"] for item in stats["topic_dynamics"]}
        suggested = self.suggested_practice_topic()
        options = [Option("[bold]Темы[/bold]", disabled=True)]
        for topic in self.services.questions.list_topics():
            marker = ">" if self.topic and topic.id == self.topic.id else " "
            suggested_marker = "*" if suggested is not None and topic.id == suggested.id else " "
            answers = counts.get(topic.title, 0)
            disabled = self.mode != "select_topic"
            options.append(
                Option(
                    f"{marker}{suggested_marker} {topic.id}. {topic.title}\n   ответов: {answers}",
                    id=f"topic-{topic.id}",
                    disabled=disabled,
                )
            )
        options.append(Option("", disabled=True))
        options.append(
            Option(
                "[dim]/accept-topic /commands /content /questions-review /generate-curriculum /history /history learning "
                "/pause-content /resume-content /materials /notebook(конспект) /readiness /mock-interview /notes /hint "
                "/answer /feedback /learn /system-design /practice /skip /stats /finish-session /quit[/dim]",
                disabled=True,
            )
        )
        return options

    def question_text(self) -> str:
        if self.mode == "select_topic":
            lines = [
                self.today_panel_text(),
                "",
                self.curriculum_startup_warning_text(),
                "",
                self.practice_topic_recommendation_text(),
                "",
                (
                    "[dim]Secondary: выбери тему слева или введи topic ID. "
                    "Команды: /readiness, /mock-interview, /generate-curriculum, /learn, /system-design, "
                    "Конспект обучения: /notebook, /commands, /notes.[/dim]"
                ),
            ]
            return "\n".join(line for line in lines if line)
        if self.mode == "session_finished":
            return self.last_feedback or self.session_outcome_text()
        if self.mode == "ended":
            return self.last_feedback or "Сессия завершена."
        if self.mode == "artifacts":
            return self.artifacts_text()
        if self.mode == "content":
            return self.content_jobs_text()
        if self.mode == "questions_review":
            return self.questions_review_text()
        if self.mode == "auto_curation_audit":
            return self.auto_curation_audit_text()
        if self.mode == "history":
            return self.history_browser_text()
        if self.mode == "notebook":
            return self.notebook_text()
        if self.mode == "readiness":
            return self.readiness_text()
        if self.mode in {"learning", "loading_learning"}:
            return self.learning_text()
        if self.mode in {
            "system_design",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            return self.system_design_text()
        if self.question is None:
            return "Нет текущего вопроса."
        lines = [
            f"[bold]Вопрос #{self.question.id}[/bold] [{self.question.difficulty}]",
        ]
        tag_text = self.current_question_tags_text()
        if tag_text:
            lines.append(f"[dim]Теги: {tag_text}[/dim]")
        competency_text = self.current_question_competencies_text()
        if competency_text:
            lines.append(f"[dim]Компетенции: {competency_text}[/dim]")
        baseline_progress_text = self.baseline_progress_text()
        if baseline_progress_text:
            lines.append(f"[dim]{baseline_progress_text}[/dim]")
        mock_interview_progress_text = self.mock_interview_progress_text()
        if mock_interview_progress_text:
            lines.append(f"[dim]{mock_interview_progress_text}[/dim]")
        lines.extend(["", self.question.prompt])
        status_text = self.practice_status_text()
        if status_text:
            lines.extend(["", "[bold]Статус[/bold]", status_text])
        if self.showing_hint:
            lines.extend(["", "[bold]Подсказка[/bold]", self.question.hint])
        if self.pending_answer_text:
            lines.extend(["", render_chat_message("Твой ответ", self.pending_answer_text)])
        self_score_text = self.practice_self_score_text()
        if self_score_text:
            lines.extend(["", "[bold]Самооценка[/bold]", self_score_text])
        rubric_scores_text = self.practice_rubric_scores_text()
        if rubric_scores_text:
            lines.extend(["", "[bold]Rubric scores[/bold]", rubric_scores_text])
        if self.showing_reference:
            lines.extend(["", render_chat_message("Эталонный ответ", self.question.reference_answer)])
        if self.mode == "loading_feedback":
            lines.extend(["", "[bold yellow]Генерирую feedback...[/bold yellow]"])
        feedback_warning = self.practice_feedback_quality_warning_text()
        if feedback_warning:
            lines.extend(["", feedback_warning])
        feedback_text = self.practice_feedback_text()
        if feedback_text:
            lines.extend(["", render_chat_message("AI feedback", feedback_text)])
        if self.mode == "scoring":
            lines.extend(["", "[bold yellow]Введи самооценку 1-5 или Enter, чтобы пропустить оценку.[/bold yellow]"])
        if self.mode == "answered":
            lines.extend(
                [
                    "",
                    "[dim]Enter - следующий вопрос, /feedback - AI feedback, "
                    "/recheck-feedback - строгая перепроверка, "
                    "/note-from-answer - сохранить gap, /stats - статистика.[/dim]",
                ]
            )
        return "\n".join(lines)

    def curriculum_startup_warning_text(self) -> str:
        try:
            status = self.services.curriculum.status()
        except Exception:
            return ""
        if status.curriculum_topic_count > 0:
            return ""
        return "\n".join(
            [
                "[bold yellow]Curriculum warning[/bold yellow]",
                "Generated curriculum отсутствует; база работает только на bootstrap/fallback.",
                "Используй `/generate-curriculum`, запусти `python -m interview_prep generate-seed` или проверь покрытие через `python -m interview_prep curriculum-status`.",
            ]
        )

    def today_panel_text(self) -> str:
        try:
            snapshot = self.services.readiness.snapshot()
            summary = snapshot.overall_summary
        except Exception:
            return "\n".join(
                [
                    "[bold cyan]Today[/bold cyan]",
                    "Recommended drill: н/д",
                    "Why this drill: readiness snapshot временно недоступен.",
                    "Expected time: 5 min triage",
                    "Primary action: /readiness - открыть dashboard и выбрать следующий drill.",
                ]
            )
        empty_state = self.today_empty_state_text(snapshot)
        if empty_state:
            return empty_state
        repeat_status = self.baseline_repeat_due_status()
        if repeat_status is not None:
            last_delta = (
                "н/д"
                if repeat_status.last_readiness_delta is None
                else f"{repeat_status.last_readiness_delta:+.2f}"
            )
            completed_at = (
                "-"
                if repeat_status.last_completed_at is None
                else repeat_status.last_completed_at.date().isoformat()
            )
            return "\n".join(
                [
                    "[bold cyan]Today[/bold cyan]",
                    "Recommended drill: повторная baseline practice session.",
                    (
                        "Why this drill: "
                        f"{escape(repeat_status.reason)} Последняя baseline: {completed_at}; "
                        f"readiness delta {last_delta}."
                    ),
                    "Expected time: 15-25 min",
                    "Primary action: Enter - начать повторную baseline session; ID темы слева - ручной выбор.",
                ]
            )
        drill = summary.recommended_drill
        if drill is None:
            return "\n".join(
                [
                    "[bold cyan]Today[/bold cyan]",
                    "Recommended drill: поддерживающая practice-сессия.",
                    "Why this drill: сохраненные evidence signals выглядят достаточно свежими.",
                    "Expected time: 10-15 min",
                    "Primary action: Enter - начать поддерживающую practice; ID темы слева - ручной выбор.",
                ]
            )
        return "\n".join(
            [
                "[bold cyan]Today[/bold cyan]",
                f"Recommended drill: {escape(drill.next_action)}",
                f"Why this drill: {self.today_drill_reason(drill)}",
                f"Expected time: {self.today_expected_time(drill)}",
                f"Primary action: {self.today_primary_action(drill)}",
            ]
        )

    def today_empty_state_action(self) -> str:
        try:
            snapshot = self.services.readiness.snapshot()
        except Exception:
            return ""
        if not self.today_snapshot_needs_empty_state(snapshot):
            return ""
        if self.generated_curriculum_missing():
            return "generate_curriculum"
        return "baseline_session"

    def today_snapshot_needs_empty_state(self, snapshot) -> bool:
        return (
            snapshot.competency_count > 0
            and snapshot.covered_competency_count == 0
            and snapshot.evaluated_competency_count == 0
        )

    def generated_curriculum_missing(self) -> bool:
        try:
            return self.services.curriculum.status().curriculum_topic_count == 0
        except Exception:
            return False

    def today_empty_state_text(self, snapshot) -> str:
        if not self.today_snapshot_needs_empty_state(snapshot):
            return ""
        if self.generated_curriculum_missing():
            return "\n".join(
                [
                    "[bold cyan]Today[/bold cyan]",
                    "Recommended drill: подготовить curriculum starter pack.",
                    (
                        "Why this drill: нет сохраненных ответов или rubric evidence; "
                        "generated curriculum еще не создан, поэтому сначала подготовь темы и вопросы."
                    ),
                    "Expected time: 5-10 min setup",
                    (
                        "Primary action: Enter - поставить /generate-curriculum; "
                        "после генерации начни первую baseline practice session."
                    ),
                ]
            )
        return "\n".join(
            [
                "[bold cyan]Today[/bold cyan]",
                "Recommended drill: первая baseline practice session.",
                (
                    "Why this drill: нет сохраненных ответов или rubric evidence; "
                    "curriculum уже создан, нужна первая practice-сессия для baseline signal."
                ),
                "Expected time: 15-25 min",
                "Primary action: Enter - начать первую baseline practice session; ID темы слева - ручной выбор.",
            ]
        )

    def baseline_repeat_due_status(self):
        try:
            status = self.services.calibration.baseline_repeat_status()
        except Exception:
            return None
        if status.last_session_id is None or not status.is_due:
            return None
        return status

    def start_due_baseline_repeat(self) -> None:
        if self.block_mode_switch_while_loading():
            return
        status = self.baseline_repeat_due_status()
        if status is None:
            try:
                current = self.services.calibration.baseline_repeat_status()
                self.add_history(current.reason)
            except Exception as exc:
                self.add_history(f"Baseline repeat status недоступен: {exc}")
            self.render_all()
            return
        self.start_baseline_session()

    def today_drill_reason(self, drill) -> str:
        if getattr(drill, "why_this_drill", ""):
            return escape(drill.why_this_drill)
        reasons = "; ".join(drill.reasons)
        competency = drill.competency
        return (
            f"{escape(competency.title)} ({escape(competency.slug)}) is the top readiness gap: "
            f"readiness {drill.readiness_score}/100; {escape(reasons)}"
        )

    def today_expected_time(self, drill) -> str:
        reasons = drill.reasons
        if "нет system design практики" in reasons:
            return "45-60 min"
        if "нет связанных вопросов" in reasons:
            return "5-10 min setup"
        if any(reason.startswith("низкая rubric оценка:") for reason in reasons):
            return "20-30 min"
        if any(reason.startswith("мало ответов:") for reason in reasons):
            return "15-25 min"
        if "нет rubric оценки" in reasons:
            return "15-25 min"
        return "10-20 min"

    def today_primary_action(self, drill) -> str:
        reasons = drill.reasons
        if "нет system design практики" in reasons:
            return "Enter - начать mock senior interview; ID темы слева - ручной practice."
        if "нет связанных вопросов" in reasons:
            return "Enter - подготовить curriculum; ID темы слева - ручной practice."
        if any(reason.startswith("низкая rubric оценка:") for reason in reasons):
            return "Enter - начать practice по рекомендованной теме; ID темы слева - ручной выбор."
        if any(reason.startswith("мало ответов:") for reason in reasons):
            return "Enter - начать practice по рекомендованной теме; ID темы слева - ручной выбор."
        if "нет rubric оценки" in reasons:
            return "Enter - ответить в TUI и сохранить rubric evaluation; ID темы слева - ручной выбор."
        return "Enter - начать рекомендованный practice drill; ID темы слева - ручной выбор."

    def current_question_tags_text(self) -> str:
        if self.question is None or self.question.id is None:
            return ""
        tags = self.services.questions.list_question_tags(self.question.id)
        return format_question_tags(tags) if tags else ""

    def current_question_competencies_text(self) -> str:
        if self.question is None or self.question.id is None:
            return ""
        competencies = self.services.questions.list_question_competencies(self.question.id)
        return format_question_competencies(competencies) if competencies else ""

    def baseline_progress_text(self) -> str:
        if self.session is None or self.baseline_session_id != self.session.id:
            return ""
        total = len(self.baseline_question_ids)
        if total <= 0:
            return ""
        answered = min(self.answered_count, total)
        remaining = max(0, total - answered)
        return f"Baseline progress: {answered}/{total} answered, {remaining} remaining."

    def mock_interview_progress_text(self) -> str:
        if self.session is None or self.mock_interview_session_id != self.session.id:
            return ""
        total = len(self.mock_interview_question_ids)
        if total <= 0 or len(self.mock_interview_sections) != total:
            return ""
        current_index = min(self.answered_count, total - 1)
        if self.question is not None and self.question.id in self.mock_interview_question_ids:
            current_index = self.mock_interview_question_ids.index(self.question.id)
        current_section = self.mock_interview_section_label(self.mock_interview_sections[current_index])
        remaining_start = max(self.answered_count, current_index + 1)
        remaining_sections = self.mock_interview_sections[remaining_start:]
        remaining_text = ", ".join(
            self.mock_interview_section_label(section)
            for section in remaining_sections
        ) or "none"
        return (
            f"Mock interview progress: section {current_section} "
            f"({current_index + 1}/{total}), remaining sections: {remaining_text}."
        )

    def mock_interview_section_label(self, section: str) -> str:
        labels = {
            "coding": "Coding",
            "theory": "Theory",
            "system_design": "System Design",
            "debugging": "Debugging",
        }
        return labels.get(section, section.replace("_", " ").title())

    def practice_self_score_text(self) -> str:
        if self.mode == "scoring":
            if self.current_answer is None:
                return ""
            return "Ожидает самооценку 1-5 или Enter, чтобы пропустить оценку."
        if self.mode not in {"answered", "loading_feedback"}:
            return ""
        if self.current_answer is None:
            return ""
        if self.current_answer.self_score is None:
            return "Без оценки."
        return f"{self.current_answer.self_score}/5"

    def practice_rubric_scores_text(self) -> str:
        if self.mode not in {"answered", "loading_feedback"}:
            return ""
        evaluation = self.latest_current_answer_evaluation()
        if evaluation is None:
            return ""
        return format_answer_evaluation(evaluation)

    def practice_feedback_quality_warning_text(self) -> str:
        if self.mode not in {"answered", "loading_feedback"}:
            return ""
        if self.current_answer is None or not self.current_answer.ai_feedback:
            return ""
        return format_feedback_quality_warning(self.latest_current_answer_evaluation())

    def latest_current_answer_evaluation(self) -> AnswerEvaluation | None:
        if self.current_answer is None or self.current_answer.id is None:
            return None
        evaluations = self.services.repository.list_answer_evaluations_for_answer(self.current_answer.id)
        return evaluations[0] if evaluations else None

    def practice_status_text(self) -> str:
        if self.mode == "answering":
            return "[dim]Ждет ответ. Подсказка доступна через /hint, эталон - через /answer.[/dim]"
        if self.mode == "scoring":
            return "[yellow]Ответ сохранен. Осталось указать самооценку 1-5 или нажать Enter.[/yellow]"
        if self.mode == "loading_feedback":
            return "[yellow]Ответ и самооценка сохранены. AI feedback генерируется.[/yellow]"
        if self.mode == "answered":
            score = self.current_answer.self_score if self.current_answer is not None else None
            score_text = f"самооценка {score}/5" if score else "без самооценки"
            if self.current_answer is not None and self.current_answer.ai_feedback:
                return (
                    f"[green]Ответ сохранен, {score_text}, AI feedback готов.[/green] "
                    "[dim]/recheck-feedback перепроверит его строже.[/dim]"
                )
            return f"[green]Ответ сохранен, {score_text}.[/green] [dim]/feedback запросит AI feedback.[/dim]"
        return ""

    def practice_feedback_text(self) -> str:
        if self.mode not in {"answered", "loading_feedback"}:
            return ""
        if self.current_answer is not None and self.current_answer.ai_feedback:
            return self.current_answer.ai_feedback
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            return ""
        return self.last_feedback

    def practice_topic_recommendation_text(self) -> str:
        recommendation = self.practice_topic_recommendation()
        if recommendation is None:
            suggested = self.suggested_practice_topic()
            if suggested is None:
                return "[bold]Предложенная следующая тема[/bold]\nПока нет данных для рекомендации."
            return "\n".join(
                [
                    "[bold]Предложенная следующая тема[/bold]",
                    f"{suggested.id}. {suggested.title} [{suggested.level}]",
                    suggested.description,
                    "Причина: базовая статистика по practice.",
                ]
            )
        topic = recommendation.topic
        lines = [
            "[bold]Предложенная следующая тема[/bold]",
            f"{topic.id}. {topic.title} [{topic.level}]",
            topic.description,
            f"Причина: {recommendation.reason}",
            f"Ответов по теме: {recommendation.answers}",
        ]
        if recommendation.avg_self_score is not None:
            lines.append(f"Средняя самооценка: {recommendation.avg_self_score:.1f}/5")
        if recommendation.last_answered_at is not None:
            lines.append(f"Последний ответ: {recommendation.last_answered_at.isoformat(timespec='minutes')}")
        return "\n".join(lines)

    def artifacts_text(self) -> str:
        topic_id = self.current_topic_id()
        topic_title = self.topic.title if self.topic is not None else "все темы"
        materials_topic_id = topic_id if self.materials_learning_filter == "current" else None
        materials = self.services.repository.list_learning_materials(topic_id=materials_topic_id, limit=10)
        scenario_topic_id = self.materials_scenario_topic_id(topic_id)
        scenarios = self.services.repository.list_system_design_scenarios(topic_id=scenario_topic_id, limit=10)
        materials_filter = "текущая тема" if self.materials_learning_filter == "current" else "все темы"
        scenarios_filter = "текущая тема" if self.materials_scenario_filter == "current" else "все темы"
        lines = [
            "[bold cyan]Materials[/bold cyan]",
            "",
            f"[bold]Контекст[/bold]: {topic_title}",
            f"[bold]Фильтр learning materials[/bold]: {materials_filter}",
            f"[bold]Фильтр system design scenarios[/bold]: {scenarios_filter}",
            "Выбери сохраненный artifact или запусти регенерацию.",
            "/material latest - открыть последнюю версию learning material текущей темы.",
            "/material <id> - открыть конкретную версию learning material в /learn.",
            "/preview-material <id|latest> - показать полный learning material без входа в /learn.",
            "/archive-material <id> confirm [reason] - скрыть неудачный learning material из списка.",
            "/materials current и /materials all - переключить learning materials.",
            "/materials scenarios current и /materials scenarios all - переключить system design scenarios.",
            "/scenario latest - открыть последнюю версию system design scenario текущего контекста.",
            "/scenario <id> - открыть конкретную версию system design scenario.",
            "/preview-scenario <id|latest> - показать полный system design scenario без входа в mock interview.",
            "/archive-scenario <id> confirm [reason] - скрыть неудачный system design scenario из списка.",
            "/regen-material и /regen-scenario - поставить новую background job.",
        ]
        if topic_id is not None:
            lines.append(f"/notebook topic {topic_id} - открыть конспект обучения текущей темы.")
        else:
            lines.append("/notebook all - открыть весь конспект обучения.")
        lines.extend(
            [
                "/notebook topic <id> - открыть конспект обучения темы выбранного artifact.",
                "/practice - вернуться назад.",
                "",
                "[bold]Learning materials[/bold]",
            ]
        )
        if not materials:
            lines.append("- пока нет сохраненных учебных материалов для текущей темы")
        else:
            for material in materials:
                preview = one_line_preview(material.body)
                version = self.learning_material_version_text(material)
                material_lines = [
                    f"- #{material.id} {material.title} [{version}, {material.source}, {material.created_at.isoformat(timespec='minutes')}]",
                    f"  {preview}",
                ]
                if self.materials_learning_filter == "all":
                    material_lines.append(f"  Тема: {self.learning_material_topic_label(material.topic_id)}")
                material_lines.append(
                    f"  Команды: /preview-material {material.id}, /material {material.id}, "
                    f"/archive-material {material.id} confirm, /notebook topic {material.topic_id}; "
                    "latest: /material latest"
                )
                lines.append("\n".join(material_lines))
        lines.extend(["", "[bold]System design scenarios[/bold]"])
        if not scenarios:
            lines.append("- пока нет сохраненных system design scenarios")
        else:
            for scenario in scenarios:
                preview = one_line_preview(scenario.scenario)
                focus = ", ".join(scenario.focus_areas[:6]) or "focus areas не указаны"
                version = self.system_design_scenario_version_text(scenario)
                scenario_lines = [
                    f"- #{scenario.id} {scenario.title} [{version}, {scenario.source}, {scenario.created_at.isoformat(timespec='minutes')}]\n"
                    f"  {preview}\n"
                    f"  Focus: {focus}"
                ]
                if self.materials_scenario_filter == "all":
                    scenario_lines.append(f"  Тема: {self.learning_material_topic_label(scenario.topic_id)}")
                scenario_lines.append(
                    f"  Команды: /preview-scenario {scenario.id}, /scenario {scenario.id}, "
                    f"/archive-scenario {scenario.id} confirm, /notebook topic {scenario.topic_id}; "
                    "latest: /scenario latest"
                )
                lines.append("\n".join(scenario_lines))
        if self.materials_preview:
            lines.extend(["", "[bold cyan]Artifact preview[/bold cyan]", self.materials_preview])
        return "\n".join(lines)

    def learning_material_version_text(self, material: LearningMaterial) -> str:
        versions = self.services.repository.list_learning_materials(topic_id=material.topic_id, limit=1000)
        return artifact_version_text(material.id, versions)

    def system_design_scenario_version_text(self, scenario: SystemDesignScenario) -> str:
        versions = self.services.repository.list_system_design_scenarios(topic_id=scenario.topic_id, limit=1000)
        return artifact_version_text(scenario.id, versions)

    def materials_scenario_topic_id(self, fallback_topic_id: int | None) -> int | None:
        if self.materials_scenario_filter == "all":
            return None
        system_topic = self.services.repository.find_topic_by_slug("system-design")
        return system_topic.id if system_topic is not None else fallback_topic_id

    def learning_material_topic_label(self, topic_id: int) -> str:
        topic = self.services.repository.get_topic(topic_id)
        return topic.title if topic is not None else f"topic #{topic_id}"

    def notebook_text(self) -> str:
        selected = self.selected_notebook_entry()
        entries = [selected] if selected is not None else self.filtered_notebook_entries(limit=30)
        manual_notes = self.filtered_manual_notes(limit=30) if selected is None else []
        lines = [
            "[bold cyan]Конспект обучения[/bold cyan]",
            "",
            "Read-only конспект сохраненных AI explanations, feedback gaps и manual notes.",
            self.notebook_filter_text(),
            "/notebook all - показать все записи.",
            "/notebook topic <id> - разбивка и фильтр по теме.",
            "/notebook subtopic <id> - разбивка и фильтр по curriculum subtopic.",
            "/notebook competency <slug> - фильтр по senior competency через linked questions.",
            "/notebook entry <id> - открыть одну запись полностью.",
            "/practice - вернуться назад.",
            "",
            "[bold]Разбивка по темам[/bold]",
        ]
        lines.extend(self.notebook_topic_navigation_lines())
        lines.extend(["", "[bold]Разбивка по subtopics[/bold]"])
        lines.extend(self.notebook_subtopic_navigation_lines())
        lines.extend(["", "[bold]AI explanations[/bold]"])
        if entries:
            for entry in entries:
                lines.extend(["", self.notebook_entry_text(entry, full=selected is not None)])
        else:
            lines.append("- пока нет AI explanations для выбранного фильтра")
        lines.extend(["", "[bold]Manual notes[/bold]"])
        if manual_notes:
            for note in manual_notes:
                lines.extend(["", self.manual_note_text(note)])
        elif selected is None:
            lines.append("- пока нет ручных заметок для выбранного фильтра")
        return "\n".join(lines)

    def notebook_filter_text(self) -> str:
        if self.notebook_selected_entry_id is not None:
            return f"[bold]Фильтр[/bold]: entry #{self.notebook_selected_entry_id}"
        if self.notebook_subtopic_filter is not None:
            subtopic = self.services.repository.get_curriculum_subtopic(self.notebook_subtopic_filter)
            title = subtopic.title if subtopic is not None else f"subtopic #{self.notebook_subtopic_filter}"
            return f"[bold]Фильтр[/bold]: subtopic #{self.notebook_subtopic_filter} {escape(title)}"
        if self.notebook_competency_filter is not None:
            competency = self.services.repository.find_competency_by_slug(self.notebook_competency_filter)
            title = competency.title if competency is not None else self.notebook_competency_filter
            return f"[bold]Фильтр[/bold]: competency {escape(self.notebook_competency_filter)} {escape(title)}"
        if self.notebook_topic_filter is not None:
            topic = self.services.repository.get_topic(self.notebook_topic_filter)
            title = topic.title if topic is not None else f"topic #{self.notebook_topic_filter}"
            return f"[bold]Фильтр[/bold]: topic #{self.notebook_topic_filter} {escape(title)}"
        return "[bold]Фильтр[/bold]: все topics/subtopics"

    def filtered_notebook_entries(self, limit: int = 30) -> list[NotebookEntry]:
        entries = self.services.repository.list_notebook_entries(
            topic_id=self.notebook_topic_filter,
            curriculum_subtopic_id=self.notebook_subtopic_filter,
            limit=max(limit, 200) if self.notebook_competency_filter is not None else limit,
        )
        if self.notebook_competency_filter is not None:
            topic_ids = self.notebook_competency_topic_ids()
            entries = [entry for entry in entries if entry.topic_id in topic_ids]
        return entries[:limit]

    def filtered_manual_notes(self, limit: int = 30) -> list[ManualNote]:
        if self.notebook_subtopic_filter is not None or self.notebook_selected_entry_id is not None:
            return []
        notes = self.services.repository.list_manual_notes(
            topic_id=self.notebook_topic_filter,
            limit=max(limit, 200),
        )
        if self.notebook_competency_filter is not None:
            topic_ids = self.notebook_competency_topic_ids()
            notes = [note for note in notes if note.topic_id in topic_ids]
        return [note for note in notes if self.is_notebook_manual_note(note)][:limit]

    def all_notebook_manual_notes(self, limit: int = 1000) -> list[ManualNote]:
        notes = self.services.repository.list_manual_notes(limit=limit)
        return [note for note in notes if self.is_notebook_manual_note(note)]

    def notebook_competency_topic_ids(self) -> set[int]:
        if self.notebook_competency_filter is None:
            return set()
        return set(self.services.repository.list_topic_ids_for_competency(self.notebook_competency_filter))

    def is_notebook_manual_note(self, note: ManualNote) -> bool:
        return note.context_type != NOTES_DRAFT_CONTEXT_TYPE and note.title != NOTES_DRAFT_TITLE

    def selected_notebook_entry(self) -> NotebookEntry | None:
        if self.notebook_selected_entry_id is None:
            return None
        return self.find_notebook_entry(self.notebook_selected_entry_id)

    def find_notebook_entry(self, entry_id: int) -> NotebookEntry | None:
        for entry in self.services.repository.list_notebook_entries(limit=1000):
            if entry.id == entry_id:
                return entry
        return None

    def notebook_topic_navigation_lines(self) -> list[str]:
        entries = self.services.repository.list_notebook_entries(limit=1000)
        notes = self.all_notebook_manual_notes(limit=1000)
        counts: dict[int, int] = {}
        for entry in entries:
            counts[entry.topic_id] = counts.get(entry.topic_id, 0) + 1
        for note in notes:
            if note.topic_id is not None:
                counts[note.topic_id] = counts.get(note.topic_id, 0) + 1
        if not counts:
            return ["- пока нет тем с записями конспекта"]
        lines = []
        for topic_id in sorted(counts):
            topic = self.services.repository.get_topic(topic_id)
            title = topic.title if topic is not None else f"Topic #{topic_id}"
            marker = ">" if self.notebook_topic_filter == topic_id and self.notebook_subtopic_filter is None else " "
            lines.append(f"{marker} /notebook topic {topic_id} - {escape(title)} ({counts[topic_id]})")
        return lines

    def notebook_subtopic_navigation_lines(self) -> list[str]:
        entries = self.services.repository.list_notebook_entries(topic_id=self.notebook_topic_filter, limit=1000)
        if self.notebook_competency_filter is not None:
            topic_ids = self.notebook_competency_topic_ids()
            entries = [entry for entry in entries if entry.topic_id in topic_ids]
        counts: dict[int, int] = {}
        for entry in entries:
            if entry.curriculum_subtopic_id is not None:
                counts[entry.curriculum_subtopic_id] = counts.get(entry.curriculum_subtopic_id, 0) + 1
        if not counts:
            return ["- для текущего фильтра нет записей с subtopic"]
        lines = []
        for subtopic_id in sorted(counts):
            subtopic = self.services.repository.get_curriculum_subtopic(subtopic_id)
            title = subtopic.title if subtopic is not None else f"Subtopic #{subtopic_id}"
            marker = ">" if self.notebook_subtopic_filter == subtopic_id else " "
            lines.append(f"{marker} /notebook subtopic {subtopic_id} - {escape(title)} ({counts[subtopic_id]})")
        return lines

    def notebook_entry_text(self, entry: NotebookEntry, full: bool = False) -> str:
        topic = self.services.repository.get_topic(entry.topic_id)
        topic_title = topic.title if topic is not None else f"topic #{entry.topic_id}"
        subtopic_label = "-"
        if entry.curriculum_subtopic_id is not None:
            subtopic = self.services.repository.get_curriculum_subtopic(entry.curriculum_subtopic_id)
            subtopic_label = subtopic.title if subtopic is not None else f"subtopic #{entry.curriculum_subtopic_id}"
        body = escape(render_llm_markdown(entry.body) if full else one_line_preview(entry.body))
        return "\n".join(
            [
                f"- Entry #{entry.id}: {escape(entry.title)}",
                f"  Topic: {escape(topic_title)} | Subtopic: {escape(subtopic_label)} | "
                f"Source: {escape(entry.source)} | Created: {entry.created_at.isoformat(timespec='minutes')}",
                f"  Команды: /notebook entry {entry.id}, /notebook topic {entry.topic_id}"
                + (
                    f", /notebook subtopic {entry.curriculum_subtopic_id}"
                    if entry.curriculum_subtopic_id is not None
                    else ""
                ),
                "",
                body,
            ]
        )

    def manual_note_text(self, note: ManualNote) -> str:
        topic_label = "global"
        if note.topic_id is not None:
            topic = self.services.repository.get_topic(note.topic_id)
            topic_label = topic.title if topic is not None else f"topic #{note.topic_id}"
        session_label = f"session #{note.session_id}" if note.session_id is not None else "no session"
        body = escape(one_line_preview(note.body))
        return "\n".join(
            [
                f"- Manual note #{note.id}: {escape(note.title)}",
                f"  Topic: {escape(topic_label)} | {session_label} | Updated: {note.updated_at.isoformat(timespec='minutes')}",
                "",
                body,
            ]
        )

    def readiness_text(self) -> str:
        try:
            snapshot = self.services.readiness.snapshot()
        except Exception as exc:
            return "\n".join(
                [
                    "[bold cyan]Readiness dashboard[/bold cyan]",
                    "",
                    "Readiness snapshot временно недоступен.",
                    f"Деталь: {escape(str(exc))}",
                    "/practice - вернуться назад.",
                ]
            )

        summary = snapshot.overall_summary
        signal = "н/д" if summary.signal_score is None else f"{summary.signal_score}/100"
        lines = [
            "[bold cyan]Readiness dashboard[/bold cyan]",
            "",
            "[bold]Overall senior readiness[/bold]",
            f"Signal: {signal}",
            f"Label: {escape(summary.label)}",
            escape(summary.summary),
            f"[dim]{escape(summary.caveat)}[/dim]",
            f"Evidence coverage: {snapshot.covered_competency_count}/{snapshot.competency_count} competencies",
            f"Rubric coverage: {snapshot.evaluated_competency_count}/{snapshot.competency_count} competencies",
        ]
        repeat_status = self.baseline_repeat_due_status()
        if repeat_status is not None:
            last_delta = (
                "н/д"
                if repeat_status.last_readiness_delta is None
                else f"{repeat_status.last_readiness_delta:+.2f}"
            )
            completed_at = (
                "-"
                if repeat_status.last_completed_at is None
                else repeat_status.last_completed_at.date().isoformat()
            )
            lines.extend(
                [
                    "",
                    "[bold]Calibration[/bold]",
                    "Repeat baseline: due now.",
                    f"Last baseline: session #{repeat_status.last_session_id}, {completed_at}, delta {last_delta}.",
                    "Action: /baseline-repeat - начать повторную baseline session.",
                ]
            )
        if snapshot.weekly_trend:
            lines.extend(["", "[bold]Weekly readiness trend[/bold]"])
            for point in snapshot.weekly_trend:
                lines.append(
                    f"- {point.week_start.isoformat()}..{point.week_end.isoformat()}: "
                    f"sessions {point.session_count}; avg delta {point.avg_readiness_delta:+.2f}; "
                    f"total {point.total_readiness_delta:+.2f}"
                )
        lines.extend(["", "[bold]Top gaps[/bold]"])
        if not summary.top_gaps:
            lines.append("- явных gaps по текущим rules нет")
        else:
            for gap in summary.top_gaps:
                reasons = "; ".join(gap.reasons)
                lines.append(
                    f"- {escape(gap.competency.title)} ({escape(gap.competency.slug)}): "
                    f"{gap.readiness_score}/100; {escape(reasons)}"
                )
                lines.append(f"  Next action: {escape(gap.next_action)}")
        lines.extend(["", "[bold]Must fix before interview[/bold]"])
        if not summary.top_gaps:
            lines.append("- явных обязательных drills по текущим rules нет")
        else:
            for index, gap in enumerate(summary.top_gaps, start=1):
                lines.append(f"{index}. {escape(gap.must_fix_drill)}")

        gap_actions = {gap.competency.slug: gap.next_action for gap in summary.top_gaps}
        lines.extend(["", "[bold]Competencies[/bold]"])
        if not snapshot.competencies:
            lines.append("- competency taxonomy пока не заполнена")
        else:
            for aggregate in snapshot.competencies:
                lines.append(self.readiness_competency_text(aggregate, gap_actions))
        lines.extend(["", "/practice - вернуться назад. /stats - краткая CLI-style статистика."])
        return "\n".join(lines)

    def readiness_competency_text(self, aggregate, gap_actions: dict[str, str]) -> str:
        competency = aggregate.competency
        slug = competency.slug
        rubric = "н/д" if aggregate.avg_rubric_score is None else f"{aggregate.avg_rubric_score:.1f}/5"
        self_score = "н/д" if aggregate.avg_self_score is None else f"{aggregate.avg_self_score:.1f}/5"
        last_answered = (
            aggregate.last_answered_at.isoformat(timespec="minutes")
            if aggregate.last_answered_at is not None
            else "-"
        )
        reasons = "; ".join(aggregate.readiness_reasons)
        next_action = gap_actions.get(slug) or readiness_next_action_for_aggregate(aggregate)
        return "\n".join(
            [
                f"- [bold]{escape(competency.title)}[/bold] ({escape(slug)})",
                f"  Score: {aggregate.readiness_score}/100",
                (
                    "  Evidence: "
                    f"answers {aggregate.answer_count}; rubric {aggregate.evaluated_answer_count}; "
                    f"coverage {aggregate.answered_questions}/{aggregate.linked_questions}"
                ),
                f"  Avg: self {self_score}; rubric {rubric}; last {last_answered}",
                f"  Reasons: {escape(reasons)}",
                f"  Next action: {escape(next_action)}",
            ]
        )

    def learning_text(self) -> str:
        topic = self.learning_topic_title()
        lines = [
            "[bold cyan]Режим обучения[/bold cyan]",
            "",
            f"[bold]Тема[/bold]: {topic}",
            "Пиши, что непонятно, обычным текстом. ИИ отвечает как mentor, а не как интервьюер.",
            "/practice - вернуться к вопросам, /commands - список команд, /quit - завершить.",
        ]
        if self.question is not None:
            lines.extend(["", "[bold]Контекст текущего вопроса[/bold]", self.question.prompt])
        if self.generated_learning_material:
            lines.extend(["", "[bold]Подготовленный материал[/bold]", render_llm_markdown(self.generated_learning_material)])
        elif self.content_worker_running:
            lines.extend(["", "[dim]Фоновая генерация учебного материала запущена.[/dim]"])
        lines.extend(["", "[bold]Учебный диалог[/bold]"])
        if not self.learning_transcript and not self.learning_pending_message:
            lines.append("Диалог еще не начат. Напиши, что именно непонятно.")
        else:
            visible_transcript, navigation = self.visible_learning_transcript()
            if navigation:
                lines.append(navigation)
            for role, message in visible_transcript:
                lines.extend(["", render_chat_message(role, message)])
            if self.learning_pending_message and self.learning_dialog_offset == 0:
                lines.extend(["", render_chat_message("Ты", self.learning_pending_message)])
        if self.mode == "loading_learning":
            lines.extend(["", "[bold yellow]ИИ готовит объяснение...[/bold yellow]"])
        return "\n".join(lines)

    def visible_learning_transcript(self) -> tuple[list[tuple[str, str]], str]:
        total = len(self.learning_transcript)
        if total <= self.learning_dialog_window_size:
            return self.learning_transcript, ""
        offset = min(self.learning_dialog_offset, total - self.learning_dialog_window_size)
        end = total - offset
        start = max(0, end - self.learning_dialog_window_size)
        visible = self.learning_transcript[start:end]
        commands = []
        if start > 0:
            commands.append("/learn-older")
        if end < total:
            commands.append("/learn-newer")
        command_text = ", ".join(commands)
        navigation = f"[dim]Показаны реплики {start + 1}-{end} из {total}."
        if command_text:
            navigation += f" Навигация: {command_text}."
        navigation += "[/dim]"
        return visible, navigation

    def system_design_text(self) -> str:
        lines = [
            "[bold cyan]System Design Mock Interview[/bold cyan]",
            "",
            "[bold]Сценарий[/bold]",
            render_llm_markdown(self.system_design_scenario),
        ]
        if self.generated_system_design_focus_areas:
            lines.extend(["", "[bold]Focus areas[/bold]", ", ".join(self.generated_system_design_focus_areas)])
        if self.content_worker_running and not self.generated_system_design_scenario:
            lines.extend(["", "[dim]Фоновая генерация system design scenario запущена.[/dim]"])
        lines.extend([
            "",
            "[bold]Как работать[/bold]",
            "Пиши свои решения и уточнения обычным текстом. ИИ будет отвечать как интервьюер.",
            "/req, /api, /data, /decision, /risk фиксируют артефакты дизайна.",
            "/sd-checkpoint - короткий checkpoint, /sd-pressure - pressure follow-up, "
            "/sd-feedback - итоговый feedback.",
            "/practice - назад к вопросам, /quit - завершить.",
            "",
            "[bold]Design artifacts[/bold]",
            self.system_design_artifacts_text(),
            "",
        ])
        missing_sections = self.system_design_missing_sections_text()
        if missing_sections:
            lines.extend([missing_sections, ""])
        lines.append("[bold]Transcript[/bold]")
        if not self.system_design_transcript and not self.system_design_pending_message:
            lines.append("Диалог еще не начат. Начни с requirements или уточняющего вопроса интервьюеру.")
        else:
            for role, message in self.system_design_transcript[-10:]:
                lines.extend(["", render_chat_message(role, message)])
            if self.system_design_pending_message:
                lines.extend(["", render_chat_message("Кандидат", self.system_design_pending_message)])
        if self.mode == "loading_system_design":
            lines.extend(["", "[bold yellow]Интервьюер генерирует следующий вопрос...[/bold yellow]"])
        if self.mode == "loading_system_design_checkpoint":
            lines.extend(["", "[bold yellow]Генерирую короткий system design checkpoint...[/bold yellow]"])
        if self.mode == "loading_system_design_pressure":
            lines.extend(["", "[bold yellow]Генерирую pressure follow-up question...[/bold yellow]"])
        if self.mode == "loading_system_design_feedback":
            lines.extend(["", "[bold yellow]Генерирую итоговый system design feedback...[/bold yellow]"])
        if self.last_feedback:
            lines.extend(["", "[bold]Feedback / следующий вопрос[/bold]"])
            if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
                lines.append(self.last_feedback)
            else:
                role = "ИИ" if self.last_feedback.startswith("Итоговый system design feedback") else "Интервьюер"
                lines.append(render_chat_message(role, self.last_feedback))
        return "\n".join(lines)

    def missing_system_design_feedback_sections(self) -> list[str]:
        return [
            section
            for section in SYSTEM_DESIGN_FEEDBACK_REQUIRED_SECTIONS
            if not any(item.strip() for item in self.system_design_artifacts.get(section, []))
        ]

    def system_design_missing_sections_text(self) -> str:
        missing_sections = self.missing_system_design_feedback_sections()
        if not missing_sections:
            return ""
        labels = ", ".join(SYSTEM_DESIGN_ARTIFACT_LABELS[section] for section in missing_sections)
        return (
            "[bold yellow]Missing sections before /sd-feedback[/bold yellow]\n"
            f"Пустые секции: {labels}.\n"
            "Заполни их через /req, /api, /data и /risk, чтобы итоговый feedback был полезнее."
        )

    def system_design_artifacts_text(self) -> str:
        lines: list[str] = []
        for key, label in SYSTEM_DESIGN_ARTIFACT_LABELS.items():
            items = self.system_design_artifacts.get(key, [])
            lines.append(f"[bold]{label}[/bold]")
            if not items:
                lines.append("- пока пусто")
            else:
                lines.extend(f"- {item}" for item in items[-5:])
        return "\n".join(lines)

    def history_text(self) -> str:
        if self.mode in {"answering", "scoring", "answered", "loading_feedback"}:
            return self.practice_side_panel_text()
        if self.mode == "content":
            return self.content_jobs_side_panel_text()
        if self.mode == "questions_review":
            return self.questions_review_side_panel_text()
        if self.mode == "auto_curation_audit":
            return self.auto_curation_audit_side_panel_text()
        if self.mode == "artifacts":
            return self.materials_side_panel_text()
        if self.mode == "history":
            return self.history_browser_side_panel_text()
        if self.mode == "notebook":
            return self.notebook_side_panel_text()
        if self.mode == "readiness":
            return self.readiness_side_panel_text()
        if self.mode in {"learning", "loading_learning"}:
            return self.learning_side_panel_text()
        if self.mode in {
            "system_design",
            "loading_system_design",
            "loading_system_design_checkpoint",
            "loading_system_design_pressure",
            "loading_system_design_feedback",
        }:
            return self.system_design_side_panel_text()
        title = "[bold]История, feedback, palette[/bold]"
        lines = [title, ""]
        lines.extend(self.history[-12:])
        if self.last_feedback:
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def practice_side_panel_text(self) -> str:
        lines = [
            "[bold]Practice[/bold]",
        ]
        baseline_progress_text = self.baseline_progress_text()
        if baseline_progress_text:
            lines.extend(["", baseline_progress_text])
        mock_interview_progress_text = self.mock_interview_progress_text()
        if mock_interview_progress_text:
            lines.extend(["", mock_interview_progress_text])
        lines.extend(
            [
                "",
                "[bold]Следующее действие[/bold]",
                self.practice_next_action_text(),
                "",
                "[bold]Последние события[/bold]",
            ]
        )
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def practice_next_action_text(self) -> str:
        if self.mode == "answering":
            return "Напиши ответ обычным текстом. /hint - подсказка, /answer - эталон."
        if self.mode == "scoring":
            return "Введи самооценку 1-5 или нажми Enter, чтобы пропустить оценку."
        if self.mode == "loading_feedback":
            return "Дождись AI feedback. После готовности Enter перейдет к следующему вопросу."
        if self.mode == "answered":
            if self.current_answer is not None and self.current_answer.ai_feedback:
                return (
                    "Нажми Enter, чтобы перейти к следующему вопросу; "
                    "/note-from-answer сохранит gap, /recheck-feedback запустит строгую проверку."
                )
            return "Нажми Enter для следующего вопроса или /feedback для AI feedback."
        return "Продолжай текущий practice flow."

    def content_jobs_text(self) -> str:
        jobs_by_status = self.content_jobs_by_status(limit=12)
        queued = jobs_by_status["queued"]
        running = jobs_by_status["running"]
        failed = jobs_by_status["failed"]
        lines = [
            "[bold cyan]Content jobs[/bold cyan]",
            "",
            "Фоновая генерация curriculum, вопросов, эталонных ответов, учебных материалов и system design scenarios.",
            f"TUI worker: {self.content_worker_state_text()}",
            "/generate-curriculum - поставить безопасную фоновую генерацию curriculum starter pack.",
            "/pause-content - поставить TUI worker на паузу без удаления jobs.",
            "/resume-content - снять паузу и запустить TUI worker.",
            "/retry-job <id> - вернуть failed job в очередь и запустить worker.",
            "/practice - вернуться назад.",
            "",
            "[bold]Summary[/bold]",
            f"Queued: {len(queued)}",
            f"Running: {len(running)}",
            f"Failed: {len(failed)}",
        ]
        lines.extend(["", self.content_job_section_text("Queued", queued)])
        lines.extend(["", self.content_job_section_text("Running", running)])
        lines.extend(["", self.content_job_section_text("Failed", failed)])
        return "\n".join(lines)

    def content_job_section_text(self, title: str, jobs: list[ContentGenerationJob]) -> str:
        lines = [f"[bold]{title}[/bold]"]
        if not jobs:
            lines.append("- нет задач")
            return "\n".join(lines)
        for job in jobs:
            lines.append(self.content_job_line(job))
        return "\n".join(lines)

    def content_job_line(self, job: ContentGenerationJob) -> str:
        payload = parse_content_payload(job.payload_json)
        topic_id = payload.get("topic_id")
        topic = self.content_job_topic_label(topic_id)
        note = one_line_preview(str(payload.get("note") or ""), limit=120)
        retry = content_job_retry_text(payload)
        lines = [
            f"- #{job.id} [{job.kind}] {job.status}",
            f"  Тема: {topic}",
            f"  Created: {job.created_at.isoformat(timespec='minutes')} | Updated: {job.updated_at.isoformat(timespec='minutes')}",
        ]
        if note:
            lines.append(f"  Note: {note}")
        if retry:
            lines.append(f"  Retry: {retry}")
        if job.error:
            lines.append(f"  Error: {one_line_preview(job.error, limit=140)}")
        return "\n".join(lines)

    def content_job_topic_label(self, raw_topic_id: object) -> str:
        try:
            topic_id = int(raw_topic_id)
        except (TypeError, ValueError):
            return "не указана"
        topic = self.services.repository.get_topic(topic_id)
        return topic.title if topic is not None else f"topic #{topic_id}"

    def content_jobs_by_status(self, limit: int = 12) -> dict[str, list[ContentGenerationJob]]:
        list_jobs = getattr(self.services.content_generation, "list_jobs", None)
        if list_jobs is None:
            return {"queued": [], "running": [], "failed": []}
        jobs_by_status: dict[str, list[ContentGenerationJob]] = {}
        for status in ("queued", "running", "failed"):
            try:
                jobs_by_status[status] = list_jobs(status=status, limit=limit)
            except Exception:
                jobs_by_status[status] = []
        return jobs_by_status

    def content_jobs_side_panel_text(self) -> str:
        jobs_by_status = self.content_jobs_by_status(limit=100)
        lines = [
            "[bold]Content jobs[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            "Сгенерируй curriculum через /generate-curriculum, поставь worker на паузу через /pause-content или верни failed job в queued через /retry-job <id>.",
            "",
            "[bold]Состояние очереди[/bold]",
            f"TUI worker: {self.content_worker_state_text()}",
            f"Queued: {len(jobs_by_status['queued'])}",
            f"Running: {len(jobs_by_status['running'])}",
            f"Failed: {len(jobs_by_status['failed'])}",
            f"Topbar: {self.content_status_text()}",
            "",
            "[bold]Команды[/bold]",
            "/content",
            "/generate-curriculum",
            "/pause-content",
            "/resume-content",
            "/retry-job <id>",
            "/materials",
            "/practice",
            "",
            "[bold]Последние события[/bold]",
        ]
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def questions_review_text(self) -> str:
        questions = self.services.questions.list_pending_review_questions()
        topics = {topic.id: topic.title for topic in self.services.questions.list_topics()}
        lines = [
            "[bold cyan]Generated question audit queue[/bold cyan]",
            "",
            "Automated curation is the happy path; this screen shows pending_review exceptions for audit.",
            "Manual accept/archive are audit overrides and never delete the question row.",
            "",
            "[bold]Команды[/bold]",
            "/questions-review - обновить список.",
            "/questions-review accept <id> - manual approve после audit.",
            "/questions-review archive <id> - manual archive после audit.",
            "/practice - вернуться назад.",
            "",
            f"[bold]Pending generated questions[/bold]: {len(questions)}",
        ]
        if not questions:
            lines.append("- pending generated questions не найдены")
            return "\n".join(lines)
        for question in questions[:20]:
            lines.append(
                self.questions_review_item_text(
                    question,
                    topics.get(question.topic_id, f"topic #{question.topic_id}"),
                )
            )
        if len(questions) > 20:
            lines.append(f"- еще {len(questions) - 20} pending questions скрыто лимитом экрана")
        return "\n".join(lines)

    def questions_review_item_text(self, question: Question, topic_title: str) -> str:
        prompt = one_line_preview(question.prompt, limit=180)
        hint = one_line_preview(question.hint, limit=140)
        reference = one_line_preview(question.reference_answer, limit=180)
        source_retrieved_at = (
            question.source_retrieved_at.isoformat(timespec="seconds")
            if question.source_retrieved_at
            else "-"
        )
        category_hints = ", ".join(question.source_category_hints) or "-"
        quality_flags = ", ".join(generated_question_quality_flags(question.prompt)) or "-"
        lines = [
            f"- #{question.id} {escape(topic_title)} [{escape(question.difficulty)}]",
            f"  Source: {escape(question.source)} | Status: {escape(question.source_quality_status)}",
            (
                "  Source metadata: "
                f"url={escape(question.source_url or '-')} retrieved_at={escape(source_retrieved_at)}"
            ),
            f"  Category hints: {escape(category_hints)}",
            f"  Frequency hint: {escape(question.source_frequency_hint or '-')}",
            f"  Quality flags: {escape(quality_flags)}",
        ]
        latest_audit = self.latest_question_auto_curation_audit(question.id)
        if latest_audit is not None:
            lines.extend(self.questions_review_audit_context_lines(question, latest_audit))
        lines.extend(
            [
                f"  Prompt: {escape(prompt)}",
                f"  Hint: {escape(hint)}",
                f"  Reference: {escape(reference)}",
                (
                    f"  Audit actions: /questions-review accept {question.id}; "
                    f"/questions-review archive {question.id}"
                ),
            ]
        )
        return "\n".join(lines)

    def latest_question_auto_curation_audit(
        self,
        question_id: int | None,
    ) -> QuestionAutoCurationAudit | None:
        if question_id is None:
            return None
        audits = self.services.repository.list_question_auto_curation_audits(question_id=question_id, limit=1)
        return audits[0] if audits else None

    def questions_review_audit_context_lines(
        self,
        question: Question,
        audit: QuestionAutoCurationAudit,
    ) -> list[str]:
        source_evidence = audit.curator_source_evidence or "-"
        undo_hint = (
            f"questions-source undo --question {question.id} restores {audit.previous_status} "
            f"if current status is still {audit.resulting_status}"
        )
        if question.source_quality_status != audit.resulting_status:
            undo_hint = (
                f"inspect first: latest audit expected current={audit.resulting_status}, "
                f"actual={question.source_quality_status}"
            )
        return [
            (
                f"  Latest auto-curation audit: #{audit.id or '-'} decision={escape(audit.decision)} "
                f"confidence={audit.confidence:.2f}"
            ),
            f"  Curator rationale: {escape(audit.rationale)}",
            f"  Source evidence: {escape(source_evidence)}",
            f"  Undo hint: {escape(undo_hint)}",
        ]

    def questions_review_side_panel_text(self) -> str:
        questions = self.services.questions.list_pending_review_questions()
        topic_ids = {question.topic_id for question in questions}
        audit_context_count = sum(
            1
            for question in questions
            if self.latest_question_auto_curation_audit(question.id) is not None
        )
        lines = [
            "[bold]Question audit queue[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            (
                "Проверь pending_review exception; manual approve/archive нужен только после audit."
                if questions
                else "Pending generated questions нет; automated curation не требует ручного действия."
            ),
            "",
            "[bold]Сводка[/bold]",
            f"Pending: {len(questions)}",
            f"Тем в очереди: {len(topic_ids)}",
            f"С audit context: {audit_context_count}",
            "",
            "[bold]Команды[/bold]",
            "/questions-review",
            "/questions-review accept <id>",
            "/questions-review archive <id>",
            "/practice",
            "",
            "[bold]Последние события[/bold]",
        ]
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def auto_curation_audit_rows(self, limit: int = 20) -> list[QuestionAutoCurationAudit]:
        return self.services.repository.list_question_auto_curation_audits(
            question_id=self.auto_curation_audit_question_filter,
            topic_id=self.auto_curation_audit_topic_filter,
            resulting_status=self.auto_curation_audit_status_filter,
            limit=limit,
        )

    def auto_curation_audit_filter_text(self) -> str:
        filters = []
        if self.auto_curation_audit_question_filter is not None:
            filters.append(f"question #{self.auto_curation_audit_question_filter}")
        if self.auto_curation_audit_topic_filter is not None:
            filters.append(f"topic #{self.auto_curation_audit_topic_filter}")
        if self.auto_curation_audit_status_filter is not None:
            filters.append(f"status {self.auto_curation_audit_status_filter}")
        return ", ".join(filters) if filters else "all decisions"

    def auto_curation_audit_text(self) -> str:
        try:
            audits = self.auto_curation_audit_rows(limit=20)
        except ValueError as exc:
            return f"[bold red]Auto-curation audit error[/bold red]\n\n{escape(str(exc))}"
        topics = {topic.id: topic.title for topic in self.services.questions.list_topics()}
        lines = [
            "[bold cyan]Auto-curation audit[/bold cyan]",
            "",
            "Read-only список решений source-backed auto-curation.",
            f"[bold]Фильтр[/bold]: {escape(self.auto_curation_audit_filter_text())}",
            "",
            "[bold]Команды[/bold]",
            "/curation-audit - все последние decisions.",
            "/curation-audit topic <id> - фильтр по теме.",
            "/curation-audit question <id> - фильтр по вопросу.",
            "/curation-audit status <accepted|archived|pending_auto_review> - фильтр по итоговому статусу.",
            "/questions-source audit ... - alias для этого экрана.",
            "CLI: questions-source undo [--question <id>] - откатить последний decision без удаления audit row.",
            "/practice - вернуться назад.",
            "",
            f"[bold]Auto-curation decisions[/bold]: {len(audits)}",
        ]
        if not audits:
            lines.append("- сохраненные auto-curation decisions не найдены")
            return "\n".join(lines)
        for audit in audits:
            question = self.services.repository.get_question(audit.question_id)
            topic_title = topics.get(question.topic_id) if question else None
            lines.append("")
            lines.append(self.auto_curation_audit_item_text(audit, question, topic_title))
        return "\n".join(lines)

    def auto_curation_audit_item_text(
        self,
        audit: QuestionAutoCurationAudit,
        question: Question | None,
        topic_title: str | None,
    ) -> str:
        current_status = question.source_quality_status if question else "missing"
        topic_label = topic_title or (f"topic #{question.topic_id}" if question else "unknown")
        prompt = one_line_preview(question.prompt if question else "question row is unavailable", limit=180)
        retrieved_at = audit.source_retrieved_at.isoformat(timespec="minutes") if audit.source_retrieved_at else "unknown"
        lines = [
            (
                f"- #{audit.id or '-'} question=#{audit.question_id} {escape(topic_label)} "
                f"decision={escape(audit.decision)} confidence={audit.confidence:.2f}"
            ),
            f"  Status: {escape(audit.previous_status)} -> {escape(audit.resulting_status)} current={escape(current_status)}",
            f"  Curator: {escape(audit.curator_model)} version={escape(audit.curator_version)} score={audit.curator_score or '-'}",
            f"  Source: {escape(audit.source_url or '-')} retrieved_at={escape(retrieved_at)}",
            f"  Category hints: {escape(', '.join(audit.source_category_hints) or '-')}",
            f"  Frequency: {escape(audit.source_frequency_hint or '-')}",
            f"  Quality flags: {escape(', '.join(audit.quality_flags) or '-')}",
            f"  Source evidence: {escape(audit.curator_source_evidence or '-')}",
            f"  Rationale: {escape(audit.rationale)}",
            f"  Prompt: {escape(prompt)}",
        ]
        if audit.duplicate_of_id is not None:
            lines.insert(2, f"  Duplicate of: #{audit.duplicate_of_id}")
        return "\n".join(lines)

    def auto_curation_audit_side_panel_text(self) -> str:
        audits = self.auto_curation_audit_rows(limit=100)
        accepted = sum(1 for audit in audits if audit.resulting_status == QUESTION_SOURCE_QUALITY_ACCEPTED)
        archived = sum(1 for audit in audits if audit.resulting_status == QUESTION_SOURCE_QUALITY_ARCHIVED)
        quarantined = sum(
            1 for audit in audits if audit.resulting_status == QUESTION_SOURCE_QUALITY_PENDING_AUTO_REVIEW
        )
        topic_count = len(
            {
                question.topic_id
                for question in (
                    self.services.repository.get_question(audit.question_id) for audit in audits
                )
                if question is not None
            }
        )
        lines = [
            "[bold]Auto-curation audit[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            "Проверь автоматические decisions и при необходимости откати последний через CLI undo.",
            "",
            "[bold]Фильтр[/bold]",
            self.auto_curation_audit_filter_text(),
            "",
            "[bold]Сводка[/bold]",
            f"Decisions: {len(audits)}",
            f"Accepted: {accepted}",
            f"Archived: {archived}",
            f"Quarantined: {quarantined}",
            f"Тем в audit: {topic_count}",
            "",
            "[bold]Команды[/bold]",
            "/curation-audit",
            "/curation-audit topic <id>",
            "/curation-audit question <id>",
            "/curation-audit status accepted",
            "CLI: questions-source undo --question <id>",
            "/practice",
            "",
            "[bold]Последние события[/bold]",
        ]
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def content_worker_state_text(self) -> str:
        if self.content_worker_paused:
            return "paused"
        if self.content_worker_running:
            return "running"
        return "ready"

    def history_browser_text(self) -> str:
        if self.history_browser_view == "system_design":
            return self.system_design_history_browser_text()

        if self.history_browser_view == "learning":
            if self.history_selected_learning_dialog_session_id is not None:
                dialog_session_id = self.history_selected_learning_dialog_session_id
                messages = self.services.learning.list_dialog_messages_for_session(dialog_session_id)
                if not messages:
                    self.history_selected_learning_dialog_session_id = None
                    self.history_selected_learning_topic_id = None
                    self.history_selected_learning_date = None
                    return "\n".join(
                        [
                            "[bold cyan]History browser[/bold cyan]",
                            "",
                            "Выбранный learning dialog больше не доступен.",
                            "/history learning - вернуться к списку.",
                        ]
                    )
                topic_id = messages[0].topic_id
                dialog_date = messages[0].created_at.date().isoformat()
                topic = self.services.repository.get_topic(topic_id)
                topic_title = topic.title if topic is not None else f"Topic #{topic_id}"
                context = messages[0].context_type or "legacy"
                context_id = messages[0].context_id or "-"
                lines = [
                    "[bold cyan]History browser[/bold cyan]",
                    "",
                    f"[bold]Learning dialog[/bold] session {escape(dialog_session_id)}",
                    f"Topic: #{topic_id} {escape(topic_title)}",
                    f"Date: {dialog_date}",
                    f"Context: {escape(context)} #{escape(context_id)}",
                    f"Messages: {len(messages)}",
                    f"Конспект обучения: /notebook topic {topic_id}",
                    "",
                    "/history learning - вернуться к списку. /practice - вернуться назад.",
                    "",
                    "[bold]Dialog[/bold]",
                ]
                for message in messages:
                    role = "Ты" if message.role == "user" else "ИИ"
                    lines.extend(
                        [
                            "",
                            f"[dim]{message.created_at.isoformat(timespec='minutes')}[/dim]",
                            render_chat_message(role, message.content),
                        ]
                    )
                return "\n".join(lines)

            if self.history_selected_learning_topic_id is not None and self.history_selected_learning_date is not None:
                topic_id = self.history_selected_learning_topic_id
                dialog_date = self.history_selected_learning_date
                try:
                    messages = self.services.learning.list_dialog_messages_for_date(topic_id, dialog_date)
                except ValueError as exc:
                    self.history_selected_learning_topic_id = None
                    self.history_selected_learning_date = None
                    return "\n".join(
                        [
                            "[bold cyan]History browser[/bold cyan]",
                            "",
                            f"Выбранный learning dialog больше не доступен: {escape(str(exc))}",
                            "/history learning - вернуться к списку.",
                        ]
                    )
                if not messages:
                    self.history_selected_learning_topic_id = None
                    self.history_selected_learning_date = None
                    return "\n".join(
                        [
                            "[bold cyan]History browser[/bold cyan]",
                            "",
                            "Выбранный learning dialog больше не доступен.",
                            "/history learning - вернуться к списку.",
                        ]
                    )
                topic = self.services.repository.get_topic(topic_id)
                topic_title = topic.title if topic is not None else f"Topic #{topic_id}"
                lines = [
                    "[bold cyan]History browser[/bold cyan]",
                    "",
                    f"[bold]Learning dialog[/bold] topic #{topic_id} | Date: {dialog_date}",
                    f"Topic: {escape(topic_title)}",
                    f"Messages: {len(messages)}",
                    f"Конспект обучения: /notebook topic {topic_id}",
                    "",
                    "/history learning - вернуться к списку. /practice - вернуться назад.",
                    "",
                    "[bold]Dialog[/bold]",
                ]
                for message in messages:
                    role = "Ты" if message.role == "user" else "ИИ"
                    lines.extend(
                        [
                            "",
                            f"[dim]{message.created_at.isoformat(timespec='minutes')}[/dim]",
                            render_chat_message(role, message.content),
                        ]
                    )
                return "\n".join(lines)

            summaries = self.services.learning.list_dialog_summaries(limit=30)
            lines = [
                "[bold cyan]History browser[/bold cyan]",
                "",
                "Read-only список сохраненных learning dialogs по session/context.",
                "/history learning <session-id> - открыть dialog.",
                "/history learning <topic-id> <YYYY-MM-DD> - открыть legacy group по дате.",
                "/notebook topic <id> - открыть конспект обучения по topic.",
                "/history - вернуться к practice sessions. /practice - вернуться назад.",
                "",
                "[bold]Learning dialogs[/bold]",
            ]
            if not summaries:
                lines.append("- пока нет сохраненных learning dialogs")
                return "\n".join(lines)
            for summary in summaries:
                session_label = summary.dialog_session_id or f"legacy:{summary.topic_id}:{summary.dialog_date}"
                context = summary.context_type or "legacy"
                context_id = f" #{summary.context_id}" if summary.context_id else ""
                open_commands = [
                    f"Open: /history learning {summary.topic_id} {summary.dialog_date}",
                    f"Конспект обучения: /notebook topic {summary.topic_id}",
                ]
                if not session_label.startswith("legacy:"):
                    open_commands.insert(0, f"Open: /history learning {escape(session_label)}")
                lines.append(
                    f"- Session: {escape(session_label)} | Topic #{summary.topic_id}: {escape(summary.topic_title)} | "
                    f"Date: {summary.dialog_date} | Context: {escape(context)}{escape(context_id)} | "
                    f"Messages: {summary.message_count} | "
                    f"First: {summary.first_message_at.isoformat(timespec='minutes')} | "
                    f"Last: {summary.last_message_at.isoformat(timespec='minutes')} | "
                    f"{' | '.join(open_commands)}"
                )
            return "\n".join(lines)

        if self.history_selected_session_id is not None:
            detail = self.services.sessions.get_completed_session_detail(self.history_selected_session_id)
            if detail is None:
                self.history_selected_session_id = None
                return "\n".join(
                    [
                        "[bold cyan]History browser[/bold cyan]",
                        "",
                        "Выбранная session больше не доступна среди завершенных practice sessions.",
                        "/history - вернуться к списку.",
                    ]
                )
            summary = detail.summary
            topic = summary.topic_title or "смешанная практика"
            score = "нет" if summary.avg_self_score is None else f"{summary.avg_self_score:.1f}/5"
            lines = [
                "[bold cyan]History browser[/bold cyan]",
                "",
                f"[bold]Session #{summary.id}[/bold]",
                f"Topic: {topic}",
                f"Started: {summary.started_at.isoformat(timespec='minutes')}",
                f"Ended: {summary.ended_at.isoformat(timespec='minutes')}",
                f"Answers: {summary.answer_count}",
                f"Avg self-score: {score}",
                "",
                "/history - вернуться к списку. /practice - вернуться назад.",
                "",
            ]
            outcome = self.services.repository.get_session_outcome_for_session(summary.id)
            if outcome is not None:
                lines.extend(
                    [
                        format_session_outcome(outcome),
                        "",
                    ]
                )
            lines.append("[bold]Answers[/bold]")
            if not detail.answers:
                lines.append("- в session нет ответов")
                return "\n".join(lines)
            for index, answer in enumerate(detail.answers, start=1):
                self_score = "без оценки" if answer.self_score is None else f"{answer.self_score}/5"
                feedback = answer.ai_feedback or "AI feedback не запрашивался."
                lines.extend(
                    [
                        "",
                        f"[bold]#{index}. Question #{answer.question_id} [{answer.question_difficulty}][/bold]",
                        f"Answered: {answer.answered_at.isoformat(timespec='minutes')} | Self-score: {self_score}",
                        "",
                        "[bold]Вопрос[/bold]",
                        escape(answer.question_prompt),
                        "",
                        render_chat_message("Твой ответ", answer.user_answer),
                        "",
                        render_chat_message("Эталонный ответ", answer.reference_answer),
                        "",
                        render_chat_message("AI feedback", feedback),
                    ]
                )
            return "\n".join(lines)

        sessions = self.services.sessions.list_completed_sessions(limit=30)
        lines = [
            "[bold cyan]History browser[/bold cyan]",
            "",
            "Read-only список завершенных practice sessions.",
            "/history <session-id> - открыть session и посмотреть ответы.",
            "/history learning - показать сохраненные learning dialogs по topic/date.",
            "/history system-design - показать final feedback и rubric scores.",
            "/practice - вернуться назад.",
            "",
            "[bold]Sessions[/bold]",
        ]
        if not sessions:
            lines.append("- пока нет завершенных practice sessions")
            return "\n".join(lines)
        for session in sessions:
            topic = session.topic_title or "смешанная практика"
            score = "нет" if session.avg_self_score is None else f"{session.avg_self_score:.1f}/5"
            lines.append(
                f"- Session #{session.id} | Topic: {topic} | "
                f"Started: {session.started_at.isoformat(timespec='minutes')} | "
                f"Ended: {session.ended_at.isoformat(timespec='minutes')} | "
                f"Answers: {session.answer_count} | Avg self-score: {score}"
            )
        return "\n".join(lines)

    def system_design_history_browser_text(self) -> str:
        if self.history_selected_system_design_feedback_id is not None:
            feedback_id = self.history_selected_system_design_feedback_id
            feedback = self.services.repository.get_system_design_feedback_artifact(feedback_id)
            if feedback is None:
                self.history_selected_system_design_feedback_id = None
                return "\n".join(
                    [
                        "[bold cyan]History browser[/bold cyan]",
                        "",
                        "Выбранный system design feedback больше не доступен.",
                        "/history system-design - вернуться к списку.",
                    ]
                )
            topic = self.services.repository.get_topic(feedback.topic_id)
            topic_title = topic.title if topic is not None else f"Topic #{feedback.topic_id}"
            scenario_title = self.system_design_history_scenario_title(feedback)
            evaluation = self.services.repository.get_system_design_evaluation_for_feedback(feedback.id or 0)
            session = f"#{feedback.session_id}" if feedback.session_id is not None else "нет session"
            lines = [
                "[bold cyan]History browser[/bold cyan]",
                "",
                f"[bold]System design feedback #{feedback.id}[/bold]",
                f"Session: {session}",
                f"Topic: #{feedback.topic_id} {escape(topic_title)}",
                f"Scenario: {escape(scenario_title)}",
                f"Created: {feedback.created_at.isoformat(timespec='minutes')}",
                f"Source: {escape(feedback.source)}",
                "",
                "/history system-design - вернуться к списку. /practice - вернуться назад.",
                "",
                render_chat_message("System design final feedback", feedback.content),
                "",
                format_system_design_evaluation(evaluation),
            ]
            return "\n".join(lines)

        feedbacks = self.system_design_history_feedback_artifacts(limit=30)
        lines = [
            "[bold cyan]History browser[/bold cyan]",
            "",
            "Read-only список system design final feedback artifacts.",
            "/history system-design <feedback-id> - открыть feedback и rubric scores.",
            "/history - вернуться к practice sessions. /practice - вернуться назад.",
            "",
            "[bold]System design sessions[/bold]",
        ]
        if not feedbacks:
            lines.append("- пока нет сохраненного system design final feedback")
            return "\n".join(lines)
        for feedback in feedbacks:
            evaluation = self.services.repository.get_system_design_evaluation_for_feedback(feedback.id or 0)
            session = f"#{feedback.session_id}" if feedback.session_id is not None else "нет"
            lines.append(
                f"- Feedback #{feedback.id} | Session: {session} | "
                f"Scenario: {escape(self.system_design_history_scenario_title(feedback))} | "
                f"Created: {feedback.created_at.isoformat(timespec='minutes')} | "
                f"Source: {escape(feedback.source)} | "
                f"Rubric: {escape(system_design_evaluation_score_label(evaluation))} | "
                f"Open: /history system-design {feedback.id}"
            )
        return "\n".join(lines)

    def system_design_history_feedback_artifacts(self, limit: int = 30) -> list[SystemDesignFeedbackArtifact]:
        topic = self.services.repository.find_topic_by_slug("system-design")
        if topic is None or topic.id is None:
            return []
        feedbacks = self.services.repository.list_system_design_feedback_artifacts(topic.id, limit=limit)
        return sorted(feedbacks, key=lambda feedback: (feedback.created_at, feedback.id or 0), reverse=True)

    def system_design_history_scenario_title(self, feedback: SystemDesignFeedbackArtifact) -> str:
        if feedback.scenario_id is None:
            return "default/custom scenario"
        scenario = self.services.repository.get_system_design_scenario(feedback.scenario_id, include_archived=True)
        if scenario is None:
            return f"Scenario #{feedback.scenario_id}"
        return scenario.title

    def history_browser_side_panel_text(self) -> str:
        sessions = self.services.sessions.list_completed_sessions(limit=100)
        learning_summaries = self.services.learning.list_dialog_summaries(limit=100)
        system_design_feedbacks = self.system_design_history_feedback_artifacts(limit=100)
        selected = self.history_selected_session_id
        selected_learning = (
            self.history_selected_learning_dialog_session_id is not None
            or (
                self.history_selected_learning_topic_id is not None
                and self.history_selected_learning_date is not None
            )
        )
        selected_system_design = self.history_selected_system_design_feedback_id is not None
        if selected is not None:
            next_action = "Открыта session в read-only режиме. /history вернет к списку."
        elif selected_system_design:
            next_action = "Открыт system design feedback в read-only режиме. /history system-design вернет к списку."
        elif selected_learning:
            next_action = "Открыт learning dialog в read-only режиме. /history learning вернет к списку."
        elif self.history_browser_view == "learning":
            next_action = "Открыт список learning dialogs. /history вернет к practice sessions."
        elif self.history_browser_view == "system_design":
            next_action = "Открыт список system design feedback. /history вернет к practice sessions."
        else:
            next_action = "Открой завершенную session через /history <session-id> или введи ID на экране history."
        lines = [
            "[bold]History[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            next_action,
            "",
            "[bold]Сводка[/bold]",
            f"Завершенных sessions: {len(sessions)}",
            f"Learning dialogs: {len(learning_summaries)}",
            f"System design feedbacks: {len(system_design_feedbacks)}",
        ]
        if selected is not None:
            lines.append(f"Открыта session: #{selected}")
        if selected_system_design:
            lines.append(f"Открыт system design feedback: #{self.history_selected_system_design_feedback_id}")
        if selected_learning:
            if self.history_selected_learning_dialog_session_id is not None:
                lines.append(f"Открыт learning dialog: {self.history_selected_learning_dialog_session_id}")
            else:
                lines.append(
                    f"Открыт learning dialog: topic #{self.history_selected_learning_topic_id} "
                    f"за {self.history_selected_learning_date}"
                )
        lines.extend(
            [
                "",
                "[bold]Команды[/bold]",
                "/history",
                "/history <session-id>",
                "/history learning",
                "/history learning <session-id>",
                "/history learning <topic-id> <YYYY-MM-DD>",
                "/history system-design",
                "/history system-design <feedback-id>",
                "/notebook topic <id>",
                "/practice",
                "",
                "[bold]Последние события[/bold]",
            ]
        )
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def materials_side_panel_text(self) -> str:
        topic_id = self.current_topic_id()
        topic_title = self.topic.title if self.topic is not None else "все темы"
        materials_topic_id = topic_id if self.materials_learning_filter == "current" else None
        materials = self.services.repository.list_learning_materials(topic_id=materials_topic_id, limit=10)
        scenario_topic_id = self.materials_scenario_topic_id(topic_id)
        scenarios = self.services.repository.list_system_design_scenarios(topic_id=scenario_topic_id, limit=10)
        materials_filter = "current topic" if self.materials_learning_filter == "current" else "all topics"
        scenarios_filter = "current topic" if self.materials_scenario_filter == "current" else "all topics"
        lines = [
            "[bold]Materials[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            "Выбери latest для последней версии текущей темы или id для конкретной версии.",
            "",
            "[bold]Контекст[/bold]",
            f"Тема learning materials: {topic_title}",
            f"Фильтр learning materials: {materials_filter}",
            f"Фильтр system design scenarios: {scenarios_filter}",
            f"Learning materials: {len(materials)}",
            f"System design scenarios: {len(scenarios)}",
            f"Content: {self.content_status_text()}",
            "",
            "[bold]Команды[/bold]",
            "/materials current",
            "/materials all",
            "/materials scenarios current",
            "/materials scenarios all",
            "/preview-material <id|latest>",
            "/preview-scenario <id|latest>",
            "/material <id|latest>",
            "/scenario <id|latest>",
            "/archive-material <id> confirm [reason]",
            "/archive-scenario <id> confirm [reason]",
            "/regen-material",
            "/regen-scenario",
            f"/notebook topic {topic_id}" if topic_id is not None else "/notebook all",
            "/notebook topic <id>",
            "/practice",
            "",
            "[bold]Последние события[/bold]",
        ]
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def notebook_side_panel_text(self) -> str:
        all_entries = self.services.repository.list_notebook_entries(limit=1000)
        visible_entries = self.filtered_notebook_entries(limit=1000)
        all_manual_notes = self.all_notebook_manual_notes(limit=1000)
        visible_manual_notes = self.filtered_manual_notes(limit=1000)
        topic_ids = {entry.topic_id for entry in all_entries}
        topic_ids.update(note.topic_id for note in all_manual_notes if note.topic_id is not None)
        subtopic_ids = {
            entry.curriculum_subtopic_id
            for entry in all_entries
            if entry.curriculum_subtopic_id is not None
        }
        lines = [
            "[bold]Конспект обучения[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            (
                "Открыта одна запись конспекта. /notebook вернет к текущему фильтру, /notebook all покажет все."
                if self.notebook_selected_entry_id is not None
                else "Выбери фильтр по теме/subtopic или открой конкретную запись."
            ),
            "",
            "[bold]Сводка[/bold]",
            f"Всего entries: {len(all_entries)}",
            f"Всего manual notes: {len(all_manual_notes)}",
            f"В текущем фильтре: {len(visible_entries)} entries; {len(visible_manual_notes)} manual notes",
            f"Тем с записями: {len(topic_ids)}",
            f"Subtopics с записями: {len(subtopic_ids)}",
            self.notebook_filter_text(),
            "",
            "[bold]Команды[/bold]",
            "/notebook",
            "/notebook all",
            "/notebook topic <id>",
            "/notebook subtopic <id>",
            "/notebook competency <slug>",
            "/notebook entry <id>",
            "/history learning",
            "/materials",
            "/practice",
            "",
            "[bold]Последние события[/bold]",
        ]
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def readiness_side_panel_text(self) -> str:
        try:
            snapshot = self.services.readiness.snapshot()
            summary = snapshot.overall_summary
            signal = "н/д" if summary.signal_score is None else f"{summary.signal_score}/100"
            top_gap = summary.recommended_drill
        except Exception as exc:
            lines = [
                "[bold]Readiness[/bold]",
                "",
                "[bold]Следующее действие[/bold]",
                "Readiness snapshot временно недоступен.",
                "",
                "[bold]Ошибка[/bold]",
                one_line_preview(str(exc), limit=140),
                "",
                "[bold]Команды[/bold]",
                "/mock-interview",
                "/readiness",
                "/stats",
                "/practice",
                "",
                "[bold]Последние события[/bold]",
            ]
            lines.extend(self.history[-8:] or ["Пока нет событий."])
            return "\n".join(lines)

        lines = [
            "[bold]Readiness[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            top_gap.next_action if top_gap is not None else "Явных gaps нет; поддерживай свежую практику.",
            "",
            "[bold]Сводка[/bold]",
            f"Signal: {signal}",
            f"Label: {summary.label}",
            f"Competencies: {snapshot.competency_count}",
            f"With answers: {snapshot.covered_competency_count}",
            f"With rubric: {snapshot.evaluated_competency_count}",
            "",
            "[bold]Команды[/bold]",
            "/baseline-repeat" if self.baseline_repeat_due_status() is not None else "",
            "/mock-interview",
            "/readiness",
            "/stats",
            "/practice",
            "/history",
            "",
            "[bold]Последние события[/bold]",
        ]
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def learning_side_panel_text(self) -> str:
        topic = self.learning_topic_title()
        material_status = "готов" if self.generated_learning_material else "генерируется" if self.content_worker_running else "нет"
        dialog_count = len(self.learning_transcript)
        lines = [
            "[bold]Learning[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            self.learning_next_action_text(),
            "",
            "[bold]Контекст[/bold]",
            f"Тема: {topic}",
            f"Материал: {material_status}",
            f"Реплик в диалоге: {dialog_count}",
        ]
        _, navigation = self.visible_learning_transcript()
        if navigation:
            lines.extend(["", "[bold]Навигация[/bold]", navigation])
        lines.extend(["", "[bold]Последние события[/bold]"])
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def learning_next_action_text(self) -> str:
        if self.mode == "loading_learning":
            return "Дождись учебного ответа. После готовности можно задать уточняющий вопрос."
        if not self.learning_transcript:
            return "Напиши, что непонятно по теме или текущему вопросу."
        total = len(self.learning_transcript)
        if total > self.learning_dialog_window_size and self.learning_dialog_offset > 0:
            return "Используй /learn-newer для возврата к свежим репликам или задай новый вопрос."
        if total > self.learning_dialog_window_size:
            return "Используй /learn-older для просмотра более старых реплик или задай новый вопрос."
        return "Задай уточняющий вопрос или вернись к практике через /practice."

    def learning_topic_title(self) -> str:
        if self.learning_topic_id is None:
            return "без выбранной темы"
        if self.topic is not None and self.topic.id == self.learning_topic_id:
            return self.topic.title
        topic = self.services.repository.get_topic(self.learning_topic_id)
        return topic.title if topic is not None else f"topic #{self.learning_topic_id}"

    def system_design_side_panel_text(self) -> str:
        topic = self.topic.title if self.topic else "system design"
        scenario_status = "готов" if self.system_design_scenario != DEFAULT_SYSTEM_DESIGN_SCENARIO else "fallback"
        if self.content_worker_running and not self.generated_system_design_scenario:
            scenario_status = "генерируется"
        artifact_count = sum(len(items) for items in self.system_design_artifacts.values())
        lines = [
            "[bold]System design[/bold]",
            "",
            "[bold]Следующее действие[/bold]",
            self.system_design_next_action_text(),
            "",
            "[bold]Контекст[/bold]",
            f"Тема: {topic}",
            f"Scenario: {scenario_status}",
            f"Focus areas: {len(self.generated_system_design_focus_areas)}",
            f"Artifacts: {artifact_count}",
            f"Реплик в transcript: {len(self.system_design_transcript)}",
            "",
            "[bold]Команды artifacts[/bold]",
            "/req, /api, /data, /decision, /risk",
            "/sd-checkpoint, /sd-pressure, /sd-feedback",
            "",
            "[bold]Последние события[/bold]",
        ]
        lines.extend(self.history[-8:] or ["Пока нет событий."])
        if self.command_palette_visible or self.last_feedback.startswith("Статистика:"):
            lines.extend(["", "[bold]Панель[/bold]", self.last_feedback])
        return "\n".join(lines)

    def system_design_next_action_text(self) -> str:
        if self.mode == "loading_system_design":
            return "Дождись ответа интервьюера. Transcript обновится автоматически."
        if self.mode == "loading_system_design_checkpoint":
            return "Дождись checkpoint. Он сохранится как реплика интервьюера."
        if self.mode == "loading_system_design_pressure":
            return "Дождись pressure follow-up. Он сохранится как реплика интервьюера."
        if self.mode == "loading_system_design_feedback":
            return "Дождись итогового feedback по mock interview."
        if not self.system_design_transcript:
            return "Начни с requirements или задай интервьюеру уточняющий вопрос."
        return "Продолжай решение, фиксируй artifacts, запроси /sd-pressure или /sd-feedback."

    def placeholder(self) -> str:
        if self.mode == "select_topic":
            return "Enter - Start Drill, ID темы или /accept-topic - ручной topic practice"
        if self.mode == "scoring":
            return "Самооценка 1-5 или Enter"
        if self.mode == "loading_feedback":
            return "AI feedback генерируется..."
        if self.mode == "loading_learning":
            return "ИИ готовит объяснение..."
        if self.mode == "loading_system_design":
            return "System design interviewer генерирует вопрос..."
        if self.mode == "loading_system_design_checkpoint":
            return "System design checkpoint генерируется..."
        if self.mode == "loading_system_design_pressure":
            return "System design pressure follow-up генерируется..."
        if self.mode == "loading_system_design_feedback":
            return "System design feedback генерируется..."
        if self.mode == "artifacts":
            return (
                "/preview-material <id|latest>, /archive-material <id> confirm [reason], "
                "/archive-scenario <id> confirm [reason], /material <id|latest>, /scenario <id|latest>, /practice"
            )
        if self.mode == "content":
            return "/pause-content, /resume-content, /retry-job <id>, /materials artifacts, /practice назад"
        if self.mode == "questions_review":
            return "/questions-review accept <id>, /questions-review archive <id> как manual audit override, /practice назад"
        if self.mode == "auto_curation_audit":
            return "/curation-audit topic <id>, /curation-audit status <status>, /practice назад"
        if self.mode == "history":
            return "/practice назад к текущему workflow"
        if self.mode == "notebook":
            return "/notebook topic <id>, /notebook subtopic <id>, /notebook competency <slug>, /notebook entry <id>, /practice"
        if self.mode == "readiness":
            return "/mock-interview, /readiness, /stats или /practice назад"
        if self.mode == "session_finished":
            return "/practice новая сессия, /history, /notebook, /quit"
        if self.mode == "learning":
            return "Спроси, что непонятно. /practice - назад"
        if self.mode == "system_design":
            return "Ответ интервьюеру. /sd-pressure - pressure question, /sd-feedback - итоговая оценка"
        if self.mode == "answered":
            return (
                "Enter - следующий вопрос, /feedback, /recheck-feedback, /note-from-answer, "
                "/learn, /stats, /commands, /finish-session, /quit"
            )
        if self.mode == "ended":
            return "Enter - закрыть"
        return "Ответ или slash command"

    def add_history(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.history.append(f"[dim]{timestamp}[/dim] {message}")

    def notes_text(self) -> str:
        try:
            notes_editor = self.query_one("#notes_editor", TextArea)
            self._notes_editor_widget = notes_editor
            self._notes_editor_text_cache = notes_editor.text
            return notes_editor.text.strip()
        except Exception:
            if self._notes_editor_widget is not None:
                try:
                    self._notes_editor_text_cache = self._notes_editor_widget.text
                except Exception:
                    pass
            return self._notes_editor_text_cache.strip()

    def notes_draft_context(self) -> tuple[int | None, int | None, str, str]:
        session_id = self.session.id if self.session is not None and self.session.id is not None else None
        topic_id = self.current_topic_id()
        context_type = NOTES_DRAFT_CONTEXT_TYPE
        if session_id is not None:
            return topic_id, session_id, context_type, f"session:{session_id}"
        if topic_id is not None:
            return topic_id, None, context_type, f"topic:{topic_id}"
        return None, None, context_type, "global"

    def saved_note_context(self) -> tuple[int | None, int | None, str]:
        session_id = self.session.id if self.session is not None and self.session.id is not None else None
        topic_id = self.current_topic_id()
        if session_id is not None:
            return topic_id, session_id, f"session:{session_id}"
        if topic_id is not None:
            return topic_id, None, f"topic:{topic_id}"
        return None, None, "global"

    def persist_notes_draft(self, context_key: tuple[int | None, int | None, str, str] | None = None) -> None:
        body = self.notes_text()
        topic_id, session_id, context_type, context_id = (
            context_key or self._active_notes_context_key or self.notes_draft_context()
        )
        context_key = (topic_id, session_id, context_type, context_id)
        previous_context = self._last_saved_notes_signature[0] if self._last_saved_notes_signature else None
        if not body and previous_context != context_key:
            return
        signature = (context_key, body)
        if signature == self._last_saved_notes_signature:
            return
        now = datetime.now()
        try:
            self.services.repository.upsert_manual_note_by_context(
                ManualNote(
                    id=None,
                    topic_id=topic_id,
                    session_id=session_id,
                    context_type=context_type,
                    context_id=context_id,
                    title=NOTES_DRAFT_TITLE,
                    body=body,
                    created_at=now,
                    updated_at=now,
                )
            )
            self._last_saved_notes_signature = signature
        except Exception as exc:
            self.add_history(f"Не удалось сохранить notes draft: {exc}")

    def restore_notes_draft(self) -> None:
        context_key = self.notes_draft_context()
        if self._active_notes_context_key == context_key:
            return
        if self._active_notes_context_key is not None:
            self.persist_notes_draft(self._active_notes_context_key)
        _, _, context_type, context_id = context_key
        body = ""
        try:
            notes = self.services.repository.list_manual_notes(
                context_type=context_type,
                context_id=context_id,
                limit=10,
            )
        except Exception as exc:
            self.add_history(f"Не удалось загрузить notes draft: {exc}")
            notes = []
        for note in notes:
            if note.title == NOTES_DRAFT_TITLE:
                body = note.body
                break
        self.query_one("#notes_editor", TextArea).text = body
        self._notes_editor_text_cache = body
        self._active_notes_context_key = context_key
        self._last_saved_notes_signature = (context_key, body)


def run_tui(db_path: str = str(DEFAULT_DB_PATH), config_path: str = str(DEFAULT_CONFIG_PATH)) -> None:
    InterviewPrepTUI(db_path, config_path).run()
