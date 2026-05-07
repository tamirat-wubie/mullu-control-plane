"""Tests for mcoi_runtime.contracts.availability module.

Covers all 6 enums, all 9 frozen dataclasses, validation logic,
immutability, to_dict() round-trip, and freeze_value semantics.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.availability import (
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

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

DT = "2025-01-01T00:00:00+00:00"
DT2 = "2025-06-15T12:30:00+00:00"
BAD_DT = "not-a-datetime"


# ===================================================================
# Enum tests
# ===================================================================


class TestAvailabilityKind:
    def test_has_seven_members(self):
        assert len(AvailabilityKind) == 7

    @pytest.mark.parametrize(
        "member,value",
        [
            (AvailabilityKind.BUSINESS_HOURS, "business_hours"),
            (AvailabilityKind.TEMPORARY_AVAILABLE, "temporary_available"),
            (AvailabilityKind.TEMPORARY_UNAVAILABLE, "temporary_unavailable"),
            (AvailabilityKind.QUIET_HOURS, "quiet_hours"),
            (AvailabilityKind.VACATION, "vacation"),
            (AvailabilityKind.ON_CALL, "on_call"),
            (AvailabilityKind.EMERGENCY_ONLY, "emergency_only"),
        ],
    )
    def test_member_value(self, member, value):
        assert member.value == value

    def test_lookup_by_value(self):
        assert AvailabilityKind("on_call") is AvailabilityKind.ON_CALL


class TestWindowType:
    def test_has_seven_members(self):
        assert len(WindowType) == 7

    @pytest.mark.parametrize(
        "member,value",
        [
            (WindowType.CONTACT, "contact"),
            (WindowType.MEETING, "meeting"),
            (WindowType.CALLBACK, "callback"),
            (WindowType.FOLLOW_UP, "follow_up"),
            (WindowType.ESCALATION, "escalation"),
            (WindowType.QUIET, "quiet"),
            (WindowType.NO_CONTACT, "no_contact"),
        ],
    )
    def test_member_value(self, member, value):
        assert member.value == value


class TestMeetingStatus:
    def test_has_six_members(self):
        assert len(MeetingStatus) == 6

    @pytest.mark.parametrize(
        "member,value",
        [
            (MeetingStatus.PROPOSED, "proposed"),
            (MeetingStatus.ACCEPTED, "accepted"),
            (MeetingStatus.DECLINED, "declined"),
            (MeetingStatus.TENTATIVE, "tentative"),
            (MeetingStatus.CANCELLED, "cancelled"),
            (MeetingStatus.COMPLETED, "completed"),
        ],
    )
    def test_member_value(self, member, value):
        assert member.value == value


class TestResponseExpectation:
    def test_has_six_members(self):
        assert len(ResponseExpectation) == 6

    @pytest.mark.parametrize(
        "member,value",
        [
            (ResponseExpectation.IMMEDIATE, "immediate"),
            (ResponseExpectation.WITHIN_BUSINESS_HOURS, "within_business_hours"),
            (ResponseExpectation.WITHIN_SLA, "within_sla"),
            (ResponseExpectation.NEXT_BUSINESS_DAY, "next_business_day"),
            (ResponseExpectation.BEST_EFFORT, "best_effort"),
            (ResponseExpectation.NO_RESPONSE_EXPECTED, "no_response_expected"),
        ],
    )
    def test_member_value(self, member, value):
        assert member.value == value


class TestAvailabilityResolution:
    def test_has_seven_members(self):
        assert len(AvailabilityResolution) == 7

    @pytest.mark.parametrize(
        "member,value",
        [
            (AvailabilityResolution.AVAILABLE_NOW, "available_now"),
            (AvailabilityResolution.AVAILABLE_LATER, "available_later"),
            (AvailabilityResolution.UNAVAILABLE, "unavailable"),
            (AvailabilityResolution.QUIET_HOURS, "quiet_hours"),
            (AvailabilityResolution.EMERGENCY_OVERRIDE, "emergency_override"),
            (AvailabilityResolution.FALLBACK_IDENTITY, "fallback_identity"),
            (AvailabilityResolution.DEFERRED, "deferred"),
        ],
    )
    def test_member_value(self, member, value):
        assert member.value == value


class TestSchedulingConflictKind:
    def test_has_six_members(self):
        assert len(SchedulingConflictKind) == 6

    @pytest.mark.parametrize(
        "member,value",
        [
            (SchedulingConflictKind.OVERLAP, "overlap"),
            (SchedulingConflictKind.QUIET_HOURS_VIOLATION, "quiet_hours_violation"),
            (SchedulingConflictKind.OUTSIDE_BUSINESS_HOURS, "outside_business_hours"),
            (SchedulingConflictKind.DOUBLE_BOOKING, "double_booking"),
            (SchedulingConflictKind.SLA_VIOLATION, "sla_violation"),
            (SchedulingConflictKind.UNAVAILABLE_PARTICIPANT, "unavailable_participant"),
        ],
    )
    def test_member_value(self, member, value):
        assert member.value == value


# ===================================================================
# AvailabilityRecord tests
# ===================================================================


def _avail_record(**overrides):
    defaults = dict(
        record_id="rec-1",
        identity_ref="id-1",
        kind=AvailabilityKind.BUSINESS_HOURS,
        starts_at=DT,
        ends_at=DT2,
        timezone="UTC",
        priority_floor="normal",
        channels_allowed=("email",),
        channels_blocked=("sms",),
        reason="test",
        active=True,
        created_at=DT,
    )
    defaults.update(overrides)
    return AvailabilityRecord(**defaults)


class TestAvailabilityRecord:
    def test_valid_construction(self):
        rec = _avail_record()
        assert rec.record_id == "rec-1"
        assert rec.identity_ref == "id-1"
        assert rec.kind is AvailabilityKind.BUSINESS_HOURS
        assert rec.active is True

    def test_record_id_empty_raises(self):
        with pytest.raises(ValueError):
            _avail_record(record_id="")

    def test_record_id_whitespace_raises(self):
        with pytest.raises(ValueError):
            _avail_record(record_id="   ")

    def test_identity_ref_empty_raises(self):
        with pytest.raises(ValueError):
            _avail_record(identity_ref="")

    def test_kind_wrong_type_raises(self):
        with pytest.raises(ValueError, match="kind must be an AvailabilityKind"):
            _avail_record(kind="business_hours")

    def test_starts_at_bad_datetime_raises(self):
        with pytest.raises(ValueError):
            _avail_record(starts_at=BAD_DT)

    def test_ends_at_bad_datetime_raises(self):
        with pytest.raises(ValueError):
            _avail_record(ends_at=BAD_DT)

    def test_created_at_bad_datetime_raises(self):
        with pytest.raises(ValueError):
            _avail_record(created_at=BAD_DT)

    @pytest.mark.parametrize("pf", ["low", "normal", "high", "urgent", "critical"])
    def test_valid_priority_floors(self, pf):
        rec = _avail_record(priority_floor=pf)
        assert rec.priority_floor == pf

    def test_priority_floor_invalid_raises(self):
        with pytest.raises(ValueError, match="priority_floor"):
            _avail_record(priority_floor="extreme")

    def test_active_non_bool_raises(self):
        with pytest.raises(ValueError, match="active must be a boolean"):
            _avail_record(active=1)

    def test_channels_allowed_frozen_as_tuple(self):
        rec = _avail_record(channels_allowed=["email", "sms"])
        assert isinstance(rec.channels_allowed, tuple)

    def test_channels_blocked_frozen_as_tuple(self):
        rec = _avail_record(channels_blocked=["phone"])
        assert isinstance(rec.channels_blocked, tuple)

    def test_frozen_immutability(self):
        rec = _avail_record()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.record_id = "new"

    def test_to_dict_returns_dict(self):
        rec = _avail_record()
        d = rec.to_dict()
        assert isinstance(d, dict)
        assert d["record_id"] == "rec-1"

    def test_to_dict_preserves_enum(self):
        rec = _avail_record()
        d = rec.to_dict()
        assert d["kind"] is AvailabilityKind.BUSINESS_HOURS

    def test_to_dict_channels_become_lists(self):
        rec = _avail_record(channels_allowed=("a", "b"))
        d = rec.to_dict()
        assert isinstance(d["channels_allowed"], list)

    def test_all_kinds_accepted(self):
        for kind in AvailabilityKind:
            rec = _avail_record(kind=kind)
            assert rec.kind is kind


# ===================================================================
# AvailabilityWindow tests
# ===================================================================


def _avail_window(**overrides):
    defaults = dict(
        window_id="win-1",
        identity_ref="id-1",
        window_type=WindowType.CONTACT,
        starts_at=DT,
        ends_at=DT2,
        timezone="UTC",
        capacity=5,
        reserved=2,
        metadata={"key": "val"},
    )
    defaults.update(overrides)
    return AvailabilityWindow(**defaults)


class TestAvailabilityWindow:
    def test_valid_construction(self):
        w = _avail_window()
        assert w.window_id == "win-1"
        assert w.capacity == 5
        assert w.reserved == 2

    def test_window_id_empty_raises(self):
        with pytest.raises(ValueError):
            _avail_window(window_id="")

    def test_identity_ref_empty_raises(self):
        with pytest.raises(ValueError):
            _avail_window(identity_ref="")

    def test_window_type_wrong_type_raises(self):
        with pytest.raises(ValueError, match="window_type must be a WindowType"):
            _avail_window(window_type="contact")

    def test_starts_at_bad_raises(self):
        with pytest.raises(ValueError):
            _avail_window(starts_at=BAD_DT)

    def test_ends_at_bad_raises(self):
        with pytest.raises(ValueError):
            _avail_window(ends_at=BAD_DT)

    def test_capacity_negative_raises(self):
        with pytest.raises(ValueError):
            _avail_window(capacity=-1)

    def test_reserved_negative_raises(self):
        with pytest.raises(ValueError):
            _avail_window(reserved=-1)

    def test_capacity_zero_ok(self):
        w = _avail_window(capacity=0, reserved=0)
        assert w.capacity == 0

    def test_capacity_zero_reserved_positive_raises(self):
        with pytest.raises(ValueError):
            _avail_window(capacity=0, reserved=2)

    def test_metadata_frozen_as_mapping_proxy(self):
        w = _avail_window(metadata={"a": 1})
        assert isinstance(w.metadata, MappingProxyType)

    def test_metadata_nested_dict_frozen(self):
        w = _avail_window(metadata={"nested": {"x": 1}})
        assert isinstance(w.metadata["nested"], MappingProxyType)

    def test_frozen_immutability(self):
        w = _avail_window()
        with pytest.raises(dataclasses.FrozenInstanceError):
            w.window_id = "new"

    def test_to_dict_preserves_enum(self):
        w = _avail_window()
        d = w.to_dict()
        assert d["window_type"] is WindowType.CONTACT

    def test_to_dict_metadata_becomes_dict(self):
        w = _avail_window(metadata={"k": "v"})
        d = w.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_all_window_types_accepted(self):
        for wt in WindowType:
            w = _avail_window(window_type=wt)
            assert w.window_type is wt

    def test_timezone_empty_raises(self):
        with pytest.raises(ValueError):
            _avail_window(timezone="")


# ===================================================================
# BusinessHoursProfile tests
# ===================================================================


def _biz_profile(**overrides):
    defaults = dict(
        profile_id="prof-1",
        identity_ref="id-1",
        timezone="America/New_York",
        weekday_start_hour=9,
        weekday_end_hour=17,
        weekend_available=False,
        quiet_start_hour=22,
        quiet_end_hour=7,
        emergency_override=True,
        created_at=DT,
    )
    defaults.update(overrides)
    return BusinessHoursProfile(**defaults)


class TestBusinessHoursProfile:
    def test_valid_construction(self):
        p = _biz_profile()
        assert p.profile_id == "prof-1"
        assert p.weekday_start_hour == 9
        assert p.weekend_available is False
        assert p.emergency_override is True

    def test_profile_id_empty_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(profile_id="")

    def test_identity_ref_empty_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(identity_ref="")

    def test_timezone_empty_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(timezone="")

    def test_weekday_start_hour_negative_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(weekday_start_hour=-1)

    def test_weekday_end_hour_negative_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(weekday_end_hour=-1)

    def test_quiet_start_hour_negative_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(quiet_start_hour=-1)

    def test_quiet_end_hour_negative_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(quiet_end_hour=-1)

    def test_weekend_available_non_bool_raises(self):
        with pytest.raises(ValueError, match="weekend_available must be a boolean"):
            _biz_profile(weekend_available=1)

    def test_emergency_override_non_bool_raises(self):
        with pytest.raises(ValueError, match="emergency_override must be a boolean"):
            _biz_profile(emergency_override=0)

    def test_created_at_bad_datetime_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(created_at=BAD_DT)

    def test_hours_zero_accepted(self):
        p = _biz_profile(weekday_start_hour=0, weekday_end_hour=1, quiet_start_hour=0, quiet_end_hour=0)
        assert p.weekday_start_hour == 0

    def test_frozen_immutability(self):
        p = _biz_profile()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.profile_id = "new"

    def test_to_dict_round_trip(self):
        p = _biz_profile()
        d = p.to_dict()
        assert d["profile_id"] == "prof-1"
        assert d["timezone"] == "America/New_York"
        assert d["weekend_available"] is False


# ===================================================================
# MeetingRecord tests
# ===================================================================


def _meeting_record(**overrides):
    defaults = dict(
        meeting_id="mtg-1",
        title="Standup",
        organizer_ref="org-1",
        participant_refs=("p1", "p2"),
        status=MeetingStatus.PROPOSED,
        starts_at=DT,
        ends_at=DT2,
        timezone="UTC",
        location="Room A",
        campaign_ref="camp-1",
        created_at=DT,
        metadata={"notes": "none"},
    )
    defaults.update(overrides)
    return MeetingRecord(**defaults)


class TestMeetingRecord:
    def test_valid_construction(self):
        m = _meeting_record()
        assert m.meeting_id == "mtg-1"
        assert m.title == "Standup"

    def test_meeting_id_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_record(meeting_id="")

    def test_title_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_record(title="")

    def test_organizer_ref_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_record(organizer_ref="")

    def test_status_wrong_type_raises(self):
        with pytest.raises(ValueError, match="status must be a MeetingStatus"):
            _meeting_record(status="proposed")

    def test_starts_at_bad_raises(self):
        with pytest.raises(ValueError):
            _meeting_record(starts_at=BAD_DT)

    def test_ends_at_bad_raises(self):
        with pytest.raises(ValueError):
            _meeting_record(ends_at=BAD_DT)

    def test_starts_equals_ends_raises(self):
        with pytest.raises(ValueError, match="must be before"):
            _meeting_record(starts_at=DT, ends_at=DT)

    def test_starts_after_ends_raises(self):
        with pytest.raises(ValueError, match="must be before"):
            _meeting_record(starts_at=DT2, ends_at=DT)

    def test_created_at_bad_raises(self):
        with pytest.raises(ValueError):
            _meeting_record(created_at=BAD_DT)

    def test_participant_refs_frozen_as_tuple(self):
        m = _meeting_record(participant_refs=["a", "b", "c"])
        assert isinstance(m.participant_refs, tuple)
        assert m.participant_refs == ("a", "b", "c")

    def test_metadata_frozen_as_mapping_proxy(self):
        m = _meeting_record(metadata={"k": "v"})
        assert isinstance(m.metadata, MappingProxyType)

    def test_frozen_immutability(self):
        m = _meeting_record()
        with pytest.raises(dataclasses.FrozenInstanceError):
            m.meeting_id = "new"

    def test_to_dict_preserves_enum(self):
        m = _meeting_record()
        d = m.to_dict()
        assert d["status"] is MeetingStatus.PROPOSED

    def test_to_dict_participant_refs_become_list(self):
        m = _meeting_record()
        d = m.to_dict()
        assert isinstance(d["participant_refs"], list)

    def test_all_statuses_accepted(self):
        for s in MeetingStatus:
            m = _meeting_record(status=s)
            assert m.status is s

    def test_timezone_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_record(timezone="")


# ===================================================================
# MeetingRequest tests
# ===================================================================


def _meeting_request(**overrides):
    defaults = dict(
        request_id="req-1",
        organizer_ref="org-1",
        participant_refs=("p1",),
        duration_minutes=30,
        earliest_start=DT,
        latest_end=DT2,
        preferred_timezone="UTC",
        campaign_ref="camp-1",
        title="Sync",
        created_at=DT,
    )
    defaults.update(overrides)
    return MeetingRequest(**defaults)


class TestMeetingRequest:
    def test_valid_construction(self):
        r = _meeting_request()
        assert r.request_id == "req-1"
        assert r.duration_minutes == 30

    def test_request_id_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(request_id="")

    def test_organizer_ref_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(organizer_ref="")

    def test_title_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(title="")

    def test_duration_minutes_negative_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(duration_minutes=-1)

    def test_duration_minutes_zero_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(duration_minutes=0)

    def test_earliest_start_bad_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(earliest_start=BAD_DT)

    def test_latest_end_bad_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(latest_end=BAD_DT)

    def test_created_at_bad_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(created_at=BAD_DT)

    def test_participant_refs_frozen_as_tuple(self):
        r = _meeting_request(participant_refs=["a", "b"])
        assert isinstance(r.participant_refs, tuple)

    def test_preferred_timezone_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(preferred_timezone="")

    def test_frozen_immutability(self):
        r = _meeting_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.request_id = "new"

    def test_to_dict_round_trip(self):
        r = _meeting_request()
        d = r.to_dict()
        assert d["request_id"] == "req-1"
        assert isinstance(d["participant_refs"], list)


# ===================================================================
# MeetingDecision tests
# ===================================================================


def _meeting_decision(**overrides):
    defaults = dict(
        decision_id="dec-1",
        request_id="req-1",
        meeting_id="mtg-1",
        scheduled=True,
        reason="fits",
        proposed_start=DT,
        proposed_end=DT2,
        conflicts=("c1", "c2"),
        decided_at=DT,
    )
    defaults.update(overrides)
    return MeetingDecision(**defaults)


class TestMeetingDecision:
    def test_valid_construction(self):
        d = _meeting_decision()
        assert d.decision_id == "dec-1"
        assert d.scheduled is True

    def test_decision_id_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_decision(decision_id="")

    def test_request_id_empty_raises(self):
        with pytest.raises(ValueError):
            _meeting_decision(request_id="")

    def test_scheduled_non_bool_raises(self):
        with pytest.raises(ValueError, match="scheduled must be a boolean"):
            _meeting_decision(scheduled=1)

    def test_decided_at_bad_raises(self):
        with pytest.raises(ValueError):
            _meeting_decision(decided_at=BAD_DT)

    def test_conflicts_frozen_as_tuple(self):
        d = _meeting_decision(conflicts=["x", "y"])
        assert isinstance(d.conflicts, tuple)
        assert d.conflicts == ("x", "y")

    def test_frozen_immutability(self):
        d = _meeting_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.decision_id = "new"

    def test_to_dict_conflicts_become_list(self):
        d = _meeting_decision()
        dd = d.to_dict()
        assert isinstance(dd["conflicts"], list)

    def test_scheduled_false_accepted(self):
        d = _meeting_decision(scheduled=False)
        assert d.scheduled is False


# ===================================================================
# ResponseSLA tests
# ===================================================================


def _response_sla(**overrides):
    defaults = dict(
        sla_id="sla-1",
        identity_ref="id-1",
        expectation=ResponseExpectation.WITHIN_BUSINESS_HOURS,
        max_response_seconds=86400,
        escalation_after_seconds=3600,
        escalation_target="manager",
        channel_preference="email",
        created_at=DT,
    )
    defaults.update(overrides)
    return ResponseSLA(**defaults)


class TestResponseSLA:
    def test_valid_construction(self):
        s = _response_sla()
        assert s.sla_id == "sla-1"
        assert s.max_response_seconds == 86400

    def test_sla_id_empty_raises(self):
        with pytest.raises(ValueError):
            _response_sla(sla_id="")

    def test_identity_ref_empty_raises(self):
        with pytest.raises(ValueError):
            _response_sla(identity_ref="")

    def test_expectation_wrong_type_raises(self):
        with pytest.raises(ValueError, match="expectation must be a ResponseExpectation"):
            _response_sla(expectation="immediate")

    def test_max_response_seconds_negative_raises(self):
        with pytest.raises(ValueError):
            _response_sla(max_response_seconds=-1)

    def test_escalation_after_seconds_negative_raises(self):
        with pytest.raises(ValueError):
            _response_sla(escalation_after_seconds=-1)

    def test_max_response_seconds_zero_ok(self):
        s = _response_sla(max_response_seconds=0, escalation_after_seconds=0, escalation_target="")
        assert s.max_response_seconds == 0

    def test_escalation_after_seconds_zero_ok(self):
        s = _response_sla(escalation_after_seconds=0)
        assert s.escalation_after_seconds == 0

    def test_created_at_bad_raises(self):
        with pytest.raises(ValueError):
            _response_sla(created_at=BAD_DT)

    def test_frozen_immutability(self):
        s = _response_sla()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.sla_id = "new"

    def test_to_dict_preserves_enum(self):
        s = _response_sla()
        d = s.to_dict()
        assert d["expectation"] is ResponseExpectation.WITHIN_BUSINESS_HOURS

    def test_all_expectations_accepted(self):
        for e in ResponseExpectation:
            s = _response_sla(expectation=e)
            assert s.expectation is e

    def test_to_dict_round_trip(self):
        s = _response_sla()
        d = s.to_dict()
        assert d["sla_id"] == "sla-1"
        assert d["escalation_target"] == "manager"


# ===================================================================
# AvailabilityConflict tests
# ===================================================================


def _avail_conflict(**overrides):
    defaults = dict(
        conflict_id="conf-1",
        identity_ref="id-1",
        kind=SchedulingConflictKind.OVERLAP,
        conflicting_window_ids=("w1", "w2"),
        description="overlap detected",
        severity="medium",
        detected_at=DT,
    )
    defaults.update(overrides)
    return AvailabilityConflict(**defaults)


class TestAvailabilityConflict:
    def test_valid_construction(self):
        c = _avail_conflict()
        assert c.conflict_id == "conf-1"
        assert c.severity == "medium"

    def test_conflict_id_empty_raises(self):
        with pytest.raises(ValueError):
            _avail_conflict(conflict_id="")

    def test_identity_ref_empty_raises(self):
        with pytest.raises(ValueError):
            _avail_conflict(identity_ref="")

    def test_kind_wrong_type_raises(self):
        with pytest.raises(ValueError, match="kind must be a SchedulingConflictKind"):
            _avail_conflict(kind="overlap")

    @pytest.mark.parametrize("sev", ["low", "medium", "high", "critical"])
    def test_valid_severities(self, sev):
        c = _avail_conflict(severity=sev)
        assert c.severity == sev

    def test_severity_invalid_raises(self):
        with pytest.raises(ValueError, match="severity"):
            _avail_conflict(severity="extreme")

    def test_detected_at_bad_raises(self):
        with pytest.raises(ValueError):
            _avail_conflict(detected_at=BAD_DT)

    def test_conflicting_window_ids_frozen_as_tuple(self):
        c = _avail_conflict(conflicting_window_ids=["a", "b"])
        assert isinstance(c.conflicting_window_ids, tuple)

    def test_frozen_immutability(self):
        c = _avail_conflict()
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.conflict_id = "new"

    def test_to_dict_preserves_enum(self):
        c = _avail_conflict()
        d = c.to_dict()
        assert d["kind"] is SchedulingConflictKind.OVERLAP

    def test_to_dict_window_ids_become_list(self):
        c = _avail_conflict()
        d = c.to_dict()
        assert isinstance(d["conflicting_window_ids"], list)

    def test_all_conflict_kinds_accepted(self):
        for k in SchedulingConflictKind:
            c = _avail_conflict(kind=k)
            assert c.kind is k


# ===================================================================
# AvailabilityRoutingDecision tests
# ===================================================================


def _routing_decision(**overrides):
    defaults = dict(
        decision_id="rd-1",
        identity_ref="id-1",
        resolution=AvailabilityResolution.AVAILABLE_NOW,
        channel_chosen="email",
        fallback_identity_ref="fallback-1",
        contact_at=DT,
        reason="available",
        priority_used="normal",
        decided_at=DT,
    )
    defaults.update(overrides)
    return AvailabilityRoutingDecision(**defaults)


class TestAvailabilityRoutingDecision:
    def test_valid_construction(self):
        r = _routing_decision()
        assert r.decision_id == "rd-1"
        assert r.resolution is AvailabilityResolution.AVAILABLE_NOW

    def test_decision_id_empty_raises(self):
        with pytest.raises(ValueError):
            _routing_decision(decision_id="")

    def test_identity_ref_empty_raises(self):
        with pytest.raises(ValueError):
            _routing_decision(identity_ref="")

    def test_resolution_wrong_type_raises(self):
        with pytest.raises(ValueError, match="resolution must be an AvailabilityResolution"):
            _routing_decision(resolution="available_now")

    @pytest.mark.parametrize("pu", ["low", "normal", "high", "urgent", "critical"])
    def test_valid_priority_used(self, pu):
        r = _routing_decision(priority_used=pu)
        assert r.priority_used == pu

    def test_priority_used_invalid_raises(self):
        with pytest.raises(ValueError, match="priority_used"):
            _routing_decision(priority_used="extreme")

    def test_decided_at_bad_raises(self):
        with pytest.raises(ValueError):
            _routing_decision(decided_at=BAD_DT)

    def test_frozen_immutability(self):
        r = _routing_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.decision_id = "new"

    def test_to_dict_preserves_enum(self):
        r = _routing_decision()
        d = r.to_dict()
        assert d["resolution"] is AvailabilityResolution.AVAILABLE_NOW

    def test_all_resolutions_accepted(self):
        for res in AvailabilityResolution:
            r = _routing_decision(resolution=res)
            assert r.resolution is res

    def test_to_dict_round_trip(self):
        r = _routing_decision()
        d = r.to_dict()
        assert d["decision_id"] == "rd-1"
        assert d["channel_chosen"] == "email"
        assert d["priority_used"] == "normal"


# ===================================================================
# Cross-cutting: freeze_value semantics
# ===================================================================


class TestFreezeValueSemantics:
    """Verify that freeze_value produces tuples (not lists) and MappingProxyType (not dicts)."""

    def test_list_channels_become_tuple(self):
        rec = _avail_record(channels_allowed=["a", "b"])
        assert isinstance(rec.channels_allowed, tuple)
        assert not isinstance(rec.channels_allowed, list)

    def test_list_participants_become_tuple(self):
        m = _meeting_record(participant_refs=["x", "y"])
        assert isinstance(m.participant_refs, tuple)

    def test_list_conflicts_become_tuple(self):
        d = _meeting_decision(conflicts=["c1"])
        assert isinstance(d.conflicts, tuple)

    def test_list_window_ids_become_tuple(self):
        c = _avail_conflict(conflicting_window_ids=["w1"])
        assert isinstance(c.conflicting_window_ids, tuple)

    def test_dict_metadata_becomes_mapping_proxy(self):
        w = _avail_window(metadata={"k": "v"})
        assert isinstance(w.metadata, MappingProxyType)
        assert not isinstance(w.metadata, dict)

    def test_nested_dict_in_metadata_frozen(self):
        w = _avail_window(metadata={"inner": {"deep": 1}})
        assert isinstance(w.metadata["inner"], MappingProxyType)

    def test_metadata_immutable_raises(self):
        w = _avail_window(metadata={"k": "v"})
        with pytest.raises(TypeError):
            w.metadata["k"] = "new"

    def test_meeting_metadata_frozen(self):
        m = _meeting_record(metadata={"a": [1, 2]})
        assert isinstance(m.metadata, MappingProxyType)
        # list inside metadata is frozen to tuple
        assert isinstance(m.metadata["a"], tuple)


# ===================================================================
# Cross-cutting: to_dict() enum preservation
# ===================================================================


class TestToDictEnumPreservation:
    """Verify that to_dict() does NOT convert enums to .value strings."""

    def test_availability_record_kind_is_enum(self):
        d = _avail_record().to_dict()
        assert isinstance(d["kind"], AvailabilityKind)

    def test_availability_window_window_type_is_enum(self):
        d = _avail_window().to_dict()
        assert isinstance(d["window_type"], WindowType)

    def test_meeting_record_status_is_enum(self):
        d = _meeting_record().to_dict()
        assert isinstance(d["status"], MeetingStatus)

    def test_response_sla_expectation_is_enum(self):
        d = _response_sla().to_dict()
        assert isinstance(d["expectation"], ResponseExpectation)

    def test_availability_conflict_kind_is_enum(self):
        d = _avail_conflict().to_dict()
        assert isinstance(d["kind"], SchedulingConflictKind)

    def test_routing_decision_resolution_is_enum(self):
        d = _routing_decision().to_dict()
        assert isinstance(d["resolution"], AvailabilityResolution)


# ===================================================================
# Cross-cutting: to_dict() round-trip for all classes
# ===================================================================


class TestToDictRoundTrip:
    """Verify all dataclasses produce a dict with all expected keys."""

    def test_availability_record_all_keys(self):
        d = _avail_record().to_dict()
        expected_keys = {
            "record_id", "identity_ref", "kind", "starts_at", "ends_at",
            "timezone", "priority_floor", "channels_allowed", "channels_blocked",
            "reason", "active", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_availability_window_all_keys(self):
        d = _avail_window().to_dict()
        expected_keys = {
            "window_id", "identity_ref", "window_type", "starts_at", "ends_at",
            "timezone", "capacity", "reserved", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_business_hours_profile_all_keys(self):
        d = _biz_profile().to_dict()
        expected_keys = {
            "profile_id", "identity_ref", "timezone", "weekday_start_hour",
            "weekday_end_hour", "weekend_available", "quiet_start_hour",
            "quiet_end_hour", "emergency_override", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_meeting_record_all_keys(self):
        d = _meeting_record().to_dict()
        expected_keys = {
            "meeting_id", "title", "organizer_ref", "participant_refs",
            "status", "starts_at", "ends_at", "timezone", "location",
            "campaign_ref", "created_at", "metadata",
        }
        assert set(d.keys()) == expected_keys

    def test_meeting_request_all_keys(self):
        d = _meeting_request().to_dict()
        expected_keys = {
            "request_id", "organizer_ref", "participant_refs", "duration_minutes",
            "earliest_start", "latest_end", "preferred_timezone", "campaign_ref",
            "title", "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_meeting_decision_all_keys(self):
        d = _meeting_decision().to_dict()
        expected_keys = {
            "decision_id", "request_id", "meeting_id", "scheduled",
            "reason", "proposed_start", "proposed_end", "conflicts", "decided_at",
        }
        assert set(d.keys()) == expected_keys

    def test_response_sla_all_keys(self):
        d = _response_sla().to_dict()
        expected_keys = {
            "sla_id", "identity_ref", "expectation", "max_response_seconds",
            "escalation_after_seconds", "escalation_target", "channel_preference",
            "created_at",
        }
        assert set(d.keys()) == expected_keys

    def test_availability_conflict_all_keys(self):
        d = _avail_conflict().to_dict()
        expected_keys = {
            "conflict_id", "identity_ref", "kind", "conflicting_window_ids",
            "description", "severity", "detected_at",
        }
        assert set(d.keys()) == expected_keys

    def test_routing_decision_all_keys(self):
        d = _routing_decision().to_dict()
        expected_keys = {
            "decision_id", "identity_ref", "resolution", "channel_chosen",
            "fallback_identity_ref", "contact_at", "reason", "priority_used",
            "decided_at",
        }
        assert set(d.keys()) == expected_keys


# ===================================================================
# Cross-field validation edge cases
# ===================================================================


class TestCrossFieldValidationEdgeCases:
    """Edge cases for cross-field validators added during audit."""

    # --- AvailabilityRecord: starts_at < ends_at ---

    def test_record_starts_equals_ends_raises(self):
        with pytest.raises(ValueError, match="must be before"):
            _avail_record(starts_at=DT, ends_at=DT)

    def test_record_starts_after_ends_raises(self):
        with pytest.raises(ValueError, match="must be before"):
            _avail_record(starts_at=DT2, ends_at=DT)

    def test_record_start_end_error_is_bounded(self):
        with pytest.raises(ValueError, match="must be before") as excinfo:
            _avail_record(starts_at=DT2, ends_at=DT)
        assert "starts_at" in str(excinfo.value)
        assert DT not in str(excinfo.value)
        assert DT2 not in str(excinfo.value)

    def test_record_one_second_gap_ok(self):
        rec = _avail_record(
            starts_at="2025-01-01T00:00:00+00:00",
            ends_at="2025-01-01T00:00:01+00:00",
        )
        assert rec.starts_at == "2025-01-01T00:00:00+00:00"

    # --- SchedulingWindow: starts_at < ends_at, reserved <= capacity ---

    def test_window_starts_equals_ends_raises(self):
        with pytest.raises(ValueError, match="must be before"):
            _avail_window(starts_at=DT, ends_at=DT)

    def test_window_reserved_exceeds_capacity_raises(self):
        with pytest.raises(ValueError):
            _avail_window(capacity=3, reserved=4)

    def test_window_reserved_exceeds_capacity_error_is_bounded(self):
        with pytest.raises(ValueError, match="must not exceed") as excinfo:
            _avail_window(capacity=3, reserved=4)
        assert str(excinfo.value) == "reserved must not exceed capacity"
        assert "3" not in str(excinfo.value)
        assert "4" not in str(excinfo.value)

    def test_window_reserved_equals_capacity_ok(self):
        w = _avail_window(capacity=5, reserved=5)
        assert w.reserved == 5

    # --- BusinessHoursProfile: hours 0-23, start < end ---

    def test_biz_hour_24_raises(self):
        with pytest.raises(ValueError, match="0-23"):
            _biz_profile(weekday_start_hour=24)

    def test_biz_hour_error_is_bounded(self):
        with pytest.raises(ValueError, match="0-23") as excinfo:
            _biz_profile(weekday_start_hour=24)
        assert str(excinfo.value) == "weekday_start_hour must be 0-23"
        assert "24" not in str(excinfo.value)
        assert "24" not in str(excinfo.value)

    def test_biz_hour_negative_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(weekday_start_hour=-1)

    def test_biz_quiet_hour_24_raises(self):
        with pytest.raises(ValueError, match="0-23"):
            _biz_profile(quiet_start_hour=24)

    def test_biz_start_equals_end_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(weekday_start_hour=10, weekday_end_hour=10)

    def test_biz_start_after_end_raises(self):
        with pytest.raises(ValueError):
            _biz_profile(weekday_start_hour=17, weekday_end_hour=9)

    def test_biz_start_after_end_error_is_bounded(self):
        with pytest.raises(ValueError, match="must be before") as excinfo:
            _biz_profile(weekday_start_hour=17, weekday_end_hour=9)
        assert "weekday_start_hour" in str(excinfo.value)
        assert "weekday_end_hour" in str(excinfo.value)
        assert "17" not in str(excinfo.value)

    # --- MeetingRequest: duration >= 1, earliest < latest ---

    def test_meeting_request_duration_zero_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(duration_minutes=0)

    def test_meeting_request_duration_error_is_bounded(self):
        with pytest.raises(ValueError, match=">= 1") as excinfo:
            _meeting_request(duration_minutes=0)
        assert str(excinfo.value) == "duration_minutes must be >= 1"
        assert "0" not in str(excinfo.value)

    def test_meeting_request_duration_negative_raises(self):
        with pytest.raises(ValueError):
            _meeting_request(duration_minutes=-5)

    def test_meeting_request_duration_one_ok(self):
        r = _meeting_request(duration_minutes=1)
        assert r.duration_minutes == 1

    def test_meeting_request_earliest_after_latest_raises(self):
        with pytest.raises(ValueError, match="must be before"):
            _meeting_request(earliest_start=DT2, latest_end=DT)

    def test_meeting_request_earliest_equals_latest_raises(self):
        with pytest.raises(ValueError, match="must be before"):
            _meeting_request(earliest_start=DT, latest_end=DT)

    # --- ResponseSLA: escalation_after <= max_response, target required ---

    def test_sla_escalation_after_exceeds_max_raises(self):
        with pytest.raises(ValueError):
            _response_sla(
                max_response_seconds=3600,
                escalation_after_seconds=7200,
                escalation_target="boss",
            )

    def test_sla_escalation_after_exceeds_max_error_is_bounded(self):
        with pytest.raises(ValueError, match="must not exceed") as excinfo:
            _response_sla(
                max_response_seconds=3600,
                escalation_after_seconds=7200,
                escalation_target="boss",
            )
        assert "escalation_after_seconds" in str(excinfo.value)
        assert "3600" not in str(excinfo.value)
        assert "7200" not in str(excinfo.value)

    def test_sla_escalation_after_equals_max_ok(self):
        s = _response_sla(
            max_response_seconds=3600,
            escalation_after_seconds=3600,
            escalation_target="boss",
        )
        assert s.escalation_after_seconds == 3600

    def test_sla_escalation_after_positive_without_target_raises(self):
        with pytest.raises(ValueError):
            _response_sla(
                max_response_seconds=3600,
                escalation_after_seconds=1800,
                escalation_target="",
            )

    def test_sla_escalation_after_zero_no_target_ok(self):
        s = _response_sla(
            max_response_seconds=3600,
            escalation_after_seconds=0,
            escalation_target="",
        )
        assert s.escalation_after_seconds == 0

    # --- MeetingDecision: meeting_id required when scheduled=True ---

    def test_meeting_decision_scheduled_true_empty_meeting_id_raises(self):
        with pytest.raises(ValueError):
            _meeting_decision(scheduled=True, meeting_id="")

    def test_meeting_decision_scheduled_false_empty_meeting_id_ok(self):
        d = _meeting_decision(scheduled=False, meeting_id="")
        assert d.meeting_id == ""


# ===================================================================
# SchedulingWindow backward-compat alias
# ===================================================================


class TestSchedulingWindowAlias:
    """Verify AvailabilityWindow is an alias for SchedulingWindow."""

    def test_alias_is_same_class(self):
        from mcoi_runtime.contracts.availability import SchedulingWindow
        assert AvailabilityWindow is SchedulingWindow

    def test_alias_constructs_same_object(self):
        w = AvailabilityWindow(
            window_id="alias-1",
            identity_ref="id-1",
            window_type=WindowType.CONTACT,
            starts_at=DT,
            ends_at=DT2,
            timezone="UTC",
            capacity=1,
            reserved=0,
        )
        assert w.window_id == "alias-1"
        assert type(w).__name__ == "SchedulingWindow"
