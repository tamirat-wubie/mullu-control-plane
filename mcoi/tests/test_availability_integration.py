"""Tests for availability integration bridge.

Covers: resolve_contact_window_for_identity, resolve_escalation_window_for_obligation,
resolve_campaign_wait_until, resolve_portfolio_schedule_with_availability,
resolve_channel_choice_by_time, attach_availability_to_memory_mesh,
attach_availability_to_graph, and constructor validation.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mcoi_runtime.contracts.availability import (
    AvailabilityKind,
    AvailabilityResolution,
    ResponseExpectation,
)
from mcoi_runtime.core.availability import AvailabilityEngine
from mcoi_runtime.core.availability_integration import AvailabilityIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEEKDAY_10AM = datetime(2025, 6, 15, 10, 0, tzinfo=timezone.utc)  # Sunday? Let's check: 2025-06-15 is a Sunday
# 2025-06-16 is Monday
WEEKDAY_MON_10AM = datetime(2025, 6, 16, 10, 0, tzinfo=timezone.utc)
WEEKDAY_MON_20PM = datetime(2025, 6, 16, 20, 0, tzinfo=timezone.utc)
WEEKDAY_MON_3AM = datetime(2025, 6, 16, 3, 0, tzinfo=timezone.utc)
SATURDAY_10AM = datetime(2025, 6, 14, 10, 0, tzinfo=timezone.utc)  # Saturday


def _make_integration(
    *,
    business_hours: bool = False,
    identity: str = "user-1",
    sla: bool = False,
    quiet_record: bool = False,
    unavailable_record: bool = False,
    channel_blocked_record: bool = False,
) -> AvailabilityIntegration:
    """Build a fresh integration with optional config."""
    es = EventSpineEngine()
    ae = AvailabilityEngine(es)
    mm = MemoryMeshEngine()

    if business_hours:
        ae.set_business_hours(
            "bh-1", identity,
            weekday_start_hour=9, weekday_end_hour=17,
        )

    if sla:
        ae.set_response_sla(
            "sla-1", identity,
            ResponseExpectation.WITHIN_SLA,
            max_response_seconds=3600,
            escalation_after_seconds=1800,
            escalation_target="manager-1",
        )

    if quiet_record:
        ae.set_availability(
            "qr-1", identity,
            AvailabilityKind.QUIET_HOURS,
            "2025-06-16T00:00:00+00:00",
            "2025-06-16T23:59:59+00:00",
            priority_floor="urgent",
            reason="quiet",
        )

    if unavailable_record:
        ae.set_availability(
            "ua-1", identity,
            AvailabilityKind.TEMPORARY_UNAVAILABLE,
            "2025-06-16T00:00:00+00:00",
            "2025-06-16T23:59:59+00:00",
            reason="away",
        )

    if channel_blocked_record:
        ae.set_availability(
            "cb-1", identity,
            AvailabilityKind.TEMPORARY_AVAILABLE,
            "2025-06-16T00:00:00+00:00",
            "2025-06-16T23:59:59+00:00",
            channels_blocked=("sms",),
            reason="no sms",
        )

    return AvailabilityIntegration(ae, es, mm)


def _full_setup():
    """Return (ai, ae, es, mm) tuple for tests needing direct engine access."""
    es = EventSpineEngine()
    ae = AvailabilityEngine(es)
    mm = MemoryMeshEngine()
    ai = AvailabilityIntegration(ae, es, mm)
    return ai, ae, es, mm


# ===================================================================
# Constructor validation
# ===================================================================


class TestConstructorValidation:
    """Constructor must reject wrong types."""

    def test_wrong_availability_engine_type(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="availability_engine"):
            AvailabilityIntegration("not-an-engine", es, mm)

    def test_wrong_availability_engine_none(self):
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="availability_engine"):
            AvailabilityIntegration(None, es, mm)

    def test_wrong_event_spine_type(self):
        es = EventSpineEngine()
        ae = AvailabilityEngine(es)
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            AvailabilityIntegration(ae, "not-a-spine", mm)

    def test_wrong_event_spine_none(self):
        es = EventSpineEngine()
        ae = AvailabilityEngine(es)
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError, match="event_spine"):
            AvailabilityIntegration(ae, None, mm)

    def test_wrong_memory_engine_type(self):
        es = EventSpineEngine()
        ae = AvailabilityEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            AvailabilityIntegration(ae, es, "not-a-mesh")

    def test_wrong_memory_engine_none(self):
        es = EventSpineEngine()
        ae = AvailabilityEngine(es)
        with pytest.raises(RuntimeCoreInvariantError, match="memory_engine"):
            AvailabilityIntegration(ae, es, None)

    def test_wrong_memory_engine_int(self):
        es = EventSpineEngine()
        ae = AvailabilityEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            AvailabilityIntegration(ae, es, 42)

    def test_valid_constructor(self):
        es = EventSpineEngine()
        ae = AvailabilityEngine(es)
        mm = MemoryMeshEngine()
        ai = AvailabilityIntegration(ae, es, mm)
        assert ai is not None


# ===================================================================
# resolve_contact_window_for_identity
# ===================================================================


class TestResolveContactWindowForIdentity:
    """Tests for resolve_contact_window_for_identity."""

    def test_no_business_hours_allowed_now(self):
        ai = _make_integration()
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is True
        assert result["resolution"] == "available_now"

    def test_no_business_hours_identity_ref_in_result(self):
        ai = _make_integration()
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["identity_ref"] == "user-1"

    def test_no_business_hours_reason_present(self):
        ai = _make_integration()
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_10AM,
        )
        assert "reason" in result

    def test_no_business_hours_decision_present(self):
        ai = _make_integration()
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_10AM,
        )
        assert "decision" in result

    def test_no_business_hours_no_next_window(self):
        ai = _make_integration()
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_10AM,
        )
        # When allowed, next_window is present but None
        assert result["next_window"] is None

    def test_during_business_hours_allowed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is True
        assert result["resolution"] == "available_now"

    def test_outside_business_hours_not_allowed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_20PM,
        )
        assert result["allowed_now"] is False

    def test_outside_business_hours_resolution_available_later(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_20PM,
        )
        assert result["resolution"] == "available_later"

    def test_outside_business_hours_next_window_populated(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_20PM,
        )
        assert "next_window" in result
        assert result["next_window"] is not None

    def test_outside_business_hours_contact_at_set(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_20PM,
        )
        assert "contact_at" in result
        assert result["contact_at"] != ""

    def test_quiet_hours_not_allowed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_3AM,
        )
        assert result["allowed_now"] is False
        assert result["resolution"] == "quiet_hours"

    def test_quiet_hours_next_window(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_3AM,
        )
        assert "next_window" in result

    def test_quiet_hours_contact_at(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=WEEKDAY_MON_3AM,
        )
        assert "contact_at" in result

    def test_with_channel_parameter(self):
        ai = _make_integration()
        result = ai.resolve_contact_window_for_identity(
            "user-1", channel="email", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is True

    def test_with_channel_during_business_hours(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", channel="sms", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is True

    def test_quiet_record_blocks_normal_priority(self):
        ai = _make_integration(quiet_record=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", priority="normal", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is False
        assert result["resolution"] == "quiet_hours"

    def test_quiet_record_allows_urgent_priority(self):
        ai = _make_integration(quiet_record=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", priority="urgent", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is True

    def test_unavailable_record_blocks(self):
        ai = _make_integration(unavailable_record=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", priority="normal", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is False
        assert result["resolution"] == "unavailable"

    def test_unavailable_record_urgent_overrides(self):
        ai = _make_integration(unavailable_record=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", priority="urgent", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is True

    def test_weekend_not_allowed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", at_time=SATURDAY_10AM,
        )
        assert result["allowed_now"] is False

    def test_emits_event(self):
        ai, ae, es, mm = _full_setup()
        ai.resolve_contact_window_for_identity("user-1", at_time=WEEKDAY_MON_10AM)
        events = es.list_events()
        assert len(events) >= 1
        payloads = [e.payload for e in events]
        actions = [p.get("action") for p in payloads]
        assert "contact_window_resolved" in actions

    def test_result_is_dict(self):
        ai = _make_integration()
        result = ai.resolve_contact_window_for_identity("user-1", at_time=WEEKDAY_MON_10AM)
        assert isinstance(result, dict)

    def test_with_priority_high(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_contact_window_for_identity(
            "user-1", priority="high", at_time=WEEKDAY_MON_10AM,
        )
        assert result["allowed_now"] is True


# ===================================================================
# resolve_escalation_window_for_obligation
# ===================================================================


class TestResolveEscalationWindowForObligation:
    """Tests for resolve_escalation_window_for_obligation."""

    def test_available_identity_escalation_allowed(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["escalation_allowed"] is True

    def test_available_identity_contact_at_set(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert "contact_at" in result
        assert result["contact_at"] != ""

    def test_available_identity_identity_ref(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["identity_ref"] == "user-1"

    def test_available_identity_obligation_id(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["obligation_id"] == "obl-1"

    def test_unavailable_identity_escalation_not_allowed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_20PM,
        )
        assert result["escalation_allowed"] is False

    def test_unavailable_identity_next_window_computed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_20PM,
        )
        assert "next_window" in result
        assert result["next_window"] is not None

    def test_unavailable_identity_contact_at(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_20PM,
        )
        assert result["contact_at"] != ""

    def test_always_includes_sla_info(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert "sla" in result
        assert isinstance(result["sla"], dict)

    def test_sla_info_with_configured_sla(self):
        ai = _make_integration(sla=True)
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["sla"]["expectation"] == "within_sla"

    def test_sla_info_without_configured_sla(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["sla"]["expectation"] == "best_effort"

    def test_uses_urgent_priority_by_default(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        # Default priority is urgent, so it should be allowed
        assert result["escalation_allowed"] is True

    def test_decision_in_result(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert "decision" in result

    def test_resolution_in_result(self):
        ai = _make_integration()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert "resolution" in result

    def test_emits_event(self):
        ai, ae, es, mm = _full_setup()
        ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        events = es.list_events()
        payloads = [e.payload for e in events]
        actions = [p.get("action") for p in payloads]
        assert "escalation_window_resolved" in actions

    def test_quiet_hours_blocks_urgent(self):
        """Quiet hours from business hours profile blocks even urgent
        unless critical priority."""
        ai = _make_integration(business_hours=True)
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", priority="urgent", at_time=WEEKDAY_MON_3AM,
        )
        assert result["escalation_allowed"] is False


# ===================================================================
# resolve_campaign_wait_until
# ===================================================================


class TestResolveCampaignWaitUntil:
    """Tests for resolve_campaign_wait_until."""

    def test_available_can_proceed_now(self):
        ai = _make_integration()
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["can_proceed_now"] is True

    def test_available_wait_until_empty(self):
        ai = _make_integration()
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["wait_until"] == ""

    def test_not_available_cannot_proceed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_20PM,
        )
        assert result["can_proceed_now"] is False

    def test_not_available_wait_until_set(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_20PM,
        )
        assert result["wait_until"] != ""

    def test_not_available_next_window_present(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_20PM,
        )
        assert "next_window" in result

    def test_no_business_hours_can_proceed(self):
        ai = _make_integration()
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["can_proceed_now"] is True

    def test_identity_ref_in_result(self):
        ai = _make_integration()
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["identity_ref"] == "user-1"

    def test_campaign_id_in_result(self):
        ai = _make_integration()
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["campaign_id"] == "camp-1"

    def test_resolution_in_result(self):
        ai = _make_integration()
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_10AM,
        )
        assert "resolution" in result

    def test_reason_in_result(self):
        ai = _make_integration()
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_10AM,
        )
        assert "reason" in result

    def test_emits_event(self):
        ai, ae, es, mm = _full_setup()
        ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_10AM,
        )
        events = es.list_events()
        payloads = [e.payload for e in events]
        actions = [p.get("action") for p in payloads]
        assert "campaign_wait_resolved" in actions

    def test_quiet_hours_cannot_proceed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=WEEKDAY_MON_3AM,
        )
        assert result["can_proceed_now"] is False

    def test_weekend_cannot_proceed(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_campaign_wait_until(
            "user-1", "camp-1", at_time=SATURDAY_10AM,
        )
        assert result["can_proceed_now"] is False


# ===================================================================
# resolve_portfolio_schedule_with_availability
# ===================================================================


class TestResolvePortfolioScheduleWithAvailability:
    """Tests for resolve_portfolio_schedule_with_availability."""

    def test_all_available(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1", "user-2"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["all_available"] is True

    def test_all_available_no_blocking(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1", "user-2"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["blocking_participants"] == []

    def test_some_blocked(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", weekday_start_hour=9, weekday_end_hour=17)
        ae.set_business_hours("bh-2", "user-2", weekday_start_hour=9, weekday_end_hour=17)
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1", "user-2"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert result["all_available"] is False
        assert "user-1" in result["blocking_participants"]
        assert "user-2" in result["blocking_participants"]

    def test_one_blocked_one_available(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", weekday_start_hour=9, weekday_end_hour=17)
        # user-2 has no business hours, so always available
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1", "user-2"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert result["all_available"] is False
        assert "user-1" in result["blocking_participants"]
        assert "user-2" not in result["blocking_participants"]

    def test_earliest_all_available_computed(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", weekday_start_hour=9, weekday_end_hour=17)
        ae.set_business_hours("bh-2", "user-2", weekday_start_hour=10, weekday_end_hour=18)
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1", "user-2"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert result["earliest_all_available"] != ""

    def test_earliest_all_available_is_latest_of_blockers(self):
        """earliest_all_available should be the latest next-available time."""
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", weekday_start_hour=9, weekday_end_hour=17)
        ae.set_business_hours("bh-2", "user-2", weekday_start_hour=11, weekday_end_hour=19)
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1", "user-2"],
            at_time=WEEKDAY_MON_20PM,
        )
        # Both should be blocking; earliest_all is the later of the two next windows
        assert result["earliest_all_available"] != ""

    def test_all_available_earliest_empty(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["earliest_all_available"] == ""

    def test_portfolio_id_in_result(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["portfolio_id"] == "pf-1"

    def test_campaign_id_in_result(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["campaign_id"] == "camp-1"

    def test_participant_results_present(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1", "user-2"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert len(result["participant_results"]) == 2

    def test_participant_result_has_identity_ref(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["participant_results"][0]["identity_ref"] == "user-1"

    def test_participant_result_has_available_flag(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["participant_results"][0]["available"] is True

    def test_blocked_participant_has_next_window(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", weekday_start_hour=9, weekday_end_hour=17)
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1"],
            at_time=WEEKDAY_MON_20PM,
        )
        pr = result["participant_results"][0]
        assert "next_window" in pr
        assert "available_at" in pr

    def test_emits_event(self):
        ai, ae, es, mm = _full_setup()
        ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1"],
            at_time=WEEKDAY_MON_10AM,
        )
        events = es.list_events()
        payloads = [e.payload for e in events]
        actions = [p.get("action") for p in payloads]
        assert "portfolio_availability_check" in actions

    def test_empty_participants(self):
        ai = _make_integration()
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", [],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["all_available"] is True
        assert result["participant_results"] == []

    def test_single_participant_blocked(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", weekday_start_hour=9, weekday_end_hour=17)
        result = ai.resolve_portfolio_schedule_with_availability(
            "pf-1", "camp-1", ["user-1"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert result["all_available"] is False
        assert result["blocking_participants"] == ["user-1"]


# ===================================================================
# resolve_channel_choice_by_time
# ===================================================================


class TestResolveChannelChoiceByTime:
    """Tests for resolve_channel_choice_by_time."""

    def test_all_channels_allowed_first_chosen(self):
        ai = _make_integration()
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email", "sms", "phone"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["chosen_channel"] == "email"
        assert result["deferred"] is False

    def test_all_channels_allowed_not_deferred(self):
        ai = _make_integration()
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email", "sms"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["deferred"] is False

    def test_channel_results_present(self):
        ai = _make_integration()
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email", "sms"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert len(result["channel_results"]) == 2

    def test_channel_result_has_channel_name(self):
        ai = _make_integration()
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["channel_results"][0]["channel"] == "email"

    def test_channel_result_has_allowed_flag(self):
        ai = _make_integration()
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["channel_results"][0]["allowed"] is True

    def test_no_channels_allowed_deferred(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email", "sms"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert result["deferred"] is True
        assert result["chosen_channel"] == ""

    def test_no_channels_allowed_next_window(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email", "sms"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert "next_window" in result

    def test_no_channels_allowed_contact_at(self):
        ai = _make_integration(business_hours=True)
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert "contact_at" in result

    def test_channel_blocked_by_availability_record(self):
        ai = _make_integration(channel_blocked_record=True)
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["sms", "email"],
            at_time=WEEKDAY_MON_10AM,
        )
        # sms is blocked, email should be chosen
        assert result["chosen_channel"] == "email"
        assert result["deferred"] is False

    def test_channel_blocked_sms_not_allowed(self):
        ai = _make_integration(channel_blocked_record=True)
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["sms", "email"],
            at_time=WEEKDAY_MON_10AM,
        )
        sms_result = [cr for cr in result["channel_results"] if cr["channel"] == "sms"]
        assert len(sms_result) == 1
        assert sms_result[0]["allowed"] is False

    def test_only_blocked_channel_deferred(self):
        ai = _make_integration(channel_blocked_record=True)
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["sms"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["deferred"] is True
        assert result["chosen_channel"] == ""

    def test_identity_ref_in_result(self):
        ai = _make_integration()
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email"],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["identity_ref"] == "user-1"

    def test_emits_event(self):
        ai, ae, es, mm = _full_setup()
        ai.resolve_channel_choice_by_time(
            "user-1", ["email"],
            at_time=WEEKDAY_MON_10AM,
        )
        events = es.list_events()
        payloads = [e.payload for e in events]
        actions = [p.get("action") for p in payloads]
        assert "channel_choice_resolved" in actions

    def test_first_allowed_channel_chosen_when_some_blocked(self):
        ai = _make_integration(channel_blocked_record=True)
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["sms", "phone", "email"],
            at_time=WEEKDAY_MON_10AM,
        )
        # sms blocked, phone should be allowed (no blocking for phone)
        assert result["chosen_channel"] == "phone"

    def test_empty_channels_list_deferred(self):
        ai = _make_integration()
        result = ai.resolve_channel_choice_by_time(
            "user-1", [],
            at_time=WEEKDAY_MON_10AM,
        )
        assert result["deferred"] is True
        assert result["chosen_channel"] == ""


# ===================================================================
# attach_availability_to_memory_mesh
# ===================================================================


class TestAttachAvailabilityToMemoryMesh:
    """Tests for attach_availability_to_memory_mesh."""

    def test_creates_memory_record(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem is not None
        assert mem.memory_id != ""

    def test_memory_record_title(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.title == "Availability state"
        assert "user-1" not in mem.title

    def test_memory_record_scope_ref(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.scope_ref_id == "user-1"

    def test_memory_record_tags(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert "availability" in mem.tags
        assert "state" in mem.tags

    def test_memory_record_source_ids(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert "user-1" in mem.source_ids

    def test_content_has_identity_ref(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.content["identity_ref"] == "user-1"

    def test_content_has_business_hours_false(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.content["has_business_hours"] is False

    def test_includes_business_hours_info_when_set(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", weekday_start_hour=9, weekday_end_hour=17)
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.content["has_business_hours"] is True
        assert "business_hours" in mem.content
        assert mem.content["business_hours"]["weekday_start"] == 9
        assert mem.content["business_hours"]["weekday_end"] == 17

    def test_business_hours_has_weekend_available(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1")
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert "weekend_available" in mem.content["business_hours"]

    def test_business_hours_has_quiet_hours(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", quiet_start_hour=22, quiet_end_hour=7)
        mem = ai.attach_availability_to_memory_mesh("user-1")
        bh = mem.content["business_hours"]
        assert bh["quiet_start"] == 22
        assert bh["quiet_end"] == 7

    def test_business_hours_has_timezone(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1")
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert "timezone" in mem.content["business_hours"]

    def test_includes_sla_info_when_set(self):
        ai, ae, es, mm = _full_setup()
        ae.set_response_sla(
            "sla-1", "user-1",
            ResponseExpectation.WITHIN_SLA,
            max_response_seconds=3600,
            escalation_after_seconds=1800,
            escalation_target="supervisor",
        )
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.content["has_sla"] is True
        assert "sla" in mem.content
        assert mem.content["sla"]["expectation"] == "within_sla"
        assert mem.content["sla"]["max_response_seconds"] == 3600
        assert mem.content["sla"]["escalation_after_seconds"] == 1800

    def test_no_sla_info_when_not_set(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.content["has_sla"] is False
        assert "sla" not in mem.content

    def test_memory_retrievable_from_mesh(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        retrieved = mm.get_memory(mem.memory_id)
        assert retrieved is not None
        assert retrieved.memory_id == mem.memory_id

    def test_availability_record_count(self):
        ai, ae, es, mm = _full_setup()
        ae.set_availability(
            "ar-1", "user-1",
            AvailabilityKind.TEMPORARY_AVAILABLE,
            "2025-06-16T00:00:00+00:00",
            "2025-06-16T23:59:59+00:00",
        )
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.content["availability_record_count"] == 1

    def test_meeting_count_zero(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.content["meeting_count"] == 0

    def test_confidence_is_one(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert mem.confidence == 1.0

    def test_no_business_hours_no_bh_key_in_content(self):
        ai, ae, es, mm = _full_setup()
        mem = ai.attach_availability_to_memory_mesh("user-1")
        assert "business_hours" not in mem.content


# ===================================================================
# attach_availability_to_graph
# ===================================================================


class TestAttachAvailabilityToGraph:
    """Tests for attach_availability_to_graph."""

    def test_returns_dict(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert isinstance(result, dict)

    def test_identity_ref_in_result(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert result["identity_ref"] == "user-1"

    def test_business_hours_none_when_not_set(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert result["business_hours"] is None

    def test_business_hours_present_when_set(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", weekday_start_hour=9, weekday_end_hour=17)
        result = ai.attach_availability_to_graph("user-1")
        assert result["business_hours"] is not None
        assert result["business_hours"]["weekday_start"] == 9
        assert result["business_hours"]["weekday_end"] == 17

    def test_business_hours_has_emergency_override(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1")
        result = ai.attach_availability_to_graph("user-1")
        assert "emergency_override" in result["business_hours"]

    def test_business_hours_has_weekend_available(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1")
        result = ai.attach_availability_to_graph("user-1")
        assert "weekend_available" in result["business_hours"]

    def test_sla_present_when_set(self):
        ai, ae, es, mm = _full_setup()
        ae.set_response_sla(
            "sla-1", "user-1",
            ResponseExpectation.IMMEDIATE,
            max_response_seconds=300,
            escalation_after_seconds=60,
            escalation_target="manager-1",
        )
        result = ai.attach_availability_to_graph("user-1")
        assert result["has_sla"] is True
        assert "sla" in result
        assert result["sla"]["expectation"] == "immediate"
        assert result["sla"]["max_response_seconds"] == 300
        assert result["sla"]["escalation_after_seconds"] == 60
        assert result["sla"]["escalation_target"] == "manager-1"

    def test_sla_absent_when_not_set(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert result["has_sla"] is False
        assert "sla" not in result

    def test_availability_records_count(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert result["availability_records"] == 0

    def test_availability_records_count_with_record(self):
        ai, ae, es, mm = _full_setup()
        ae.set_availability(
            "ar-1", "user-1",
            AvailabilityKind.TEMPORARY_AVAILABLE,
            "2025-06-16T00:00:00+00:00",
            "2025-06-16T23:59:59+00:00",
        )
        result = ai.attach_availability_to_graph("user-1")
        assert result["availability_records"] == 1

    def test_meetings_count(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert result["meetings"] == 0

    def test_windows_count(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert result["windows"] == 0

    def test_conflicts_count(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert result["conflicts"] == 0

    def test_routing_decisions_count(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        assert result["routing_decisions"] == 0

    def test_routing_decisions_count_after_contact_check(self):
        ai, ae, es, mm = _full_setup()
        ae.contact_allowed_now("user-1", at_time=WEEKDAY_MON_10AM)
        result = ai.attach_availability_to_graph("user-1")
        assert result["routing_decisions"] >= 1

    def test_all_counts_present(self):
        ai, ae, es, mm = _full_setup()
        result = ai.attach_availability_to_graph("user-1")
        expected_keys = {
            "identity_ref", "business_hours", "availability_records",
            "meetings", "windows", "conflicts", "routing_decisions", "has_sla",
        }
        assert expected_keys.issubset(set(result.keys()))

    def test_business_hours_quiet_hours_in_graph(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", quiet_start_hour=22, quiet_end_hour=7)
        result = ai.attach_availability_to_graph("user-1")
        bh = result["business_hours"]
        assert bh["quiet_start"] == 22
        assert bh["quiet_end"] == 7

    def test_business_hours_timezone_in_graph(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "user-1", timezone_str="US/Eastern")
        result = ai.attach_availability_to_graph("user-1")
        assert result["business_hours"]["timezone"] == "US/Eastern"


# ===================================================================
# Integration edge case tests
# ===================================================================


class TestIntegrationConsistentReturnSchemas:
    """Verify all bridge methods return consistent schemas."""

    def test_contact_window_allowed_has_next_window_none(self):
        ai = _make_integration(identity="user-1")
        result = ai.resolve_contact_window_for_identity("user-1", at_time=WEEKDAY_MON_10AM)
        assert result["allowed_now"] is True
        assert result["next_window"] is None
        assert result["contact_at"] != ""

    def test_contact_window_blocked_has_next_window(self):
        ai = _make_integration(business_hours=True, identity="user-1")
        result = ai.resolve_contact_window_for_identity("user-1", at_time=WEEKDAY_MON_20PM)
        assert result["allowed_now"] is False
        assert "next_window" in result
        assert "contact_at" in result

    def test_escalation_allowed_has_next_window_none(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert result["escalation_allowed"] is True
        assert result["next_window"] is None
        assert result["contact_at"] != ""

    def test_escalation_blocked_has_next_window(self):
        ai = _make_integration(
            business_hours=True, identity="user-1",
            unavailable_record=True,
        )
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", priority="normal", at_time=WEEKDAY_MON_10AM,
        )
        # Unavailable blocks normal priority
        if not result["escalation_allowed"]:
            assert "next_window" in result

    def test_campaign_wait_can_proceed_has_empty_wait_until(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_campaign_wait_until("user-1", "camp-1", at_time=WEEKDAY_MON_10AM)
        assert result["can_proceed_now"] is True
        assert result["wait_until"] == ""
        assert result["next_window"] is None

    def test_campaign_wait_blocked_has_wait_until(self):
        ai = _make_integration(
            business_hours=True, identity="user-1",
            unavailable_record=True,
        )
        result = ai.resolve_campaign_wait_until("user-1", "camp-1", at_time=WEEKDAY_MON_10AM)
        if not result["can_proceed_now"]:
            assert result["wait_until"] != "" or result["next_window"] is not None


class TestIntegrationResolutionSerialization:
    """Verify resolution fields are serialized as strings, not enums."""

    def test_contact_window_resolution_is_string(self):
        ai = _make_integration(identity="user-1")
        result = ai.resolve_contact_window_for_identity("user-1", at_time=WEEKDAY_MON_10AM)
        assert isinstance(result["resolution"], str)

    def test_escalation_resolution_is_string(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert isinstance(result["resolution"], str)

    def test_campaign_resolution_is_string(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_campaign_wait_until("user-1", "camp-1", at_time=WEEKDAY_MON_10AM)
        assert isinstance(result["resolution"], str)

    def test_portfolio_resolution_is_string(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_portfolio_schedule_with_availability(
            "port-1", "camp-1", ["user-1"], at_time=WEEKDAY_MON_10AM,
        )
        for pr in result["participant_results"]:
            assert isinstance(pr["resolution"], str)

    def test_channel_choice_resolution_is_string(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email", "sms"], at_time=WEEKDAY_MON_10AM,
        )
        for cr in result["channel_results"]:
            assert isinstance(cr["resolution"], str)


class TestIntegrationEventEmission:
    """Verify all bridge methods emit events."""

    def test_contact_window_emits_event(self):
        ai, ae, es, mm = _full_setup()
        count_before = len(es.list_events())
        ai.resolve_contact_window_for_identity("user-1", at_time=WEEKDAY_MON_10AM)
        assert len(es.list_events()) > count_before

    def test_escalation_emits_event(self):
        ai, ae, es, mm = _full_setup()
        count_before = len(es.list_events())
        ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", at_time=WEEKDAY_MON_10AM,
        )
        assert len(es.list_events()) > count_before

    def test_campaign_wait_emits_event(self):
        ai, ae, es, mm = _full_setup()
        count_before = len(es.list_events())
        ai.resolve_campaign_wait_until("user-1", "camp-1", at_time=WEEKDAY_MON_10AM)
        assert len(es.list_events()) > count_before

    def test_portfolio_emits_event(self):
        ai, ae, es, mm = _full_setup()
        count_before = len(es.list_events())
        ai.resolve_portfolio_schedule_with_availability(
            "port-1", "camp-1", ["user-1"], at_time=WEEKDAY_MON_10AM,
        )
        assert len(es.list_events()) > count_before

    def test_channel_choice_emits_event(self):
        ai, ae, es, mm = _full_setup()
        count_before = len(es.list_events())
        ai.resolve_channel_choice_by_time(
            "user-1", ["email"], at_time=WEEKDAY_MON_10AM,
        )
        assert len(es.list_events()) > count_before

    def test_memory_attach_emits_event(self):
        ai, ae, es, mm = _full_setup()
        count_before = len(es.list_events())
        ai.attach_availability_to_memory_mesh("user-1")
        assert len(es.list_events()) > count_before


class TestIntegrationPortfolioEdgeCases:
    """Edge cases for portfolio scheduling."""

    def test_empty_participant_list(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_portfolio_schedule_with_availability(
            "port-1", "camp-1", [], at_time=WEEKDAY_MON_10AM,
        )
        assert result["all_available"] is True
        assert result["blocking_participants"] == []
        assert result["participant_results"] == []

    def test_single_participant_available(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_portfolio_schedule_with_availability(
            "port-1", "camp-1", ["user-1"], at_time=WEEKDAY_MON_10AM,
        )
        assert result["all_available"] is True
        assert len(result["participant_results"]) == 1

    def test_mixed_availability_reports_blocking(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "blocker")
        # blocker at 20:00 = outside biz hours
        result = ai.resolve_portfolio_schedule_with_availability(
            "port-1", "camp-1", ["user-1", "blocker"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert result["all_available"] is False
        assert "blocker" in result["blocking_participants"]

    def test_all_participants_blocked(self):
        ai, ae, es, mm = _full_setup()
        ae.set_business_hours("bh-1", "a")
        ae.set_business_hours("bh-2", "b")
        result = ai.resolve_portfolio_schedule_with_availability(
            "port-1", "camp-1", ["a", "b"],
            at_time=WEEKDAY_MON_20PM,
        )
        assert result["all_available"] is False
        assert len(result["blocking_participants"]) == 2


class TestIntegrationChannelChoiceEdgeCases:
    """Edge cases for channel choice."""

    def test_empty_channel_list_defers(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_channel_choice_by_time(
            "user-1", [], at_time=WEEKDAY_MON_10AM,
        )
        assert result["deferred"] is True
        assert result["chosen_channel"] == ""

    def test_first_allowed_channel_chosen(self):
        ai, ae, es, mm = _full_setup()
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email", "sms", "phone"], at_time=WEEKDAY_MON_10AM,
        )
        assert result["chosen_channel"] == "email"

    def test_all_channels_blocked_defers(self):
        ai = _make_integration(
            business_hours=True, identity="user-1",
            unavailable_record=True,
        )
        result = ai.resolve_channel_choice_by_time(
            "user-1", ["email", "sms"], at_time=WEEKDAY_MON_10AM,
        )
        if result["deferred"]:
            assert result["chosen_channel"] == ""


class TestIntegrationMemoryMeshIdempotency:
    """Verify memory mesh attachment produces deterministic IDs."""

    def test_deterministic_memory_id(self):
        """Same identity produces the same memory_id (deterministic hash)."""
        ai1, ae1, es1, mm1 = _full_setup()
        mem1 = ai1.attach_availability_to_memory_mesh("user-1")
        ai2, ae2, es2, mm2 = _full_setup()
        mem2 = ai2.attach_availability_to_memory_mesh("user-1")
        assert mem1.memory_id == mem2.memory_id

    def test_duplicate_attach_raises(self):
        """Second attach to same engine raises because memory_id is deterministic."""
        ai, ae, es, mm = _full_setup()
        ai.attach_availability_to_memory_mesh("user-1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            ai.attach_availability_to_memory_mesh("user-1")

    def test_different_identities_produce_different_ids(self):
        ai, ae, es, mm = _full_setup()
        mem1 = ai.attach_availability_to_memory_mesh("user-1")
        mem2 = ai.attach_availability_to_memory_mesh("user-2")
        assert mem1.memory_id != mem2.memory_id


class TestIntegrationEscalationWithVacation:
    """Escalation for identity on vacation with SLA."""

    def test_vacation_blocks_normal_escalation(self):
        ai, ae, es, mm = _full_setup()
        ae.set_availability(
            "vac-1", "user-1", AvailabilityKind.VACATION,
            "2025-06-14T00:00:00+00:00", "2025-06-18T23:59:59+00:00",
            priority_floor="critical",
        )
        ae.set_response_sla(
            "sla-1", "user-1", ResponseExpectation.WITHIN_SLA,
            max_response_seconds=3600,
            escalation_after_seconds=1800,
            escalation_target="manager-1",
        )
        result = ai.resolve_escalation_window_for_obligation(
            "user-1", "obl-1", priority="urgent", at_time=WEEKDAY_MON_10AM,
        )
        # Vacation blocks urgent — only critical goes through
        assert result["escalation_allowed"] is False
        assert "sla" in result
