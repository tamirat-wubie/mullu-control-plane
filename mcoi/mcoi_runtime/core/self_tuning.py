"""Purpose: self-tuning runtime engine.
Governance scope: registering learning signals, proposing improvements,
    approving/rejecting/deferring proposals, applying parameter adjustments,
    policy tunings, execution tunings, rolling back improvements, assessing
    effectiveness, detecting violations, and producing immutable snapshots.
Dependencies: self_tuning contracts, event_spine, core invariants.
Invariants:
  - LOW risk auto-applies; MEDIUM+ requires approval.
  - CONSTITUTIONAL scope is always treated as CRITICAL risk.
  - Terminal-state proposals cannot transition further.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.self_tuning import (
    ApprovalDisposition,
    ExecutionTuningRecord,
    ImprovementAssessment,
    ImprovementClosureReport,
    ImprovementDecision,
    ImprovementKind,
    ImprovementProposal,
    ImprovementRiskLevel,
    ImprovementScope,
    ImprovementSnapshot,
    ImprovementStatus,
    ImprovementViolation,
    LearningSignal,
    LearningSignalKind,
    ParameterAdjustment,
    PolicyTuningRecord,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


_PROPOSAL_TERMINAL = frozenset({
    ImprovementStatus.APPLIED,
    ImprovementStatus.REJECTED,
    ImprovementStatus.ROLLED_BACK,
})


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-stun", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class SelfTuningEngine:
    """Engine for self-tuning / autonomous improvement runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._signals: dict[str, LearningSignal] = {}
        self._proposals: dict[str, ImprovementProposal] = {}
        self._adjustments: dict[str, ParameterAdjustment] = {}
        self._policy_tunings: dict[str, PolicyTuningRecord] = {}
        self._execution_tunings: dict[str, ExecutionTuningRecord] = {}
        self._decisions: dict[str, ImprovementDecision] = {}
        self._violations: dict[str, ImprovementViolation] = {}

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def signal_count(self) -> int:
        return len(self._signals)

    @property
    def proposal_count(self) -> int:
        return len(self._proposals)

    @property
    def adjustment_count(self) -> int:
        return len(self._adjustments)

    @property
    def policy_tuning_count(self) -> int:
        return len(self._policy_tunings)

    @property
    def execution_tuning_count(self) -> int:
        return len(self._execution_tunings)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Learning Signals
    # ------------------------------------------------------------------

    def register_learning_signal(
        self,
        signal_id: str,
        tenant_id: str,
        kind: LearningSignalKind,
        source_runtime: str,
        description: str,
        occurrence_count: int = 1,
    ) -> LearningSignal:
        """Register a learning signal."""
        if signal_id in self._signals:
            raise RuntimeCoreInvariantError(f"Duplicate signal_id: {signal_id}")
        now = self._now()
        sig = LearningSignal(
            signal_id=signal_id,
            tenant_id=tenant_id,
            kind=kind,
            source_runtime=source_runtime,
            description=description,
            occurrence_count=occurrence_count,
            first_seen_at=now,
            last_seen_at=now,
        )
        self._signals[signal_id] = sig
        _emit(self._events, "learning_signal_registered", {
            "signal_id": signal_id, "kind": kind.value,
        }, signal_id, self._now())
        return sig

    def get_signal(self, signal_id: str) -> LearningSignal:
        s = self._signals.get(signal_id)
        if s is None:
            raise RuntimeCoreInvariantError(f"Unknown signal_id: {signal_id}")
        return s

    def signals_for_tenant(self, tenant_id: str) -> tuple[LearningSignal, ...]:
        return tuple(s for s in self._signals.values() if s.tenant_id == tenant_id)

    def signals_by_kind(self, tenant_id: str, kind: LearningSignalKind) -> tuple[LearningSignal, ...]:
        return tuple(
            s for s in self._signals.values()
            if s.tenant_id == tenant_id and s.kind == kind
        )

    # ------------------------------------------------------------------
    # Proposals
    # ------------------------------------------------------------------

    def propose_improvement(
        self,
        proposal_id: str,
        tenant_id: str,
        signal_ref: str,
        kind: ImprovementKind,
        scope: ImprovementScope,
        risk_level: ImprovementRiskLevel,
        description: str,
        justification: str,
    ) -> ImprovementProposal:
        """Propose an improvement. LOW risk auto-applies; CONSTITUTIONAL always CRITICAL."""
        if proposal_id in self._proposals:
            raise RuntimeCoreInvariantError(f"Duplicate proposal_id: {proposal_id}")
        now = self._now()

        # CONSTITUTIONAL scope is always CRITICAL
        if scope == ImprovementScope.CONSTITUTIONAL:
            risk_level = ImprovementRiskLevel.CRITICAL

        # Determine initial status based on risk
        if risk_level == ImprovementRiskLevel.LOW:
            status = ImprovementStatus.APPLIED
        else:
            status = ImprovementStatus.PROPOSED

        prop = ImprovementProposal(
            proposal_id=proposal_id,
            tenant_id=tenant_id,
            signal_ref=signal_ref,
            kind=kind,
            scope=scope,
            risk_level=risk_level,
            status=status,
            description=description,
            justification=justification,
            created_at=now,
        )
        self._proposals[proposal_id] = prop

        # Auto-apply decision for LOW risk
        if risk_level == ImprovementRiskLevel.LOW:
            dec_id = stable_identifier("dec-stun", {"proposal": proposal_id, "auto": "true"})
            dec = ImprovementDecision(
                decision_id=dec_id,
                tenant_id=tenant_id,
                proposal_ref=proposal_id,
                disposition=ApprovalDisposition.AUTO_APPLIED,
                decided_by="self_tuning_engine",
                reason="LOW risk auto-applied",
                decided_at=now,
            )
            self._decisions[dec_id] = dec

        _emit(self._events, "improvement_proposed", {
            "proposal_id": proposal_id, "risk_level": risk_level.value,
            "status": status.value,
        }, proposal_id, self._now())
        return prop

    def get_proposal(self, proposal_id: str) -> ImprovementProposal:
        p = self._proposals.get(proposal_id)
        if p is None:
            raise RuntimeCoreInvariantError(f"Unknown proposal_id: {proposal_id}")
        return p

    def proposals_for_tenant(self, tenant_id: str) -> tuple[ImprovementProposal, ...]:
        return tuple(p for p in self._proposals.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Approval / Rejection / Deferral
    # ------------------------------------------------------------------

    def _transition_proposal(
        self,
        proposal_id: str,
        new_status: ImprovementStatus,
        valid_from: frozenset[ImprovementStatus],
    ) -> ImprovementProposal:
        old = self.get_proposal(proposal_id)
        if old.status in _PROPOSAL_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Proposal {proposal_id} is in terminal state {old.status.value}"
            )
        if old.status not in valid_from:
            raise RuntimeCoreInvariantError(
                f"Cannot transition from {old.status.value} to {new_status.value}"
            )
        updated = ImprovementProposal(
            proposal_id=old.proposal_id,
            tenant_id=old.tenant_id,
            signal_ref=old.signal_ref,
            kind=old.kind,
            scope=old.scope,
            risk_level=old.risk_level,
            status=new_status,
            description=old.description,
            justification=old.justification,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._proposals[proposal_id] = updated
        return updated

    def approve_improvement(self, proposal_id: str) -> ImprovementProposal:
        """Approve a PROPOSED or DEFERRED proposal."""
        updated = self._transition_proposal(
            proposal_id,
            ImprovementStatus.APPROVED,
            frozenset({ImprovementStatus.PROPOSED, ImprovementStatus.DEFERRED}),
        )
        now = self._now()
        dec_id = stable_identifier("dec-stun", {"proposal": proposal_id, "approve": "true"})
        dec = ImprovementDecision(
            decision_id=dec_id,
            tenant_id=updated.tenant_id,
            proposal_ref=proposal_id,
            disposition=ApprovalDisposition.APPROVED,
            decided_by="approver",
            reason="Approved",
            decided_at=now,
        )
        self._decisions[dec_id] = dec
        _emit(self._events, "improvement_approved", {
            "proposal_id": proposal_id,
        }, proposal_id, self._now())
        return updated

    def reject_improvement(self, proposal_id: str) -> ImprovementProposal:
        """Reject a PROPOSED or DEFERRED proposal."""
        updated = self._transition_proposal(
            proposal_id,
            ImprovementStatus.REJECTED,
            frozenset({ImprovementStatus.PROPOSED, ImprovementStatus.DEFERRED}),
        )
        now = self._now()
        dec_id = stable_identifier("dec-stun", {"proposal": proposal_id, "reject": "true"})
        dec = ImprovementDecision(
            decision_id=dec_id,
            tenant_id=updated.tenant_id,
            proposal_ref=proposal_id,
            disposition=ApprovalDisposition.REJECTED,
            decided_by="approver",
            reason="Rejected",
            decided_at=now,
        )
        self._decisions[dec_id] = dec
        _emit(self._events, "improvement_rejected", {
            "proposal_id": proposal_id,
        }, proposal_id, self._now())
        return updated

    def defer_improvement(self, proposal_id: str) -> ImprovementProposal:
        """Defer a PROPOSED proposal."""
        updated = self._transition_proposal(
            proposal_id,
            ImprovementStatus.DEFERRED,
            frozenset({ImprovementStatus.PROPOSED}),
        )
        now = self._now()
        dec_id = stable_identifier("dec-stun", {"proposal": proposal_id, "defer": "true"})
        dec = ImprovementDecision(
            decision_id=dec_id,
            tenant_id=updated.tenant_id,
            proposal_ref=proposal_id,
            disposition=ApprovalDisposition.DEFERRED,
            decided_by="approver",
            reason="Deferred",
            decided_at=now,
        )
        self._decisions[dec_id] = dec
        _emit(self._events, "improvement_deferred", {
            "proposal_id": proposal_id,
        }, proposal_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Apply adjustments / tunings
    # ------------------------------------------------------------------

    def _validate_proposal_applicable(self, proposal_ref: str) -> ImprovementProposal:
        """Validate a proposal is in APPROVED or APPLIED (auto-applied LOW risk) state."""
        prop = self.get_proposal(proposal_ref)
        if prop.status not in (ImprovementStatus.APPROVED, ImprovementStatus.APPLIED):
            raise RuntimeCoreInvariantError(
                f"Proposal {proposal_ref} must be APPROVED or APPLIED (auto-applied) to apply changes, got {prop.status.value}"
            )
        return prop

    def _mark_proposal_applied(self, proposal_ref: str) -> None:
        """Mark proposal as APPLIED if not already."""
        prop = self._proposals[proposal_ref]
        if prop.status != ImprovementStatus.APPLIED:
            updated = ImprovementProposal(
                proposal_id=prop.proposal_id,
                tenant_id=prop.tenant_id,
                signal_ref=prop.signal_ref,
                kind=prop.kind,
                scope=prop.scope,
                risk_level=prop.risk_level,
                status=ImprovementStatus.APPLIED,
                description=prop.description,
                justification=prop.justification,
                created_at=prop.created_at,
                metadata=prop.metadata,
            )
            self._proposals[proposal_ref] = updated

    def apply_parameter_adjustment(
        self,
        adj_id: str,
        tenant_id: str,
        proposal_ref: str,
        target_component: str,
        parameter_name: str,
        old_value: str,
        proposed_value: str,
    ) -> ParameterAdjustment:
        """Apply a parameter adjustment from an approved proposal."""
        if adj_id in self._adjustments:
            raise RuntimeCoreInvariantError(f"Duplicate adjustment_id: {adj_id}")
        self._validate_proposal_applicable(proposal_ref)
        now = self._now()
        adj = ParameterAdjustment(
            adjustment_id=adj_id,
            tenant_id=tenant_id,
            proposal_ref=proposal_ref,
            target_component=target_component,
            parameter_name=parameter_name,
            old_value=old_value,
            proposed_value=proposed_value,
            applied_at=now,
        )
        self._adjustments[adj_id] = adj
        self._mark_proposal_applied(proposal_ref)
        _emit(self._events, "parameter_adjustment_applied", {
            "adjustment_id": adj_id, "proposal_ref": proposal_ref,
        }, adj_id, self._now())
        return adj

    def apply_policy_tuning(
        self,
        tuning_id: str,
        tenant_id: str,
        proposal_ref: str,
        rule_target: str,
        previous_setting: str,
        proposed_setting: str,
        blast_radius: ImprovementScope,
    ) -> PolicyTuningRecord:
        """Apply a policy tuning from an approved proposal."""
        if tuning_id in self._policy_tunings:
            raise RuntimeCoreInvariantError(f"Duplicate tuning_id: {tuning_id}")
        self._validate_proposal_applicable(proposal_ref)
        now = self._now()
        pt = PolicyTuningRecord(
            tuning_id=tuning_id,
            tenant_id=tenant_id,
            proposal_ref=proposal_ref,
            rule_target=rule_target,
            previous_setting=previous_setting,
            proposed_setting=proposed_setting,
            blast_radius=blast_radius,
            created_at=now,
        )
        self._policy_tunings[tuning_id] = pt
        self._mark_proposal_applied(proposal_ref)
        _emit(self._events, "policy_tuning_applied", {
            "tuning_id": tuning_id, "proposal_ref": proposal_ref,
        }, tuning_id, self._now())
        return pt

    def apply_execution_tuning(
        self,
        tuning_id: str,
        tenant_id: str,
        proposal_ref: str,
        target_runtime: str,
        change_type: str,
        expected_gain: str,
        expected_risk: str,
    ) -> ExecutionTuningRecord:
        """Apply an execution tuning from an approved proposal."""
        if tuning_id in self._execution_tunings:
            raise RuntimeCoreInvariantError(f"Duplicate tuning_id: {tuning_id}")
        self._validate_proposal_applicable(proposal_ref)
        now = self._now()
        et = ExecutionTuningRecord(
            tuning_id=tuning_id,
            tenant_id=tenant_id,
            proposal_ref=proposal_ref,
            target_runtime=target_runtime,
            change_type=change_type,
            expected_gain=expected_gain,
            expected_risk=expected_risk,
            created_at=now,
        )
        self._execution_tunings[tuning_id] = et
        self._mark_proposal_applied(proposal_ref)
        _emit(self._events, "execution_tuning_applied", {
            "tuning_id": tuning_id, "proposal_ref": proposal_ref,
        }, tuning_id, self._now())
        return et

    # ------------------------------------------------------------------
    # Rollback
    # ------------------------------------------------------------------

    def rollback_improvement(self, proposal_id: str) -> ImprovementProposal:
        """Roll back an APPLIED improvement."""
        old = self.get_proposal(proposal_id)
        if old.status != ImprovementStatus.APPLIED:
            raise RuntimeCoreInvariantError(
                f"Can only rollback APPLIED proposals, got {old.status.value}"
            )
        updated = ImprovementProposal(
            proposal_id=old.proposal_id,
            tenant_id=old.tenant_id,
            signal_ref=old.signal_ref,
            kind=old.kind,
            scope=old.scope,
            risk_level=old.risk_level,
            status=ImprovementStatus.ROLLED_BACK,
            description=old.description,
            justification=old.justification,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._proposals[proposal_id] = updated

        now = self._now()
        dec_id = stable_identifier("dec-stun", {"proposal": proposal_id, "rollback": "true"})
        dec = ImprovementDecision(
            decision_id=dec_id,
            tenant_id=updated.tenant_id,
            proposal_ref=proposal_id,
            disposition=ApprovalDisposition.REJECTED,
            decided_by="self_tuning_engine",
            reason=f"Rolled back improvement {proposal_id}",
            decided_at=now,
        )
        self._decisions[dec_id] = dec
        _emit(self._events, "improvement_rolled_back", {
            "proposal_id": proposal_id,
        }, proposal_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Assessment
    # ------------------------------------------------------------------

    def improvement_assessment(
        self,
        assessment_id: str,
        tenant_id: str,
    ) -> ImprovementAssessment:
        """Produce an improvement assessment for a tenant."""
        now = self._now()
        tenant_proposals = [p for p in self._proposals.values() if p.tenant_id == tenant_id]
        tenant_signals = [s for s in self._signals.values() if s.tenant_id == tenant_id]
        applied = sum(1 for p in tenant_proposals if p.status == ImprovementStatus.APPLIED)
        rolled_back = sum(1 for p in tenant_proposals if p.status == ImprovementStatus.ROLLED_BACK)
        total = applied + rolled_back
        rate = applied / total if total > 0 else 1.0

        asm = ImprovementAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            total_signals=len(tenant_signals),
            total_proposals=len(tenant_proposals),
            total_applied=applied,
            total_rolled_back=rolled_back,
            improvement_rate=rate,
            assessed_at=now,
        )
        _emit(self._events, "improvement_assessed", {
            "assessment_id": assessment_id, "improvement_rate": rate,
        }, assessment_id, self._now())
        return asm

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def improvement_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> ImprovementSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = ImprovementSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_signals=sum(1 for s in self._signals.values() if s.tenant_id == tenant_id),
            total_proposals=sum(1 for p in self._proposals.values() if p.tenant_id == tenant_id),
            total_adjustments=sum(1 for a in self._adjustments.values() if a.tenant_id == tenant_id),
            total_policy_tunings=sum(1 for pt in self._policy_tunings.values() if pt.tenant_id == tenant_id),
            total_execution_tunings=sum(1 for et in self._execution_tunings.values() if et.tenant_id == tenant_id),
            total_decisions=sum(1 for d in self._decisions.values() if d.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_improvement_violations(self, tenant_id: str) -> tuple[ImprovementViolation, ...]:
        """Detect improvement violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[ImprovementViolation] = []

        tenant_proposals = [p for p in self._proposals.values() if p.tenant_id == tenant_id]

        # 1) Unapproved high-risk: APPLIED proposal with HIGH/CRITICAL risk
        #    without an APPROVED decision
        for prop in tenant_proposals:
            if (
                prop.risk_level in (ImprovementRiskLevel.HIGH, ImprovementRiskLevel.CRITICAL)
                and prop.status == ImprovementStatus.APPLIED
            ):
                has_approval = any(
                    d.proposal_ref == prop.proposal_id
                    and d.disposition == ApprovalDisposition.APPROVED
                    for d in self._decisions.values()
                )
                if not has_approval:
                    vid = stable_identifier("viol-stun", {
                        "prop": prop.proposal_id, "op": "unapproved_high_risk",
                    })
                    if vid not in self._violations:
                        v = ImprovementViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="unapproved_high_risk",
                            reason=f"Proposal {prop.proposal_id} is {prop.risk_level.value} risk and APPLIED without APPROVED decision",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2) Conflicting proposals: two PROPOSED/APPROVED proposals for same target_component
        #    (detected via adjustments sharing target_component)
        target_proposals: dict[str, list[str]] = {}
        for adj in self._adjustments.values():
            if adj.tenant_id == tenant_id:
                prop = self._proposals.get(adj.proposal_ref)
                if prop and prop.status in (ImprovementStatus.PROPOSED, ImprovementStatus.APPROVED):
                    target_proposals.setdefault(adj.target_component, []).append(prop.proposal_id)
        for target, prop_ids in target_proposals.items():
            if len(prop_ids) > 1:
                vid = stable_identifier("viol-stun", {
                    "target": target, "op": "conflicting_proposals",
                })
                if vid not in self._violations:
                    v = ImprovementViolation(
                        violation_id=vid,
                        tenant_id=tenant_id,
                        operation="conflicting_proposals",
                        reason=f"Multiple active proposals for target {target}: {', '.join(sorted(prop_ids))}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3) Excessive rollbacks: more rollbacks than applied
        applied = sum(1 for p in tenant_proposals if p.status == ImprovementStatus.APPLIED)
        rolled_back = sum(1 for p in tenant_proposals if p.status == ImprovementStatus.ROLLED_BACK)
        if rolled_back > applied:
            vid = stable_identifier("viol-stun", {
                "tenant": tenant_id, "op": "excessive_rollbacks",
            })
            if vid not in self._violations:
                v = ImprovementViolation(
                    violation_id=vid,
                    tenant_id=tenant_id,
                    operation="excessive_rollbacks",
                    reason=f"More rollbacks ({rolled_back}) than applied ({applied})",
                    detected_at=now,
                )
                self._violations[vid] = v
                new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "signals": self._signals,
            "proposals": self._proposals,
            "adjustments": self._adjustments,
            "policy_tunings": self._policy_tunings,
            "execution_tunings": self._execution_tunings,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
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

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (sorted keys, no timestamps)."""
        parts = [
            f"adjustments={self.adjustment_count}",
            f"decisions={self.decision_count}",
            f"execution_tunings={self.execution_tuning_count}",
            f"policy_tunings={self.policy_tuning_count}",
            f"proposals={self.proposal_count}",
            f"signals={self.signal_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
