"""Purpose: assurance / attestation / certification runtime contracts.
Governance scope: typed descriptors for attestations, certifications,
    assurance assessments, evidence bindings, recertification windows,
    findings, decisions, snapshots, violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every attestation has explicit scope and level.
  - Certification requires sufficient evidence.
  - Expired certifications degrade automatically.
  - Assurance revocation requires explicit decision.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AttestationStatus(Enum):
    """Status of an attestation."""
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    REVOKED = "revoked"
    EXPIRED = "expired"


class CertificationStatus(Enum):
    """Status of a certification."""
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    EXPIRED = "expired"
    RECERTIFICATION_REQUIRED = "recertification_required"


class AssuranceLevel(Enum):
    """Level of assurance granted."""
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    FULL = "full"


class AssuranceScope(Enum):
    """Scope of an assurance assessment."""
    CONTROL = "control"
    PROGRAM = "program"
    WORKSPACE = "workspace"
    TENANT = "tenant"
    CONNECTOR = "connector"
    CAMPAIGN = "campaign"


class EvidenceSufficiency(Enum):
    """Sufficiency of evidence for assurance."""
    INSUFFICIENT = "insufficient"
    PARTIAL = "partial"
    SUFFICIENT = "sufficient"
    COMPREHENSIVE = "comprehensive"


class RecertificationStatus(Enum):
    """Status of a recertification window."""
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    OVERDUE = "overdue"
    WAIVED = "waived"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AttestationRecord(ContractRecord):
    """A formal attestation of assurance."""

    attestation_id: str = ""
    tenant_id: str = ""
    scope: AssuranceScope = AssuranceScope.CONTROL
    scope_ref_id: str = ""
    level: AssuranceLevel = AssuranceLevel.NONE
    status: AttestationStatus = AttestationStatus.PENDING
    attested_by: str = ""
    attested_at: str = ""
    expires_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "attestation_id", require_non_empty_text(self.attestation_id, "attestation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, AssuranceScope):
            raise ValueError("scope must be an AssuranceScope")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        if not isinstance(self.level, AssuranceLevel):
            raise ValueError("level must be an AssuranceLevel")
        if not isinstance(self.status, AttestationStatus):
            raise ValueError("status must be an AttestationStatus")
        object.__setattr__(self, "attested_by", require_non_empty_text(self.attested_by, "attested_by"))
        require_datetime_text(self.attested_at, "attested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CertificationRecord(ContractRecord):
    """A formal certification of a scope."""

    certification_id: str = ""
    tenant_id: str = ""
    scope: AssuranceScope = AssuranceScope.CONTROL
    scope_ref_id: str = ""
    status: CertificationStatus = CertificationStatus.PENDING
    level: AssuranceLevel = AssuranceLevel.NONE
    certified_by: str = ""
    certified_at: str = ""
    expires_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "certification_id", require_non_empty_text(self.certification_id, "certification_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, AssuranceScope):
            raise ValueError("scope must be an AssuranceScope")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        if not isinstance(self.status, CertificationStatus):
            raise ValueError("status must be a CertificationStatus")
        if not isinstance(self.level, AssuranceLevel):
            raise ValueError("level must be an AssuranceLevel")
        object.__setattr__(self, "certified_by", require_non_empty_text(self.certified_by, "certified_by"))
        require_datetime_text(self.certified_at, "certified_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssuranceAssessment(ContractRecord):
    """An assessment of assurance for a scope."""

    assessment_id: str = ""
    tenant_id: str = ""
    scope: AssuranceScope = AssuranceScope.CONTROL
    scope_ref_id: str = ""
    level: AssuranceLevel = AssuranceLevel.NONE
    sufficiency: EvidenceSufficiency = EvidenceSufficiency.INSUFFICIENT
    confidence: float = 0.0
    assessed_by: str = ""
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.scope, AssuranceScope):
            raise ValueError("scope must be an AssuranceScope")
        object.__setattr__(self, "scope_ref_id", require_non_empty_text(self.scope_ref_id, "scope_ref_id"))
        if not isinstance(self.level, AssuranceLevel):
            raise ValueError("level must be an AssuranceLevel")
        if not isinstance(self.sufficiency, EvidenceSufficiency):
            raise ValueError("sufficiency must be an EvidenceSufficiency")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        object.__setattr__(self, "assessed_by", require_non_empty_text(self.assessed_by, "assessed_by"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssuranceEvidenceBinding(ContractRecord):
    """A binding of evidence to an attestation or certification."""

    binding_id: str = ""
    target_id: str = ""
    target_type: str = ""
    source_type: str = ""
    source_id: str = ""
    bound_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "target_type", require_non_empty_text(self.target_type, "target_type"))
        object.__setattr__(self, "source_type", require_non_empty_text(self.source_type, "source_type"))
        object.__setattr__(self, "source_id", require_non_empty_text(self.source_id, "source_id"))
        require_datetime_text(self.bound_at, "bound_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RecertificationWindow(ContractRecord):
    """A scheduled recertification window."""

    window_id: str = ""
    certification_id: str = ""
    status: RecertificationStatus = RecertificationStatus.SCHEDULED
    starts_at: str = ""
    ends_at: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "certification_id", require_non_empty_text(self.certification_id, "certification_id"))
        if not isinstance(self.status, RecertificationStatus):
            raise ValueError("status must be a RecertificationStatus")
        require_datetime_text(self.starts_at, "starts_at")
        require_datetime_text(self.ends_at, "ends_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssuranceFinding(ContractRecord):
    """A finding that affects assurance status."""

    finding_id: str = ""
    target_id: str = ""
    target_type: str = ""
    description: str = ""
    impact_level: AssuranceLevel = AssuranceLevel.NONE
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "finding_id", require_non_empty_text(self.finding_id, "finding_id"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "target_type", require_non_empty_text(self.target_type, "target_type"))
        if not isinstance(self.impact_level, AssuranceLevel):
            raise ValueError("impact_level must be an AssuranceLevel")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssuranceDecision(ContractRecord):
    """A formal assurance decision."""

    decision_id: str = ""
    target_id: str = ""
    target_type: str = ""
    level: AssuranceLevel = AssuranceLevel.NONE
    decided_by: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "target_type", require_non_empty_text(self.target_type, "target_type"))
        if not isinstance(self.level, AssuranceLevel):
            raise ValueError("level must be an AssuranceLevel")
        object.__setattr__(self, "decided_by", require_non_empty_text(self.decided_by, "decided_by"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssuranceSnapshot(ContractRecord):
    """Point-in-time assurance state snapshot."""

    snapshot_id: str = ""
    scope_ref_id: str = ""
    total_attestations: int = 0
    granted_attestations: int = 0
    total_certifications: int = 0
    active_certifications: int = 0
    total_assessments: int = 0
    total_evidence_bindings: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "total_attestations", require_non_negative_int(self.total_attestations, "total_attestations"))
        object.__setattr__(self, "granted_attestations", require_non_negative_int(self.granted_attestations, "granted_attestations"))
        object.__setattr__(self, "total_certifications", require_non_negative_int(self.total_certifications, "total_certifications"))
        object.__setattr__(self, "active_certifications", require_non_negative_int(self.active_certifications, "active_certifications"))
        object.__setattr__(self, "total_assessments", require_non_negative_int(self.total_assessments, "total_assessments"))
        object.__setattr__(self, "total_evidence_bindings", require_non_negative_int(self.total_evidence_bindings, "total_evidence_bindings"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssuranceViolation(ContractRecord):
    """A detected assurance governance violation."""

    violation_id: str = ""
    target_id: str = ""
    target_type: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "target_type", require_non_empty_text(self.target_type, "target_type"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssuranceClosureReport(ContractRecord):
    """Summary report for assurance closure."""

    report_id: str = ""
    target_id: str = ""
    target_type: str = ""
    tenant_id: str = ""
    final_level: AssuranceLevel = AssuranceLevel.NONE
    total_evidence_bindings: int = 0
    total_assessments: int = 0
    total_findings: int = 0
    total_violations: int = 0
    closed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "target_type", require_non_empty_text(self.target_type, "target_type"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.final_level, AssuranceLevel):
            raise ValueError("final_level must be an AssuranceLevel")
        object.__setattr__(self, "total_evidence_bindings", require_non_negative_int(self.total_evidence_bindings, "total_evidence_bindings"))
        object.__setattr__(self, "total_assessments", require_non_negative_int(self.total_assessments, "total_assessments"))
        object.__setattr__(self, "total_findings", require_non_negative_int(self.total_findings, "total_findings"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.closed_at, "closed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
