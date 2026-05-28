from __future__ import annotations

import json
from datetime import timedelta
from io import StringIO

from rich.console import Console
from rich.markdown import Markdown
from rich.markup import escape

from interview_prep.domain.models import (
    Answer,
    AnswerEvaluation,
    Question,
    QuestionCompetencyLink,
    SessionOutcome,
    SystemDesignEvaluation,
    Tag,
)
from interview_prep.services.content_generation_service import (
    JOB_KIND_CURRICULUM,
    JOB_KIND_LEARNING_MATERIAL,
    JOB_KIND_REFERENCE_ANSWER,
    JOB_KIND_SYSTEM_DESIGN_SCENARIO,
)
from interview_prep.services.session_service import (
    FEEDBACK_FALLBACK_FLAG,
    FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG,
)


SYSTEM_DESIGN_ARTIFACT_COMMANDS = (
    ("/requirement ", "requirements"),
    ("/req ", "requirements"),
    ("/api ", "api"),
    ("/data ", "data_model"),
    ("/decision ", "decisions"),
    ("/risk ", "risks"),
)

SYSTEM_DESIGN_ARTIFACT_LABELS = {
    "requirements": "Requirements",
    "api": "API",
    "data_model": "Data model",
    "decisions": "Architecture decisions",
    "risks": "Risks / failure modes",
}

SYSTEM_DESIGN_FEEDBACK_REQUIRED_SECTIONS = ("requirements", "api", "data_model", "risks")
NOTES_DRAFT_CONTEXT_TYPE = "tui-notes-draft"
NOTES_DRAFT_TITLE = "TUI notes draft"
SAVED_NOTE_CONTEXT_TYPE = "tui-saved-note"

CHAT_ROLE_STYLES = {
    "Ты": "bold cyan",
    "Кандидат": "bold cyan",
    "ИИ": "bold magenta",
    "Интервьюер": "bold magenta",
    "Твой ответ": "bold cyan",
    "Эталонный ответ": "bold magenta",
    "AI feedback": "bold magenta",
    "System design final feedback": "bold magenta",
}

MARKDOWN_MESSAGE_ROLES = {
    "ИИ",
    "Интервьюер",
    "Эталонный ответ",
    "AI feedback",
    "System design final feedback",
}


def render_llm_markdown(message: str, width: int = 88) -> str:
    stripped = message.rstrip()
    if not stripped:
        return ""
    console = Console(file=StringIO(), record=True, width=width, color_system=None)
    console.print(Markdown(stripped))
    rendered = console.export_text(styles=False)
    return "\n".join(line.rstrip() for line in rendered.rstrip().splitlines())


def render_chat_message(role: str, message: str) -> str:
    style = CHAT_ROLE_STYLES.get(role, "bold")
    safe_role = escape(role)
    if role in MARKDOWN_MESSAGE_ROLES:
        safe_message = escape(render_llm_markdown(message))
    else:
        safe_message = escape(message.rstrip())
    body = safe_message if safe_message else "[dim](пусто)[/dim]"
    return "\n".join(
        [
            "[dim]---[/dim]",
            f"[{style}]{safe_role}[/{style}]",
            body,
        ]
    )


def format_question_tags(tags: list[Tag]) -> str:
    labels = []
    for tag in tags:
        label = f"{tag.title} ({tag.slug})" if tag.title != tag.slug else tag.title
        labels.append(escape(label))
    return ", ".join(labels)


def format_question_competencies(links: list[QuestionCompetencyLink]) -> str:
    labels = []
    for link in links:
        competency = link.competency
        label = f"{competency.title} ({competency.slug})"
        if link.is_primary:
            label += " [основная]"
        labels.append(escape(label))
    return ", ".join(labels)


def format_answer_evaluation(evaluation: AnswerEvaluation) -> str:
    score_lines = [
        f"- {escape(score.dimension.title)} ({escape(score.dimension.slug)}): {score.score}/5"
        for score in evaluation.scores
    ]
    if evaluation.scores:
        average = sum(score.score for score in evaluation.scores) / len(evaluation.scores)
        score_lines.insert(0, f"Средний rubric score: {average:.1f}/5")
    lines = [
        f"[dim]Источник: {escape(evaluation.source)}[/dim]",
        f"Summary: {escape(evaluation.summary)}",
        *score_lines,
    ]
    if evaluation.next_drills:
        lines.extend(
            [
                "",
                "[bold]Next drills[/bold]",
                *[
                    f"{index}. {escape(one_line_preview(drill, limit=120))}"
                    for index, drill in enumerate(evaluation.next_drills[:4], start=1)
                ],
            ]
        )
    return "\n".join(lines)


def format_system_design_evaluation(evaluation: SystemDesignEvaluation | None) -> str:
    if evaluation is None:
        return "\n".join(
            [
                "[bold]System design rubric[/bold]",
                "- saved rubric evaluation не найдена",
            ]
        )

    score_lines = [
        f"- {escape(score.dimension.title)} ({escape(score.dimension.slug)}): {score.score}/5"
        for score in evaluation.scores
    ]
    if evaluation.scores:
        average = sum(score.score for score in evaluation.scores) / len(evaluation.scores)
        score_lines.insert(0, f"Average score: {average:.1f}/5")
    lines = [
        "[bold]System design rubric[/bold]",
        f"[dim]Источник: {escape(evaluation.source)} | Создан: {evaluation.created_at.isoformat(timespec='minutes')}[/dim]",
        f"Summary: {escape(evaluation.summary)}",
        *score_lines,
    ]
    if evaluation.next_drills:
        lines.extend(
            [
                "",
                "[bold]Next drills[/bold]",
                *[
                    f"{index}. {escape(one_line_preview(drill, limit=120))}"
                    for index, drill in enumerate(evaluation.next_drills[:4], start=1)
                ],
            ]
        )
    return "\n".join(lines)


def system_design_evaluation_score_label(evaluation: SystemDesignEvaluation | None) -> str:
    if evaluation is None or not evaluation.scores:
        return "нет evaluation"
    average = sum(score.score for score in evaluation.scores) / len(evaluation.scores)
    return f"{average:.1f}/5"


def format_session_outcome(outcome: SessionOutcome | None) -> str:
    if outcome is None:
        return "\n".join(
            [
                "[bold]Итог сессии[/bold]",
                "Outcome не создан: в session нет сохраненных ответов.",
            ]
        )

    lines = [
        "[bold]Итог сессии[/bold]",
        f"[dim]Создан: {outcome.created_at.isoformat(timespec='minutes')}[/dim]",
        f"Type: {escape(outcome.outcome_type)}",
        f"Readiness delta: {outcome.readiness_delta:+.2f}",
        "",
        "[bold]Summary[/bold]",
        escape(outcome.summary),
        "",
        "[bold]Strengths[/bold]",
        *format_outcome_bullets(outcome.strengths),
        "",
        "[bold]Gaps[/bold]",
        *format_outcome_bullets(outcome.gaps),
        "",
        "[bold]Next drills[/bold]",
        *format_outcome_bullets(outcome.next_drills),
    ]
    return "\n".join(lines)


def format_outcome_bullets(items: list[str]) -> list[str]:
    if not items:
        return ["- нет данных"]
    return [f"- {escape(item)}" for item in items]


def readiness_next_action_for_aggregate(aggregate) -> str:
    reasons = aggregate.readiness_reasons
    title = aggregate.competency.title
    if "нет system design практики" in reasons:
        return "Провести system design mock и сохранить transcript."
    if "нет связанных вопросов" in reasons:
        return f"Сгенерировать или добавить вопросы по competency: {title}."
    if any(reason.startswith("низкая rubric оценка:") for reason in reasons):
        return f"Перерешать слабый ответ по competency: {title} и закрыть rubric gaps."
    if any(reason.startswith("мало ответов:") for reason in reasons):
        return f"Ответить на 2-3 вопроса по competency: {title}."
    if "нет rubric оценки" in reasons:
        return f"Ответить в TUI по competency: {title}, чтобы сохранить rubric evaluation."
    if any(reason.startswith("давно не повторялось:") for reason in reasons):
        return f"Повторить competency сегодня: {title}."
    if "нет свежей практики" in reasons:
        return f"Начать baseline drill по competency: {title}."
    return f"Поддерживать свежую практику по competency: {title}."


def format_feedback_quality_warning(evaluation: AnswerEvaluation | None) -> str:
    if evaluation is None or not evaluation.raw_payload_json:
        return ""
    try:
        payload = json.loads(evaluation.raw_payload_json)
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""

    quality = payload.get("feedback_quality")
    flags: list[str] = []
    fallback = False
    suspicious = False
    fallback_error = None
    if isinstance(quality, dict):
        raw_flags = quality.get("flags")
        if isinstance(raw_flags, list):
            flags = [str(flag) for flag in raw_flags if str(flag).strip()]
        fallback = bool(quality.get("fallback")) or FEEDBACK_FALLBACK_FLAG in flags
        suspicious = bool(quality.get("suspicious")) or any(
            flag != FEEDBACK_FALLBACK_FLAG for flag in flags
        )
        fallback_error = quality.get("fallback_error")
    else:
        raw_flags = payload.get("feedback_quality_flags")
        if isinstance(raw_flags, list):
            flags = [str(flag) for flag in raw_flags if str(flag).strip()]
        fallback = FEEDBACK_FALLBACK_FLAG in flags
        suspicious = any(flag != FEEDBACK_FALLBACK_FLAG for flag in flags)

    if not fallback and not suspicious:
        return ""

    lines = ["[bold yellow]Проверь AI feedback[/bold yellow]"]
    if fallback:
        fallback_text = "AI feedback получен через fallback; используй его как черновую подсказку."
        if fallback_error:
            fallback_text += f" Деталь: {one_line_preview(str(fallback_error), limit=100)}."
        lines.append(f"[yellow]{escape(fallback_text)}[/yellow]")
    if suspicious:
        if FEEDBACK_PRAISE_WITHOUT_EVIDENCE_FLAG in flags:
            warning = (
                "Похвала в feedback может быть не подтверждена evidence из твоего ответа; "
                "сверяйся с rubric scores."
            )
        else:
            warning = "Feedback помечен как suspicious; сверяйся с rubric scores и своим ответом."
        lines.append(f"[yellow]{escape(warning)}[/yellow]")
    return "\n".join(lines)


def format_duration(value: timedelta) -> str:
    total_seconds = max(0, int(value.total_seconds()))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def notes_line_count(text: str) -> int:
    if not text.strip():
        return 0
    return len([line for line in text.splitlines() if line.strip()])


def one_line_preview(text: str, limit: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def feedback_gap_notebook_body(
    question: Question,
    answer: Answer,
    feedback: str,
    evaluation: AnswerEvaluation | None,
) -> str:
    feedback_gap = extract_feedback_gap_section(feedback)
    lines = [
        f"Вопрос #{question.id}: {question.prompt}",
        "",
        f"Ответ #{answer.id}: {answer.user_answer}",
        "",
        "Feedback gap:",
        feedback_gap or one_line_preview(feedback, limit=500),
    ]
    rubric_gap_lines = answer_evaluation_gap_lines(evaluation)
    if rubric_gap_lines:
        lines.extend(["", "Rubric gaps:", *rubric_gap_lines])
    drill_lines = answer_evaluation_drill_lines(evaluation)
    if drill_lines:
        lines.extend(["", "Next drills:", *drill_lines])
    return "\n".join(lines).strip()


def extract_feedback_gap_section(feedback: str) -> str:
    captured: list[str] = []
    capture = False
    for raw_line in feedback.splitlines():
        line = raw_line.strip()
        if not line:
            if capture and captured and captured[-1] != "":
                captured.append("")
            continue
        if is_feedback_section_heading(line):
            capture = is_feedback_gap_heading(line)
            if capture:
                captured.append(raw_line)
            continue
        if capture:
            captured.append(raw_line)
    while captured and captured[-1] == "":
        captured.pop()
    if captured:
        return "\n".join(captured).strip()
    keyword_lines = [
        raw_line.strip()
        for raw_line in feedback.splitlines()
        if is_feedback_gap_heading(raw_line.strip())
    ]
    return "\n".join(keyword_lines).strip()


def is_feedback_section_heading(line: str) -> bool:
    stripped = line.strip().strip("#*_` ").strip()
    if not stripped:
        return False
    if stripped.endswith(":"):
        return len(stripped.split()) <= 7
    if line.lstrip().startswith("#"):
        return True
    return False


def is_feedback_gap_heading(line: str) -> bool:
    normalized = line.lower().strip().strip("#*_` ").strip()
    if ":" in normalized:
        normalized = normalized.split(":", 1)[0].strip()
    return any(
        keyword in normalized
        for keyword in (
            "упущ",
            "gap",
            "пробел",
            "доработ",
            "улучш",
            "повтор",
            "next drill",
            "next step",
        )
    )


def answer_evaluation_gap_lines(evaluation: AnswerEvaluation | None) -> list[str]:
    if evaluation is None:
        return []
    lines = []
    for score in evaluation.scores:
        gap = score.gaps.strip()
        if gap and (score.score <= 3 or not lines):
            lines.append(f"- {score.dimension.title} ({score.dimension.slug}): {gap}")
    return lines[:5]


def answer_evaluation_drill_lines(evaluation: AnswerEvaluation | None) -> list[str]:
    if evaluation is None:
        return []
    drills = [drill.strip() for drill in evaluation.next_drills if drill.strip()]
    return [f"- {drill}" for drill in drills[:5]]


def artifact_version_text(artifact_id: int | None, newest_first_versions: list[object]) -> str:
    ordered = list(reversed(newest_first_versions))
    total = len(ordered)
    if artifact_id is None or total == 0:
        return "version unknown"
    latest_id = getattr(newest_first_versions[0], "id", None)
    for index, artifact in enumerate(ordered, start=1):
        if getattr(artifact, "id", None) == artifact_id:
            label = f"v{index}/{total}"
            if artifact_id == latest_id:
                label += " latest"
            return label
    return "version unknown"


def extract_system_design_artifact_commands(text: str) -> list[tuple[str, str]]:
    artifacts: list[tuple[str, str]] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        for prefix, section in SYSTEM_DESIGN_ARTIFACT_COMMANDS:
            if line.startswith(prefix):
                content = line.removeprefix(prefix).strip()
                if content:
                    artifacts.append((section, content))
                break
    return artifacts


def parse_content_result(result_json: str | None) -> dict:
    if not result_json:
        return {}
    try:
        value = json.loads(result_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def parse_content_payload(payload_json: str | None) -> dict:
    if not payload_json:
        return {}
    try:
        value = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def content_artifact_id_label(kind: str, artifact: dict) -> str:
    if kind == "question":
        question_id = artifact.get("question_id")
        return f"question#{question_id}" if question_id else ""
    if kind == JOB_KIND_LEARNING_MATERIAL:
        material_id = artifact.get("material_id")
        return f"material#{material_id}" if material_id else ""
    if kind == JOB_KIND_SYSTEM_DESIGN_SCENARIO:
        scenario_id = artifact.get("scenario_id")
        return f"scenario#{scenario_id}" if scenario_id else ""
    if kind == JOB_KIND_REFERENCE_ANSWER:
        updated_count = artifact.get("updated_count")
        return f"answers:{updated_count}" if updated_count else ""
    if kind == JOB_KIND_CURRICULUM:
        topic_count = artifact.get("topic_count")
        questions_saved = artifact.get("questions_saved")
        if topic_count is not None and questions_saved is not None:
            return f"curriculum:{topic_count}t/{questions_saved}q"
        return "curriculum"
    return ""


def content_job_retry_text(payload: dict) -> str:
    retry = payload.get("retry")
    if not isinstance(retry, dict):
        return ""
    attempt = retry.get("attempt")
    max_attempts = retry.get("max_attempts")
    next_attempt_at = retry.get("next_attempt_at")
    last_error = retry.get("last_error")
    parts: list[str] = []
    if attempt is not None and max_attempts is not None:
        parts.append(f"{attempt}/{max_attempts}")
    if next_attempt_at:
        parts.append(f"next {next_attempt_at}")
    if last_error:
        parts.append(one_line_preview(str(last_error), limit=100))
    return "; ".join(parts)


def command_palette_text() -> str:
    groups = [
        (
            "Today workflow",
            [
                "/accept-topic начать рекомендованную тему",
                "/readiness focused dashboard по competencies, score, evidence и next action",
                "/baseline-repeat начать due repeat baseline session",
                "/mock-interview начать mixed senior interview без ручного выбора topic",
                "/generate-curriculum поставить curriculum starter pack в background queue",
                "/system-design  mock interview по проектированию сервиса",
            ],
        ),
        (
            "Practice workflow",
            [
                "/hint      показать подсказку",
                "/answer    показать эталонный ответ",
                "/feedback  получить AI feedback по последнему ответу",
                "/recheck-feedback  перепроверить последний AI feedback строгим prompt",
                "/finish-session завершить текущую practice session и показать outcome без выхода из TUI",
                "/skip      пропустить текущий вопрос",
                "/next      следующий вопрос после ответа",
                "/practice  вернуться из отдельного режима к интервью",
            ],
        ),
        (
            "Learning workflow",
            [
                "/learn     режим обучения и разъяснения",
                "/learn-older /learn-newer листать длинный учебный диалог",
            ],
        ),
        (
            "Notebook workflow",
            [
                "/notebook конспект обучения с AI explanations",
                "/notebook topic <id> разбивка конспекта по теме",
                "/notebook subtopic <id> разбивка конспекта по curriculum subtopic",
                "/notebook competency <slug> фильтр конспекта по senior competency",
                "/notebook entry <id> открыть запись конспекта полностью",
                "/note-from-answer  сохранить gap из последнего feedback в notebook",
                "/notes     перейти в notes editor",
                "/save-note <title> сохранить текст из multiline composer как manual note",
            ],
        ),
        (
            "Content workflow",
            [
                "/content   список queued/running/failed background jobs",
                "/pause-content  поставить TUI content worker на паузу",
                "/resume-content снять паузу и запустить TUI content worker",
                "/retry-job <id>  вернуть failed content job в очередь",
                "/questions-review список pending generated questions",
                "/questions-review accept <id> принять generated question",
                "/questions-review archive <id> архивировать generated question",
                "/curation-audit список решений source-backed auto-curation",
                "/curation-audit topic <id> фильтр audit decisions по теме",
                "/curation-audit status <status> фильтр audit decisions по итоговому статусу",
                "CLI: questions-source undo --question <id> откат последнего decision",
            ],
        ),
        (
            "Materials workflow",
            [
                "/materials список сохраненных materials/scenarios",
                "/materials current/all фильтр learning materials",
                "/materials scenarios current/all фильтр system design scenarios",
                "/preview-material <id|latest>  preview учебного материала",
                "/preview-scenario <id|latest>  preview system design scenario",
                "/material <id|latest>  открыть сохраненный учебный материал",
                "/scenario <id|latest>  открыть сохраненный system design scenario",
                "/archive-material <id> confirm [reason]  скрыть неудачный learning material",
                "/archive-scenario <id> confirm [reason]  скрыть неудачный system design scenario",
                "/regen-material поставить новую генерацию учебного материала",
                "/regen-scenario поставить новую генерацию system design scenario",
            ],
        ),
        (
            "System design workflow",
            [
                "/sd <сценарий>   начать system design с собственным сценарием",
                "/sd-checkpoint короткий interviewer checkpoint без финальной оценки",
                "/sd-pressure   pressure follow-up по capacity/hot keys/retries/idempotency",
                "/sd-feedback    итоговый feedback по system design",
                "/req <текст>     добавить requirement в system design",
                "/api <текст>     добавить API note в system design",
                "/data <текст>    добавить data model note",
                "/decision <текст> добавить architecture decision",
                "/risk <текст>    добавить risk/failure mode",
            ],
        ),
        (
            "History workflow",
            [
                "/history   read-only список завершенных practice sessions",
                "/history <id> открыть завершенную practice session",
                "/history learning список saved learning dialogs по session/context",
                "/history learning <session-id> открыть saved learning dialog",
                "/history learning <topic-id> <date> открыть legacy group",
                "/history system-design список final feedback и rubric scores",
                "/history system-design <feedback-id> открыть system design feedback",
            ],
        ),
        (
            "Utility",
            [
                "/stats     показать статистику",
                "/quit      завершить сессию",
            ],
        ),
    ]
    lines = ["Command palette", "Команды сгруппированы по workflow."]
    for title, commands in groups:
        lines.extend(["", title])
        lines.extend(commands)
    lines.extend(["", "Hotkeys:", "Ctrl+P commands, Ctrl+N notes, Esc input, Ctrl+Q quit"])
    return "\n".join(lines)
