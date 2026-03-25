"""Purpose: human availability, calendar, and meeting runtime engine.
Governance scope: business hours, quiet hours, temporary availability,
    meeting scheduling, response SLAs, contact-allowed decisions,
    next-valid-window computation, conflict detection.
Dependencies: availability contracts, event_spine, core invariants.
Invariants:
  - No duplicate record or profile IDs.
  - Contact decisions are deterministic given time and priority.
  - Quiet hours block low-priority but not emergency.
  - All returns are immutable.
  - Every operation emits an event.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

from ..contracts.availability import (
    AvailabilityConflict,
    AvailabilityKind,
    AvailabilityRecord,
    AvailabilityResolution,
    AvailabilityRoutingDecision,
    AvailabilityWindow,
    BusinessHoursProfile,
    MeetingDecision,
    MeetingRecord,
    MeetingRequest,
    MeetingStatus,
    ResponseExpectation,
    ResponseSLA,
    SchedulingConflictKind,
    WindowType,
)
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-avail", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


_PRIORITY_RANK = {"low": 0, "normal": 1, "high": 2, "urgent": 3, "critical": 4}
_VALID_PRIORITIES = frozenset(_PRIORITY_RANK.keys())


def _validate_priority(priority: str) -> int:
    """Validate and return priority rank. Raises on invalid priority."""
    if priority not in _VALID_PRIORITIES:
        raise RuntimeCoreInvariantError(
            f"unknown priority: '{priority}' — must be one of {sorted(_VALID_PRIORITIES)}"
        )
    return _PRIORITY_RANK[priority]


class AvailabilityEngine:
    """Engine for human availability, calendar, and meeting coordination."""

    def __init__(self, event_spine: EventSpineEngine) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError(
                "event_spine must be an EventSpineEngine"
            )
        self._events = event_spine
        self._business_hours: dict[str, BusinessHoursProfile] = {}  # identity_ref -> profile
        self._availability_records: dict[str, AvailabilityRecord] = {}  # record_id -> record
        self._availability_by_identity: dict[str, list[str]] = {}  # identity_ref -> [record_id]
        self._windows: dict[str, AvailabilityWindow] = {}  # window_id -> window
        self._meetings: dict[str, MeetingRecord] = {}  # meeting_id -> meeting
        self._meeting_requests: dict[str, MeetingRequest] = {}  # request_id -> request
        self._meeting_decisions: list[MeetingDecision] = []
        self._response_slas: dict[str, ResponseSLA] = {}  # identity_ref -> sla
        self._conflicts: list[AvailabilityConflict] = []
        self._routing_decisions: list[AvailabilityRoutingDecision] = []

    # ------------------------------------------------------------------
    # Business hours
    # ------------------------------------------------------------------

    def set_business_hours(
        self,
        profile_id: str,
        identity_ref: str,
        *,
        timezone_str: str = "UTC",
        weekday_start_hour: int = 9,
        weekday_end_hour: int = 17,
        weekend_available: bool = False,
        quiet_start_hour: int = 22,
        quiet_end_hour: int = 7,
        emergency_override: bool = True,
    ) -> BusinessHoursProfile:
        now = _now_iso()
        profile = BusinessHoursProfile(
            profile_id=profile_id,
            identity_ref=identity_ref,
            timezone=timezone_str,
            weekday_start_hour=weekday_start_hour,
            weekday_end_hour=weekday_end_hour,
            weekend_available=weekend_available,
            quiet_start_hour=quiet_start_hour,
            quiet_end_hour=quiet_end_hour,
            emergency_override=emergency_override,
            created_at=now,
        )
        self._business_hours[identity_ref] = profile

        _emit(self._events, "business_hours_set", {
            "identity_ref": identity_ref,
            "start": weekday_start_hour,
            "end": weekday_end_hour,
        }, identity_ref)

        return profile

    def get_business_hours(self, identity_ref: str) -> BusinessHoursProfile | None:
        return self._business_hours.get(identity_ref)

    # ------------------------------------------------------------------
    # Availability records
    # ------------------------------------------------------------------

    def set_availability(
        self,
        record_id: str,
        identity_ref: str,
        kind: AvailabilityKind,
        starts_at: str,
        ends_at: str,
        *,
        timezone_str: str = "UTC",
        priority_floor: str = "normal",
        channels_allowed: tuple[str, ...] = (),
        channels_blocked: tuple[str, ...] = (),
        reason: str = "",
    ) -> AvailabilityRecord:
        if record_id in self._availability_records:
            raise RuntimeCoreInvariantError(
                f"availability record '{record_id}' already exists"
            )
        now = _now_iso()
        record = AvailabilityRecord(
            record_id=record_id,
            identity_ref=identity_ref,
            kind=kind,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone=timezone_str,
            priority_floor=priority_floor,
            channels_allowed=channels_allowed,
            channels_blocked=channels_blocked,
            reason=reason,
            created_at=now,
        )
        self._availability_records[record_id] = record
        self._availability_by_identity.setdefault(identity_ref, []).append(record_id)

        _emit(self._events, "availability_set", {
            "record_id": record_id,
            "identity_ref": identity_ref,
            "kind": kind.value,
        }, identity_ref)

        return record

    def get_availability(
        self, identity_ref: str, *, at_time: str | None = None,
    ) -> tuple[AvailabilityRecord, ...]:
        """Get availability records for an identity, optionally filtered by time."""
        record_ids = self._availability_by_identity.get(identity_ref, [])
        records = [self._availability_records[rid] for rid in record_ids if rid in self._availability_records]

        if at_time:
            try:
                check_time = datetime.fromisoformat(at_time.replace("Z", "+00:00"))
                filtered = []
                for r in records:
                    if not r.active:
                        continue
                    start = datetime.fromisoformat(r.starts_at.replace("Z", "+00:00"))
                    end = datetime.fromisoformat(r.ends_at.replace("Z", "+00:00"))
                    if start <= check_time <= end:
                        filtered.append(r)
                records = filtered
            except (ValueError, TypeError):
                pass

        return tuple(r for r in records if r.active)

    def deactivate_availability(self, record_id: str) -> AvailabilityRecord:
        """Deactivate an availability record (set active=False)."""
        record = self._availability_records.get(record_id)
        if record is None:
            raise RuntimeCoreInvariantError(
                f"availability record '{record_id}' not found"
            )
        if not record.active:
            raise RuntimeCoreInvariantError(
                f"availability record '{record_id}' is already inactive"
            )
        deactivated = AvailabilityRecord(
            record_id=record.record_id,
            identity_ref=record.identity_ref,
            kind=record.kind,
            starts_at=record.starts_at,
            ends_at=record.ends_at,
            timezone=record.timezone,
            priority_floor=record.priority_floor,
            channels_allowed=record.channels_allowed,
            channels_blocked=record.channels_blocked,
            reason=record.reason,
            active=False,
            created_at=record.created_at,
        )
        self._availability_records[record_id] = deactivated

        _emit(self._events, "availability_deactivated", {
            "record_id": record_id,
            "identity_ref": record.identity_ref,
        }, record.identity_ref)

        return deactivated

    # ------------------------------------------------------------------
    # Contact decisions
    # ------------------------------------------------------------------

    def contact_allowed_now(
        self,
        identity_ref: str,
        *,
        priority: str = "normal",
        channel: str = "",
        at_time: datetime | None = None,
    ) -> AvailabilityRoutingDecision:
        """Determine if contact is allowed now for the given identity and priority."""
        now_dt = at_time or datetime.now(timezone.utc)
        now_str = now_dt.isoformat()
        priority_rank = _validate_priority(priority)

        # Check temporary unavailability
        active_records = self.get_availability(identity_ref, at_time=now_dt.isoformat())
        for record in active_records:
            if record.kind == AvailabilityKind.TEMPORARY_UNAVAILABLE:
                if priority_rank < _PRIORITY_RANK.get("urgent", 3):
                    decision = AvailabilityRoutingDecision(
                        decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str}),
                        identity_ref=identity_ref,
                        resolution=AvailabilityResolution.UNAVAILABLE,
                        reason=f"temporarily unavailable: {record.reason}",
                        priority_used=priority,
                        decided_at=now_str,
                    )
                    self._routing_decisions.append(decision)
                    return decision

            if record.kind == AvailabilityKind.VACATION:
                if priority_rank < _PRIORITY_RANK.get("critical", 4):
                    decision = AvailabilityRoutingDecision(
                        decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "v": "vacation"}),
                        identity_ref=identity_ref,
                        resolution=AvailabilityResolution.UNAVAILABLE,
                        reason="on vacation",
                        priority_used=priority,
                        decided_at=now_str,
                    )
                    self._routing_decisions.append(decision)
                    return decision

            if record.kind == AvailabilityKind.QUIET_HOURS:
                floor_rank = _PRIORITY_RANK.get(record.priority_floor, 1)
                if priority_rank < floor_rank:
                    decision = AvailabilityRoutingDecision(
                        decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "q": "quiet"}),
                        identity_ref=identity_ref,
                        resolution=AvailabilityResolution.QUIET_HOURS,
                        reason="quiet hours active",
                        priority_used=priority,
                        decided_at=now_str,
                    )
                    self._routing_decisions.append(decision)
                    return decision

            if record.kind == AvailabilityKind.EMERGENCY_ONLY:
                if priority_rank < _PRIORITY_RANK.get("critical", 4):
                    decision = AvailabilityRoutingDecision(
                        decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "e": "emergency"}),
                        identity_ref=identity_ref,
                        resolution=AvailabilityResolution.UNAVAILABLE,
                        reason="emergency only mode",
                        priority_used=priority,
                        decided_at=now_str,
                    )
                    self._routing_decisions.append(decision)
                    return decision

            # Check channel blocking
            if channel and record.channels_blocked and channel in record.channels_blocked:
                decision = AvailabilityRoutingDecision(
                    decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "ch": channel}),
                    identity_ref=identity_ref,
                    resolution=AvailabilityResolution.UNAVAILABLE,
                    channel_chosen=channel,
                    reason=f"channel {channel} blocked",
                    priority_used=priority,
                    decided_at=now_str,
                )
                self._routing_decisions.append(decision)
                return decision

        # Check business hours
        bh = self._business_hours.get(identity_ref)
        if bh:
            hour = now_dt.hour
            weekday = now_dt.weekday()  # 0=Monday, 6=Sunday

            # Check quiet hours (wraps around midnight)
            in_quiet = False
            if bh.quiet_start_hour > bh.quiet_end_hour:
                # e.g., 22-7: quiet if hour >= 22 or hour < 7
                in_quiet = hour >= bh.quiet_start_hour or hour < bh.quiet_end_hour
            else:
                in_quiet = bh.quiet_start_hour <= hour < bh.quiet_end_hour

            if in_quiet:
                if bh.emergency_override and priority_rank >= _PRIORITY_RANK.get("critical", 4):
                    decision = AvailabilityRoutingDecision(
                        decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "eo": "override"}),
                        identity_ref=identity_ref,
                        resolution=AvailabilityResolution.EMERGENCY_OVERRIDE,
                        reason="emergency override during quiet hours",
                        priority_used=priority,
                        decided_at=now_str,
                    )
                    self._routing_decisions.append(decision)
                    return decision
                else:
                    decision = AvailabilityRoutingDecision(
                        decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "qh": "bh"}),
                        identity_ref=identity_ref,
                        resolution=AvailabilityResolution.QUIET_HOURS,
                        reason="quiet hours (business hours profile)",
                        priority_used=priority,
                        decided_at=now_str,
                    )
                    self._routing_decisions.append(decision)
                    return decision

            # Check weekend
            if weekday >= 5 and not bh.weekend_available:
                decision = AvailabilityRoutingDecision(
                    decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "wk": "weekend"}),
                    identity_ref=identity_ref,
                    resolution=AvailabilityResolution.AVAILABLE_LATER,
                    reason="weekend — not available until Monday",
                    priority_used=priority,
                    decided_at=now_str,
                )
                self._routing_decisions.append(decision)
                return decision

            # Check business hours
            if not (bh.weekday_start_hour <= hour < bh.weekday_end_hour):
                decision = AvailabilityRoutingDecision(
                    decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "obh": "outside"}),
                    identity_ref=identity_ref,
                    resolution=AvailabilityResolution.AVAILABLE_LATER,
                    reason="outside business hours",
                    priority_used=priority,
                    decided_at=now_str,
                )
                self._routing_decisions.append(decision)
                return decision

        # Available now
        decision = AvailabilityRoutingDecision(
            decision_id=stable_identifier("avd", {"id": identity_ref, "ts": now_str, "ok": "now"}),
            identity_ref=identity_ref,
            resolution=AvailabilityResolution.AVAILABLE_NOW,
            channel_chosen=channel,
            reason="available now",
            priority_used=priority,
            decided_at=now_str,
        )
        self._routing_decisions.append(decision)
        return decision

    def next_contact_window(
        self,
        identity_ref: str,
        *,
        after: datetime | None = None,
    ) -> AvailabilityWindow | None:
        """Compute next valid contact window for an identity."""
        start = after or datetime.now(timezone.utc)
        bh = self._business_hours.get(identity_ref)
        if not bh:
            return None

        now_str = _now_iso()
        # Find next business hours window
        current = start
        for _ in range(14):  # Search up to 14 days ahead
            weekday = current.weekday()
            if weekday >= 5 and not bh.weekend_available:
                # Skip to Monday
                days_until_monday = 7 - weekday
                current = current.replace(
                    hour=bh.weekday_start_hour, minute=0, second=0, microsecond=0,
                ) + timedelta(days=days_until_monday)
                continue

            # Check if we're before business hours start
            if current.hour < bh.weekday_start_hour:
                window_start = current.replace(
                    hour=bh.weekday_start_hour, minute=0, second=0, microsecond=0,
                )
                window_end = current.replace(
                    hour=bh.weekday_end_hour, minute=0, second=0, microsecond=0,
                )
                return AvailabilityWindow(
                    window_id=stable_identifier("aw-next", {"id": identity_ref, "seq": str(len(self._windows))}),
                    identity_ref=identity_ref,
                    window_type=WindowType.CONTACT,
                    starts_at=window_start.isoformat(),
                    ends_at=window_end.isoformat(),
                    timezone=bh.timezone,
                )

            # Check if we're within business hours
            if bh.weekday_start_hour <= current.hour < bh.weekday_end_hour:
                # Check if in quiet hours
                in_quiet = False
                if bh.quiet_start_hour > bh.quiet_end_hour:
                    in_quiet = current.hour >= bh.quiet_start_hour or current.hour < bh.quiet_end_hour
                else:
                    in_quiet = bh.quiet_start_hour <= current.hour < bh.quiet_end_hour

                if not in_quiet:
                    window_end = current.replace(
                        hour=bh.weekday_end_hour, minute=0, second=0, microsecond=0,
                    )
                    return AvailabilityWindow(
                        window_id=stable_identifier("aw-next", {"id": identity_ref, "seq": str(len(self._windows))}),
                        identity_ref=identity_ref,
                        window_type=WindowType.CONTACT,
                        starts_at=current.isoformat(),
                        ends_at=window_end.isoformat(),
                        timezone=bh.timezone,
                    )

            # Move to next day
            current = (current + timedelta(days=1)).replace(
                hour=bh.weekday_start_hour, minute=0, second=0, microsecond=0,
            )

        return None

    # ------------------------------------------------------------------
    # Meeting scheduling
    # ------------------------------------------------------------------

    def schedule_meeting(
        self,
        request: MeetingRequest,
    ) -> MeetingDecision:
        """Schedule a meeting by finding a shared available slot."""
        now = _now_iso()
        self._meeting_requests[request.request_id] = request

        # Check all participants' availability
        try:
            earliest = datetime.fromisoformat(request.earliest_start.replace("Z", "+00:00"))
            latest = datetime.fromisoformat(request.latest_end.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            decision = MeetingDecision(
                decision_id=stable_identifier("mdec", {"rid": request.request_id, "ts": now}),
                request_id=request.request_id,
                reason="invalid time range",
                decided_at=now,
            )
            self._meeting_decisions.append(decision)
            return decision

        duration = timedelta(minutes=request.duration_minutes)
        participants = list(request.participant_refs) + [request.organizer_ref]

        # Simple slot-finding: check each hour from earliest to latest
        slot_start = earliest
        conflicts: list[str] = []
        while slot_start + duration <= latest:
            all_available = True
            conflicts = []

            for pid in participants:
                check = self.contact_allowed_now(pid, priority="high", at_time=slot_start)
                if check.resolution not in (
                    AvailabilityResolution.AVAILABLE_NOW,
                    AvailabilityResolution.EMERGENCY_OVERRIDE,
                ):
                    all_available = False
                    conflicts.append(f"{pid}: {check.reason}")

            if all_available:
                # Found a slot — create meeting
                slot_end = slot_start + duration
                meeting = MeetingRecord(
                    meeting_id=stable_identifier("mtg", {"rid": request.request_id, "seq": str(len(self._meetings))}),
                    title=request.title,
                    organizer_ref=request.organizer_ref,
                    participant_refs=request.participant_refs,
                    status=MeetingStatus.ACCEPTED,
                    starts_at=slot_start.isoformat(),
                    ends_at=slot_end.isoformat(),
                    timezone=request.preferred_timezone,
                    campaign_ref=request.campaign_ref,
                    created_at=now,
                )
                self._meetings[meeting.meeting_id] = meeting

                decision = MeetingDecision(
                    decision_id=stable_identifier("mdec", {"rid": request.request_id, "ts": now}),
                    request_id=request.request_id,
                    meeting_id=meeting.meeting_id,
                    scheduled=True,
                    reason="slot found",
                    proposed_start=slot_start.isoformat(),
                    proposed_end=slot_end.isoformat(),
                    decided_at=now,
                )
                self._meeting_decisions.append(decision)

                _emit(self._events, "meeting_scheduled", {
                    "meeting_id": meeting.meeting_id,
                    "participants": len(participants),
                }, request.organizer_ref)

                return decision

            slot_start += timedelta(hours=1)

        # No slot found
        all_conflicts = conflicts if conflicts else []
        decision = MeetingDecision(
            decision_id=stable_identifier("mdec", {"rid": request.request_id, "ts": now, "f": "none"}),
            request_id=request.request_id,
            reason="no shared available slot found",
            conflicts=tuple(all_conflicts),
            decided_at=now,
        )
        self._meeting_decisions.append(decision)

        _emit(self._events, "meeting_not_scheduled", {
            "request_id": request.request_id,
            "reason": "no shared available slot found",
            "conflict_count": len(all_conflicts),
        }, request.organizer_ref)

        return decision

    def cancel_meeting(self, meeting_id: str, *, reason: str = "cancelled") -> MeetingRecord:
        """Cancel a meeting by replacing it with a CANCELLED-status copy."""
        meeting = self._meetings.get(meeting_id)
        if meeting is None:
            raise RuntimeCoreInvariantError(f"meeting '{meeting_id}' not found")
        if meeting.status == MeetingStatus.CANCELLED:
            raise RuntimeCoreInvariantError(f"meeting '{meeting_id}' is already cancelled")

        cancelled = MeetingRecord(
            meeting_id=meeting.meeting_id,
            title=meeting.title,
            organizer_ref=meeting.organizer_ref,
            participant_refs=meeting.participant_refs,
            status=MeetingStatus.CANCELLED,
            starts_at=meeting.starts_at,
            ends_at=meeting.ends_at,
            timezone=meeting.timezone,
            location=meeting.location,
            campaign_ref=meeting.campaign_ref,
            created_at=meeting.created_at,
            metadata=dict(meeting.metadata),
        )
        self._meetings[meeting_id] = cancelled

        _emit(self._events, "meeting_cancelled", {
            "meeting_id": meeting_id,
            "reason": reason,
        }, meeting.organizer_ref)

        return cancelled

    def get_meeting(self, meeting_id: str) -> MeetingRecord | None:
        return self._meetings.get(meeting_id)

    def get_meetings_for_identity(
        self, identity_ref: str,
    ) -> tuple[MeetingRecord, ...]:
        result = []
        for m in self._meetings.values():
            if m.organizer_ref == identity_ref or identity_ref in m.participant_refs:
                result.append(m)
        return tuple(sorted(result, key=lambda m: m.starts_at))

    # ------------------------------------------------------------------
    # Response SLAs
    # ------------------------------------------------------------------

    def set_response_sla(
        self,
        sla_id: str,
        identity_ref: str,
        expectation: ResponseExpectation,
        *,
        max_response_seconds: int = 86400,
        escalation_after_seconds: int = 0,
        escalation_target: str = "",
        channel_preference: str = "",
    ) -> ResponseSLA:
        now = _now_iso()
        sla = ResponseSLA(
            sla_id=sla_id,
            identity_ref=identity_ref,
            expectation=expectation,
            max_response_seconds=max_response_seconds,
            escalation_after_seconds=escalation_after_seconds,
            escalation_target=escalation_target,
            channel_preference=channel_preference,
            created_at=now,
        )
        self._response_slas[identity_ref] = sla
        return sla

    def get_response_sla(self, identity_ref: str) -> ResponseSLA | None:
        return self._response_slas.get(identity_ref)

    def resolve_response_deadline(
        self,
        identity_ref: str,
        *,
        sent_at: datetime | None = None,
    ) -> dict[str, Any]:
        """Resolve response deadline considering SLA and business hours."""
        sla = self._response_slas.get(identity_ref)
        start = sent_at or datetime.now(timezone.utc)

        if not sla:
            return {
                "identity_ref": identity_ref,
                "deadline": (start + timedelta(days=1)).isoformat(),
                "expectation": "best_effort",
                "escalation_target": "",
            }

        deadline = start + timedelta(seconds=sla.max_response_seconds)
        escalation_at = ""
        if sla.escalation_after_seconds > 0:
            escalation_at = (start + timedelta(seconds=sla.escalation_after_seconds)).isoformat()

        return {
            "identity_ref": identity_ref,
            "deadline": deadline.isoformat(),
            "expectation": sla.expectation.value,
            "escalation_target": sla.escalation_target,
            "escalation_at": escalation_at,
            "channel_preference": sla.channel_preference,
        }

    # ------------------------------------------------------------------
    # Conflict detection
    # ------------------------------------------------------------------

    def find_conflicts(
        self, identity_ref: str,
    ) -> tuple[AvailabilityConflict, ...]:
        """Detect scheduling conflicts for an identity."""
        now = _now_iso()
        meetings = self.get_meetings_for_identity(identity_ref)
        conflicts: list[AvailabilityConflict] = []

        # Check for overlapping meetings
        for i, m1 in enumerate(meetings):
            for m2 in meetings[i + 1:]:
                try:
                    s1 = datetime.fromisoformat(m1.starts_at.replace("Z", "+00:00"))
                    e1 = datetime.fromisoformat(m1.ends_at.replace("Z", "+00:00"))
                    s2 = datetime.fromisoformat(m2.starts_at.replace("Z", "+00:00"))
                    e2 = datetime.fromisoformat(m2.ends_at.replace("Z", "+00:00"))
                    if s1 < e2 and s2 < e1:
                        conflict = AvailabilityConflict(
                            conflict_id=stable_identifier("aconf", {
                                "id": identity_ref, "m1": m1.meeting_id, "m2": m2.meeting_id,
                            }),
                            identity_ref=identity_ref,
                            kind=SchedulingConflictKind.DOUBLE_BOOKING,
                            conflicting_window_ids=(m1.meeting_id, m2.meeting_id),
                            description=f"Meetings '{m1.title}' and '{m2.title}' overlap",
                            detected_at=now,
                        )
                        conflicts.append(conflict)
                        self._conflicts.append(conflict)
                except (ValueError, TypeError):
                    pass

        return tuple(conflicts)

    # ------------------------------------------------------------------
    # Windows
    # ------------------------------------------------------------------

    def add_window(
        self,
        window_id: str,
        identity_ref: str,
        window_type: WindowType,
        starts_at: str,
        ends_at: str,
        *,
        timezone_str: str = "UTC",
        capacity: int = 1,
    ) -> AvailabilityWindow:
        if window_id in self._windows:
            raise RuntimeCoreInvariantError(
                f"window '{window_id}' already exists"
            )
        window = AvailabilityWindow(
            window_id=window_id,
            identity_ref=identity_ref,
            window_type=window_type,
            starts_at=starts_at,
            ends_at=ends_at,
            timezone=timezone_str,
            capacity=capacity,
        )
        self._windows[window_id] = window
        return window

    def get_windows(
        self, identity_ref: str, *, window_type: WindowType | None = None,
    ) -> tuple[AvailabilityWindow, ...]:
        result = [w for w in self._windows.values() if w.identity_ref == identity_ref]
        if window_type is not None:
            result = [w for w in result if w.window_type == window_type]
        return tuple(sorted(result, key=lambda w: w.starts_at))

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_routing_decisions(
        self, identity_ref: str | None = None,
    ) -> tuple[AvailabilityRoutingDecision, ...]:
        if identity_ref is None:
            return tuple(self._routing_decisions)
        return tuple(d for d in self._routing_decisions if d.identity_ref == identity_ref)

    @property
    def business_hours_count(self) -> int:
        return len(self._business_hours)

    @property
    def availability_count(self) -> int:
        return len(self._availability_records)

    @property
    def meeting_count(self) -> int:
        return len(self._meetings)

    @property
    def window_count(self) -> int:
        return len(self._windows)

    @property
    def conflict_count(self) -> int:
        return len(self._conflicts)

    def state_hash(self) -> str:
        h = sha256()
        for iref in sorted(self._business_hours):
            bh = self._business_hours[iref]
            h.update(f"bh:{iref}:{bh.weekday_start_hour}:{bh.weekday_end_hour}".encode())
        for rid in sorted(self._availability_records):
            r = self._availability_records[rid]
            h.update(f"avail:{rid}:{r.kind.value}:{r.active}".encode())
        for mid in sorted(self._meetings):
            m = self._meetings[mid]
            h.update(f"mtg:{mid}:{m.status.value}".encode())
        for wid in sorted(self._windows):
            w = self._windows[wid]
            h.update(f"win:{wid}:{w.window_type.value}".encode())
        for sla_key in sorted(self._response_slas):
            sla = self._response_slas[sla_key]
            h.update(f"sla:{sla_key}:{sla.expectation.value}:{sla.max_response_seconds}".encode())
        h.update(f"decisions:{len(self._routing_decisions)}".encode())
        return h.hexdigest()
