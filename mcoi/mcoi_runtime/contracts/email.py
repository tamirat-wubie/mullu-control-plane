"""Purpose: canonical email workflow contract mapping.
Governance scope: email message, envelope, parsing, approval, and workflow linkage typing.
Dependencies: shared contract base helpers.
Invariants:
  - Every email carries explicit identity and correlation.
  - Approval parsing is explicit — ambiguous responses fail closed.
  - Workflow correlation IDs link emails to skills, runs, and traces.
  - No fabricated sender/recipient attribution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class EmailDirection(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class EmailPurpose(StrEnum):
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_RESPONSE = "approval_response"
    ESCALATION = "escalation"
    NOTIFICATION = "notification"
    COMPLETION = "completion"
    GENERAL = "general"


class ApprovalDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"


class EmailParseStatus(StrEnum):
    PARSED = "parsed"
    MALFORMED = "malformed"
    UNSUPPORTED = "unsupported"


class ActionExtractionStatus(StrEnum):
    ACTION_FOUND = "action_found"
    NO_ACTION = "no_action"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class EmailEnvelope(ContractRecord):
    """Addressing and routing metadata for an email."""

    sender: str
    recipients: tuple[str, ...]
    subject: str
    sent_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sender", require_non_empty_text(self.sender, "sender"))
        if not self.recipients:
            raise ValueError("recipients must contain at least one address")
        for idx, r in enumerate(self.recipients):
            require_non_empty_text(r, f"recipients[{idx}]")
        object.__setattr__(self, "recipients", freeze_value(list(self.recipients)))
        object.__setattr__(self, "subject", require_non_empty_text(self.subject, "subject"))


@dataclass(frozen=True, slots=True)
class EmailThreadRef(ContractRecord):
    """Reference linking an email to a conversation thread."""

    thread_id: str
    in_reply_to: str | None = None
    references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "thread_id", require_non_empty_text(self.thread_id, "thread_id"))
        object.__setattr__(self, "references", freeze_value(list(self.references)))


@dataclass(frozen=True, slots=True)
class EmailWorkflowLink(ContractRecord):
    """Correlation IDs linking an email to platform workflow artifacts."""

    correlation_id: str
    skill_id: str | None = None
    execution_id: str | None = None
    goal_id: str | None = None
    trace_id: str | None = None
    runbook_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "correlation_id", require_non_empty_text(self.correlation_id, "correlation_id"))


@dataclass(frozen=True, slots=True)
class EmailMessage(ContractRecord):
    """A typed email message with identity, direction, and workflow linkage."""

    message_id: str
    direction: EmailDirection
    purpose: EmailPurpose
    envelope: EmailEnvelope
    body: str
    thread: EmailThreadRef | None = None
    workflow_link: EmailWorkflowLink | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_id", require_non_empty_text(self.message_id, "message_id"))
        if not isinstance(self.direction, EmailDirection):
            raise ValueError("direction must be an EmailDirection value")
        if not isinstance(self.purpose, EmailPurpose):
            raise ValueError("purpose must be an EmailPurpose value")
        if not isinstance(self.envelope, EmailEnvelope):
            raise ValueError("envelope must be an EmailEnvelope instance")
        if not isinstance(self.body, str):
            raise ValueError("body must be a string")
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class ApprovalResponse(ContractRecord):
    """Parsed approval decision from an inbound email."""

    response_id: str
    message_id: str
    correlation_id: str
    decision: ApprovalDecision
    responder: str
    reason: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "response_id", require_non_empty_text(self.response_id, "response_id"))
        object.__setattr__(self, "message_id", require_non_empty_text(self.message_id, "message_id"))
        object.__setattr__(self, "correlation_id", require_non_empty_text(self.correlation_id, "correlation_id"))
        if not isinstance(self.decision, ApprovalDecision):
            raise ValueError("decision must be an ApprovalDecision value")
        object.__setattr__(self, "responder", require_non_empty_text(self.responder, "responder"))


@dataclass(frozen=True, slots=True)
class EmailParseResult(ContractRecord):
    """Result of parsing an inbound email."""

    parse_id: str
    message_id: str
    status: EmailParseStatus
    detected_purpose: EmailPurpose | None = None
    approval_response: ApprovalResponse | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "parse_id", require_non_empty_text(self.parse_id, "parse_id"))
        object.__setattr__(self, "message_id", require_non_empty_text(self.message_id, "message_id"))
        if not isinstance(self.status, EmailParseStatus):
            raise ValueError("status must be an EmailParseStatus value")


@dataclass(frozen=True, slots=True)
class EmailActionExtraction(ContractRecord):
    """Extracted actionable signal from an email."""

    extraction_id: str
    message_id: str
    status: ActionExtractionStatus
    action_type: str | None = None
    action_parameters: Mapping[str, Any] = field(default_factory=dict)
    suggested_skill_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "extraction_id", require_non_empty_text(self.extraction_id, "extraction_id"))
        object.__setattr__(self, "message_id", require_non_empty_text(self.message_id, "message_id"))
        if not isinstance(self.status, ActionExtractionStatus):
            raise ValueError("status must be an ActionExtractionStatus value")
        object.__setattr__(self, "action_parameters", freeze_value(self.action_parameters))
