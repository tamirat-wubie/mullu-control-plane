"""Purpose: canonical operator identity and attribution contracts.
Governance scope: operator identity, approval actor, and audit attribution typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every human action carries explicit operator identity.
  - Approval decisions are attributed to a specific operator.
  - Manual overrides are auditable.
  - System actions are distinguished from human actions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class ActorType(StrEnum):
    HUMAN = "human"
    SYSTEM = "system"
    AUTOMATED = "automated"


class OperatorRole(StrEnum):
    OBSERVER = "observer"
    OPERATOR = "operator"
    APPROVER = "approver"
    ADMIN = "admin"


@dataclass(frozen=True, slots=True)
class OperatorIdentity(ContractRecord):
    """Identity of a human or system operator."""

    operator_id: str
    name: str
    actor_type: ActorType
    role: OperatorRole
    email: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "operator_id", require_non_empty_text(self.operator_id, "operator_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.actor_type, ActorType):
            raise ValueError("actor_type must be an ActorType value")
        if not isinstance(self.role, OperatorRole):
            raise ValueError("role must be an OperatorRole value")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ActionAttribution(ContractRecord):
    """Links an action to the operator who initiated or approved it."""

    attribution_id: str
    operator_id: str
    action_type: str
    target_id: str
    timestamp: str
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "attribution_id", require_non_empty_text(self.attribution_id, "attribution_id"))
        object.__setattr__(self, "operator_id", require_non_empty_text(self.operator_id, "operator_id"))
        object.__setattr__(self, "action_type", require_non_empty_text(self.action_type, "action_type"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "timestamp", require_non_empty_text(self.timestamp, "timestamp"))


@dataclass(frozen=True, slots=True)
class ApprovalAttribution(ContractRecord):
    """Links an approval decision to the approver."""

    approval_id: str
    approver_id: str
    decision: str
    target_id: str
    correlation_id: str
    timestamp: str
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "approval_id", require_non_empty_text(self.approval_id, "approval_id"))
        object.__setattr__(self, "approver_id", require_non_empty_text(self.approver_id, "approver_id"))
        object.__setattr__(self, "decision", require_non_empty_text(self.decision, "decision"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "correlation_id", require_non_empty_text(self.correlation_id, "correlation_id"))
        object.__setattr__(self, "timestamp", require_non_empty_text(self.timestamp, "timestamp"))


@dataclass(frozen=True, slots=True)
class ManualOverride(ContractRecord):
    """Record of a human override of system behavior."""

    override_id: str
    operator_id: str
    overridden_decision_id: str
    original_status: str
    new_status: str
    reason: str
    timestamp: str

    def __post_init__(self) -> None:
        for f in ("override_id", "operator_id", "overridden_decision_id",
                   "original_status", "new_status", "reason", "timestamp"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))


@dataclass(frozen=True, slots=True)
class AuditEntry(ContractRecord):
    """Audit trail entry linking operator action to system artifact."""

    entry_id: str
    operator_id: str
    actor_type: ActorType
    action: str
    target_artifact_id: str
    timestamp: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "entry_id", require_non_empty_text(self.entry_id, "entry_id"))
        object.__setattr__(self, "operator_id", require_non_empty_text(self.operator_id, "operator_id"))
        if not isinstance(self.actor_type, ActorType):
            raise ValueError("actor_type must be an ActorType value")
        object.__setattr__(self, "action", require_non_empty_text(self.action, "action"))
        object.__setattr__(self, "target_artifact_id", require_non_empty_text(self.target_artifact_id, "target_artifact_id"))
        object.__setattr__(self, "timestamp", require_non_empty_text(self.timestamp, "timestamp"))
        object.__setattr__(self, "details", freeze_value(self.details))
