"""Purpose: compensation assurance contracts for failed or partial effects.
Governance scope: recovery action planning, execution, verification, and
evidence closure after unresolved effect reconciliation.
Dependencies: shared contract base helpers.
Invariants:
  - Compensation references the original command, effect plan, reconciliation,
    and case.
  - Compensation cannot be implicit; approval, capability, and evidence are
    explicit.
  - Compensation outcome is terminal and evidence-backed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_empty_tuple,
)


class CompensationKind(StrEnum):
    """Type of recovery action used to counter a failed effect."""

    ROLLBACK = "rollback"
    COMPENSATION = "compensation"
    CORRECTION = "correction"


class CompensationStatus(StrEnum):
    """Terminal status of a compensation attempt."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REQUIRES_REVIEW = "requires_review"


@dataclass(frozen=True, slots=True)
class CompensationPlan(ContractRecord):
    """Approved plan for counteracting an unresolved original effect."""

    compensation_plan_id: str
    command_id: str
    effect_plan_id: str
    reconciliation_id: str
    case_id: str
    capability_id: str
    kind: CompensationKind
    approval_id: str
    expected_effects: tuple[str, ...]
    forbidden_effects: tuple[str, ...]
    evidence_required: tuple[str, ...]
    created_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "compensation_plan_id",
            "command_id",
            "effect_plan_id",
            "reconciliation_id",
            "case_id",
            "capability_id",
            "approval_id",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.kind, CompensationKind):
            raise ValueError("kind must be a CompensationKind value")
        object.__setattr__(self, "expected_effects", require_non_empty_tuple(self.expected_effects, "expected_effects"))
        object.__setattr__(self, "forbidden_effects", require_non_empty_tuple(self.forbidden_effects, "forbidden_effects"))
        object.__setattr__(self, "evidence_required", require_non_empty_tuple(self.evidence_required, "evidence_required"))
        for field_name in ("expected_effects", "forbidden_effects", "evidence_required"):
            for value in getattr(self, field_name):
                require_non_empty_text(value, f"{field_name} element")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class CompensationAttempt(ContractRecord):
    """Execution witness for one compensation dispatch."""

    attempt_id: str
    compensation_plan_id: str
    command_id: str
    execution_id: str
    started_at: str
    finished_at: str
    evidence_refs: tuple[str, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("attempt_id", "compensation_plan_id", "command_id", "execution_id"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        object.__setattr__(self, "evidence_refs", require_non_empty_tuple(self.evidence_refs, "evidence_refs"))
        for evidence_ref in self.evidence_refs:
            require_non_empty_text(evidence_ref, "evidence_refs element")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class CompensationOutcome(ContractRecord):
    """Terminal result of verifying and reconciling compensation effects."""

    outcome_id: str
    compensation_plan_id: str
    attempt_id: str
    command_id: str
    status: CompensationStatus
    verification_result_id: str
    reconciliation_id: str
    evidence_refs: tuple[str, ...]
    decided_at: str
    case_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "outcome_id",
            "compensation_plan_id",
            "attempt_id",
            "command_id",
            "verification_result_id",
            "reconciliation_id",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.status, CompensationStatus):
            raise ValueError("status must be a CompensationStatus value")
        object.__setattr__(self, "evidence_refs", require_non_empty_tuple(self.evidence_refs, "evidence_refs"))
        for evidence_ref in self.evidence_refs:
            require_non_empty_text(evidence_ref, "evidence_refs element")
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
        if self.case_id is not None:
            object.__setattr__(self, "case_id", require_non_empty_text(self.case_id, "case_id"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
