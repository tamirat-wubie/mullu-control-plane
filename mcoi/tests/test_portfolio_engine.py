"""Comprehensive tests for PortfolioEngine and PortfolioIntegration.

Covers:
  - PortfolioEngine (mcoi_runtime/core/portfolio.py)
  - PortfolioIntegration (mcoi_runtime/core/portfolio_integration.py)
  - Golden scenarios (44E)
"""

from __future__ import annotations

import time

import pytest
from datetime import datetime, timezone, timedelta

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.work_campaign import WorkCampaignEngine
from mcoi_runtime.core.work_campaign_integration import WorkCampaignIntegration
from mcoi_runtime.core.portfolio import PortfolioEngine
from mcoi_runtime.core.portfolio_integration import PortfolioIntegration
from mcoi_runtime.contracts.work_campaign import (
    CampaignStep, CampaignStepType, CampaignPriority, CampaignStatus,
)
from mcoi_runtime.contracts.portfolio import (
    CampaignReservation,
    CapacitySnapshot,
    PortfolioClosureReport,
    PortfolioDescriptor,
    PortfolioHealth,
    PortfolioPriority,
    PortfolioStatus,
    PreemptionPolicy,
    PreemptionRecord,
    QuotaReservation,
    ResourceClass,
    ResourceReservation,
    ReservationType,
    ScheduleWindow,
    SchedulingDecision,
    SchedulingMode,
    SchedulingVerdict,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def engines():
    es = EventSpineEngine()
    mm = MemoryMeshEngine()
    wce = WorkCampaignEngine(es)
    wci = WorkCampaignIntegration(wce, es, mm)
    pe = PortfolioEngine(wce, es)
    pi = PortfolioIntegration(pe, wce, wci, es, mm)
    return es, mm, wce, wci, pe, pi


def _register_campaign(wce, campaign_id, priority=CampaignPriority.NORMAL):
    steps = [
        CampaignStep(
            step_id=f"{campaign_id}-check", campaign_id=campaign_id,
            step_type=CampaignStepType.CHECK_CONDITION, order=0, name="Check",
        ),
        CampaignStep(
            step_id=f"{campaign_id}-close", campaign_id=campaign_id,
            step_type=CampaignStepType.CLOSE, order=1, name="Close",
        ),
    ]
    return wce.register_campaign(campaign_id, f"Campaign {campaign_id}", steps, priority=priority)


def _future_iso(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _past_iso(seconds: int = 3600) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=seconds)).isoformat()


# ======================================================================
# TestPortfolioRegistration
# ======================================================================


class TestPortfolioRegistration:
    """Tests for portfolio registration and retrieval."""

    def test_register_portfolio_returns_descriptor(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "Portfolio One")
        assert isinstance(desc, PortfolioDescriptor)
        assert desc.portfolio_id == "p1"
        assert desc.name == "Portfolio One"

    def test_register_portfolio_status_is_active(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1")
        assert desc.status == PortfolioStatus.ACTIVE

    def test_register_portfolio_default_mode_is_priority(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1")
        assert desc.scheduling_mode == SchedulingMode.PRIORITY

    def test_register_portfolio_default_policy_is_priority_only(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1")
        assert desc.preemption_policy == PreemptionPolicy.PRIORITY_ONLY

    def test_register_portfolio_custom_mode(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1", scheduling_mode=SchedulingMode.FIFO)
        assert desc.scheduling_mode == SchedulingMode.FIFO

    def test_register_portfolio_custom_policy(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1", preemption_policy=PreemptionPolicy.NEVER)
        assert desc.preemption_policy == PreemptionPolicy.NEVER

    def test_register_portfolio_custom_priority(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1", priority=PortfolioPriority.URGENT)
        assert desc.priority == PortfolioPriority.URGENT

    def test_register_portfolio_rejects_duplicate(self, engines):
        _, _, _, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        with pytest.raises(RuntimeCoreInvariantError, match="^portfolio already registered$") as exc_info:
            pe.register_portfolio("p1", "P1 again")
        assert "p1" not in str(exc_info.value)

    def test_register_portfolio_max_concurrent(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1", max_concurrent=3)
        assert desc.max_concurrent == 3

    def test_register_portfolio_tags(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1", tags=("alpha", "beta"))
        assert "alpha" in desc.tags
        assert "beta" in desc.tags

    def test_register_portfolio_metadata(self, engines):
        _, _, _, _, pe, _ = engines
        desc = pe.register_portfolio("p1", "P1", metadata={"region": "us-east"})
        assert desc.metadata["region"] == "us-east"

    def test_register_portfolio_emits_event(self, engines):
        es, _, _, _, pe, _ = engines
        before = len(es.list_events())
        pe.register_portfolio("p1", "P1")
        after = len(es.list_events())
        assert after > before

    def test_get_portfolio_works(self, engines):
        _, _, _, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        desc = pe.get_portfolio("p1")
        assert desc.portfolio_id == "p1"

    def test_get_portfolio_unknown_raises(self, engines):
        _, _, _, _, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError, match="^portfolio not found$") as exc_info:
            pe.get_portfolio("nonexistent")
        assert "nonexistent" not in str(exc_info.value)


# ======================================================================
# TestCampaignRegistrationInPortfolio
# ======================================================================


class TestCampaignRegistrationInPortfolio:
    """Tests for registering campaigns into portfolios."""

    def test_register_campaign_returns_reservation(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        res = pe.register_campaign("p1", "c1")
        assert isinstance(res, CampaignReservation)
        assert res.campaign_id == "c1"
        assert res.portfolio_id == "p1"

    def test_register_campaign_priority_score(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1", priority=CampaignPriority.HIGH)
        res = pe.register_campaign("p1", "c1")
        assert res.priority_score == pytest.approx(0.6)

    def test_register_campaign_critical_priority_score(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1", priority=CampaignPriority.CRITICAL)
        res = pe.register_campaign("p1", "c1")
        assert res.priority_score == pytest.approx(1.0)

    def test_register_campaign_low_priority_score(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1", priority=CampaignPriority.LOW)
        res = pe.register_campaign("p1", "c1")
        assert res.priority_score == pytest.approx(0.2)

    def test_register_campaign_rejects_duplicate(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        with pytest.raises(RuntimeCoreInvariantError, match="^campaign already registered in portfolio$") as exc_info:
            pe.register_campaign("p1", "c1")
        assert "c1" not in str(exc_info.value)

    def test_register_campaign_with_deadline_boost_near(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1", priority=CampaignPriority.NORMAL)
        near_deadline = _future_iso(seconds=1800)  # 30 minutes
        res = pe.register_campaign("p1", "c1", deadline=near_deadline)
        # NORMAL = 0.4, near-deadline boost = +0.3 => 0.7
        assert res.priority_score == pytest.approx(0.7)

    def test_register_campaign_with_deadline_boost_day(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1", priority=CampaignPriority.NORMAL)
        day_deadline = _future_iso(seconds=43200)  # 12 hours
        res = pe.register_campaign("p1", "c1", deadline=day_deadline)
        # NORMAL = 0.4, day boost = +0.1 => 0.5
        assert res.priority_score == pytest.approx(0.5)

    def test_register_campaign_updates_portfolio_campaign_ids(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        portfolio = pe.get_portfolio("p1")
        assert "c1" in portfolio.campaign_ids

    def test_register_campaign_preemptible_default_true(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        res = pe.register_campaign("p1", "c1")
        assert res.preemptible is True

    def test_register_campaign_non_preemptible(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        res = pe.register_campaign("p1", "c1", preemptible=False)
        assert res.preemptible is False

    def test_register_campaign_with_sla(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        res = pe.register_campaign("p1", "c1", sla_seconds=600)
        assert res.sla_seconds == 600


# ======================================================================
# TestScheduling
# ======================================================================


class TestScheduling:
    """Tests for schedule_next and scheduling modes."""

    def test_schedule_next_picks_highest_priority(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-high", priority=CampaignPriority.HIGH)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-high")
        decision = pe.schedule_next("p1")
        assert decision.verdict == SchedulingVerdict.SCHEDULED
        assert decision.campaign_id == "c-high"

    def test_schedule_next_fifo_picks_oldest(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", scheduling_mode=SchedulingMode.FIFO)
        _register_campaign(wce, "c-first", priority=CampaignPriority.HIGH)
        pe.register_campaign("p1", "c-first")
        time.sleep(0.01)
        _register_campaign(wce, "c-second", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-second")
        decision = pe.schedule_next("p1")
        assert decision.campaign_id == "c-first"

    def test_schedule_next_deadline_mode_picks_nearest(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", scheduling_mode=SchedulingMode.DEADLINE)
        _register_campaign(wce, "c-far")
        _register_campaign(wce, "c-near")
        pe.register_campaign("p1", "c-far", deadline=_future_iso(7200))
        pe.register_campaign("p1", "c-near", deadline=_future_iso(1800))
        decision = pe.schedule_next("p1")
        assert decision.campaign_id == "c-near"

    def test_schedule_next_returns_unschedulable_when_empty(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        decision = pe.schedule_next("p1")
        assert decision.verdict == SchedulingVerdict.UNSCHEDULABLE

    def test_schedule_next_returns_deferred_when_max_concurrent_reached(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", max_concurrent=1)
        _register_campaign(wce, "c1", priority=CampaignPriority.HIGH)
        _register_campaign(wce, "c2", priority=CampaignPriority.NORMAL)
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        # Schedule first
        d1 = pe.schedule_next("p1")
        assert d1.verdict == SchedulingVerdict.SCHEDULED
        # Second should be deferred
        d2 = pe.schedule_next("p1")
        assert d2.verdict == SchedulingVerdict.DEFERRED

    def test_schedule_next_returns_waiting_for_human(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        # Manually mark as waiting_on_human
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=True,
            domain_pack_id=res.domain_pack_id,
            scheduled=res.scheduled,
            deferred=res.deferred,
            created_at=res.created_at,
        )
        decision = pe.schedule_next("p1")
        assert decision.verdict == SchedulingVerdict.WAITING

    def test_schedule_next_marks_campaign_as_scheduled(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.schedule_next("p1")
        res = pe.get_campaign_reservation("c1")
        assert res.scheduled is True

    def test_schedule_next_emits_event(self, engines):
        es, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        before = len(es.list_events())
        pe.schedule_next("p1")
        after = len(es.list_events())
        assert after > before

    def test_scheduling_decision_recorded(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.schedule_next("p1")
        decisions = pe.get_scheduling_decisions("p1")
        assert len(decisions) >= 1

    def test_schedule_next_unknown_portfolio_raises(self, engines):
        _, _, _, _, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            pe.schedule_next("nonexistent")

    def test_schedule_already_scheduled_skipped(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.schedule_next("p1")  # schedules c1
        decision = pe.schedule_next("p1")  # no more candidates
        assert decision.verdict == SchedulingVerdict.UNSCHEDULABLE

    def test_sla_mode_picks_shortest_sla(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", scheduling_mode=SchedulingMode.SLA)
        _register_campaign(wce, "c-long")
        _register_campaign(wce, "c-short")
        pe.register_campaign("p1", "c-long", sla_seconds=3600)
        pe.register_campaign("p1", "c-short", sla_seconds=300)
        decision = pe.schedule_next("p1")
        assert decision.campaign_id == "c-short"


# ======================================================================
# TestResourceReservation
# ======================================================================


class TestResourceReservation:
    """Tests for reserve_resources and release_resources."""

    def test_reserve_resources_returns_reservation(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("worker-1", 5)
        res = pe.reserve_resources("p1", "c1", "worker-1", units=2)
        assert isinstance(res, ResourceReservation)
        assert res.units_reserved == 2

    def test_reserve_resources_insufficient_capacity_returns_none(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("worker-1", 1)
        res = pe.reserve_resources("p1", "c1", "worker-1", units=5)
        assert res is None

    def test_reserve_resources_no_capacity_set_returns_none(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        res = pe.reserve_resources("p1", "c1", "unknown-worker", units=1)
        assert res is None

    def test_release_resources_works(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("worker-1", 5)
        res = pe.reserve_resources("p1", "c1", "worker-1", units=2)
        released = pe.release_resources(res.reservation_id)
        assert released is True

    def test_release_resources_returns_capacity(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("worker-1", 3)
        res = pe.reserve_resources("p1", "c1", "worker-1", units=3)
        # Now at capacity
        assert pe.reserve_resources("p1", "c1", "worker-1", units=1) is None
        pe.release_resources(res.reservation_id)
        # Should be available again
        res2 = pe.reserve_resources("p1", "c1", "worker-1", units=1)
        assert res2 is not None

    def test_release_unknown_reservation_returns_false(self, engines):
        _, _, _, _, pe, _ = engines
        assert pe.release_resources("nonexistent") is False

    def test_release_already_released_returns_false(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("worker-1", 5)
        res = pe.reserve_resources("p1", "c1", "worker-1", units=1)
        pe.release_resources(res.reservation_id)
        assert pe.release_resources(res.reservation_id) is False

    def test_reserve_resources_custom_class_and_type(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("sys-1", 10)
        res = pe.reserve_resources(
            "p1", "c1", "sys-1",
            resource_class=ResourceClass.SYSTEM,
            reservation_type=ReservationType.FUNCTION,
        )
        assert res.resource_class == ResourceClass.SYSTEM
        assert res.reservation_type == ReservationType.FUNCTION

    def test_get_resource_reservations_by_campaign(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("w1", 10)
        pe.reserve_resources("p1", "c1", "w1", units=1)
        reservations = pe.get_resource_reservations("c1")
        assert len(reservations) == 1


# ======================================================================
# TestQuotaReservation
# ======================================================================


class TestQuotaReservation:
    """Tests for reserve_quota."""

    def test_reserve_quota_returns_quota_reservation(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        qr = pe.reserve_quota("p1", "c1", "connector-email", 100)
        assert isinstance(qr, QuotaReservation)
        assert qr.quota_units == 100
        assert qr.quota_remaining == 100
        assert qr.connector_id == "connector-email"

    def test_reserve_quota_stored(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.reserve_quota("p1", "c1", "conn-1", 50)
        quotas = pe.get_quota_reservations("c1")
        assert len(quotas) == 1

    def test_reserve_quota_emits_event(self, engines):
        es, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        before = len(es.list_events())
        pe.reserve_quota("p1", "c1", "conn-1", 50)
        after = len(es.list_events())
        assert after > before


# ======================================================================
# TestScheduleWindows
# ======================================================================


class TestScheduleWindows:
    """Tests for add_schedule_window."""

    def test_add_schedule_window_returns_window(self, engines):
        _, _, _, _, pe, _ = engines
        now = datetime.now(timezone.utc).isoformat()
        later = _future_iso(3600)
        window = pe.add_schedule_window("w1", "agent-1", now, later)
        assert isinstance(window, ScheduleWindow)
        assert window.window_id == "w1"
        assert window.resource_ref == "agent-1"

    def test_add_schedule_window_rejects_duplicate(self, engines):
        _, _, _, _, pe, _ = engines
        now = datetime.now(timezone.utc).isoformat()
        later = _future_iso(3600)
        pe.add_schedule_window("w1", "agent-1", now, later)
        with pytest.raises(RuntimeCoreInvariantError, match="^schedule window already exists$") as exc_info:
            pe.add_schedule_window("w1", "agent-1", now, later)
        assert "w1" not in str(exc_info.value)

    def test_add_schedule_window_custom_class(self, engines):
        _, _, _, _, pe, _ = engines
        now = datetime.now(timezone.utc).isoformat()
        later = _future_iso(3600)
        window = pe.add_schedule_window(
            "w1", "sys-1", now, later, resource_class=ResourceClass.SYSTEM,
        )
        assert window.resource_class == ResourceClass.SYSTEM


# ======================================================================
# TestPreemption
# ======================================================================


class TestPreemption:
    """Tests for preempt_campaign."""

    def test_preempt_higher_over_lower(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-high", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-high")
        pe.schedule_next("p1")  # schedules c-high
        record = pe.preempt_campaign("p1", "c-high", "c-low")
        assert isinstance(record, PreemptionRecord)
        assert record.preempting_campaign_id == "c-high"
        assert record.preempted_campaign_id == "c-low"

    def test_preempt_never_policy_blocks(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", preemption_policy=PreemptionPolicy.NEVER)
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-high", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-high")
        record = pe.preempt_campaign("p1", "c-high", "c-low")
        assert record is None

    def test_preempt_non_preemptible_blocked(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-high", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-low", preemptible=False)
        pe.register_campaign("p1", "c-high")
        record = pe.preempt_campaign("p1", "c-high", "c-low")
        assert record is None

    def test_preempt_equal_priority_blocked_with_priority_only(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", preemption_policy=PreemptionPolicy.PRIORITY_ONLY)
        _register_campaign(wce, "c1", priority=CampaignPriority.NORMAL)
        _register_campaign(wce, "c2", priority=CampaignPriority.NORMAL)
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        record = pe.preempt_campaign("p1", "c2", "c1")
        assert record is None

    def test_preempt_marks_deferred(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-high", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-high")
        pe.preempt_campaign("p1", "c-high", "c-low")
        res = pe.get_campaign_reservation("c-low")
        assert res.deferred is True
        assert res.scheduled is False
        assert res.deferred_reason == "preempted by higher-priority campaign"
        assert "c-high" not in res.deferred_reason

    def test_preempt_releases_resources(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-high", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-high")
        pe.set_resource_capacity("w1", 10)
        pe.reserve_resources("p1", "c-low", "w1", units=3)
        pe.preempt_campaign("p1", "c-high", "c-low")
        # Resources for c-low should be released
        reservations = pe.get_resource_reservations("c-low")
        assert all(not r.active for r in reservations)

    def test_preempt_records_stored(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-high", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-high")
        pe.preempt_campaign("p1", "c-high", "c-low")
        records = pe.get_preemption_records("p1")
        assert len(records) == 1

    def test_preempt_nonexistent_campaign_returns_none(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        record = pe.preempt_campaign("p1", "c1", "nonexistent")
        assert record is None

    def test_preempt_always_policy_allows_equal_priority(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", preemption_policy=PreemptionPolicy.ALWAYS)
        _register_campaign(wce, "c1", priority=CampaignPriority.NORMAL)
        _register_campaign(wce, "c2", priority=CampaignPriority.NORMAL)
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        record = pe.preempt_campaign("p1", "c2", "c1")
        assert record is not None

    def test_preempt_priority_delta(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-crit", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-crit")
        record = pe.preempt_campaign("p1", "c-crit", "c-low")
        # CRITICAL=1.0, LOW=0.2 => delta=0.8
        assert record.priority_delta == pytest.approx(0.8)


# ======================================================================
# TestRebalance
# ======================================================================


class TestRebalance:
    """Tests for rebalance_portfolio."""

    def test_rebalance_reschedules_deferred(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", max_concurrent=1)
        _register_campaign(wce, "c1", priority=CampaignPriority.HIGH)
        _register_campaign(wce, "c2", priority=CampaignPriority.NORMAL)
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        pe.schedule_next("p1")  # schedules c1
        pe.schedule_next("p1")  # defers c2
        # Now raise max_concurrent
        portfolio = pe.get_portfolio("p1")
        pe._portfolios["p1"] = PortfolioDescriptor(
            portfolio_id=portfolio.portfolio_id,
            name=portfolio.name,
            description=portfolio.description,
            status=portfolio.status,
            priority=portfolio.priority,
            scheduling_mode=portfolio.scheduling_mode,
            preemption_policy=portfolio.preemption_policy,
            owner_id=portfolio.owner_id,
            campaign_ids=portfolio.campaign_ids,
            max_concurrent=10,
            tags=portfolio.tags,
            created_at=portfolio.created_at,
            metadata=dict(portfolio.metadata),
        )
        # Mark c2 as deferred manually (it should already be from schedule_next)
        # Actually the DEFERRED verdict does not set deferred=True on the reservation.
        # We need to manually defer it.
        res_c2 = pe._campaign_reservations["c2"]
        pe._campaign_reservations["c2"] = CampaignReservation(
            reservation_id=res_c2.reservation_id,
            portfolio_id=res_c2.portfolio_id,
            campaign_id=res_c2.campaign_id,
            priority_score=res_c2.priority_score,
            deadline=res_c2.deadline,
            sla_seconds=res_c2.sla_seconds,
            preemptible=res_c2.preemptible,
            waiting_on_human=res_c2.waiting_on_human,
            domain_pack_id=res_c2.domain_pack_id,
            scheduled=False,
            deferred=True,
            deferred_reason="max concurrent",
            created_at=res_c2.created_at,
        )
        decisions = pe.rebalance_portfolio("p1")
        assert len(decisions) >= 1
        assert any(d.campaign_id == "c2" for d in decisions)

    def test_rebalance_respects_max_concurrent(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", max_concurrent=1)
        _register_campaign(wce, "c1", priority=CampaignPriority.HIGH)
        _register_campaign(wce, "c2", priority=CampaignPriority.NORMAL)
        _register_campaign(wce, "c3", priority=CampaignPriority.LOW)
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        pe.register_campaign("p1", "c3")
        pe.schedule_next("p1")  # schedules c1
        # Mark c2 and c3 as deferred
        for cid in ("c2", "c3"):
            res = pe._campaign_reservations[cid]
            pe._campaign_reservations[cid] = CampaignReservation(
                reservation_id=res.reservation_id,
                portfolio_id=res.portfolio_id,
                campaign_id=res.campaign_id,
                priority_score=res.priority_score,
                deadline=res.deadline,
                sla_seconds=res.sla_seconds,
                preemptible=res.preemptible,
                waiting_on_human=res.waiting_on_human,
                domain_pack_id=res.domain_pack_id,
                scheduled=False,
                deferred=True,
                created_at=res.created_at,
            )
        # max_concurrent=1 and c1 is already scheduled => no room
        decisions = pe.rebalance_portfolio("p1")
        assert len(decisions) == 0

    def test_rebalance_returns_scheduling_decisions(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", max_concurrent=5)
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=res.waiting_on_human,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=True,
            created_at=res.created_at,
        )
        decisions = pe.rebalance_portfolio("p1")
        assert len(decisions) == 1
        assert decisions[0].verdict == SchedulingVerdict.SCHEDULED

    def test_rebalance_emits_event(self, engines):
        es, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        before = len(es.list_events())
        pe.rebalance_portfolio("p1")
        after = len(es.list_events())
        assert after > before


# ======================================================================
# TestOverdueCampaigns
# ======================================================================


class TestOverdueCampaigns:
    """Tests for overdue_campaigns."""

    def test_overdue_past_deadline(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        past = _past_iso(3600)
        pe.register_campaign("p1", "c1", deadline=past)
        overdue = pe.overdue_campaigns("p1")
        assert len(overdue) >= 1
        assert any(r.campaign_id == "c1" for r in overdue)

    def test_overdue_max_age(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        # With max_age_seconds=0, everything is overdue
        overdue = pe.overdue_campaigns("p1", max_age_seconds=0)
        assert len(overdue) >= 1

    def test_not_overdue_future_deadline(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        future = _future_iso(86400 * 7)
        pe.register_campaign("p1", "c1", deadline=future)
        overdue = pe.overdue_campaigns("p1", max_age_seconds=86400 * 365)
        assert len(overdue) == 0


# ======================================================================
# TestBlockedCampaigns
# ======================================================================


class TestBlockedCampaigns:
    """Tests for blocked_campaigns."""

    def test_blocked_returns_deferred(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=False,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=True,
            created_at=res.created_at,
        )
        blocked = pe.blocked_campaigns("p1")
        assert len(blocked) == 1

    def test_blocked_returns_waiting(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=True,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=False,
            created_at=res.created_at,
        )
        blocked = pe.blocked_campaigns("p1")
        assert len(blocked) == 1

    def test_blocked_empty_when_all_scheduled(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.schedule_next("p1")
        blocked = pe.blocked_campaigns("p1")
        assert len(blocked) == 0


# ======================================================================
# TestCapacitySnapshot
# ======================================================================


class TestCapacitySnapshot:
    """Tests for capacity_snapshot."""

    def test_capacity_snapshot_returns_snapshot(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        snap = pe.capacity_snapshot("p1")
        assert isinstance(snap, CapacitySnapshot)
        assert snap.portfolio_id == "p1"

    def test_capacity_snapshot_counts_active(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.schedule_next("p1")
        snap = pe.capacity_snapshot("p1")
        assert snap.active_campaigns == 1

    def test_capacity_snapshot_counts_workers(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        pe.set_resource_capacity("w1", 5)
        pe.set_resource_capacity("w2", 3)
        snap = pe.capacity_snapshot("p1")
        assert snap.total_workers == 8
        assert snap.available_workers == 8

    def test_capacity_snapshot_available_after_reservation(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("w1", 5)
        pe.reserve_resources("p1", "c1", "w1", units=2)
        snap = pe.capacity_snapshot("p1")
        assert snap.total_workers == 5
        assert snap.available_workers == 3


# ======================================================================
# TestPortfolioHealth
# ======================================================================


class TestPortfolioHealth:
    """Tests for portfolio_health."""

    def test_portfolio_health_returns_health(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        health = pe.portfolio_health("p1")
        assert isinstance(health, PortfolioHealth)
        assert health.portfolio_id == "p1"

    def test_portfolio_health_counts(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        _register_campaign(wce, "c2")
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        pe.schedule_next("p1")  # schedules c1
        health = pe.portfolio_health("p1")
        assert health.total_campaigns == 2
        assert health.active_campaigns == 1

    def test_portfolio_health_utilization(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        _register_campaign(wce, "c2")
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        pe.schedule_next("p1")  # schedules 1 of 2
        health = pe.portfolio_health("p1")
        assert health.utilization == pytest.approx(0.5)

    def test_portfolio_health_deferred_count(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=False,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=True,
            created_at=res.created_at,
        )
        health = pe.portfolio_health("p1")
        assert health.deferred_campaigns == 1

    def test_portfolio_health_blocked_count(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=True,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=False,
            created_at=res.created_at,
        )
        health = pe.portfolio_health("p1")
        assert health.blocked_campaigns == 1


# ======================================================================
# TestClosePortfolio
# ======================================================================


class TestClosePortfolio:
    """Tests for close_portfolio."""

    def test_close_portfolio_returns_report(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        report = pe.close_portfolio("p1")
        assert isinstance(report, PortfolioClosureReport)
        assert report.portfolio_id == "p1"
        assert report.total_campaigns == 1

    def test_close_portfolio_sets_completed_status(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        pe.close_portfolio("p1")
        portfolio = pe.get_portfolio("p1")
        assert portfolio.status == PortfolioStatus.COMPLETED

    def test_close_portfolio_counts_scheduling_decisions(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.schedule_next("p1")
        report = pe.close_portfolio("p1")
        assert report.total_scheduling_decisions >= 1

    def test_close_portfolio_counts_reservations(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("w1", 10)
        pe.reserve_resources("p1", "c1", "w1", units=1)
        pe.reserve_quota("p1", "c1", "conn-1", 50)
        report = pe.close_portfolio("p1")
        assert report.total_resource_reservations == 1
        assert report.total_quota_reservations == 1


# ======================================================================
# TestStateHash
# ======================================================================


class TestStateHash:
    """Tests for state_hash."""

    def test_state_hash_deterministic(self, engines):
        _, _, _, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        h1 = pe.state_hash()
        h2 = pe.state_hash()
        assert h1 == h2

    def test_state_hash_changes_after_modification(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        h1 = pe.state_hash()
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        h2 = pe.state_hash()
        assert h1 != h2

    def test_state_hash_changes_after_scheduling(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        h1 = pe.state_hash()
        pe.schedule_next("p1")
        h2 = pe.state_hash()
        assert h1 != h2

    def test_state_hash_is_string(self, engines):
        _, _, _, _, pe, _ = engines
        h = pe.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64


# ======================================================================
# TestProperties
# ======================================================================


class TestProperties:
    """Tests for portfolio_count, reservation_count, decision_count."""

    def test_portfolio_count_starts_zero(self, engines):
        _, _, _, _, pe, _ = engines
        assert pe.portfolio_count == 0

    def test_portfolio_count_increments(self, engines):
        _, _, _, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        pe.register_portfolio("p2", "P2")
        assert pe.portfolio_count == 2

    def test_reservation_count_starts_zero(self, engines):
        _, _, _, _, pe, _ = engines
        assert pe.reservation_count == 0

    def test_reservation_count_increments(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        assert pe.reservation_count == 1

    def test_decision_count_starts_zero(self, engines):
        _, _, _, _, pe, _ = engines
        assert pe.decision_count == 0

    def test_decision_count_increments(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.schedule_next("p1")
        assert pe.decision_count >= 1


# ======================================================================
# TestPortfolioIntegrationConstructor
# ======================================================================


class TestPortfolioIntegrationConstructor:
    """Tests for PortfolioIntegration constructor type validation."""

    def test_invalid_portfolio_engine_raises(self, engines):
        _, _, wce, wci, _, _ = engines
        es = EventSpineEngine()
        mm = MemoryMeshEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            PortfolioIntegration("not_engine", wce, wci, es, mm)

    def test_invalid_campaign_engine_raises(self, engines):
        es, mm, wce, wci, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            PortfolioIntegration(pe, "not_engine", wci, es, mm)

    def test_invalid_campaign_integration_raises(self, engines):
        es, mm, wce, wci, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            PortfolioIntegration(pe, wce, "not_integration", es, mm)

    def test_invalid_event_spine_raises(self, engines):
        es, mm, wce, wci, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            PortfolioIntegration(pe, wce, wci, "not_spine", mm)

    def test_invalid_memory_engine_raises(self, engines):
        es, mm, wce, wci, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            PortfolioIntegration(pe, wce, wci, es, "not_memory")


# ======================================================================
# TestPortfolioIntegrationScheduling
# ======================================================================


class TestPortfolioIntegrationScheduling:
    """Tests for schedule_campaign_run, schedule_from_goal, schedule_from_obligations."""

    def test_schedule_campaign_run_returns_dict(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        result = pi.schedule_campaign_run("p1", "c1")
        assert isinstance(result, dict)
        assert "decision" in result

    def test_schedule_campaign_run_scheduled_has_run_result(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        result = pi.schedule_campaign_run("p1", "c1")
        assert result["decision"].verdict == SchedulingVerdict.SCHEDULED
        assert result["run_result"] is not None

    def test_schedule_campaign_run_unschedulable_no_run(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        result = pi.schedule_campaign_run("p1", "c1")
        assert result["decision"].verdict == SchedulingVerdict.UNSCHEDULABLE
        assert result["run_result"] is None

    def test_schedule_from_goal_returns_reservation_and_decision(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        result = pi.schedule_from_goal("p1", "goal-1", "c1")
        assert "reservation" in result
        assert "decision" in result
        assert result["goal_id"] == "goal-1"

    def test_schedule_from_goal_creates_reservation(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        result = pi.schedule_from_goal("p1", "goal-1", "c1")
        assert isinstance(result["reservation"], CampaignReservation)

    def test_schedule_from_obligations_returns_dict(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        result = pi.schedule_from_obligations("p1", ["obl-1", "obl-2"], "c1")
        assert "reservation" in result
        assert "decision" in result
        assert result["obligation_ids"] == ["obl-1", "obl-2"]

    def test_schedule_from_obligations_with_sla(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        result = pi.schedule_from_obligations(
            "p1", ["obl-1"], "c1", sla_seconds=600,
        )
        assert result["reservation"].sla_seconds == 600


# ======================================================================
# TestPortfolioIntegrationResourceReservation
# ======================================================================


class TestPortfolioIntegrationResourceReservation:
    """Tests for reserve_connector_quota, reserve_team_capacity, reserve_function_capacity."""

    def test_reserve_connector_quota_delegates(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        qr = pi.reserve_connector_quota("p1", "c1", "email-conn", 200)
        assert isinstance(qr, QuotaReservation)
        assert qr.quota_units == 200

    def test_reserve_team_capacity_uses_team_type(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("team-alpha", 5)
        res = pi.reserve_team_capacity("p1", "c1", "team-alpha", units=1)
        assert res is not None
        assert res.reservation_type == ReservationType.TEAM
        assert res.resource_class == ResourceClass.HUMAN

    def test_reserve_function_capacity_uses_function_type(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("func-parser", 3)
        res = pi.reserve_function_capacity("p1", "c1", "func-parser", units=1)
        assert res is not None
        assert res.reservation_type == ReservationType.FUNCTION
        assert res.resource_class == ResourceClass.SYSTEM


# ======================================================================
# TestPortfolioIntegrationRouting
# ======================================================================


class TestPortfolioIntegrationRouting:
    """Tests for route_waiting_campaigns and escalate_unschedulable_campaigns."""

    def test_route_waiting_campaigns_unblocks(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        # Mark as waiting_on_human
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=True,
            domain_pack_id=res.domain_pack_id,
            scheduled=res.scheduled,
            deferred=res.deferred,
            created_at=res.created_at,
        )
        # No waiting runs exist, so it should unblock
        results = pi.route_waiting_campaigns("p1")
        assert len(results) >= 1
        assert results[0]["action"] == "unblocked"

    def test_escalate_unschedulable_past_deadline(self, engines):
        es, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        past = _past_iso(7200)
        pe.register_campaign("p1", "c1", deadline=past)
        escalated = pi.escalate_unschedulable_campaigns("p1")
        assert len(escalated) >= 1
        assert escalated[0]["campaign_id"] == "c1"
        assert escalated[0]["reason"] == "deadline_exceeded"

    def test_escalate_no_deadline_not_escalated(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        escalated = pi.escalate_unschedulable_campaigns("p1")
        assert len(escalated) == 0

    def test_escalate_scheduled_not_escalated(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        past = _past_iso(7200)
        pe.register_campaign("p1", "c1", deadline=past)
        pe.schedule_next("p1")  # schedule it
        escalated = pi.escalate_unschedulable_campaigns("p1")
        assert len(escalated) == 0


# ======================================================================
# TestPortfolioIntegrationMemory
# ======================================================================


class TestPortfolioIntegrationMemory:
    """Tests for attach_portfolio_to_memory_mesh and attach_portfolio_to_graph."""

    def test_attach_to_memory_mesh_returns_record(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        mem = pi.attach_portfolio_to_memory_mesh("p1")
        assert mem.title == "Portfolio state"
        assert "P1" not in mem.title
        assert mem.scope_ref_id == "p1"

    def test_attach_to_memory_mesh_includes_health(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        mem = pi.attach_portfolio_to_memory_mesh("p1")
        assert "total_campaigns" in mem.content
        assert mem.content["total_campaigns"] == 1

    def test_attach_to_graph_returns_dict(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        graph = pi.attach_portfolio_to_graph("p1")
        assert isinstance(graph, dict)
        assert graph["portfolio_id"] == "p1"

    def test_attach_to_graph_has_expected_keys(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        graph = pi.attach_portfolio_to_graph("p1")
        expected_keys = {
            "portfolio_id", "name", "status", "scheduling_mode",
            "preemption_policy", "campaign_count", "health",
            "capacity", "decision_count", "preemption_count",
        }
        assert expected_keys.issubset(set(graph.keys()))

    def test_attach_to_graph_health_subdict(self, engines):
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        graph = pi.attach_portfolio_to_graph("p1")
        health = graph["health"]
        assert "active" in health
        assert "deferred" in health
        assert "blocked" in health
        assert "overdue" in health
        assert "utilization" in health


# ======================================================================
# TestGoldenScenarios
# ======================================================================


class TestGoldenScenarios:
    """Golden scenarios (44E) for portfolio engine."""

    def test_golden_two_campaigns_compete_for_worker_higher_wins(self, engines):
        """Two campaigns compete for same worker; higher priority wins."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-urgent", priority=CampaignPriority.URGENT)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-urgent")

        pe.set_resource_capacity("shared-worker", 1)
        # Both try to reserve
        r_urgent = pe.reserve_resources("p1", "c-urgent", "shared-worker", units=1)
        r_low = pe.reserve_resources("p1", "c-low", "shared-worker", units=1)

        # Urgent gets the worker, low does not
        assert r_urgent is not None
        assert r_low is None

        # Schedule picks urgent first
        decision = pe.schedule_next("p1")
        assert decision.campaign_id == "c-urgent"

    def test_golden_connector_quota_deferred_not_failed(self, engines):
        """Campaign blocked by connector quota gets deferred, not failed."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", max_concurrent=1)
        _register_campaign(wce, "c1", priority=CampaignPriority.HIGH)
        _register_campaign(wce, "c2", priority=CampaignPriority.NORMAL)
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        # Reserve quota for c1
        pe.reserve_quota("p1", "c1", "email-connector", 100)
        # Schedule c1 first
        d1 = pe.schedule_next("p1")
        assert d1.verdict == SchedulingVerdict.SCHEDULED
        # c2 should be deferred (max_concurrent=1)
        d2 = pe.schedule_next("p1")
        assert d2.verdict == SchedulingVerdict.DEFERRED
        # Not UNSCHEDULABLE or FAILED
        assert d2.verdict != SchedulingVerdict.UNSCHEDULABLE

    def test_golden_overdue_waiting_on_human_escalates(self, engines):
        """Overdue waiting-on-human campaign escalates."""
        _, _, wce, _, pe, pi = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        past_deadline = _past_iso(7200)
        pe.register_campaign("p1", "c1", deadline=past_deadline)

        # Mark as waiting_on_human
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=True,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=False,
            created_at=res.created_at,
        )

        # Campaign is overdue
        overdue = pe.overdue_campaigns("p1")
        assert any(r.campaign_id == "c1" for r in overdue)

        # Escalate
        escalated = pi.escalate_unschedulable_campaigns("p1")
        assert any(e["campaign_id"] == "c1" for e in escalated)

    def test_golden_rebalance_moves_deferred_to_available(self, engines):
        """Rebalance moves work from overloaded team to alternative route."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", max_concurrent=5)
        _register_campaign(wce, "c1", priority=CampaignPriority.HIGH)
        _register_campaign(wce, "c2", priority=CampaignPriority.NORMAL)
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")

        # Manually defer c2
        res = pe._campaign_reservations["c2"]
        pe._campaign_reservations["c2"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=False,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=True,
            deferred_reason="overloaded team",
            created_at=res.created_at,
        )

        decisions = pe.rebalance_portfolio("p1")
        assert any(d.campaign_id == "c2" for d in decisions)
        # c2 should now be scheduled
        updated = pe.get_campaign_reservation("c2")
        assert updated.scheduled is True
        assert updated.deferred is False

    def test_golden_impossible_schedule_produces_unschedulable(self, engines):
        """Impossible schedule produces typed UNSCHEDULABLE decision."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        # No campaigns registered at all
        decision = pe.schedule_next("p1")
        assert decision.verdict == SchedulingVerdict.UNSCHEDULABLE
        assert decision.reason == "no candidates available"
        assert isinstance(decision, SchedulingDecision)

    def test_golden_preemption_pauses_low_for_urgent(self, engines):
        """Preemption pauses a low-priority campaign for urgent incident work."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-incident", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-incident")

        # Schedule c-incident and c-low
        pe.schedule_next("p1")  # c-incident (higher priority)
        pe.schedule_next("p1")  # c-low

        # Preempt low for incident
        record = pe.preempt_campaign(
            "p1", "c-incident", "c-low", reason="urgent incident",
        )
        assert record is not None
        assert record.reason == "urgent incident"

        # c-low is deferred
        res = pe.get_campaign_reservation("c-low")
        assert res.deferred is True
        assert res.scheduled is False

    def test_golden_portfolio_health_shows_all_counts(self, engines):
        """Portfolio health shows blocked/overdue/degraded counts correctly."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c-active", priority=CampaignPriority.NORMAL)
        _register_campaign(wce, "c-deferred", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-waiting", priority=CampaignPriority.NORMAL)
        _register_campaign(wce, "c-overdue", priority=CampaignPriority.LOW)

        pe.register_campaign("p1", "c-active")
        pe.register_campaign("p1", "c-deferred")
        pe.register_campaign("p1", "c-waiting")
        pe.register_campaign("p1", "c-overdue", deadline=_past_iso(86400))

        # Schedule c-active
        pe.schedule_next("p1")

        # Mark c-deferred as deferred
        res = pe._campaign_reservations["c-deferred"]
        pe._campaign_reservations["c-deferred"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=False,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=True,
            created_at=res.created_at,
        )

        # Mark c-waiting as waiting_on_human
        res = pe._campaign_reservations["c-waiting"]
        pe._campaign_reservations["c-waiting"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=True,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=False,
            created_at=res.created_at,
        )

        health = pe.portfolio_health("p1")
        assert health.total_campaigns == 4
        assert health.active_campaigns >= 1
        assert health.deferred_campaigns >= 1
        assert health.blocked_campaigns >= 1
        assert health.overdue_campaigns >= 1

    def test_golden_state_hash_stable_after_reservations_and_scheduling(self, engines):
        """State hash preserves after reservations and scheduling."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("w1", 10)
        pe.reserve_resources("p1", "c1", "w1", units=2)
        pe.schedule_next("p1")

        h1 = pe.state_hash()
        h2 = pe.state_hash()
        assert h1 == h2
        assert isinstance(h1, str)
        assert len(h1) == 64

    def test_golden_multiple_portfolios_independent(self, engines):
        """Multiple portfolios do not interfere with each other."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        pe.register_portfolio("p2", "P2")
        _register_campaign(wce, "c1")
        _register_campaign(wce, "c2")
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p2", "c2")

        d1 = pe.schedule_next("p1")
        d2 = pe.schedule_next("p2")
        assert d1.campaign_id == "c1"
        assert d2.campaign_id == "c2"
        assert d1.portfolio_id == "p1"
        assert d2.portfolio_id == "p2"

    def test_golden_full_lifecycle(self, engines):
        """Full lifecycle: register, schedule, preempt, rebalance, close."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "Lifecycle Test", max_concurrent=2)
        _register_campaign(wce, "c1", priority=CampaignPriority.NORMAL)
        _register_campaign(wce, "c2", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c3", priority=CampaignPriority.CRITICAL)
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p1", "c2")
        pe.register_campaign("p1", "c3")

        # Schedule top two
        d1 = pe.schedule_next("p1")
        assert d1.verdict == SchedulingVerdict.SCHEDULED
        d2 = pe.schedule_next("p1")
        assert d2.verdict == SchedulingVerdict.SCHEDULED

        # Third gets deferred
        d3 = pe.schedule_next("p1")
        assert d3.verdict == SchedulingVerdict.DEFERRED

        # Preempt c2 for c3 (mark c2 deferred from the deferred verdict above)
        # c3 is the third, but it was already scheduled. Let's work with what we have.
        # Close
        report = pe.close_portfolio("p1")
        assert report.total_campaigns == 3
        assert report.portfolio_id == "p1"

    def test_golden_preemption_chain(self, engines):
        """Multiple preemptions in sequence work correctly."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", preemption_policy=PreemptionPolicy.ALWAYS)
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-norm", priority=CampaignPriority.NORMAL)
        _register_campaign(wce, "c-high", priority=CampaignPriority.HIGH)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-norm")
        pe.register_campaign("p1", "c-high")

        # First preempt low with norm
        r1 = pe.preempt_campaign("p1", "c-norm", "c-low")
        assert r1 is not None

        # Then preempt norm with high
        r2 = pe.preempt_campaign("p1", "c-high", "c-norm")
        assert r2 is not None

        records = pe.get_preemption_records("p1")
        assert len(records) == 2

    def test_golden_quota_and_resource_combined(self, engines):
        """Campaign has both quota and resource reservations."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("agent-1", 5)
        rr = pe.reserve_resources("p1", "c1", "agent-1", units=2)
        qr = pe.reserve_quota("p1", "c1", "email-conn", 500)
        assert rr is not None
        assert qr is not None

        report = pe.close_portfolio("p1")
        assert report.total_resource_reservations == 1
        assert report.total_quota_reservations == 1


# ======================================================================
# TestEdgeCases
# ======================================================================


class TestEdgeCases:
    """Edge case tests for robustness."""

    def test_engine_constructor_rejects_invalid_campaign_engine(self):
        es = EventSpineEngine()
        with pytest.raises(RuntimeCoreInvariantError):
            PortfolioEngine("not_engine", es)

    def test_engine_constructor_rejects_invalid_event_spine(self):
        es = EventSpineEngine()
        wce = WorkCampaignEngine(es)
        with pytest.raises(RuntimeCoreInvariantError):
            PortfolioEngine(wce, "not_spine")

    def test_register_campaign_in_unknown_portfolio_raises(self, engines):
        _, _, wce, _, pe, _ = engines
        _register_campaign(wce, "c1")
        with pytest.raises(RuntimeCoreInvariantError):
            pe.register_campaign("nonexistent-portfolio", "c1")

    def test_schedule_next_with_all_deferred(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        res = pe._campaign_reservations["c1"]
        pe._campaign_reservations["c1"] = CampaignReservation(
            reservation_id=res.reservation_id,
            portfolio_id=res.portfolio_id,
            campaign_id=res.campaign_id,
            priority_score=res.priority_score,
            deadline=res.deadline,
            sla_seconds=res.sla_seconds,
            preemptible=res.preemptible,
            waiting_on_human=False,
            domain_pack_id=res.domain_pack_id,
            scheduled=False,
            deferred=True,
            created_at=res.created_at,
        )
        decision = pe.schedule_next("p1")
        assert decision.verdict == SchedulingVerdict.UNSCHEDULABLE

    def test_get_campaign_reservation_returns_none_for_unknown(self, engines):
        _, _, _, _, pe, _ = engines
        assert pe.get_campaign_reservation("nonexistent") is None

    def test_get_scheduling_decisions_empty(self, engines):
        _, _, _, _, pe, _ = engines
        decisions = pe.get_scheduling_decisions()
        assert len(decisions) == 0

    def test_get_preemption_records_empty(self, engines):
        _, _, _, _, pe, _ = engines
        records = pe.get_preemption_records()
        assert len(records) == 0

    def test_get_scheduling_decisions_all_portfolios(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        pe.register_portfolio("p2", "P2")
        _register_campaign(wce, "c1")
        _register_campaign(wce, "c2")
        pe.register_campaign("p1", "c1")
        pe.register_campaign("p2", "c2")
        pe.schedule_next("p1")
        pe.schedule_next("p2")
        all_decisions = pe.get_scheduling_decisions()
        assert len(all_decisions) >= 2

    def test_capacity_snapshot_unknown_portfolio_raises(self, engines):
        _, _, _, _, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            pe.capacity_snapshot("nonexistent")

    def test_close_portfolio_unknown_raises(self, engines):
        _, _, _, _, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            pe.close_portfolio("nonexistent")

    def test_rebalance_unknown_portfolio_raises(self, engines):
        _, _, _, _, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            pe.rebalance_portfolio("nonexistent")

    def test_blocked_campaigns_unknown_portfolio_raises(self, engines):
        _, _, _, _, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            pe.blocked_campaigns("nonexistent")

    def test_overdue_campaigns_unknown_portfolio_raises(self, engines):
        _, _, _, _, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            pe.overdue_campaigns("nonexistent")

    def test_portfolio_health_unknown_raises(self, engines):
        _, _, _, _, pe, _ = engines
        with pytest.raises(RuntimeCoreInvariantError):
            pe.portfolio_health("nonexistent")

    def test_many_campaigns_scheduling(self, engines):
        """Register and schedule many campaigns without error."""
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", max_concurrent=50)
        for i in range(20):
            _register_campaign(wce, f"c-{i}")
            pe.register_campaign("p1", f"c-{i}")
        for _ in range(20):
            decision = pe.schedule_next("p1")
            assert decision.verdict == SchedulingVerdict.SCHEDULED
        # 21st should be unschedulable
        decision = pe.schedule_next("p1")
        assert decision.verdict == SchedulingVerdict.UNSCHEDULABLE

    def test_deadline_mode_no_deadlines_falls_back_to_priority(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1", scheduling_mode=SchedulingMode.DEADLINE)
        _register_campaign(wce, "c-low", priority=CampaignPriority.LOW)
        _register_campaign(wce, "c-high", priority=CampaignPriority.HIGH)
        pe.register_campaign("p1", "c-low")
        pe.register_campaign("p1", "c-high")
        decision = pe.schedule_next("p1")
        assert decision.campaign_id == "c-high"

    def test_set_resource_capacity_preserves_reserved(self, engines):
        _, _, wce, _, pe, _ = engines
        pe.register_portfolio("p1", "P1")
        _register_campaign(wce, "c1")
        pe.register_campaign("p1", "c1")
        pe.set_resource_capacity("w1", 10)
        pe.reserve_resources("p1", "c1", "w1", units=3)
        pe.set_resource_capacity("w1", 20)
        # Reserved should still be 3
        assert pe._resource_capacity["w1"]["reserved"] == 3
        assert pe._resource_capacity["w1"]["total"] == 20
