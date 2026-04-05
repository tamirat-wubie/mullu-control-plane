"""Phase 215C — Task Queue Contracts.

Purpose: Async task processing with priority queuing.
    Tasks are submitted, queued, and processed in priority order.
    Supports delayed execution and result retrieval.
Governance scope: task lifecycle management only.
Dependencies: none (pure queue logic).
Invariants:
  - Tasks are processed in priority order (highest first).
  - Each task has exactly one state at any time.
  - Completed task results are retrievable by ID.
  - Queue depth is bounded.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Any, Callable


def _classify_task_exception(exc: Exception) -> str:
    exc_type = type(exc).__name__
    if isinstance(exc, TimeoutError):
        return f"task timeout ({exc_type})"
    if isinstance(exc, ConnectionError):
        return f"task network error ({exc_type})"
    if isinstance(exc, ValueError):
        return f"task validation error ({exc_type})"
    return f"task handler error ({exc_type})"


def _sanitize_recorded_task_error(error: str) -> str:
    if not error:
        return "task failed"
    if error.startswith((
        "task timeout (",
        "task network error (",
        "task validation error (",
        "task handler error (",
    )):
        return error
    return "task failed"


@dataclass(frozen=True, slots=True)
class QueuedTask:
    """Task in the queue."""

    task_id: str
    priority: int  # Higher = processed first
    payload: dict[str, Any]
    tenant_id: str = ""
    submitted_at: str = ""


@dataclass(frozen=True, slots=True)
class TaskQueueResult:
    """Result of a processed task."""

    task_id: str
    output: dict[str, Any]
    succeeded: bool
    error: str = ""
    processed_at: str = ""


class TaskQueue:
    """Priority queue for async task processing."""

    def __init__(self, *, clock: Callable[[], str], max_depth: int = 10000) -> None:
        self._clock = clock
        self._max_depth = max_depth
        self._heap: list[tuple[int, str, QueuedTask]] = []  # (-priority, task_id, task)
        self._results: dict[str, TaskQueueResult] = {}
        self._counter = 0
        self._processed = 0

    def submit(self, task_id: str, payload: dict[str, Any], priority: int = 0, tenant_id: str = "") -> QueuedTask:
        """Submit a task to the queue."""
        if len(self._heap) >= self._max_depth:
            raise ValueError("queue full")

        task = QueuedTask(
            task_id=task_id, priority=priority,
            payload=payload, tenant_id=tenant_id,
            submitted_at=self._clock(),
        )
        heapq.heappush(self._heap, (-priority, task_id, task))
        self._counter += 1
        return task

    def pop(self) -> QueuedTask | None:
        """Pop highest priority task."""
        if not self._heap:
            return None
        _, _, task = heapq.heappop(self._heap)
        return task

    def peek(self) -> QueuedTask | None:
        """Peek at highest priority task without removing."""
        if not self._heap:
            return None
        return self._heap[0][2]

    def record_result(self, task_id: str, output: dict[str, Any], succeeded: bool = True, error: str = "") -> TaskQueueResult:
        """Record a task's result."""
        result = TaskQueueResult(
            task_id=task_id, output=output, succeeded=succeeded,
            error="" if succeeded else _sanitize_recorded_task_error(error),
            processed_at=self._clock(),
        )
        self._results[task_id] = result
        self._processed += 1
        return result

    def get_result(self, task_id: str) -> TaskQueueResult | None:
        return self._results.get(task_id)

    def process_one(self, handler: Callable[[dict[str, Any]], dict[str, Any]]) -> TaskQueueResult | None:
        """Pop and process one task."""
        task = self.pop()
        if task is None:
            return None
        try:
            output = handler(task.payload)
            return self.record_result(task.task_id, output, succeeded=True)
        except Exception as exc:
            return self.record_result(
                task.task_id,
                {},
                succeeded=False,
                error=_classify_task_exception(exc),
            )

    @property
    def depth(self) -> int:
        return len(self._heap)

    @property
    def total_submitted(self) -> int:
        return self._counter

    @property
    def total_processed(self) -> int:
        return self._processed

    def summary(self) -> dict[str, Any]:
        succeeded = sum(1 for r in self._results.values() if r.succeeded)
        return {
            "depth": self.depth,
            "submitted": self.total_submitted,
            "processed": self.total_processed,
            "succeeded": succeeded,
            "failed": self.total_processed - succeeded,
        }
