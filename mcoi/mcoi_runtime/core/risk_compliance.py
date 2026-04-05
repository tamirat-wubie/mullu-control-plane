"""Purpose: risk / compliance / controls runtime engine.
Governance scope: registering risks, requirements, controls; binding controls
    to scopes; recording test outcomes; managing exceptions; assessing risk
    posture; producing compliance snapshots and assurance reports.
Dependencies: risk_compliance contracts, event_spine, core invariants.
Invariants:
  - Every risk has explicit severity and category.
  - Controls bind to scoped entities and require test evidence.
  - Exceptions are time-bounded and require approval.
  - Compliance snapshots aggregate control status.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.risk_compliance import (
    AssuranceReport,
    ComplianceDisposition,
    ComplianceRequirement,
    ComplianceSnapshot,
    ControlBinding,
    ControlFailure,
    ControlRecord,
    ControlStatus,
    ControlTestRecord,
    ControlTestStatus,
    EvidenceSourceKind,
    ExceptionRequest,
    ExceptionStatus,
    RiskAssessment,
    RiskCategory,
    RiskRecord,
    RiskSeverity,
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
        event_id=stable_identifier("evt-risk", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class RiskComplianceEngine:
    """Enterprise risk, compliance, and controls engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._risks: dict[str, RiskRecord] = {}
        self._requirements: dict[str, ComplianceRequirement] = {}
        self._controls: dict[str, ControlRecord] = {}
        self._bindings: dict[str, ControlBinding] = {}
        self._tests: dict[str, ControlTestRecord] = {}
        self._exceptions: dict[str, ExceptionRequest] = {}
        self._assessments: dict[str, RiskAssessment] = {}
        self._snapshots: dict[str, ComplianceSnapshot] = {}
        self._failures: dict[str, ControlFailure] = {}
        self._reports: dict[str, AssuranceReport] = {}

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def risk_count(self) -> int:
        return len(self._risks)

    @property
    def requirement_count(self) -> int:
        return len(self._requirements)

    @property
    def control_count(self) -> int:
        return len(self._controls)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def test_count(self) -> int:
        return len(self._tests)

    @property
    def exception_count(self) -> int:
        return len(self._exceptions)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def snapshot_count(self) -> int:
        return len(self._snapshots)

    @property
    def failure_count(self) -> int:
        return len(self._failures)

    @property
    def report_count(self) -> int:
        return len(self._reports)

    # ------------------------------------------------------------------
    # Risk management
    # ------------------------------------------------------------------

    def register_risk(
        self,
        risk_id: str,
        title: str,
        *,
        severity: RiskSeverity = RiskSeverity.MEDIUM,
        category: RiskCategory = RiskCategory.OPERATIONAL,
        likelihood: float = 0.0,
        impact: float = 0.0,
        scope_ref_id: str = "",
        owner: str = "",
        mitigations: list[str] | None = None,
    ) -> RiskRecord:
        """Register a new risk in the risk register."""
        if risk_id in self._risks:
            raise RuntimeCoreInvariantError("Duplicate risk_id")
        now = _now_iso()
        risk = RiskRecord(
            risk_id=risk_id,
            title=title,
            severity=severity,
            category=category,
            likelihood=likelihood,
            impact=impact,
            scope_ref_id=scope_ref_id,
            owner=owner,
            mitigations=tuple(mitigations or []),
            created_at=now,
        )
        self._risks[risk_id] = risk
        _emit(self._events, "risk_registered", {"risk_id": risk_id}, risk_id)
        return risk

    def update_risk_severity(
        self, risk_id: str, severity: RiskSeverity,
    ) -> RiskRecord:
        """Update the severity of an existing risk."""
        old = self._risks.get(risk_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown risk_id")
        now = _now_iso()
        updated = RiskRecord(
            risk_id=old.risk_id,
            title=old.title,
            description=old.description,
            severity=severity,
            category=old.category,
            likelihood=old.likelihood,
            impact=old.impact,
            scope_ref_id=old.scope_ref_id,
            owner=old.owner,
            mitigations=old.mitigations,
            created_at=old.created_at,
            updated_at=now,
            metadata=old.metadata,
        )
        self._risks[risk_id] = updated
        _emit(self._events, "risk_severity_updated", {
            "risk_id": risk_id, "severity": severity.value,
        }, risk_id)
        return updated

    def risks_by_severity(self, severity: RiskSeverity) -> tuple[RiskRecord, ...]:
        """Return all risks with the given severity."""
        return tuple(r for r in self._risks.values() if r.severity == severity)

    def risks_for_scope(self, scope_ref_id: str) -> tuple[RiskRecord, ...]:
        """Return all risks for a given scope."""
        return tuple(r for r in self._risks.values() if r.scope_ref_id == scope_ref_id)

    # ------------------------------------------------------------------
    # Requirement management
    # ------------------------------------------------------------------

    def register_requirement(
        self,
        requirement_id: str,
        title: str,
        *,
        category: RiskCategory = RiskCategory.COMPLIANCE,
        mandatory: bool = True,
        control_ids: list[str] | None = None,
        evidence_source_kinds: list[str] | None = None,
    ) -> ComplianceRequirement:
        """Register a compliance requirement."""
        if requirement_id in self._requirements:
            raise RuntimeCoreInvariantError("Duplicate requirement_id")
        now = _now_iso()
        req = ComplianceRequirement(
            requirement_id=requirement_id,
            title=title,
            category=category,
            mandatory=mandatory,
            control_ids=tuple(control_ids or []),
            evidence_source_kinds=tuple(evidence_source_kinds or []),
            created_at=now,
        )
        self._requirements[requirement_id] = req
        _emit(self._events, "requirement_registered", {"requirement_id": requirement_id}, requirement_id)
        return req

    # ------------------------------------------------------------------
    # Control management
    # ------------------------------------------------------------------

    def register_control(
        self,
        control_id: str,
        title: str,
        *,
        requirement_id: str = "",
        test_frequency_seconds: float = 86400.0,
        owner: str = "",
    ) -> ControlRecord:
        """Register a new control."""
        if control_id in self._controls:
            raise RuntimeCoreInvariantError("Duplicate control_id")
        now = _now_iso()
        ctrl = ControlRecord(
            control_id=control_id,
            title=title,
            status=ControlStatus.ACTIVE,
            requirement_id=requirement_id,
            test_frequency_seconds=test_frequency_seconds,
            owner=owner,
            created_at=now,
        )
        self._controls[control_id] = ctrl
        _emit(self._events, "control_registered", {"control_id": control_id}, control_id)
        return ctrl

    def set_control_status(
        self, control_id: str, status: ControlStatus,
    ) -> ControlRecord:
        """Update a control's status."""
        old = self._controls.get(control_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown control_id")
        updated = ControlRecord(
            control_id=old.control_id,
            title=old.title,
            description=old.description,
            status=status,
            requirement_id=old.requirement_id,
            test_frequency_seconds=old.test_frequency_seconds,
            last_tested_at=old.last_tested_at,
            owner=old.owner,
            created_at=old.created_at,
            metadata=old.metadata,
        )
        self._controls[control_id] = updated
        _emit(self._events, "control_status_updated", {
            "control_id": control_id, "status": status.value,
        }, control_id)
        return updated

    # ------------------------------------------------------------------
    # Control binding
    # ------------------------------------------------------------------

    def bind_control(
        self,
        binding_id: str,
        control_id: str,
        scope_ref_id: str,
        *,
        scope_type: str = "",
        enforced: bool = True,
    ) -> ControlBinding:
        """Bind a control to a scoped entity."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError("Duplicate binding_id")
        if control_id not in self._controls:
            raise RuntimeCoreInvariantError("Unknown control_id")
        now = _now_iso()
        binding = ControlBinding(
            binding_id=binding_id,
            control_id=control_id,
            scope_ref_id=scope_ref_id,
            scope_type=scope_type,
            enforced=enforced,
            bound_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "control_bound", {
            "binding_id": binding_id, "control_id": control_id, "scope_ref_id": scope_ref_id,
        }, binding_id)
        return binding

    def bindings_for_scope(self, scope_ref_id: str) -> tuple[ControlBinding, ...]:
        """Return all bindings for a given scope."""
        return tuple(b for b in self._bindings.values() if b.scope_ref_id == scope_ref_id)

    def bindings_for_control(self, control_id: str) -> tuple[ControlBinding, ...]:
        """Return all bindings for a given control."""
        return tuple(b for b in self._bindings.values() if b.control_id == control_id)

    # ------------------------------------------------------------------
    # Control testing
    # ------------------------------------------------------------------

    def record_control_test(
        self,
        test_id: str,
        control_id: str,
        status: ControlTestStatus,
        *,
        evidence_refs: list[str] | None = None,
        tester: str = "",
        notes: str = "",
    ) -> ControlTestRecord:
        """Record the outcome of a control test."""
        if test_id in self._tests:
            raise RuntimeCoreInvariantError("Duplicate test_id")
        if control_id not in self._controls:
            raise RuntimeCoreInvariantError("Unknown control_id")
        now = _now_iso()
        test = ControlTestRecord(
            test_id=test_id,
            control_id=control_id,
            status=status,
            evidence_refs=tuple(evidence_refs or []),
            tester=tester,
            notes=notes,
            tested_at=now,
        )
        self._tests[test_id] = test

        # Update control's last_tested_at and status based on test result
        old_ctrl = self._controls[control_id]
        new_status = old_ctrl.status
        if status == ControlTestStatus.FAILED:
            new_status = ControlStatus.FAILED
        elif status == ControlTestStatus.PASSED and old_ctrl.status in (
            ControlStatus.TESTING, ControlStatus.FAILED, ControlStatus.REMEDIATION,
        ):
            new_status = ControlStatus.ACTIVE
        updated_ctrl = ControlRecord(
            control_id=old_ctrl.control_id,
            title=old_ctrl.title,
            description=old_ctrl.description,
            status=new_status,
            requirement_id=old_ctrl.requirement_id,
            test_frequency_seconds=old_ctrl.test_frequency_seconds,
            last_tested_at=now,
            owner=old_ctrl.owner,
            created_at=old_ctrl.created_at,
            metadata=old_ctrl.metadata,
        )
        self._controls[control_id] = updated_ctrl

        _emit(self._events, "control_tested", {
            "test_id": test_id, "control_id": control_id, "status": status.value,
        }, test_id)
        return test

    def tests_for_control(self, control_id: str) -> tuple[ControlTestRecord, ...]:
        """Return all test records for a control."""
        return tuple(t for t in self._tests.values() if t.control_id == control_id)

    def latest_test_for_control(self, control_id: str) -> ControlTestRecord | None:
        """Return the most recent test for a control, or None."""
        tests = self.tests_for_control(control_id)
        return tests[-1] if tests else None

    # ------------------------------------------------------------------
    # Exception management
    # ------------------------------------------------------------------

    def request_exception(
        self,
        exception_id: str,
        control_id: str,
        *,
        scope_ref_id: str = "",
        reason: str = "",
        requested_by: str = "",
        expires_at: str = "",
    ) -> ExceptionRequest:
        """Request a compliance exception."""
        if exception_id in self._exceptions:
            raise RuntimeCoreInvariantError("Duplicate exception_id")
        if control_id not in self._controls:
            raise RuntimeCoreInvariantError("Unknown control_id")
        now = _now_iso()
        exc = ExceptionRequest(
            exception_id=exception_id,
            control_id=control_id,
            scope_ref_id=scope_ref_id,
            status=ExceptionStatus.REQUESTED,
            reason=reason,
            requested_by=requested_by,
            expires_at=expires_at,
            requested_at=now,
        )
        self._exceptions[exception_id] = exc
        _emit(self._events, "exception_requested", {
            "exception_id": exception_id, "control_id": control_id,
        }, exception_id)
        return exc

    def approve_exception(
        self,
        exception_id: str,
        *,
        approved_by: str = "",
    ) -> ExceptionRequest:
        """Approve an exception request."""
        old = self._exceptions.get(exception_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown exception_id")
        if old.status != ExceptionStatus.REQUESTED:
            raise RuntimeCoreInvariantError("Cannot approve exception in current status")
        now = _now_iso()
        updated = ExceptionRequest(
            exception_id=old.exception_id,
            control_id=old.control_id,
            scope_ref_id=old.scope_ref_id,
            status=ExceptionStatus.APPROVED,
            reason=old.reason,
            requested_by=old.requested_by,
            approved_by=approved_by,
            expires_at=old.expires_at,
            requested_at=old.requested_at,
            resolved_at=now,
            metadata=old.metadata,
        )
        self._exceptions[exception_id] = updated
        _emit(self._events, "exception_approved", {"exception_id": exception_id}, exception_id)
        return updated

    def deny_exception(self, exception_id: str) -> ExceptionRequest:
        """Deny an exception request."""
        old = self._exceptions.get(exception_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown exception_id")
        if old.status != ExceptionStatus.REQUESTED:
            raise RuntimeCoreInvariantError("Cannot deny exception in current status")
        now = _now_iso()
        updated = ExceptionRequest(
            exception_id=old.exception_id,
            control_id=old.control_id,
            scope_ref_id=old.scope_ref_id,
            status=ExceptionStatus.DENIED,
            reason=old.reason,
            requested_by=old.requested_by,
            approved_by=old.approved_by,
            expires_at=old.expires_at,
            requested_at=old.requested_at,
            resolved_at=now,
            metadata=old.metadata,
        )
        self._exceptions[exception_id] = updated
        _emit(self._events, "exception_denied", {"exception_id": exception_id}, exception_id)
        return updated

    def revoke_exception(self, exception_id: str) -> ExceptionRequest:
        """Revoke an approved exception."""
        old = self._exceptions.get(exception_id)
        if old is None:
            raise RuntimeCoreInvariantError("Unknown exception_id")
        if old.status != ExceptionStatus.APPROVED:
            raise RuntimeCoreInvariantError("Cannot revoke exception in current status")
        now = _now_iso()
        updated = ExceptionRequest(
            exception_id=old.exception_id,
            control_id=old.control_id,
            scope_ref_id=old.scope_ref_id,
            status=ExceptionStatus.REVOKED,
            reason=old.reason,
            requested_by=old.requested_by,
            approved_by=old.approved_by,
            expires_at=old.expires_at,
            requested_at=old.requested_at,
            resolved_at=now,
            metadata=old.metadata,
        )
        self._exceptions[exception_id] = updated
        _emit(self._events, "exception_revoked", {"exception_id": exception_id}, exception_id)
        return updated

    def active_exceptions_for_control(self, control_id: str) -> tuple[ExceptionRequest, ...]:
        """Return all active (approved) exceptions for a control."""
        return tuple(
            e for e in self._exceptions.values()
            if e.control_id == control_id and e.status == ExceptionStatus.APPROVED
        )

    def active_exceptions_for_scope(self, scope_ref_id: str) -> tuple[ExceptionRequest, ...]:
        """Return all active exceptions for a scope."""
        return tuple(
            e for e in self._exceptions.values()
            if e.scope_ref_id == scope_ref_id and e.status == ExceptionStatus.APPROVED
        )

    # ------------------------------------------------------------------
    # Control failure recording
    # ------------------------------------------------------------------

    def record_control_failure(
        self,
        failure_id: str,
        control_id: str,
        *,
        test_id: str = "",
        scope_ref_id: str = "",
        severity: RiskSeverity = RiskSeverity.MEDIUM,
        action_taken: str = "",
        escalated: bool = False,
        blocked: bool = False,
    ) -> ControlFailure:
        """Record a control failure."""
        if failure_id in self._failures:
            raise RuntimeCoreInvariantError("Duplicate failure_id")
        now = _now_iso()
        failure = ControlFailure(
            failure_id=failure_id,
            control_id=control_id,
            test_id=test_id,
            scope_ref_id=scope_ref_id,
            severity=severity,
            action_taken=action_taken,
            escalated=escalated,
            blocked=blocked,
            recorded_at=now,
        )
        self._failures[failure_id] = failure
        _emit(self._events, "control_failure_recorded", {
            "failure_id": failure_id, "control_id": control_id, "severity": severity.value,
        }, failure_id)
        return failure

    def failures_for_control(self, control_id: str) -> tuple[ControlFailure, ...]:
        """Return all failures for a control."""
        return tuple(f for f in self._failures.values() if f.control_id == control_id)

    def failures_for_scope(self, scope_ref_id: str) -> tuple[ControlFailure, ...]:
        """Return all failures for a scope."""
        return tuple(f for f in self._failures.values() if f.scope_ref_id == scope_ref_id)

    # ------------------------------------------------------------------
    # Risk assessment
    # ------------------------------------------------------------------

    def assess_scope(
        self,
        assessment_id: str,
        scope_ref_id: str,
    ) -> RiskAssessment:
        """Assess risk posture for a scope, aggregating from registered risks."""
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError("Duplicate assessment_id")

        scope_risks = self.risks_for_scope(scope_ref_id)
        risk_count = len(scope_risks)
        critical_risks = sum(1 for r in scope_risks if r.severity == RiskSeverity.CRITICAL)
        high_risks = sum(1 for r in scope_risks if r.severity == RiskSeverity.HIGH)
        unmitigated = sum(1 for r in scope_risks if len(r.mitigations) == 0)

        # Determine overall severity
        if critical_risks > 0:
            overall = RiskSeverity.CRITICAL
        elif high_risks > 0:
            overall = RiskSeverity.HIGH
        elif risk_count > 0:
            overall = RiskSeverity.MEDIUM
        else:
            overall = RiskSeverity.LOW

        # Risk score: weighted average of likelihood * impact, capped at 1.0
        if risk_count > 0:
            raw_score = sum(r.likelihood * r.impact for r in scope_risks) / risk_count
            risk_score = min(raw_score, 1.0)
        else:
            risk_score = 0.0

        now = _now_iso()
        assessment = RiskAssessment(
            assessment_id=assessment_id,
            scope_ref_id=scope_ref_id,
            overall_severity=overall,
            risk_count=risk_count,
            critical_risks=critical_risks,
            high_risks=high_risks,
            unmitigated_risks=unmitigated,
            risk_score=risk_score,
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "scope_assessed", {
            "assessment_id": assessment_id, "scope_ref_id": scope_ref_id,
            "overall_severity": overall.value, "risk_score": risk_score,
        }, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Compliance snapshot
    # ------------------------------------------------------------------

    def capture_compliance_snapshot(
        self,
        snapshot_id: str,
        scope_ref_id: str,
    ) -> ComplianceSnapshot:
        """Capture a point-in-time compliance snapshot for a scope."""
        if snapshot_id in self._snapshots:
            raise RuntimeCoreInvariantError("Duplicate snapshot_id")

        scope_bindings = self.bindings_for_scope(scope_ref_id)
        bound_control_ids = {b.control_id for b in scope_bindings if b.enforced}

        total = len(bound_control_ids)
        passing = 0
        failing = 0
        for cid in bound_control_ids:
            ctrl = self._controls.get(cid)
            if ctrl is None:
                continue
            if ctrl.status == ControlStatus.FAILED:
                failing += 1
            elif ctrl.status == ControlStatus.ACTIVE:
                passing += 1

        exceptions_active = len(self.active_exceptions_for_scope(scope_ref_id))
        compliance_pct = (passing / total * 100.0) if total > 0 else 0.0

        # Determine disposition
        if total == 0:
            disposition = ComplianceDisposition.NOT_ASSESSED
        elif failing == 0 and passing == total:
            disposition = ComplianceDisposition.COMPLIANT
        elif failing == 0 and exceptions_active > 0:
            disposition = ComplianceDisposition.EXCEPTION_GRANTED
        elif failing > 0 and passing > 0:
            disposition = ComplianceDisposition.PARTIALLY_COMPLIANT
        else:
            disposition = ComplianceDisposition.NON_COMPLIANT

        now = _now_iso()
        snapshot = ComplianceSnapshot(
            snapshot_id=snapshot_id,
            scope_ref_id=scope_ref_id,
            disposition=disposition,
            total_controls=total,
            passing_controls=passing,
            failing_controls=failing,
            exceptions_active=exceptions_active,
            compliance_pct=compliance_pct,
            captured_at=now,
        )
        self._snapshots[snapshot_id] = snapshot
        _emit(self._events, "compliance_snapshot_captured", {
            "snapshot_id": snapshot_id, "scope_ref_id": scope_ref_id,
            "disposition": disposition.value, "compliance_pct": compliance_pct,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # Assurance report
    # ------------------------------------------------------------------

    def assurance_report(
        self,
        report_id: str,
        scope_ref_id: str,
    ) -> AssuranceReport:
        """Generate an assurance report for a scope."""
        if report_id in self._reports:
            raise RuntimeCoreInvariantError("Duplicate report_id")

        # Requirements
        total_requirements = len(self._requirements)
        # A requirement is met if all its control_ids have ACTIVE status
        met = 0
        for req in self._requirements.values():
            if not req.control_ids:
                met += 1
                continue
            all_active = all(
                self._controls.get(cid) is not None
                and self._controls[cid].status == ControlStatus.ACTIVE
                for cid in req.control_ids
            )
            if all_active:
                met += 1

        # Controls for scope
        scope_bindings = self.bindings_for_scope(scope_ref_id)
        bound_control_ids = {b.control_id for b in scope_bindings if b.enforced}
        total_controls = len(bound_control_ids)
        passing_controls = 0
        failing_controls = 0
        for cid in bound_control_ids:
            ctrl = self._controls.get(cid)
            if ctrl is None:
                continue
            if ctrl.status == ControlStatus.FAILED:
                failing_controls += 1
            elif ctrl.status == ControlStatus.ACTIVE:
                passing_controls += 1

        active_exceptions = len(self.active_exceptions_for_scope(scope_ref_id))
        total_failures = len(self.failures_for_scope(scope_ref_id))

        # Risk assessment
        scope_risks = self.risks_for_scope(scope_ref_id)
        if scope_risks:
            critical = any(r.severity == RiskSeverity.CRITICAL for r in scope_risks)
            high = any(r.severity == RiskSeverity.HIGH for r in scope_risks)
            if critical:
                overall_risk = RiskSeverity.CRITICAL
            elif high:
                overall_risk = RiskSeverity.HIGH
            else:
                overall_risk = RiskSeverity.MEDIUM
            raw_score = sum(r.likelihood * r.impact for r in scope_risks) / len(scope_risks)
            risk_score = min(raw_score, 1.0)
        else:
            overall_risk = RiskSeverity.LOW
            risk_score = 0.0

        compliance_pct = (passing_controls / total_controls * 100.0) if total_controls > 0 else 0.0

        # Disposition
        if total_controls == 0:
            disposition = ComplianceDisposition.NOT_ASSESSED
        elif failing_controls == 0 and passing_controls == total_controls:
            disposition = ComplianceDisposition.COMPLIANT
        elif failing_controls == 0 and active_exceptions > 0:
            disposition = ComplianceDisposition.EXCEPTION_GRANTED
        elif failing_controls > 0 and passing_controls > 0:
            disposition = ComplianceDisposition.PARTIALLY_COMPLIANT
        else:
            disposition = ComplianceDisposition.NON_COMPLIANT

        now = _now_iso()
        report = AssuranceReport(
            report_id=report_id,
            scope_ref_id=scope_ref_id,
            overall_disposition=disposition,
            overall_risk_severity=overall_risk,
            total_requirements=total_requirements,
            met_requirements=met,
            total_controls=total_controls,
            passing_controls=passing_controls,
            failing_controls=failing_controls,
            active_exceptions=active_exceptions,
            total_failures=total_failures,
            risk_score=risk_score,
            compliance_pct=compliance_pct,
            generated_at=now,
        )
        self._reports[report_id] = report
        _emit(self._events, "assurance_report_generated", {
            "report_id": report_id, "scope_ref_id": scope_ref_id,
            "disposition": disposition.value,
        }, report_id)
        return report

    # ------------------------------------------------------------------
    # Failed controls
    # ------------------------------------------------------------------

    def failed_controls(self) -> tuple[ControlRecord, ...]:
        """Return all controls in FAILED status."""
        return tuple(c for c in self._controls.values() if c.status == ControlStatus.FAILED)

    def controls_for_requirement(self, requirement_id: str) -> tuple[ControlRecord, ...]:
        """Return all controls linked to a requirement."""
        return tuple(
            c for c in self._controls.values() if c.requirement_id == requirement_id
        )

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"risks={self.risk_count}",
            f"requirements={self.requirement_count}",
            f"controls={self.control_count}",
            f"bindings={self.binding_count}",
            f"tests={self.test_count}",
            f"exceptions={self.exception_count}",
            f"assessments={self.assessment_count}",
            f"snapshots={self.snapshot_count}",
            f"failures={self.failure_count}",
            f"reports={self.report_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
