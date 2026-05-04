"""Purpose: in-memory temporal action scheduler.
Governance scope: deferred temporal action admission, lease control, policy
    re-check, run receipts, and missed/expired action closure.
Dependencies: temporal_runtime engine and temporal_runtime contracts.
Invariants:
  - Scheduled actions never become due before execute_at.
  - Expired actions are closed instead of executed.
  - Leases prevent duplicate worker execution.
  - Temporal policy is re-checked at wake time.
  - Every due evaluation emits a bounded receipt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import StrEnum
from typing import Any, Mapping

from mcoi_runtime.contracts.temporal_runtime import (
    TemporalActionDecision,
    TemporalActionRequest,
    TemporalPolicyVerdict,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.temporal_runtime import TemporalRuntimeEngine


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class ScheduledActionState(StrEnum):
    """Lifecycle state for a scheduled temporal action."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    EXPIRED = "expired"
    BLOCKED = "blocked"
    MISSED = "missed"
    FAILED = "failed"


class ScheduleDecisionVerdict(StrEnum):
    """Scheduler decision for a due-action evaluation."""

    DUE = "due"
    NOT_DUE = "not_due"
    LEASED = "leased"
    COMPLETED = "completed"
    EXPIRED = "expired"
    BLOCKED = "blocked"


@dataclass(frozen=True, slots=True)
class ScheduledTemporalAction:
    """Deferred temporal action waiting for governed wake-time evaluation."""

    schedule_id: str
    tenant_id: str
    action: TemporalActionRequest
    execute_at: str
    state: ScheduledActionState = ScheduledActionState.PENDING
    handler_name: str = ""
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TemporalLease:
    """Worker lease for one scheduled temporal action."""

    lease_id: str
    schedule_id: str
    worker_id: str
    acquired_at: str
    expires_at: str


@dataclass(frozen=True, slots=True)
class TemporalRunReceipt:
    """Bounded receipt for a scheduler evaluation or state closure."""

    receipt_id: str
    schedule_id: str
    tenant_id: str
    verdict: ScheduleDecisionVerdict
    reason: str
    evaluated_at: str
    worker_id: str = ""
    temporal_decision_id: str = ""
    temporal_verdict: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)


class TemporalSchedulerEngine:
    """In-memory scheduler for deferred temporal actions."""

    def __init__(
        self,
        temporal_runtime: TemporalRuntimeEngine,
        *,
        clock: Any,
    ) -> None:
        if not isinstance(temporal_runtime, TemporalRuntimeEngine):
            raise RuntimeCoreInvariantError("temporal_runtime must be a TemporalRuntimeEngine")
        self._temporal_runtime = temporal_runtime
        self._clock = clock
        self._actions: dict[str, ScheduledTemporalAction] = {}
        self._leases: dict[str, TemporalLease] = {}
        self._receipts: list[TemporalRunReceipt] = []

    @property
    def action_count(self) -> int:
        return len(self._actions)

    @property
    def receipt_count(self) -> int:
        return len(self._receipts)

    def register(
        self,
        schedule_id: str,
        action: TemporalActionRequest,
        *,
        handler_name: str = "",
        metadata: Mapping[str, Any] | None = None,
    ) -> ScheduledTemporalAction:
        """Register a deferred temporal action."""
        if schedule_id in self._actions:
            raise RuntimeCoreInvariantError("Duplicate schedule_id")
        if not isinstance(action, TemporalActionRequest):
            raise RuntimeCoreInvariantError("action must be a TemporalActionRequest")
        if not action.execute_at:
            raise RuntimeCoreInvariantError("execute_at is required")

        now = self._clock()
        scheduled = ScheduledTemporalAction(
            schedule_id=schedule_id,
            tenant_id=action.tenant_id,
            action=action,
            execute_at=action.execute_at,
            handler_name=handler_name,
            created_at=now,
            updated_at=now,
            metadata=dict(metadata or {}),
        )
        self._actions[schedule_id] = scheduled
        return scheduled

    def get(self, schedule_id: str) -> ScheduledTemporalAction:
        """Return a scheduled action by id."""
        action = self._actions.get(schedule_id)
        if action is None:
            raise RuntimeCoreInvariantError("Unknown schedule_id")
        return action

    def due_actions(self, now: str | None = None) -> tuple[ScheduledTemporalAction, ...]:
        """Return pending actions due at or before now."""
        now_dt = _parse_iso(now or self._clock())
        due: list[ScheduledTemporalAction] = []
        for action in self._actions.values():
            if action.state is not ScheduledActionState.PENDING:
                continue
            if self._active_lease(action.schedule_id, now_dt) is not None:
                continue
            if action.action.expires_at and now_dt > _parse_iso(action.action.expires_at):
                continue
            if _parse_iso(action.execute_at) <= now_dt:
                due.append(action)
        return tuple(sorted(due, key=lambda item: item.schedule_id))

    def acquire_lease(
        self,
        schedule_id: str,
        worker_id: str,
        *,
        lease_seconds: int = 60,
    ) -> TemporalLease | None:
        """Acquire a lease for a due pending action."""
        action = self.get(schedule_id)
        now_text = self._clock()
        now_dt = _parse_iso(now_text)
        if action.state is not ScheduledActionState.PENDING:
            return None
        if _parse_iso(action.execute_at) > now_dt:
            return None
        if self._active_lease(schedule_id, now_dt) is not None:
            return None

        lease = TemporalLease(
            lease_id=stable_identifier(
                "temp-lease",
                {"schedule_id": schedule_id, "worker_id": worker_id, "at": now_text},
            ),
            schedule_id=schedule_id,
            worker_id=worker_id,
            acquired_at=now_text,
            expires_at=_iso(now_dt + timedelta(seconds=lease_seconds)),
        )
        self._leases[schedule_id] = lease
        self._replace_action(action, ScheduledActionState.RUNNING)
        return lease

    def evaluate_due_action(self, schedule_id: str, *, worker_id: str = "") -> TemporalRunReceipt:
        """Re-check temporal policy for a due action and emit a receipt."""
        action = self.get(schedule_id)
        now = self._clock()
        now_dt = _parse_iso(now)

        if action.state is ScheduledActionState.COMPLETED:
            return self._record(action, ScheduleDecisionVerdict.COMPLETED, "already_completed", now, worker_id)
        if action.state is ScheduledActionState.EXPIRED:
            return self._record(action, ScheduleDecisionVerdict.EXPIRED, "already_expired", now, worker_id)
        if action.state is ScheduledActionState.PENDING and _parse_iso(action.execute_at) > now_dt:
            return self._record(action, ScheduleDecisionVerdict.NOT_DUE, "not_due", now, worker_id)
        if action.action.expires_at and now_dt > _parse_iso(action.action.expires_at):
            self._replace_action(action, ScheduledActionState.EXPIRED)
            return self._record(action, ScheduleDecisionVerdict.EXPIRED, "command_expired", now, worker_id)

        decision = self._temporal_runtime.decide_temporal_action(action.action)
        if decision.verdict is TemporalPolicyVerdict.ALLOW:
            return self._record_temporal(
                action, decision, ScheduleDecisionVerdict.DUE, "temporal_policy_passed", now, worker_id
            )
        if decision.verdict is TemporalPolicyVerdict.DEFER:
            self._replace_action(action, ScheduledActionState.PENDING)
            return self._record_temporal(
                action, decision, ScheduleDecisionVerdict.NOT_DUE, decision.reason, now, worker_id
            )

        self._replace_action(action, ScheduledActionState.BLOCKED)
        return self._record_temporal(
            action, decision, ScheduleDecisionVerdict.BLOCKED, decision.reason, now, worker_id
        )

    def mark_completed(self, schedule_id: str, *, worker_id: str = "") -> TemporalRunReceipt:
        """Mark a scheduled action completed and release its lease."""
        action = self.get(schedule_id)
        self._replace_action(action, ScheduledActionState.COMPLETED)
        self._leases.pop(schedule_id, None)
        return self._record(action, ScheduleDecisionVerdict.COMPLETED, "completed", self._clock(), worker_id)

    def mark_failed(self, schedule_id: str, *, worker_id: str = "") -> TemporalRunReceipt:
        """Mark a scheduled action failed and release its lease."""
        action = self.get(schedule_id)
        self._replace_action(action, ScheduledActionState.FAILED)
        self._leases.pop(schedule_id, None)
        return self._record(action, ScheduleDecisionVerdict.BLOCKED, "failed", self._clock(), worker_id)

    def mark_missed(self, schedule_id: str, *, worker_id: str = "") -> TemporalRunReceipt:
        """Mark a scheduled action missed and release its lease."""
        action = self.get(schedule_id)
        self._replace_action(action, ScheduledActionState.MISSED)
        self._leases.pop(schedule_id, None)
        return self._record(action, ScheduleDecisionVerdict.BLOCKED, "missed_run", self._clock(), worker_id)

    def release_lease(self, schedule_id: str) -> bool:
        """Release a lease and return a running action to pending."""
        action = self.get(schedule_id)
        removed = self._leases.pop(schedule_id, None)
        if removed is None:
            return False
        if action.state is ScheduledActionState.RUNNING:
            self._replace_action(action, ScheduledActionState.PENDING)
        return True

    def recent_receipts(self, limit: int = 50) -> tuple[TemporalRunReceipt, ...]:
        """Return recent scheduler receipts newest first."""
        return tuple(reversed(self._receipts[-limit:]))

    def summary(self) -> dict[str, int]:
        """Return bounded scheduler counters for observability."""
        counts = {state.value: 0 for state in ScheduledActionState}
        for action in self._actions.values():
            counts[action.state.value] += 1
        return {
            "actions": len(self._actions),
            "receipts": len(self._receipts),
            "leases": len(self._leases),
            **counts,
        }

    def _active_lease(self, schedule_id: str, now_dt: datetime) -> TemporalLease | None:
        lease = self._leases.get(schedule_id)
        if lease is None:
            return None
        if _parse_iso(lease.expires_at) <= now_dt:
            self._leases.pop(schedule_id, None)
            action = self._actions.get(schedule_id)
            if action is not None and action.state is ScheduledActionState.RUNNING:
                self._replace_action(action, ScheduledActionState.PENDING)
            return None
        return lease

    def _replace_action(self, action: ScheduledTemporalAction, state: ScheduledActionState) -> None:
        now = self._clock()
        self._actions[action.schedule_id] = ScheduledTemporalAction(
            schedule_id=action.schedule_id,
            tenant_id=action.tenant_id,
            action=action.action,
            execute_at=action.execute_at,
            state=state,
            handler_name=action.handler_name,
            created_at=action.created_at,
            updated_at=now,
            metadata=action.metadata,
        )

    def _record(
        self,
        action: ScheduledTemporalAction,
        verdict: ScheduleDecisionVerdict,
        reason: str,
        evaluated_at: str,
        worker_id: str,
        *,
        temporal_decision_id: str = "",
        temporal_verdict: str = "",
    ) -> TemporalRunReceipt:
        receipt = TemporalRunReceipt(
            receipt_id=stable_identifier(
                "temp-run",
                {
                    "schedule_id": action.schedule_id,
                    "verdict": verdict.value,
                    "reason": reason,
                    "at": evaluated_at,
                    "worker_id": worker_id,
                    "count": str(len(self._receipts) + 1),
                },
            ),
            schedule_id=action.schedule_id,
            tenant_id=action.tenant_id,
            verdict=verdict,
            reason=reason,
            evaluated_at=evaluated_at,
            worker_id=worker_id,
            temporal_decision_id=temporal_decision_id,
            temporal_verdict=temporal_verdict,
        )
        self._receipts.append(receipt)
        return receipt

    def _record_temporal(
        self,
        action: ScheduledTemporalAction,
        decision: TemporalActionDecision,
        verdict: ScheduleDecisionVerdict,
        reason: str,
        evaluated_at: str,
        worker_id: str,
    ) -> TemporalRunReceipt:
        return self._record(
            action,
            verdict,
            reason,
            evaluated_at,
            worker_id,
            temporal_decision_id=decision.decision_id,
            temporal_verdict=decision.verdict.value,
        )
