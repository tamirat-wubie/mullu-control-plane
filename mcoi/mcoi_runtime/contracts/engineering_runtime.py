"""Purpose: engineering quantities / systems constraints runtime contracts.
Governance scope: typed descriptors for engineering quantities, tolerances,
    reliability targets, safety margins, load envelopes, process windows,
    capacity curves, snapshots, violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Float(any) fields accept int/float but reject bool.
  - Non-negative float fields reject negative values.
  - Unit float fields are clamped to [0.0, 1.0].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_finite_float,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EngineeringDomain(Enum):
    """Domain of engineering discipline."""
    MECHANICAL = "mechanical"
    ELECTRICAL = "electrical"
    THERMAL = "thermal"
    CHEMICAL = "chemical"
    STRUCTURAL = "structural"
    PROCESS = "process"


class ToleranceStatus(Enum):
    """Status of a tolerance check."""
    WITHIN = "within"
    WARNING = "warning"
    EXCEEDED = "exceeded"
    CRITICAL = "critical"


class ReliabilityGrade(Enum):
    """Reliability grade for a component."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class SafetyMarginStatus(Enum):
    """Status of a safety margin assessment."""
    ADEQUATE = "adequate"
    MARGINAL = "marginal"
    INSUFFICIENT = "insufficient"
    UNKNOWN = "unknown"


class LoadEnvelopeStatus(Enum):
    """Status of a load envelope measurement."""
    NOMINAL = "nominal"
    ELEVATED = "elevated"
    OVERLOAD = "overload"
    FAILURE = "failure"


class ProcessWindowStatus(Enum):
    """Status of a process window measurement."""
    IN_SPEC = "in_spec"
    DRIFT = "drift"
    OUT_OF_SPEC = "out_of_spec"
    SHUTDOWN = "shutdown"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EngineeringQuantity(ContractRecord):
    """A registered engineering quantity with unit and tolerance."""

    quantity_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    value: float = 0.0
    unit_label: str = ""
    domain: EngineeringDomain = EngineeringDomain.MECHANICAL
    tolerance: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity_id", require_non_empty_text(self.quantity_id, "quantity_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "value", require_finite_float(self.value, "value"))
        object.__setattr__(self, "unit_label", require_non_empty_text(self.unit_label, "unit_label"))
        if not isinstance(self.domain, EngineeringDomain):
            raise ValueError("domain must be an EngineeringDomain")
        object.__setattr__(self, "tolerance", require_non_negative_float(self.tolerance, "tolerance"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ToleranceRecord(ContractRecord):
    """A tolerance check record for an engineering quantity."""

    tolerance_id: str = ""
    tenant_id: str = ""
    quantity_ref: str = ""
    nominal: float = 0.0
    lower_limit: float = 0.0
    upper_limit: float = 0.0
    status: ToleranceStatus = ToleranceStatus.WITHIN
    checked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "tolerance_id", require_non_empty_text(self.tolerance_id, "tolerance_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "quantity_ref", require_non_empty_text(self.quantity_ref, "quantity_ref"))
        object.__setattr__(self, "nominal", require_finite_float(self.nominal, "nominal"))
        object.__setattr__(self, "lower_limit", require_finite_float(self.lower_limit, "lower_limit"))
        object.__setattr__(self, "upper_limit", require_finite_float(self.upper_limit, "upper_limit"))
        if not isinstance(self.status, ToleranceStatus):
            raise ValueError("status must be a ToleranceStatus")
        require_datetime_text(self.checked_at, "checked_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReliabilityTarget(ContractRecord):
    """A reliability target for a component."""

    target_id: str = ""
    tenant_id: str = ""
    component_ref: str = ""
    grade: ReliabilityGrade = ReliabilityGrade.A
    mtbf_hours: float = 0.0
    target_availability: float = 1.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "component_ref", require_non_empty_text(self.component_ref, "component_ref"))
        if not isinstance(self.grade, ReliabilityGrade):
            raise ValueError("grade must be a ReliabilityGrade")
        object.__setattr__(self, "mtbf_hours", require_non_negative_float(self.mtbf_hours, "mtbf_hours"))
        object.__setattr__(self, "target_availability", require_unit_float(self.target_availability, "target_availability"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SafetyMargin(ContractRecord):
    """A safety margin assessment for a component."""

    margin_id: str = ""
    tenant_id: str = ""
    component_ref: str = ""
    design_load: float = 0.0
    actual_load: float = 0.0
    margin_ratio: float = 0.0
    status: SafetyMarginStatus = SafetyMarginStatus.UNKNOWN
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "margin_id", require_non_empty_text(self.margin_id, "margin_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "component_ref", require_non_empty_text(self.component_ref, "component_ref"))
        object.__setattr__(self, "design_load", require_non_negative_float(self.design_load, "design_load"))
        object.__setattr__(self, "actual_load", require_non_negative_float(self.actual_load, "actual_load"))
        object.__setattr__(self, "margin_ratio", require_non_negative_float(self.margin_ratio, "margin_ratio"))
        if not isinstance(self.status, SafetyMarginStatus):
            raise ValueError("status must be a SafetyMarginStatus")
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LoadEnvelope(ContractRecord):
    """A load envelope measurement for a component."""

    envelope_id: str = ""
    tenant_id: str = ""
    component_ref: str = ""
    max_load: float = 0.0
    current_load: float = 0.0
    status: LoadEnvelopeStatus = LoadEnvelopeStatus.NOMINAL
    measured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "envelope_id", require_non_empty_text(self.envelope_id, "envelope_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "component_ref", require_non_empty_text(self.component_ref, "component_ref"))
        object.__setattr__(self, "max_load", require_non_negative_float(self.max_load, "max_load"))
        object.__setattr__(self, "current_load", require_non_negative_float(self.current_load, "current_load"))
        if not isinstance(self.status, LoadEnvelopeStatus):
            raise ValueError("status must be a LoadEnvelopeStatus")
        require_datetime_text(self.measured_at, "measured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcessWindow(ContractRecord):
    """A process window measurement for a process."""

    window_id: str = ""
    tenant_id: str = ""
    process_ref: str = ""
    target_value: float = 0.0
    lower_spec: float = 0.0
    upper_spec: float = 0.0
    actual_value: float = 0.0
    status: ProcessWindowStatus = ProcessWindowStatus.IN_SPEC
    measured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "process_ref", require_non_empty_text(self.process_ref, "process_ref"))
        object.__setattr__(self, "target_value", require_finite_float(self.target_value, "target_value"))
        object.__setattr__(self, "lower_spec", require_finite_float(self.lower_spec, "lower_spec"))
        object.__setattr__(self, "upper_spec", require_finite_float(self.upper_spec, "upper_spec"))
        object.__setattr__(self, "actual_value", require_finite_float(self.actual_value, "actual_value"))
        if not isinstance(self.status, ProcessWindowStatus):
            raise ValueError("status must be a ProcessWindowStatus")
        require_datetime_text(self.measured_at, "measured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CapacityCurve(ContractRecord):
    """A capacity curve for a component."""

    curve_id: str = ""
    tenant_id: str = ""
    component_ref: str = ""
    max_capacity: float = 0.0
    current_utilization: float = 0.0
    headroom: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "curve_id", require_non_empty_text(self.curve_id, "curve_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "component_ref", require_non_empty_text(self.component_ref, "component_ref"))
        object.__setattr__(self, "max_capacity", require_non_negative_float(self.max_capacity, "max_capacity"))
        object.__setattr__(self, "current_utilization", require_unit_float(self.current_utilization, "current_utilization"))
        object.__setattr__(self, "headroom", require_non_negative_float(self.headroom, "headroom"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EngineeringSnapshot(ContractRecord):
    """Point-in-time snapshot of engineering runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_quantities: int = 0
    total_tolerances: int = 0
    total_targets: int = 0
    total_margins: int = 0
    total_envelopes: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_quantities", require_non_negative_int(self.total_quantities, "total_quantities"))
        object.__setattr__(self, "total_tolerances", require_non_negative_int(self.total_tolerances, "total_tolerances"))
        object.__setattr__(self, "total_targets", require_non_negative_int(self.total_targets, "total_targets"))
        object.__setattr__(self, "total_margins", require_non_negative_int(self.total_margins, "total_margins"))
        object.__setattr__(self, "total_envelopes", require_non_negative_int(self.total_envelopes, "total_envelopes"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EngineeringViolation(ContractRecord):
    """A violation detected in the engineering runtime."""

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
class EngineeringClosureReport(ContractRecord):
    """Final closure report for engineering runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_quantities: int = 0
    total_tolerances: int = 0
    total_targets: int = 0
    total_margins: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_quantities", require_non_negative_int(self.total_quantities, "total_quantities"))
        object.__setattr__(self, "total_tolerances", require_non_negative_int(self.total_tolerances, "total_tolerances"))
        object.__setattr__(self, "total_targets", require_non_negative_int(self.total_targets, "total_targets"))
        object.__setattr__(self, "total_margins", require_non_negative_int(self.total_margins, "total_margins"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
