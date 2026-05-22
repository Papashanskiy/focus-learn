from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

from interview_prep.domain.models import (
    ContentGenerationJob,
    LearningMaterial,
    Question,
    QuestionCompetencyLink,
    QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
    SystemDesignScenario,
    Tag,
)
from interview_prep.domain.rules import normalize_difficulty
from interview_prep.infra.llm import LLMClient
from interview_prep.infra.repositories import SQLiteRepository
from interview_prep.services.curriculum_service import CurriculumService
from interview_prep.services.question_service import QuestionService


JOB_KIND_QUESTION = "question"
JOB_KIND_LEARNING_MATERIAL = "learning-material"
JOB_KIND_SYSTEM_DESIGN_SCENARIO = "system-design-scenario"
JOB_KIND_REFERENCE_ANSWER = "reference-answer"
JOB_KIND_CURRICULUM = "curriculum"
JOB_KINDS = {
    JOB_KIND_QUESTION,
    JOB_KIND_LEARNING_MATERIAL,
    JOB_KIND_SYSTEM_DESIGN_SCENARIO,
    JOB_KIND_REFERENCE_ANSWER,
    JOB_KIND_CURRICULUM,
}
JOB_STATUSES = {"queued", "running", "done", "failed"}
ACTIVE_JOB_STATUSES = {"queued", "running"}
DEFAULT_MAX_ACTIVE_JOBS_PER_TOPIC_KIND = 1
DEFAULT_RETRY_MAX_ATTEMPTS = 3
DEFAULT_RETRY_BACKOFF_SECONDS = 60
QUESTION_SIMILARITY_SEQUENCE_THRESHOLD = 0.9
QUESTION_SIMILARITY_TOKEN_OVERLAP_THRESHOLD = 0.85
QUESTION_SIMILARITY_MIN_TOKEN_COUNT = 4
GENERATED_QUESTION_MAX_TAGS = 5
GENERATED_QUESTION_MAX_COMPETENCIES = 4
QUESTION_SIMILARITY_STOPWORDS = {
    "and",
    "are",
    "for",
    "how",
    "into",
    "the",
    "what",
    "when",
    "where",
    "which",
    "why",
    "без",
    "для",
    "или",
    "как",
    "над",
    "при",
    "про",
    "что",
    "это",
}


@dataclass(frozen=True)
class ProcessedJob:
    job: ContentGenerationJob
    created_question: Question | None
    artifact: dict[str, Any] | None = None


class ContentGenerationService:
    def __init__(
        self,
        repository: SQLiteRepository,
        llm: LLMClient,
        max_active_jobs_per_topic_kind: int = DEFAULT_MAX_ACTIVE_JOBS_PER_TOPIC_KIND,
    ):
        if max_active_jobs_per_topic_kind < 1:
            raise ValueError("max_active_jobs_per_topic_kind must be positive")
        self.repository = repository
        self.llm = llm
        self.max_active_jobs_per_topic_kind = max_active_jobs_per_topic_kind

    def enqueue_question(self, topic_id: int, note: str = "") -> ContentGenerationJob:
        return self.enqueue(JOB_KIND_QUESTION, topic_id, note)

    def enqueue_learning_material(self, topic_id: int, note: str = "") -> ContentGenerationJob:
        return self.enqueue(JOB_KIND_LEARNING_MATERIAL, topic_id, note)

    def enqueue_system_design_scenario(self, topic_id: int, note: str = "") -> ContentGenerationJob:
        return self.enqueue(JOB_KIND_SYSTEM_DESIGN_SCENARIO, topic_id, note)

    def enqueue_reference_answer_regeneration(self, topic_id: int, note: str = "") -> ContentGenerationJob:
        return self.enqueue(JOB_KIND_REFERENCE_ANSWER, topic_id, note)

    def enqueue_curriculum(
        self,
        note: str = "",
        topic_count: int = 3,
        questions_per_topic: int = 3,
    ) -> ContentGenerationJob:
        self._ensure_active_job_limit(JOB_KIND_CURRICULUM, 0)
        payload = build_curriculum_job_payload(note, topic_count, questions_per_topic)
        return self.repository.create_content_generation_job(
            JOB_KIND_CURRICULUM,
            json.dumps(payload, ensure_ascii=False),
        )

    def enqueue(self, kind: str, topic_id: int, note: str = "") -> ContentGenerationJob:
        if kind not in JOB_KINDS:
            raise ValueError(f"Unknown generation job kind: {kind}")
        if kind == JOB_KIND_CURRICULUM:
            return self.enqueue_curriculum(note)
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ValueError(f"Unknown topic id: {topic_id}")
        self._ensure_active_job_limit(kind, topic_id)
        payload = build_job_payload(topic_id, note)
        return self.repository.create_content_generation_job(
            kind,
            json.dumps(payload, ensure_ascii=False),
        )

    def ensure_question_backlog(
        self,
        topic_id: int,
        min_questions: int = 4,
        note: str = "",
    ) -> ContentGenerationJob | None:
        questions = self.repository.list_questions(topic_id)
        if len(questions) >= min_questions:
            return None
        if self.has_active_question_job(topic_id):
            return None
        return self.enqueue_question(topic_id, note)

    def ensure_learning_material(self, topic_id: int, note: str = "") -> ContentGenerationJob | None:
        if self.repository.latest_learning_material(topic_id) is not None:
            return None
        if self.has_job_for_topic(
            JOB_KIND_LEARNING_MATERIAL,
            topic_id,
            statuses={"queued", "running"},
        ):
            return None
        return self.enqueue_learning_material(topic_id, note)

    def ensure_system_design_scenario(self, topic_id: int, note: str = "") -> ContentGenerationJob | None:
        if self.repository.latest_system_design_scenario(topic_id) is not None:
            return None
        if self.has_job_for_topic(
            JOB_KIND_SYSTEM_DESIGN_SCENARIO,
            topic_id,
            statuses={"queued", "running"},
        ):
            return None
        return self.enqueue_system_design_scenario(topic_id, note)

    def has_active_question_job(self, topic_id: int) -> bool:
        return self.has_active_job(JOB_KIND_QUESTION, topic_id)

    def has_active_job(self, kind: str, topic_id: int) -> bool:
        return self.has_job_for_topic(kind, topic_id, statuses=ACTIVE_JOB_STATUSES)

    def has_job_for_topic(self, kind: str, topic_id: int, statuses: set[str]) -> bool:
        return bool(self.jobs_for_topic(kind, topic_id, statuses=statuses))

    def jobs_for_topic(
        self,
        kind: str,
        topic_id: int,
        statuses: set[str],
        ignored_job_id: int | None = None,
    ) -> list[ContentGenerationJob]:
        jobs = []
        for job in self.repository.list_content_generation_jobs(limit=1000):
            if ignored_job_id is not None and job.id == ignored_job_id:
                continue
            if job.kind != kind or job.status not in statuses:
                continue
            payload = parse_payload(job.payload_json)
            if int(payload.get("topic_id") or 0) == topic_id:
                jobs.append(job)
        return jobs

    def active_job_count_for_topic(self, kind: str, topic_id: int, ignored_job_id: int | None = None) -> int:
        return len(
            self.jobs_for_topic(
                kind,
                topic_id,
                statuses=ACTIVE_JOB_STATUSES,
                ignored_job_id=ignored_job_id,
            )
        )

    def _ensure_active_job_limit(self, kind: str, topic_id: int, ignored_job_id: int | None = None) -> None:
        active_count = self.active_job_count_for_topic(kind, topic_id, ignored_job_id=ignored_job_id)
        if active_count >= self.max_active_jobs_per_topic_kind:
            raise ValueError(
                "Active generation job limit reached "
                f"for topic {topic_id} and kind {kind}: "
                f"{active_count}/{self.max_active_jobs_per_topic_kind}"
            )

    def list_jobs(self, status: str | None = None, limit: int = 20) -> list[ContentGenerationJob]:
        if status is not None and status not in JOB_STATUSES:
            raise ValueError(f"Unknown job status: {status}")
        return self.repository.list_content_generation_jobs(status=status, limit=limit)

    def retry_job(self, job_id: int) -> None:
        job = self.repository.get_content_generation_job(job_id)
        if job is None:
            raise ValueError(f"Unknown job id: {job_id}")
        payload = parse_payload(job.payload_json)
        topic_id = int(payload.get("topic_id") or 0)
        if job.kind == JOB_KIND_CURRICULUM:
            self._ensure_active_job_limit(job.kind, 0, ignored_job_id=job_id)
        elif job.kind in JOB_KINDS and topic_id:
            self._ensure_active_job_limit(job.kind, topic_id, ignored_job_id=job_id)
        self._prepare_job_manual_retry(job)
        self.repository.retry_content_generation_job(job_id)

    def process_next_job(self) -> ProcessedJob | None:
        job = self._next_ready_queued_job()
        if job is None:
            return None
        return self.process_job(job)

    def _next_ready_queued_job(self) -> ContentGenerationJob | None:
        for job in self.repository.list_queued_content_generation_jobs(limit=100):
            if is_job_ready_for_attempt(job):
                return job
        return None

    def process_job(self, job: ContentGenerationJob) -> ProcessedJob:
        self.repository.update_content_generation_job(job.id or 0, "running")
        try:
            if job.kind == JOB_KIND_QUESTION:
                question = self._process_question_job(job)
                tag_slugs = (
                    [tag.slug for tag in self.repository.list_question_tags(question.id)]
                    if question.id is not None
                    else []
                )
                competency_slugs = (
                    [
                        link.competency.slug
                        for link in self.repository.list_question_competencies(question.id)
                    ]
                    if question.id is not None
                    else []
                )
                artifact = {
                    "kind": job.kind,
                    "question_id": question.id,
                    "prompt": question.prompt,
                    "source_quality_status": question.source_quality_status,
                    "tag_slugs": tag_slugs,
                    "competency_slugs": competency_slugs,
                }
            elif job.kind == JOB_KIND_LEARNING_MATERIAL:
                question = None
                artifact = self._process_learning_material_job(job)
            elif job.kind == JOB_KIND_SYSTEM_DESIGN_SCENARIO:
                question = None
                artifact = self._process_system_design_scenario_job(job)
            elif job.kind == JOB_KIND_REFERENCE_ANSWER:
                question = None
                artifact = self._process_reference_answer_job(job)
            elif job.kind == JOB_KIND_CURRICULUM:
                question = None
                artifact = self._process_curriculum_job(job)
            else:
                raise ValueError(f"Unsupported generation job kind: {job.kind}")
            self.repository.update_content_generation_job(
                job.id or 0,
                "done",
                result_json=json.dumps(artifact, ensure_ascii=False),
                error=None,
            )
            saved_job = self.repository.get_content_generation_job(job.id or 0) or job
            return ProcessedJob(saved_job, question, artifact)
        except Exception as exc:
            self._record_job_failure(job, str(exc))
            self.repository.update_content_generation_job(job.id or 0, "failed", error=str(exc))
            saved_job = self.repository.get_content_generation_job(job.id or 0) or job
            return ProcessedJob(saved_job, None, None)

    def _ensure_job_retry_metadata(self, job: ContentGenerationJob) -> None:
        payload = parse_payload(job.payload_json)
        normalized = normalize_retry_metadata(payload.get("retry"))
        if payload.get("retry") == normalized:
            return
        payload["retry"] = normalized
        self.repository.update_content_generation_job_payload(
            job.id or 0,
            json.dumps(payload, ensure_ascii=False),
        )

    def _prepare_job_manual_retry(self, job: ContentGenerationJob) -> None:
        payload = parse_payload(job.payload_json)
        retry = normalize_retry_metadata(payload.get("retry"))
        retry["next_attempt_at"] = None
        retry["last_error"] = None
        payload["retry"] = retry
        self.repository.update_content_generation_job_payload(
            job.id or 0,
            json.dumps(payload, ensure_ascii=False),
        )

    def _record_job_failure(self, job: ContentGenerationJob, error: str) -> None:
        payload = parse_payload(job.payload_json)
        retry = normalize_retry_metadata(payload.get("retry"))
        attempt = retry["attempt"] + 1
        delay_seconds = retry_backoff_seconds(attempt)
        retry.update(
            {
                "attempt": attempt,
                "backoff_seconds": delay_seconds,
                "next_attempt_at": (datetime.now() + timedelta(seconds=delay_seconds)).isoformat(
                    timespec="seconds"
                ),
                "last_error": error,
            }
        )
        payload["retry"] = retry
        self.repository.update_content_generation_job_payload(
            job.id or 0,
            json.dumps(payload, ensure_ascii=False),
        )

    def _process_question_job(self, job: ContentGenerationJob) -> Question:
        payload = parse_payload(job.payload_json)
        topic_id = int(payload.get("topic_id") or 0)
        note = str(payload.get("note") or "").strip()
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ValueError(f"Unknown topic id in job payload: {topic_id}")
        raw = self.llm.generate(
            build_background_question_prompt(
                topic.title,
                topic.description,
                note,
                [competency.slug for competency in self.repository.list_competencies()],
            )
        )
        raw_payload = parse_json_object(raw)
        parsed = QuestionService(self.repository, self.llm)._parse_question_json(raw, note or topic.title)
        candidate = Question(
            id=None,
            topic_id=topic_id,
            difficulty=normalize_difficulty(parsed["difficulty"]),
            prompt=parsed["prompt"].strip(),
            hint=parsed["hint"].strip(),
            reference_answer=parsed["reference_answer"].strip(),
            source="background-llm",
            source_quality_status=QUESTION_SOURCE_QUALITY_PENDING_REVIEW,
        )
        similar_question = self._find_similar_topic_question(topic_id, candidate.prompt)
        if similar_question is not None:
            return similar_question
        saved = self.repository.add_question(candidate)
        self._link_generated_question_metadata(saved, raw_payload)
        return saved

    def _link_generated_question_metadata(self, question: Question, raw_payload: dict[str, Any]) -> None:
        if question.id is None:
            return
        tag_slugs = normalize_generated_slugs(
            raw_payload.get("tag_slugs"),
            limit=GENERATED_QUESTION_MAX_TAGS,
        )
        if tag_slugs:
            tags = []
            for slug in tag_slugs:
                tag = self.repository.find_tag_by_slug(slug)
                if tag is None:
                    tag = self.repository.upsert_tag(
                        Tag(
                            id=None,
                            slug=slug,
                            title=generated_tag_title(slug),
                            source="background-llm",
                        )
                    )
                tags.append(tag)
            self.repository.set_question_tags(question.id, [tag.id or 0 for tag in tags])

        competency_slugs = normalize_generated_slugs(
            raw_payload.get("competency_slugs"),
            limit=GENERATED_QUESTION_MAX_COMPETENCIES,
        )
        links: list[QuestionCompetencyLink] = []
        for slug in competency_slugs:
            competency = self.repository.find_competency_by_slug(slug)
            if competency is None:
                continue
            links.append(
                QuestionCompetencyLink(
                    competency=competency,
                    is_primary=not links,
                    weight=1.0,
                )
            )
        if links:
            self.repository.set_question_competencies(question.id, links)

    def _find_similar_topic_question(self, topic_id: int, prompt: str) -> Question | None:
        for question in self.repository.list_questions(topic_id):
            if question_prompts_are_similar(prompt, question.prompt):
                return question
        return None

    def _process_learning_material_job(self, job: ContentGenerationJob) -> dict[str, Any]:
        payload = parse_payload(job.payload_json)
        topic_id = int(payload.get("topic_id") or 0)
        note = str(payload.get("note") or "").strip()
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ValueError(f"Unknown topic id in job payload: {topic_id}")
        material = self.llm.generate(build_learning_material_prompt(topic.title, topic.description, note)).strip()
        saved = self.repository.add_learning_material(
            LearningMaterial(
                id=None,
                topic_id=topic_id,
                title=f"Учебный разбор: {topic.title}",
                body=material,
                source="background-llm",
                created_at=datetime.now(),
            )
        )
        return {
            "kind": JOB_KIND_LEARNING_MATERIAL,
            "topic_id": topic_id,
            "material_id": saved.id,
            "title": saved.title,
            "material": saved.body,
        }

    def _process_system_design_scenario_job(self, job: ContentGenerationJob) -> dict[str, Any]:
        payload = parse_payload(job.payload_json)
        topic_id = int(payload.get("topic_id") or 0)
        note = str(payload.get("note") or "").strip()
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ValueError(f"Unknown topic id in job payload: {topic_id}")
        raw = self.llm.generate(build_system_design_scenario_prompt(topic.title, topic.description, note))
        parsed = parse_json_object(raw)
        scenario = str(
            parsed.get("scenario")
            or "Спроектируй backend-сервис end-to-end: requirements, API, data model, storage, scaling, observability и failure modes."
        ).strip()
        focus_areas = parsed.get("focus_areas")
        if not isinstance(focus_areas, list):
            focus_areas = [
                "requirements",
                "API",
                "data model",
                "scaling",
                "observability",
                "failure modes",
            ]
        focus_area_strings = [str(item).strip() for item in focus_areas if str(item).strip()]
        saved = self.repository.add_system_design_scenario(
            SystemDesignScenario(
                id=None,
                topic_id=topic_id,
                title=f"System design scenario: {topic.title}",
                scenario=scenario,
                focus_areas=focus_area_strings,
                source="background-llm",
                created_at=datetime.now(),
            )
        )
        return {
            "kind": JOB_KIND_SYSTEM_DESIGN_SCENARIO,
            "topic_id": topic_id,
            "scenario_id": saved.id,
            "title": saved.title,
            "scenario": saved.scenario,
            "focus_areas": saved.focus_areas,
        }

    def _process_reference_answer_job(self, job: ContentGenerationJob) -> dict[str, Any]:
        payload = parse_payload(job.payload_json)
        topic_id = int(payload.get("topic_id") or 0)
        note = str(payload.get("note") or "").strip()
        topic = self.repository.get_topic(topic_id)
        if topic is None:
            raise ValueError(f"Unknown topic id in job payload: {topic_id}")
        questions = self.repository.list_questions(topic_id)
        if not questions:
            raise ValueError(f"No questions found for topic id in job payload: {topic_id}")

        updates = []
        for question in questions:
            regenerated = self.llm.generate(
                build_reference_answer_prompt(topic.title, topic.description, question, note)
            ).strip()
            if not regenerated:
                raise ValueError(f"Empty reference answer generated for question {question.id}")
            updates.append((question.id or 0, regenerated))

        updated_questions = self.repository.update_question_reference_answers(updates)
        return {
            "kind": JOB_KIND_REFERENCE_ANSWER,
            "topic_id": topic_id,
            "updated_count": len(updated_questions),
            "question_ids": [question.id for question in updated_questions],
        }

    def _process_curriculum_job(self, job: ContentGenerationJob) -> dict[str, Any]:
        payload = parse_payload(job.payload_json)
        note = str(payload.get("note") or "").strip()
        topic_count = normalize_job_count(payload.get("topic_count"), default=3, minimum=1, maximum=12)
        questions_per_topic = normalize_job_count(
            payload.get("questions_per_topic"),
            default=3,
            minimum=1,
            maximum=10,
        )
        result = CurriculumService(self.repository, self.llm).generate_and_save(
            topic_count=topic_count,
            questions_per_topic=questions_per_topic,
            dry_run=False,
        )
        return {
            "kind": JOB_KIND_CURRICULUM,
            "topic_id": 0,
            "topic_count": len(result.curriculum.topics),
            "topics_saved": result.topics_saved,
            "curriculum_topics_saved": result.curriculum_topics_saved,
            "subtopics_saved": result.subtopics_saved,
            "objectives_saved": result.objectives_saved,
            "questions_saved": result.questions_saved,
            "note": note,
            "topic_slugs": [topic.slug for topic in result.curriculum.topics],
        }


def parse_payload(payload_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def build_job_payload(topic_id: int, note: str) -> dict[str, Any]:
    return {
        "topic_id": topic_id,
        "note": note.strip(),
        "retry": normalize_retry_metadata(None),
    }


def build_curriculum_job_payload(note: str, topic_count: int, questions_per_topic: int) -> dict[str, Any]:
    return {
        "topic_id": 0,
        "note": note.strip(),
        "topic_count": normalize_job_count(topic_count, default=3, minimum=1, maximum=12),
        "questions_per_topic": normalize_job_count(questions_per_topic, default=3, minimum=1, maximum=10),
        "retry": normalize_retry_metadata(None),
    }


def normalize_job_count(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        count = int(value)
    except (TypeError, ValueError):
        count = default
    return max(minimum, min(count, maximum))


def normalize_retry_metadata(value: Any) -> dict[str, Any]:
    retry = value if isinstance(value, dict) else {}
    try:
        attempt = int(retry.get("attempt", 0))
    except (TypeError, ValueError):
        attempt = 0
    try:
        max_attempts = int(retry.get("max_attempts", DEFAULT_RETRY_MAX_ATTEMPTS))
    except (TypeError, ValueError):
        max_attempts = DEFAULT_RETRY_MAX_ATTEMPTS
    try:
        backoff_seconds = int(retry.get("backoff_seconds", DEFAULT_RETRY_BACKOFF_SECONDS))
    except (TypeError, ValueError):
        backoff_seconds = DEFAULT_RETRY_BACKOFF_SECONDS
    return {
        "attempt": max(0, attempt),
        "max_attempts": max(1, max_attempts),
        "backoff_seconds": max(1, backoff_seconds),
        "next_attempt_at": retry.get("next_attempt_at") or None,
        "last_error": retry.get("last_error") or None,
    }


def retry_backoff_seconds(attempt: int) -> int:
    normalized_attempt = max(1, attempt)
    return DEFAULT_RETRY_BACKOFF_SECONDS * (2 ** (normalized_attempt - 1))


def is_job_ready_for_attempt(job: ContentGenerationJob, now: datetime | None = None) -> bool:
    payload = parse_payload(job.payload_json)
    retry = normalize_retry_metadata(payload.get("retry"))
    next_attempt_at = retry.get("next_attempt_at")
    if not next_attempt_at:
        return True
    try:
        ready_at = datetime.fromisoformat(str(next_attempt_at))
    except ValueError:
        return True
    current_time = now or datetime.now(tz=ready_at.tzinfo)
    if ready_at.tzinfo is not None and current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=ready_at.tzinfo)
    elif ready_at.tzinfo is None and current_time.tzinfo is not None:
        current_time = current_time.replace(tzinfo=None)
    return ready_at <= current_time


def parse_json_object(raw: str) -> dict[str, Any]:
    try:
        start = raw.find("{")
        end = raw.rfind("}")
        payload = json.loads(raw[start : end + 1] if start >= 0 and end >= start else raw)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def question_prompts_are_similar(left: str, right: str) -> bool:
    left_tokens = normalized_question_tokens(left)
    right_tokens = normalized_question_tokens(right)
    if not left_tokens or not right_tokens:
        return False

    left_normalized = " ".join(left_tokens)
    right_normalized = " ".join(right_tokens)
    if left_normalized == right_normalized:
        return True
    if SequenceMatcher(None, left_normalized, right_normalized).ratio() >= QUESTION_SIMILARITY_SEQUENCE_THRESHOLD:
        return True

    left_set = set(left_tokens)
    right_set = set(right_tokens)
    comparable_token_count = min(len(left_set), len(right_set))
    if comparable_token_count < QUESTION_SIMILARITY_MIN_TOKEN_COUNT:
        return False
    overlap_ratio = len(left_set & right_set) / comparable_token_count
    return overlap_ratio >= QUESTION_SIMILARITY_TOKEN_OVERLAP_THRESHOLD


def normalized_question_tokens(text: str) -> list[str]:
    normalized = text.lower().replace("ё", "е")
    tokens = re.findall(r"[0-9a-zа-я]+", normalized)
    return [
        token
        for token in tokens
        if len(token) > 2 and token not in QUESTION_SIMILARITY_STOPWORDS
    ]


def normalize_generated_slugs(value: Any, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    slugs: list[str] = []
    seen: set[str] = set()
    for item in value:
        slug = str(item).strip().lower().replace("_", "-")
        slug = re.sub(r"[^a-z0-9-]+", "-", slug)
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        if not slug or slug in seen:
            continue
        seen.add(slug)
        slugs.append(slug)
        if len(slugs) >= limit:
            break
    return slugs


def generated_tag_title(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-") if part) or slug


def build_background_question_prompt(
    topic_title: str,
    topic_description: str,
    note: str,
    competency_slugs: list[str] | None = None,
) -> str:
    known_competencies = ", ".join(competency_slugs or [])
    competency_instruction = (
        f"competency_slugs must use only these known slugs: {known_competencies}."
        if known_competencies
        else "competency_slugs must be an empty JSON array if no known competency fits."
    )
    return f"""
Create one structured interview question for a middle+/senior Python backend developer.
Return JSON only with keys: difficulty, prompt, hint, reference_answer, tag_slugs, competency_slugs.
All values except difficulty must be written in Russian.
Difficulty must be one of: middle, middle+, senior.
tag_slugs must be a JSON array of 2-5 short lowercase kebab-case English tags.
{competency_instruction}
Choose 1-4 competency_slugs, ordered from primary to secondary.

This request comes from a background content generation job. Make the question practical and non-trivial.

Topic: {topic_title}
Topic description: {topic_description}
Generation note:
{note or "Сгенерируй вопрос, который закрывает слабое место senior backend подготовки."}
""".strip()


def build_learning_material_prompt(topic_title: str, topic_description: str, note: str) -> str:
    return f"""
Create a compact Russian learning material for a middle+/senior Python backend developer.
This is not an interview evaluation. The goal is to reduce cognitive load before practice.

Structure the answer with these sections:
1. Короткое объяснение темы.
2. Что senior должен понимать глубже middle.
3. Production tradeoffs.
4. Типичные ошибки и failure modes.
5. Мини-план практики на 15 минут.

Topic: {topic_title}
Topic description: {topic_description}
Generation note:
{note or "Подготовь материал, который поможет быстро войти в тему перед вопросами."}
""".strip()


def build_system_design_scenario_prompt(topic_title: str, topic_description: str, note: str) -> str:
    return f"""
Create one system design mock interview scenario for a senior Python backend developer.
Return JSON only with keys: scenario, focus_areas.
scenario must be written in Russian and describe a service to design end-to-end.
focus_areas must be a JSON array of short strings.

The scenario must force discussion of requirements, API, data model, storage, scale,
consistency, async/background work, observability, failure modes and tradeoffs.

Topic: {topic_title}
Topic description: {topic_description}
Generation note:
{note or "Сгенерируй реалистичный backend/system design mock interview scenario."}
""".strip()


def build_reference_answer_prompt(topic_title: str, topic_description: str, question: Question, note: str) -> str:
    return f"""
Regenerate the reference answer for one interview question.
Write only the new reference answer in Russian. Do not return JSON or Markdown fences.
Keep the existing question, hint and difficulty unchanged.

The answer must be useful for a middle+/senior Python backend developer:
- mention mechanisms, tradeoffs and production examples;
- include failure modes or edge cases where relevant;
- stay compact enough to read during terminal practice.

Topic: {topic_title}
Topic description: {topic_description}
Difficulty: {question.difficulty}
Question:
{question.prompt}
Hint:
{question.hint}
Current reference answer:
{question.reference_answer}
Generation note:
{note or "Обнови эталонный ответ так, чтобы он был точнее и полезнее для senior-level самопроверки."}
""".strip()
