"""Purpose: canonical contact / identity graph contracts.
Governance scope: identity records, channel handles, identity links,
    contact preferences, availability, escalation chains, identity resolution,
    and routing decisions.
Dependencies: shared contract base helpers, communication_surface enums.
Invariants:
  - Every identity has explicit type, display name, and creation timestamp.
  - Channel handles always reference a real identity.
  - Escalation chains are ordered and deterministic.
  - Routing decisions are immutable audit records.
  - Identity links are explicit — never inferred silently.
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
    require_non_negative_int,
)
from .communication_surface import ChannelType


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class IdentityType(StrEnum):
    """What kind of entity this identity represents."""

    PERSON = "person"
    TEAM = "team"
    FUNCTION = "function"
    ORGANIZATION = "organization"
    SYSTEM = "system"
    PROVIDER = "provider"
    OPERATOR = "operator"
    UNKNOWN = "unknown"


class ChannelPreferenceLevel(StrEnum):
    """How preferred a channel handle is for contacting this identity."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    EMERGENCY_ONLY = "emergency_only"
    DISABLED = "disabled"


class AvailabilityState(StrEnum):
    """Current availability of an identity."""

    AVAILABLE = "available"
    LIMITED = "limited"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class EscalationMode(StrEnum):
    """How escalation targets should be contacted."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    EMERGENCY_BROADCAST = "emergency_broadcast"


# ---------------------------------------------------------------------------
# Identity record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityRecord(ContractRecord):
    """Canonical identity record for a person, team, system, or org."""

    identity_id: str
    identity_type: IdentityType
    display_name: str
    organization_id: str = ""
    team_id: str = ""
    role_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    created_at: str = ""
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        if not isinstance(self.identity_type, IdentityType):
            raise ValueError("identity_type must be an IdentityType value")
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "role_ids", freeze_value(list(self.role_ids)))
        object.__setattr__(self, "tags", freeze_value(list(self.tags)))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "updated_at", require_datetime_text(self.updated_at, "updated_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Channel handle
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ChannelHandle(ContractRecord):
    """A specific channel address belonging to an identity."""

    handle_id: str
    identity_id: str
    channel_type: ChannelType
    address: str
    verified: bool = False
    preference_level: ChannelPreferenceLevel = ChannelPreferenceLevel.SECONDARY
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "handle_id", require_non_empty_text(self.handle_id, "handle_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        if not isinstance(self.channel_type, ChannelType):
            raise ValueError("channel_type must be a ChannelType value")
        object.__setattr__(self, "address", require_non_empty_text(self.address, "address"))
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean")
        if not isinstance(self.preference_level, ChannelPreferenceLevel):
            raise ValueError("preference_level must be a ChannelPreferenceLevel value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Identity link
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityLink(ContractRecord):
    """Explicit link between two identities (e.g. person→team, team→org)."""

    link_id: str
    from_identity_id: str
    to_identity_id: str
    relation: str
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "link_id", require_non_empty_text(self.link_id, "link_id"))
        object.__setattr__(self, "from_identity_id", require_non_empty_text(self.from_identity_id, "from_identity_id"))
        object.__setattr__(self, "to_identity_id", require_non_empty_text(self.to_identity_id, "to_identity_id"))
        if self.from_identity_id == self.to_identity_id:
            raise ValueError("identity link cannot be self-referential")
        object.__setattr__(self, "relation", require_non_empty_text(self.relation, "relation"))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))


# ---------------------------------------------------------------------------
# Contact preference record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ContactPreferenceRecord(ContractRecord):
    """Contact preferences for an identity — channel ordering and restrictions."""

    preference_id: str
    identity_id: str
    preferred_channels: tuple[ChannelType, ...] = ()
    blocked_channels: tuple[ChannelType, ...] = ()
    quiet_hours_start: str = ""
    quiet_hours_end: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "preference_id", require_non_empty_text(self.preference_id, "preference_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        object.__setattr__(self, "preferred_channels", freeze_value(list(self.preferred_channels)))
        for ch in self.preferred_channels:
            if not isinstance(ch, ChannelType):
                raise ValueError("each preferred_channel must be a ChannelType value")
        object.__setattr__(self, "blocked_channels", freeze_value(list(self.blocked_channels)))
        for ch in self.blocked_channels:
            if not isinstance(ch, ChannelType):
                raise ValueError("each blocked_channel must be a ChannelType value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Availability window
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AvailabilityWindow(ContractRecord):
    """Current availability state for an identity."""

    window_id: str
    identity_id: str
    state: AvailabilityState
    reason: str = ""
    valid_from: str = ""
    valid_until: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "window_id", require_non_empty_text(self.window_id, "window_id"))
        object.__setattr__(self, "identity_id", require_non_empty_text(self.identity_id, "identity_id"))
        if not isinstance(self.state, AvailabilityState):
            raise ValueError("state must be an AvailabilityState value")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Escalation chain record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class EscalationChainRecord(ContractRecord):
    """Ordered escalation chain with mode and target identities."""

    chain_id: str
    name: str
    mode: EscalationMode
    target_identity_ids: tuple[str, ...]
    timeout_minutes: int = 30
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "chain_id", require_non_empty_text(self.chain_id, "chain_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.mode, EscalationMode):
            raise ValueError("mode must be an EscalationMode value")
        object.__setattr__(self, "target_identity_ids", freeze_value(list(self.target_identity_ids)))
        if not self.target_identity_ids:
            raise ValueError("escalation chain must have at least one target")
        for tid in self.target_identity_ids:
            if not isinstance(tid, str) or not tid.strip():
                raise ValueError("each target_identity_id must be a non-empty string")
        object.__setattr__(self, "timeout_minutes", require_non_negative_int(self.timeout_minutes, "timeout_minutes"))
        if self.timeout_minutes == 0:
            raise ValueError("timeout_minutes must be positive")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


# ---------------------------------------------------------------------------
# Identity resolution record
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityResolutionRecord(ContractRecord):
    """Record of resolving an external reference to a canonical identity."""

    resolution_id: str
    resolved_identity_id: str
    source_ref: str
    source_type: str
    confidence: float = 1.0
    resolved_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "resolution_id", require_non_empty_text(self.resolution_id, "resolution_id"))
        object.__setattr__(self, "resolved_identity_id", require_non_empty_text(self.resolved_identity_id, "resolved_identity_id"))
        object.__setattr__(self, "source_ref", require_non_empty_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "source_type", require_non_empty_text(self.source_type, "source_type"))
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        object.__setattr__(self, "resolved_at", require_datetime_text(self.resolved_at, "resolved_at"))


# ---------------------------------------------------------------------------
# Identity routing decision
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IdentityRoutingDecision(ContractRecord):
    """Immutable record of a routing decision for contacting an identity."""

    decision_id: str
    target_identity_id: str
    selected_handle_id: str
    reason: str
    fallback_handle_ids: tuple[str, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "target_identity_id", require_non_empty_text(self.target_identity_id, "target_identity_id"))
        object.__setattr__(self, "selected_handle_id", require_non_empty_text(self.selected_handle_id, "selected_handle_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        object.__setattr__(self, "fallback_handle_ids", freeze_value(list(self.fallback_handle_ids)))
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))
