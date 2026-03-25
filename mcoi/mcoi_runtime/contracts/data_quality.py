"""Purpose: data quality, schema evolution, and lineage runtime contracts.
Governance scope: typed descriptors for data quality records, schema versions,
    drift detections, lineage records, duplicate records, reconciliation,
    source quality policies, snapshots, violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Trust scores are derived from error counts.
  - Schema evolution follows CURRENT -> MIGRATING -> DEPRECATED -> RETIRED.
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


class DataQualityStatus(Enum):
    """Status of a data quality record."""
    CLEAN = "clean"
    DEGRADED = "degraded"
    DIRTY = "dirty"
    QUARANTINED = "quarantined"


class SchemaEvolutionStatus(Enum):
    """Status of a schema version."""
    CURRENT = "current"
    MIGRATING = "migrating"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class DriftSeverity(Enum):
    """Severity of a schema drift detection."""
    NONE = "none"
    MINOR = "minor"
    MAJOR = "major"
    BREAKING = "breaking"


class LineageDisposition(Enum):
    """Disposition of a lineage record."""
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    BROKEN = "broken"
    UNKNOWN = "unknown"


class DuplicateDisposition(Enum):
    """Disposition of a duplicate record."""
    UNIQUE = "unique"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"
    MERGED = "merged"


class TrustScore(Enum):
    """Trust score level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNTRUSTED = "untrusted"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DataQualityRecord(ContractRecord):
    """A data quality assessment record."""

    record_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    status: DataQualityStatus = DataQualityStatus.CLEAN
    trust_score: TrustScore = TrustScore.HIGH
    error_count: int = 0
    checked_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        if not isinstance(self.status, DataQualityStatus):
            raise ValueError("status must be a DataQualityStatus")
        if not isinstance(self.trust_score, TrustScore):
            raise ValueError("trust_score must be a TrustScore")
        object.__setattr__(self, "error_count", require_non_negative_int(self.error_count, "error_count"))
        require_datetime_text(self.checked_at, "checked_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SchemaVersion(ContractRecord):
    """A registered schema version."""

    version_id: str = ""
    tenant_id: str = ""
    schema_ref: str = ""
    status: SchemaEvolutionStatus = SchemaEvolutionStatus.CURRENT
    version_number: int = 0
    field_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "version_id", require_non_empty_text(self.version_id, "version_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "schema_ref", require_non_empty_text(self.schema_ref, "schema_ref"))
        if not isinstance(self.status, SchemaEvolutionStatus):
            raise ValueError("status must be a SchemaEvolutionStatus")
        object.__setattr__(self, "version_number", require_non_negative_int(self.version_number, "version_number"))
        object.__setattr__(self, "field_count", require_non_negative_int(self.field_count, "field_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DriftDetection(ContractRecord):
    """A schema drift detection event."""

    detection_id: str = ""
    tenant_id: str = ""
    schema_ref: str = ""
    severity: DriftSeverity = DriftSeverity.NONE
    field_name: str = ""
    expected_type: str = ""
    actual_type: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "detection_id", require_non_empty_text(self.detection_id, "detection_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "schema_ref", require_non_empty_text(self.schema_ref, "schema_ref"))
        if not isinstance(self.severity, DriftSeverity):
            raise ValueError("severity must be a DriftSeverity")
        object.__setattr__(self, "field_name", require_non_empty_text(self.field_name, "field_name"))
        object.__setattr__(self, "expected_type", require_non_empty_text(self.expected_type, "expected_type"))
        object.__setattr__(self, "actual_type", require_non_empty_text(self.actual_type, "actual_type"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LineageRecord(ContractRecord):
    """A data lineage record tracking source-to-target flows."""

    lineage_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    target_ref: str = ""
    disposition: LineageDisposition = LineageDisposition.UNVERIFIED
    hop_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "lineage_id", require_non_empty_text(self.lineage_id, "lineage_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "target_ref", require_non_empty_text(self.target_ref, "target_ref"))
        if not isinstance(self.disposition, LineageDisposition):
            raise ValueError("disposition must be a LineageDisposition")
        object.__setattr__(self, "hop_count", require_non_negative_int(self.hop_count, "hop_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DuplicateRecord(ContractRecord):
    """A duplicate detection record."""

    duplicate_id: str = ""
    tenant_id: str = ""
    record_ref_a: str = ""
    record_ref_b: str = ""
    disposition: DuplicateDisposition = DuplicateDisposition.SUSPECTED
    confidence: float = 0.0
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "duplicate_id", require_non_empty_text(self.duplicate_id, "duplicate_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "record_ref_a", require_non_empty_text(self.record_ref_a, "record_ref_a"))
        object.__setattr__(self, "record_ref_b", require_non_empty_text(self.record_ref_b, "record_ref_b"))
        if not isinstance(self.disposition, DuplicateDisposition):
            raise ValueError("disposition must be a DuplicateDisposition")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReconciliationRecord(ContractRecord):
    """A data reconciliation record."""

    reconciliation_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    canonical_ref: str = ""
    resolved: bool = False
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "reconciliation_id", require_non_empty_text(self.reconciliation_id, "reconciliation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "canonical_ref", require_non_empty_text(self.canonical_ref, "canonical_ref"))
        if not isinstance(self.resolved, bool):
            raise ValueError("resolved must be a bool")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SourceQualityPolicy(ContractRecord):
    """A source quality policy defining thresholds."""

    policy_id: str = ""
    tenant_id: str = ""
    source_ref: str = ""
    min_trust: TrustScore = TrustScore.MEDIUM
    max_errors: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        if not isinstance(self.min_trust, TrustScore):
            raise ValueError("min_trust must be a TrustScore")
        object.__setattr__(self, "max_errors", require_non_negative_int(self.max_errors, "max_errors"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DataQualitySnapshot(ContractRecord):
    """Point-in-time snapshot of data quality state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_records: int = 0
    total_schemas: int = 0
    total_drifts: int = 0
    total_duplicates: int = 0
    total_lineages: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_records", require_non_negative_int(self.total_records, "total_records"))
        object.__setattr__(self, "total_schemas", require_non_negative_int(self.total_schemas, "total_schemas"))
        object.__setattr__(self, "total_drifts", require_non_negative_int(self.total_drifts, "total_drifts"))
        object.__setattr__(self, "total_duplicates", require_non_negative_int(self.total_duplicates, "total_duplicates"))
        object.__setattr__(self, "total_lineages", require_non_negative_int(self.total_lineages, "total_lineages"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DataQualityViolation(ContractRecord):
    """A data quality violation."""

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
class DataQualityClosureReport(ContractRecord):
    """Closure report for data quality state."""

    report_id: str = ""
    tenant_id: str = ""
    total_records: int = 0
    total_schemas: int = 0
    total_drifts: int = 0
    total_duplicates: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_records", require_non_negative_int(self.total_records, "total_records"))
        object.__setattr__(self, "total_schemas", require_non_negative_int(self.total_schemas, "total_schemas"))
        object.__setattr__(self, "total_drifts", require_non_negative_int(self.total_drifts, "total_drifts"))
        object.__setattr__(self, "total_duplicates", require_non_negative_int(self.total_duplicates, "total_duplicates"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
