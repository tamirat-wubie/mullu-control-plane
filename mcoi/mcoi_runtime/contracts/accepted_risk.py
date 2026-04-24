"""Purpose: accepted-risk closure contracts for unresolved verification gaps.
Governance scope: explicit residual-risk admission after effect reconciliation.
Dependencies: shared contract base helpers.
Invariants:
  - Accepted risk always references command, execution, reconciliation, and case.
  - Accepted risk has an owner, approver, expiry, review obligation, and evidence.
  - Acceptance scope is explicit and cannot be inferred from a failed action.
  - Closure is bounded; permanent unreviewed risk is rejected.
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


class AcceptedRiskScope(StrEnum):
    """Boundary of the residual risk being accepted."""

    EFFECT_RECONCILIATION = "effect_reconciliation"
    VERIFICATION_GAP = "verification_gap"
    PROVIDER_UNCERTAINTY = "provider_uncertainty"
    OPERATIONAL_LIMITATION = "operational_limitation"


class AcceptedRiskDisposition(StrEnum):
    """Lifecycle state for an accepted-risk record."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    CLOSED = "closed"


@dataclass(frozen=True, slots=True)
class AcceptedRiskRecord(ContractRecord):
    """Explicit owner-approved admission of bounded residual risk."""

    risk_id: str
    command_id: str
    execution_id: str
    effect_plan_id: str
    reconciliation_id: str
    case_id: str
    scope: AcceptedRiskScope
    disposition: AcceptedRiskDisposition
    reason: str
    accepted_by: str
    owner_id: str
    expires_at: str
    review_obligation_id: str
    evidence_refs: tuple[str, ...]
    accepted_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "risk_id",
            "command_id",
            "execution_id",
            "effect_plan_id",
            "reconciliation_id",
            "case_id",
            "reason",
            "accepted_by",
            "owner_id",
            "review_obligation_id",
        ):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        if not isinstance(self.scope, AcceptedRiskScope):
            raise ValueError("scope must be an AcceptedRiskScope value")
        if not isinstance(self.disposition, AcceptedRiskDisposition):
            raise ValueError("disposition must be an AcceptedRiskDisposition value")
        object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))
        object.__setattr__(self, "evidence_refs", require_non_empty_tuple(self.evidence_refs, "evidence_refs"))
        for evidence_ref in self.evidence_refs:
            require_non_empty_text(evidence_ref, "evidence_refs element")
        object.__setattr__(self, "accepted_at", require_datetime_text(self.accepted_at, "accepted_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class AcceptedRiskDecision(ContractRecord):
    """Deterministic admission result for a proposed risk acceptance."""

    decision_id: str
    command_id: str
    allowed: bool
    reason: str
    decided_at: str
    missing_requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "command_id", require_non_empty_text(self.command_id, "command_id"))
        if not isinstance(self.allowed, bool):
            raise ValueError("allowed must be a boolean")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))
        if not isinstance(self.missing_requirements, tuple):
            object.__setattr__(self, "missing_requirements", tuple(self.missing_requirements))
        for requirement in self.missing_requirements:
            require_non_empty_text(requirement, "missing_requirements element")
