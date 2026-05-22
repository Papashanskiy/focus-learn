from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PAUSED_MESSAGE = "TUI content worker на паузе; queued jobs сохранены."


@dataclass(frozen=True)
class ContentWorkerAction:
    status: str
    history_message: str | None = None
    should_render: bool = True
    should_start_thread: bool = False


@dataclass(frozen=True)
class ContentWorkerRun:
    results: tuple[Any, ...]
    last_error: str | None = None


@dataclass(frozen=True)
class ContentWorkerFinish:
    results: tuple[Any, ...]
    status: str
    history_message: str | None = None


class ContentWorkerOrchestrator:
    """Small state holder for TUI-local background worker controls."""

    def __init__(self) -> None:
        self.status = "idle"
        self.running = False
        self.paused = False

    def pause(self) -> ContentWorkerAction:
        if self.paused:
            return ContentWorkerAction(
                status=self.status,
                history_message="TUI content worker уже на паузе; queued jobs сохранены.",
            )
        self.paused = True
        self.status = "paused"
        if self.running:
            message = "TUI content worker поставлен на паузу после текущей running-задачи."
        else:
            message = "TUI content worker поставлен на паузу; queued jobs сохранены."
        return ContentWorkerAction(status=self.status, history_message=message)

    def resume(self) -> ContentWorkerAction:
        if not self.paused:
            return ContentWorkerAction(
                status=self.status,
                history_message="TUI content worker уже активен.",
                should_start_thread=False,
            )
        self.paused = False
        self.status = "idle"
        return ContentWorkerAction(
            status=self.status,
            history_message="TUI content worker возобновлен.",
            should_start_thread=True,
        )

    def request_start(self, *, paused_message_already_visible: bool = False) -> ContentWorkerAction:
        if self.paused:
            self.status = "paused"
            return ContentWorkerAction(
                status=self.status,
                history_message=None if paused_message_already_visible else PAUSED_MESSAGE,
                should_start_thread=False,
            )
        if self.running:
            return ContentWorkerAction(
                status=self.status,
                should_render=False,
                should_start_thread=False,
            )
        self.running = True
        self.status = "generating..."
        return ContentWorkerAction(
            status=self.status,
            should_render=True,
            should_start_thread=True,
        )

    def process_available_jobs(self, content_generation: Any, llm: Any, *, limit: int = 3) -> ContentWorkerRun:
        results: list[Any] = []
        last_error = None
        try:
            for _ in range(limit):
                result = content_generation.process_next_job()
                if result is None:
                    break
                results.append(result)
                last_error = getattr(llm, "last_error", None)
        except Exception as exc:
                last_error = str(exc)
        return ContentWorkerRun(results=tuple(results), last_error=last_error)

    def finish_run(self, result: Any) -> ContentWorkerFinish:
        self.running = False
        if isinstance(result, (list, tuple)):
            results = tuple(result)
        elif result is None:
            results = ()
        else:
            results = (result,)

        if not results:
            status = "idle"
            history_message = "Автогенерация контента: задач в очереди нет."
        elif any(item.job.status == "failed" for item in results):
            status = "failed"
            history_message = None
        else:
            status = f"done {len(results)} job(s)"
            history_message = None

        if self.paused:
            status = "paused"
        self.status = status
        return ContentWorkerFinish(
            results=results,
            status=status,
            history_message=history_message,
        )

    def mark_unmounted(self) -> None:
        if self.running:
            self.status = "idle"
        self.running = False
