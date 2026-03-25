"""Purpose: channel adapter contracts.
Governance scope: typed descriptors, capability manifests, normalized messages,
    health reports, and policy constraints for omni-channel adapter families.
Dependencies: _base contract utilities, communication_surface ChannelType.
Invariants:
  - Every adapter declares its family, direction, and capability manifest.
  - All outputs are frozen and immutable.
  - Reliability scores are unit floats [0.0, 1.0].
  - Rate limits and size constraints are positive integers.
  - Failure modes are explicitly enumerated per adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_positive_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ChannelAdapterFamily(Enum):
    """High-level adapter family classification."""
    SMS = "sms"
    CHAT = "chat"
    VOICE = "voice"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    SOCIAL = "social"
    EMAIL = "email"


class AdapterStatus(Enum):
    """Operational status of an adapter instance."""
    AVAILABLE = "available"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


class AdapterDirection(Enum):
    """Message flow direction an adapter supports."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"
    BIDIRECTIONAL = "bidirectional"


class NormalizationLevel(Enum):
    """How thoroughly inbound messages are normalized."""
    RAW = "raw"
    BASIC = "basic"
    STRUCTURED = "structured"
    SEMANTIC = "semantic"


class DeliveryGuarantee(Enum):
    """Delivery reliability tier."""
    BEST_EFFORT = "best_effort"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AdapterRateLimit(ContractRecord):
    """Rate limiting constraint for an adapter."""

    max_messages_per_second: int = 0
    max_messages_per_minute: int = 0
    max_burst_size: int = 0
    cooldown_seconds: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "max_messages_per_second",
            require_non_negative_int(self.max_messages_per_second, "max_messages_per_second"),
        )
        object.__setattr__(
            self, "max_messages_per_minute",
            require_non_negative_int(self.max_messages_per_minute, "max_messages_per_minute"),
        )
        object.__setattr__(
            self, "max_burst_size",
            require_non_negative_int(self.max_burst_size, "max_burst_size"),
        )
        object.__setattr__(
            self, "cooldown_seconds",
            require_non_negative_int(self.cooldown_seconds, "cooldown_seconds"),
        )


@dataclass(frozen=True, slots=True)
class AdapterPolicyConstraint(ContractRecord):
    """Policy constraint governing adapter behavior."""

    constraint_id: str = ""
    description: str = ""
    constraint_type: str = ""
    value: str = ""
    enforced: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "constraint_id",
            require_non_empty_text(self.constraint_id, "constraint_id"),
        )
        object.__setattr__(
            self, "description",
            require_non_empty_text(self.description, "description"),
        )
        object.__setattr__(
            self, "constraint_type",
            require_non_empty_text(self.constraint_type, "constraint_type"),
        )


@dataclass(frozen=True, slots=True)
class AdapterFailureMode(ContractRecord):
    """Describes a known failure mode for an adapter."""

    mode_id: str = ""
    description: str = ""
    severity: str = "medium"
    is_recoverable: bool = True
    recommended_action: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "mode_id",
            require_non_empty_text(self.mode_id, "mode_id"),
        )
        object.__setattr__(
            self, "description",
            require_non_empty_text(self.description, "description"),
        )
        if self.severity not in ("low", "medium", "high", "critical"):
            raise ValueError("severity must be low, medium, high, or critical")


@dataclass(frozen=True, slots=True)
class AdapterCapabilityManifest(ContractRecord):
    """Full capability manifest for a channel adapter.

    Exposes supported channels, limits, policy constraints,
    reliability score, and known failure modes.
    """

    manifest_id: str = ""
    adapter_id: str = ""
    family: ChannelAdapterFamily = ChannelAdapterFamily.EMAIL
    direction: AdapterDirection = AdapterDirection.BIDIRECTIONAL
    supported_channel_types: tuple[str, ...] = ()
    max_body_bytes: int = 0
    max_attachments: int = 0
    supports_rich_text: bool = False
    supports_attachments: bool = False
    supports_threading: bool = False
    supports_read_receipts: bool = False
    supports_typing_indicator: bool = False
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.BEST_EFFORT
    rate_limit: AdapterRateLimit | None = None
    policy_constraints: tuple[AdapterPolicyConstraint, ...] = ()
    failure_modes: tuple[AdapterFailureMode, ...] = ()
    reliability_score: float = 1.0
    normalization_level: NormalizationLevel = NormalizationLevel.BASIC
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "manifest_id",
            require_non_empty_text(self.manifest_id, "manifest_id"),
        )
        object.__setattr__(
            self, "adapter_id",
            require_non_empty_text(self.adapter_id, "adapter_id"),
        )
        if not isinstance(self.family, ChannelAdapterFamily):
            raise ValueError("family must be a ChannelAdapterFamily")
        if not isinstance(self.direction, AdapterDirection):
            raise ValueError("direction must be an AdapterDirection")
        object.__setattr__(
            self, "supported_channel_types",
            freeze_value(list(self.supported_channel_types)),
        )
        object.__setattr__(
            self, "max_body_bytes",
            require_non_negative_int(self.max_body_bytes, "max_body_bytes"),
        )
        object.__setattr__(
            self, "max_attachments",
            require_non_negative_int(self.max_attachments, "max_attachments"),
        )
        object.__setattr__(
            self, "reliability_score",
            require_unit_float(self.reliability_score, "reliability_score"),
        )
        if not isinstance(self.delivery_guarantee, DeliveryGuarantee):
            raise ValueError("delivery_guarantee must be a DeliveryGuarantee")
        if not isinstance(self.normalization_level, NormalizationLevel):
            raise ValueError("normalization_level must be a NormalizationLevel")
        object.__setattr__(
            self, "policy_constraints",
            freeze_value(list(self.policy_constraints)),
        )
        object.__setattr__(
            self, "failure_modes",
            freeze_value(list(self.failure_modes)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class ChannelAdapterDescriptor(ContractRecord):
    """Canonical descriptor for a registered channel adapter."""

    adapter_id: str = ""
    name: str = ""
    family: ChannelAdapterFamily = ChannelAdapterFamily.EMAIL
    direction: AdapterDirection = AdapterDirection.BIDIRECTIONAL
    status: AdapterStatus = AdapterStatus.AVAILABLE
    provider_name: str = ""
    version: str = "1.0.0"
    manifest_id: str = ""
    tags: tuple[str, ...] = ()
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "adapter_id",
            require_non_empty_text(self.adapter_id, "adapter_id"),
        )
        object.__setattr__(
            self, "name",
            require_non_empty_text(self.name, "name"),
        )
        if not isinstance(self.family, ChannelAdapterFamily):
            raise ValueError("family must be a ChannelAdapterFamily")
        if not isinstance(self.direction, AdapterDirection):
            raise ValueError("direction must be an AdapterDirection")
        if not isinstance(self.status, AdapterStatus):
            raise ValueError("status must be an AdapterStatus")
        object.__setattr__(
            self, "version",
            require_non_empty_text(self.version, "version"),
        )
        object.__setattr__(
            self, "tags",
            freeze_value(list(self.tags)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class NormalizedInbound(ContractRecord):
    """Adapter-normalized inbound message."""

    message_id: str = ""
    adapter_id: str = ""
    family: ChannelAdapterFamily = ChannelAdapterFamily.EMAIL
    sender_address: str = ""
    body_text: str = ""
    body_html: str = ""
    subject: str = ""
    thread_id: str = ""
    attachment_refs: tuple[str, ...] = ()
    normalization_level: NormalizationLevel = NormalizationLevel.BASIC
    raw_payload: Mapping[str, Any] = field(default_factory=dict)
    received_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "message_id",
            require_non_empty_text(self.message_id, "message_id"),
        )
        object.__setattr__(
            self, "adapter_id",
            require_non_empty_text(self.adapter_id, "adapter_id"),
        )
        if not isinstance(self.family, ChannelAdapterFamily):
            raise ValueError("family must be a ChannelAdapterFamily")
        object.__setattr__(
            self, "attachment_refs",
            freeze_value(list(self.attachment_refs)),
        )
        object.__setattr__(
            self, "raw_payload",
            freeze_value(dict(self.raw_payload)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.received_at, "received_at")


@dataclass(frozen=True, slots=True)
class NormalizedOutbound(ContractRecord):
    """Adapter-normalized outbound message."""

    message_id: str = ""
    adapter_id: str = ""
    family: ChannelAdapterFamily = ChannelAdapterFamily.EMAIL
    recipient_address: str = ""
    body_text: str = ""
    body_html: str = ""
    subject: str = ""
    thread_id: str = ""
    attachment_refs: tuple[str, ...] = ()
    priority: str = "normal"
    prepared_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "message_id",
            require_non_empty_text(self.message_id, "message_id"),
        )
        object.__setattr__(
            self, "adapter_id",
            require_non_empty_text(self.adapter_id, "adapter_id"),
        )
        if not isinstance(self.family, ChannelAdapterFamily):
            raise ValueError("family must be a ChannelAdapterFamily")
        object.__setattr__(
            self, "recipient_address",
            require_non_empty_text(self.recipient_address, "recipient_address"),
        )
        if self.priority not in ("low", "normal", "high", "urgent"):
            raise ValueError("priority must be low, normal, high, or urgent")
        object.__setattr__(
            self, "attachment_refs",
            freeze_value(list(self.attachment_refs)),
        )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )
        require_datetime_text(self.prepared_at, "prepared_at")


@dataclass(frozen=True, slots=True)
class AdapterHealthReport(ContractRecord):
    """Point-in-time health report for a channel adapter."""

    report_id: str = ""
    adapter_id: str = ""
    status: AdapterStatus = AdapterStatus.AVAILABLE
    reliability_score: float = 1.0
    messages_sent: int = 0
    messages_received: int = 0
    messages_failed: int = 0
    avg_latency_ms: float = 0.0
    active_failure_modes: tuple[str, ...] = ()
    reported_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "report_id",
            require_non_empty_text(self.report_id, "report_id"),
        )
        object.__setattr__(
            self, "adapter_id",
            require_non_empty_text(self.adapter_id, "adapter_id"),
        )
        if not isinstance(self.status, AdapterStatus):
            raise ValueError("status must be an AdapterStatus")
        object.__setattr__(
            self, "reliability_score",
            require_unit_float(self.reliability_score, "reliability_score"),
        )
        object.__setattr__(
            self, "messages_sent",
            require_non_negative_int(self.messages_sent, "messages_sent"),
        )
        object.__setattr__(
            self, "messages_received",
            require_non_negative_int(self.messages_received, "messages_received"),
        )
        object.__setattr__(
            self, "messages_failed",
            require_non_negative_int(self.messages_failed, "messages_failed"),
        )
        object.__setattr__(
            self, "active_failure_modes",
            freeze_value(list(self.active_failure_modes)),
        )
        require_datetime_text(self.reported_at, "reported_at")
