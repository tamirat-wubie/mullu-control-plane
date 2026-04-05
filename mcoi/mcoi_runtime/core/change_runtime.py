"""Purpose: controlled change / recommendation execution runtime engine.
Governance scope: managing change lifecycle — create, plan, approve, execute,
    pause, abort, rollback, complete, collect evidence, assess impact.
Dependencies: change_runtime contracts, event_spine, core invariants.
Invariants:
  - No duplicate change or plan IDs.
  - Approval is required before execution when approval_required=True.
  - Status transitions are validated.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.change_runtime import (
    ChangeApprovalBinding,
    ChangeEvidenceKind,
    ChangeEvidence,
    ChangeExecution,
    ChangeImpactAssessment,
    ChangeOutcome,
    ChangePlan,
    ChangeRequest,
    ChangeScope,
    ChangeStatus,
    ChangeStep,
    ChangeType,
    RollbackDisposition,
    RollbackPlan,
    RolloutMode,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-chg", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


# Valid status transitions
_VALID_TRANSITIONS: dict[ChangeStatus, set[ChangeStatus]] = {
    ChangeStatus.DRAFT: {ChangeStatus.PENDING_APPROVAL, ChangeStatus.APPROVED, ChangeStatus.IN_PROGRESS},
    ChangeStatus.PENDING_APPROVAL: {ChangeStatus.APPROVED, ChangeStatus.ABORTED},
    ChangeStatus.APPROVED: {ChangeStatus.IN_PROGRESS, ChangeStatus.ABORTED},
    ChangeStatus.IN_PROGRESS: {ChangeStatus.PAUSED, ChangeStatus.COMPLETED, ChangeStatus.ABORTED, ChangeStatus.FAILED, ChangeStatus.ROLLED_BACK},
    ChangeStatus.PAUSED: {ChangeStatus.IN_PROGRESS, ChangeStatus.ABORTED, ChangeStatus.ROLLED_BACK},
    ChangeStatus.COMPLETED: set(),
    ChangeStatus.ABORTED: set(),
    ChangeStatus.ROLLED_BACK: set(),
    ChangeStatus.FAILED: {ChangeStatus.ROLLED_BACK},
}


class ChangeRuntimeEngine:
    """Engine for controlled change lifecycle management."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._changes: dict[str, ChangeRequest] = {}
        self._plans: dict[str, ChangePlan] = {}
        self._steps: dict[str, ChangeStep] = {}
        self._executions: dict[str, ChangeExecution] = {}
        self._approvals: dict[str, list[ChangeApprovalBinding]] = {}
        self._evidence: dict[str, list[ChangeEvidence]] = {}
        self._rollbacks: dict[str, RollbackPlan] = {}
        self._outcomes: dict[str, ChangeOutcome] = {}
        self._impacts: list[ChangeImpactAssessment] = []
        # Track current status per change
        self._status: dict[str, ChangeStatus] = {}

    # ------------------------------------------------------------------
    # Change request management
    # ------------------------------------------------------------------

    def create_change_request(
        self,
        change_id: str,
        title: str,
        change_type: ChangeType,
        *,
        recommendation_id: str = "",
        scope: ChangeScope = ChangeScope.GLOBAL,
        scope_ref_id: str = "",
        description: str = "",
        rollout_mode: RolloutMode = RolloutMode.IMMEDIATE,
        priority: str = "normal",
        requested_by: str = "",
        reason: str = "",
        approval_required: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ChangeRequest:
        if change_id in self._changes:
            raise RuntimeCoreInvariantError("change already exists")
        now = _now_iso()
        change = ChangeRequest(
            change_id=change_id,
            recommendation_id=recommendation_id,
            change_type=change_type,
            scope=scope,
            scope_ref_id=scope_ref_id or change_id,
            title=title,
            description=description,
            status=ChangeStatus.DRAFT,
            rollout_mode=rollout_mode,
            priority=priority,
            requested_by=requested_by,
            reason=reason,
            approval_required=approval_required,
            created_at=now,
            metadata=metadata or {},
        )
        self._changes[change_id] = change
        self._status[change_id] = ChangeStatus.DRAFT
        _emit(self._events, "change_request_created", {
            "change_id": change_id,
            "change_type": change_type.value,
            "approval_required": approval_required,
        }, change_id)
        return change

    def get_change(self, change_id: str) -> ChangeRequest | None:
        return self._changes.get(change_id)

    def get_change_status(self, change_id: str) -> ChangeStatus:
        if change_id not in self._status:
            raise RuntimeCoreInvariantError("change not found")
        return self._status[change_id]

    # ------------------------------------------------------------------
    # Plan management
    # ------------------------------------------------------------------

    def plan_change(
        self,
        plan_id: str,
        change_id: str,
        title: str,
        steps: list[dict[str, Any]],
        *,
        rollout_mode: RolloutMode | None = None,
        estimated_duration_seconds: float = 0.0,
    ) -> ChangePlan:
        if change_id not in self._changes:
            raise RuntimeCoreInvariantError("change not found")
        if plan_id in self._plans:
            raise RuntimeCoreInvariantError("plan already exists")
        now = _now_iso()
        change = self._changes[change_id]
        mode = rollout_mode or change.rollout_mode

        # Create steps
        step_ids = []
        for i, step_data in enumerate(steps):
            sid = step_data.get("step_id", f"{plan_id}-step-{i}")
            step = ChangeStep(
                step_id=sid,
                plan_id=plan_id,
                change_id=change_id,
                ordinal=i,
                action=step_data.get("action", f"step-{i}"),
                target_ref_id=step_data.get("target_ref_id", ""),
                description=step_data.get("description", ""),
                status=ChangeStatus.DRAFT,
                metadata=step_data.get("metadata", {}),
            )
            self._steps[sid] = step
            step_ids.append(sid)

        plan = ChangePlan(
            plan_id=plan_id,
            change_id=change_id,
            title=title,
            step_ids=tuple(step_ids),
            rollout_mode=mode,
            estimated_duration_seconds=estimated_duration_seconds,
            created_at=now,
            metadata={},
        )
        self._plans[plan_id] = plan
        _emit(self._events, "change_planned", {
            "plan_id": plan_id,
            "change_id": change_id,
            "steps": len(step_ids),
            "rollout_mode": mode.value,
        }, change_id)
        return plan

    def get_plan(self, plan_id: str) -> ChangePlan | None:
        return self._plans.get(plan_id)

    # ------------------------------------------------------------------
    # Approval management
    # ------------------------------------------------------------------

    def approve_change(
        self,
        approval_id: str,
        change_id: str,
        approved_by: str,
        *,
        approved: bool = True,
        reason: str = "",
    ) -> ChangeApprovalBinding:
        if change_id not in self._changes:
            raise RuntimeCoreInvariantError("change not found")
        now = _now_iso()
        binding = ChangeApprovalBinding(
            approval_id=approval_id,
            change_id=change_id,
            approved_by=approved_by,
            approved=approved,
            reason=reason,
            approved_at=now,
        )
        self._approvals.setdefault(change_id, []).append(binding)

        if approved:
            self._transition(change_id, ChangeStatus.APPROVED)
        else:
            self._transition(change_id, ChangeStatus.ABORTED)

        _emit(self._events, "change_approval", {
            "change_id": change_id,
            "approved": approved,
            "approved_by": approved_by,
        }, change_id)
        return binding

    def get_approvals(self, change_id: str) -> tuple[ChangeApprovalBinding, ...]:
        return tuple(self._approvals.get(change_id, []))

    def is_approved(self, change_id: str) -> bool:
        return self._status.get(change_id) in {
            ChangeStatus.APPROVED,
            ChangeStatus.IN_PROGRESS,
            ChangeStatus.PAUSED,
            ChangeStatus.COMPLETED,
        }

    # ------------------------------------------------------------------
    # Execution management
    # ------------------------------------------------------------------

    def execute_change_step(
        self,
        change_id: str,
        step_id: str,
        *,
        success: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ChangeStep:
        if change_id not in self._changes:
            raise RuntimeCoreInvariantError("change not found")
        change = self._changes[change_id]

        # Must be approved if approval required
        if change.approval_required and self._status[change_id] not in {
            ChangeStatus.APPROVED, ChangeStatus.IN_PROGRESS,
        }:
            raise RuntimeCoreInvariantError(
                "change requires approval before execution from current status"
            )

        # Transition to IN_PROGRESS on first step
        if self._status[change_id] == ChangeStatus.APPROVED:
            self._transition(change_id, ChangeStatus.IN_PROGRESS)
        elif self._status[change_id] == ChangeStatus.DRAFT and not change.approval_required:
            self._transition(change_id, ChangeStatus.IN_PROGRESS)

        if step_id not in self._steps:
            raise RuntimeCoreInvariantError("step not found")

        now = _now_iso()
        old_step = self._steps[step_id]
        new_status = ChangeStatus.COMPLETED if success else ChangeStatus.FAILED
        updated = ChangeStep(
            step_id=old_step.step_id,
            plan_id=old_step.plan_id,
            change_id=old_step.change_id,
            ordinal=old_step.ordinal,
            action=old_step.action,
            target_ref_id=old_step.target_ref_id,
            description=old_step.description,
            status=new_status,
            started_at=old_step.started_at or now,
            completed_at=now,
            metadata=metadata or dict(old_step.metadata),
        )
        self._steps[step_id] = updated

        # Create/update execution record
        self._ensure_execution(change_id, now)

        _emit(self._events, "change_step_executed", {
            "change_id": change_id,
            "step_id": step_id,
            "success": success,
        }, change_id)
        return updated

    def _ensure_execution(self, change_id: str, now: str) -> None:
        """Create or update the execution record for a change."""
        # Find plan for this change
        plan = None
        for p in self._plans.values():
            if p.change_id == change_id:
                plan = p
                break

        # Count current step statuses
        completed = sum(
            1 for s in self._steps.values()
            if s.change_id == change_id and s.status == ChangeStatus.COMPLETED
        )
        failed = sum(
            1 for s in self._steps.values()
            if s.change_id == change_id and s.status == ChangeStatus.FAILED
        )

        if change_id not in self._executions:
            exec_id = stable_identifier("cexe", {"cid": change_id, "ts": now})
            plan_id = plan.plan_id if plan else change_id
            steps_total = len(plan.step_ids) if plan else 0
            execution = ChangeExecution(
                execution_id=exec_id,
                change_id=change_id,
                plan_id=plan_id,
                status=ChangeStatus.IN_PROGRESS,
                steps_total=steps_total,
                steps_completed=completed,
                steps_failed=failed,
                rollout_mode=plan.rollout_mode if plan else RolloutMode.IMMEDIATE,
                started_at=now,
                completed_at=now,
            )
            self._executions[change_id] = execution
        else:
            old = self._executions[change_id]
            updated = ChangeExecution(
                execution_id=old.execution_id,
                change_id=old.change_id,
                plan_id=old.plan_id,
                status=old.status,
                steps_total=old.steps_total,
                steps_completed=completed,
                steps_failed=failed,
                rollout_mode=old.rollout_mode,
                started_at=old.started_at,
                completed_at=now,
            )
            self._executions[change_id] = updated

    # ------------------------------------------------------------------
    # Pause / abort / rollback
    # ------------------------------------------------------------------

    def pause_change(self, change_id: str, *, reason: str = "") -> ChangeStatus:
        self._require_change(change_id)
        self._transition(change_id, ChangeStatus.PAUSED)
        _emit(self._events, "change_paused", {
            "change_id": change_id, "reason": reason,
        }, change_id)
        return ChangeStatus.PAUSED

    def resume_change(self, change_id: str) -> ChangeStatus:
        self._require_change(change_id)
        self._transition(change_id, ChangeStatus.IN_PROGRESS)
        _emit(self._events, "change_resumed", {"change_id": change_id}, change_id)
        return ChangeStatus.IN_PROGRESS

    def abort_change(self, change_id: str, *, reason: str = "") -> ChangeStatus:
        self._require_change(change_id)
        self._transition(change_id, ChangeStatus.ABORTED)
        _emit(self._events, "change_aborted", {
            "change_id": change_id, "reason": reason,
        }, change_id)
        return ChangeStatus.ABORTED

    def rollback_change(
        self,
        change_id: str,
        *,
        reason: str = "",
        rollback_steps: list[str] | None = None,
    ) -> RollbackPlan:
        self._require_change(change_id)
        now = _now_iso()

        rollback = RollbackPlan(
            rollback_id=stable_identifier("crbk", {"cid": change_id, "ts": now}),
            change_id=change_id,
            disposition=RollbackDisposition.TRIGGERED,
            rollback_steps=tuple(rollback_steps or []),
            reason=reason,
            triggered_at=now,
        )
        self._rollbacks[change_id] = rollback
        self._transition(change_id, ChangeStatus.ROLLED_BACK)

        _emit(self._events, "change_rolled_back", {
            "change_id": change_id,
            "reason": reason,
        }, change_id)
        return rollback

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    def complete_change(
        self,
        change_id: str,
        *,
        success: bool = True,
        improvement_observed: bool = False,
        improvement_pct: float = 0.0,
    ) -> ChangeOutcome:
        self._require_change(change_id)
        now = _now_iso()

        current = self._status[change_id]
        if current == ChangeStatus.IN_PROGRESS:
            self._transition(change_id, ChangeStatus.COMPLETED)
        elif current == ChangeStatus.PAUSED:
            # Allow completing from paused
            self._status[change_id] = ChangeStatus.COMPLETED
        else:
            raise RuntimeCoreInvariantError(
                "cannot complete change from current status"
            )

        exec_record = self._executions.get(change_id)
        exec_id = exec_record.execution_id if exec_record else change_id
        evidence_list = self._evidence.get(change_id, [])
        rollback = self._rollbacks.get(change_id)

        outcome = ChangeOutcome(
            outcome_id=stable_identifier("cout", {"cid": change_id, "ts": now}),
            change_id=change_id,
            execution_id=exec_id,
            status=ChangeStatus.COMPLETED if success else ChangeStatus.FAILED,
            success=success,
            improvement_observed=improvement_observed,
            improvement_pct=improvement_pct,
            rollback_disposition=rollback.disposition if rollback else RollbackDisposition.NOT_NEEDED,
            evidence_count=len(evidence_list),
            completed_at=now,
        )
        self._outcomes[change_id] = outcome

        _emit(self._events, "change_completed", {
            "change_id": change_id,
            "success": success,
            "improvement_observed": improvement_observed,
        }, change_id)
        return outcome

    # ------------------------------------------------------------------
    # Evidence collection
    # ------------------------------------------------------------------

    def collect_evidence(
        self,
        change_id: str,
        kind: ChangeEvidenceKind,
        *,
        metric_name: str = "",
        metric_value: float = 0.0,
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> ChangeEvidence:
        self._require_change(change_id)
        now = _now_iso()
        evidence = ChangeEvidence(
            evidence_id=stable_identifier("cevd", {"cid": change_id, "k": kind.value, "ts": now}),
            change_id=change_id,
            kind=kind,
            metric_name=metric_name,
            metric_value=metric_value,
            description=description,
            collected_at=now,
            metadata=metadata or {},
        )
        self._evidence.setdefault(change_id, []).append(evidence)

        _emit(self._events, "change_evidence_collected", {
            "change_id": change_id,
            "kind": kind.value,
        }, change_id)
        return evidence

    # ------------------------------------------------------------------
    # Impact assessment
    # ------------------------------------------------------------------

    def assess_change_impact(
        self,
        change_id: str,
        metric_name: str,
        baseline_value: float,
        current_value: float,
        *,
        confidence: float = 0.8,
        assessment_window_seconds: float = 3600.0,
    ) -> ChangeImpactAssessment:
        self._require_change(change_id)
        now = _now_iso()
        improvement = ((current_value - baseline_value) / abs(baseline_value) * 100) if baseline_value != 0 else 0.0

        assessment = ChangeImpactAssessment(
            assessment_id=stable_identifier("cias", {"cid": change_id, "m": metric_name, "ts": now}),
            change_id=change_id,
            metric_name=metric_name,
            baseline_value=baseline_value,
            current_value=current_value,
            improvement_pct=improvement,
            confidence=confidence,
            assessment_window_seconds=assessment_window_seconds,
            assessed_at=now,
        )
        self._impacts.append(assessment)

        _emit(self._events, "change_impact_assessed", {
            "change_id": change_id,
            "metric_name": metric_name,
            "improvement_pct": improvement,
        }, change_id)
        return assessment

    # ------------------------------------------------------------------
    # Submit for approval
    # ------------------------------------------------------------------

    def submit_for_approval(self, change_id: str) -> ChangeStatus:
        """Move a DRAFT change to PENDING_APPROVAL."""
        self._require_change(change_id)
        self._transition(change_id, ChangeStatus.PENDING_APPROVAL)
        _emit(self._events, "change_submitted_for_approval", {
            "change_id": change_id,
        }, change_id)
        return ChangeStatus.PENDING_APPROVAL

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_execution(self, change_id: str) -> ChangeExecution | None:
        return self._executions.get(change_id)

    def get_outcome(self, change_id: str) -> ChangeOutcome | None:
        return self._outcomes.get(change_id)

    def get_evidence(self, change_id: str) -> tuple[ChangeEvidence, ...]:
        return tuple(self._evidence.get(change_id, []))

    def get_rollback(self, change_id: str) -> RollbackPlan | None:
        return self._rollbacks.get(change_id)

    def get_steps(self, change_id: str) -> tuple[ChangeStep, ...]:
        return tuple(
            s for s in self._steps.values() if s.change_id == change_id
        )

    @property
    def change_count(self) -> int:
        return len(self._changes)

    @property
    def plan_count(self) -> int:
        return len(self._plans)

    @property
    def outcome_count(self) -> int:
        return len(self._outcomes)

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._changes):
            parts.append(f"chg:{k}:{self._changes[k].status.value}")
        for k in sorted(self._plans):
            parts.append(f"plan:{k}:{self._plans[k].change_id}")
        for k in sorted(self._steps):
            parts.append(f"step:{k}:{self._steps[k].status.value}")
        for k in sorted(self._executions):
            parts.append(f"exec:{k}:{self._executions[k].status.value}")
        for k in sorted(self._approvals):
            parts.append(f"appr:{k}:{len(self._approvals[k])}")
        for k in sorted(self._evidence):
            parts.append(f"evid:{k}:{len(self._evidence[k])}")
        for k in sorted(self._rollbacks):
            parts.append(f"rbk:{k}:{self._rollbacks[k].disposition.value}")
        for k in sorted(self._outcomes):
            parts.append(f"out:{k}:{self._outcomes[k].status.value}")
        for k in sorted(self._status):
            parts.append(f"st:{k}:{self._status[k].value}")
        parts.append(f"impacts={len(self._impacts)}")
        digest = sha256("|".join(parts).encode()).hexdigest()
        return digest

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_change(self, change_id: str) -> ChangeRequest:
        change = self._changes.get(change_id)
        if change is None:
            raise RuntimeCoreInvariantError("change not found")
        return change

    def _transition(self, change_id: str, new_status: ChangeStatus) -> None:
        current = self._status.get(change_id)
        if current is None:
            raise RuntimeCoreInvariantError("change not found")
        valid = _VALID_TRANSITIONS.get(current, set())
        if new_status not in valid:
            raise RuntimeCoreInvariantError(
                f"invalid transition for '{change_id}': {current.value} → {new_status.value}"
            )
        self._status[change_id] = new_status
