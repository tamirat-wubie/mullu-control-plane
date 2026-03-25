"""Purpose: canonical approval and override contracts.
Governance scope: approval request, decision, scope, expiry, and override typing.
Dependencies: shared contract base helpers.
Invariants:
  - Approvals are first-class durable artifacts with explicit scope and expiry.
  - Stale or mismatched approvals fail closed.
  - Manual overrides are attributed and auditable.
  - Revoked approvals cannot be reused.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class ApprovalScopeType(StrEnum):
    EXECUTION = "execution"
    SKILL = "skill"
    RUNBOOK = "runbook"
    RECOVERY = "recovery"
    ROLLBACK = "rollback"
    COMMUNICATION = "communication"


class OverrideType(StrEnum):
    POLICY_OVERRIDE = "policy_override"
    AUTONOMY_OVERRIDE = "autonomy_override"
    RECOVERY_OVERRIDE = "recovery_override"
    PROVIDER_OVERRIDE = "provider_override"


@dataclass(frozen=True, slots=True)
class ApprovalScope(ContractRecord):
    """What the approval covers — typed and bounded."""

    scope_type: ApprovalScopeType
    target_id: str
    allowed_actions: tuple[str, ...] = ()
    max_executions: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.scope_type, ApprovalScopeType):
            raise ValueError("scope_type must be an ApprovalScopeType value")
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "allowed_actions", freeze_value(list(self.allowed_actions)))
        if not isinstance(self.max_executions, int) or self.max_executions < 1:
            raise ValueError("max_executions must be a positive integer")


@dataclass(frozen=True, slots=True)
class ApprovalRequest(ContractRecord):
    """A request for human approval before an action proceeds."""

    request_id: str
    requester_id: str
    scope: ApprovalScope
    reason: str
    requested_at: str
    expires_at: str | None = None
    correlation_id: str | None = None
    goal_id: str | None = None
    incident_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "requester_id", require_non_empty_text(self.requester_id, "requester_id"))
        if not isinstance(self.scope, ApprovalScope):
            raise ValueError("scope must be an ApprovalScope instance")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "requested_at", require_datetime_text(self.requested_at, "requested_at"))
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", require_datetime_text(self.expires_at, "expires_at"))


@dataclass(frozen=True, slots=True)
class ApprovalDecisionRecord(ContractRecord):
    """A durable record of an approval decision."""

    decision_id: str
    request_id: str
    approver_id: str
    status: ApprovalStatus
    decided_at: str
    reason: str | None = None
    executions_used: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "approver_id", require_non_empty_text(self.approver_id, "approver_id"))
        if not isinstance(self.status, ApprovalStatus):
            raise ValueError("status must be an ApprovalStatus value")
        object.__setattr__(self, "decided_at", require_datetime_text(self.decided_at, "decided_at"))

    @property
    def is_active(self) -> bool:
        return self.status is ApprovalStatus.APPROVED

    @property
    def is_terminal(self) -> bool:
        return self.status in (ApprovalStatus.REJECTED, ApprovalStatus.EXPIRED, ApprovalStatus.REVOKED)


@dataclass(frozen=True, slots=True)
class OverrideRecord(ContractRecord):
    """A durable record of a manual override by an operator."""

    override_id: str
    operator_id: str
    override_type: OverrideType
    target_id: str
    original_decision: str
    new_decision: str
    reason: str
    overridden_at: str
    approval_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "override_id", require_non_empty_text(self.override_id, "override_id"))
        object.__setattr__(self, "operator_id", require_non_empty_text(self.operator_id, "operator_id"))
        if not isinstance(self.override_type, OverrideType):
            raise ValueError("override_type must be an OverrideType value")
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "original_decision", require_non_empty_text(self.original_decision, "original_decision"))
        object.__setattr__(self, "new_decision", require_non_empty_text(self.new_decision, "new_decision"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "overridden_at", require_datetime_text(self.overridden_at, "overridden_at"))
