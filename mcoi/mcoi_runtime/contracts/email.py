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
from typing import Any, Mapping, cast

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text


def _freeze_text_array(
    values: object,
    field_name: str,
    *,
    allow_empty: bool = True,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[Any, ...], freeze_value(list(values)))
    if not allow_empty and not frozen:
        raise ValueError(f"{field_name} must contain at least one item")
    for idx, value in enumerate(frozen):
        require_non_empty_text(value, f"{field_name}[{idx}]")
    return cast(tuple[str, ...], frozen)


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
        object.__setattr__(
            self,
            "recipients",
            _freeze_text_array(self.recipients, "recipients", allow_empty=False),
        )
        object.__setattr__(self, "subject", require_non_empty_text(self.subject, "subject"))
        if self.sent_at is not None:
            object.__setattr__(self, "sent_at", require_datetime_text(self.sent_at, "sent_at"))


@dataclass(frozen=True, slots=True)
class EmailThreadRef(ContractRecord):
    """Reference linking an email to a conversation thread."""

    thread_id: str
    in_reply_to: str | None = None
    references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "thread_id", require_non_empty_text(self.thread_id, "thread_id"))
        if self.in_reply_to is not None:
            object.__setattr__(self, "in_reply_to", require_non_empty_text(self.in_reply_to, "in_reply_to"))
        object.__setattr__(self, "references", _freeze_text_array(self.references, "references"))


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
        for field_name in ("skill_id", "execution_id", "goal_id", "trace_id", "runbook_id"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, require_non_empty_text(value, field_name))


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
        if self.thread is not None and not isinstance(self.thread, EmailThreadRef):
            raise ValueError("thread must be an EmailThreadRef instance")
        if self.workflow_link is not None and not isinstance(self.workflow_link, EmailWorkflowLink):
            raise ValueError("workflow_link must be an EmailWorkflowLink instance")
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
        if self.reason is not None:
            object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))


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
        if self.detected_purpose is not None and not isinstance(self.detected_purpose, EmailPurpose):
            raise ValueError("detected_purpose must be an EmailPurpose value")
        if self.approval_response is not None and not isinstance(self.approval_response, ApprovalResponse):
            raise ValueError("approval_response must be an ApprovalResponse instance")
        if self.error_message is not None:
            object.__setattr__(self, "error_message", require_non_empty_text(self.error_message, "error_message"))


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
        if self.action_type is not None:
            object.__setattr__(self, "action_type", require_non_empty_text(self.action_type, "action_type"))
        if self.suggested_skill_id is not None:
            object.__setattr__(
                self,
                "suggested_skill_id",
                require_non_empty_text(self.suggested_skill_id, "suggested_skill_id"),
            )
        object.__setattr__(self, "action_parameters", freeze_value(self.action_parameters))
