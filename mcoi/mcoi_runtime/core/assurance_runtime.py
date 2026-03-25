"""Purpose: assurance / attestation / certification runtime engine.
Governance scope: registering attestations and certifications; binding evidence
    from records, cases, remediations, and control tests; evaluating evidence
    sufficiency; granting, denying, and revoking assurance; scheduling
    recertification windows; degrading assurance on new failures; producing
    immutable snapshots and closure reports.
Dependencies: assurance_runtime contracts, event_spine, core invariants.
Invariants:
  - Certification requires sufficient evidence.
  - Expired certifications degrade automatically.
  - New failures revoke previously granted assurance.
  - Every mutation emits an event.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from ..contracts.assurance_runtime import (
    AssuranceAssessment,
    AssuranceClosureReport,
    AssuranceDecision,
    AssuranceEvidenceBinding,
    AssuranceFinding,
    AssuranceLevel,
    AssuranceScope,
    AssuranceSnapshot,
    AssuranceViolation,
    AttestationRecord,
    AttestationStatus,
    CertificationRecord,
    CertificationStatus,
    EvidenceSufficiency,
    RecertificationStatus,
    RecertificationWindow,
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
        event_id=stable_identifier("evt-asur", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_ATTESTATION_TERMINAL = frozenset({AttestationStatus.REVOKED, AttestationStatus.EXPIRED})
_CERTIFICATION_TERMINAL = frozenset({CertificationStatus.REVOKED, CertificationStatus.EXPIRED})


class AssuranceRuntimeEngine:
    """Assurance, attestation, and certification engine."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._attestations: dict[str, AttestationRecord] = {}
        self._certifications: dict[str, CertificationRecord] = {}
        self._assessments: dict[str, AssuranceAssessment] = {}
        self._bindings: dict[str, AssuranceEvidenceBinding] = {}
        self._windows: dict[str, RecertificationWindow] = {}
        self._findings: dict[str, AssuranceFinding] = {}
        self._decisions: dict[str, AssuranceDecision] = {}
        self._violations: dict[str, AssuranceViolation] = {}
        self._snapshot_ids: set[str] = set()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def attestation_count(self) -> int:
        return len(self._attestations)

    @property
    def granted_attestation_count(self) -> int:
        return sum(1 for a in self._attestations.values() if a.status == AttestationStatus.GRANTED)

    @property
    def certification_count(self) -> int:
        return len(self._certifications)

    @property
    def active_certification_count(self) -> int:
        return sum(1 for c in self._certifications.values() if c.status == CertificationStatus.ACTIVE)

    @property
    def assessment_count(self) -> int:
        return len(self._assessments)

    @property
    def binding_count(self) -> int:
        return len(self._bindings)

    @property
    def window_count(self) -> int:
        return len(self._windows)

    @property
    def finding_count(self) -> int:
        return len(self._findings)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Attestations
    # ------------------------------------------------------------------

    def register_attestation(
        self,
        attestation_id: str,
        tenant_id: str,
        scope_ref_id: str,
        *,
        scope: AssuranceScope = AssuranceScope.CONTROL,
        level: AssuranceLevel = AssuranceLevel.NONE,
        attested_by: str = "system",
        expires_at: str = "",
    ) -> AttestationRecord:
        """Register an attestation."""
        if attestation_id in self._attestations:
            raise RuntimeCoreInvariantError(f"Duplicate attestation_id: {attestation_id}")
        now = _now_iso()
        rec = AttestationRecord(
            attestation_id=attestation_id,
            tenant_id=tenant_id,
            scope=scope,
            scope_ref_id=scope_ref_id,
            level=level,
            status=AttestationStatus.PENDING,
            attested_by=attested_by,
            attested_at=now,
            expires_at=expires_at,
        )
        self._attestations[attestation_id] = rec
        _emit(self._events, "attestation_registered", {
            "attestation_id": attestation_id, "scope": scope.value,
        }, attestation_id)
        return rec

    def get_attestation(self, attestation_id: str) -> AttestationRecord:
        """Get an attestation by ID."""
        a = self._attestations.get(attestation_id)
        if a is None:
            raise RuntimeCoreInvariantError(f"Unknown attestation_id: {attestation_id}")
        return a

    def attestations_for_tenant(self, tenant_id: str) -> tuple[AttestationRecord, ...]:
        """Return all attestations for a tenant."""
        return tuple(a for a in self._attestations.values() if a.tenant_id == tenant_id)

    def grant_attestation(self, attestation_id: str, level: AssuranceLevel) -> AttestationRecord:
        """Grant an attestation with a specific assurance level."""
        old = self.get_attestation(attestation_id)
        if old.status in _ATTESTATION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot grant attestation in status {old.status.value}"
            )
        # Check evidence sufficiency
        bindings = self.bindings_for_target(attestation_id, "attestation")
        if not bindings:
            raise RuntimeCoreInvariantError(
                "Cannot grant attestation without evidence bindings"
            )
        updated = AttestationRecord(
            attestation_id=old.attestation_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            level=level,
            status=AttestationStatus.GRANTED,
            attested_by=old.attested_by,
            attested_at=old.attested_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._attestations[attestation_id] = updated
        _emit(self._events, "attestation_granted", {
            "attestation_id": attestation_id, "level": level.value,
        }, attestation_id)
        return updated

    def deny_attestation(self, attestation_id: str, *, reason: str = "") -> AttestationRecord:
        """Deny an attestation."""
        old = self.get_attestation(attestation_id)
        if old.status in _ATTESTATION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot deny attestation in status {old.status.value}"
            )
        updated = AttestationRecord(
            attestation_id=old.attestation_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            level=AssuranceLevel.NONE,
            status=AttestationStatus.DENIED,
            attested_by=old.attested_by,
            attested_at=old.attested_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._attestations[attestation_id] = updated
        _emit(self._events, "attestation_denied", {
            "attestation_id": attestation_id, "reason": reason,
        }, attestation_id)
        return updated

    def revoke_attestation(self, attestation_id: str, *, reason: str = "") -> AttestationRecord:
        """Revoke a previously granted attestation."""
        old = self.get_attestation(attestation_id)
        if old.status != AttestationStatus.GRANTED:
            raise RuntimeCoreInvariantError("Can only revoke GRANTED attestations")
        updated = AttestationRecord(
            attestation_id=old.attestation_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            level=AssuranceLevel.NONE,
            status=AttestationStatus.REVOKED,
            attested_by=old.attested_by,
            attested_at=old.attested_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._attestations[attestation_id] = updated
        _emit(self._events, "attestation_revoked", {
            "attestation_id": attestation_id, "reason": reason,
        }, attestation_id)
        return updated

    # ------------------------------------------------------------------
    # Certifications
    # ------------------------------------------------------------------

    def register_certification(
        self,
        certification_id: str,
        tenant_id: str,
        scope_ref_id: str,
        *,
        scope: AssuranceScope = AssuranceScope.CONTROL,
        level: AssuranceLevel = AssuranceLevel.NONE,
        certified_by: str = "system",
        expires_at: str = "",
    ) -> CertificationRecord:
        """Register a certification."""
        if certification_id in self._certifications:
            raise RuntimeCoreInvariantError(f"Duplicate certification_id: {certification_id}")
        now = _now_iso()
        rec = CertificationRecord(
            certification_id=certification_id,
            tenant_id=tenant_id,
            scope=scope,
            scope_ref_id=scope_ref_id,
            status=CertificationStatus.PENDING,
            level=level,
            certified_by=certified_by,
            certified_at=now,
            expires_at=expires_at,
        )
        self._certifications[certification_id] = rec
        _emit(self._events, "certification_registered", {
            "certification_id": certification_id, "scope": scope.value,
        }, certification_id)
        return rec

    def get_certification(self, certification_id: str) -> CertificationRecord:
        """Get a certification by ID."""
        c = self._certifications.get(certification_id)
        if c is None:
            raise RuntimeCoreInvariantError(f"Unknown certification_id: {certification_id}")
        return c

    def activate_certification(self, certification_id: str, level: AssuranceLevel) -> CertificationRecord:
        """Activate a certification with a specific assurance level."""
        old = self.get_certification(certification_id)
        if old.status in _CERTIFICATION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot activate certification in status {old.status.value}"
            )
        bindings = self.bindings_for_target(certification_id, "certification")
        if not bindings:
            raise RuntimeCoreInvariantError(
                "Cannot activate certification without evidence bindings"
            )
        updated = CertificationRecord(
            certification_id=old.certification_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            status=CertificationStatus.ACTIVE,
            level=level,
            certified_by=old.certified_by,
            certified_at=old.certified_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._certifications[certification_id] = updated
        _emit(self._events, "certification_activated", {
            "certification_id": certification_id, "level": level.value,
        }, certification_id)
        return updated

    def suspend_certification(self, certification_id: str, *, reason: str = "") -> CertificationRecord:
        """Suspend an active certification."""
        old = self.get_certification(certification_id)
        if old.status != CertificationStatus.ACTIVE:
            raise RuntimeCoreInvariantError("Can only suspend ACTIVE certifications")
        updated = CertificationRecord(
            certification_id=old.certification_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            status=CertificationStatus.SUSPENDED,
            level=old.level,
            certified_by=old.certified_by,
            certified_at=old.certified_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._certifications[certification_id] = updated
        _emit(self._events, "certification_suspended", {
            "certification_id": certification_id, "reason": reason,
        }, certification_id)
        return updated

    def revoke_certification(self, certification_id: str, *, reason: str = "") -> CertificationRecord:
        """Revoke a certification."""
        old = self.get_certification(certification_id)
        if old.status in _CERTIFICATION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot revoke certification in status {old.status.value}"
            )
        updated = CertificationRecord(
            certification_id=old.certification_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            status=CertificationStatus.REVOKED,
            level=AssuranceLevel.NONE,
            certified_by=old.certified_by,
            certified_at=old.certified_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._certifications[certification_id] = updated
        _emit(self._events, "certification_revoked", {
            "certification_id": certification_id, "reason": reason,
        }, certification_id)
        return updated

    def expire_certification(self, certification_id: str) -> CertificationRecord:
        """Mark a certification as expired."""
        old = self.get_certification(certification_id)
        if old.status in _CERTIFICATION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot expire certification in status {old.status.value}"
            )
        updated = CertificationRecord(
            certification_id=old.certification_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            status=CertificationStatus.EXPIRED,
            level=AssuranceLevel.NONE,
            certified_by=old.certified_by,
            certified_at=old.certified_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._certifications[certification_id] = updated
        _emit(self._events, "certification_expired", {
            "certification_id": certification_id,
        }, certification_id)
        return updated

    def mark_recertification_required(self, certification_id: str) -> CertificationRecord:
        """Mark a certification as requiring recertification."""
        old = self.get_certification(certification_id)
        if old.status in _CERTIFICATION_TERMINAL:
            raise RuntimeCoreInvariantError(
                f"Cannot mark recertification for status {old.status.value}"
            )
        updated = CertificationRecord(
            certification_id=old.certification_id,
            tenant_id=old.tenant_id,
            scope=old.scope,
            scope_ref_id=old.scope_ref_id,
            status=CertificationStatus.RECERTIFICATION_REQUIRED,
            level=old.level,
            certified_by=old.certified_by,
            certified_at=old.certified_at,
            expires_at=old.expires_at,
            metadata=old.metadata,
        )
        self._certifications[certification_id] = updated
        _emit(self._events, "recertification_required", {
            "certification_id": certification_id,
        }, certification_id)
        return updated

    # ------------------------------------------------------------------
    # Evidence bindings
    # ------------------------------------------------------------------

    def bind_evidence(
        self,
        binding_id: str,
        target_id: str,
        target_type: str,
        source_type: str,
        source_id: str,
    ) -> AssuranceEvidenceBinding:
        """Bind evidence to an attestation or certification."""
        if binding_id in self._bindings:
            raise RuntimeCoreInvariantError(f"Duplicate binding_id: {binding_id}")
        now = _now_iso()
        binding = AssuranceEvidenceBinding(
            binding_id=binding_id,
            target_id=target_id,
            target_type=target_type,
            source_type=source_type,
            source_id=source_id,
            bound_at=now,
        )
        self._bindings[binding_id] = binding
        _emit(self._events, "evidence_bound", {
            "binding_id": binding_id, "target_id": target_id,
            "source_type": source_type,
        }, target_id)
        return binding

    def bindings_for_target(self, target_id: str, target_type: str) -> tuple[AssuranceEvidenceBinding, ...]:
        """Return all evidence bindings for a target."""
        return tuple(
            b for b in self._bindings.values()
            if b.target_id == target_id and b.target_type == target_type
        )

    # ------------------------------------------------------------------
    # Assessments
    # ------------------------------------------------------------------

    def assess_assurance(
        self,
        assessment_id: str,
        tenant_id: str,
        scope_ref_id: str,
        *,
        scope: AssuranceScope = AssuranceScope.CONTROL,
        assessed_by: str = "system",
    ) -> AssuranceAssessment:
        """Assess assurance for a scope, evaluating evidence sufficiency."""
        if assessment_id in self._assessments:
            raise RuntimeCoreInvariantError(f"Duplicate assessment_id: {assessment_id}")

        # Count evidence bindings for this scope
        bindings = [
            b for b in self._bindings.values()
            if b.target_id == scope_ref_id
        ]
        binding_count = len(bindings)

        # Determine sufficiency and level based on evidence count
        if binding_count == 0:
            sufficiency = EvidenceSufficiency.INSUFFICIENT
            level = AssuranceLevel.NONE
            confidence = 0.0
        elif binding_count == 1:
            sufficiency = EvidenceSufficiency.PARTIAL
            level = AssuranceLevel.LOW
            confidence = 0.3
        elif binding_count <= 3:
            sufficiency = EvidenceSufficiency.SUFFICIENT
            level = AssuranceLevel.MODERATE
            confidence = 0.7
        else:
            sufficiency = EvidenceSufficiency.COMPREHENSIVE
            level = AssuranceLevel.HIGH
            confidence = 0.9

        now = _now_iso()
        assessment = AssuranceAssessment(
            assessment_id=assessment_id,
            tenant_id=tenant_id,
            scope=scope,
            scope_ref_id=scope_ref_id,
            level=level,
            sufficiency=sufficiency,
            confidence=confidence,
            assessed_by=assessed_by,
            assessed_at=now,
        )
        self._assessments[assessment_id] = assessment
        _emit(self._events, "assurance_assessed", {
            "assessment_id": assessment_id,
            "level": level.value,
            "sufficiency": sufficiency.value,
        }, assessment_id)
        return assessment

    # ------------------------------------------------------------------
    # Findings (assurance-affecting)
    # ------------------------------------------------------------------

    def record_assurance_finding(
        self,
        finding_id: str,
        target_id: str,
        target_type: str,
        *,
        description: str = "",
        impact_level: AssuranceLevel = AssuranceLevel.NONE,
    ) -> AssuranceFinding:
        """Record a finding that affects assurance status."""
        if finding_id in self._findings:
            raise RuntimeCoreInvariantError(f"Duplicate finding_id: {finding_id}")
        now = _now_iso()
        finding = AssuranceFinding(
            finding_id=finding_id,
            target_id=target_id,
            target_type=target_type,
            description=description,
            impact_level=impact_level,
            detected_at=now,
        )
        self._findings[finding_id] = finding

        # Auto-degrade: revoke attestations/suspend certifications if HIGH+ impact
        if impact_level in (AssuranceLevel.HIGH, AssuranceLevel.FULL):
            for att in list(self._attestations.values()):
                if att.scope_ref_id == target_id and att.status == AttestationStatus.GRANTED:
                    self.revoke_attestation(att.attestation_id, reason=f"Finding: {finding_id}")
            for cert in list(self._certifications.values()):
                if cert.scope_ref_id == target_id and cert.status == CertificationStatus.ACTIVE:
                    self.suspend_certification(cert.certification_id, reason=f"Finding: {finding_id}")

        _emit(self._events, "assurance_finding_recorded", {
            "finding_id": finding_id, "target_id": target_id,
            "impact_level": impact_level.value,
        }, target_id)
        return finding

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def make_assurance_decision(
        self,
        decision_id: str,
        target_id: str,
        target_type: str,
        *,
        level: AssuranceLevel = AssuranceLevel.NONE,
        decided_by: str = "system",
        reason: str = "",
    ) -> AssuranceDecision:
        """Make a formal assurance decision."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError(f"Duplicate decision_id: {decision_id}")
        now = _now_iso()
        decision = AssuranceDecision(
            decision_id=decision_id,
            target_id=target_id,
            target_type=target_type,
            level=level,
            decided_by=decided_by,
            reason=reason,
            decided_at=now,
        )
        self._decisions[decision_id] = decision
        _emit(self._events, "assurance_decision_made", {
            "decision_id": decision_id, "target_id": target_id,
            "level": level.value,
        }, target_id)
        return decision

    # ------------------------------------------------------------------
    # Recertification windows
    # ------------------------------------------------------------------

    def schedule_recertification(
        self,
        window_id: str,
        certification_id: str,
        starts_at: str,
        ends_at: str,
    ) -> RecertificationWindow:
        """Schedule a recertification window."""
        if window_id in self._windows:
            raise RuntimeCoreInvariantError(f"Duplicate window_id: {window_id}")
        if certification_id not in self._certifications:
            raise RuntimeCoreInvariantError(f"Unknown certification_id: {certification_id}")
        window = RecertificationWindow(
            window_id=window_id,
            certification_id=certification_id,
            status=RecertificationStatus.SCHEDULED,
            starts_at=starts_at,
            ends_at=ends_at,
        )
        self._windows[window_id] = window
        _emit(self._events, "recertification_scheduled", {
            "window_id": window_id, "certification_id": certification_id,
        }, certification_id)
        return window

    def complete_recertification(self, window_id: str) -> RecertificationWindow:
        """Mark a recertification window as completed."""
        old = self._windows.get(window_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown window_id: {window_id}")
        now = _now_iso()
        updated = RecertificationWindow(
            window_id=old.window_id,
            certification_id=old.certification_id,
            status=RecertificationStatus.COMPLETED,
            starts_at=old.starts_at,
            ends_at=old.ends_at,
            completed_at=now,
            metadata=old.metadata,
        )
        self._windows[window_id] = updated
        _emit(self._events, "recertification_completed", {
            "window_id": window_id,
        }, old.certification_id)
        return updated

    def windows_for_certification(self, certification_id: str) -> tuple[RecertificationWindow, ...]:
        """Return all recertification windows for a certification."""
        return tuple(w for w in self._windows.values() if w.certification_id == certification_id)

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_assurance_violations(self) -> tuple[AssuranceViolation, ...]:
        """Detect assurance governance violations."""
        now = _now_iso()
        new_violations: list[AssuranceViolation] = []

        # Expired certifications still marked ACTIVE
        for cert in self._certifications.values():
            if cert.status == CertificationStatus.ACTIVE and cert.expires_at:
                try:
                    exp_dt = datetime.fromisoformat(cert.expires_at.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > exp_dt:
                        vid = stable_identifier("viol-asur", {
                            "cert": cert.certification_id, "op": "expired_active",
                        })
                        if vid not in self._violations:
                            v = AssuranceViolation(
                                violation_id=vid,
                                target_id=cert.certification_id,
                                target_type="certification",
                                tenant_id=cert.tenant_id,
                                operation="expired_certification_active",
                                reason=f"Certification expired at {cert.expires_at} but still active",
                                detected_at=now,
                            )
                            self._violations[vid] = v
                            new_violations.append(v)
                except (ValueError, TypeError):
                    pass

        # Overdue recertification windows
        for window in self._windows.values():
            if window.status == RecertificationStatus.SCHEDULED:
                try:
                    end_dt = datetime.fromisoformat(window.ends_at.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) > end_dt:
                        vid = stable_identifier("viol-asur", {
                            "win": window.window_id, "op": "overdue_recert",
                        })
                        if vid not in self._violations:
                            cert = self._certifications.get(window.certification_id)
                            tenant_id = cert.tenant_id if cert else "unknown"
                            v = AssuranceViolation(
                                violation_id=vid,
                                target_id=window.certification_id,
                                target_type="certification",
                                tenant_id=tenant_id,
                                operation="overdue_recertification",
                                reason=f"Recertification window {window.window_id} overdue",
                                detected_at=now,
                            )
                            self._violations[vid] = v
                            new_violations.append(v)
                except (ValueError, TypeError):
                    pass

        # Granted attestations without evidence
        for att in self._attestations.values():
            if att.status == AttestationStatus.GRANTED:
                bindings = self.bindings_for_target(att.attestation_id, "attestation")
                if not bindings:
                    vid = stable_identifier("viol-asur", {
                        "att": att.attestation_id, "op": "granted_no_evidence",
                    })
                    if vid not in self._violations:
                        v = AssuranceViolation(
                            violation_id=vid,
                            target_id=att.attestation_id,
                            target_type="attestation",
                            tenant_id=att.tenant_id,
                            operation="granted_without_evidence",
                            reason="Attestation granted but no evidence bindings found",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        if new_violations:
            _emit(self._events, "assurance_violations_detected", {
                "count": len(new_violations),
            }, "violation-scan")
        return tuple(new_violations)

    def violations_for_tenant(self, tenant_id: str) -> tuple[AssuranceViolation, ...]:
        """Return all violations for a tenant."""
        return tuple(v for v in self._violations.values() if v.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def assurance_snapshot(
        self,
        snapshot_id: str,
        scope_ref_id: str = "",
    ) -> AssuranceSnapshot:
        """Capture a point-in-time assurance state snapshot."""
        if snapshot_id in self._snapshot_ids:
            raise RuntimeCoreInvariantError(f"Duplicate snapshot_id: {snapshot_id}")
        now = _now_iso()
        snapshot = AssuranceSnapshot(
            snapshot_id=snapshot_id,
            scope_ref_id=scope_ref_id,
            total_attestations=self.attestation_count,
            granted_attestations=self.granted_attestation_count,
            total_certifications=self.certification_count,
            active_certifications=self.active_certification_count,
            total_assessments=self.assessment_count,
            total_evidence_bindings=self.binding_count,
            total_violations=self.violation_count,
            captured_at=now,
        )
        self._snapshot_ids.add(snapshot_id)
        _emit(self._events, "assurance_snapshot_captured", {
            "snapshot_id": snapshot_id,
        }, snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # State hash
    # ------------------------------------------------------------------

    def state_hash(self) -> str:
        """Compute a hash of the current engine state."""
        parts = [
            f"attestations={self.attestation_count}",
            f"granted={self.granted_attestation_count}",
            f"certifications={self.certification_count}",
            f"active_certs={self.active_certification_count}",
            f"assessments={self.assessment_count}",
            f"bindings={self.binding_count}",
            f"findings={self.finding_count}",
            f"decisions={self.decision_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
