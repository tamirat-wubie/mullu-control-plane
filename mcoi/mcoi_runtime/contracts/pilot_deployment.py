"""Purpose: pilot deployment / tenant bootstrap / live connector activation contracts.
Governance scope: typed descriptors for tenant bootstrapping, connector activation,
    data migration, pilot lifecycle, go-live readiness, runbook entries, SLO
    definitions, pilot assessments, violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every bootstrap, connector, migration, and pilot record is immutable.
  - Status enums gate all state transitions.
  - Numeric fields are validated at construction time.
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


class BootstrapStatus(Enum):
    """Status of a tenant bootstrap operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ConnectorActivationStatus(Enum):
    """Status of a connector activation."""
    INACTIVE = "inactive"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEGRADED = "degraded"
    FAILED = "failed"


class MigrationStatus(Enum):
    """Status of a data migration."""
    PENDING = "pending"
    VALIDATING = "validating"
    IMPORTING = "importing"
    COMPLETED = "completed"
    FAILED = "failed"


class PilotPhase(Enum):
    """Phase of a pilot deployment."""
    SETUP = "setup"
    ONBOARDING = "onboarding"
    ACTIVE_USE = "active_use"
    EVALUATION = "evaluation"
    GRADUATED = "graduated"


class GoLiveReadiness(Enum):
    """Readiness level for go-live."""
    NOT_READY = "not_ready"
    PARTIAL = "partial"
    READY = "ready"
    LIVE = "live"


class PilotRiskLevel(Enum):
    """Risk level for a pilot deployment."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TenantBootstrap(ContractRecord):
    """A tenant bootstrap operation record."""

    bootstrap_id: str = ""
    tenant_id: str = ""
    pack_ref: str = ""
    status: BootstrapStatus = BootstrapStatus.PENDING
    workspace_count: int = 0
    connector_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bootstrap_id", require_non_empty_text(self.bootstrap_id, "bootstrap_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "pack_ref", require_non_empty_text(self.pack_ref, "pack_ref"))
        if not isinstance(self.status, BootstrapStatus):
            raise ValueError("status must be a BootstrapStatus")
        object.__setattr__(self, "workspace_count", require_non_negative_int(self.workspace_count, "workspace_count"))
        object.__setattr__(self, "connector_count", require_non_negative_int(self.connector_count, "connector_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConnectorActivation(ContractRecord):
    """A connector activation record."""

    activation_id: str = ""
    tenant_id: str = ""
    connector_type: str = ""
    target_url: str = ""
    status: ConnectorActivationStatus = ConnectorActivationStatus.INACTIVE
    health_check_passed: bool = False
    activated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "activation_id", require_non_empty_text(self.activation_id, "activation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "connector_type", require_non_empty_text(self.connector_type, "connector_type"))
        object.__setattr__(self, "target_url", require_non_empty_text(self.target_url, "target_url"))
        if not isinstance(self.status, ConnectorActivationStatus):
            raise ValueError("status must be a ConnectorActivationStatus")
        if not isinstance(self.health_check_passed, bool):
            raise ValueError("health_check_passed must be a boolean")
        require_datetime_text(self.activated_at, "activated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DataMigration(ContractRecord):
    """A data migration record."""

    migration_id: str = ""
    tenant_id: str = ""
    source_system: str = ""
    record_count: int = 0
    imported_count: int = 0
    failed_count: int = 0
    status: MigrationStatus = MigrationStatus.PENDING
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "migration_id", require_non_empty_text(self.migration_id, "migration_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "source_system", require_non_empty_text(self.source_system, "source_system"))
        object.__setattr__(self, "record_count", require_non_negative_int(self.record_count, "record_count"))
        object.__setattr__(self, "imported_count", require_non_negative_int(self.imported_count, "imported_count"))
        object.__setattr__(self, "failed_count", require_non_negative_int(self.failed_count, "failed_count"))
        if not isinstance(self.status, MigrationStatus):
            raise ValueError("status must be a MigrationStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PilotRecord(ContractRecord):
    """A pilot deployment record."""

    pilot_id: str = ""
    tenant_id: str = ""
    pack_ref: str = ""
    phase: PilotPhase = PilotPhase.SETUP
    started_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "pilot_id", require_non_empty_text(self.pilot_id, "pilot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "pack_ref", require_non_empty_text(self.pack_ref, "pack_ref"))
        if not isinstance(self.phase, PilotPhase):
            raise ValueError("phase must be a PilotPhase")
        require_datetime_text(self.started_at, "started_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GoLiveChecklist(ContractRecord):
    """A go-live readiness checklist."""

    checklist_id: str = ""
    tenant_id: str = ""
    pilot_ref: str = ""
    total_items: int = 0
    passed_items: int = 0
    readiness: GoLiveReadiness = GoLiveReadiness.NOT_READY
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "checklist_id", require_non_empty_text(self.checklist_id, "checklist_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "pilot_ref", require_non_empty_text(self.pilot_ref, "pilot_ref"))
        object.__setattr__(self, "total_items", require_non_negative_int(self.total_items, "total_items"))
        object.__setattr__(self, "passed_items", require_non_negative_int(self.passed_items, "passed_items"))
        if not isinstance(self.readiness, GoLiveReadiness):
            raise ValueError("readiness must be a GoLiveReadiness")
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RunbookEntry(ContractRecord):
    """A runbook procedure entry."""

    entry_id: str = ""
    tenant_id: str = ""
    title: str = ""
    category: str = ""
    procedure: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", require_non_empty_text(self.entry_id, "entry_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "title", require_non_empty_text(self.title, "title"))
        object.__setattr__(self, "category", require_non_empty_text(self.category, "category"))
        object.__setattr__(self, "procedure", require_non_empty_text(self.procedure, "procedure"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SloDefinition(ContractRecord):
    """A service-level objective definition."""

    slo_id: str = ""
    tenant_id: str = ""
    metric_name: str = ""
    target_value: float = 0.0
    current_value: float = 0.0
    unit: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "slo_id", require_non_empty_text(self.slo_id, "slo_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "metric_name", require_non_empty_text(self.metric_name, "metric_name"))
        object.__setattr__(self, "target_value", require_non_negative_float(self.target_value, "target_value"))
        object.__setattr__(self, "current_value", require_non_negative_float(self.current_value, "current_value"))
        object.__setattr__(self, "unit", require_non_empty_text(self.unit, "unit"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PilotAssessment(ContractRecord):
    """A pilot deployment assessment."""

    assessment_id: str = ""
    tenant_id: str = ""
    pilot_ref: str = ""
    total_connectors: int = 0
    active_connectors: int = 0
    migration_completeness: float = 0.0
    readiness_score: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "pilot_ref", require_non_empty_text(self.pilot_ref, "pilot_ref"))
        object.__setattr__(self, "total_connectors", require_non_negative_int(self.total_connectors, "total_connectors"))
        object.__setattr__(self, "active_connectors", require_non_negative_int(self.active_connectors, "active_connectors"))
        object.__setattr__(self, "migration_completeness", require_unit_float(self.migration_completeness, "migration_completeness"))
        object.__setattr__(self, "readiness_score", require_unit_float(self.readiness_score, "readiness_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PilotViolation(ContractRecord):
    """A pilot deployment violation."""

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
class PilotClosureReport(ContractRecord):
    """A pilot closure report."""

    report_id: str = ""
    tenant_id: str = ""
    total_bootstraps: int = 0
    total_connectors: int = 0
    total_migrations: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_bootstraps", require_non_negative_int(self.total_bootstraps, "total_bootstraps"))
        object.__setattr__(self, "total_connectors", require_non_negative_int(self.total_connectors, "total_connectors"))
        object.__setattr__(self, "total_migrations", require_non_negative_int(self.total_migrations, "total_migrations"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
