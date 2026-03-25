"""Purpose: logic / proof / truth-maintenance runtime contracts.
Governance scope: typed descriptors for logical statements, inference rules,
    proofs, assumptions, contradictions, revisions, truth-maintenance decisions,
    assessments, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Boolean fields are strictly validated.
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
# Local validators
# ---------------------------------------------------------------------------


def _require_bool(value: bool, field_name: str) -> bool:
    """Validate that a value is strictly a bool."""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a bool")
    return value


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class LogicalStatus(Enum):
    """Lifecycle status of a logical statement."""
    ASSERTED = "asserted"
    DERIVED = "derived"
    RETRACTED = "retracted"
    CONTRADICTED = "contradicted"
    PROVISIONAL = "provisional"


class StatementKind(Enum):
    """Category of logical statement."""
    FACT = "fact"
    RULE = "rule"
    ASSUMPTION = "assumption"
    CONCLUSION = "conclusion"
    AXIOM = "axiom"


class ProofStatus(Enum):
    """Status of a proof record."""
    VALID = "valid"
    INVALID = "invalid"
    PENDING = "pending"
    RETRACTED = "retracted"


class AssumptionDisposition(Enum):
    """Disposition of an assumption."""
    ACTIVE = "active"
    RETRACTED = "retracted"
    SUPERSEDED = "superseded"
    CHALLENGED = "challenged"


class ContradictionSeverity(Enum):
    """Severity level of a contradiction."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RevisionDisposition(Enum):
    """Disposition of a belief revision."""
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    MERGED = "merged"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class LogicalStatement(ContractRecord):
    """A logical statement in the truth-maintenance system."""

    statement_id: str = ""
    tenant_id: str = ""
    kind: StatementKind = StatementKind.FACT
    content: str = ""
    status: LogicalStatus = LogicalStatus.ASSERTED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "statement_id", require_non_empty_text(self.statement_id, "statement_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.kind, StatementKind):
            raise ValueError("kind must be a StatementKind")
        object.__setattr__(self, "content", require_non_empty_text(self.content, "content"))
        if not isinstance(self.status, LogicalStatus):
            raise ValueError("status must be a LogicalStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InferenceRule(ContractRecord):
    """An inference rule: antecedent => consequent."""

    rule_id: str = ""
    tenant_id: str = ""
    antecedent: str = ""
    consequent: str = ""
    confidence: float = 1.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_id", require_non_empty_text(self.rule_id, "rule_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "antecedent", require_non_empty_text(self.antecedent, "antecedent"))
        object.__setattr__(self, "consequent", require_non_empty_text(self.consequent, "consequent"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProofRecord(ContractRecord):
    """A proof linking a conclusion to a rule application."""

    proof_id: str = ""
    tenant_id: str = ""
    conclusion_ref: str = ""
    rule_ref: str = ""
    status: ProofStatus = ProofStatus.VALID
    step_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "proof_id", require_non_empty_text(self.proof_id, "proof_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "conclusion_ref", require_non_empty_text(self.conclusion_ref, "conclusion_ref"))
        object.__setattr__(self, "rule_ref", require_non_empty_text(self.rule_ref, "rule_ref"))
        if not isinstance(self.status, ProofStatus):
            raise ValueError("status must be a ProofStatus")
        object.__setattr__(self, "step_count", require_non_negative_int(self.step_count, "step_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class AssumptionRecord(ContractRecord):
    """An assumption in the truth-maintenance system."""

    assumption_id: str = ""
    tenant_id: str = ""
    statement_ref: str = ""
    disposition: AssumptionDisposition = AssumptionDisposition.ACTIVE
    justification: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assumption_id", require_non_empty_text(self.assumption_id, "assumption_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "statement_ref", require_non_empty_text(self.statement_ref, "statement_ref"))
        if not isinstance(self.disposition, AssumptionDisposition):
            raise ValueError("disposition must be an AssumptionDisposition")
        object.__setattr__(self, "justification", require_non_empty_text(self.justification, "justification"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ContradictionRecord(ContractRecord):
    """A detected contradiction between two statements."""

    contradiction_id: str = ""
    tenant_id: str = ""
    statement_a_ref: str = ""
    statement_b_ref: str = ""
    severity: ContradictionSeverity = ContradictionSeverity.MEDIUM
    resolved: bool = False
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "contradiction_id", require_non_empty_text(self.contradiction_id, "contradiction_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "statement_a_ref", require_non_empty_text(self.statement_a_ref, "statement_a_ref"))
        object.__setattr__(self, "statement_b_ref", require_non_empty_text(self.statement_b_ref, "statement_b_ref"))
        if not isinstance(self.severity, ContradictionSeverity):
            raise ValueError("severity must be a ContradictionSeverity")
        object.__setattr__(self, "resolved", _require_bool(self.resolved, "resolved"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RevisionRecord(ContractRecord):
    """A record of a belief revision."""

    revision_id: str = ""
    tenant_id: str = ""
    statement_ref: str = ""
    disposition: RevisionDisposition = RevisionDisposition.ACCEPTED
    reason: str = ""
    revised_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "revision_id", require_non_empty_text(self.revision_id, "revision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "statement_ref", require_non_empty_text(self.statement_ref, "statement_ref"))
        if not isinstance(self.disposition, RevisionDisposition):
            raise ValueError("disposition must be a RevisionDisposition")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.revised_at, "revised_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class TruthMaintenanceDecision(ContractRecord):
    """A truth-maintenance decision resolving a contradiction."""

    decision_id: str = ""
    tenant_id: str = ""
    contradiction_ref: str = ""
    disposition: RevisionDisposition = RevisionDisposition.ACCEPTED
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "contradiction_ref", require_non_empty_text(self.contradiction_ref, "contradiction_ref"))
        if not isinstance(self.disposition, RevisionDisposition):
            raise ValueError("disposition must be a RevisionDisposition")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LogicAssessment(ContractRecord):
    """Assessment of logical consistency for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_statements: int = 0
    total_proofs: int = 0
    total_contradictions: int = 0
    consistency_rate: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_statements", require_non_negative_int(self.total_statements, "total_statements"))
        object.__setattr__(self, "total_proofs", require_non_negative_int(self.total_proofs, "total_proofs"))
        object.__setattr__(self, "total_contradictions", require_non_negative_int(self.total_contradictions, "total_contradictions"))
        object.__setattr__(self, "consistency_rate", require_unit_float(self.consistency_rate, "consistency_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LogicSnapshot(ContractRecord):
    """Point-in-time snapshot of logic runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_statements: int = 0
    total_rules: int = 0
    total_proofs: int = 0
    total_assumptions: int = 0
    total_contradictions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_statements", require_non_negative_int(self.total_statements, "total_statements"))
        object.__setattr__(self, "total_rules", require_non_negative_int(self.total_rules, "total_rules"))
        object.__setattr__(self, "total_proofs", require_non_negative_int(self.total_proofs, "total_proofs"))
        object.__setattr__(self, "total_assumptions", require_non_negative_int(self.total_assumptions, "total_assumptions"))
        object.__setattr__(self, "total_contradictions", require_non_negative_int(self.total_contradictions, "total_contradictions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class LogicClosureReport(ContractRecord):
    """Final closure report for logic runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_statements: int = 0
    total_proofs: int = 0
    total_contradictions: int = 0
    total_revisions: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_statements", require_non_negative_int(self.total_statements, "total_statements"))
        object.__setattr__(self, "total_proofs", require_non_negative_int(self.total_proofs, "total_proofs"))
        object.__setattr__(self, "total_contradictions", require_non_negative_int(self.total_contradictions, "total_contradictions"))
        object.__setattr__(self, "total_revisions", require_non_negative_int(self.total_revisions, "total_revisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
