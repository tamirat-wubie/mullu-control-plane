"""Purpose: canonical obligation runtime contracts for ownership, deadlines,
transfers, escalations, and closures.
Governance scope: obligation plane contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Obligations are created from events or subsystem actions.
  - Every obligation has an owner, deadline, and explicit state.
  - Transfers preserve history.
  - Closures are explicit — never silent.
  - Escalations are typed and traceable.
  - All timestamps are ISO-8601.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ObligationState(StrEnum):
    """Lifecycle state of an obligation."""

    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    EXPIRED = "expired"
    ESCALATED = "escalated"
    TRANSFERRED = "transferred"
    CANCELLED = "cancelled"


class ObligationTrigger(StrEnum):
    """What created this obligation."""

    APPROVAL_REQUEST = "approval_request"
    JOB_ASSIGNMENT = "job_assignment"
    REVIEW_REQUEST = "review_request"
    COMMUNICATION_FOLLOW_UP = "communication_follow_up"
    INCIDENT_SLA = "incident_sla"
    ESCALATION_ACK = "escalation_ack"
    WORKFLOW_STAGE = "workflow_stage"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Core obligation records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObligationOwner(ContractRecord):
    """Identifies who owns an obligation."""

    owner_id: str
    owner_type: str
    display_name: str

    def __post_init__(self) -> None:
        for f in ("owner_id", "owner_type", "display_name"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))


@dataclass(frozen=True, slots=True)
class ObligationDeadline(ContractRecord):
    """Deadline specification for an obligation."""

    deadline_id: str
    due_at: str
    warn_at: str | None = None
    hard: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "deadline_id",
            require_non_empty_text(self.deadline_id, "deadline_id"),
        )
        object.__setattr__(
            self, "due_at",
            require_datetime_text(self.due_at, "due_at"),
        )
        if self.warn_at is not None:
            object.__setattr__(
                self, "warn_at",
                require_datetime_text(self.warn_at, "warn_at"),
            )


@dataclass(frozen=True, slots=True)
class ObligationRecord(ContractRecord):
    """A first-class obligation owed by an owner, traceable to its trigger.

    Obligations are never silently resolved — closure, transfer, escalation,
    and expiry are all explicit typed operations.
    """

    obligation_id: str
    trigger: ObligationTrigger
    trigger_ref_id: str
    state: ObligationState
    owner: ObligationOwner
    deadline: ObligationDeadline
    description: str
    correlation_id: str
    metadata: Mapping[str, Any]
    created_at: str
    updated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "obligation_id",
            require_non_empty_text(self.obligation_id, "obligation_id"),
        )
        if not isinstance(self.trigger, ObligationTrigger):
            raise ValueError("trigger must be an ObligationTrigger value")
        object.__setattr__(
            self, "trigger_ref_id",
            require_non_empty_text(self.trigger_ref_id, "trigger_ref_id"),
        )
        if not isinstance(self.state, ObligationState):
            raise ValueError("state must be an ObligationState value")
        if not isinstance(self.owner, ObligationOwner):
            raise ValueError("owner must be an ObligationOwner instance")
        if not isinstance(self.deadline, ObligationDeadline):
            raise ValueError("deadline must be an ObligationDeadline instance")
        object.__setattr__(
            self, "description",
            require_non_empty_text(self.description, "description"),
        )
        object.__setattr__(
            self, "correlation_id",
            require_non_empty_text(self.correlation_id, "correlation_id"),
        )
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
        object.__setattr__(
            self, "created_at",
            require_datetime_text(self.created_at, "created_at"),
        )
        object.__setattr__(
            self, "updated_at",
            require_datetime_text(self.updated_at, "updated_at"),
        )


# ---------------------------------------------------------------------------
# Obligation lifecycle records
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ObligationClosure(ContractRecord):
    """Explicit closure of an obligation — satisfied, cancelled, or expired."""

    closure_id: str
    obligation_id: str
    final_state: ObligationState
    reason: str
    closed_by: str
    closed_at: str

    def __post_init__(self) -> None:
        for f in ("closure_id", "obligation_id", "reason", "closed_by"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        if not isinstance(self.final_state, ObligationState):
            raise ValueError("final_state must be an ObligationState value")
        if self.final_state not in (
            ObligationState.COMPLETED,
            ObligationState.EXPIRED,
            ObligationState.CANCELLED,
        ):
            raise ValueError(
                "final_state must be a terminal closure state"
            )
        object.__setattr__(
            self, "closed_at",
            require_datetime_text(self.closed_at, "closed_at"),
        )


@dataclass(frozen=True, slots=True)
class ObligationTransfer(ContractRecord):
    """Transfer of an obligation from one owner to another."""

    transfer_id: str
    obligation_id: str
    from_owner: ObligationOwner
    to_owner: ObligationOwner
    reason: str
    transferred_at: str

    def __post_init__(self) -> None:
        for f in ("transfer_id", "obligation_id", "reason"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        if not isinstance(self.from_owner, ObligationOwner):
            raise ValueError("from_owner must be an ObligationOwner instance")
        if not isinstance(self.to_owner, ObligationOwner):
            raise ValueError("to_owner must be an ObligationOwner instance")
        if self.from_owner.owner_id == self.to_owner.owner_id:
            raise ValueError("cannot transfer obligation to the same owner")
        object.__setattr__(
            self, "transferred_at",
            require_datetime_text(self.transferred_at, "transferred_at"),
        )


@dataclass(frozen=True, slots=True)
class ObligationEscalation(ContractRecord):
    """Escalation of an obligation — deadline breach or explicit escalation."""

    escalation_id: str
    obligation_id: str
    escalated_to: ObligationOwner
    reason: str
    severity: str
    escalated_at: str

    def __post_init__(self) -> None:
        for f in ("escalation_id", "obligation_id", "reason", "severity"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        if not isinstance(self.escalated_to, ObligationOwner):
            raise ValueError("escalated_to must be an ObligationOwner instance")
        object.__setattr__(
            self, "escalated_at",
            require_datetime_text(self.escalated_at, "escalated_at"),
        )
