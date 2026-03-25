"""Purpose: business continuity / disaster recovery runtime engine.
Governance scope: registering continuity and recovery plans, recording
    disruptions, triggering failover and recovery flows, tracking RTO/RPO
    objectives, verifying restoration, detecting violations, producing
    immutable snapshots and closure reports.
Dependencies: continuity_runtime contracts, event_spine, core invariants.
Invariants:
  - Recovery plans must reference valid continuity plans.
  - Failed verification keeps system degraded.
  - Terminal recoveries cannot be re-opened.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.continuity_runtime import (
    ContinuityClosureReport,
    ContinuityPlan,
    ContinuityScope,
    ContinuitySnapshot,
    ContinuityStatus,
    ContinuityViolation,
    DisruptionEvent,
    DisruptionSeverity,
    FailoverDisposition,
    FailoverRecord,
    RecoveryExecution,
    RecoveryObjective,
    RecoveryPlan,
    RecoveryStatus,
    RecoveryVerificationStatus,
    VerificationRecord,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str = "") -> EventRecord:
    if not now:
        now = datetime.now(timezone.utc).isoformat()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cont", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_RECOVERY_TERMINAL = frozenset({RecoveryStatus.COMPLETED, RecoveryStatus.FAILED, RecoveryStatus.CANCELLED})
_PLAN_TERMINAL = frozenset({ContinuityStatus.RETIRED,})


class ContinuityRuntimeEngine:
    """Business continuity and disaster recovery engine."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._plans: dict[str, ContinuityPlan] = {}
        self._recovery_plans: dict[str, RecoveryPlan] = {}
        self._disruptions: dict[str, DisruptionEvent] = {}
        self._failovers: dict[str, FailoverRecord] = {}
        self._executions: dict[str, RecoveryExecution] = {}
        self._objectives: dict[str, RecoveryObjective] = {}
        self._verifications: dict[str, VerificationRecord] = {}
        self._violations: dict[str, ContinuityViolation] = {}
        self._snapshot_ids: set[str] = set()

    def _now(self) -> str:
        """Get current time from injected clock."""
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def plan_count(self) -> int:
        return len(self._plans)

    @property
    def recovery_plan_count(self) -> int:
        return len(self._recovery_plans)

    @property
    def disruption_count(self) -> int:
        return len(self._disruptions)

    @property
    def failover_count(self) -> int:
        return len(self._failovers)

    @property
    def execution_count(self) -> int:
        return len(self._executions)

    @property
    def objective_count(self) -> int:
        return len(self._objectives)

    @property
    def verification_count(self) -> int:
        return len(self._verifications)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Continuity plans
    # ------------------------------------------------------------------

    def register_continuity_plan(
        self,
        plan_id: str,
        name: str,
        tenant_id: str,
        *,
        scope: ContinuityScope = ContinuityScope.SERVICE,
        scope_ref_id: str = "",
        rto_minutes: int = 0,
        rpo_minutes: int = 0,
        failover_target_ref: str = "",
        owner_ref: str = "",
    ) -> ContinuityPlan:
        """Register a continuity plan."""
        if plan_id in self._plans:
            raise RuntimeCoreInvariantError(f"Duplicate plan_id: {plan_id}")
        now = self._now()
        plan = ContinuityPlan(
            plan_id=plan_id, name=name, tenant_id=tenant_id,
            scope=scope, status=ContinuityStatus.ACTIVE,
            scope_ref_id=scope_ref_id, rto_minutes=rto_minutes,
            rpo_minutes=rpo_minutes, failover_target_ref=failover_target_ref,
            owner_ref=owner_ref, created_at=now,
        )
        self._plans[plan_id] = plan
        _emit(self._events, "continuity_plan_registered", {
            "plan_id": plan_id, "name": name, "scope": scope.value,
        }, plan_id, now=self._now())
        return plan

    def get_plan(self, plan_id: str) -> ContinuityPlan:
        """Get a continuity plan by ID."""
        plan = self._plans.get(plan_id)
        if plan is None:
            raise RuntimeCoreInvariantError(f"Unknown plan_id: {plan_id}")
        return plan

    def activate_plan(self, plan_id: str) -> ContinuityPlan:
        """Activate a continuity plan (mark as activated/triggered)."""
        old = self.get_plan(plan_id)
        if old.status in _PLAN_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot activate plan in status {old.status.value}"
            )
        updated = ContinuityPlan(
            plan_id=old.plan_id, name=old.name, tenant_id=old.tenant_id,
            scope=old.scope, status=ContinuityStatus.ACTIVATED,
            scope_ref_id=old.scope_ref_id, rto_minutes=old.rto_minutes,
            rpo_minutes=old.rpo_minutes, failover_target_ref=old.failover_target_ref,
            owner_ref=old.owner_ref, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._plans[plan_id] = updated
        _emit(self._events, "continuity_plan_activated", {"plan_id": plan_id}, plan_id, now=self._now())
        return updated

    def suspend_plan(self, plan_id: str) -> ContinuityPlan:
        """Suspend a continuity plan."""
        old = self.get_plan(plan_id)
        if old.status in _PLAN_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot suspend plan in status {old.status.value}"
            )
        updated = ContinuityPlan(
            plan_id=old.plan_id, name=old.name, tenant_id=old.tenant_id,
            scope=old.scope, status=ContinuityStatus.SUSPENDED,
            scope_ref_id=old.scope_ref_id, rto_minutes=old.rto_minutes,
            rpo_minutes=old.rpo_minutes, failover_target_ref=old.failover_target_ref,
            owner_ref=old.owner_ref, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._plans[plan_id] = updated
        _emit(self._events, "continuity_plan_suspended", {"plan_id": plan_id}, plan_id, now=self._now())
        return updated

    def retire_plan(self, plan_id: str) -> ContinuityPlan:
        """Retire a continuity plan."""
        old = self.get_plan(plan_id)
        if old.status == ContinuityStatus.RETIRED:
            raise RuntimeCoreInvariantError("Plan already retired")
        updated = ContinuityPlan(
            plan_id=old.plan_id, name=old.name, tenant_id=old.tenant_id,
            scope=old.scope, status=ContinuityStatus.RETIRED,
            scope_ref_id=old.scope_ref_id, rto_minutes=old.rto_minutes,
            rpo_minutes=old.rpo_minutes, failover_target_ref=old.failover_target_ref,
            owner_ref=old.owner_ref, created_at=old.created_at,
            metadata=old.metadata,
        )
        self._plans[plan_id] = updated
        _emit(self._events, "continuity_plan_retired", {"plan_id": plan_id}, plan_id, now=self._now())
        return updated

    def plans_for_tenant(self, tenant_id: str) -> tuple[ContinuityPlan, ...]:
        """Return all plans for a tenant."""
        return tuple(p for p in self._plans.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Recovery plans
    # ------------------------------------------------------------------

    def register_recovery_plan(
        self,
        recovery_plan_id: str,
        plan_id: str,
        name: str,
        tenant_id: str,
        *,
        priority: int = 0,
        description: str = "",
    ) -> RecoveryPlan:
        """Register a recovery plan linked to a continuity plan."""
        if recovery_plan_id in self._recovery_plans:
            raise RuntimeCoreInvariantError(f"Duplicate recovery_plan_id: {recovery_plan_id}")
        if plan_id not in self._plans:
            raise RuntimeCoreInvariantError(f"Unknown plan_id: {plan_id}")
        now = self._now()
        rp = RecoveryPlan(
            recovery_plan_id=recovery_plan_id, plan_id=plan_id,
            name=name, tenant_id=tenant_id,
            status=RecoveryStatus.PENDING, priority=priority,
            description=description, created_at=now,
        )
        self._recovery_plans[recovery_plan_id] = rp
        _emit(self._events, "recovery_plan_registered", {
            "recovery_plan_id": recovery_plan_id, "plan_id": plan_id,
        }, recovery_plan_id, now=self._now())
        return rp

    def get_recovery_plan(self, recovery_plan_id: str) -> RecoveryPlan:
        """Get a recovery plan by ID."""
        rp = self._recovery_plans.get(recovery_plan_id)
        if rp is None:
            raise RuntimeCoreInvariantError(f"Unknown recovery_plan_id: {recovery_plan_id}")
        return rp

    def recovery_plans_for_plan(self, plan_id: str) -> tuple[RecoveryPlan, ...]:
        """Return all recovery plans for a continuity plan."""
        return tuple(rp for rp in self._recovery_plans.values() if rp.plan_id == plan_id)

    # ------------------------------------------------------------------
    # Disruptions
    # ------------------------------------------------------------------

    def record_disruption(
        self,
        disruption_id: str,
        tenant_id: str,
        *,
        scope: ContinuityScope = ContinuityScope.SERVICE,
        scope_ref_id: str = "",
        severity: DisruptionSeverity = DisruptionSeverity.MEDIUM,
        description: str = "",
    ) -> DisruptionEvent:
        """Record a disruption event."""
        if disruption_id in self._disruptions:
            raise RuntimeCoreInvariantError(f"Duplicate disruption_id: {disruption_id}")
        now = self._now()
        event = DisruptionEvent(
            disruption_id=disruption_id, tenant_id=tenant_id,
            scope=scope, scope_ref_id=scope_ref_id,
            severity=severity, description=description,
            detected_at=now,
        )
        self._disruptions[disruption_id] = event
        _emit(self._events, "disruption_recorded", {
            "disruption_id": disruption_id, "severity": severity.value,
            "scope": scope.value,
        }, disruption_id, now=self._now())
        return event

    def get_disruption(self, disruption_id: str) -> DisruptionEvent:
        """Get a disruption event by ID."""
        d = self._disruptions.get(disruption_id)
        if d is None:
            raise RuntimeCoreInvariantError(f"Unknown disruption_id: {disruption_id}")
        return d

    def resolve_disruption(self, disruption_id: str) -> DisruptionEvent:
        """Mark a disruption as resolved."""
        old = self.get_disruption(disruption_id)
        if old.resolved_at:
            raise RuntimeCoreInvariantError("Disruption already resolved")
        now = self._now()
        updated = DisruptionEvent(
            disruption_id=old.disruption_id, tenant_id=old.tenant_id,
            scope=old.scope, scope_ref_id=old.scope_ref_id,
            severity=old.severity, description=old.description,
            detected_at=old.detected_at, resolved_at=now,
            metadata=old.metadata,
        )
        self._disruptions[disruption_id] = updated
        _emit(self._events, "disruption_resolved", {
            "disruption_id": disruption_id,
        }, disruption_id, now=self._now())
        return updated

    def disruptions_for_tenant(self, tenant_id: str) -> tuple[DisruptionEvent, ...]:
        """Return all disruptions for a tenant."""
        return tuple(d for d in self._disruptions.values() if d.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Failover
    # ------------------------------------------------------------------

    def trigger_failover(
        self,
        failover_id: str,
        plan_id: str,
        disruption_id: str,
        *,
        source_ref: str = "",
        target_ref: str = "",
    ) -> FailoverRecord:
        """Trigger a failover action."""
        if failover_id in self._failovers:
            raise RuntimeCoreInvariantError(f"Duplicate failover_id: {failover_id}")
        plan = self.get_plan(plan_id)
        if plan.status in _PLAN_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot trigger failover for {plan.status.value} plan"
            )
        if disruption_id not in self._disruptions:
            raise RuntimeCoreInvariantError(f"Unknown disruption_id: {disruption_id}")
        # Auto-activate plan if not already
        if plan.status not in (ContinuityStatus.ACTIVATED,):
            self.activate_plan(plan_id)
        now = self._now()
        effective_target = target_ref or plan.failover_target_ref
        fo = FailoverRecord(
            failover_id=failover_id, plan_id=plan_id,
            disruption_id=disruption_id,
            disposition=FailoverDisposition.INITIATED,
            source_ref=source_ref, target_ref=effective_target,
            initiated_at=now,
        )
        self._failovers[failover_id] = fo
        _emit(self._events, "failover_triggered", {
            "failover_id": failover_id, "plan_id": plan_id,
            "disruption_id": disruption_id,
        }, failover_id, now=self._now())
        return fo

    def complete_failover(self, failover_id: str) -> FailoverRecord:
        """Complete a failover action."""
        old = self._failovers.get(failover_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown failover_id: {failover_id}")
        if old.disposition != FailoverDisposition.INITIATED:
            raise RuntimeCoreInvariantError(
                f"Can only complete INITIATED failovers, got {old.disposition.value}"
            )
        now = self._now()
        updated = FailoverRecord(
            failover_id=old.failover_id, plan_id=old.plan_id,
            disruption_id=old.disruption_id,
            disposition=FailoverDisposition.COMPLETED,
            source_ref=old.source_ref, target_ref=old.target_ref,
            initiated_at=old.initiated_at, completed_at=now,
            metadata=old.metadata,
        )
        self._failovers[failover_id] = updated
        _emit(self._events, "failover_completed", {"failover_id": failover_id}, failover_id, now=self._now())
        return updated

    def fail_failover(self, failover_id: str) -> FailoverRecord:
        """Mark a failover as failed."""
        old = self._failovers.get(failover_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown failover_id: {failover_id}")
        if old.disposition != FailoverDisposition.INITIATED:
            raise RuntimeCoreInvariantError(
                f"Can only fail INITIATED failovers, got {old.disposition.value}"
            )
        now = self._now()
        updated = FailoverRecord(
            failover_id=old.failover_id, plan_id=old.plan_id,
            disruption_id=old.disruption_id,
            disposition=FailoverDisposition.FAILED,
            source_ref=old.source_ref, target_ref=old.target_ref,
            initiated_at=old.initiated_at, completed_at=now,
            metadata=old.metadata,
        )
        self._failovers[failover_id] = updated
        _emit(self._events, "failover_failed", {"failover_id": failover_id}, failover_id, now=self._now())
        return updated

    def rollback_failover(self, failover_id: str) -> FailoverRecord:
        """Roll back a failover."""
        old = self._failovers.get(failover_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown failover_id: {failover_id}")
        if old.disposition in (FailoverDisposition.ROLLED_BACK, FailoverDisposition.FAILED):
            raise RuntimeCoreInvariantError(
                f"Cannot roll back failover in {old.disposition.value}"
            )
        now = self._now()
        updated = FailoverRecord(
            failover_id=old.failover_id, plan_id=old.plan_id,
            disruption_id=old.disruption_id,
            disposition=FailoverDisposition.ROLLED_BACK,
            source_ref=old.source_ref, target_ref=old.target_ref,
            initiated_at=old.initiated_at, completed_at=now,
            metadata=old.metadata,
        )
        self._failovers[failover_id] = updated
        _emit(self._events, "failover_rolled_back", {"failover_id": failover_id}, failover_id, now=self._now())
        return updated

    def failovers_for_plan(self, plan_id: str) -> tuple[FailoverRecord, ...]:
        """Return all failovers for a plan."""
        return tuple(f for f in self._failovers.values() if f.plan_id == plan_id)

    # ------------------------------------------------------------------
    # Recovery execution
    # ------------------------------------------------------------------

    def start_recovery(
        self,
        execution_id: str,
        recovery_plan_id: str,
        disruption_id: str,
        *,
        executed_by: str = "system",
    ) -> RecoveryExecution:
        """Start a recovery execution."""
        if execution_id in self._executions:
            raise RuntimeCoreInvariantError(f"Duplicate execution_id: {execution_id}")
        if recovery_plan_id not in self._recovery_plans:
            raise RuntimeCoreInvariantError(f"Unknown recovery_plan_id: {recovery_plan_id}")
        if disruption_id not in self._disruptions:
            raise RuntimeCoreInvariantError(f"Unknown disruption_id: {disruption_id}")
        now = self._now()
        exe = RecoveryExecution(
            execution_id=execution_id, recovery_plan_id=recovery_plan_id,
            disruption_id=disruption_id, status=RecoveryStatus.IN_PROGRESS,
            executed_by=executed_by, started_at=now,
        )
        self._executions[execution_id] = exe
        _emit(self._events, "recovery_started", {
            "execution_id": execution_id, "recovery_plan_id": recovery_plan_id,
        }, execution_id, now=self._now())
        return exe

    def complete_recovery(self, execution_id: str) -> RecoveryExecution:
        """Complete a recovery execution."""
        old = self._executions.get(execution_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown execution_id: {execution_id}")
        if old.status in _RECOVERY_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Recovery already in terminal status {old.status.value}"
            )
        now = self._now()
        updated = RecoveryExecution(
            execution_id=old.execution_id, recovery_plan_id=old.recovery_plan_id,
            disruption_id=old.disruption_id, status=RecoveryStatus.COMPLETED,
            executed_by=old.executed_by, started_at=old.started_at,
            completed_at=now, metadata=old.metadata,
        )
        self._executions[execution_id] = updated
        _emit(self._events, "recovery_completed", {"execution_id": execution_id}, execution_id, now=self._now())
        return updated

    def fail_recovery(self, execution_id: str) -> RecoveryExecution:
        """Mark a recovery as failed."""
        old = self._executions.get(execution_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown execution_id: {execution_id}")
        if old.status in _RECOVERY_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Recovery already in terminal status {old.status.value}"
            )
        now = self._now()
        updated = RecoveryExecution(
            execution_id=old.execution_id, recovery_plan_id=old.recovery_plan_id,
            disruption_id=old.disruption_id, status=RecoveryStatus.FAILED,
            executed_by=old.executed_by, started_at=old.started_at,
            completed_at=now, metadata=old.metadata,
        )
        self._executions[execution_id] = updated
        _emit(self._events, "recovery_failed", {"execution_id": execution_id}, execution_id, now=self._now())
        return updated

    def cancel_recovery(self, execution_id: str) -> RecoveryExecution:
        """Cancel a recovery execution."""
        old = self._executions.get(execution_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown execution_id: {execution_id}")
        if old.status in _RECOVERY_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Recovery already in terminal status {old.status.value}"
            )
        updated = RecoveryExecution(
            execution_id=old.execution_id, recovery_plan_id=old.recovery_plan_id,
            disruption_id=old.disruption_id, status=RecoveryStatus.CANCELLED,
            executed_by=old.executed_by, started_at=old.started_at,
            metadata=old.metadata,
        )
        self._executions[execution_id] = updated
        _emit(self._events, "recovery_cancelled", {"execution_id": execution_id}, execution_id, now=self._now())
        return updated

    def executions_for_disruption(self, disruption_id: str) -> tuple[RecoveryExecution, ...]:
        """Return all executions for a disruption."""
        return tuple(e for e in self._executions.values() if e.disruption_id == disruption_id)

    # ------------------------------------------------------------------
    # Recovery objectives
    # ------------------------------------------------------------------

    def record_objective(
        self,
        objective_id: str,
        plan_id: str,
        name: str,
        target_minutes: int,
        actual_minutes: int,
    ) -> RecoveryObjective:
        """Record a recovery objective evaluation."""
        if objective_id in self._objectives:
            raise RuntimeCoreInvariantError(f"Duplicate objective_id: {objective_id}")
        if plan_id not in self._plans:
            raise RuntimeCoreInvariantError(f"Unknown plan_id: {plan_id}")
        now = self._now()
        met = actual_minutes <= target_minutes
        obj = RecoveryObjective(
            objective_id=objective_id, plan_id=plan_id, name=name,
            target_minutes=target_minutes, actual_minutes=actual_minutes,
            met=met, evaluated_at=now,
        )
        self._objectives[objective_id] = obj
        _emit(self._events, "objective_recorded", {
            "objective_id": objective_id, "met": met,
        }, plan_id, now=self._now())
        return obj

    def objectives_for_plan(self, plan_id: str) -> tuple[RecoveryObjective, ...]:
        """Return all objectives for a plan."""
        return tuple(o for o in self._objectives.values() if o.plan_id == plan_id)

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    def verify_recovery(
        self,
        verification_id: str,
        execution_id: str,
        *,
        status: RecoveryVerificationStatus = RecoveryVerificationStatus.PASSED,
        verified_by: str = "system",
        confidence: float = 1.0,
        reason: str = "",
    ) -> VerificationRecord:
        """Verify a recovery execution."""
        if verification_id in self._verifications:
            raise RuntimeCoreInvariantError(f"Duplicate verification_id: {verification_id}")
        if execution_id not in self._executions:
            raise RuntimeCoreInvariantError(f"Unknown execution_id: {execution_id}")
        now = self._now()
        vr = VerificationRecord(
            verification_id=verification_id, execution_id=execution_id,
            status=status, verified_by=verified_by,
            confidence=confidence, reason=reason,
            verified_at=now,
        )
        self._verifications[verification_id] = vr

        # If verification failed, mark recovery as failed
        if status == RecoveryVerificationStatus.FAILED:
            exe = self._executions[execution_id]
            if exe.status not in _RECOVERY_TERMINAL:
                self.fail_recovery(execution_id)

        _emit(self._events, "recovery_verified", {
            "verification_id": verification_id, "execution_id": execution_id,
            "status": status.value,
        }, execution_id, now=self._now())
        return vr

    def verifications_for_execution(self, execution_id: str) -> tuple[VerificationRecord, ...]:
        """Return all verifications for an execution."""
        return tuple(v for v in self._verifications.values() if v.execution_id == execution_id)

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_continuity_violations(self) -> tuple[ContinuityViolation, ...]:
        """Detect continuity and recovery violations."""
        now = self._now()
        new_violations: list[ContinuityViolation] = []

        # Activated plans with no recovery plans
        for plan in self._plans.values():
            if plan.status == ContinuityStatus.ACTIVATED:
                rps = [rp for rp in self._recovery_plans.values() if rp.plan_id == plan.plan_id]
                if not rps:
                    vid = stable_identifier("viol-cont", {
                        "plan": plan.plan_id, "op": "activated_no_recovery",
                    })
                    if vid not in self._violations:
                        v = ContinuityViolation(
                            violation_id=vid, plan_id=plan.plan_id,
                            tenant_id=plan.tenant_id,
                            operation="activated_no_recovery",
                            reason=f"Plan {plan.plan_id} is activated but has no recovery plans",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Failed failovers with no subsequent recovery
        for fo in self._failovers.values():
            if fo.disposition == FailoverDisposition.FAILED:
                has_recovery = any(
                    e.disruption_id == fo.disruption_id
                    for e in self._executions.values()
                )
                if not has_recovery:
                    vid = stable_identifier("viol-cont", {
                        "failover": fo.failover_id, "op": "failed_no_recovery",
                    })
                    if vid not in self._violations:
                        plan = self._plans.get(fo.plan_id)
                        tenant_id = plan.tenant_id if plan else "unknown"
                        v = ContinuityViolation(
                            violation_id=vid, plan_id=fo.plan_id,
                            tenant_id=tenant_id,
                            operation="failed_failover_no_recovery",
                            reason=f"Failover {fo.failover_id} failed but no recovery started for disruption {fo.disruption_id}",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # Unresolved disruptions with failed recoveries
        for disruption in self._disruptions.values():
            if not disruption.resolved_at:
                exes = [e for e in self._executions.values() if e.disruption_id == disruption.disruption_id]
                if exes and all(e.status == RecoveryStatus.FAILED for e in exes):
                    vid = stable_identifier("viol-cont", {
                        "disruption": disruption.disruption_id, "op": "all_recoveries_failed",
                    })
                    if vid not in self._violations:
                        v = ContinuityViolation(
                            violation_id=vid, plan_id=disruption.disruption_id,
                            tenant_id=disruption.tenant_id,
                            operation="all_recoveries_failed",
                            reason=f"All {len(exes)} recovery executions failed for disruption {disruption.disruption_id}",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "continuity_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan", now=self._now())
        return tuple(new_violations)

    def violations_for_plan(self, plan_id: str) -> tuple[ContinuityViolation, ...]:
        """Return all violations for a plan."""
        return tuple(v for v in self._violations.values() if v.plan_id == plan_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def continuity_snapshot(self, snapshot_id: str) -> ContinuitySnapshot:
        """Capture a point-in-time continuity snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = self._now()
        snap = ContinuitySnapshot(
            snapshot_id=snapshot_id,
            total_plans=self.plan_count,
            total_active_plans=sum(
                1 for p in self._plans.values()
                if p.status in (ContinuityStatus.ACTIVE, ContinuityStatus.ACTIVATED)
            ),
            total_recovery_plans=self.recovery_plan_count,
            total_disruptions=self.disruption_count,
            total_failovers=self.failover_count,
            total_recoveries=self.execution_count,
            total_verifications=self.verification_count,
            total_violations=self.violation_count,
            total_objectives=self.objective_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "continuity_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id, now=self._now())
        return snap

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"plans={self.plan_count}",
            f"recovery_plans={self.recovery_plan_count}",
            f"disruptions={self.disruption_count}",
            f"failovers={self.failover_count}",
            f"executions={self.execution_count}",
            f"objectives={self.objective_count}",
            f"verifications={self.verification_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()

    # ------------------------------------------------------------------
    # Snapshot / Restore
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        return {
            "plans": self._plans,
            "recovery_plans": self._recovery_plans,
            "disruptions": self._disruptions,
            "failovers": self._failovers,
            "executions": self._executions,
            "objectives": self._objectives,
            "verifications": self._verifications,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result
