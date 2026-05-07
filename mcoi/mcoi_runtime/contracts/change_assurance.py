"""Purpose: governed evolution contracts for repository and release changes.
Governance scope: typed ChangeCommand, blast-radius, invariant, replay, and
    release-certificate records for production-evolution assurance.
Dependencies: shared contract utilities and Python standard library enums.
Invariants:
  - Every production-evolution change has explicit identity, risk, scope, and evidence.
  - High-risk changes require approval and rollback evidence.
  - Certificates bind all assurance reports to one immutable change command.
  - All outputs are frozen and JSON-serializable.
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
)


class ChangeRisk(Enum):
    """Risk tier assigned to a production-evolution change."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EvolutionChangeType(Enum):
    """Type of repository or deployment law being changed."""

    CODE = "code"
    SCHEMA = "schema"
    POLICY = "policy"
    CAPABILITY = "capability"
    AUTHORITY = "authority"
    PROVIDER = "provider"
    MIGRATION = "migration"
    DEPLOYMENT = "deployment"
    CONFIGURATION = "configuration"
    DOCUMENTATION = "documentation"


class AssuranceDisposition(Enum):
    """Terminal disposition for an assurance report."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True, slots=True)
class ChangeCommand(ContractRecord):
    """First-class command describing a proposed system evolution."""

    change_id: str = ""
    author_id: str = ""
    branch: str = ""
    base_commit: str = ""
    head_commit: str = ""
    change_type: EvolutionChangeType = EvolutionChangeType.CODE
    risk: ChangeRisk = ChangeRisk.LOW
    affected_files: tuple[str, ...] = ()
    affected_contracts: tuple[str, ...] = ()
    affected_capabilities: tuple[str, ...] = ()
    affected_invariants: tuple[str, ...] = ()
    required_replays: tuple[str, ...] = ()
    requires_approval: bool = False
    rollback_required: bool = False
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(self, "author_id", require_non_empty_text(self.author_id, "author_id"))
        object.__setattr__(self, "branch", require_non_empty_text(self.branch, "branch"))
        object.__setattr__(self, "base_commit", require_non_empty_text(self.base_commit, "base_commit"))
        object.__setattr__(self, "head_commit", require_non_empty_text(self.head_commit, "head_commit"))
        if not isinstance(self.change_type, EvolutionChangeType):
            raise ValueError("change_type must be an EvolutionChangeType")
        if not isinstance(self.risk, ChangeRisk):
            raise ValueError("risk must be a ChangeRisk")
        if not isinstance(self.requires_approval, bool):
            raise ValueError("requires_approval must be a boolean")
        if not isinstance(self.rollback_required, bool):
            raise ValueError("rollback_required must be a boolean")
        object.__setattr__(self, "affected_files", freeze_value(list(self.affected_files)))
        object.__setattr__(self, "affected_contracts", freeze_value(list(self.affected_contracts)))
        object.__setattr__(self, "affected_capabilities", freeze_value(list(self.affected_capabilities)))
        object.__setattr__(self, "affected_invariants", freeze_value(list(self.affected_invariants)))
        object.__setattr__(self, "required_replays", freeze_value(list(self.required_replays)))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class BlastRadiusReport(ContractRecord):
    """Deterministic impact report for a ChangeCommand."""

    report_id: str = ""
    change_id: str = ""
    affected_files_count: int = 0
    affected_contracts: tuple[str, ...] = ()
    affected_capabilities: tuple[str, ...] = ()
    affected_invariants: tuple[str, ...] = ()
    risk: ChangeRisk = ChangeRisk.LOW
    requires_migration_review: bool = False
    requires_authority_review: bool = False
    evidence_refs: tuple[str, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        object.__setattr__(
            self,
            "affected_files_count",
            require_non_negative_int(self.affected_files_count, "affected_files_count"),
        )
        if not isinstance(self.risk, ChangeRisk):
            raise ValueError("risk must be a ChangeRisk")
        if not isinstance(self.requires_migration_review, bool):
            raise ValueError("requires_migration_review must be a boolean")
        if not isinstance(self.requires_authority_review, bool):
            raise ValueError("requires_authority_review must be a boolean")
        object.__setattr__(self, "affected_contracts", freeze_value(list(self.affected_contracts)))
        object.__setattr__(self, "affected_capabilities", freeze_value(list(self.affected_capabilities)))
        object.__setattr__(self, "affected_invariants", freeze_value(list(self.affected_invariants)))
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class InvariantCheckReport(ContractRecord):
    """Report for hard governance laws evaluated against a ChangeCommand."""

    report_id: str = ""
    change_id: str = ""
    disposition: AssuranceDisposition = AssuranceDisposition.PASSED
    checked_invariants: tuple[str, ...] = ()
    violations: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        if not isinstance(self.disposition, AssuranceDisposition):
            raise ValueError("disposition must be an AssuranceDisposition")
        object.__setattr__(self, "checked_invariants", freeze_value(list(self.checked_invariants)))
        object.__setattr__(self, "violations", freeze_value(list(self.violations)))
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ReplayCertificationReport(ContractRecord):
    """Report describing required replay scenarios for semantic drift control."""

    report_id: str = ""
    change_id: str = ""
    disposition: AssuranceDisposition = AssuranceDisposition.PASSED
    required_scenarios: tuple[str, ...] = ()
    executed_scenarios: tuple[str, ...] = ()
    skipped_scenarios: tuple[str, ...] = ()
    scenario_results: Mapping[str, str] = field(default_factory=dict)
    failure_reasons: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        if not isinstance(self.disposition, AssuranceDisposition):
            raise ValueError("disposition must be an AssuranceDisposition")
        object.__setattr__(self, "required_scenarios", freeze_value(list(self.required_scenarios)))
        object.__setattr__(self, "executed_scenarios", freeze_value(list(self.executed_scenarios)))
        object.__setattr__(self, "skipped_scenarios", freeze_value(list(self.skipped_scenarios)))
        object.__setattr__(self, "scenario_results", freeze_value(dict(self.scenario_results)))
        object.__setattr__(self, "failure_reasons", freeze_value(list(self.failure_reasons)))
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ChangeCertificate(ContractRecord):
    """Release certificate proving a ChangeCommand passed governed assurance."""

    certificate_id: str = ""
    change_id: str = ""
    schema_checks_passed: bool = False
    tests_passed: bool = False
    replay_passed: bool = False
    invariant_checks_passed: bool = False
    migration_safe: bool = False
    rollback_plan_present: bool = False
    approval_id: str | None = None
    evidence_refs: tuple[str, ...] = ()
    certified_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "certificate_id",
            require_non_empty_text(self.certificate_id, "certificate_id"),
        )
        object.__setattr__(self, "change_id", require_non_empty_text(self.change_id, "change_id"))
        for field_name in (
            "schema_checks_passed",
            "tests_passed",
            "replay_passed",
            "invariant_checks_passed",
            "migration_safe",
            "rollback_plan_present",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise ValueError(f"{field_name} must be a boolean")
        if self.approval_id is not None:
            object.__setattr__(
                self,
                "approval_id",
                require_non_empty_text(self.approval_id, "approval_id"),
            )
        object.__setattr__(self, "evidence_refs", freeze_value(list(self.evidence_refs)))
        require_datetime_text(self.certified_at, "certified_at")
