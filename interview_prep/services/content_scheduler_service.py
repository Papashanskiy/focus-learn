from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

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
    JOB_KIND_SYSTEM_DESIGN_SCENARIO,
    ContentGenerationService,
)

SCHEDULER_ACTION_ENQUEUED = "enqueued"
SCHEDULER_ACTION_SKIPPED = "skipped"


@dataclass(frozen=True)
class ContentSchedulerPolicy:
    max_jobs_per_run: int = 3


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

    def run_once(
        self,
        *,
        upcoming_modes: Iterable[str] | None = None,
        now: datetime | None = None,
    ) -> ContentSchedulerRun:
        snapshot = self.demand.snapshot(upcoming_modes=upcoming_modes, now=now)
        decisions: list[ContentSchedulerDecision] = []
        planned_topic_jobs: set[tuple[str, int]] = set()

        for target in snapshot.deficits:
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
            if self.content_generation.has_active_job(job_kind, target.topic_id):
                decisions.append(
                    ContentSchedulerDecision(
                        target=target,
                        action=SCHEDULER_ACTION_SKIPPED,
                        reason="active job already exists",
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
        raise ValueError(f"Unsupported scheduler job kind: {job_kind}")


def scheduler_job_kind_for_target(target: ContentDemandTarget) -> str | None:
    if target.kind == CONTENT_DEMAND_CANDIDATE_QUESTIONS:
        return JOB_KIND_QUESTION
    if target.kind == CONTENT_DEMAND_LEARNING_MATERIALS:
        return JOB_KIND_LEARNING_MATERIAL
    if target.kind == CONTENT_DEMAND_SYSTEM_DESIGN_SCENARIOS:
        return JOB_KIND_SYSTEM_DESIGN_SCENARIO
    return None


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
