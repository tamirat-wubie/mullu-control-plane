"""Purpose: canonical review workflow contracts.
Governance scope: review request, decision, scope, and record typing.
Dependencies: shared contract base helpers.
Invariants:
  - Reviews are first-class durable governance artifacts.
  - Review-gated actions MUST NOT proceed without resolution.
  - Review scope is explicit and bounded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class ReviewStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    EXPIRED = "expired"


class ReviewScopeType(StrEnum):
    RUNBOOK_ADMISSION = "runbook_admission"
    RUNBOOK_DRIFT = "runbook_drift"
    DEPLOYMENT_CHANGE = "deployment_change"
    PROVIDER_POLICY_CHANGE = "provider_policy_change"
    INCIDENT_CLOSURE = "incident_closure"
    SKILL_PROMOTION = "skill_promotion"
    SOFTWARE_RECEIPT_CHAIN = "software_receipt_chain"


@dataclass(frozen=True, slots=True)
class ReviewScope(ContractRecord):
    """What the review covers."""

    scope_type: ReviewScopeType
    target_id: str
    description: str

    def __post_init__(self) -> None:
        if not isinstance(self.scope_type, ReviewScopeType):
            raise ValueError("scope_type must be a ReviewScopeType value")
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "description", require_non_empty_text(self.description, "description"))


@dataclass(frozen=True, slots=True)
class ReviewRequest(ContractRecord):
    """A request for human review of a governance-relevant change."""

    request_id: str
    requester_id: str
    scope: ReviewScope
    reason: str
    requested_at: str
    expires_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "requester_id", require_non_empty_text(self.requester_id, "requester_id"))
        if not isinstance(self.scope, ReviewScope):
            raise ValueError("scope must be a ReviewScope instance")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "requested_at", require_datetime_text(self.requested_at, "requested_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ReviewDecision(ContractRecord):
    """A durable record of a review decision."""

    decision_id: str
    request_id: str
    reviewer_id: str
    status: ReviewStatus
    decided_at: str
    comment: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "reviewer_id", require_non_empty_text(self.reviewer_id, "reviewer_id"))
        if not isinstance(self.status, ReviewStatus):
            raise ValueError("status must be a ReviewStatus value")
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))

    @property
    def is_approved(self) -> bool:
        return self.status is ReviewStatus.APPROVED

    @property
    def is_resolved(self) -> bool:
        return self.status in (ReviewStatus.APPROVED, ReviewStatus.REJECTED, ReviewStatus.EXPIRED)
