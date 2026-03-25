"""Purpose: product operations / release / lifecycle runtime engine.
Governance scope: registering versions/releases, evaluating gates, promoting
    across environments, rolling back, tracking lifecycle milestones,
    detecting violations, producing immutable snapshots.
Dependencies: product_ops contracts, event_spine, core invariants.
Invariants:
  - Duplicate IDs raise.
  - Completed/failed/rolled-back releases cannot be modified.
  - All gates must pass before promotion.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.product_ops import (
    LifecycleMilestone,
    LifecycleStatus,
    ProductVersionRecord,
    PromotionDisposition,
    PromotionRecord,
    ReleaseAssessment,
    ReleaseClosureReport,
    ReleaseGate,
    ReleaseKind,
    ReleaseRecord,
    ReleaseRiskLevel,
    ReleaseSnapshot,
    ReleaseStatus,
    ReleaseViolation,
    RollbackRecord,
    RollbackStatus,
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
        event_id=stable_identifier("evt-pops", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_RELEASE_TERMINAL = frozenset({ReleaseStatus.COMPLETED, ReleaseStatus.FAILED, ReleaseStatus.ROLLED_BACK})
_LIFECYCLE_TERMINAL = frozenset({LifecycleStatus.RETIRED})
_ROLLBACK_TERMINAL = frozenset({RollbackStatus.COMPLETED, RollbackStatus.FAILED})


class ProductOpsEngine:
    """Product operations / release / lifecycle engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._versions: dict[str, ProductVersionRecord] = {}
        self._releases: dict[str, ReleaseRecord] = {}
        self._gates: dict[str, ReleaseGate] = {}
        self._promotions: dict[str, PromotionRecord] = {}
        self._rollbacks: dict[str, RollbackRecord] = {}
        self._milestones: dict[str, LifecycleMilestone] = {}
        self._assessments: dict[str, ReleaseAssessment] = {}
        self._violations: dict[str, ReleaseViolation] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def version_count(self) -> int:
        return len(self._versions)

    @property
    def release_count(self) -> int:
        return len(self._releases)

    @property
    def gate_count(self) -> int:
        return len(self._gates)

    @property
    def promotion_count(self) -> int:
        return len(self._promotions)

    @property
    def rollback_count(self) -> int:
        return len(self._rollbacks)

    @property
    def milestone_count(self) -> int:
        return len(self._milestones)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    def register_version(
        self,
        version_id: str,
        product_id: str,
        tenant_id: str,
        version_label: str,
        lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE,
    ) -> ProductVersionRecord:
        if version_id in self._versions:
            raise RuntimeCoreInvariantError(f"version already registered: {version_id}")
        now = _now_iso()
        record = ProductVersionRecord(
            version_id=version_id,
            product_id=product_id,
            tenant_id=tenant_id,
            version_label=version_label,
            lifecycle_status=lifecycle_status,
            created_at=now,
        )
        self._versions[version_id] = record
        _emit(self._events, "register_version", {"version_id": version_id, "product_id": product_id}, version_id)
        return record

    def get_version(self, version_id: str) -> ProductVersionRecord:
        if version_id not in self._versions:
            raise RuntimeCoreInvariantError(f"unknown version: {version_id}")
        return self._versions[version_id]

    def deprecate_version(self, version_id: str, reason: str = "deprecated") -> LifecycleMilestone:
        return self._transition_lifecycle(version_id, LifecycleStatus.DEPRECATED, reason)

    def retire_version(self, version_id: str, reason: str = "retired") -> LifecycleMilestone:
        return self._transition_lifecycle(version_id, LifecycleStatus.RETIRED, reason)

    def end_of_life_version(self, version_id: str, reason: str = "end_of_life") -> LifecycleMilestone:
        return self._transition_lifecycle(version_id, LifecycleStatus.END_OF_LIFE, reason)

    def versions_for_product(self, product_id: str) -> tuple[ProductVersionRecord, ...]:
        return tuple(v for v in self._versions.values() if v.product_id == product_id)

    def versions_for_tenant(self, tenant_id: str) -> tuple[ProductVersionRecord, ...]:
        return tuple(v for v in self._versions.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Releases
    # ------------------------------------------------------------------

    def create_release(
        self,
        release_id: str,
        version_id: str,
        tenant_id: str,
        kind: ReleaseKind = ReleaseKind.MINOR,
        target_environment: str = "staging",
    ) -> ReleaseRecord:
        if release_id in self._releases:
            raise RuntimeCoreInvariantError(f"release already exists: {release_id}")
        if version_id not in self._versions:
            raise RuntimeCoreInvariantError(f"unknown version: {version_id}")
        ver = self._versions[version_id]
        if ver.lifecycle_status in _LIFECYCLE_TERMINAL:
            raise RuntimeCoreInvariantError(f"version is retired: {version_id}")
        now = _now_iso()
        record = ReleaseRecord(
            release_id=release_id,
            version_id=version_id,
            tenant_id=tenant_id,
            kind=kind,
            status=ReleaseStatus.DRAFT,
            target_environment=target_environment,
            gate_count=0,
            gates_passed=0,
            created_at=now,
        )
        self._releases[release_id] = record
        _emit(self._events, "create_release", {"release_id": release_id, "version_id": version_id}, release_id)
        return record

    def get_release(self, release_id: str) -> ReleaseRecord:
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        return self._releases[release_id]

    def mark_release_ready(self, release_id: str) -> ReleaseRecord:
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        old = self._releases[release_id]
        if old.status in _RELEASE_TERMINAL:
            raise RuntimeCoreInvariantError(f"release is in terminal state: {old.status.value}")
        updated = ReleaseRecord(
            release_id=old.release_id, version_id=old.version_id, tenant_id=old.tenant_id,
            kind=old.kind, status=ReleaseStatus.READY, target_environment=old.target_environment,
            gate_count=old.gate_count, gates_passed=old.gates_passed, created_at=old.created_at,
        )
        self._releases[release_id] = updated
        _emit(self._events, "mark_release_ready", {"release_id": release_id}, release_id)
        return updated

    def start_release(self, release_id: str) -> ReleaseRecord:
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        old = self._releases[release_id]
        if old.status in _RELEASE_TERMINAL:
            raise RuntimeCoreInvariantError(f"release is in terminal state: {old.status.value}")
        updated = ReleaseRecord(
            release_id=old.release_id, version_id=old.version_id, tenant_id=old.tenant_id,
            kind=old.kind, status=ReleaseStatus.IN_PROGRESS, target_environment=old.target_environment,
            gate_count=old.gate_count, gates_passed=old.gates_passed, created_at=old.created_at,
        )
        self._releases[release_id] = updated
        _emit(self._events, "start_release", {"release_id": release_id}, release_id)
        return updated

    def complete_release(self, release_id: str) -> ReleaseRecord:
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        old = self._releases[release_id]
        if old.status in _RELEASE_TERMINAL:
            raise RuntimeCoreInvariantError(f"release is in terminal state: {old.status.value}")
        updated = ReleaseRecord(
            release_id=old.release_id, version_id=old.version_id, tenant_id=old.tenant_id,
            kind=old.kind, status=ReleaseStatus.COMPLETED, target_environment=old.target_environment,
            gate_count=old.gate_count, gates_passed=old.gates_passed, created_at=old.created_at,
        )
        self._releases[release_id] = updated
        _emit(self._events, "complete_release", {"release_id": release_id}, release_id)
        return updated

    def fail_release(self, release_id: str) -> ReleaseRecord:
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        old = self._releases[release_id]
        if old.status in _RELEASE_TERMINAL:
            raise RuntimeCoreInvariantError(f"release is in terminal state: {old.status.value}")
        updated = ReleaseRecord(
            release_id=old.release_id, version_id=old.version_id, tenant_id=old.tenant_id,
            kind=old.kind, status=ReleaseStatus.FAILED, target_environment=old.target_environment,
            gate_count=old.gate_count, gates_passed=old.gates_passed, created_at=old.created_at,
        )
        self._releases[release_id] = updated
        _emit(self._events, "fail_release", {"release_id": release_id}, release_id)
        return updated

    def releases_for_version(self, version_id: str) -> tuple[ReleaseRecord, ...]:
        return tuple(r for r in self._releases.values() if r.version_id == version_id)

    def releases_for_tenant(self, tenant_id: str) -> tuple[ReleaseRecord, ...]:
        return tuple(r for r in self._releases.values() if r.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Gates
    # ------------------------------------------------------------------

    def evaluate_gate(
        self,
        gate_id: str,
        release_id: str,
        tenant_id: str,
        gate_name: str,
        passed: bool,
        reason: str = "",
    ) -> ReleaseGate:
        if gate_id in self._gates:
            raise RuntimeCoreInvariantError(f"gate already evaluated: {gate_id}")
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        rel = self._releases[release_id]
        if rel.status in _RELEASE_TERMINAL:
            raise RuntimeCoreInvariantError(f"release is in terminal state: {rel.status.value}")
        now = _now_iso()
        gate = ReleaseGate(
            gate_id=gate_id,
            release_id=release_id,
            tenant_id=tenant_id,
            gate_name=gate_name,
            passed=passed,
            reason=reason if reason else ("passed" if passed else "failed"),
            evaluated_at=now,
        )
        self._gates[gate_id] = gate
        # Update release gate counts
        updated = ReleaseRecord(
            release_id=rel.release_id, version_id=rel.version_id, tenant_id=rel.tenant_id,
            kind=rel.kind, status=rel.status, target_environment=rel.target_environment,
            gate_count=rel.gate_count + 1,
            gates_passed=rel.gates_passed + (1 if passed else 0),
            created_at=rel.created_at,
        )
        self._releases[release_id] = updated
        _emit(self._events, "evaluate_gate", {"gate_id": gate_id, "release_id": release_id, "passed": passed}, gate_id)
        return gate

    def gates_for_release(self, release_id: str) -> tuple[ReleaseGate, ...]:
        return tuple(g for g in self._gates.values() if g.release_id == release_id)

    def all_gates_passed(self, release_id: str) -> bool:
        """Check if all gates for a release have passed."""
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        rel = self._releases[release_id]
        return rel.gate_count > 0 and rel.gates_passed == rel.gate_count

    # ------------------------------------------------------------------
    # Promotions
    # ------------------------------------------------------------------

    def promote_release(
        self,
        promotion_id: str,
        release_id: str,
        tenant_id: str,
        from_environment: str,
        to_environment: str,
    ) -> PromotionRecord:
        if promotion_id in self._promotions:
            raise RuntimeCoreInvariantError(f"promotion already exists: {promotion_id}")
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        rel = self._releases[release_id]
        if rel.status in _RELEASE_TERMINAL:
            raise RuntimeCoreInvariantError(f"release is in terminal state: {rel.status.value}")
        now = _now_iso()

        # Check if all gates passed
        if not self.all_gates_passed(release_id):
            # Block promotion
            promotion = PromotionRecord(
                promotion_id=promotion_id, release_id=release_id, tenant_id=tenant_id,
                from_environment=from_environment, to_environment=to_environment,
                disposition=PromotionDisposition.BLOCKED, decided_at=now,
            )
            self._promotions[promotion_id] = promotion
            _emit(self._events, "promote_release_blocked", {"promotion_id": promotion_id, "release_id": release_id}, promotion_id)
            return promotion

        promotion = PromotionRecord(
            promotion_id=promotion_id, release_id=release_id, tenant_id=tenant_id,
            from_environment=from_environment, to_environment=to_environment,
            disposition=PromotionDisposition.PROMOTED, decided_at=now,
        )
        self._promotions[promotion_id] = promotion
        # Update release target environment
        updated = ReleaseRecord(
            release_id=rel.release_id, version_id=rel.version_id, tenant_id=rel.tenant_id,
            kind=rel.kind, status=rel.status, target_environment=to_environment,
            gate_count=rel.gate_count, gates_passed=rel.gates_passed, created_at=rel.created_at,
        )
        self._releases[release_id] = updated
        _emit(self._events, "promote_release", {"promotion_id": promotion_id, "release_id": release_id, "to": to_environment}, promotion_id)
        return promotion

    def promotions_for_release(self, release_id: str) -> tuple[PromotionRecord, ...]:
        return tuple(p for p in self._promotions.values() if p.release_id == release_id)

    # ------------------------------------------------------------------
    # Rollbacks
    # ------------------------------------------------------------------

    def rollback_release(
        self,
        rollback_id: str,
        release_id: str,
        tenant_id: str,
        reason: str,
    ) -> RollbackRecord:
        if rollback_id in self._rollbacks:
            raise RuntimeCoreInvariantError(f"rollback already exists: {rollback_id}")
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        rel = self._releases[release_id]
        if rel.status in _RELEASE_TERMINAL:
            raise RuntimeCoreInvariantError(f"release is in terminal state: {rel.status.value}")
        now = _now_iso()
        rollback = RollbackRecord(
            rollback_id=rollback_id, release_id=release_id, tenant_id=tenant_id,
            reason=reason, status=RollbackStatus.INITIATED, initiated_at=now,
        )
        self._rollbacks[rollback_id] = rollback
        # Mark release as rolled back
        updated = ReleaseRecord(
            release_id=rel.release_id, version_id=rel.version_id, tenant_id=rel.tenant_id,
            kind=rel.kind, status=ReleaseStatus.ROLLED_BACK, target_environment=rel.target_environment,
            gate_count=rel.gate_count, gates_passed=rel.gates_passed, created_at=rel.created_at,
        )
        self._releases[release_id] = updated
        _emit(self._events, "rollback_release", {"rollback_id": rollback_id, "release_id": release_id}, rollback_id)
        return rollback

    def complete_rollback(self, rollback_id: str) -> RollbackRecord:
        if rollback_id not in self._rollbacks:
            raise RuntimeCoreInvariantError(f"unknown rollback: {rollback_id}")
        old = self._rollbacks[rollback_id]
        if old.status in _ROLLBACK_TERMINAL:
            raise RuntimeCoreInvariantError(f"rollback is in terminal state: {old.status.value}")
        updated = RollbackRecord(
            rollback_id=old.rollback_id, release_id=old.release_id, tenant_id=old.tenant_id,
            reason=old.reason, status=RollbackStatus.COMPLETED, initiated_at=old.initiated_at,
        )
        self._rollbacks[rollback_id] = updated
        _emit(self._events, "complete_rollback", {"rollback_id": rollback_id}, rollback_id)
        return updated

    def fail_rollback(self, rollback_id: str) -> RollbackRecord:
        if rollback_id not in self._rollbacks:
            raise RuntimeCoreInvariantError(f"unknown rollback: {rollback_id}")
        old = self._rollbacks[rollback_id]
        if old.status in _ROLLBACK_TERMINAL:
            raise RuntimeCoreInvariantError(f"rollback is in terminal state: {old.status.value}")
        updated = RollbackRecord(
            rollback_id=old.rollback_id, release_id=old.release_id, tenant_id=old.tenant_id,
            reason=old.reason, status=RollbackStatus.FAILED, initiated_at=old.initiated_at,
        )
        self._rollbacks[rollback_id] = updated
        _emit(self._events, "fail_rollback", {"rollback_id": rollback_id}, rollback_id)
        return updated

    def rollbacks_for_release(self, release_id: str) -> tuple[RollbackRecord, ...]:
        return tuple(r for r in self._rollbacks.values() if r.release_id == release_id)

    # ------------------------------------------------------------------
    # Assessments
    # ------------------------------------------------------------------

    def assess_release(
        self,
        assessment_id: str,
        release_id: str,
        tenant_id: str,
        readiness_score: float = 1.0,
        customer_impact_score: float = 0.0,
    ) -> ReleaseAssessment:
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError(f"assessment already exists: {assessment_id}")
        if release_id not in self._releases:
            raise RuntimeCoreInvariantError(f"unknown release: {release_id}")
        now = _now_iso()
        risk = self._derive_risk_level(readiness_score, customer_impact_score)
        assessment = ReleaseAssessment(
            assessment_id=assessment_id, release_id=release_id, tenant_id=tenant_id,
            risk_level=risk, readiness_score=readiness_score,
            customer_impact_score=customer_impact_score, assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "assess_release", {"assessment_id": assessment_id, "risk": risk.value}, assessment_id)
        return assessment

    def assessments_for_release(self, release_id: str) -> tuple[ReleaseAssessment, ...]:
        return tuple(a for a in self._assessments.values() if a.release_id == release_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def release_snapshot(self, snapshot_id: str) -> ReleaseSnapshot:
        now = _now_iso()
        return ReleaseSnapshot(
            snapshot_id=snapshot_id,
            total_versions=len(self._versions),
            total_releases=len(self._releases),
            total_gates=len(self._gates),
            total_promotions=len(self._promotions),
            total_rollbacks=len(self._rollbacks),
            total_milestones=len(self._milestones),
            total_assessments=len(self._assessments),
            total_violations=len(self._violations),
            captured_at=now,
        )

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def detect_release_violations(self, tenant_id: str) -> tuple[ReleaseViolation, ...]:
        """Detect release violations. Idempotent per violation_id."""
        now = _now_iso()
        new_violations: list[ReleaseViolation] = []

        # 1. Releases with failed gates still in progress
        for r in self._releases.values():
            if r.tenant_id == tenant_id and r.status == ReleaseStatus.IN_PROGRESS:
                gates = self.gates_for_release(r.release_id)
                failed_gates = [g for g in gates if not g.passed]
                if failed_gates:
                    vid = stable_identifier("viol-pops", {"type": "failed_gate_in_progress", "release_id": r.release_id})
                    if vid not in self._violations:
                        v = ReleaseViolation(
                            violation_id=vid, tenant_id=tenant_id, release_id=r.release_id,
                            operation="failed_gate_in_progress",
                            reason=f"release {r.release_id} in progress with {len(failed_gates)} failed gate(s)",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2. Releases with no gates
        for r in self._releases.values():
            if r.tenant_id == tenant_id and r.status not in _RELEASE_TERMINAL and r.gate_count == 0:
                vid = stable_identifier("viol-pops", {"type": "no_gates", "release_id": r.release_id})
                if vid not in self._violations:
                    v = ReleaseViolation(
                        violation_id=vid, tenant_id=tenant_id, release_id=r.release_id,
                        operation="no_gates",
                        reason=f"release {r.release_id} has no gates evaluated",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        # 3. Blocked promotions
        for p in self._promotions.values():
            if p.tenant_id == tenant_id and p.disposition == PromotionDisposition.BLOCKED:
                vid = stable_identifier("viol-pops", {"type": "blocked_promotion", "promotion_id": p.promotion_id})
                if vid not in self._violations:
                    rel = self._releases.get(p.release_id)
                    v = ReleaseViolation(
                        violation_id=vid, tenant_id=tenant_id, release_id=p.release_id,
                        operation="blocked_promotion",
                        reason=f"promotion {p.promotion_id} blocked for release {p.release_id}",
                        detected_at=now,
                    )
                    self._violations[vid] = v
                    new_violations.append(v)

        _emit(self._events, "detect_release_violations", {"tenant_id": tenant_id, "count": len(new_violations)}, tenant_id)
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[ReleaseViolation, ...]:
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Closure report
    # ------------------------------------------------------------------

    def closure_report(self, report_id: str, tenant_id: str) -> ReleaseClosureReport:
        now = _now_iso()
        return ReleaseClosureReport(
            report_id=report_id, tenant_id=tenant_id,
            total_versions=len([v for v in self._versions.values() if v.tenant_id == tenant_id]),
            total_releases=len([r for r in self._releases.values() if r.tenant_id == tenant_id]),
            total_promotions=len([p for p in self._promotions.values() if p.tenant_id == tenant_id]),
            total_rollbacks=len([r for r in self._rollbacks.values() if r.tenant_id == tenant_id]),
            total_milestones=len([m for m in self._milestones.values() if m.tenant_id == tenant_id]),
            total_violations=len([v for v in self._violations.values() if v.tenant_id == tenant_id]),
            closed_at=now,
        )

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        parts: list[str] = []
        for k in sorted(self._versions):
            parts.append(f"v:{k}")
        for k in sorted(self._releases):
            parts.append(f"r:{k}")
        for k in sorted(self._gates):
            parts.append(f"g:{k}")
        for k in sorted(self._promotions):
            parts.append(f"p:{k}")
        for k in sorted(self._rollbacks):
            parts.append(f"rb:{k}")
        for k in sorted(self._milestones):
            parts.append(f"m:{k}")
        for k in sorted(self._assessments):
            parts.append(f"a:{k}")
        for k in sorted(self._violations):
            parts.append(f"vl:{k}")
        return sha256("|".join(parts).encode()).hexdigest()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _transition_lifecycle(
        self, version_id: str, to_status: LifecycleStatus, reason: str
    ) -> LifecycleMilestone:
        if version_id not in self._versions:
            raise RuntimeCoreInvariantError(f"unknown version: {version_id}")
        old = self._versions[version_id]
        if old.lifecycle_status in _LIFECYCLE_TERMINAL:
            raise RuntimeCoreInvariantError(f"version is in terminal state: {old.lifecycle_status.value}")
        now = _now_iso()
        mid = stable_identifier("ms", {"version_id": version_id, "to": to_status.value})
        milestone = LifecycleMilestone(
            milestone_id=mid, version_id=version_id, tenant_id=old.tenant_id,
            from_status=old.lifecycle_status, to_status=to_status,
            reason=reason, recorded_at=now,
        )
        self._milestones[mid] = milestone
        # Update version
        updated = ProductVersionRecord(
            version_id=old.version_id, product_id=old.product_id, tenant_id=old.tenant_id,
            version_label=old.version_label, lifecycle_status=to_status, created_at=old.created_at,
        )
        self._versions[version_id] = updated
        _emit(self._events, "lifecycle_transition", {"version_id": version_id, "to": to_status.value}, mid)
        return milestone

    @staticmethod
    def _derive_risk_level(readiness: float, impact: float) -> ReleaseRiskLevel:
        if readiness < 0.3 or impact >= 0.8:
            return ReleaseRiskLevel.CRITICAL
        if readiness < 0.5 or impact >= 0.5:
            return ReleaseRiskLevel.HIGH
        if readiness < 0.8 or impact >= 0.3:
            return ReleaseRiskLevel.MEDIUM
        return ReleaseRiskLevel.LOW
