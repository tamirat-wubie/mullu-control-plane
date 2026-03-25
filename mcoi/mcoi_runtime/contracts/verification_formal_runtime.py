"""Purpose: formal verification runtime contracts.
Governance scope: typed descriptors for formal specifications, properties,
    verification runs, proof certificates, counter-examples, invariants,
    assessments, violations, snapshots, and closure reports for formal
    verification of runtime behaviors.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Property and specification lifecycles are enum-guarded.
  - Proof coverage is explicit and computable.
Note: uses FormalVerificationViolation, FormalVerificationSnapshot, and
    FormalVerificationClosureReport to avoid name conflicts with verification.py.
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


class FormalVerificationStatus(Enum):
    """Status of a verification run."""
    PENDING = "pending"
    PROVING = "proving"
    PROVEN = "proven"
    DISPROVEN = "disproven"
    TIMEOUT = "timeout"


class PropertyKind(Enum):
    """Kind of formal property being verified."""
    SAFETY = "safety"
    LIVENESS = "liveness"
    INVARIANT = "invariant"
    REACHABILITY = "reachability"
    DEADLOCK_FREE = "deadlock_free"


class ProofMethod(Enum):
    """Method used for formal verification."""
    MODEL_CHECK = "model_check"
    THEOREM_PROVE = "theorem_prove"
    ABSTRACT_INTERPRET = "abstract_interpret"
    BOUNDED_CHECK = "bounded_check"
    SIMULATION = "simulation"


class AssertionStatus(Enum):
    """Status of a formal assertion or property check."""
    HOLDS = "holds"
    VIOLATED = "violated"
    UNKNOWN = "unknown"
    VACUOUS = "vacuous"


class SpecificationStatus(Enum):
    """Lifecycle status of a formal specification."""
    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class VerificationRiskLevel(Enum):
    """Risk level for formal verification operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FormalSpecification(ContractRecord):
    """A formal specification describing expected runtime behavior."""

    spec_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    target_runtime: str = ""
    status: SpecificationStatus = SpecificationStatus.DRAFT
    property_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "spec_id", require_non_empty_text(self.spec_id, "spec_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        if not isinstance(self.status, SpecificationStatus):
            raise ValueError("status must be a SpecificationStatus")
        object.__setattr__(self, "property_count", require_non_negative_int(self.property_count, "property_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FormalProperty(ContractRecord):
    """A formal property within a specification."""

    property_id: str = ""
    tenant_id: str = ""
    spec_ref: str = ""
    kind: PropertyKind = PropertyKind.SAFETY
    expression: str = ""
    status: AssertionStatus = AssertionStatus.UNKNOWN
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "property_id", require_non_empty_text(self.property_id, "property_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "spec_ref", require_non_empty_text(self.spec_ref, "spec_ref"))
        if not isinstance(self.kind, PropertyKind):
            raise ValueError("kind must be a PropertyKind")
        object.__setattr__(self, "expression", require_non_empty_text(self.expression, "expression"))
        if not isinstance(self.status, AssertionStatus):
            raise ValueError("status must be an AssertionStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VerificationRun(ContractRecord):
    """A single verification run against a specification."""

    run_id: str = ""
    tenant_id: str = ""
    spec_ref: str = ""
    method: ProofMethod = ProofMethod.MODEL_CHECK
    status: FormalVerificationStatus = FormalVerificationStatus.PENDING
    duration_ms: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_non_empty_text(self.run_id, "run_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "spec_ref", require_non_empty_text(self.spec_ref, "spec_ref"))
        if not isinstance(self.method, ProofMethod):
            raise ValueError("method must be a ProofMethod")
        if not isinstance(self.status, FormalVerificationStatus):
            raise ValueError("status must be a FormalVerificationStatus")
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProofCertificate(ContractRecord):
    """A certificate proving a property holds or does not hold."""

    cert_id: str = ""
    tenant_id: str = ""
    run_ref: str = ""
    property_ref: str = ""
    proven: bool = False
    witness: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "cert_id", require_non_empty_text(self.cert_id, "cert_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "run_ref", require_non_empty_text(self.run_ref, "run_ref"))
        object.__setattr__(self, "property_ref", require_non_empty_text(self.property_ref, "property_ref"))
        if not isinstance(self.proven, bool):
            raise ValueError("proven must be a bool")
        object.__setattr__(self, "witness", require_non_empty_text(self.witness, "witness"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CounterExample(ContractRecord):
    """A counter-example demonstrating a property violation."""

    example_id: str = ""
    tenant_id: str = ""
    run_ref: str = ""
    property_ref: str = ""
    trace: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "example_id", require_non_empty_text(self.example_id, "example_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "run_ref", require_non_empty_text(self.run_ref, "run_ref"))
        object.__setattr__(self, "property_ref", require_non_empty_text(self.property_ref, "property_ref"))
        object.__setattr__(self, "trace", require_non_empty_text(self.trace, "trace"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InvariantRecord(ContractRecord):
    """A runtime invariant to be checked."""

    invariant_id: str = ""
    tenant_id: str = ""
    target_runtime: str = ""
    expression: str = ""
    status: AssertionStatus = AssertionStatus.UNKNOWN
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "invariant_id", require_non_empty_text(self.invariant_id, "invariant_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "expression", require_non_empty_text(self.expression, "expression"))
        if not isinstance(self.status, AssertionStatus):
            raise ValueError("status must be an AssertionStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VerificationAssessment(ContractRecord):
    """Assessment of formal verification coverage for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_specs: int = 0
    total_properties: int = 0
    total_proven: int = 0
    proof_coverage: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_specs", require_non_negative_int(self.total_specs, "total_specs"))
        object.__setattr__(self, "total_properties", require_non_negative_int(self.total_properties, "total_properties"))
        object.__setattr__(self, "total_proven", require_non_negative_int(self.total_proven, "total_proven"))
        object.__setattr__(self, "proof_coverage", require_unit_float(self.proof_coverage, "proof_coverage"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FormalVerificationViolation(ContractRecord):
    """A detected violation in the formal verification runtime."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FormalVerificationSnapshot(ContractRecord):
    """Point-in-time snapshot of formal verification runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_specs: int = 0
    total_properties: int = 0
    total_runs: int = 0
    total_certificates: int = 0
    total_counterexamples: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_specs", require_non_negative_int(self.total_specs, "total_specs"))
        object.__setattr__(self, "total_properties", require_non_negative_int(self.total_properties, "total_properties"))
        object.__setattr__(self, "total_runs", require_non_negative_int(self.total_runs, "total_runs"))
        object.__setattr__(self, "total_certificates", require_non_negative_int(self.total_certificates, "total_certificates"))
        object.__setattr__(self, "total_counterexamples", require_non_negative_int(self.total_counterexamples, "total_counterexamples"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FormalVerificationClosureReport(ContractRecord):
    """Closure report for formal verification runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_specs: int = 0
    total_properties: int = 0
    total_proven: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_specs", require_non_negative_int(self.total_specs, "total_specs"))
        object.__setattr__(self, "total_properties", require_non_negative_int(self.total_properties, "total_properties"))
        object.__setattr__(self, "total_proven", require_non_negative_int(self.total_proven, "total_proven"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
