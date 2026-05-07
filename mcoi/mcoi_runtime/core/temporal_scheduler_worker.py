"""Purpose: governed worker loop for due temporal scheduler actions.
Governance scope: lease acquisition, wake-time policy re-check, handler
    dispatch, receipt persistence, and optional proof certification.
Dependencies: temporal scheduler engine, temporal scheduler store, proof bridge.
Invariants:
  - A handler is called only after temporal policy returns a due receipt.
  - Missing or failing handlers close the schedule with a bounded failure receipt.
  - Every scheduler receipt is persisted before the next action is processed.
  - Proof certification is optional but deterministic when supplied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from mcoi_runtime.core.proof_bridge import ProofBridge, TemporalSchedulerProof
from mcoi_runtime.core.temporal_scheduler import (
    ScheduledTemporalAction,
    ScheduleDecisionVerdict,
    TemporalRunReceipt,
    TemporalSchedulerEngine,
)
from mcoi_runtime.persistence.temporal_scheduler_store import TemporalSchedulerStore


TemporalActionHandler = Callable[[ScheduledTemporalAction], Mapping[str, Any] | None]


@dataclass(frozen=True, slots=True)
class TemporalWorkerResult:
    """Result of one scheduler worker action attempt."""

    schedule_id: str
    worker_id: str
    evaluation_receipt: TemporalRunReceipt
    closure_receipt: TemporalRunReceipt | None = None
    proofs: tuple[TemporalSchedulerProof, ...] = ()


class TemporalSchedulerWorker:
    """Bounded runner for due temporal actions."""

    def __init__(
        self,
        *,
        scheduler: TemporalSchedulerEngine,
        store: TemporalSchedulerStore,
        worker_id: str,
        handlers: Mapping[str, TemporalActionHandler] | None = None,
        proof_bridge: ProofBridge | None = None,
        lease_seconds: int = 60,
    ) -> None:
        if not isinstance(scheduler, TemporalSchedulerEngine):
            raise TypeError("scheduler must be a TemporalSchedulerEngine")
        if not isinstance(store, TemporalSchedulerStore):
            raise TypeError("store must be a TemporalSchedulerStore")
        if not worker_id:
            raise ValueError("worker_id is required")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        self._scheduler = scheduler
        self._store = store
        self._worker_id = worker_id
        self._handlers = dict(handlers or {})
        self._proof_bridge = proof_bridge
        self._lease_seconds = lease_seconds

    def run_once(self, *, limit: int = 10) -> tuple[TemporalWorkerResult, ...]:
        """Process currently due actions up to limit."""
        if limit < 1:
            raise ValueError("limit must be positive")
        results: list[TemporalWorkerResult] = []
        for scheduled in self._scheduler.due_actions()[:limit]:
            lease = self._scheduler.acquire_lease(
                scheduled.schedule_id,
                self._worker_id,
                lease_seconds=self._lease_seconds,
            )
            if lease is None:
                continue
            results.append(self._run_leased(scheduled))
        return tuple(results)

    def _run_leased(self, scheduled: ScheduledTemporalAction) -> TemporalWorkerResult:
        evaluation = self._scheduler.evaluate_due_action(
            scheduled.schedule_id,
            worker_id=self._worker_id,
        )
        self._store.append_receipt(evaluation)
        self._store.save_action(self._scheduler.get(scheduled.schedule_id))
        proofs = self._certify(scheduled, evaluation)
        if evaluation.verdict is not ScheduleDecisionVerdict.DUE:
            return TemporalWorkerResult(
                schedule_id=scheduled.schedule_id,
                worker_id=self._worker_id,
                evaluation_receipt=evaluation,
                proofs=proofs,
            )

        running = self._scheduler.get(scheduled.schedule_id)
        handler = self._handlers.get(running.handler_name)
        if handler is None:
            closure = self._scheduler.mark_failed(
                scheduled.schedule_id,
                worker_id=self._worker_id,
                reason="missing_handler",
            )
        else:
            try:
                handler(running)
            except Exception:
                closure = self._scheduler.mark_failed(
                    scheduled.schedule_id,
                    worker_id=self._worker_id,
                    reason="handler_error",
                )
            else:
                closure = self._scheduler.mark_completed(
                    scheduled.schedule_id,
                    worker_id=self._worker_id,
                )
        self._store.append_receipt(closure)
        self._store.save_action(self._scheduler.get(scheduled.schedule_id))
        closure_proofs = self._certify(running, closure)
        return TemporalWorkerResult(
            schedule_id=scheduled.schedule_id,
            worker_id=self._worker_id,
            evaluation_receipt=evaluation,
            closure_receipt=closure,
            proofs=proofs + closure_proofs,
        )

    def _certify(
        self,
        scheduled: ScheduledTemporalAction,
        receipt: TemporalRunReceipt,
    ) -> tuple[TemporalSchedulerProof, ...]:
        if self._proof_bridge is None:
            return ()
        proof = self._proof_bridge.certify_temporal_run_receipt(
            scheduled_action=scheduled,
            run_receipt=receipt,
            actor_id=self._worker_id,
        )
        return (proof,)
