"""Purpose: global policy / constitutional governance runtime contracts.
Governance scope: typed descriptors for constitution rules, bundles,
    global overrides, emergency governance, decisions, violations,
    precedence resolutions, snapshots, assessments, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every rule references a tenant.
  - Precedence levels are respected during resolution.
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


class ConstitutionStatus(Enum):
    """Status of a constitution rule or bundle."""
    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    RETIRED = "retired"


class ConstitutionRuleKind(Enum):
    """Kind of constitutional rule."""
    HARD_DENY = "hard_deny"
    SOFT_DENY = "soft_deny"
    ALLOW = "allow"
    RESTRICT = "restrict"
    REQUIRE = "require"


class PrecedenceLevel(Enum):
    """Precedence level for policy resolution."""
    CONSTITUTIONAL = "constitutional"
    PLATFORM = "platform"
    TENANT = "tenant"
    RUNTIME = "runtime"


class OverrideDisposition(Enum):
    """Disposition of a global override."""
    APPLIED = "applied"
    DENIED = "denied"
    RECORDED = "recorded"
    EXPIRED = "expired"


class EmergencyMode(Enum):
    """Emergency governance mode."""
    NORMAL = "normal"
    LOCKDOWN = "lockdown"
    DEGRADED = "degraded"
    RESTRICTED = "restricted"


class GlobalPolicyDisposition(Enum):
    """Disposition of a global policy evaluation."""
    ALLOWED = "allowed"
    DENIED = "denied"
    RESTRICTED = "restricted"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConstitutionRule(ContractRecord):
    """A global constitutional rule."""

    rule_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: ConstitutionRuleKind = ConstitutionRuleKind.HARD_DENY
    precedence: PrecedenceLevel = PrecedenceLevel.CONSTITUTIONAL
    status: ConstitutionStatus = ConstitutionStatus.DRAFT
    target_runtime: str = ""
    target_action: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, ConstitutionRuleKind):
            raise ValueError("kind must be a ConstitutionRuleKind")
        if not isinstance(self.precedence, PrecedenceLevel):
            raise ValueError("precedence must be a PrecedenceLevel")
        if not isinstance(self.status, ConstitutionStatus):
            raise ValueError("status must be a ConstitutionStatus")
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "target_action", require_non_empty_text(self.target_action, "target_action"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstitutionBundle(ContractRecord):
    """A bundle of constitutional rules."""

    bundle_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    rule_count: int = 0
    status: ConstitutionStatus = ConstitutionStatus.DRAFT
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "bundle_id", require_non_empty_text(self.bundle_id, "bundle_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "rule_count", require_non_negative_int(self.rule_count, "rule_count"))
        if not isinstance(self.status, ConstitutionStatus):
            raise ValueError("status must be a ConstitutionStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class GlobalOverrideRecord(ContractRecord):
    """A record of a global override attempt."""

    override_id: str = ""
    rule_id: str = ""
    tenant_id: str = ""
    authority_ref: str = ""
    disposition: OverrideDisposition = OverrideDisposition.RECORDED
    reason: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "override_id", require_non_empty_text(self.override_id, "override_id"))
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "authority_ref", require_non_empty_text(self.authority_ref, "authority_ref"))
        if not isinstance(self.disposition, OverrideDisposition):
            raise ValueError("disposition must be an OverrideDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class EmergencyGovernanceRecord(ContractRecord):
    """A record of an emergency governance mode change."""

    emergency_id: str = ""
    tenant_id: str = ""
    mode: EmergencyMode = EmergencyMode.NORMAL
    previous_mode: EmergencyMode = EmergencyMode.NORMAL
    authority_ref: str = ""
    reason: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "emergency_id", require_non_empty_text(self.emergency_id, "emergency_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.mode, EmergencyMode):
            raise ValueError("mode must be an EmergencyMode")
        if not isinstance(self.previous_mode, EmergencyMode):
            raise ValueError("previous_mode must be an EmergencyMode")
        object.__setattr__(self, "authority_ref", require_non_empty_text(self.authority_ref, "authority_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstitutionDecision(ContractRecord):
    """A decision from global policy evaluation."""

    decision_id: str = ""
    tenant_id: str = ""
    target_runtime: str = ""
    target_action: str = ""
    disposition: GlobalPolicyDisposition = GlobalPolicyDisposition.ALLOWED
    matched_rule_id: str = ""
    emergency_mode: EmergencyMode = EmergencyMode.NORMAL
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "target_action", require_non_empty_text(self.target_action, "target_action"))
        if not isinstance(self.disposition, GlobalPolicyDisposition):
            raise ValueError("disposition must be a GlobalPolicyDisposition")
        if not isinstance(self.emergency_mode, EmergencyMode):
            raise ValueError("emergency_mode must be an EmergencyMode")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstitutionViolation(ContractRecord):
    """A constitutional violation."""

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
class PrecedenceResolution(ContractRecord):
    """A record of precedence resolution between rules."""

    resolution_id: str = ""
    tenant_id: str = ""
    winning_rule_id: str = ""
    losing_rule_id: str = ""
    winning_precedence: PrecedenceLevel = PrecedenceLevel.CONSTITUTIONAL
    losing_precedence: PrecedenceLevel = PrecedenceLevel.RUNTIME
    resolved_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolution_id", require_non_empty_text(self.resolution_id, "resolution_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "winning_rule_id", require_non_empty_text(self.winning_rule_id, "winning_rule_id"))
        object.__setattr__(self, "losing_rule_id", require_non_empty_text(self.losing_rule_id, "losing_rule_id"))
        if not isinstance(self.winning_precedence, PrecedenceLevel):
            raise ValueError("winning_precedence must be a PrecedenceLevel")
        if not isinstance(self.losing_precedence, PrecedenceLevel):
            raise ValueError("losing_precedence must be a PrecedenceLevel")
        require_datetime_text(self.resolved_at, "resolved_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstitutionSnapshot(ContractRecord):
    """Point-in-time snapshot of constitutional governance."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_rules: int = 0
    active_rules: int = 0
    total_bundles: int = 0
    total_overrides: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    emergency_mode: EmergencyMode = EmergencyMode.NORMAL
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_rules", require_non_negative_int(self.total_rules, "total_rules"))
        object.__setattr__(self, "active_rules", require_non_negative_int(self.active_rules, "active_rules"))
        object.__setattr__(self, "total_bundles", require_non_negative_int(self.total_bundles, "total_bundles"))
        object.__setattr__(self, "total_overrides", require_non_negative_int(self.total_overrides, "total_overrides"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        if not isinstance(self.emergency_mode, EmergencyMode):
            raise ValueError("emergency_mode must be an EmergencyMode")
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstitutionAssessment(ContractRecord):
    """An assessment of constitutional governance health."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_rules: int = 0
    active_rules: int = 0
    compliance_score: float = 0.0
    override_count: int = 0
    violation_count: int = 0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_rules", require_non_negative_int(self.total_rules, "total_rules"))
        object.__setattr__(self, "active_rules", require_non_negative_int(self.active_rules, "active_rules"))
        object.__setattr__(self, "compliance_score", require_unit_float(self.compliance_score, "compliance_score"))
        object.__setattr__(self, "override_count", require_non_negative_int(self.override_count, "override_count"))
        object.__setattr__(self, "violation_count", require_non_negative_int(self.violation_count, "violation_count"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstitutionClosureReport(ContractRecord):
    """Closure report for constitutional governance."""

    report_id: str = ""
    tenant_id: str = ""
    total_rules: int = 0
    total_bundles: int = 0
    total_overrides: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    total_resolutions: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_rules", require_non_negative_int(self.total_rules, "total_rules"))
        object.__setattr__(self, "total_bundles", require_non_negative_int(self.total_bundles, "total_bundles"))
        object.__setattr__(self, "total_overrides", require_non_negative_int(self.total_overrides, "total_overrides"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_resolutions", require_non_negative_int(self.total_resolutions, "total_resolutions"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
