"""Purpose: canonical omni-channel communication surface contracts.
Governance scope: channel identity, inbound/outbound messages, delivery receipts,
    contact/escalation preferences, call sessions/transcripts, communication policy,
    and channel capability manifests.
Dependencies: shared contract base helpers.
Invariants:
  - Every message has explicit channel, direction, and provenance.
  - Delivery receipts are immutable and reference exactly one outbound message.
  - Contact preferences are per-contact, not per-channel.
  - Escalation preferences define fallback chains — not single targets.
  - Call transcripts are append-only segments — no silent mutation.
  - Communication policy is fail-closed: denied channels are recorded with reason.
  - Channel capability manifests declare what each channel can and cannot do.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping, TypeVar, cast

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


ContractT = TypeVar("ContractT", bound=ContractRecord)


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


def _freeze_channel_array(
    values: object,
    field_name: str,
    *,
    allow_empty: bool = True,
) -> tuple[ChannelType, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[Any, ...], freeze_value(list(values)))
    if not allow_empty and not frozen:
        raise ValueError(f"{field_name} must contain at least one item")
    for idx, value in enumerate(frozen):
        if not isinstance(value, ChannelType):
            raise ValueError(f"{field_name}[{idx}] must be a ChannelType value")
    return cast(tuple[ChannelType, ...], frozen)


def _freeze_contract_array(
    values: object,
    field_name: str,
    record_type: type[ContractT],
    *,
    allow_empty: bool = True,
) -> tuple[ContractT, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    frozen = cast(tuple[Any, ...], freeze_value(list(values)))
    if not allow_empty and not frozen:
        raise ValueError(f"{field_name} must contain at least one item")
    for idx, value in enumerate(frozen):
        if not isinstance(value, record_type):
            raise ValueError(f"{field_name}[{idx}] must be a {record_type.__name__}")
    return cast(tuple[ContractT, ...], frozen)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ChannelType(StrEnum):
    """Supported communication channel families."""

    EMAIL = "email"
    SMS = "sms"
    CHAT = "chat"
    VOICE = "voice"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    VIDEO = "video"
    FAX = "fax"


class MessageDirection(StrEnum):
    """Whether a message is inbound or outbound."""

    INBOUND = "inbound"
    OUTBOUND = "outbound"


class DeliveryStatus(StrEnum):
    """Delivery outcome for outbound messages."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    REJECTED = "rejected"
    EXPIRED = "expired"


class CallSessionState(StrEnum):
    """Lifecycle state of a call session."""

    RINGING = "ringing"
    CONNECTED = "connected"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    FAILED = "failed"
    MISSED = "missed"
    VOICEMAIL = "voicemail"


class CommunicationPolicyEffect(StrEnum):
    """Effect of a communication policy evaluation."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
    RATE_LIMITED = "rate_limited"


# ---------------------------------------------------------------------------
# Channel identity
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChannelIdentity(ContractRecord):
    """A contact's identity on a specific channel.

    Maps a contact to their address/handle on a given channel type.
    """

    identity_id: str
    contact_id: str
    channel_type: ChannelType
    address: str
    display_name: str = ""
    verified: bool = False
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "contact_id", require_non_empty_text(self.contact_id, "contact_id"))
        if not isinstance(self.channel_type, ChannelType):
            raise ValueError("channel_type must be a ChannelType value")
        object.__setattr__(self, "address", require_non_empty_text(self.address, "address"))
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Conversation handle
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ConversationHandle(ContractRecord):
    """A thread/conversation reference that groups related messages.

    Conversations span channels — an email thread that continues
    via SMS is still one ConversationHandle.
    """

    conversation_id: str
    subject: str
    contact_ids: tuple[str, ...]
    channel_types: tuple[ChannelType, ...]
    started_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "conversation_id", require_non_empty_text(self.conversation_id, "conversation_id"))
        object.__setattr__(self, "subject", require_non_empty_text(self.subject, "subject"))
        object.__setattr__(
            self,
            "contact_ids",
            _freeze_text_array(self.contact_ids, "contact_ids", allow_empty=False),
        )
        object.__setattr__(
            self,
            "channel_types",
            _freeze_channel_array(self.channel_types, "channel_types"),
        )
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Inbound / Outbound messages
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class InboundMessage(ContractRecord):
    """A message received from an external contact.

    Normalized from any channel into this canonical form.
    """

    message_id: str
    conversation_id: str
    channel_type: ChannelType
    sender_identity_id: str
    body: str
    subject: str = ""
    attachments: tuple[str, ...] = ()
    received_at: str = ""
    raw_payload: Mapping[str, Any] = field(default_factory=dict)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_id", require_non_empty_text(self.message_id, "message_id"))
        object.__setattr__(self, "conversation_id", require_non_empty_text(self.conversation_id, "conversation_id"))
        if not isinstance(self.channel_type, ChannelType):
            raise ValueError("channel_type must be a ChannelType value")
        object.__setattr__(self, "sender_identity_id", require_non_empty_text(self.sender_identity_id, "sender_identity_id"))
        object.__setattr__(self, "body", require_non_empty_text(self.body, "body"))
        object.__setattr__(self, "attachments", _freeze_text_array(self.attachments, "attachments"))
        object.__setattr__(self, "received_at", require_datetime_text(self.received_at, "received_at"))
        object.__setattr__(self, "raw_payload", freeze_value(self.raw_payload))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class OutboundMessage(ContractRecord):
    """A message to be sent to an external contact.

    Normalized from any channel into this canonical form.
    """

    message_id: str
    conversation_id: str
    channel_type: ChannelType
    recipient_identity_id: str
    body: str
    subject: str = ""
    attachments: tuple[str, ...] = ()
    scheduled_at: str = ""
    sent_at: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_id", require_non_empty_text(self.message_id, "message_id"))
        object.__setattr__(self, "conversation_id", require_non_empty_text(self.conversation_id, "conversation_id"))
        if not isinstance(self.channel_type, ChannelType):
            raise ValueError("channel_type must be a ChannelType value")
        object.__setattr__(self, "recipient_identity_id", require_non_empty_text(self.recipient_identity_id, "recipient_identity_id"))
        object.__setattr__(self, "body", require_non_empty_text(self.body, "body"))
        object.__setattr__(self, "attachments", _freeze_text_array(self.attachments, "attachments"))
        object.__setattr__(self, "scheduled_at", require_datetime_text(self.scheduled_at, "scheduled_at"))
        if self.sent_at is not None:
            object.__setattr__(self, "sent_at", require_datetime_text(self.sent_at, "sent_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Delivery receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DeliveryReceipt(ContractRecord):
    """Immutable record of an outbound message's delivery outcome."""

    receipt_id: str
    message_id: str
    status: DeliveryStatus
    channel_type: ChannelType
    delivered_at: str | None = None
    failure_reason: str = ""
    provider_ref: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", require_non_empty_text(self.receipt_id, "receipt_id"))
        object.__setattr__(self, "message_id", require_non_empty_text(self.message_id, "message_id"))
        if not isinstance(self.status, DeliveryStatus):
            raise ValueError("status must be a DeliveryStatus value")
        if not isinstance(self.channel_type, ChannelType):
            raise ValueError("channel_type must be a ChannelType value")
        if self.delivered_at is not None:
            object.__setattr__(self, "delivered_at", require_datetime_text(self.delivered_at, "delivered_at"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Contact / escalation preferences
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContactPreference(ContractRecord):
    """A contact's preferred communication channels and constraints."""

    preference_id: str
    contact_id: str
    preferred_channels: tuple[ChannelType, ...]
    blocked_channels: tuple[ChannelType, ...] = ()
    quiet_hours_start: str = ""
    quiet_hours_end: str = ""
    timezone: str = "UTC"
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "preference_id", require_non_empty_text(self.preference_id, "preference_id"))
        object.__setattr__(self, "contact_id", require_non_empty_text(self.contact_id, "contact_id"))
        object.__setattr__(
            self,
            "preferred_channels",
            _freeze_channel_array(self.preferred_channels, "preferred_channels"),
        )
        object.__setattr__(
            self,
            "blocked_channels",
            _freeze_channel_array(self.blocked_channels, "blocked_channels"),
        )
        object.__setattr__(self, "timezone", require_non_empty_text(self.timezone, "timezone"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class EscalationPreference(ContractRecord):
    """Escalation fallback chain for a contact or team.

    Defines the ordered sequence of channels to try when
    primary communication fails or requires escalation.
    """

    preference_id: str
    contact_id: str
    escalation_chain: tuple[ChannelType, ...]
    max_attempts_per_channel: int = 3
    escalation_timeout_seconds: int = 300
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "preference_id", require_non_empty_text(self.preference_id, "preference_id"))
        object.__setattr__(self, "contact_id", require_non_empty_text(self.contact_id, "contact_id"))
        object.__setattr__(
            self,
            "escalation_chain",
            _freeze_channel_array(self.escalation_chain, "escalation_chain", allow_empty=False),
        )
        object.__setattr__(
            self,
            "max_attempts_per_channel",
            require_positive_int(self.max_attempts_per_channel, "max_attempts_per_channel"),
        )
        object.__setattr__(
            self,
            "escalation_timeout_seconds",
            require_positive_int(self.escalation_timeout_seconds, "escalation_timeout_seconds"),
        )
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Call sessions and transcripts
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CallSession(ContractRecord):
    """A voice/video call session lifecycle record."""

    session_id: str
    conversation_id: str
    channel_type: ChannelType
    participant_ids: tuple[str, ...]
    state: CallSessionState
    started_at: str
    ended_at: str | None = None
    duration_seconds: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "conversation_id", require_non_empty_text(self.conversation_id, "conversation_id"))
        if not isinstance(self.channel_type, ChannelType):
            raise ValueError("channel_type must be a ChannelType value")
        object.__setattr__(
            self,
            "participant_ids",
            _freeze_text_array(self.participant_ids, "participant_ids", allow_empty=False),
        )
        if not isinstance(self.state, CallSessionState):
            raise ValueError("state must be a CallSessionState value")
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        if self.ended_at is not None:
            object.__setattr__(self, "ended_at", require_datetime_text(self.ended_at, "ended_at"))
        if self.duration_seconds is not None:
            object.__setattr__(self, "duration_seconds", require_non_negative_int(self.duration_seconds, "duration_seconds"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


@dataclass(frozen=True, slots=True)
class TranscriptSegment(ContractRecord):
    """A single segment of a call transcript."""

    segment_id: str
    speaker_id: str
    text: str
    started_at: str
    ended_at: str
    confidence: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "segment_id", require_non_empty_text(self.segment_id, "segment_id"))
        object.__setattr__(self, "speaker_id", require_non_empty_text(self.speaker_id, "speaker_id"))
        object.__setattr__(self, "text", require_non_empty_text(self.text, "text"))
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "ended_at", require_datetime_text(self.ended_at, "ended_at"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))


@dataclass(frozen=True, slots=True)
class CallTranscript(ContractRecord):
    """Complete transcript for a call session. Append-only segments."""

    transcript_id: str
    session_id: str
    segments: tuple[TranscriptSegment, ...]
    language: str = "en"
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "transcript_id", require_non_empty_text(self.transcript_id, "transcript_id"))
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(
            self,
            "segments",
            _freeze_contract_array(self.segments, "segments", TranscriptSegment),
        )
        object.__setattr__(self, "language", require_non_empty_text(self.language, "language"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Communication policy
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CommunicationPolicy(ContractRecord):
    """Policy controlling what communication is permitted.

    Fail-closed: if no policy matches, communication is denied.
    """

    policy_id: str
    name: str
    allowed_channels: tuple[ChannelType, ...]
    denied_channels: tuple[ChannelType, ...] = ()
    require_approval_channels: tuple[ChannelType, ...] = ()
    max_outbound_per_hour: int | None = None
    max_outbound_per_day: int | None = None
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(
            self,
            "allowed_channels",
            _freeze_channel_array(self.allowed_channels, "allowed_channels"),
        )
        object.__setattr__(
            self,
            "denied_channels",
            _freeze_channel_array(self.denied_channels, "denied_channels"),
        )
        object.__setattr__(
            self,
            "require_approval_channels",
            _freeze_channel_array(self.require_approval_channels, "require_approval_channels"),
        )
        if self.max_outbound_per_hour is not None:
            object.__setattr__(
                self,
                "max_outbound_per_hour",
                require_positive_int(self.max_outbound_per_hour, "max_outbound_per_hour"),
            )
        if self.max_outbound_per_day is not None:
            object.__setattr__(
                self,
                "max_outbound_per_day",
                require_positive_int(self.max_outbound_per_day, "max_outbound_per_day"),
            )
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class CommunicationPolicyDecision(ContractRecord):
    """Result of evaluating a communication policy for a specific action."""

    decision_id: str
    policy_id: str
    channel_type: ChannelType
    effect: CommunicationPolicyEffect
    reason: str
    evaluated_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        if not isinstance(self.channel_type, ChannelType):
            raise ValueError("channel_type must be a ChannelType value")
        if not isinstance(self.effect, CommunicationPolicyEffect):
            raise ValueError("effect must be a CommunicationPolicyEffect value")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "evaluated_at", require_datetime_text(self.evaluated_at, "evaluated_at"))


# ---------------------------------------------------------------------------
# Channel capability manifest
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChannelCapabilityManifest(ContractRecord):
    """Declares what a channel can and cannot do.

    Used for routing decisions — e.g., voice channels cannot carry
    attachments, SMS has character limits, etc.
    """

    manifest_id: str
    channel_type: ChannelType
    supports_attachments: bool = False
    supports_threading: bool = False
    supports_rich_text: bool = False
    supports_read_receipts: bool = False
    max_body_length: int | None = None
    capabilities: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "manifest_id", require_non_empty_text(self.manifest_id, "manifest_id"))
        if not isinstance(self.channel_type, ChannelType):
            raise ValueError("channel_type must be a ChannelType value")
        for f in ("supports_attachments", "supports_threading", "supports_rich_text", "supports_read_receipts"):
            if not isinstance(getattr(self, f), bool):
                raise ValueError("value must be a boolean flag")
        if self.max_body_length is not None:
            object.__setattr__(
                self,
                "max_body_length",
                require_positive_int(self.max_body_length, "max_body_length"),
            )
        object.__setattr__(self, "capabilities", freeze_value(self.capabilities))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
