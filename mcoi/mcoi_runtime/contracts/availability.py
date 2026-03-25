"""Purpose: human availability, calendar, and meeting runtime contracts.
Governance scope: typed descriptors for person/team/function availability,
    business hours, quiet hours, meeting windows, response SLAs, availability
    conflicts, and routing decisions that account for human time.
Dependencies: _base contract utilities.
Invariants:
  - Every availability record has explicit kind and resolution.
  - Meeting decisions are immutable.
  - Business hours are deterministic given timezone.
  - All outputs are frozen.
  - Cross-field invariants: starts_at < ends_at, reserved <= capacity,
    escalation_after_seconds <= max_response_seconds, hour fields 0-23,
    weekday_start_hour < weekday_end_hour.

Note on AvailabilityKind vs contact_identity.AvailabilityState:
  - AvailabilityKind classifies *policy/window types* (vacation, quiet hours, etc.)
  - AvailabilityState (contact_identity) represents *current real-time state* (available/limited/unavailable)
  These are complementary: a VACATION AvailabilityKind record produces an UNAVAILABLE AvailabilityState.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


def _require_hour(value: int, field_name: str) -> int:
    """Validate that an hour value is in range 0-23."""
    v = require_non_negative_int(value, field_name)
    if v > 23:
        raise ValueError(f"{field_name} must be 0-23, got {v}")
    return v


def _require_positive_int(value: int, field_name: str) -> int:
    """Validate that an integer is strictly positive (>= 1)."""
    v = require_non_negative_int(value, field_name)
    if v < 1:
        raise ValueError(f"{field_name} must be >= 1, got {v}")
    return v


def _require_starts_before_ends(starts_at: str, ends_at: str) -> None:
    """Validate that starts_at is chronologically before ends_at."""
    try:
        s = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        e = datetime.fromisoformat(ends_at.replace("Z", "+00:00"))
        if s >= e:
            raise ValueError(
                f"starts_at ({starts_at}) must be before ends_at ({ends_at})"
            )
    except (ValueError, TypeError) as exc:
        if "must be before" in str(exc):
            raise
        # datetime parsing errors are caught by require_datetime_text


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AvailabilityKind(Enum):
    """Kind of availability record."""
    BUSINESS_HOURS = "business_hours"
    TEMPORARY_AVAILABLE = "temporary_available"
    TEMPORARY_UNAVAILABLE = "temporary_unavailable"
    QUIET_HOURS = "quiet_hours"
    VACATION = "vacation"
    ON_CALL = "on_call"
    EMERGENCY_ONLY = "emergency_only"


class WindowType(Enum):
    """Type of time window."""
    CONTACT = "contact"
    MEETING = "meeting"
    CALLBACK = "callback"
    FOLLOW_UP = "follow_up"
    ESCALATION = "escalation"
    QUIET = "quiet"
    NO_CONTACT = "no_contact"


class MeetingStatus(Enum):
    """Status of a meeting."""
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class ResponseExpectation(Enum):
    """Expected response behavior."""
    IMMEDIATE = "immediate"
    WITHIN_BUSINESS_HOURS = "within_business_hours"
    WITHIN_SLA = "within_sla"
    NEXT_BUSINESS_DAY = "next_business_day"
    BEST_EFFORT = "best_effort"
    NO_RESPONSE_EXPECTED = "no_response_expected"


class AvailabilityResolution(Enum):
    """How an availability check was resolved."""
    AVAILABLE_NOW = "available_now"
    AVAILABLE_LATER = "available_later"
    UNAVAILABLE = "unavailable"
    QUIET_HOURS = "quiet_hours"
    EMERGENCY_OVERRIDE = "emergency_override"
    FALLBACK_IDENTITY = "fallback_identity"
    DEFERRED = "deferred"


class SchedulingConflictKind(Enum):
    """Kind of scheduling conflict."""
    OVERLAP = "overlap"
    QUIET_HOURS_VIOLATION = "quiet_hours_violation"
    OUTSIDE_BUSINESS_HOURS = "outside_business_hours"
    DOUBLE_BOOKING = "double_booking"
    SLA_VIOLATION = "sla_violation"
    UNAVAILABLE_PARTICIPANT = "unavailable_participant"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AvailabilityRecord(ContractRecord):
    """Availability record for a person, team, or function."""

    record_id: str = ""
    identity_ref: str = ""
    kind: AvailabilityKind = AvailabilityKind.BUSINESS_HOURS
    starts_at: str = ""
    ends_at: str = ""
    timezone: str = "UTC"
    priority_floor: str = "normal"
    channels_allowed: tuple[str, ...] = ()
    channels_blocked: tuple[str, ...] = ()
    reason: str = ""
    active: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "record_id",
            require_non_empty_text(self.record_id, "record_id"),
        )
        object.__setattr__(
            self, "identity_ref",
            require_non_empty_text(self.identity_ref, "identity_ref"),
        )
        if not isinstance(self.kind, AvailabilityKind):
            raise ValueError("kind must be an AvailabilityKind")
        require_datetime_text(self.starts_at, "starts_at")
        require_datetime_text(self.ends_at, "ends_at")
        _require_starts_before_ends(self.starts_at, self.ends_at)
        object.__setattr__(
            self, "timezone",
            require_non_empty_text(self.timezone, "timezone"),
        )
        if self.priority_floor not in ("low", "normal", "high", "urgent", "critical"):
            raise ValueError("priority_floor must be low, normal, high, urgent, or critical")
        object.__setattr__(
            self, "channels_allowed",
            freeze_value(list(self.channels_allowed)),
        )
        object.__setattr__(
            self, "channels_blocked",
            freeze_value(list(self.channels_blocked)),
        )
        if not isinstance(self.active, bool):
            raise ValueError("active must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class SchedulingWindow(ContractRecord):
    """A concrete scheduling time window during which an identity is available.

    Distinct from contact_identity.AvailabilityWindow which models current state.
    This class models scheduled time windows with capacity tracking.
    """

    window_id: str = ""
    identity_ref: str = ""
    window_type: WindowType = WindowType.CONTACT
    starts_at: str = ""
    ends_at: str = ""
    timezone: str = "UTC"
    capacity: int = 1
    reserved: int = 0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "window_id",
            require_non_empty_text(self.window_id, "window_id"),
        )
        object.__setattr__(
            self, "identity_ref",
            require_non_empty_text(self.identity_ref, "identity_ref"),
        )
        if not isinstance(self.window_type, WindowType):
            raise ValueError("window_type must be a WindowType")
        require_datetime_text(self.starts_at, "starts_at")
        require_datetime_text(self.ends_at, "ends_at")
        _require_starts_before_ends(self.starts_at, self.ends_at)
        object.__setattr__(
            self, "timezone",
            require_non_empty_text(self.timezone, "timezone"),
        )
        object.__setattr__(
            self, "capacity",
            require_non_negative_int(self.capacity, "capacity"),
        )
        object.__setattr__(
            self, "reserved",
            require_non_negative_int(self.reserved, "reserved"),
        )
        if self.reserved > self.capacity:
            raise ValueError(
                f"reserved ({self.reserved}) must not exceed capacity ({self.capacity})"
            )
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )


# Backwards-compatible alias
AvailabilityWindow = SchedulingWindow


@dataclass(frozen=True, slots=True)
class BusinessHoursProfile(ContractRecord):
    """Business hours profile for an identity or organization."""

    profile_id: str = ""
    identity_ref: str = ""
    timezone: str = "UTC"
    weekday_start_hour: int = 9
    weekday_end_hour: int = 17
    weekend_available: bool = False
    quiet_start_hour: int = 22
    quiet_end_hour: int = 7
    emergency_override: bool = True
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "profile_id",
            require_non_empty_text(self.profile_id, "profile_id"),
        )
        object.__setattr__(
            self, "identity_ref",
            require_non_empty_text(self.identity_ref, "identity_ref"),
        )
        object.__setattr__(
            self, "timezone",
            require_non_empty_text(self.timezone, "timezone"),
        )
        object.__setattr__(
            self, "weekday_start_hour",
            _require_hour(self.weekday_start_hour, "weekday_start_hour"),
        )
        object.__setattr__(
            self, "weekday_end_hour",
            _require_hour(self.weekday_end_hour, "weekday_end_hour"),
        )
        if self.weekday_start_hour >= self.weekday_end_hour:
            raise ValueError(
                f"weekday_start_hour ({self.weekday_start_hour}) must be < "
                f"weekday_end_hour ({self.weekday_end_hour})"
            )
        if not isinstance(self.weekend_available, bool):
            raise ValueError("weekend_available must be a boolean")
        object.__setattr__(
            self, "quiet_start_hour",
            _require_hour(self.quiet_start_hour, "quiet_start_hour"),
        )
        object.__setattr__(
            self, "quiet_end_hour",
            _require_hour(self.quiet_end_hour, "quiet_end_hour"),
        )
        if not isinstance(self.emergency_override, bool):
            raise ValueError("emergency_override must be a boolean")
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class MeetingRecord(ContractRecord):
    """Record of a scheduled or completed meeting."""

    meeting_id: str = ""
    title: str = ""
    organizer_ref: str = ""
    participant_refs: tuple[str, ...] = ()
    status: MeetingStatus = MeetingStatus.PROPOSED
    starts_at: str = ""
    ends_at: str = ""
    timezone: str = "UTC"
    location: str = ""
    campaign_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "meeting_id",
            require_non_empty_text(self.meeting_id, "meeting_id"),
        )
        object.__setattr__(
            self, "title",
            require_non_empty_text(self.title, "title"),
        )
        object.__setattr__(
            self, "organizer_ref",
            require_non_empty_text(self.organizer_ref, "organizer_ref"),
        )
        object.__setattr__(
            self, "participant_refs",
            freeze_value(list(self.participant_refs)),
        )
        if not isinstance(self.status, MeetingStatus):
            raise ValueError("status must be a MeetingStatus")
        require_datetime_text(self.starts_at, "starts_at")
        require_datetime_text(self.ends_at, "ends_at")
        object.__setattr__(
            self, "timezone",
            require_non_empty_text(self.timezone, "timezone"),
        )
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(
            self, "metadata",
            freeze_value(dict(self.metadata)),
        )


@dataclass(frozen=True, slots=True)
class MeetingRequest(ContractRecord):
    """Request to schedule a meeting."""

    request_id: str = ""
    organizer_ref: str = ""
    participant_refs: tuple[str, ...] = ()
    duration_minutes: int = 30
    earliest_start: str = ""
    latest_end: str = ""
    preferred_timezone: str = "UTC"
    campaign_ref: str = ""
    title: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "request_id",
            require_non_empty_text(self.request_id, "request_id"),
        )
        object.__setattr__(
            self, "organizer_ref",
            require_non_empty_text(self.organizer_ref, "organizer_ref"),
        )
        object.__setattr__(
            self, "participant_refs",
            freeze_value(list(self.participant_refs)),
        )
        object.__setattr__(
            self, "duration_minutes",
            _require_positive_int(self.duration_minutes, "duration_minutes"),
        )
        require_datetime_text(self.earliest_start, "earliest_start")
        require_datetime_text(self.latest_end, "latest_end")
        _require_starts_before_ends(self.earliest_start, self.latest_end)
        object.__setattr__(
            self, "preferred_timezone",
            require_non_empty_text(self.preferred_timezone, "preferred_timezone"),
        )
        object.__setattr__(
            self, "title",
            require_non_empty_text(self.title, "title"),
        )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class MeetingDecision(ContractRecord):
    """Decision outcome for a meeting request."""

    decision_id: str = ""
    request_id: str = ""
    meeting_id: str = ""
    scheduled: bool = False
    reason: str = ""
    proposed_start: str = ""
    proposed_end: str = ""
    conflicts: tuple[str, ...] = ()
    decided_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_id",
            require_non_empty_text(self.decision_id, "decision_id"),
        )
        object.__setattr__(
            self, "request_id",
            require_non_empty_text(self.request_id, "request_id"),
        )
        if not isinstance(self.scheduled, bool):
            raise ValueError("scheduled must be a boolean")
        if self.scheduled and not self.meeting_id.strip():
            raise ValueError(
                "meeting_id must be non-empty when scheduled=True"
            )
        object.__setattr__(
            self, "conflicts",
            freeze_value(list(self.conflicts)),
        )
        require_datetime_text(self.decided_at, "decided_at")


@dataclass(frozen=True, slots=True)
class ResponseSLA(ContractRecord):
    """Response SLA for an identity or channel."""

    sla_id: str = ""
    identity_ref: str = ""
    expectation: ResponseExpectation = ResponseExpectation.WITHIN_BUSINESS_HOURS
    max_response_seconds: int = 86400
    escalation_after_seconds: int = 0
    escalation_target: str = ""
    channel_preference: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "sla_id",
            require_non_empty_text(self.sla_id, "sla_id"),
        )
        object.__setattr__(
            self, "identity_ref",
            require_non_empty_text(self.identity_ref, "identity_ref"),
        )
        if not isinstance(self.expectation, ResponseExpectation):
            raise ValueError("expectation must be a ResponseExpectation")
        object.__setattr__(
            self, "max_response_seconds",
            require_non_negative_int(self.max_response_seconds, "max_response_seconds"),
        )
        object.__setattr__(
            self, "escalation_after_seconds",
            require_non_negative_int(self.escalation_after_seconds, "escalation_after_seconds"),
        )
        if self.escalation_after_seconds > self.max_response_seconds:
            raise ValueError(
                f"escalation_after_seconds ({self.escalation_after_seconds}) "
                f"must not exceed max_response_seconds ({self.max_response_seconds})"
            )
        if self.escalation_after_seconds > 0 and not self.escalation_target.strip():
            raise ValueError(
                "escalation_target must be non-empty when escalation_after_seconds > 0"
            )
        require_datetime_text(self.created_at, "created_at")


@dataclass(frozen=True, slots=True)
class AvailabilityConflict(ContractRecord):
    """Record of a scheduling conflict."""

    conflict_id: str = ""
    identity_ref: str = ""
    kind: SchedulingConflictKind = SchedulingConflictKind.OVERLAP
    conflicting_window_ids: tuple[str, ...] = ()
    description: str = ""
    severity: str = "medium"
    detected_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "conflict_id",
            require_non_empty_text(self.conflict_id, "conflict_id"),
        )
        object.__setattr__(
            self, "identity_ref",
            require_non_empty_text(self.identity_ref, "identity_ref"),
        )
        if not isinstance(self.kind, SchedulingConflictKind):
            raise ValueError("kind must be a SchedulingConflictKind")
        object.__setattr__(
            self, "conflicting_window_ids",
            freeze_value(list(self.conflicting_window_ids)),
        )
        if self.severity not in ("low", "medium", "high", "critical"):
            raise ValueError("severity must be low, medium, high, or critical")
        require_datetime_text(self.detected_at, "detected_at")


@dataclass(frozen=True, slots=True)
class AvailabilityRoutingDecision(ContractRecord):
    """Decision on how to route contact based on availability."""

    decision_id: str = ""
    identity_ref: str = ""
    resolution: AvailabilityResolution = AvailabilityResolution.AVAILABLE_NOW
    channel_chosen: str = ""
    fallback_identity_ref: str = ""
    contact_at: str = ""
    reason: str = ""
    priority_used: str = "normal"
    decided_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "decision_id",
            require_non_empty_text(self.decision_id, "decision_id"),
        )
        object.__setattr__(
            self, "identity_ref",
            require_non_empty_text(self.identity_ref, "identity_ref"),
        )
        if not isinstance(self.resolution, AvailabilityResolution):
            raise ValueError("resolution must be an AvailabilityResolution")
        if self.priority_used not in ("low", "normal", "high", "urgent", "critical"):
            raise ValueError("priority_used must be low, normal, high, urgent, or critical")
        require_datetime_text(self.decided_at, "decided_at")
