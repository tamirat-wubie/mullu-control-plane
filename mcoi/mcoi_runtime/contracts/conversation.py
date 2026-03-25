"""Purpose: canonical conversation thread and threaded messaging contracts.
Governance scope: threaded communication contract typing only.
Dependencies: shared contract base helpers.
Invariants:
  - Every message belongs to a thread.
  - Every thread has explicit lifecycle status.
  - Message attribution MUST NOT be fabricated.
  - No mutation after thread close.
  - StatusReport progress_pct is bounded [0, 100].
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
)


class ThreadStatus(StrEnum):
    """Lifecycle status for a conversation thread."""

    OPEN = "open"
    ACTIVE = "active"
    WAITING = "waiting"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MessageDirection(StrEnum):
    """Direction of a thread message."""

    OUTBOUND = "outbound"
    INBOUND = "inbound"


class MessageType(StrEnum):
    """Canonical message types within a conversation thread."""

    REQUEST = "request"
    RESPONSE = "response"
    CLARIFICATION_REQUEST = "clarification_request"
    CLARIFICATION_RESPONSE = "clarification_response"
    STATUS_UPDATE = "status_update"
    FOLLOW_UP = "follow_up"


@dataclass(frozen=True, slots=True)
class ThreadMessage(ContractRecord):
    """A single message within a conversation thread."""

    message_id: str
    thread_id: str
    direction: MessageDirection
    message_type: MessageType
    content: str
    sender_id: str
    recipient_id: str
    sent_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("message_id", "thread_id", "content", "sender_id", "recipient_id"):
            object.__setattr__(
                self, field_name, require_non_empty_text(getattr(self, field_name), field_name)
            )
        if not isinstance(self.direction, MessageDirection):
            raise ValueError("direction must be a MessageDirection value")
        if not isinstance(self.message_type, MessageType):
            raise ValueError("message_type must be a MessageType value")
        object.__setattr__(self, "sent_at", require_datetime_text(self.sent_at, "sent_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ConversationThread(ContractRecord):
    """A tracked multi-turn conversation thread."""

    thread_id: str
    subject: str
    status: ThreadStatus
    messages: tuple[ThreadMessage, ...] = ()
    goal_id: str | None = None
    workflow_id: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "thread_id", require_non_empty_text(self.thread_id, "thread_id"))
        object.__setattr__(self, "subject", require_non_empty_text(self.subject, "subject"))
        if not isinstance(self.status, ThreadStatus):
            raise ValueError("status must be a ThreadStatus value")
        object.__setattr__(self, "messages", freeze_value(list(self.messages)))
        object.__setattr__(
            self, "created_at", require_datetime_text(self.created_at, "created_at")
        )
        object.__setattr__(
            self, "updated_at", require_datetime_text(self.updated_at, "updated_at")
        )
        if self.goal_id is not None:
            object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        if self.workflow_id is not None:
            object.__setattr__(self, "workflow_id", require_non_empty_text(self.workflow_id, "workflow_id"))


@dataclass(frozen=True, slots=True)
class ClarificationRequest(ContractRecord):
    """A structured clarification question within a thread."""

    request_id: str
    thread_id: str
    question: str
    context: str
    requested_from_id: str
    requested_at: str
    response_deadline: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("request_id", "thread_id", "question", "context", "requested_from_id"):
            object.__setattr__(
                self, field_name, require_non_empty_text(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self, "requested_at", require_datetime_text(self.requested_at, "requested_at")
        )
        if self.response_deadline is not None:
            object.__setattr__(
                self,
                "response_deadline",
                require_datetime_text(self.response_deadline, "response_deadline"),
            )


@dataclass(frozen=True, slots=True)
class ClarificationResponse(ContractRecord):
    """The answer to a clarification request."""

    request_id: str
    thread_id: str
    answer: str
    responded_by_id: str
    responded_at: str

    def __post_init__(self) -> None:
        for field_name in ("request_id", "thread_id", "answer", "responded_by_id"):
            object.__setattr__(
                self, field_name, require_non_empty_text(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self, "responded_at", require_datetime_text(self.responded_at, "responded_at")
        )


@dataclass(frozen=True, slots=True)
class FollowUpRecord(ContractRecord):
    """A scheduled follow-up action linked to a thread."""

    follow_up_id: str
    thread_id: str
    reason: str
    scheduled_at: str
    executed_at: str | None = None
    resolved: bool = False

    def __post_init__(self) -> None:
        for field_name in ("follow_up_id", "thread_id", "reason"):
            object.__setattr__(
                self, field_name, require_non_empty_text(getattr(self, field_name), field_name)
            )
        object.__setattr__(
            self, "scheduled_at", require_datetime_text(self.scheduled_at, "scheduled_at")
        )
        if self.executed_at is not None:
            object.__setattr__(
                self, "executed_at", require_datetime_text(self.executed_at, "executed_at")
            )
        if not isinstance(self.resolved, bool):
            raise ValueError("resolved must be a boolean")


@dataclass(frozen=True, slots=True)
class StatusReport(ContractRecord):
    """A point-in-time progress report for a thread or linked goal."""

    report_id: str
    thread_id: str
    goal_id: str | None
    summary: str
    progress_pct: int
    reported_at: str

    def __post_init__(self) -> None:
        for field_name in ("report_id", "thread_id", "summary"):
            object.__setattr__(
                self, field_name, require_non_empty_text(getattr(self, field_name), field_name)
            )
        if self.goal_id is not None:
            require_non_empty_text(self.goal_id, "goal_id")
        if not isinstance(self.progress_pct, int) or not (0 <= self.progress_pct <= 100):
            raise ValueError("progress_pct must be an integer between 0 and 100")
        object.__setattr__(
            self, "reported_at", require_datetime_text(self.reported_at, "reported_at")
        )
