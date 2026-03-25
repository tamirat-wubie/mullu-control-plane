"""Purpose: canonical industry-pack contracts.
Governance scope: industry pack descriptors, capabilities, configurations,
    bindings, assessments, decisions, violations, snapshots, deployments,
    and closure reports.
Dependencies: shared contract base helpers.
Invariants:
  - Every industry pack has explicit status, domain, and capability count.
  - Only VALIDATED packs may be deployed.
  - Capabilities always reference their parent pack_ref.
  - All fields validated at construction time.
  - Boolean fields are strictly typed.
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


class IndustryPackStatus(Enum):
    """Lifecycle status of an industry pack."""

    DRAFT = "draft"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class PackDomain(Enum):
    """Domain classification for an industry pack."""

    REGULATED_OPS = "regulated_ops"
    RESEARCH_LAB = "research_lab"
    FACTORY_QUALITY = "factory_quality"
    ENTERPRISE_SERVICE = "enterprise_service"
    FINANCIAL_CONTROL = "financial_control"
    CUSTOM = "custom"


class PackCapabilityKind(Enum):
    """Kind of capability provided by a pack."""

    INTAKE = "intake"
    CASE_MANAGEMENT = "case_management"
    APPROVAL = "approval"
    EVIDENCE = "evidence"
    REPORTING = "reporting"
    DASHBOARD = "dashboard"
    COPILOT = "copilot"
    GOVERNANCE = "governance"
    OBSERVABILITY = "observability"
    CONTINUITY = "continuity"


class PackReadiness(Enum):
    """Readiness level of a pack assessment."""

    NOT_READY = "not_ready"
    PARTIAL = "partial"
    READY = "ready"
    DEPLOYED = "deployed"


class DeploymentDisposition(Enum):
    """Disposition of a deployment decision."""

    PENDING = "pending"
    APPROVED = "approved"
    BLOCKED = "blocked"
    ROLLED_BACK = "rolled_back"


class PackRiskLevel(Enum):
    """Risk level classification for a pack."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# IndustryPack
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IndustryPack(ContractRecord):
    """Top-level descriptor for an industry pack."""

    pack_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    domain: PackDomain = PackDomain.CUSTOM
    status: IndustryPackStatus = IndustryPackStatus.DRAFT
    capability_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.pack_id, "pack_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.display_name, "display_name")
        if not isinstance(self.domain, PackDomain):
            raise ValueError(f"domain must be PackDomain, got {type(self.domain)}")
        if not isinstance(self.status, IndustryPackStatus):
            raise ValueError(f"status must be IndustryPackStatus, got {type(self.status)}")
        require_non_negative_int(self.capability_count, "capability_count")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackCapability
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackCapability(ContractRecord):
    """A single capability provided by an industry pack."""

    capability_id: str = ""
    tenant_id: str = ""
    pack_ref: str = ""
    kind: PackCapabilityKind = PackCapabilityKind.INTAKE
    target_runtime: str = ""
    enabled: bool = True
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.capability_id, "capability_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.pack_ref, "pack_ref")
        if not isinstance(self.kind, PackCapabilityKind):
            raise ValueError(f"kind must be PackCapabilityKind, got {type(self.kind)}")
        require_non_empty_text(self.target_runtime, "target_runtime")
        if not isinstance(self.enabled, bool):
            raise ValueError(f"enabled must be bool, got {type(self.enabled)}")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackConfiguration
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackConfiguration(ContractRecord):
    """A key-value configuration entry for a pack."""

    config_id: str = ""
    tenant_id: str = ""
    pack_ref: str = ""
    key: str = ""
    value: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.config_id, "config_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.pack_ref, "pack_ref")
        require_non_empty_text(self.key, "key")
        require_non_empty_text(self.value, "value")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackBinding
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackBinding(ContractRecord):
    """Binds a pack to a runtime component."""

    binding_id: str = ""
    tenant_id: str = ""
    pack_ref: str = ""
    runtime_ref: str = ""
    binding_type: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.binding_id, "binding_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.pack_ref, "pack_ref")
        require_non_empty_text(self.runtime_ref, "runtime_ref")
        require_non_empty_text(self.binding_type, "binding_type")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackAssessment
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackAssessment(ContractRecord):
    """Assessment of pack readiness."""

    assessment_id: str = ""
    tenant_id: str = ""
    pack_ref: str = ""
    readiness: PackReadiness = PackReadiness.NOT_READY
    total_capabilities: int = 0
    enabled_capabilities: int = 0
    readiness_score: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.assessment_id, "assessment_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.pack_ref, "pack_ref")
        if not isinstance(self.readiness, PackReadiness):
            raise ValueError(f"readiness must be PackReadiness, got {type(self.readiness)}")
        require_non_negative_int(self.total_capabilities, "total_capabilities")
        require_non_negative_int(self.enabled_capabilities, "enabled_capabilities")
        require_unit_float(self.readiness_score, "readiness_score")
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackDecision
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackDecision(ContractRecord):
    """A deployment decision for a pack."""

    decision_id: str = ""
    tenant_id: str = ""
    pack_ref: str = ""
    disposition: DeploymentDisposition = DeploymentDisposition.PENDING
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.decision_id, "decision_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.pack_ref, "pack_ref")
        if not isinstance(self.disposition, DeploymentDisposition):
            raise ValueError(f"disposition must be DeploymentDisposition, got {type(self.disposition)}")
        require_non_empty_text(self.reason, "reason")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackViolation
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackViolation(ContractRecord):
    """A detected violation in the industry pack runtime."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.violation_id, "violation_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.operation, "operation")
        require_non_empty_text(self.reason, "reason")
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackSnapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackSnapshot(ContractRecord):
    """Point-in-time snapshot of the industry pack runtime."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_packs: int = 0
    total_capabilities: int = 0
    total_bindings: int = 0
    total_configs: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.snapshot_id, "snapshot_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_negative_int(self.total_packs, "total_packs")
        require_non_negative_int(self.total_capabilities, "total_capabilities")
        require_non_negative_int(self.total_bindings, "total_bindings")
        require_non_negative_int(self.total_configs, "total_configs")
        require_non_negative_int(self.total_violations, "total_violations")
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackDeploymentRecord
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackDeploymentRecord(ContractRecord):
    """Records a pack deployment event."""

    deployment_id: str = ""
    tenant_id: str = ""
    pack_ref: str = ""
    disposition: DeploymentDisposition = DeploymentDisposition.APPROVED
    deployed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.deployment_id, "deployment_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_empty_text(self.pack_ref, "pack_ref")
        if not isinstance(self.disposition, DeploymentDisposition):
            raise ValueError(f"disposition must be DeploymentDisposition, got {type(self.disposition)}")
        require_datetime_text(self.deployed_at, "deployed_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# PackClosureReport
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class PackClosureReport(ContractRecord):
    """Summary closure report for the industry pack runtime."""

    report_id: str = ""
    tenant_id: str = ""
    total_packs: int = 0
    total_deployments: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_non_empty_text(self.report_id, "report_id")
        require_non_empty_text(self.tenant_id, "tenant_id")
        require_non_negative_int(self.total_packs, "total_packs")
        require_non_negative_int(self.total_deployments, "total_deployments")
        require_non_negative_int(self.total_violations, "total_violations")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
