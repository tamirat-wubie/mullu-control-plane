"""Purpose: red-team / adversarial reasoning runtime contracts.
Governance scope: typed descriptors for attack scenarios, vulnerabilities,
    exploit paths, defenses, stress tests, decisions, assessments, violations,
    snapshots, and closure reports for adversarial red-team operations.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Attack and vulnerability lifecycles are enum-guarded.
  - Severity levels are explicit and computable.
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


class AttackStatus(Enum):
    """Status of an attack scenario."""
    PLANNED = "planned"
    EXECUTING = "executing"
    COMPLETED = "completed"
    BLOCKED = "blocked"


class AttackKind(Enum):
    """Kind of attack being simulated."""
    POLICY_BYPASS = "policy_bypass"
    DATA_POISONING = "data_poisoning"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    GAMING = "gaming"
    INJECTION = "injection"
    DENIAL = "denial"


class VulnerabilityStatus(Enum):
    """Status of a discovered vulnerability."""
    OPEN = "open"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    FALSE_POSITIVE = "false_positive"


class ExploitSeverity(Enum):
    """Severity level of an exploit or vulnerability."""
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DefenseDisposition(Enum):
    """Disposition of a defense mechanism."""
    EFFECTIVE = "effective"
    PARTIAL = "partial"
    INEFFECTIVE = "ineffective"
    UNTESTED = "untested"


class AdversarialRiskLevel(Enum):
    """Risk level for adversarial operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AttackScenario(ContractRecord):
    """An attack scenario for red-team testing."""

    scenario_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: AttackKind = AttackKind.POLICY_BYPASS
    target_runtime: str = ""
    status: AttackStatus = AttackStatus.PLANNED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, AttackKind):
            raise ValueError("kind must be an AttackKind")
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        if not isinstance(self.status, AttackStatus):
            raise ValueError("status must be an AttackStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VulnerabilityRecord(ContractRecord):
    """A discovered vulnerability."""

    vulnerability_id: str = ""
    tenant_id: str = ""
    target_runtime: str = ""
    status: VulnerabilityStatus = VulnerabilityStatus.OPEN
    severity: ExploitSeverity = ExploitSeverity.MEDIUM
    description: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "vulnerability_id", require_non_empty_text(self.vulnerability_id, "vulnerability_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        if not isinstance(self.status, VulnerabilityStatus):
            raise ValueError("status must be a VulnerabilityStatus")
        if not isinstance(self.severity, ExploitSeverity):
            raise ValueError("severity must be an ExploitSeverity")
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExploitPath(ContractRecord):
    """A recorded exploit path through the system."""

    path_id: str = ""
    tenant_id: str = ""
    scenario_ref: str = ""
    step_count: int = 0
    success: bool = False
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "path_id", require_non_empty_text(self.path_id, "path_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "scenario_ref", require_non_empty_text(self.scenario_ref, "scenario_ref"))
        object.__setattr__(self, "step_count", require_non_negative_int(self.step_count, "step_count"))
        if not isinstance(self.success, bool):
            raise ValueError("success must be a bool")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DefenseRecord(ContractRecord):
    """A defense mechanism applied to a vulnerability."""

    defense_id: str = ""
    tenant_id: str = ""
    vulnerability_ref: str = ""
    disposition: DefenseDisposition = DefenseDisposition.UNTESTED
    mitigation: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "defense_id", require_non_empty_text(self.defense_id, "defense_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "vulnerability_ref", require_non_empty_text(self.vulnerability_ref, "vulnerability_ref"))
        if not isinstance(self.disposition, DefenseDisposition):
            raise ValueError("disposition must be a DefenseDisposition")
        object.__setattr__(self, "mitigation", require_non_empty_text(self.mitigation, "mitigation"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdversarialDecision(ContractRecord):
    """A decision made in the adversarial runtime context."""

    decision_id: str = ""
    tenant_id: str = ""
    scenario_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "scenario_ref", require_non_empty_text(self.scenario_ref, "scenario_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class StressTestRecord(ContractRecord):
    """A stress test record against a target runtime."""

    test_id: str = ""
    tenant_id: str = ""
    target_runtime: str = ""
    load_factor: float = 0.0
    outcome: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "test_id", require_non_empty_text(self.test_id, "test_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "load_factor", require_non_negative_float(self.load_factor, "load_factor"))
        object.__setattr__(self, "outcome", require_non_empty_text(self.outcome, "outcome"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdversarialAssessment(ContractRecord):
    """Assessment of adversarial posture for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_scenarios: int = 0
    total_vulnerabilities: int = 0
    total_mitigated: int = 0
    defense_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_scenarios", require_non_negative_int(self.total_scenarios, "total_scenarios"))
        object.__setattr__(self, "total_vulnerabilities", require_non_negative_int(self.total_vulnerabilities, "total_vulnerabilities"))
        object.__setattr__(self, "total_mitigated", require_non_negative_int(self.total_mitigated, "total_mitigated"))
        object.__setattr__(self, "defense_rate", require_unit_float(self.defense_rate, "defense_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdversarialViolation(ContractRecord):
    """A detected violation in the adversarial runtime."""

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
class AdversarialSnapshot(ContractRecord):
    """Point-in-time snapshot of adversarial runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_scenarios: int = 0
    total_vulnerabilities: int = 0
    total_exploits: int = 0
    total_defenses: int = 0
    total_stress_tests: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_scenarios", require_non_negative_int(self.total_scenarios, "total_scenarios"))
        object.__setattr__(self, "total_vulnerabilities", require_non_negative_int(self.total_vulnerabilities, "total_vulnerabilities"))
        object.__setattr__(self, "total_exploits", require_non_negative_int(self.total_exploits, "total_exploits"))
        object.__setattr__(self, "total_defenses", require_non_negative_int(self.total_defenses, "total_defenses"))
        object.__setattr__(self, "total_stress_tests", require_non_negative_int(self.total_stress_tests, "total_stress_tests"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AdversarialClosureReport(ContractRecord):
    """Closure report for adversarial runtime state."""

    report_id: str = ""
    tenant_id: str = ""
    total_scenarios: int = 0
    total_vulnerabilities: int = 0
    total_defenses: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_scenarios", require_non_negative_int(self.total_scenarios, "total_scenarios"))
        object.__setattr__(self, "total_vulnerabilities", require_non_negative_int(self.total_vulnerabilities, "total_vulnerabilities"))
        object.__setattr__(self, "total_defenses", require_non_negative_int(self.total_defenses, "total_defenses"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
