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

import hashlib
import json
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


@dataclass(frozen=True, slots=True)
class TaskQueueMutationReceipt:
    """Observed task-queue mutation receipt."""

    receipt_id: str
    mutation_type: str
    effect_name: str
    task_id: str
    tenant_id: str
    evidence_ref: str
    before_depth: int
    after_depth: int
    recorded_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "mutation_type": self.mutation_type,
            "effect_name": self.effect_name,
            "task_id": self.task_id,
            "tenant_id": self.tenant_id,
            "evidence_ref": self.evidence_ref,
            "before_depth": self.before_depth,
            "after_depth": self.after_depth,
            "recorded_at": self.recorded_at,
            "metadata": dict(self.metadata),
        }

    def to_effect_record(self) -> Any:
        from mcoi_runtime.contracts.execution import EffectRecord

        return EffectRecord(
            name=self.effect_name,
            details={
                "receipt_id": self.receipt_id,
                "mutation_type": self.mutation_type,
                "task_id": self.task_id,
                "tenant_id": self.tenant_id,
                "evidence_ref": self.evidence_ref,
                "before_depth": self.before_depth,
                "after_depth": self.after_depth,
                "observed_at": self.recorded_at,
                "metadata": dict(self.metadata),
                "source": "task_queue",
            },
        )


class TaskQueue:
    """Priority queue for async task processing."""

    _MAX_MUTATION_RECEIPTS = 1000

    def __init__(self, *, clock: Callable[[], str], max_depth: int = 10000) -> None:
        self._clock = clock
        self._max_depth = max_depth
        self._heap: list[tuple[int, str, QueuedTask]] = []  # (-priority, task_id, task)
        self._results: dict[str, TaskQueueResult] = {}
        self._mutation_receipts: list[TaskQueueMutationReceipt] = []
        self._counter = 0
        self._processed = 0

    def submit(self, task_id: str, payload: dict[str, Any], priority: int = 0, tenant_id: str = "") -> QueuedTask:
        """Submit a task to the queue."""
        if len(self._heap) >= self._max_depth:
            raise ValueError("queue full")

        before_depth = self.depth
        task = QueuedTask(
            task_id=task_id, priority=priority,
            payload=payload, tenant_id=tenant_id,
            submitted_at=self._clock(),
        )
        heapq.heappush(self._heap, (-priority, task_id, task))
        self._counter += 1
        self._record_mutation_receipt(
            mutation_type="submit",
            effect_name="task_queue_item_submitted",
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            before_depth=before_depth,
            after_depth=self.depth,
            metadata={
                "priority": priority,
                "payload_hash": _sha256_json(payload),
            },
        )
        return task

    def pop(self) -> QueuedTask | None:
        """Pop highest priority task."""
        if not self._heap:
            return None
        before_depth = self.depth
        _, _, task = heapq.heappop(self._heap)
        self._record_mutation_receipt(
            mutation_type="pop",
            effect_name="task_queue_item_dequeued",
            task_id=task.task_id,
            tenant_id=task.tenant_id,
            before_depth=before_depth,
            after_depth=self.depth,
            metadata={"priority": task.priority},
        )
        return task

    def peek(self) -> QueuedTask | None:
        """Peek at highest priority task without removing."""
        if not self._heap:
            return None
        return self._heap[0][2]

    def record_result(self, task_id: str, output: dict[str, Any], succeeded: bool = True, error: str = "") -> TaskQueueResult:
        """Record a task's result."""
        before_depth = self.depth
        result = TaskQueueResult(
            task_id=task_id, output=output, succeeded=succeeded,
            error="" if succeeded else _sanitize_recorded_task_error(error),
            processed_at=self._clock(),
        )
        self._results[task_id] = result
        self._processed += 1
        self._record_mutation_receipt(
            mutation_type="record_result",
            effect_name="task_queue_result_recorded",
            task_id=task_id,
            tenant_id="",
            before_depth=before_depth,
            after_depth=self.depth,
            metadata={
                "succeeded": succeeded,
                "error_present": bool(result.error),
                "output_hash": _sha256_json(output),
            },
        )
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
            "mutation_receipts": len(self._mutation_receipts),
        }

    def mutation_receipts(self, limit: int = 50) -> tuple[TaskQueueMutationReceipt, ...]:
        if limit <= 0:
            return ()
        return tuple(self._mutation_receipts[-limit:])

    def effect_records(self, limit: int = 50) -> tuple[Any, ...]:
        return tuple(receipt.to_effect_record() for receipt in self.mutation_receipts(limit=limit))

    def _record_mutation_receipt(
        self,
        *,
        mutation_type: str,
        effect_name: str,
        task_id: str,
        tenant_id: str,
        before_depth: int,
        after_depth: int,
        metadata: dict[str, Any],
    ) -> TaskQueueMutationReceipt:
        recorded_at = self._clock()
        receipt_id = _receipt_id(
            mutation_type=mutation_type,
            task_id=task_id,
            recorded_at=recorded_at,
            ordinal=len(self._mutation_receipts),
        )
        receipt = TaskQueueMutationReceipt(
            receipt_id=receipt_id,
            mutation_type=mutation_type,
            effect_name=effect_name,
            task_id=task_id,
            tenant_id=tenant_id,
            evidence_ref=f"task-queue-receipt:{receipt_id}",
            before_depth=before_depth,
            after_depth=after_depth,
            recorded_at=recorded_at,
            metadata=metadata,
        )
        self._mutation_receipts.append(receipt)
        if len(self._mutation_receipts) > self._MAX_MUTATION_RECEIPTS:
            self._mutation_receipts = self._mutation_receipts[-self._MAX_MUTATION_RECEIPTS:]
        return receipt


def _sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _receipt_id(*, mutation_type: str, task_id: str, recorded_at: str, ordinal: int) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "mutation_type": mutation_type,
                "task_id": task_id,
                "recorded_at": recorded_at,
                "ordinal": ordinal,
            },
            sort_keys=True,
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"taskq-{mutation_type}-{digest}"
