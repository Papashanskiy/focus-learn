from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Iterable

from interview_prep.domain.models import ContentGenerationJob
from interview_prep.services.content_demand_service import (
    CONTENT_DEMAND_ACCEPTED_QUESTIONS,
    CONTENT_DEMAND_CANDIDATE_QUESTIONS,
    CONTENT_DEMAND_LEARNING_MATERIALS,
    CONTENT_DEMAND_SYSTEM_DESIGN_SCENARIOS,
    ContentDemandService,
    ContentDemandSnapshot,
    ContentDemandTarget,
)
from interview_prep.services.content_generation_service import (
    JOB_KIND_LEARNING_MATERIAL,
    JOB_KIND_QUESTION,
    JOB_KIND_SOURCE_REFRESH,
    JOB_KIND_SYSTEM_DESIGN_SCENARIO,
    ContentGenerationService,
    is_job_ready_for_attempt,
)
from interview_prep.services.question_source_service import (
    QuestionSourceService,
    QuestionSourceStalenessReport,
    WHITELISTED_QUESTION_SOURCES,
)

SCHEDULER_ACTION_ENQUEUED = "enqueued"
SCHEDULER_ACTION_SKIPPED = "skipped"


@dataclass(frozen=True)
class ContentSchedulerPolicy:
    max_jobs_per_run: int = 3
    completed_job_cooldown_seconds: int = 6 * 60 * 60
    failed_job_cooldown_seconds: int = 60 * 60
    local_llm_work_enabled: bool = True
    local_llm_available: Callable[[], bool] | None = None
    source_refresh_enabled: bool = False
    source_refresh_staleness_days: int = 30


@dataclass(frozen=True)
class ContentSchedulerDecision:
    target: ContentDemandTarget
    action: str
    reason: str
    job_kind: str | None = None
    job: ContentGenerationJob | None = None

    @property
    def enqueued(self) -> bool:
        return self.action == SCHEDULER_ACTION_ENQUEUED and self.job is not None


@dataclass(frozen=True)
class ContentSchedulerRun:
    snapshot: ContentDemandSnapshot
    decisions: tuple[ContentSchedulerDecision, ...]

    @property
    def enqueued_jobs(self) -> tuple[ContentGenerationJob, ...]:
        return tuple(decision.job for decision in self.decisions if decision.enqueued and decision.job)


class ContentSchedulerService:
    def __init__(
        self,
        demand: ContentDemandService,
        content_generation: ContentGenerationService,
        policy: ContentSchedulerPolicy | None = None,
    ):
        self.demand = demand
        self.content_generation = content_generation
        self.policy = policy or ContentSchedulerPolicy()
        if self.policy.max_jobs_per_run < 1:
            raise ValueError("max_jobs_per_run must be positive")
        if self.policy.completed_job_cooldown_seconds < 0:
            raise ValueError("completed_job_cooldown_seconds must be non-negative")
        if self.policy.failed_job_cooldown_seconds < 0:
            raise ValueError("failed_job_cooldown_seconds must be non-negative")
        if self.policy.local_llm_available is not None and not callable(self.policy.local_llm_available):
            raise ValueError("local_llm_available must be callable")
        if self.policy.source_refresh_staleness_days < 1:
            raise ValueError("source_refresh_staleness_days must be positive")

    def run_once(
        self,
        *,
        upcoming_modes: Iterable[str] | None = None,
        now: datetime | None = None,
    ) -> ContentSchedulerRun:
        reference_now = now or datetime.now()
        snapshot = self.demand.snapshot(upcoming_modes=upcoming_modes, now=reference_now)
        decisions: list[ContentSchedulerDecision] = []
        planned_topic_jobs: set[tuple[str, int]] = set()
        model_guard_reason = self._model_guard_skip_reason()
        source_refresh_decision = self._source_refresh_decision(reference_now, planned_topic_jobs)
        if source_refresh_decision is not None:
            decisions.append(source_refresh_decision)

        for target in prioritized_scheduler_targets(snapshot.deficits):
            job_kind = scheduler_job_kind_for_target(target)
            if job_kind is None:
                decisions.append(
                    ContentSchedulerDecision(
                        target=target,
                        action=SCHEDULER_ACTION_SKIPPED,
                        reason=scheduler_skip_reason_for_target(target),
                    )
                )
                continue
            if target.topic_id is None:
                decisions.append(
                    ContentSchedulerDecision(
                        target=target,
                        action=SCHEDULER_ACTION_SKIPPED,
                        reason="target has no topic mapping yet",
                        job_kind=job_kind,
                    )
                )
                continue
            if model_guard_reason and job_kind in LOCAL_LLM_JOB_KINDS:
                decisions.append(
                    ContentSchedulerDecision(
                        target=target,
                        action=SCHEDULER_ACTION_SKIPPED,
                        reason=model_guard_reason,
                        job_kind=job_kind,
                    )
                )
                continue
            topic_key = (job_kind, target.topic_id)
            if topic_key in planned_topic_jobs:
                decisions.append(
                    ContentSchedulerDecision(
                        target=target,
                        action=SCHEDULER_ACTION_SKIPPED,
                        reason="job already planned for this topic in this pass",
                        job_kind=job_kind,
                    )
                )
                continue
            attempt_guard_reason = self._attempt_guard_skip_reason(
                job_kind,
                target.topic_id,
                reference_now,
            )
            if attempt_guard_reason:
                decisions.append(
                    ContentSchedulerDecision(
                        target=target,
                        action=SCHEDULER_ACTION_SKIPPED,
                        reason=attempt_guard_reason,
                        job_kind=job_kind,
                    )
                )
                continue
            if len(planned_topic_jobs) >= self.policy.max_jobs_per_run:
                decisions.append(
                    ContentSchedulerDecision(
                        target=target,
                        action=SCHEDULER_ACTION_SKIPPED,
                        reason="scheduler budget exhausted",
                        job_kind=job_kind,
                    )
                )
                continue

            job = self._enqueue_target_job(target, job_kind)
            planned_topic_jobs.add(topic_key)
            decisions.append(
                ContentSchedulerDecision(
                    target=target,
                    action=SCHEDULER_ACTION_ENQUEUED,
                    reason="deficit queued",
                    job_kind=job_kind,
                    job=job,
                )
            )

        return ContentSchedulerRun(snapshot=snapshot, decisions=tuple(decisions))

    def _enqueue_target_job(self, target: ContentDemandTarget, job_kind: str) -> ContentGenerationJob:
        topic_id = target.topic_id or 0
        note = scheduler_job_note(target)
        if job_kind == JOB_KIND_QUESTION:
            return self.content_generation.enqueue_question(topic_id, note)
        if job_kind == JOB_KIND_LEARNING_MATERIAL:
            return self.content_generation.enqueue_learning_material(topic_id, note)
        if job_kind == JOB_KIND_SYSTEM_DESIGN_SCENARIO:
            return self.content_generation.enqueue_system_design_scenario(topic_id, note)
        if job_kind == JOB_KIND_SOURCE_REFRESH:
            return self.content_generation.enqueue_source_refresh(note)
        raise ValueError(f"Unsupported scheduler job kind: {job_kind}")

    def _source_refresh_decision(
        self,
        now: datetime,
        planned_topic_jobs: set[tuple[str, int]],
    ) -> ContentSchedulerDecision | None:
        if not self.policy.source_refresh_enabled:
            return None
        report = QuestionSourceService(self.content_generation.repository).staleness_report(
            max_age_days=self.policy.source_refresh_staleness_days,
            now=now,
        )
        if not report.needs_refresh:
            return None
        target = source_refresh_target(report)
        topic_key = (JOB_KIND_SOURCE_REFRESH, 0)
        attempt_guard_reason = self._attempt_guard_skip_reason(JOB_KIND_SOURCE_REFRESH, 0, now)
        if attempt_guard_reason:
            return ContentSchedulerDecision(
                target=target,
                action=SCHEDULER_ACTION_SKIPPED,
                reason=attempt_guard_reason,
                job_kind=JOB_KIND_SOURCE_REFRESH,
            )
        if len(planned_topic_jobs) >= self.policy.max_jobs_per_run:
            return ContentSchedulerDecision(
                target=target,
                action=SCHEDULER_ACTION_SKIPPED,
                reason="scheduler budget exhausted",
                job_kind=JOB_KIND_SOURCE_REFRESH,
            )
        job = self._enqueue_target_job(target, JOB_KIND_SOURCE_REFRESH)
        planned_topic_jobs.add(topic_key)
        return ContentSchedulerDecision(
            target=target,
            action=SCHEDULER_ACTION_ENQUEUED,
            reason=target.reason,
            job_kind=JOB_KIND_SOURCE_REFRESH,
            job=job,
        )

    def _attempt_guard_skip_reason(self, job_kind: str, topic_id: int, now: datetime) -> str | None:
        jobs = self.content_generation.jobs_for_topic(
            job_kind,
            topic_id,
            statuses={"queued", "running", "done", "failed"},
        )
        for job in jobs:
            if job.status in {"queued", "running"}:
                if job.status == "queued" and _retry_backoff_pending(job, now):
                    return "retry backoff already scheduled"
                return "active job already exists"
        for job in jobs:
            if job.status == "done" and _within_cooldown(
                job.updated_at,
                now,
                self.policy.completed_job_cooldown_seconds,
            ):
                return "recent completed job cooldown"
            if job.status == "failed" and _within_cooldown(
                job.updated_at,
                now,
                self.policy.failed_job_cooldown_seconds,
            ):
                return "recent failed job cooldown"
        return None

    def _model_guard_skip_reason(self) -> str | None:
        if not self.policy.local_llm_work_enabled:
            return "local LLM generation disabled by policy"
        if self.policy.local_llm_available is None:
            return None
        try:
            available = self.policy.local_llm_available()
        except Exception as exc:
            return f"local LLM availability check failed: {exc}"
        if not available:
            return "local LLM runtime unavailable"
        return None


def scheduler_job_kind_for_target(target: ContentDemandTarget) -> str | None:
    if target.kind == CONTENT_DEMAND_CANDIDATE_QUESTIONS:
        return JOB_KIND_QUESTION
    if target.kind == CONTENT_DEMAND_LEARNING_MATERIALS:
        return JOB_KIND_LEARNING_MATERIAL
    if target.kind == CONTENT_DEMAND_SYSTEM_DESIGN_SCENARIOS:
        return JOB_KIND_SYSTEM_DESIGN_SCENARIO
    if target.kind == JOB_KIND_SOURCE_REFRESH:
        return JOB_KIND_SOURCE_REFRESH
    return None


def prioritized_scheduler_targets(
    targets: Iterable[ContentDemandTarget],
) -> tuple[ContentDemandTarget, ...]:
    return tuple(sorted(targets, key=scheduler_target_priority_key))


def scheduler_target_priority_key(target: ContentDemandTarget) -> tuple[int, int, int, str]:
    job_kind = scheduler_job_kind_for_target(target)
    if target.kind == CONTENT_DEMAND_ACCEPTED_QUESTIONS:
        tier = 0
    elif job_kind == JOB_KIND_QUESTION:
        tier = 1
    elif job_kind == JOB_KIND_SOURCE_REFRESH:
        tier = 2
    elif job_kind == JOB_KIND_LEARNING_MATERIAL:
        tier = 3
    elif job_kind == JOB_KIND_SYSTEM_DESIGN_SCENARIO:
        tier = 4
    else:
        tier = 9
    return (tier, target.priority, target.topic_id or 0, target.kind)


def scheduler_skip_reason_for_target(target: ContentDemandTarget) -> str:
    if target.kind == CONTENT_DEMAND_ACCEPTED_QUESTIONS:
        return "accepted question deficit waits for curation"
    return "target kind is not enqueueable in planner foundation"


def scheduler_job_note(target: ContentDemandTarget) -> str:
    parts = [
        "auto-scheduler",
        f"target={target.kind}",
        f"deficit={target.deficit}",
        f"reason={target.reason}",
    ]
    if target.upcoming_mode:
        parts.append(f"mode={target.upcoming_mode}")
    return "; ".join(parts)


def source_refresh_target(report: QuestionSourceStalenessReport) -> ContentDemandTarget:
    return ContentDemandTarget(
        kind=JOB_KIND_SOURCE_REFRESH,
        target_count=len(WHITELISTED_QUESTION_SOURCES),
        current_count=report.fresh_count,
        reason=report.reason,
        priority=5,
        topic_id=0,
        topic_slug="source-refresh",
        topic_title="Question sources",
        upcoming_mode="source-refresh",
    )


def _within_cooldown(updated_at: datetime, now: datetime, cooldown_seconds: int) -> bool:
    if cooldown_seconds <= 0:
        return False
    return updated_at + timedelta(seconds=cooldown_seconds) > now


def _retry_backoff_pending(job: ContentGenerationJob, now: datetime) -> bool:
    return not is_job_ready_for_attempt(job, now=now)


LOCAL_LLM_JOB_KINDS = {
    JOB_KIND_QUESTION,
    JOB_KIND_LEARNING_MATERIAL,
    JOB_KIND_SYSTEM_DESIGN_SCENARIO,
}
