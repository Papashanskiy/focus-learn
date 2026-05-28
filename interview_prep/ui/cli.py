from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Sequence

from interview_prep.domain.models import (
    AnswerEvaluation,
    QUESTION_SOURCE_QUALITY_STATUSES,
    Question,
    QuestionAutoCurationAudit,
    QuestionCompetencyLink,
    SESSION_STATUS_ABANDONED,
    QuestionSourceSnapshot,
    SESSION_STATUS_COMPLETED,
    SessionOutcome,
    SystemDesignArtifact,
    SystemDesignEvaluation,
    SystemDesignFeedbackArtifact,
    SystemDesignScenario,
    SystemDesignTranscriptMessage,
    Tag,
)
from interview_prep.infra.config import DEFAULT_CONFIG_PATH, load_config, write_default_config
from interview_prep.infra.database import DEFAULT_DB_PATH
from interview_prep.services.content_generation_service import (
    JOB_KIND_LEARNING_MATERIAL,
    JOB_KIND_QUESTION,
    JOB_KIND_REFERENCE_ANSWER,
    JOB_KIND_SYSTEM_DESIGN_SCENARIO,
    parse_payload,
)
from interview_prep.services.app_factory import AppServices
from interview_prep.services.curriculum_service import CurriculumStatus
from interview_prep.services.question_quality_audit_service import (
    DEFAULT_MAX_QUESTION_PROMPT_CHARS,
    QuestionQualityFinding,
)
from interview_prep.services.question_quality_rules import generated_question_quality_flags
from interview_prep.services.question_auto_curation_service import (
    QuestionAutoCurationDecision,
    QuestionAutoCurationUndoResult,
)
from interview_prep.services.readiness_service import ReadinessSnapshot


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "no_services", False):
        return args.handler(args, None)
    services = AppServices(args.db, args.config)
    try:
        return args.handler(args, services)
    finally:
        services.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="interview-prep")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Путь к SQLite базе")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Путь к TOML config-файлу")
    shared_parent = argparse.ArgumentParser(add_help=False)
    shared_parent.add_argument("--db", default=argparse.SUPPRESS, help="Путь к SQLite базе")
    shared_parent.add_argument("--config", default=argparse.SUPPRESS, help="Путь к TOML config-файлу")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser(
        "init", parents=[shared_parent], help="Создать базу и стартовые данные"
    )
    init_parser.set_defaults(handler=cmd_init)

    topics_parser = subparsers.add_parser("topics", parents=[shared_parent], help="Показать темы")
    topics_parser.set_defaults(handler=cmd_topics)

    questions_parser = subparsers.add_parser("questions", parents=[shared_parent], help="Режим только вопросов")
    questions_parser.add_argument("--topic", type=int, help="ID темы")
    questions_parser.add_argument("--tag", help="Slug тега для фильтрации вопросов")
    questions_parser.set_defaults(handler=cmd_questions)

    questions_review_parser = subparsers.add_parser(
        "questions-review",
        parents=[shared_parent],
        help=(
            "Audit pending generated questions; auto-curation is the primary flow, "
            "accept/archive are manual overrides"
        ),
    )
    questions_review_parser.add_argument("--topic", type=int, help="ID темы для списка pending questions")
    questions_review_parser.add_argument("--limit", type=int, default=20, help="Сколько pending questions показать")
    questions_review_parser.add_argument(
        "action",
        nargs="?",
        choices=["list", "accept", "archive"],
        default="list",
        help="Действие review",
    )
    questions_review_parser.add_argument("question_id", nargs="?", type=int, help="ID question для accept/archive")
    questions_review_parser.set_defaults(handler=cmd_questions_review)

    questions_audit_parser = subparsers.add_parser(
        "questions-audit",
        parents=[shared_parent],
        help="Read-only audit of generic, duplicate and too-long questions",
    )
    questions_audit_parser.add_argument("--topic", type=int, help="ID темы для аудита")
    questions_audit_parser.add_argument(
        "--max-prompt-chars",
        type=int,
        default=DEFAULT_MAX_QUESTION_PROMPT_CHARS,
        help="Порог длины prompt для too-long finding",
    )
    questions_audit_parser.set_defaults(handler=cmd_questions_audit)

    questions_cleanup_parser = subparsers.add_parser(
        "questions-cleanup",
        parents=[shared_parent],
        help="Archive accepted generic generated questions found by quality audit",
    )
    questions_cleanup_parser.add_argument(
        "target",
        nargs="?",
        default="accepted-generic",
        choices=["accepted-generic"],
        help="Cleanup target: accepted-generic archives accepted generated questions with generic wording",
    )
    questions_cleanup_parser.add_argument("--topic", type=int, help="ID темы для cleanup")
    questions_cleanup_parser.set_defaults(handler=cmd_questions_cleanup)

    questions_source_parser = subparsers.add_parser(
        "questions-source",
        parents=[shared_parent],
        help="Refresh whitelisted source metadata and prepare source-backed candidates",
    )
    questions_source_parser.add_argument(
        "action",
        choices=["refresh", "candidates", "auto-curate", "audit", "undo"],
        help="Source metadata action",
    )
    questions_source_parser.add_argument("--topic", type=int, help="ID темы для auto-curation/audit/undo")
    questions_source_parser.add_argument("--question", type=int, help="ID question для audit/undo")
    questions_source_parser.add_argument(
        "--status",
        choices=QUESTION_SOURCE_QUALITY_STATUSES,
        help="Resulting source_quality status для audit display/undo filter",
    )
    questions_source_parser.add_argument("--limit", type=int, default=20, help="Сколько audit decisions показать")
    questions_source_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Показать результат без записи в SQLite",
    )
    questions_source_parser.add_argument(
        "--llm-curator",
        action="store_true",
        help="Перед применением статусов прогнать quarantined candidates через strict LLM curator rubric",
    )
    questions_source_parser.set_defaults(handler=cmd_questions_source)

    session_parser = subparsers.add_parser(
        "session", parents=[shared_parent], help="Начать ежедневную сессию"
    )
    session_parser.add_argument("--topic", type=int, help="ID темы")
    session_parser.add_argument("--minutes", type=int, default=60, help="Целевая длительность")
    session_parser.add_argument("--no-feedback", action="store_true", help="Не запрашивать AI feedback")
    session_parser.set_defaults(handler=cmd_session)

    add_parser = subparsers.add_parser(
        "add-question", parents=[shared_parent], help="Создать структурированный вопрос из свободного текста"
    )
    add_parser.add_argument("--topic", type=int, required=True, help="ID темы")
    add_parser.add_argument("text", nargs="*", help="Идея вопроса. Если не указана, используется stdin.")
    add_parser.set_defaults(handler=cmd_add_question)

    generate_seed_parser = subparsers.add_parser(
        "generate-seed",
        parents=[shared_parent],
        help="Сгенерировать starter pack тем и вопросов через локальную LLM",
    )
    generate_seed_parser.add_argument("--topics", type=int, default=3, help="Сколько тем сгенерировать")
    generate_seed_parser.add_argument(
        "--questions-per-topic",
        type=int,
        default=3,
        help="Сколько вопросов сгенерировать на тему",
    )
    generate_seed_parser.add_argument("--dry-run", action="store_true", help="Показать результат без записи в SQLite")
    generate_seed_parser.set_defaults(handler=cmd_generate_seed)

    curriculum_status_parser = subparsers.add_parser(
        "curriculum-status",
        parents=[shared_parent],
        help="Показать покрытие generated curriculum и пустые зоны",
    )
    curriculum_status_parser.add_argument("--source", default="llm-seed", help="Источник curriculum для проверки")
    curriculum_status_parser.set_defaults(handler=cmd_curriculum_status)

    enqueue_parser = subparsers.add_parser(
        "content-enqueue",
        parents=[shared_parent],
        help="Поставить задачу фоновой генерации контента в SQLite-очередь",
    )
    enqueue_parser.add_argument("--topic", type=int, required=True, help="ID темы")
    enqueue_parser.add_argument(
        "--kind",
        choices=[
            JOB_KIND_QUESTION,
            JOB_KIND_LEARNING_MATERIAL,
            JOB_KIND_SYSTEM_DESIGN_SCENARIO,
            JOB_KIND_REFERENCE_ANSWER,
        ],
        default=JOB_KIND_QUESTION,
        help="Тип контента для генерации",
    )
    enqueue_parser.add_argument("text", nargs="*", help="Заметка для генерации")
    enqueue_parser.set_defaults(handler=cmd_content_enqueue)

    jobs_parser = subparsers.add_parser(
        "content-jobs",
        parents=[shared_parent],
        help="Показать задачи фоновой генерации контента",
    )
    jobs_parser.add_argument("--status", choices=["queued", "running", "done", "failed"], help="Фильтр по статусу")
    jobs_parser.add_argument("--limit", type=int, default=20, help="Сколько задач показать")
    jobs_parser.set_defaults(handler=cmd_content_jobs)

    retry_parser = subparsers.add_parser(
        "content-retry",
        parents=[shared_parent],
        help="Вернуть failed/running/done задачу генерации в queued",
    )
    retry_parser.add_argument("job_id", type=int, help="ID задачи")
    retry_parser.set_defaults(handler=cmd_content_retry)

    worker_parser = subparsers.add_parser(
        "content-worker",
        parents=[shared_parent],
        help="Обработать очередь фоновой генерации контента",
    )
    worker_parser.add_argument("--once", action="store_true", help="Обработать доступные задачи и завершиться")
    worker_parser.add_argument("--limit", type=int, default=1, help="Максимум задач за один запуск с --once")
    worker_parser.add_argument("--interval", type=float, default=5.0, help="Пауза между проверками очереди")
    worker_parser.set_defaults(handler=cmd_content_worker)

    stats_parser = subparsers.add_parser("stats", parents=[shared_parent], help="Показать прогресс")
    stats_parser.set_defaults(handler=cmd_stats)

    evaluations_parser = subparsers.add_parser(
        "evaluations",
        parents=[shared_parent],
        help="Показать сохраненную rubric evaluation для ответа",
    )
    evaluations_parser.add_argument("--answer", type=int, required=True, help="ID ответа")
    evaluations_parser.set_defaults(handler=cmd_evaluations)

    evaluation_override_parser = subparsers.add_parser(
        "evaluation-override",
        parents=[shared_parent],
        help="Вручную исправить score одной rubric dimension с audit metadata",
    )
    evaluation_override_parser.add_argument("--evaluation", type=int, required=True, help="ID rubric evaluation")
    evaluation_override_parser.add_argument("--dimension", required=True, help="Slug rubric dimension")
    evaluation_override_parser.add_argument("--score", type=int, required=True, help="Manual score 1..5")
    evaluation_override_parser.add_argument("--reason", default="", help="Почему AI score исправлен")
    evaluation_override_parser.set_defaults(handler=cmd_evaluation_override)

    session_summary_parser = subparsers.add_parser(
        "session-summary",
        parents=[shared_parent],
        help="Показать сохраненный outcome завершенной practice session",
    )
    session_summary_parser.add_argument("session_id", type=int, help="ID practice session")
    session_summary_parser.set_defaults(handler=cmd_session_summary)

    interview_report_parser = subparsers.add_parser(
        "interview-report",
        parents=[shared_parent],
        help="Export Markdown interview readiness report",
    )
    interview_report_parser.add_argument(
        "--session",
        type=int,
        help="ID completed practice session; defaults to latest completed session",
    )
    interview_report_parser.add_argument(
        "--answers",
        type=int,
        default=5,
        help="Сколько evidence answers включить",
    )
    interview_report_parser.set_defaults(handler=cmd_interview_report)

    system_design_history_parser = subparsers.add_parser(
        "system-design-history",
        parents=[shared_parent],
        help="Показать system design scenarios, transcript, artifacts и final feedback",
    )
    system_design_history_parser.add_argument("--topic", type=int, help="ID system design topic")
    system_design_history_parser.add_argument("--scenario", type=int, help="Открыть history конкретного scenario")
    system_design_history_parser.add_argument("--feedback", type=int, help="Открыть конкретный final feedback")
    system_design_history_parser.add_argument("--limit", type=int, default=10, help="Сколько элементов показать")
    system_design_history_parser.set_defaults(handler=cmd_system_design_history)

    llm_parser = subparsers.add_parser("llm-check", parents=[shared_parent], help="Проверить подключение к Ollama")
    llm_parser.set_defaults(handler=cmd_llm_check)

    config_init_parser = subparsers.add_parser(
        "config-init",
        parents=[shared_parent],
        help="Создать пример config/interview_prep.toml",
    )
    config_init_parser.add_argument("--force", action="store_true", help="Перезаписать существующий config")
    config_init_parser.set_defaults(handler=cmd_config_init, no_services=True)

    config_show_parser = subparsers.add_parser(
        "config-show",
        parents=[shared_parent],
        help="Показать эффективные настройки",
    )
    config_show_parser.set_defaults(handler=cmd_config_show, no_services=True)

    tui_parser = subparsers.add_parser("tui", parents=[shared_parent], help="Запустить полноэкранный TUI workspace")
    tui_parser.set_defaults(handler=cmd_tui, no_services=True)

    app_parser = subparsers.add_parser("app", parents=[shared_parent], help="Алиас для TUI workspace")
    app_parser.set_defaults(handler=cmd_tui, no_services=True)

    return parser


def cmd_init(args: argparse.Namespace, services: AppServices) -> int:
    topics = services.questions.list_topics()
    questions = services.questions.list_questions()
    print(f"База готова: {args.db}")
    print(f"Тем: {len(topics)}")
    print(f"Вопросов: {len(questions)}")
    return 0


def cmd_topics(args: argparse.Namespace, services: AppServices) -> int:
    for topic in services.questions.list_topics():
        print(f"{topic.id}. {topic.title} [{topic.level}]")
        print(f"   {topic.description}")
    return 0


def cmd_questions(args: argparse.Namespace, services: AppServices) -> int:
    questions = services.questions.list_questions(args.topic, tag_slug=args.tag)
    if not questions:
        print("Вопросы не найдены.")
        return 1
    topics = {topic.id: topic.title for topic in services.questions.list_topics()}
    for question in questions:
        print(f"\n#{question.id} {topics.get(question.topic_id, 'Неизвестная тема')} [{question.difficulty}]")
        if question.id is not None:
            tags = services.questions.list_question_tags(question.id)
            if tags:
                print(f"Теги: {format_question_tags(tags)}")
            competencies = services.questions.list_question_competencies(question.id)
            if competencies:
                print(f"Компетенции: {format_question_competencies(competencies)}")
        print(question.prompt)
        print(f"Подсказка: {question.hint}")
    return 0


def cmd_questions_review(args: argparse.Namespace, services: AppServices) -> int:
    if args.action == "accept":
        if args.question_id is None:
            print("Укажи ID вопроса: questions-review accept <question-id>", file=sys.stderr)
            return 1
        return update_review_question_status(args.question_id, "accept", services)
    if args.action == "archive":
        if args.question_id is None:
            print("Укажи ID вопроса: questions-review archive <question-id>", file=sys.stderr)
            return 1
        return update_review_question_status(args.question_id, "archive", services)

    questions = services.questions.list_pending_review_questions(topic_id=args.topic)
    if args.limit > 0:
        questions = questions[: args.limit]
    if not questions:
        print("Manual audit queue empty: pending generated questions не найдены.")
        return 0

    topic_label = f" для topic #{args.topic}" if args.topic is not None else ""
    print(f"Generated question audit queue{topic_label}: {len(questions)}")
    print("Auto-curation is the happy path; use this list only for pending_review audit exceptions.")
    topics = {topic.id: topic.title for topic in services.questions.list_topics()}
    for question in questions:
        print()
        latest_audit = latest_question_auto_curation_audit(services, question.id)
        print(format_review_question_for_cli(question, topics.get(question.topic_id, "Неизвестная тема"), latest_audit))
    print(
        "\nAudit actions: questions-review accept <id> вручную принимает exception; "
        "questions-review archive <id> вручную архивирует exception."
    )
    return 0


def update_review_question_status(question_id: int, action: str, services: AppServices) -> int:
    try:
        if action == "accept":
            question = services.questions.accept_review_question(question_id)
        else:
            question = services.questions.archive_review_question(question_id)
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    print(f"Manual audit override: Question #{question.id} {question.source_quality_status}.")
    return 0


def latest_question_auto_curation_audit(
    services: AppServices,
    question_id: int | None,
) -> QuestionAutoCurationAudit | None:
    if question_id is None:
        return None
    audits = services.repository.list_question_auto_curation_audits(question_id=question_id, limit=1)
    return audits[0] if audits else None


def format_review_question_for_cli(
    question: Question,
    topic_title: str,
    latest_audit: QuestionAutoCurationAudit | None = None,
) -> str:
    source_retrieved_at = (
        question.source_retrieved_at.isoformat(timespec="seconds") if question.source_retrieved_at else "-"
    )
    category_hints = ", ".join(question.source_category_hints) or "-"
    quality_flags = ", ".join(generated_question_quality_flags(question.prompt)) or "-"
    lines = [
        f"#{question.id} {topic_title} [{question.difficulty}]",
        f"Source: {question.source}",
        f"Status: {question.source_quality_status}",
        f"Source metadata: url={question.source_url or '-'} retrieved_at={source_retrieved_at}",
        f"Category hints: {category_hints}",
        f"Frequency hint: {question.source_frequency_hint or '-'}",
        f"Quality flags: {quality_flags}",
    ]
    if latest_audit is not None:
        lines.extend(format_review_question_audit_context_for_cli(question, latest_audit))
    lines.extend(
        [
            f"Prompt: {question.prompt}",
            f"Hint: {question.hint}",
            f"Reference: {question.reference_answer}",
        ]
    )
    return "\n".join(lines)


def format_review_question_audit_context_for_cli(
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
            f"Latest auto-curation audit: #{audit.id or '-'} decision={audit.decision} "
            f"confidence={audit.confidence:.2f}"
        ),
        f"Curator rationale: {audit.rationale}",
        f"Source evidence: {source_evidence}",
        f"Undo hint: {undo_hint}",
    ]


def cmd_questions_audit(args: argparse.Namespace, services: AppServices) -> int:
    try:
        findings = services.question_quality_audit.audit(
            topic_id=args.topic,
            max_prompt_chars=args.max_prompt_chars,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    topic_label = f" for topic #{args.topic}" if args.topic is not None else ""
    if not findings:
        print(f"Question quality audit{topic_label}: no findings.")
        return 0

    print(f"Question quality audit findings{topic_label}: {len(findings)}")
    for finding in findings:
        print()
        print(format_question_quality_finding_for_cli(finding))
    return 0


def cmd_questions_cleanup(args: argparse.Namespace, services: AppServices) -> int:
    try:
        result = services.question_quality_audit.archive_accepted_generic_generated_questions(
            topic_id=args.topic,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    topic_label = f" for topic #{args.topic}" if args.topic is not None else ""
    if not result.archived_questions:
        print(f"Question quality cleanup{topic_label}: no accepted generic generated questions archived.")
        return 0

    print(
        f"Question quality cleanup{topic_label}: archived "
        f"{len(result.archived_questions)} accepted generic generated question(s)."
    )
    topics = {topic.id: topic.title for topic in services.questions.list_topics()}
    for question in result.archived_questions:
        print(f"#{question.id} topic={topics.get(question.topic_id, f'topic #{question.topic_id}')} status=archived")
    return 0


def format_question_quality_finding_for_cli(finding: QuestionQualityFinding) -> str:
    question = finding.question
    lines = [
        f"#{question.id} kind={finding.kind} topic={finding.topic_title}",
        (
            f"source={question.source} "
            f"source_quality={question.source_quality_status} "
            f"status={question.source_quality_status}"
        ),
        f"detail={finding.detail}",
        f"prompt={question.prompt}",
    ]
    if finding.duplicate_of_id is not None:
        lines.insert(2, f"duplicate_of=#{finding.duplicate_of_id}")
    return "\n".join(lines)


def cmd_questions_source(args: argparse.Namespace, services: AppServices) -> int:
    if args.action == "refresh":
        result = services.question_sources.refresh(dry_run=args.dry_run)
        mode = "dry-run" if result.dry_run else "saved"
        print(f"Question source refresh {mode}: {len(result.snapshots)} whitelisted source(s).")
        for snapshot in result.snapshots:
            print()
            print(format_question_source_snapshot_for_cli(snapshot))
        if result.dry_run:
            print("\nDry run: no source snapshots saved and no questions created.")
        else:
            print(f"\nSaved {result.saved_count} source snapshot metadata row(s); no questions created.")
        return 0

    if args.action == "candidates":
        result = services.question_sources.create_source_backed_candidates(dry_run=args.dry_run)
        mode = "dry-run" if result.dry_run else "saved"
        print(f"Question source candidates {mode}: {len(result.candidates)} candidate question(s).")
        if not result.candidates:
            print("No source snapshots found. Run `questions-source refresh` first.")
            return 0
        topics = {topic.id: topic.title for topic in services.questions.list_topics()}
        for question in result.candidates:
            print()
            print(format_source_backed_candidate_for_cli(question, topics.get(question.topic_id)))
        if result.dry_run:
            print("\nDry run: no candidate questions saved.")
        else:
            print(
                "\nCreated "
                f"{result.created_count} source-backed candidate question(s); "
                f"skipped {result.skipped_count} existing or unavailable candidate(s)."
            )
        return 0

    if args.action == "audit":
        try:
            audits = services.repository.list_question_auto_curation_audits(
                question_id=args.question,
                topic_id=args.topic,
                resulting_status=args.status,
                limit=args.limit,
            )
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        filters = []
        if args.question is not None:
            filters.append(f"question #{args.question}")
        if args.topic is not None:
            filters.append(f"topic #{args.topic}")
        if args.status is not None:
            filters.append(f"status {args.status}")
        filter_label = f" for {', '.join(filters)}" if filters else ""
        print(f"Question source auto-curation audit{filter_label}: {len(audits)} decision(s).")
        if not audits:
            print("No auto-curation audit decisions found.")
            return 0
        topics = {topic.id: topic.title for topic in services.questions.list_topics()}
        for audit in audits:
            question = services.repository.get_question(audit.question_id)
            print()
            print(format_auto_curation_audit_for_cli(audit, question, topics.get(question.topic_id) if question else None))
        return 0

    if args.action == "undo":
        try:
            result = services.question_auto_curation.undo_latest_decision(
                question_id=args.question,
                topic_id=args.topic,
                resulting_status=args.status,
                dry_run=args.dry_run,
            )
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        question = services.repository.get_question(result.audit.question_id)
        topic = None
        if question is not None:
            topic = {item.id: item.title for item in services.questions.list_topics()}.get(question.topic_id)
        print(format_auto_curation_undo_for_cli(result, topic))
        return 0

    if args.action == "auto-curate":
        try:
            if args.dry_run:
                result = services.question_auto_curation.preview_pending_source_backed_candidates(
                    topic_id=args.topic,
                    use_llm_curator=args.llm_curator,
                )
            else:
                result = services.question_auto_curation.apply_pending_source_backed_candidates(
                    topic_id=args.topic,
                    use_llm_curator=args.llm_curator,
                )
        except ValueError as error:
            print(str(error), file=sys.stderr)
            return 1
        topic_label = f" for topic #{args.topic}" if args.topic is not None else ""
        mode = "dry-run" if result.dry_run else "apply"
        print(f"Question source auto-curation {mode}{topic_label}: {len(result.decisions)} pending candidate(s).")
        if not result.decisions:
            print("No pending source-backed candidates found.")
            return 0
        for decision in result.decisions:
            print()
            print(format_auto_curation_decision_for_cli(decision))
        if result.dry_run:
            suffix = " LLM curator rubric was enabled." if args.llm_curator else ""
            print(f"\nDry run: no question statuses changed.{suffix}")
        else:
            mode_label = "auto-curation" if args.llm_curator else "deterministic"
            print(
                f"\nApplied {mode_label} decisions: "
                f"accepted {result.accepted_count}, archived {result.archived_count}, "
                f"quarantined {result.quarantined_count} left pending_auto_review."
            )
        return 0

    print(f"Unsupported questions-source action: {args.action}", file=sys.stderr)
    return 1


def format_question_source_snapshot_for_cli(snapshot: QuestionSourceSnapshot) -> str:
    return "\n".join(
        [
            f"{snapshot.source_id} title={snapshot.title}",
            f"url={snapshot.url}",
            (
                f"retrieved_at={snapshot.retrieved_at.isoformat(timespec='seconds')} "
                f"checksum={snapshot.checksum}"
            ),
            f"category_hints={', '.join(snapshot.category_hints)}",
        ]
    )


def format_source_backed_candidate_for_cli(question: Question, topic_title: str | None) -> str:
    topic_label = topic_title or f"topic #{question.topic_id}"
    source_retrieved_at = (
        question.source_retrieved_at.isoformat(timespec="seconds") if question.source_retrieved_at else "unknown"
    )
    return "\n".join(
        [
            f"#{question.id or '-'} topic={topic_label} status={question.source_quality_status}",
            f"source={question.source} url={question.source_url or '-'} retrieved_at={source_retrieved_at}",
            f"category_hints={', '.join(question.source_category_hints)}",
            f"frequency_hint={question.source_frequency_hint or '-'}",
            f"prompt={question.prompt}",
        ]
    )


def format_auto_curation_decision_for_cli(decision: QuestionAutoCurationDecision) -> str:
    question = decision.question
    source_retrieved_at = (
        question.source_retrieved_at.isoformat(timespec="seconds") if question.source_retrieved_at else "unknown"
    )
    lines = [
        (
            f"#{question.id or '-'} topic={decision.topic_title} "
            f"decision={decision.decision} confidence={decision.confidence:.2f}"
        ),
        f"status={question.source_quality_status} source={question.source}",
        f"url={question.source_url or '-'} retrieved_at={source_retrieved_at}",
        f"category_hints={', '.join(question.source_category_hints) or '-'}",
        f"frequency_hint={question.source_frequency_hint or '-'}",
        f"quality_flags={', '.join(decision.quality_flags) or '-'}",
        f"rationale={decision.rationale}",
        f"prompt={question.prompt}",
    ]
    if decision.curator_score is not None:
        lines.insert(-1, f"curator_score={decision.curator_score}")
    if decision.curator_source_evidence:
        lines.insert(-1, f"curator_source_evidence={decision.curator_source_evidence}")
    if decision.duplicate_of_id is not None:
        lines.insert(2, f"duplicate_of=#{decision.duplicate_of_id}")
    return "\n".join(lines)


def format_auto_curation_audit_for_cli(
    audit: QuestionAutoCurationAudit,
    question: Question | None,
    topic_title: str | None,
) -> str:
    retrieved_at = audit.source_retrieved_at.isoformat(timespec="seconds") if audit.source_retrieved_at else "unknown"
    current_status = question.source_quality_status if question else "missing"
    topic_label = topic_title or (f"topic #{question.topic_id}" if question else "unknown")
    prompt = question.prompt if question else "question row is unavailable"
    lines = [
        (
            f"#{audit.id or '-'} question=#{audit.question_id} topic={topic_label} "
            f"decision={audit.decision} confidence={audit.confidence:.2f}"
        ),
        f"status={audit.previous_status} -> {audit.resulting_status} current={current_status}",
        f"curator={audit.curator_model} version={audit.curator_version} score={audit.curator_score or '-'}",
        f"url={audit.source_url or '-'} retrieved_at={retrieved_at}",
        f"category_hints={', '.join(audit.source_category_hints) or '-'}",
        f"frequency_hint={audit.source_frequency_hint or '-'}",
        f"quality_flags={', '.join(audit.quality_flags) or '-'}",
        f"source_evidence={audit.curator_source_evidence or '-'}",
        f"rationale={audit.rationale}",
        f"prompt={prompt}",
    ]
    if audit.duplicate_of_id is not None:
        lines.insert(2, f"duplicate_of=#{audit.duplicate_of_id}")
    return "\n".join(lines)


def format_auto_curation_undo_for_cli(
    result: QuestionAutoCurationUndoResult,
    topic_title: str | None,
) -> str:
    audit = result.audit
    question = result.question_before
    topic_label = topic_title or f"topic #{question.topic_id}"
    mode = "undo dry-run" if result.dry_run else "undo"
    if result.dry_run:
        status_line = (
            f"would_restore={question.source_quality_status} -> {audit.previous_status}"
            if result.changed
            else f"would_keep={question.source_quality_status}"
        )
    else:
        status_line = (
            f"status={result.question_before.source_quality_status} -> {result.question_after.source_quality_status}"
            if result.changed
            else f"status={result.question_after.source_quality_status} unchanged"
        )
    return "\n".join(
        [
            f"Question source auto-curation {mode}: audit #{audit.id or '-'} question #{audit.question_id}.",
            f"topic={topic_label} decision={audit.decision}",
            status_line,
            "audit_row=kept",
            f"prompt={question.prompt}",
        ]
    )


def format_question_tags(tags: Sequence[Tag]) -> str:
    labels = []
    for tag in tags:
        labels.append(f"{tag.title} ({tag.slug})" if tag.title != tag.slug else tag.title)
    return ", ".join(labels)


def format_question_competencies(links: Sequence[QuestionCompetencyLink]) -> str:
    labels = []
    for link in links:
        competency = link.competency
        label = f"{competency.title} ({competency.slug})"
        if link.is_primary:
            label += " [основная]"
        labels.append(label)
    return ", ".join(labels)


def cmd_add_question(args: argparse.Namespace, services: AppServices) -> int:
    text = " ".join(args.text).strip()
    if not text:
        text = sys.stdin.read().strip()
    if not text:
        print("Идея вопроса пустая.", file=sys.stderr)
        return 1
    question = services.questions.add_from_free_text(text, args.topic)
    print(f"Вопрос сохранен: #{question.id} [{question.difficulty}]")
    print(question.prompt)
    return 0


def cmd_generate_seed(args: argparse.Namespace, services: AppServices) -> int:
    action = "Генерирую starter pack через Ollama/fallback"
    if args.dry_run:
        action += " без записи в SQLite"
    print(f"{action}...")
    result = services.curriculum.generate_and_save(
        topic_count=args.topics,
        questions_per_topic=args.questions_per_topic,
        dry_run=args.dry_run,
    )
    if getattr(services.llm, "last_error", None):
        print(f"Ollama недоступна или timeout, использован fallback. Деталь: {services.llm.last_error}")
    print(f"Тем в плане: {len(result.curriculum.topics)}")
    print(f"Тем сохранено: {result.topics_saved}")
    print(f"Curriculum topics сохранено: {result.curriculum_topics_saved}")
    print(f"Subtopics сохранено: {result.subtopics_saved}")
    print(f"Learning objectives сохранено: {result.objectives_saved}")
    print(f"Новых вопросов сохранено: {result.questions_saved}")
    for topic in result.curriculum.topics:
        print(f"\n{topic.title} [{topic.level}]")
        print(f"Slug: {topic.slug}")
        print(topic.description)
        if topic.objectives:
            print("Objectives:")
            for objective in topic.objectives:
                print(f"- {objective}")
        if topic.subtopics:
            print("Subtopics:")
            for subtopic in topic.subtopics:
                print(f"- {subtopic.title}: {subtopic.description}")
                for objective in subtopic.objectives:
                    print(f"  - {objective}")
        print("Questions:")
        for question in topic.questions:
            print(f"- [{question.difficulty}] {question.prompt}")
        if topic.mock_scenarios:
            print("Mock scenarios:")
            for scenario in topic.mock_scenarios:
                print(f"- {scenario}")
    return 0


def cmd_curriculum_status(args: argparse.Namespace, services: AppServices) -> int:
    print(format_curriculum_status_for_cli(services.curriculum.status(source=args.source)))
    return 0


def format_curriculum_status_for_cli(status: CurriculumStatus) -> str:
    lines = [
        f"Curriculum status (source={status.source})",
        f"App topics: {status.app_topic_count}",
        f"Curriculum topics: {status.curriculum_topic_count}",
        f"Subtopics: {status.subtopic_count}",
        f"Learning objectives: {status.objective_count}",
        f"Generated questions: {status.question_count}",
    ]
    if status.topics:
        lines.append("Topics:")
        for topic_status in status.topics:
            curriculum_topic = topic_status.curriculum_topic
            linked_topic = topic_status.topic_title or "н/д"
            lines.append(
                f"- {curriculum_topic.slug} -> {linked_topic}: "
                f"subtopics {topic_status.subtopic_count}, "
                f"objectives {topic_status.objective_count}, "
                f"questions {topic_status.question_count}"
            )
    lines.append("Empty zones:")
    if status.empty_zones:
        lines.extend(f"- {zone}" for zone in status.empty_zones)
    else:
        lines.append("- none")
    return "\n".join(lines)


def cmd_content_enqueue(args: argparse.Namespace, services: AppServices) -> int:
    note = " ".join(args.text).strip()
    if not note:
        note = sys.stdin.read().strip()
    job = services.content_generation.enqueue(args.kind, args.topic, note)
    print(f"Задача поставлена в очередь: #{job.id} [{job.kind}] {job.status}")
    return 0


def cmd_content_jobs(args: argparse.Namespace, services: AppServices) -> int:
    jobs = services.content_generation.list_jobs(status=args.status, limit=args.limit)
    if not jobs:
        print("Задачи не найдены.")
        return 0
    for job in jobs:
        print(f"#{job.id} [{job.kind}] {job.status} created={job.created_at.isoformat(timespec='seconds')}")
        if job.result_json:
            print(f"  result: {job.result_json}")
        if job.error:
            print(f"  error: {job.error}")
    return 0


def cmd_content_retry(args: argparse.Namespace, services: AppServices) -> int:
    services.content_generation.retry_job(args.job_id)
    print(f"Задача #{args.job_id} возвращена в queued.")
    return 0


def cmd_content_worker(args: argparse.Namespace, services: AppServices) -> int:
    processed = 0
    print("Content worker started. Ctrl+C - остановить.")
    try:
        while True:
            result = services.content_generation.process_next_job()
            if result is None:
                if args.once:
                    break
                time.sleep(max(0.1, args.interval))
                continue
            processed += 1
            job = result.job
            if result.created_question is None:
                if job.status == "done" and result.artifact:
                    print(f"#{job.id} done: {job.kind}")
                elif job.status == "queued":
                    retry = parse_payload(job.payload_json).get("retry")
                    retry_text = ""
                    if isinstance(retry, dict):
                        attempt = retry.get("attempt")
                        max_attempts = retry.get("max_attempts")
                        next_attempt_at = retry.get("next_attempt_at")
                        last_error = retry.get("last_error")
                        retry_parts = []
                        if attempt is not None and max_attempts is not None:
                            retry_parts.append(f"{attempt}/{max_attempts}")
                        if next_attempt_at:
                            retry_parts.append(f"next {next_attempt_at}")
                        if last_error:
                            retry_parts.append(str(last_error))
                        retry_text = f": {'; '.join(retry_parts)}" if retry_parts else ""
                    print(f"#{job.id} retry scheduled{retry_text}")
                else:
                    print(f"#{job.id} failed: {job.error}")
            else:
                print(f"#{job.id} done: question #{result.created_question.id}")
            if args.once and processed >= max(1, args.limit):
                break
    except KeyboardInterrupt:
        print("\nContent worker stopped.")
    print(f"Обработано задач: {processed}")
    return 0


def cmd_stats(args: argparse.Namespace, services: AppServices) -> int:
    stats = services.stats.dashboard()
    print("Прогресс")
    print(f"Сессий начато/завершено: {stats['session_count']}")
    print(f"Ответов сохранено: {stats['answered_count']}")
    print(f"Предложенная тема: {stats['suggested_topic'] or 'н/д'}")
    print()
    print(format_readiness_for_cli(services.readiness.snapshot()))

    print("\nПоследние сессии")
    if stats["recent_sessions"]:
        for item in stats["recent_sessions"]:
            topic = item["topic_title"] or "смешанная"
            ended = item["ended_at"] or "в процессе"
            status = {
                "completed": "завершена",
                "abandoned": "abandoned",
                "in_progress": "в процессе",
            }.get(item.get("status"), item.get("status") or "н/д")
            print(
                f"- #{item['id']} {item['started_at']} -> {ended}, "
                f"{topic}, статус {status}, ответов {item['answers']}"
            )
    else:
        print("- н/д")

    print("\nДинамика по темам")
    for item in stats["topic_dynamics"]:
        print(f"- {item['title']}: ответов {item['answers']}")
    return 0


def format_readiness_for_cli(snapshot: ReadinessSnapshot) -> str:
    overall = snapshot.overall_summary
    signal = f"{overall.signal_score}/100" if overall.signal_score is not None else "н/д"
    lines = [
        "Senior readiness",
        f"Signal: {signal}",
        f"Label: {overall.label}",
        f"Summary: {overall.summary}",
        f"Caveat: {overall.caveat}",
    ]
    if snapshot.weekly_trend:
        lines.append("Weekly readiness trend:")
        for point in snapshot.weekly_trend:
            lines.append(
                f"- {point.week_start.isoformat()}..{point.week_end.isoformat()}: "
                f"sessions {point.session_count}, avg delta {point.avg_readiness_delta:+.2f}, "
                f"total {point.total_readiness_delta:+.2f}"
            )
    lines.append("Top gaps:")
    if overall.top_gaps:
        for gap in overall.top_gaps:
            reasons = "; ".join(gap.reasons)
            lines.append(
                f"- {gap.competency.title} ({gap.competency.slug}): "
                f"{gap.readiness_score}/100; {reasons}"
            )
            lines.append(f"  Next action: {gap.next_action}")
    else:
        lines.append("- н/д")
    lines.append("Must fix before interview:")
    if overall.top_gaps:
        for index, gap in enumerate(overall.top_gaps, start=1):
            lines.append(f"{index}. {gap.must_fix_drill}")
    else:
        lines.append("- н/д")
    return "\n".join(lines)


def cmd_evaluations(args: argparse.Namespace, services: AppServices) -> int:
    evaluations = services.evaluations.list_answer_evaluations(args.answer)
    if not evaluations:
        print(f"Rubric evaluations для ответа #{args.answer} не найдены.")
        return 1

    for index, evaluation in enumerate(evaluations):
        if index:
            print()
        print(format_answer_evaluation_for_cli(evaluation))
    return 0


def cmd_evaluation_override(args: argparse.Namespace, services: AppServices) -> int:
    try:
        evaluation = services.evaluations.override_score(
            args.evaluation,
            dimension_slug=args.dimension,
            score=args.score,
            reason=args.reason,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    score = next(
        (item for item in evaluation.scores if item.dimension.slug == args.dimension.strip()),
        None,
    )
    if score is None:
        print(f"Override сохранен для evaluation #{evaluation.id}.")
        return 0
    session = services.repository.get_session(evaluation.session_id)
    if session is not None and session.status == SESSION_STATUS_COMPLETED:
        services.sessions.generate_session_outcome(evaluation.session_id)
    print(
        f"Override сохранен: evaluation #{evaluation.id}, "
        f"{score.dimension.slug} {score.effective_score}/5 (original {score.score}/5)."
    )
    return 0


def cmd_session_summary(args: argparse.Namespace, services: AppServices) -> int:
    try:
        outcome = services.sessions.get_session_outcome(args.session_id)
    except ValueError:
        print(f"Session #{args.session_id} не найдена.", file=sys.stderr)
        return 1
    if outcome is None:
        print(f"Session outcome для session #{args.session_id} не найден.")
        return 1

    print(format_session_outcome_for_cli(outcome))
    return 0


def cmd_interview_report(args: argparse.Namespace, services: AppServices) -> int:
    try:
        report = services.interview_report.markdown(
            session_id=args.session,
            answer_limit=args.answers,
        )
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(report)
    return 0


def cmd_system_design_history(args: argparse.Namespace, services: AppServices) -> int:
    if args.scenario is not None and args.feedback is not None:
        print("Укажи только один detail selector: --scenario или --feedback.", file=sys.stderr)
        return 1

    if args.feedback is not None:
        feedback = services.repository.get_system_design_feedback_artifact(args.feedback)
        if feedback is None:
            print(f"System design feedback #{args.feedback} не найден.", file=sys.stderr)
            return 1
        print(format_system_design_feedback_history_for_cli(feedback, services))
        return 0

    if args.scenario is not None:
        scenario = services.repository.get_system_design_scenario(args.scenario, include_archived=True)
        if scenario is None:
            print(f"System design scenario #{args.scenario} не найден.", file=sys.stderr)
            return 1
        print(format_system_design_scenario_history_for_cli(scenario, services, limit=args.limit))
        return 0

    topic_id = args.topic
    if topic_id is None:
        topic = services.repository.find_topic_by_slug("system-design")
        if topic is None or topic.id is None:
            print("System design topic не найден.", file=sys.stderr)
            return 1
        topic_id = topic.id

    topic = services.repository.get_topic(topic_id)
    topic_title = topic.title if topic is not None else f"Topic #{topic_id}"
    limit = max(1, args.limit)
    feedbacks = sorted(
        services.repository.list_system_design_feedback_artifacts(topic_id, limit=limit),
        key=lambda feedback: (feedback.created_at, feedback.id or 0),
        reverse=True,
    )
    scenarios = services.repository.list_system_design_scenarios(topic_id=topic_id, limit=limit)

    lines = [
        "System design history",
        f"Topic: #{topic_id} {topic_title}",
        "",
        "Feedback artifacts:",
    ]
    if feedbacks:
        for feedback in feedbacks:
            lines.append(format_system_design_feedback_summary_for_cli(feedback, services))
    else:
        lines.append("- нет сохраненного final feedback")

    lines.extend(["", "Scenarios:"])
    if scenarios:
        for scenario in scenarios:
            focus = ", ".join(scenario.focus_areas) if scenario.focus_areas else "нет"
            lines.append(
                f"- Scenario #{scenario.id}: {scenario.title} | "
                f"Created: {scenario.created_at.isoformat(timespec='minutes')} | "
                f"Source: {scenario.source} | Focus: {focus}"
            )
    else:
        lines.append("- нет сохраненных scenarios")

    lines.extend(["", "Open: system-design-history --feedback <id> или --scenario <id>."])
    print("\n".join(lines))
    return 0


def format_answer_evaluation_for_cli(evaluation: AnswerEvaluation) -> str:
    lines = [
        f"Rubric evaluation #{evaluation.id} для ответа #{evaluation.answer_id}",
        f"Сессия: #{evaluation.session_id}",
        f"Вопрос: #{evaluation.question_id}",
        f"Источник: {evaluation.source}",
        f"Создано: {evaluation.created_at.isoformat(timespec='seconds')}",
        f"Summary: {evaluation.summary}",
    ]
    if evaluation.scores:
        average = sum(score.effective_score for score in evaluation.scores) / len(evaluation.scores)
        lines.append(f"Средний rubric score: {average:.1f}/5")
        lines.append("Scores:")
        for score in evaluation.scores:
            score_label = f"{score.effective_score}/5"
            if score.manual_override_score is not None:
                score_label += f" (manual override; original {score.score}/5)"
            lines.append(f"- {score.dimension.title} ({score.dimension.slug}): {score_label}")
            if score.manual_override_reason:
                lines.append(f"  Override reason: {score.manual_override_reason}")
            if score.manual_override_at:
                lines.append(
                    f"  Override at: {score.manual_override_at.isoformat(timespec='seconds')}"
                )
            lines.append(f"  Evidence: {score.evidence}")
            lines.append(f"  Gaps: {score.gaps}")
            if score.next_drill:
                lines.append(f"  Next drill: {score.next_drill}")
    if evaluation.next_drills:
        lines.append("Next drills:")
        for drill_index, drill in enumerate(evaluation.next_drills, start=1):
            lines.append(f"{drill_index}. {drill}")
    if evaluation.raw_payload_json:
        lines.append(f"Raw payload: {evaluation.raw_payload_json}")
    return "\n".join(lines)


def format_system_design_feedback_history_for_cli(
    feedback: SystemDesignFeedbackArtifact,
    services: AppServices,
) -> str:
    topic = services.repository.get_topic(feedback.topic_id)
    topic_title = topic.title if topic is not None else f"Topic #{feedback.topic_id}"
    scenario = (
        services.repository.get_system_design_scenario(feedback.scenario_id, include_archived=True)
        if feedback.scenario_id is not None
        else None
    )
    transcript = services.repository.list_system_design_transcript_messages(
        feedback.topic_id,
        scenario_id=feedback.scenario_id,
        limit=200,
    )
    artifacts = services.repository.list_system_design_artifacts(
        feedback.topic_id,
        scenario_id=feedback.scenario_id,
        limit=200,
    )
    evaluation = services.repository.get_system_design_evaluation_for_feedback(feedback.id or 0)
    scenario_label = system_design_scenario_label(feedback.scenario_id, scenario)
    session_label = f"#{feedback.session_id}" if feedback.session_id is not None else "нет session"
    lines = [
        f"System design feedback #{feedback.id}",
        f"Topic: #{feedback.topic_id} {topic_title}",
        f"Session: {session_label}",
        f"Scenario: {scenario_label}",
        f"Created: {feedback.created_at.isoformat(timespec='minutes')}",
        f"Source: {feedback.source}",
        "",
        "Scenario text:",
        scenario.scenario if scenario is not None else "default/custom scenario не сохранен отдельной записью",
    ]
    if scenario is not None and scenario.focus_areas:
        lines.extend(["", "Focus areas:", *format_cli_bullets(scenario.focus_areas)])
    lines.extend(["", format_system_design_transcript_for_cli(transcript)])
    lines.extend(["", format_system_design_artifacts_for_cli(artifacts)])
    lines.extend(["", "Final feedback:", feedback.content])
    lines.extend(["", format_system_design_evaluation_for_cli(evaluation)])
    return "\n".join(lines)


def format_system_design_scenario_history_for_cli(
    scenario: SystemDesignScenario,
    services: AppServices,
    limit: int = 10,
) -> str:
    topic = services.repository.get_topic(scenario.topic_id)
    topic_title = topic.title if topic is not None else f"Topic #{scenario.topic_id}"
    transcript = services.repository.list_system_design_transcript_messages(
        scenario.topic_id,
        scenario_id=scenario.id,
        limit=200,
    )
    artifacts = services.repository.list_system_design_artifacts(
        scenario.topic_id,
        scenario_id=scenario.id,
        limit=200,
    )
    feedbacks = sorted(
        services.repository.list_system_design_feedback_artifacts(
            scenario.topic_id,
            scenario_id=scenario.id,
            limit=max(1, limit),
        ),
        key=lambda feedback: (feedback.created_at, feedback.id or 0),
        reverse=True,
    )
    lines = [
        f"System design scenario #{scenario.id}",
        f"Topic: #{scenario.topic_id} {topic_title}",
        f"Title: {scenario.title}",
        f"Created: {scenario.created_at.isoformat(timespec='minutes')}",
        f"Source: {scenario.source}",
        "",
        "Scenario text:",
        scenario.scenario,
    ]
    if scenario.focus_areas:
        lines.extend(["", "Focus areas:", *format_cli_bullets(scenario.focus_areas)])
    lines.extend(["", format_system_design_transcript_for_cli(transcript)])
    lines.extend(["", format_system_design_artifacts_for_cli(artifacts)])
    lines.extend(["", "Feedback artifacts:"])
    if feedbacks:
        for feedback in feedbacks:
            lines.append(format_system_design_feedback_summary_for_cli(feedback, services))
    else:
        lines.append("- нет сохраненного final feedback")
    return "\n".join(lines)


def format_system_design_feedback_summary_for_cli(
    feedback: SystemDesignFeedbackArtifact,
    services: AppServices,
) -> str:
    scenario = (
        services.repository.get_system_design_scenario(feedback.scenario_id, include_archived=True)
        if feedback.scenario_id is not None
        else None
    )
    transcript_count = len(
        services.repository.list_system_design_transcript_messages(
            feedback.topic_id,
            scenario_id=feedback.scenario_id,
            limit=1000,
        )
    )
    artifact_count = len(
        services.repository.list_system_design_artifacts(
            feedback.topic_id,
            scenario_id=feedback.scenario_id,
            limit=1000,
        )
    )
    evaluation = services.repository.get_system_design_evaluation_for_feedback(feedback.id or 0)
    session = f"#{feedback.session_id}" if feedback.session_id is not None else "нет"
    return (
        f"- Feedback #{feedback.id} | Session: {session} | "
        f"Scenario: {system_design_scenario_label(feedback.scenario_id, scenario)} | "
        f"Created: {feedback.created_at.isoformat(timespec='minutes')} | "
        f"Source: {feedback.source} | Transcript: {transcript_count} | "
        f"Artifacts: {artifact_count} | Rubric: {system_design_evaluation_score_label(evaluation)}"
    )


def system_design_scenario_label(
    scenario_id: int | None,
    scenario: SystemDesignScenario | None,
) -> str:
    if scenario is not None:
        return f"#{scenario.id} {scenario.title}"
    if scenario_id is not None:
        return f"#{scenario_id}"
    return "default/custom scenario"


def format_system_design_transcript_for_cli(messages: Sequence[SystemDesignTranscriptMessage]) -> str:
    lines = ["Transcript:"]
    if not messages:
        lines.append("- нет сохраненного transcript")
        return "\n".join(lines)
    for message in messages:
        role = {"candidate": "Кандидат", "interviewer": "Интервьюер"}.get(message.role, message.role)
        lines.append(f"- [{message.created_at.isoformat(timespec='minutes')}] {role}: {message.content}")
    return "\n".join(lines)


def format_system_design_artifacts_for_cli(artifacts: Sequence[SystemDesignArtifact]) -> str:
    lines = ["Artifacts:"]
    if not artifacts:
        lines.append("- нет сохраненных artifacts")
        return "\n".join(lines)
    artifacts_by_section: dict[str, list[SystemDesignArtifact]] = {}
    for artifact in artifacts:
        artifacts_by_section.setdefault(artifact.section, []).append(artifact)
    for section in ("requirements", "api", "data_model", "decisions", "risks"):
        section_artifacts = artifacts_by_section.get(section, [])
        if not section_artifacts:
            continue
        lines.append(f"{section}:")
        for artifact in section_artifacts:
            lines.append(f"- #{artifact.id} {artifact.content}")
    return "\n".join(lines)


def format_system_design_evaluation_for_cli(evaluation: SystemDesignEvaluation | None) -> str:
    if evaluation is None:
        return "\n".join(["System design rubric", "- saved rubric evaluation не найдена"])

    lines = [
        "System design rubric",
        f"Источник: {evaluation.source}",
        f"Создано: {evaluation.created_at.isoformat(timespec='minutes')}",
        f"Summary: {evaluation.summary}",
    ]
    if evaluation.scores:
        average = sum(score.score for score in evaluation.scores) / len(evaluation.scores)
        lines.append(f"Average score: {average:.1f}/5")
        lines.append("Scores:")
        for score in evaluation.scores:
            lines.append(f"- {score.dimension.title} ({score.dimension.slug}): {score.score}/5")
            lines.append(f"  Evidence: {score.evidence}")
            lines.append(f"  Gaps: {score.gaps}")
            if score.next_drill:
                lines.append(f"  Next drill: {score.next_drill}")
    if evaluation.next_drills:
        lines.append("Next drills:")
        for drill_index, drill in enumerate(evaluation.next_drills, start=1):
            lines.append(f"{drill_index}. {drill}")
    return "\n".join(lines)


def system_design_evaluation_score_label(evaluation: SystemDesignEvaluation | None) -> str:
    if evaluation is None or not evaluation.scores:
        return "нет evaluation"
    average = sum(score.score for score in evaluation.scores) / len(evaluation.scores)
    return f"{average:.1f}/5"


def format_session_outcome_for_cli(outcome: SessionOutcome) -> str:
    lines = [
        f"Session outcome #{outcome.id} для session #{outcome.session_id}",
        f"Создано: {outcome.created_at.isoformat(timespec='seconds')}",
        f"Type: {outcome.outcome_type}",
        f"Readiness delta: {outcome.readiness_delta:+.2f}",
        f"Summary: {outcome.summary}",
        "Strengths:",
        *format_cli_bullets(outcome.strengths),
        "Gaps:",
        *format_cli_bullets(outcome.gaps),
        "Next drills:",
        *format_cli_bullets(outcome.next_drills),
    ]
    return "\n".join(lines)


def format_cli_bullets(items: Sequence[str]) -> list[str]:
    if not items:
        return ["- нет данных"]
    return [f"- {item}" for item in items]


def cmd_session(args: argparse.Namespace, services: AppServices) -> int:
    topic_id = args.topic or choose_topic(services)
    session = services.sessions.start_session(topic_id=topic_id, target_minutes=args.minutes)
    topic = services.repository.get_topic(topic_id) if topic_id else None
    print(f"Сессия #{session.id} начата. Цель: {session.target_minutes} минут.")
    if topic:
        print(f"Тема: {topic.title}")
    print("Ответ: введи одну строку и нажми Enter. Для многострочного ответа используй /multi, для выхода /quit.")

    try:
        while True:
            question = services.sessions.next_question(session.id or 0)
            if question is None:
                print("Нет доступных вопросов.")
                break
            print(f"\nВопрос #{question.id} [{question.difficulty}]")
            print(question.prompt)
            if ask_yes_no("Показать подсказку?", default=False):
                print(f"Подсказка: {question.hint}")

            user_answer = read_answer()
            if user_answer == "/quit":
                break
            if not user_answer.strip():
                print("Вопрос пропущен.")
                if not ask_yes_no("Продолжить?", default=True):
                    break
                continue

            print("\nОтвет принят.")
            print("\nЭталонный ответ")
            print(question.reference_answer)
            print("\nСохраняю ответ...")
            answer = services.sessions.answer_question(
                session.id or 0,
                question.id or 0,
                user_answer,
                None,
                with_feedback=False,
            )
            print(f"Ответ сохранен как #{answer.id}.")
            if not args.no_feedback:
                print("Генерирую AI feedback через Ollama. Если модель не ответит вовремя, будет fallback...")
                answer = services.sessions.add_feedback_to_answer(answer, question, user_answer)
                if getattr(services.llm, "last_error", None):
                    print(f"Ollama не ответила штатно, использован fallback. Деталь: {services.llm.last_error}")
                print("Feedback сохранен.")
            if answer.ai_feedback:
                print("\nAI feedback")
                print(answer.ai_feedback)
            if not ask_yes_no("Следующий вопрос?", default=True):
                break
    finally:
        finished = services.sessions.finish_session(session.id or 0, abandon_if_empty=True)
        if finished.status == SESSION_STATUS_ABANDONED:
            print(f"Сессия #{session.id} завершена без ответов и помечена как abandoned.")
        else:
            print(f"Сессия #{session.id} завершена.")
    return 0


def cmd_llm_check(args: argparse.Namespace, services: AppServices) -> int:
    started_at = time.monotonic()
    print("Проверяю Ollama...")
    response = services.llm.generate("Ответь по-русски одной короткой фразой: AI feedback работает.")
    elapsed = time.monotonic() - started_at
    if getattr(services.llm, "last_error", None):
        print(f"Ollama недоступна или timeout. Fallback сработал за {elapsed:.1f} сек.")
        print(f"Деталь: {services.llm.last_error}")
        print(response)
        return 1
    print(f"Ollama ответила за {elapsed:.1f} сек.")
    print(response)
    return 0


def cmd_tui(args: argparse.Namespace, services: AppServices | None) -> int:
    from interview_prep.ui.tui import run_tui

    run_tui(args.db, args.config)
    return 0


def cmd_config_init(args: argparse.Namespace, services: AppServices | None) -> int:
    from pathlib import Path

    existed = Path(args.config).exists()
    path = write_default_config(args.config, overwrite=args.force)
    if existed and not args.force:
        print(f"Config готов: {path}")
        print("Если файл уже существовал, он не был перезаписан. Используй --force для перезаписи.")
    else:
        print(f"Config создан: {path}")
    return 0


def cmd_config_show(args: argparse.Namespace, services: AppServices | None) -> int:
    config = load_config(args.config)
    print(f"Config path: {args.config}")
    print("[ollama]")
    print(f"model = {config.ollama.model}")
    print(f"base_url = {config.ollama.base_url}")
    print(f"timeout_seconds = {config.ollama.timeout_seconds:g}")
    return 0


def choose_topic(services: AppServices) -> int | None:
    topics = services.questions.list_topics()
    suggested = services.stats.dashboard().get("suggested_topic")
    print("Темы")
    for topic in topics:
        marker = " * предложено" if topic.title == suggested else ""
        print(f"{topic.id}. {topic.title} [{topic.level}]{marker}")
    raw = input("Выбери ID темы или нажми Enter для смешанной сессии: ").strip()
    if not raw:
        return None
    try:
        topic_id = int(raw)
    except ValueError:
        print("Некорректный ID темы, использую смешанную сессию.")
        return None
    if services.repository.get_topic(topic_id) is None:
        print("Неизвестный ID темы, использую смешанную сессию.")
        return None
    return topic_id


def ask_yes_no(label: str, default: bool) -> bool:
    suffix = "Y/n" if default else "y/N"
    raw = input(f"{label} [{suffix}] ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes", "д", "да"}


def read_answer() -> str:
    first_line = input("Твой ответ: ").strip()
    if first_line in {"", "/quit"}:
        return first_line
    if first_line != "/multi":
        return first_line

    print("Многострочный ответ. Заверши пустой строкой или одной точкой. /quit завершает сессию.")
    lines: list[str] = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line in {"", "."}:
            break
        if line == "/quit" and not lines:
            return "/quit"
        lines.append(line)
    return "\n".join(lines).strip()
