"""Purpose: risk / compliance / controls runtime contracts.
Governance scope: typed descriptors for risks, controls, control bindings,
    test outcomes, compliance requirements, exceptions, risk assessments,
    compliance snapshots, control failures, and assurance reports.
Dependencies: _base contract utilities.
Invariants:
  - Every risk has explicit severity and category.
  - Controls bind to scoped entities and require test evidence.
  - Exceptions are time-bounded and require approval.
  - Compliance snapshots aggregate control status.
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
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RiskSeverity(Enum):
    """Severity level of a risk."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class RiskCategory(Enum):
    """Category of risk."""
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    SECURITY = "security"
    REPUTATIONAL = "reputational"
    STRATEGIC = "strategic"
    TECHNICAL = "technical"


class ControlStatus(Enum):
    """Status of a control."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    FAILED = "failed"
    REMEDIATION = "remediation"
    RETIRED = "retired"


class ControlTestStatus(Enum):
    """Outcome of a control test."""
    PASSED = "passed"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    ERROR = "error"


class ExceptionStatus(Enum):
    """Status of a compliance exception."""
    REQUESTED = "requested"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ComplianceDisposition(Enum):
    """Compliance disposition for a scope."""
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    EXCEPTION_GRANTED = "exception_granted"
    NOT_ASSESSED = "not_assessed"


class EvidenceSourceKind(Enum):
    """Source kind for compliance evidence."""
    ARTIFACT = "artifact"
    EVENT = "event"
    MEMORY = "memory"
    TEST_RESULT = "test_result"
    MANUAL_ATTESTATION = "manual_attestation"
    AUDIT_LOG = "audit_log"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RiskRecord(ContractRecord):
    """A registered risk in the risk register."""

    risk_id: str = ""
    title: str = ""
    description: str = ""
    severity: RiskSeverity = RiskSeverity.MEDIUM
    category: RiskCategory = RiskCategory.OPERATIONAL
    likelihood: float = 0.0
    impact: float = 0.0
    scope_ref_id: str = ""
    owner: str = ""
    mitigations: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "risk_id", require_non_empty_text(self.risk_id, "risk_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.severity, RiskSeverity):
            raise ValueError("severity must be a RiskSeverity")
        if not isinstance(self.category, RiskCategory):
            raise ValueError("category must be a RiskCategory")
        object.__setattr__(self, "likelihood", require_unit_float(self.likelihood, "likelihood"))
        object.__setattr__(self, "impact", require_unit_float(self.impact, "impact"))
        object.__setattr__(self, "mitigations", freeze_value(list(self.mitigations)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ControlRecord(ContractRecord):
    """A compliance control."""

    control_id: str = ""
    title: str = ""
    description: str = ""
    status: ControlStatus = ControlStatus.ACTIVE
    requirement_id: str = ""
    test_frequency_seconds: float = 86400.0
    last_tested_at: str = ""
    owner: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "control_id", require_non_empty_text(self.control_id, "control_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.status, ControlStatus):
            raise ValueError("status must be a ControlStatus")
        object.__setattr__(self, "test_frequency_seconds", require_non_negative_float(self.test_frequency_seconds, "test_frequency_seconds"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ControlBinding(ContractRecord):
    """Binds a control to a scoped entity."""

    binding_id: str = ""
    control_id: str = ""
    scope_ref_id: str = ""
    scope_type: str = ""
    enforced: bool = True
    bound_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "control_id", require_non_empty_text(self.control_id, "control_id"))
        if not isinstance(self.enforced, bool):
            raise ValueError("enforced must be a boolean")
        require_datetime_text(self.bound_at, "bound_at")


@dataclass(frozen=True, slots=True)
class ControlTestRecord(ContractRecord):
    """Record of a control test execution."""

    test_id: str = ""
    control_id: str = ""
    status: ControlTestStatus = ControlTestStatus.PASSED
    evidence_refs: tuple[str, ...] = ()
    tester: str = ""
    notes: str = ""
    tested_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "test_id", require_non_empty_text(self.test_id, "test_id"))
        object.__setattr__(self, "control_id", require_non_empty_text(self.control_id, "control_id"))
        if not isinstance(self.status, ControlTestStatus):
            raise ValueError("status must be a ControlTestStatus")
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))
        require_datetime_text(self.tested_at, "tested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ComplianceRequirement(ContractRecord):
    """A compliance requirement that must be satisfied."""

    requirement_id: str = ""
    title: str = ""
    description: str = ""
    category: RiskCategory = RiskCategory.COMPLIANCE
    mandatory: bool = True
    control_ids: tuple[str, ...] = ()
    evidence_source_kinds: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_id", require_non_empty_text(self.requirement_id, "requirement_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        if not isinstance(self.category, RiskCategory):
            raise ValueError("category must be a RiskCategory")
        if not isinstance(self.mandatory, bool):
            raise ValueError("mandatory must be a boolean")
        object.__setattr__(self, "control_ids", freeze_value(list(self.control_ids)))
        object.__setattr__(self, "evidence_source_kinds", freeze_value(list(self.evidence_source_kinds)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExceptionRequest(ContractRecord):
    """A request for a temporary compliance exception."""

    exception_id: str = ""
    control_id: str = ""
    scope_ref_id: str = ""
    status: ExceptionStatus = ExceptionStatus.REQUESTED
    reason: str = ""
    requested_by: str = ""
    approved_by: str = ""
    expires_at: str = ""
    requested_at: str = ""
    resolved_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "exception_id", require_non_empty_text(self.exception_id, "exception_id"))
        object.__setattr__(self, "control_id", require_non_empty_text(self.control_id, "control_id"))
        if not isinstance(self.status, ExceptionStatus):
            raise ValueError("status must be an ExceptionStatus")
        require_datetime_text(self.requested_at, "requested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RiskAssessment(ContractRecord):
    """Assessment of risk for a specific scope."""

    assessment_id: str = ""
    scope_ref_id: str = ""
    overall_severity: RiskSeverity = RiskSeverity.LOW
    risk_count: int = 0
    critical_risks: int = 0
    high_risks: int = 0
    unmitigated_risks: int = 0
    risk_score: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        if not isinstance(self.overall_severity, RiskSeverity):
            raise ValueError("overall_severity must be a RiskSeverity")
        object.__setattr__(self, "risk_count", require_non_negative_int(self.risk_count, "risk_count"))
        object.__setattr__(self, "critical_risks", require_non_negative_int(self.critical_risks, "critical_risks"))
        object.__setattr__(self, "high_risks", require_non_negative_int(self.high_risks, "high_risks"))
        object.__setattr__(self, "unmitigated_risks", require_non_negative_int(self.unmitigated_risks, "unmitigated_risks"))
        object.__setattr__(self, "risk_score", require_unit_float(self.risk_score, "risk_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ComplianceSnapshot(ContractRecord):
    """Point-in-time compliance snapshot for a scope."""

    snapshot_id: str = ""
    scope_ref_id: str = ""
    disposition: ComplianceDisposition = ComplianceDisposition.NOT_ASSESSED
    total_controls: int = 0
    passing_controls: int = 0
    failing_controls: int = 0
    exceptions_active: int = 0
    compliance_pct: float = 0.0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        if not isinstance(self.disposition, ComplianceDisposition):
            raise ValueError("disposition must be a ComplianceDisposition")
        object.__setattr__(self, "total_controls", require_non_negative_int(self.total_controls, "total_controls"))
        object.__setattr__(self, "passing_controls", require_non_negative_int(self.passing_controls, "passing_controls"))
        object.__setattr__(self, "failing_controls", require_non_negative_int(self.failing_controls, "failing_controls"))
        object.__setattr__(self, "exceptions_active", require_non_negative_int(self.exceptions_active, "exceptions_active"))
        object.__setattr__(self, "compliance_pct", require_non_negative_float(self.compliance_pct, "compliance_pct"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ControlFailure(ContractRecord):
    """Record of a control failure."""

    failure_id: str = ""
    control_id: str = ""
    test_id: str = ""
    scope_ref_id: str = ""
    severity: RiskSeverity = RiskSeverity.MEDIUM
    action_taken: str = ""
    escalated: bool = False
    blocked: bool = False
    recorded_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "failure_id", require_non_empty_text(self.failure_id, "failure_id"))
        object.__setattr__(self, "control_id", require_non_empty_text(self.control_id, "control_id"))
        if not isinstance(self.severity, RiskSeverity):
            raise ValueError("severity must be a RiskSeverity")
        if not isinstance(self.escalated, bool):
            raise ValueError("escalated must be a boolean")
        if not isinstance(self.blocked, bool):
            raise ValueError("blocked must be a boolean")
        require_datetime_text(self.recorded_at, "recorded_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssuranceReport(ContractRecord):
    """Overall assurance report across scopes."""

    report_id: str = ""
    scope_ref_id: str = ""
    overall_disposition: ComplianceDisposition = ComplianceDisposition.NOT_ASSESSED
    overall_risk_severity: RiskSeverity = RiskSeverity.LOW
    total_requirements: int = 0
    met_requirements: int = 0
    total_controls: int = 0
    passing_controls: int = 0
    failing_controls: int = 0
    active_exceptions: int = 0
    total_failures: int = 0
    risk_score: float = 0.0
    compliance_pct: float = 0.0
    generated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        if not isinstance(self.overall_disposition, ComplianceDisposition):
            raise ValueError("overall_disposition must be a ComplianceDisposition")
        if not isinstance(self.overall_risk_severity, RiskSeverity):
            raise ValueError("overall_risk_severity must be a RiskSeverity")
        object.__setattr__(self, "total_requirements", require_non_negative_int(self.total_requirements, "total_requirements"))
        object.__setattr__(self, "met_requirements", require_non_negative_int(self.met_requirements, "met_requirements"))
        object.__setattr__(self, "total_controls", require_non_negative_int(self.total_controls, "total_controls"))
        object.__setattr__(self, "passing_controls", require_non_negative_int(self.passing_controls, "passing_controls"))
        object.__setattr__(self, "failing_controls", require_non_negative_int(self.failing_controls, "failing_controls"))
        object.__setattr__(self, "active_exceptions", require_non_negative_int(self.active_exceptions, "active_exceptions"))
        object.__setattr__(self, "total_failures", require_non_negative_int(self.total_failures, "total_failures"))
        object.__setattr__(self, "risk_score", require_unit_float(self.risk_score, "risk_score"))
        object.__setattr__(self, "compliance_pct", require_non_negative_float(self.compliance_pct, "compliance_pct"))
        require_datetime_text(self.generated_at, "generated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
