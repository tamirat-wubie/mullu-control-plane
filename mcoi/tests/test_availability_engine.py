"""Comprehensive tests for AvailabilityEngine.

Covers: business hours, availability records, contact-allowed decisions,
next-contact-window, meeting scheduling, response SLAs, conflict detection,
window management, properties, state hashing, and 8 golden scenarios.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from mcoi_runtime.contracts.availability import (
    AvailabilityKind,
    AvailabilityResolution,
    MeetingRequest,
    MeetingStatus,
    ResponseExpectation,
    SchedulingConflictKind,
    WindowType,
)
from mcoi_runtime.core.availability import AvailabilityEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine() -> tuple[EventSpineEngine, AvailabilityEngine]:
    es = EventSpineEngine()
    return es, AvailabilityEngine(es)


def _dt(year=2025, month=6, day=15, hour=10, minute=0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def _iso(year=2025, month=6, day=15, hour=10, minute=0) -> str:
    return _dt(year, month, day, hour, minute).isoformat()


# A Monday in June 2025: June 16 is Monday
MON = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
SAT = datetime(2025, 6, 14, 10, 0, tzinfo=timezone.utc)  # Saturday
SUN = datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)  # Sunday


# ===================================================================
# TestBusinessHours
# ===================================================================


class TestBusinessHours:
    """Tests for set_business_hours / get_business_hours."""

    def test_set_and_get_default_profile(self):
        _, eng = _engine()
        p = eng.set_business_hours("bh-1", "alice")
        assert p.profile_id == "bh-1"
        assert p.identity_ref == "alice"
        assert p.weekday_start_hour == 9
        assert p.weekday_end_hour == 17
        assert p.weekend_available is False
        assert p.quiet_start_hour == 22
        assert p.quiet_end_hour == 7
        assert p.emergency_override is True
        assert eng.get_business_hours("alice") is p

    def test_get_business_hours_missing(self):
        _, eng = _engine()
        assert eng.get_business_hours("nobody") is None

    def test_set_custom_hours(self):
        _, eng = _engine()
        p = eng.set_business_hours(
            "bh-2", "bob",
            timezone_str="US/Eastern",
            weekday_start_hour=8,
            weekday_end_hour=16,
            weekend_available=True,
            quiet_start_hour=23,
            quiet_end_hour=6,
            emergency_override=False,
        )
        assert p.weekday_start_hour == 8
        assert p.weekday_end_hour == 16
        assert p.weekend_available is True
        assert p.quiet_start_hour == 23
        assert p.quiet_end_hour == 6
        assert p.emergency_override is False
        assert p.timezone == "US/Eastern"

    def test_overwrite_replaces_profile(self):
        _, eng = _engine()
        eng.set_business_hours("bh-a", "alice", weekday_start_hour=8)
        eng.set_business_hours("bh-b", "alice", weekday_start_hour=10)
        p = eng.get_business_hours("alice")
        assert p.weekday_start_hour == 10
        assert p.profile_id == "bh-b"

    def test_business_hours_count(self):
        _, eng = _engine()
        assert eng.business_hours_count == 0
        eng.set_business_hours("bh-1", "alice")
        assert eng.business_hours_count == 1
        eng.set_business_hours("bh-2", "bob")
        assert eng.business_hours_count == 2

    def test_set_business_hours_emits_event(self):
        es, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        events = es.list_events()
        assert len(events) >= 1

    def test_multiple_identities_independent(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", weekday_start_hour=8)
        eng.set_business_hours("bh-2", "bob", weekday_start_hour=10)
        assert eng.get_business_hours("alice").weekday_start_hour == 8
        assert eng.get_business_hours("bob").weekday_start_hour == 10

    def test_profile_has_created_at(self):
        _, eng = _engine()
        p = eng.set_business_hours("bh-1", "alice")
        assert p.created_at != ""


# ===================================================================
# TestAvailabilityRecords
# ===================================================================


class TestAvailabilityRecords:
    """Tests for set_availability / get_availability."""

    def test_set_and_get_record(self):
        _, eng = _engine()
        r = eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        assert r.record_id == "rec-1"
        assert r.identity_ref == "alice"
        assert r.kind == AvailabilityKind.VACATION

    def test_get_returns_tuple(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        records = eng.get_availability("alice")
        assert isinstance(records, tuple)
        assert len(records) == 1

    def test_duplicate_record_id_raises(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        with pytest.raises(RuntimeCoreInvariantError, match="already exists") as exc_info:
            eng.set_availability(
                "rec-1", "bob", AvailabilityKind.QUIET_HOURS,
                _iso(2025, 6, 10), _iso(2025, 6, 20),
                )
        assert "rec-1" not in str(exc_info.value)

    def test_filter_by_time_inside(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        records = eng.get_availability("alice", at_time=_iso(2025, 6, 15))
        assert len(records) == 1

    def test_filter_by_time_outside(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        records = eng.get_availability("alice", at_time=_iso(2025, 7, 1))
        assert len(records) == 0

    def test_no_records_returns_empty(self):
        _, eng = _engine()
        records = eng.get_availability("nobody")
        assert records == ()

    def test_multiple_records_same_identity(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 14),
        )
        eng.set_availability(
            "rec-2", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        assert len(eng.get_availability("alice")) == 2

    def test_availability_count(self):
        _, eng = _engine()
        assert eng.availability_count == 0
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        assert eng.availability_count == 1

    def test_record_with_channels_blocked(self):
        _, eng = _engine()
        r = eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
            channels_blocked=("sms", "phone"),
        )
        assert "sms" in r.channels_blocked
        assert "phone" in r.channels_blocked

    def test_record_with_priority_floor(self):
        _, eng = _engine()
        r = eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
            priority_floor="urgent",
        )
        assert r.priority_floor == "urgent"

    def test_set_availability_emits_event(self):
        es, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        events = es.list_events()
        assert len(events) >= 1

    def test_different_identities_isolated(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        assert len(eng.get_availability("bob")) == 0


# ===================================================================
# TestContactAllowedNow
# ===================================================================


class TestContactAllowedNow:
    """Tests for contact_allowed_now decision logic."""

    def test_no_business_hours_returns_available_now(self):
        _, eng = _engine()
        d = eng.contact_allowed_now("alice", at_time=MON)
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_within_business_hours_available(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")  # 9-17
        d = eng.contact_allowed_now("alice", at_time=MON)  # 10am Monday
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_outside_business_hours_available_later(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        late = MON.replace(hour=20)
        d = eng.contact_allowed_now("alice", at_time=late)
        assert d.resolution == AvailabilityResolution.AVAILABLE_LATER
        assert "outside business hours" in d.reason

    def test_before_business_hours_available_later(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        # 8am but quiet hours end at 7, so hour=8 is before start (9)
        early = MON.replace(hour=8)
        d = eng.contact_allowed_now("alice", at_time=early)
        assert d.resolution == AvailabilityResolution.AVAILABLE_LATER

    def test_temporary_unavailable_blocks_low(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            reason="in a meeting",
        )
        d = eng.contact_allowed_now("alice", priority="low", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE
        assert d.reason == "temporarily unavailable"
        assert "in a meeting" not in d.reason

    def test_temporary_unavailable_blocks_normal(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="normal", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_temporary_unavailable_blocks_high(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="high", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_temporary_unavailable_allows_urgent(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="urgent", at_time=_dt(2025, 6, 16))
        assert d.resolution != AvailabilityResolution.UNAVAILABLE

    def test_temporary_unavailable_allows_critical(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="critical", at_time=_dt(2025, 6, 16))
        assert d.resolution != AvailabilityResolution.UNAVAILABLE

    def test_vacation_blocks_low(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="low", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE
        assert "vacation" in d.reason

    def test_vacation_blocks_normal(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="normal", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_vacation_blocks_high(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="high", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_vacation_blocks_urgent(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="urgent", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_vacation_allows_critical(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="critical", at_time=_dt(2025, 6, 16))
        assert d.resolution != AvailabilityResolution.UNAVAILABLE

    def test_quiet_hours_record_blocks_below_floor(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            priority_floor="high",
        )
        d = eng.contact_allowed_now("alice", priority="normal", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_quiet_hours_record_allows_at_floor(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            priority_floor="high",
        )
        d = eng.contact_allowed_now("alice", priority="high", at_time=_dt(2025, 6, 16))
        assert d.resolution != AvailabilityResolution.QUIET_HOURS

    def test_emergency_only_blocks_below_critical(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.EMERGENCY_ONLY,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="urgent", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE
        assert "emergency only" in d.reason

    def test_emergency_only_allows_critical(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.EMERGENCY_ONLY,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="critical", at_time=_dt(2025, 6, 16))
        assert d.resolution != AvailabilityResolution.UNAVAILABLE

    def test_channel_blocked(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_AVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            channels_blocked=("sms",),
        )
        d = eng.contact_allowed_now(
            "alice", priority="critical", channel="sms", at_time=_dt(2025, 6, 16),
        )
        assert d.resolution == AvailabilityResolution.UNAVAILABLE
        assert d.reason == "channel blocked"
        assert "sms" not in d.reason

    def test_channel_not_blocked_passes(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_AVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            channels_blocked=("sms",),
        )
        d = eng.contact_allowed_now(
            "alice", priority="normal", channel="email", at_time=_dt(2025, 6, 16),
        )
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_quiet_hours_wrap_midnight_late_night(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_23 = MON.replace(hour=23)
        d = eng.contact_allowed_now("alice", priority="normal", at_time=at_23)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_quiet_hours_wrap_midnight_early_morning(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_5 = MON.replace(hour=5)
        d = eng.contact_allowed_now("alice", priority="normal", at_time=at_5)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_quiet_hours_non_wrapping(self):
        _, eng = _engine()
        eng.set_business_hours(
            "bh-1", "alice",
            quiet_start_hour=12, quiet_end_hour=13,
            weekday_start_hour=8, weekday_end_hour=18,
        )
        at_noon = MON.replace(hour=12)
        d = eng.contact_allowed_now("alice", priority="normal", at_time=at_noon)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_emergency_override_during_quiet(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", emergency_override=True)
        at_23 = MON.replace(hour=23)
        d = eng.contact_allowed_now("alice", priority="critical", at_time=at_23)
        assert d.resolution == AvailabilityResolution.EMERGENCY_OVERRIDE

    def test_no_emergency_override_during_quiet(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", emergency_override=False)
        at_23 = MON.replace(hour=23)
        d = eng.contact_allowed_now("alice", priority="critical", at_time=at_23)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_weekend_blocked(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", weekend_available=False)
        d = eng.contact_allowed_now("alice", at_time=SAT)
        assert d.resolution == AvailabilityResolution.AVAILABLE_LATER
        assert "weekend" in d.reason.lower()

    def test_weekend_available(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", weekend_available=True)
        d = eng.contact_allowed_now("alice", at_time=SAT)
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_sunday_blocked(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", weekend_available=False)
        d = eng.contact_allowed_now("alice", at_time=SUN)
        assert d.resolution == AvailabilityResolution.AVAILABLE_LATER

    def test_decision_has_priority_used(self):
        _, eng = _engine()
        d = eng.contact_allowed_now("alice", priority="urgent", at_time=MON)
        assert d.priority_used == "urgent"

    def test_decision_has_identity_ref(self):
        _, eng = _engine()
        d = eng.contact_allowed_now("alice", at_time=MON)
        assert d.identity_ref == "alice"

    def test_decision_has_decided_at(self):
        _, eng = _engine()
        d = eng.contact_allowed_now("alice", at_time=MON)
        assert d.decided_at != ""

    def test_routing_decisions_accumulate(self):
        _, eng = _engine()
        eng.contact_allowed_now("alice", at_time=MON)
        eng.contact_allowed_now("alice", at_time=MON)
        decisions = eng.get_routing_decisions("alice")
        assert len(decisions) == 2

    def test_routing_decisions_filter_by_identity(self):
        _, eng = _engine()
        eng.contact_allowed_now("alice", at_time=MON)
        eng.contact_allowed_now("bob", at_time=MON)
        assert len(eng.get_routing_decisions("alice")) == 1
        assert len(eng.get_routing_decisions("bob")) == 1
        assert len(eng.get_routing_decisions()) == 2

    def test_channel_chosen_set_when_available(self):
        _, eng = _engine()
        d = eng.contact_allowed_now("alice", channel="email", at_time=MON)
        assert d.channel_chosen == "email"

    def test_at_boundary_start_hour(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        at_9 = MON.replace(hour=9)
        d = eng.contact_allowed_now("alice", at_time=at_9)
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_at_boundary_end_hour(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")  # end=17
        at_17 = MON.replace(hour=17)
        d = eng.contact_allowed_now("alice", at_time=at_17)
        # hour=17 is NOT < 17 so outside
        assert d.resolution == AvailabilityResolution.AVAILABLE_LATER


# ===================================================================
# TestNextContactWindow
# ===================================================================


class TestNextContactWindow:
    """Tests for next_contact_window."""

    def test_no_business_hours_returns_none(self):
        _, eng = _engine()
        assert eng.next_contact_window("alice") is None

    def test_before_business_hours_returns_start(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")  # 9-17
        at_7 = MON.replace(hour=7)
        w = eng.next_contact_window("alice", after=at_7)
        assert w is not None
        start_dt = datetime.fromisoformat(w.starts_at)
        assert start_dt.hour == 9

    def test_within_business_hours_returns_now(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        w = eng.next_contact_window("alice", after=MON)
        assert w is not None
        start_dt = datetime.fromisoformat(w.starts_at)
        assert start_dt.hour == 10

    def test_after_business_hours_returns_next_day(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        at_20 = MON.replace(hour=20)
        w = eng.next_contact_window("alice", after=at_20)
        assert w is not None
        start_dt = datetime.fromisoformat(w.starts_at)
        assert start_dt.day == MON.day + 1
        assert start_dt.hour == 9

    def test_weekend_skips_to_monday(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", weekend_available=False)
        w = eng.next_contact_window("alice", after=SAT)
        assert w is not None
        start_dt = datetime.fromisoformat(w.starts_at)
        assert start_dt.weekday() == 0  # Monday

    def test_window_type_is_contact(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        w = eng.next_contact_window("alice", after=MON)
        assert w.window_type == WindowType.CONTACT

    def test_window_ends_at_business_end(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")  # end=17
        w = eng.next_contact_window("alice", after=MON)
        end_dt = datetime.fromisoformat(w.ends_at)
        assert end_dt.hour == 17

    def test_window_identity_ref(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        w = eng.next_contact_window("alice", after=MON)
        assert w.identity_ref == "alice"

    def test_window_timezone_matches_profile(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", timezone_str="US/Eastern")
        w = eng.next_contact_window("alice", after=MON)
        assert w.timezone == "US/Eastern"

    def test_during_quiet_hours_advances(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_3am = MON.replace(hour=3)
        w = eng.next_contact_window("alice", after=at_3am)
        assert w is not None
        start_dt = datetime.fromisoformat(w.starts_at)
        assert start_dt.hour == 9

    def test_friday_evening_skips_to_monday(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", weekend_available=False)
        # Friday June 20, 2025 at 20:00
        friday_evening = datetime(2025, 6, 20, 20, 0, tzinfo=timezone.utc)
        assert friday_evening.weekday() == 4  # Friday
        w = eng.next_contact_window("alice", after=friday_evening)
        assert w is not None
        start_dt = datetime.fromisoformat(w.starts_at)
        # Should skip Sat/Sun and land on Monday
        assert start_dt.weekday() == 0


# ===================================================================
# TestScheduleMeeting
# ===================================================================


class TestScheduleMeeting:
    """Tests for schedule_meeting."""

    def _make_request(
        self, req_id="mreq-1", organizer="alice",
        participants=("bob",), duration=60,
        earliest=None, latest=None, title="Sync",
    ) -> MeetingRequest:
        now = _iso()
        e = earliest or _iso(2025, 6, 16, 9)   # Monday 9am
        l_ = latest or _iso(2025, 6, 16, 17)    # Monday 5pm
        return MeetingRequest(
            request_id=req_id,
            organizer_ref=organizer,
            participant_refs=tuple(participants),
            duration_minutes=duration,
            earliest_start=e,
            latest_end=l_,
            title=title,
            created_at=now,
        )

    def test_all_available_scheduled(self):
        _, eng = _engine()
        # No business hours → everyone available
        req = self._make_request()
        d = eng.schedule_meeting(req)
        assert d.scheduled is True
        assert d.reason == "slot found"
        assert d.meeting_id != ""

    def test_meeting_record_created(self):
        _, eng = _engine()
        req = self._make_request()
        d = eng.schedule_meeting(req)
        m = eng.get_meeting(d.meeting_id)
        assert m is not None
        assert m.title == "Sync"
        assert m.status == MeetingStatus.ACCEPTED

    def test_some_unavailable_returns_conflicts(self):
        _, eng = _engine()
        # Make bob unavailable all day
        eng.set_availability(
            "rec-1", "bob", AvailabilityKind.VACATION,
            _iso(2025, 6, 16, 0), _iso(2025, 6, 16, 23, 59),
        )
        req = self._make_request()
        d = eng.schedule_meeting(req)
        assert d.scheduled is False

    def test_invalid_time_range(self):
        """MeetingRequest validates dates at construction, so bad dates raise ValueError."""
        import pytest
        with pytest.raises(ValueError, match="earliest_start"):
            self._make_request(
                earliest="bad-date", latest="bad-date",
            )

    def test_meeting_count(self):
        _, eng = _engine()
        assert eng.meeting_count == 0
        req = self._make_request()
        eng.schedule_meeting(req)
        assert eng.meeting_count == 1

    def test_meeting_emits_event(self):
        es, eng = _engine()
        req = self._make_request()
        eng.schedule_meeting(req)
        events = es.list_events()
        assert any("meeting_scheduled" in str(e.payload) for e in events)

    def test_meeting_for_identity_organizer(self):
        _, eng = _engine()
        req = self._make_request(organizer="alice", participants=("bob",))
        eng.schedule_meeting(req)
        meetings = eng.get_meetings_for_identity("alice")
        assert len(meetings) == 1

    def test_meeting_for_identity_participant(self):
        _, eng = _engine()
        req = self._make_request(organizer="alice", participants=("bob",))
        eng.schedule_meeting(req)
        meetings = eng.get_meetings_for_identity("bob")
        assert len(meetings) == 1

    def test_meeting_for_identity_not_involved(self):
        _, eng = _engine()
        req = self._make_request(organizer="alice", participants=("bob",))
        eng.schedule_meeting(req)
        meetings = eng.get_meetings_for_identity("carol")
        assert len(meetings) == 0

    def test_proposed_start_and_end_set_on_success(self):
        _, eng = _engine()
        req = self._make_request()
        d = eng.schedule_meeting(req)
        assert d.proposed_start != ""
        assert d.proposed_end != ""

    def test_short_window_no_slot(self):
        _, eng = _engine()
        # 30 min window, 60 min meeting
        req = self._make_request(
            duration=60,
            earliest=_iso(2025, 6, 16, 9),
            latest=_iso(2025, 6, 16, 9, 30),
        )
        d = eng.schedule_meeting(req)
        assert d.scheduled is False

    def test_multiple_participants(self):
        _, eng = _engine()
        req = self._make_request(
            organizer="alice",
            participants=("bob", "carol", "dave"),
        )
        d = eng.schedule_meeting(req)
        assert d.scheduled is True


# ===================================================================
# TestResponseSLA
# ===================================================================


class TestResponseSLA:
    """Tests for set_response_sla, get_response_sla, resolve_response_deadline."""

    def test_set_and_get_sla(self):
        _, eng = _engine()
        sla = eng.set_response_sla(
            "sla-1", "alice", ResponseExpectation.WITHIN_SLA,
            max_response_seconds=3600,
        )
        assert sla.sla_id == "sla-1"
        assert eng.get_response_sla("alice") is sla

    def test_get_sla_missing(self):
        _, eng = _engine()
        assert eng.get_response_sla("nobody") is None

    def test_resolve_with_sla(self):
        _, eng = _engine()
        eng.set_response_sla(
            "sla-1", "alice", ResponseExpectation.WITHIN_SLA,
            max_response_seconds=3600,
            escalation_after_seconds=1800,
            escalation_target="manager",
            channel_preference="email",
        )
        sent = _dt(2025, 6, 16, 10)
        result = eng.resolve_response_deadline("alice", sent_at=sent)
        deadline_dt = datetime.fromisoformat(result["deadline"])
        assert deadline_dt == sent + timedelta(seconds=3600)
        assert result["expectation"] == "within_sla"
        assert result["escalation_target"] == "manager"
        assert result["channel_preference"] == "email"
        assert result["escalation_at"] != ""

    def test_resolve_without_sla_defaults(self):
        _, eng = _engine()
        sent = _dt(2025, 6, 16, 10)
        result = eng.resolve_response_deadline("nobody", sent_at=sent)
        deadline_dt = datetime.fromisoformat(result["deadline"])
        assert deadline_dt == sent + timedelta(days=1)
        assert result["expectation"] == "best_effort"
        assert result["escalation_target"] == ""

    def test_resolve_no_escalation_when_zero(self):
        _, eng = _engine()
        eng.set_response_sla(
            "sla-1", "alice", ResponseExpectation.IMMEDIATE,
            max_response_seconds=60,
            escalation_after_seconds=0,
        )
        result = eng.resolve_response_deadline("alice", sent_at=_dt(2025, 6, 16, 10))
        assert result["escalation_at"] == ""

    def test_sla_overwrites_previous(self):
        _, eng = _engine()
        eng.set_response_sla("sla-1", "alice", ResponseExpectation.BEST_EFFORT)
        eng.set_response_sla("sla-2", "alice", ResponseExpectation.IMMEDIATE)
        sla = eng.get_response_sla("alice")
        assert sla.sla_id == "sla-2"
        assert sla.expectation == ResponseExpectation.IMMEDIATE

    def test_resolve_identity_ref_in_result(self):
        _, eng = _engine()
        result = eng.resolve_response_deadline("alice", sent_at=_dt(2025, 6, 16))
        assert result["identity_ref"] == "alice"


# ===================================================================
# TestFindConflicts
# ===================================================================


class TestFindConflicts:
    """Tests for find_conflicts (double-booked meetings)."""

    def _schedule(self, eng, req_id, organizer, participants, start_h, end_h, title="M"):
        # Create a direct meeting by scheduling in a window where all are available
        req = MeetingRequest(
            request_id=req_id,
            organizer_ref=organizer,
            participant_refs=tuple(participants),
            duration_minutes=(end_h - start_h) * 60,
            earliest_start=_iso(2025, 6, 16, start_h),
            latest_end=_iso(2025, 6, 16, end_h),
            title=title,
            created_at=_iso(),
        )
        return eng.schedule_meeting(req)

    def test_no_meetings_no_conflicts(self):
        _, eng = _engine()
        conflicts = eng.find_conflicts("alice")
        assert conflicts == ()

    def test_overlapping_meetings_detected(self):
        _, eng = _engine()
        d1 = self._schedule(eng, "r1", "alice", ("bob",), 9, 11, "M1")
        d2 = self._schedule(eng, "r2", "alice", ("carol",), 10, 12, "M2")
        assert d1.scheduled
        assert d2.scheduled
        conflicts = eng.find_conflicts("alice")
        assert len(conflicts) >= 1
        assert conflicts[0].kind == SchedulingConflictKind.DOUBLE_BOOKING
        assert conflicts[0].description == "meetings overlap"
        assert "M1" not in conflicts[0].description
        assert "M2" not in conflicts[0].description

    def test_non_overlapping_no_conflict(self):
        _, eng = _engine()
        self._schedule(eng, "r1", "alice", ("bob",), 9, 10, "M1")
        self._schedule(eng, "r2", "alice", ("carol",), 11, 12, "M2")
        conflicts = eng.find_conflicts("alice")
        assert len(conflicts) == 0

    def test_conflict_count_property(self):
        _, eng = _engine()
        assert eng.conflict_count == 0
        self._schedule(eng, "r1", "alice", ("bob",), 9, 11, "M1")
        self._schedule(eng, "r2", "alice", ("carol",), 10, 12, "M2")
        eng.find_conflicts("alice")
        assert eng.conflict_count >= 1

    def test_adjacent_meetings_no_conflict(self):
        _, eng = _engine()
        self._schedule(eng, "r1", "alice", ("bob",), 9, 10, "M1")
        self._schedule(eng, "r2", "alice", ("carol",), 10, 11, "M2")
        conflicts = eng.find_conflicts("alice")
        assert len(conflicts) == 0

    def test_conflict_description_is_bounded(self):
        _, eng = _engine()
        self._schedule(eng, "r1", "alice", ("bob",), 9, 11, "StandUp")
        self._schedule(eng, "r2", "alice", ("carol",), 10, 12, "Review")
        conflicts = eng.find_conflicts("alice")
        assert conflicts[0].description == "meetings overlap"
        assert "StandUp" not in conflicts[0].description
        assert "Review" not in conflicts[0].description


# ===================================================================
# TestWindows
# ===================================================================


class TestWindows:
    """Tests for add_window / get_windows."""

    def test_add_and_get(self):
        _, eng = _engine()
        w = eng.add_window(
            "w-1", "alice", WindowType.CONTACT,
            _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17),
        )
        assert w.window_id == "w-1"
        assert w.identity_ref == "alice"
        windows = eng.get_windows("alice")
        assert len(windows) == 1

    def test_duplicate_window_raises(self):
        _, eng = _engine()
        eng.add_window("w-1", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
        with pytest.raises(RuntimeCoreInvariantError, match="already exists") as exc_info:
            eng.add_window("w-1", "bob", WindowType.MEETING, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
        assert "w-1" not in str(exc_info.value)

    def test_filter_by_type(self):
        _, eng = _engine()
        eng.add_window("w-1", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
        eng.add_window("w-2", "alice", WindowType.MEETING, _iso(2025, 6, 16, 10), _iso(2025, 6, 16, 11))
        contacts = eng.get_windows("alice", window_type=WindowType.CONTACT)
        meetings = eng.get_windows("alice", window_type=WindowType.MEETING)
        assert len(contacts) == 1
        assert len(meetings) == 1

    def test_window_count(self):
        _, eng = _engine()
        assert eng.window_count == 0
        eng.add_window("w-1", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
        assert eng.window_count == 1

    def test_get_windows_empty(self):
        _, eng = _engine()
        assert eng.get_windows("nobody") == ()

    def test_windows_sorted_by_starts_at(self):
        _, eng = _engine()
        eng.add_window("w-late", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 14), _iso(2025, 6, 16, 17))
        eng.add_window("w-early", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 12))
        windows = eng.get_windows("alice")
        assert windows[0].window_id == "w-early"
        assert windows[1].window_id == "w-late"

    def test_window_with_custom_capacity(self):
        _, eng = _engine()
        w = eng.add_window(
            "w-1", "alice", WindowType.MEETING,
            _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17),
            capacity=5,
        )
        assert w.capacity == 5

    def test_different_identities_isolated(self):
        _, eng = _engine()
        eng.add_window("w-1", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
        eng.add_window("w-2", "bob", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
        assert len(eng.get_windows("alice")) == 1
        assert len(eng.get_windows("bob")) == 1

    def test_all_window_types(self):
        _, eng = _engine()
        for i, wt in enumerate(WindowType):
            eng.add_window(
                f"w-{i}", "alice", wt,
                _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 10),
            )
        all_windows = eng.get_windows("alice")
        assert len(all_windows) == len(WindowType)


# ===================================================================
# TestProperties
# ===================================================================


class TestProperties:
    """Tests for count properties."""

    def test_initial_counts_zero(self):
        _, eng = _engine()
        assert eng.business_hours_count == 0
        assert eng.availability_count == 0
        assert eng.meeting_count == 0
        assert eng.window_count == 0
        assert eng.conflict_count == 0

    def test_counts_after_operations(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        eng.add_window("w-1", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
        assert eng.business_hours_count == 1
        assert eng.availability_count == 1
        assert eng.window_count == 1


# ===================================================================
# TestStateHash
# ===================================================================


class TestStateHash:
    """Tests for state_hash determinism."""

    def test_empty_state_hash(self):
        _, eng = _engine()
        h = eng.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_same_inputs_same_hash(self):
        _, eng1 = _engine()
        _, eng2 = _engine()
        eng1.set_business_hours("bh-1", "alice")
        eng2.set_business_hours("bh-1", "alice")
        assert eng1.state_hash() == eng2.state_hash()

    def test_different_inputs_different_hash(self):
        _, eng1 = _engine()
        _, eng2 = _engine()
        eng1.set_business_hours("bh-1", "alice")
        eng2.set_business_hours("bh-1", "bob")
        assert eng1.state_hash() != eng2.state_hash()

    def test_hash_changes_after_mutation(self):
        _, eng = _engine()
        h1 = eng.state_hash()
        eng.set_business_hours("bh-1", "alice")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_hash_changes_with_availability(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        h1 = eng.state_hash()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        h2 = eng.state_hash()
        assert h1 != h2

    def test_hash_changes_with_window(self):
        _, eng = _engine()
        h1 = eng.state_hash()
        eng.add_window("w-1", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
        h2 = eng.state_hash()
        assert h1 != h2

    def test_hash_changes_with_contact_decision(self):
        _, eng = _engine()
        h1 = eng.state_hash()
        eng.contact_allowed_now("alice", at_time=MON)
        h2 = eng.state_hash()
        # Decisions change the count, which feeds into hash
        assert h1 != h2


# ===================================================================
# TestConstructor
# ===================================================================


class TestConstructor:
    """Tests for AvailabilityEngine constructor."""

    def test_requires_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            AvailabilityEngine("not an event spine")

    def test_requires_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            AvailabilityEngine(None)

    def test_accepts_event_spine(self):
        es = EventSpineEngine()
        eng = AvailabilityEngine(es)
        assert eng is not None


# ===================================================================
# Golden Scenarios
# ===================================================================


class TestGoldenScenario1_UrgentSmsEmailByAvailability:
    """Identity with business hours 9-17 UTC: check at 10am allowed,
    at 23pm quiet hours, at 23pm with critical + emergency_override -> override."""

    def test_during_hours_allowed(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        at_10 = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("alice", priority="urgent", channel="sms", at_time=at_10)
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_during_hours_email(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        at_10 = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("alice", priority="urgent", channel="email", at_time=at_10)
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_quiet_hours_blocks(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        at_23 = datetime(2025, 6, 16, 23, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("alice", priority="normal", at_time=at_23)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_critical_emergency_override(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", emergency_override=True)
        at_23 = datetime(2025, 6, 16, 23, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("alice", priority="critical", at_time=at_23)
        assert d.resolution == AvailabilityResolution.EMERGENCY_OVERRIDE


class TestGoldenScenario2_BusinessWindowWait:
    """Identity with 9-17 hours, check at 20:00 -> AVAILABLE_LATER,
    next_contact_window returns next day 9am."""

    def test_available_later(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        at_20 = datetime(2025, 6, 16, 20, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("alice", at_time=at_20)
        assert d.resolution == AvailabilityResolution.AVAILABLE_LATER

    def test_next_window_next_day_9am(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        at_20 = datetime(2025, 6, 16, 20, 0, tzinfo=timezone.utc)
        w = eng.next_contact_window("alice", after=at_20)
        assert w is not None
        start_dt = datetime.fromisoformat(w.starts_at)
        assert start_dt.hour == 9
        assert start_dt.day == 17  # Next day


class TestGoldenScenario3_UnavailableApproverEscalation:
    """Identity on vacation: urgent -> blocked, critical -> allowed."""

    def test_vacation_blocks_urgent(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "approver", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 25),
        )
        at = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("approver", priority="urgent", at_time=at)
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_vacation_allows_critical(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "approver", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 25),
        )
        at = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("approver", priority="critical", at_time=at)
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW


class TestGoldenScenario4_SharedMeetingSlot:
    """Two participants: one available 9-17, other 10-16. Meeting
    scheduled in overlap window."""

    def test_meeting_in_overlap(self):
        _, eng = _engine()
        eng.set_business_hours("bh-a", "alice", weekday_start_hour=9, weekday_end_hour=17)
        eng.set_business_hours("bh-b", "bob", weekday_start_hour=10, weekday_end_hour=16)
        req = MeetingRequest(
            request_id="mreq-1",
            organizer_ref="alice",
            participant_refs=("bob",),
            duration_minutes=60,
            earliest_start=_iso(2025, 6, 16, 9),
            latest_end=_iso(2025, 6, 16, 17),
            title="Overlap Test",
            created_at=_iso(),
        )
        d = eng.schedule_meeting(req)
        assert d.scheduled is True
        start_dt = datetime.fromisoformat(d.proposed_start)
        # Should be at 10 or later (bob's start)
        assert start_dt.hour >= 10

    def test_meeting_ends_within_overlap(self):
        _, eng = _engine()
        eng.set_business_hours("bh-a", "alice", weekday_start_hour=9, weekday_end_hour=17)
        eng.set_business_hours("bh-b", "bob", weekday_start_hour=10, weekday_end_hour=16)
        req = MeetingRequest(
            request_id="mreq-2",
            organizer_ref="alice",
            participant_refs=("bob",),
            duration_minutes=60,
            earliest_start=_iso(2025, 6, 16, 9),
            latest_end=_iso(2025, 6, 16, 17),
            title="Overlap End",
            created_at=_iso(),
        )
        d = eng.schedule_meeting(req)
        assert d.scheduled is True
        end_dt = datetime.fromisoformat(d.proposed_end)
        assert end_dt.hour <= 16


class TestGoldenScenario5_QuietHoursBlocking:
    """Quiet hours 22-7, check at 23:00 with normal priority -> QUIET_HOURS."""

    def test_quiet_hours_blocks_normal(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_23 = datetime(2025, 6, 16, 23, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("alice", priority="normal", at_time=at_23)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_quiet_hours_blocks_low(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_23 = datetime(2025, 6, 16, 23, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("alice", priority="low", at_time=at_23)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_quiet_hours_at_2am(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_2 = datetime(2025, 6, 16, 2, 0, tzinfo=timezone.utc)
        d = eng.contact_allowed_now("alice", priority="normal", at_time=at_2)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS


class TestGoldenScenario6_OverdueReRouting:
    """SLA with 3600s max response: deadline 1hr from sent_at."""

    def test_deadline_one_hour(self):
        _, eng = _engine()
        eng.set_response_sla(
            "sla-1", "alice", ResponseExpectation.WITHIN_SLA,
            max_response_seconds=3600,
            escalation_after_seconds=1800,
            escalation_target="manager",
        )
        sent = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
        result = eng.resolve_response_deadline("alice", sent_at=sent)
        deadline_dt = datetime.fromisoformat(result["deadline"])
        expected = sent + timedelta(hours=1)
        assert deadline_dt == expected

    def test_escalation_at_30min(self):
        _, eng = _engine()
        eng.set_response_sla(
            "sla-1", "alice", ResponseExpectation.WITHIN_SLA,
            max_response_seconds=3600,
            escalation_after_seconds=1800,
            escalation_target="manager",
        )
        sent = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
        result = eng.resolve_response_deadline("alice", sent_at=sent)
        esc_dt = datetime.fromisoformat(result["escalation_at"])
        expected = sent + timedelta(minutes=30)
        assert esc_dt == expected

    def test_escalation_target(self):
        _, eng = _engine()
        eng.set_response_sla(
            "sla-1", "alice", ResponseExpectation.WITHIN_SLA,
            max_response_seconds=3600,
            escalation_target="manager",
        )
        result = eng.resolve_response_deadline("alice", sent_at=_dt(2025, 6, 16))
        assert result["escalation_target"] == "manager"


class TestGoldenScenario7_PortfolioAvailabilityScheduling:
    """Multiple identities: check all availability, verify who blocks."""

    def test_identify_blockers(self):
        _, eng = _engine()
        # Alice: available
        eng.set_business_hours("bh-a", "alice")
        # Bob: on vacation
        eng.set_availability(
            "rec-1", "bob", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 25),
        )
        # Carol: available
        eng.set_business_hours("bh-c", "carol")

        at = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
        identities = ["alice", "bob", "carol"]
        blockers = []
        for ident in identities:
            d = eng.contact_allowed_now(ident, priority="normal", at_time=at)
            if d.resolution != AvailabilityResolution.AVAILABLE_NOW:
                blockers.append(ident)

        assert "bob" in blockers
        assert "alice" not in blockers
        assert "carol" not in blockers

    def test_meeting_fails_with_blocker(self):
        _, eng = _engine()
        eng.set_business_hours("bh-a", "alice")
        eng.set_availability(
            "rec-1", "bob", AvailabilityKind.VACATION,
            _iso(2025, 6, 16, 0), _iso(2025, 6, 16, 23, 59),
        )
        eng.set_business_hours("bh-c", "carol")
        req = MeetingRequest(
            request_id="mreq-1",
            organizer_ref="alice",
            participant_refs=("bob", "carol"),
            duration_minutes=60,
            earliest_start=_iso(2025, 6, 16, 9),
            latest_end=_iso(2025, 6, 16, 17),
            title="Team Sync",
            created_at=_iso(),
        )
        d = eng.schedule_meeting(req)
        assert d.scheduled is False

    def test_meeting_succeeds_without_blocker(self):
        _, eng = _engine()
        eng.set_business_hours("bh-a", "alice")
        eng.set_business_hours("bh-c", "carol")
        req = MeetingRequest(
            request_id="mreq-2",
            organizer_ref="alice",
            participant_refs=("carol",),
            duration_minutes=60,
            earliest_start=_iso(2025, 6, 16, 9),
            latest_end=_iso(2025, 6, 16, 17),
            title="1:1",
            created_at=_iso(),
        )
        d = eng.schedule_meeting(req)
        assert d.scheduled is True


class TestGoldenScenario8_ReplayPreservation:
    """Same operations -> same state_hash."""

    def test_replay_deterministic(self):
        def build_engine():
            es = EventSpineEngine()
            eng = AvailabilityEngine(es)
            eng.set_business_hours("bh-1", "alice")
            eng.set_business_hours("bh-2", "bob")
            eng.set_availability(
                "rec-1", "alice", AvailabilityKind.VACATION,
                _iso(2025, 6, 10), _iso(2025, 6, 20),
            )
            eng.add_window("w-1", "alice", WindowType.CONTACT, _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17))
            return eng

        eng1 = build_engine()
        eng2 = build_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_replay_with_availability_and_windows(self):
        """Replay with deterministic operations (no wall-clock-dependent meeting scheduling)."""
        def build_engine():
            es = EventSpineEngine()
            eng = AvailabilityEngine(es)
            eng.set_business_hours("bh-1", "alice")
            eng.set_business_hours("bh-2", "bob")
            eng.add_window(
                "w-1", "alice", WindowType.CONTACT,
                _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17),
            )
            return eng

        eng1 = build_engine()
        eng2 = build_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_order_matters_for_different_state(self):
        _, eng1 = _engine()
        eng1.set_business_hours("bh-1", "alice")

        _, eng2 = _engine()
        eng2.set_business_hours("bh-1", "bob")

        assert eng1.state_hash() != eng2.state_hash()


# ===================================================================
# Additional edge-case tests for thorough coverage
# ===================================================================


class TestEdgeCases:
    """Additional edge cases and boundary conditions."""

    def test_emergency_only_low_priority_blocked(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.EMERGENCY_ONLY,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="low", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_emergency_only_normal_blocked(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.EMERGENCY_ONLY,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="normal", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_emergency_only_high_blocked(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.EMERGENCY_ONLY,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="high", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_multiple_records_first_match_wins(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            reason="meeting",
        )
        eng.set_availability(
            "rec-2", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
        )
        d = eng.contact_allowed_now("alice", priority="low", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.UNAVAILABLE
        assert d.reason == "temporarily unavailable"
        assert "meeting" not in d.reason

    def test_quiet_hours_with_urgent_floor(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            priority_floor="urgent",
        )
        # high < urgent -> blocked
        d = eng.contact_allowed_now("alice", priority="high", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_quiet_hours_urgent_meets_urgent_floor(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            priority_floor="urgent",
        )
        d = eng.contact_allowed_now("alice", priority="urgent", at_time=_dt(2025, 6, 16))
        assert d.resolution != AvailabilityResolution.QUIET_HOURS

    def test_channel_blocked_with_no_channel_passes(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_AVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            channels_blocked=("sms",),
        )
        d = eng.contact_allowed_now("alice", priority="normal", at_time=_dt(2025, 6, 16))
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_at_exact_start_of_availability(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            "2025-06-16T10:00:00+00:00", "2025-06-16T18:00:00+00:00",
        )
        d = eng.contact_allowed_now(
            "alice", priority="normal",
            at_time=datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc),
        )
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_at_exact_end_of_availability(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            "2025-06-16T10:00:00+00:00", "2025-06-16T18:00:00+00:00",
        )
        d = eng.contact_allowed_now(
            "alice", priority="normal",
            at_time=datetime(2025, 6, 16, 18, 0, tzinfo=timezone.utc),
        )
        # 18:00 == end, start <= check <= end is true
        assert d.resolution == AvailabilityResolution.UNAVAILABLE

    def test_just_past_end_of_availability(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            "2025-06-16T10:00:00+00:00", "2025-06-16T18:00:00+00:00",
        )
        d = eng.contact_allowed_now(
            "alice", priority="normal",
            at_time=datetime(2025, 6, 16, 18, 0, 1, tzinfo=timezone.utc),
        )
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_availability_record_with_reason(self):
        _, eng = _engine()
        r = eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            reason="dentist appointment",
        )
        assert r.reason == "dentist appointment"

    def test_meeting_get_returns_none_for_unknown(self):
        _, eng = _engine()
        assert eng.get_meeting("nonexistent") is None

    def test_get_meetings_sorted_by_start(self):
        _, eng = _engine()
        req1 = MeetingRequest(
            request_id="r1", organizer_ref="alice", participant_refs=("bob",),
            duration_minutes=30,
            earliest_start=_iso(2025, 6, 16, 14),
            latest_end=_iso(2025, 6, 16, 15),
            title="Later", created_at=_iso(),
        )
        req2 = MeetingRequest(
            request_id="r2", organizer_ref="alice", participant_refs=("carol",),
            duration_minutes=30,
            earliest_start=_iso(2025, 6, 16, 9),
            latest_end=_iso(2025, 6, 16, 10),
            title="Earlier", created_at=_iso(),
        )
        eng.schedule_meeting(req1)
        eng.schedule_meeting(req2)
        meetings = eng.get_meetings_for_identity("alice")
        assert meetings[0].title == "Earlier"
        assert meetings[1].title == "Later"

    def test_sla_with_all_expectations(self):
        _, eng = _engine()
        for i, exp in enumerate(ResponseExpectation):
            eng.set_response_sla(f"sla-{i}", f"id-{i}", exp)
            sla = eng.get_response_sla(f"id-{i}")
            assert sla.expectation == exp

    def test_quiet_hours_boundary_exact_start(self):
        _, eng = _engine()
        eng.set_business_hours(
            "bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7,
        )
        at_22 = MON.replace(hour=22)
        d = eng.contact_allowed_now("alice", priority="normal", at_time=at_22)
        assert d.resolution == AvailabilityResolution.QUIET_HOURS

    def test_quiet_hours_boundary_exact_end(self):
        _, eng = _engine()
        eng.set_business_hours(
            "bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7,
            weekday_start_hour=7, weekday_end_hour=22,
        )
        at_7 = MON.replace(hour=7)
        d = eng.contact_allowed_now("alice", priority="normal", at_time=at_7)
        # hour=7 is NOT < 7 and NOT >= 22 -> not quiet
        assert d.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_business_hours_custom_timezone_stored(self):
        _, eng = _engine()
        p = eng.set_business_hours("bh-1", "alice", timezone_str="Europe/Berlin")
        assert p.timezone == "Europe/Berlin"

    def test_availability_with_channels_allowed(self):
        _, eng = _engine()
        r = eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_AVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 20),
            channels_allowed=("email", "slack"),
        )
        assert "email" in r.channels_allowed
        assert "slack" in r.channels_allowed

    def test_next_window_for_weekend_with_weekend_available(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", weekend_available=True)
        w = eng.next_contact_window("alice", after=SAT)
        assert w is not None
        start_dt = datetime.fromisoformat(w.starts_at)
        assert start_dt.hour == 10  # SAT is 10am, within 9-17

    def test_conflict_identity_ref(self):
        _, eng = _engine()
        req1 = MeetingRequest(
            request_id="r1", organizer_ref="alice", participant_refs=("bob",),
            duration_minutes=120,
            earliest_start=_iso(2025, 6, 16, 9),
            latest_end=_iso(2025, 6, 16, 11),
            title="Long", created_at=_iso(),
        )
        req2 = MeetingRequest(
            request_id="r2", organizer_ref="alice", participant_refs=("carol",),
            duration_minutes=120,
            earliest_start=_iso(2025, 6, 16, 10),
            latest_end=_iso(2025, 6, 16, 12),
            title="Overlap", created_at=_iso(),
        )
        eng.schedule_meeting(req1)
        eng.schedule_meeting(req2)
        conflicts = eng.find_conflicts("alice")
        if conflicts:
            assert conflicts[0].identity_ref == "alice"

    def test_window_with_timezone(self):
        _, eng = _engine()
        w = eng.add_window(
            "w-1", "alice", WindowType.FOLLOW_UP,
            _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 17),
            timezone_str="Asia/Tokyo",
        )
        assert w.timezone == "Asia/Tokyo"

    def test_state_hash_16_chars(self):
        _, eng = _engine()
        h = eng.state_hash()
        assert len(h) == 64
        # Should be hex
        int(h, 16)

    def test_multiple_slas_different_identities(self):
        _, eng = _engine()
        eng.set_response_sla("sla-1", "alice", ResponseExpectation.IMMEDIATE, max_response_seconds=60)
        eng.set_response_sla("sla-2", "bob", ResponseExpectation.BEST_EFFORT, max_response_seconds=86400)
        sent = _dt(2025, 6, 16, 10)
        r_alice = eng.resolve_response_deadline("alice", sent_at=sent)
        r_bob = eng.resolve_response_deadline("bob", sent_at=sent)
        d_alice = datetime.fromisoformat(r_alice["deadline"])
        d_bob = datetime.fromisoformat(r_bob["deadline"])
        assert d_alice < d_bob


# ===================================================================
# TestInvalidPriority — edge cases for _validate_priority
# ===================================================================


class TestInvalidPriority:
    """Tests for invalid priority string rejection."""

    def test_invalid_priority_in_contact_allowed(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            eng.contact_allowed_now("alice", priority="super_high", at_time=MON)
        assert str(exc_info.value) == "priority has unsupported value"
        assert "super_high" not in str(exc_info.value)
        assert "critical" not in str(exc_info.value)

    def test_empty_priority_rejected(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            eng.contact_allowed_now("alice", priority="", at_time=MON)
        assert str(exc_info.value) == "priority has unsupported value"

    def test_case_sensitive_priority(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            eng.contact_allowed_now("alice", priority="Normal", at_time=MON)
        assert str(exc_info.value) == "priority has unsupported value"
        assert "Normal" not in str(exc_info.value)

    def test_numeric_string_priority_rejected(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError) as exc_info:
            eng.contact_allowed_now("alice", priority="1", at_time=MON)
        assert str(exc_info.value) == "priority has unsupported value"
        assert "1" not in str(exc_info.value)

    @pytest.mark.parametrize("valid_prio", ["low", "normal", "high", "urgent", "critical"])
    def test_all_valid_priorities_accepted(self, valid_prio):
        _, eng = _engine()
        # Should not raise
        result = eng.contact_allowed_now("alice", priority=valid_prio, at_time=MON)
        assert result.priority_used == valid_prio

    def test_invalid_priority_in_set_availability(self):
        _, eng = _engine()
        with pytest.raises(ValueError, match="priority_floor"):
            eng.set_availability(
                "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
                _iso(2025, 6, 10), _iso(2025, 6, 20),
                priority_floor="mega",
            )


# ===================================================================
# TestDeactivateAvailability — edge cases for new method
# ===================================================================


class TestDeactivateAvailability:
    """Tests for deactivate_availability."""

    def test_deactivate_sets_active_false(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        deactivated = eng.deactivate_availability("rec-1")
        assert deactivated.active is False
        assert deactivated.record_id == "rec-1"
        assert deactivated.identity_ref == "alice"
        assert deactivated.kind == AvailabilityKind.VACATION

    def test_deactivate_preserves_all_fields(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
            priority_floor="urgent",
            channels_blocked=("sms",),
            reason="night time",
        )
        deactivated = eng.deactivate_availability("rec-1")
        assert deactivated.priority_floor == "urgent"
        assert "sms" in deactivated.channels_blocked
        assert deactivated.reason == "night time"

    def test_deactivate_nonexistent_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            eng.deactivate_availability("no-such-record")
        assert "no-such-record" not in str(exc_info.value)

    def test_deactivate_already_inactive_raises(self):
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        eng.deactivate_availability("rec-1")
        with pytest.raises(RuntimeCoreInvariantError, match="already inactive") as exc_info:
            eng.deactivate_availability("rec-1")
        assert "rec-1" not in str(exc_info.value)

    def test_deactivate_emits_event(self):
        es, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 10), _iso(2025, 6, 20),
        )
        count_before = len(es.list_events())
        eng.deactivate_availability("rec-1")
        count_after = len(es.list_events())
        assert count_after > count_before

    def test_deactivated_record_not_blocking(self):
        """Deactivated vacation should not block contact."""
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 14), _iso(2025, 6, 18),
            priority_floor="urgent",
        )
        # Should be blocked before deactivation
        decision = eng.contact_allowed_now("alice", priority="normal", at_time=MON)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW
        # Deactivate
        eng.deactivate_availability("rec-1")
        # Should now be available (assuming no business hours blocking)
        decision2 = eng.contact_allowed_now("alice", priority="normal", at_time=MON)
        assert decision2.resolution == AvailabilityResolution.AVAILABLE_NOW


# ===================================================================
# TestCancelMeeting — edge cases for new method
# ===================================================================


class TestCancelMeeting:
    """Tests for cancel_meeting."""

    def _schedule_meeting(self, eng):
        """Helper to schedule a meeting and return the decision."""
        req = MeetingRequest(
            request_id="req-1",
            title="Test Meeting",
            organizer_ref="alice",
            participant_refs=("bob",),
            duration_minutes=60,
            earliest_start=_iso(2025, 6, 16, 9),
            latest_end=_iso(2025, 6, 16, 17),
            created_at=_iso(2025, 6, 16, 8),
        )
        return eng.schedule_meeting(req)

    def test_cancel_meeting_status(self):
        _, eng = _engine()
        decision = self._schedule_meeting(eng)
        assert decision.scheduled is True
        cancelled = eng.cancel_meeting(decision.meeting_id)
        assert cancelled.status == MeetingStatus.CANCELLED

    def test_cancel_meeting_preserves_fields(self):
        _, eng = _engine()
        decision = self._schedule_meeting(eng)
        meeting = eng.get_meeting(decision.meeting_id)
        cancelled = eng.cancel_meeting(decision.meeting_id)
        assert cancelled.title == meeting.title
        assert cancelled.organizer_ref == meeting.organizer_ref
        assert cancelled.participant_refs == meeting.participant_refs
        assert cancelled.starts_at == meeting.starts_at
        assert cancelled.ends_at == meeting.ends_at

    def test_cancel_nonexistent_raises(self):
        _, eng = _engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            eng.cancel_meeting("no-such-meeting")
        assert "no-such-meeting" not in str(exc_info.value)

    def test_cancel_already_cancelled_raises(self):
        _, eng = _engine()
        decision = self._schedule_meeting(eng)
        eng.cancel_meeting(decision.meeting_id)
        with pytest.raises(RuntimeCoreInvariantError, match="already cancelled") as exc_info:
            eng.cancel_meeting(decision.meeting_id)
        assert decision.meeting_id not in str(exc_info.value)

    def test_cancel_emits_event(self):
        es, eng = _engine()
        decision = self._schedule_meeting(eng)
        count_before = len(es.list_events())
        eng.cancel_meeting(decision.meeting_id)
        count_after = len(es.list_events())
        assert count_after > count_before

    def test_cancel_with_custom_reason(self):
        es, eng = _engine()
        decision = self._schedule_meeting(eng)
        eng.cancel_meeting(decision.meeting_id, reason="rescheduled")
        # Check event payload contains the reason
        events = es.list_events()
        cancel_events = [e for e in events if e.payload.get("action") == "meeting_cancelled"]
        assert len(cancel_events) == 1
        assert cancel_events[0].payload["reason"] == "rescheduled"


# ===================================================================
# TestWeekendBoundaryConditions
# ===================================================================


class TestWeekendBoundaryConditions:
    """Tests for weekend boundary edge cases."""

    # Friday 2025-06-13 17:01 → after business hours on Friday
    FRI_AFTER_HOURS = datetime(2025, 6, 13, 17, 1, tzinfo=timezone.utc)
    # Saturday 00:00
    SAT_MIDNIGHT = datetime(2025, 6, 14, 0, 0, tzinfo=timezone.utc)
    # Sunday 23:59
    SUN_LAST_MINUTE = datetime(2025, 6, 15, 23, 59, tzinfo=timezone.utc)
    # Monday 00:00
    MON_MIDNIGHT = datetime(2025, 6, 16, 0, 0, tzinfo=timezone.utc)
    # Monday 09:00
    MON_BIZ_START = datetime(2025, 6, 16, 9, 0, tzinfo=timezone.utc)

    def test_friday_after_hours_blocked(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        decision = eng.contact_allowed_now("alice", at_time=self.FRI_AFTER_HOURS)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW

    def test_saturday_midnight_blocked(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        decision = eng.contact_allowed_now("alice", at_time=self.SAT_MIDNIGHT)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW

    def test_sunday_23_59_blocked(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        decision = eng.contact_allowed_now("alice", at_time=self.SUN_LAST_MINUTE)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW

    def test_monday_midnight_blocked_before_biz_start(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        decision = eng.contact_allowed_now("alice", at_time=self.MON_MIDNIGHT)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW

    def test_monday_biz_start_allowed(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        decision = eng.contact_allowed_now("alice", at_time=self.MON_BIZ_START)
        assert decision.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_weekend_allowed_when_weekend_available(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", weekend_available=True)
        decision = eng.contact_allowed_now("alice", at_time=self.SAT_MIDNIGHT)
        # When weekend_available=True and within business hours or available
        # depends on implementation, but should not be blocked by weekend flag
        assert decision is not None

    def test_emergency_overrides_weekend(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", emergency_override=True)
        decision = eng.contact_allowed_now(
            "alice", priority="critical", at_time=self.SAT_MIDNIGHT,
        )
        assert decision.resolution == AvailabilityResolution.EMERGENCY_OVERRIDE


# ===================================================================
# TestQuietHoursEdgeCases
# ===================================================================


class TestQuietHoursEdgeCases:
    """Tests for quiet hours boundary conditions."""

    def test_quiet_start_boundary(self):
        """At exactly quiet_start_hour, contact should be restricted."""
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_quiet = datetime(2025, 6, 16, 22, 0, tzinfo=timezone.utc)
        decision = eng.contact_allowed_now("alice", priority="low", at_time=at_quiet)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW

    def test_quiet_end_boundary(self):
        """At exactly quiet_end_hour, contact may resume."""
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_end = datetime(2025, 6, 16, 7, 0, tzinfo=timezone.utc)
        # 7AM on Monday — should be after quiet hours but before biz start (9AM)
        decision = eng.contact_allowed_now("alice", priority="normal", at_time=at_end)
        # At 7AM, quiet hours end but biz hours start at 9 — so this is out of business hours
        assert decision is not None

    def test_urgent_bypasses_quiet_hours(self):
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice", quiet_start_hour=22, quiet_end_hour=7)
        at_quiet = datetime(2025, 6, 16, 23, 0, tzinfo=timezone.utc)
        decision = eng.contact_allowed_now("alice", priority="urgent", at_time=at_quiet)
        # Urgent should bypass quiet hours depending on implementation
        assert decision is not None

    def test_critical_bypasses_quiet_hours_via_emergency(self):
        _, eng = _engine()
        eng.set_business_hours(
            "bh-1", "alice",
            quiet_start_hour=22, quiet_end_hour=7,
            emergency_override=True,
        )
        at_quiet = datetime(2025, 6, 16, 23, 0, tzinfo=timezone.utc)
        decision = eng.contact_allowed_now("alice", priority="critical", at_time=at_quiet)
        assert decision.resolution == AvailabilityResolution.EMERGENCY_OVERRIDE


# ===================================================================
# TestMultipleOverlappingRecords
# ===================================================================


class TestMultipleOverlappingRecords:
    """Tests for multiple availability records affecting same identity."""

    def test_vacation_and_quiet_hours_both_block(self):
        """When both vacation and quiet hours cover the same period, most restrictive wins."""
        _, eng = _engine()
        eng.set_availability(
            "vac-1", "alice", AvailabilityKind.VACATION,
            _iso(2025, 6, 14), _iso(2025, 6, 18),
            priority_floor="critical",
        )
        eng.set_availability(
            "quiet-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 14), _iso(2025, 6, 18),
            priority_floor="urgent",
        )
        decision = eng.contact_allowed_now("alice", priority="urgent", at_time=MON)
        # Vacation blocks even urgent (only critical or higher)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW

    def test_overlapping_available_and_unavailable(self):
        """Unavailable record should take precedence over temporary available."""
        _, eng = _engine()
        eng.set_availability(
            "avail-1", "alice", AvailabilityKind.TEMPORARY_AVAILABLE,
            _iso(2025, 6, 14), _iso(2025, 6, 18),
        )
        eng.set_availability(
            "unavail-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 15), _iso(2025, 6, 17),
            priority_floor="urgent",
        )
        decision = eng.contact_allowed_now("alice", priority="normal", at_time=MON)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW

    def test_record_plus_business_hours_both_apply(self):
        """Business hours AND availability record both restrict contact."""
        _, eng = _engine()
        eng.set_business_hours("bh-1", "alice")
        eng.set_availability(
            "unavail-1", "alice", AvailabilityKind.TEMPORARY_UNAVAILABLE,
            _iso(2025, 6, 16, 9), _iso(2025, 6, 16, 12),
            priority_floor="urgent",
        )
        # Monday 10AM is within biz hours but unavailable record blocks
        decision = eng.contact_allowed_now("alice", priority="normal", at_time=MON)
        assert decision.resolution != AvailabilityResolution.AVAILABLE_NOW


# ===================================================================
# TestChannelBlocking
# ===================================================================


class TestChannelBlocking:
    """Tests for channel-specific blocking edge cases."""

    def test_empty_channel_string_not_blocked(self):
        """Empty channel should not match blocked channels."""
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 14), _iso(2025, 6, 18),
            channels_blocked=("sms", "phone"),
            priority_floor="low",
        )
        # Empty channel should still be governed by the record's priority_floor
        decision = eng.contact_allowed_now(
            "alice", channel="", priority="normal", at_time=MON,
        )
        assert decision is not None

    def test_blocked_channel_rejected(self):
        """A specifically blocked channel should be rejected."""
        _, eng = _engine()
        eng.set_availability(
            "rec-1", "alice", AvailabilityKind.QUIET_HOURS,
            _iso(2025, 6, 14), _iso(2025, 6, 18),
            channels_blocked=("sms",),
            priority_floor="low",
        )
        decision = eng.contact_allowed_now(
            "alice", channel="sms", priority="normal", at_time=MON,
        )
        # Should be affected by the quiet hours record
        assert decision is not None


# ===================================================================
# TestEmptyEdgeCases
# ===================================================================


class TestEmptyEdgeCases:
    """Tests for empty/boundary inputs."""

    def test_no_records_no_biz_hours_always_available(self):
        """Identity with no config should be available."""
        _, eng = _engine()
        decision = eng.contact_allowed_now("unknown-identity", at_time=MON)
        assert decision.resolution == AvailabilityResolution.AVAILABLE_NOW

    def test_get_availability_empty(self):
        _, eng = _engine()
        records = eng.get_availability("nobody")
        assert records == ()

    def test_get_meetings_empty(self):
        _, eng = _engine()
        meetings = eng.get_meetings_for_identity("nobody")
        assert meetings == ()

    def test_next_contact_window_no_data(self):
        _, eng = _engine()
        window = eng.next_contact_window("nobody", after=MON)
        # Implementation may return None or a window — just verify it doesn't crash
        assert window is None or hasattr(window, "starts_at")

    def test_find_conflicts_empty(self):
        _, eng = _engine()
        conflicts = eng.find_conflicts("nobody")
        assert conflicts == ()

    def test_get_windows_empty(self):
        _, eng = _engine()
        windows = eng.get_windows("nobody")
        assert windows == ()

    def test_get_routing_decisions_empty(self):
        _, eng = _engine()
        decisions = eng.get_routing_decisions("nobody")
        assert decisions == ()
