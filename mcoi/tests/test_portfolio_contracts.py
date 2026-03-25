"""Comprehensive tests for mcoi_runtime.contracts.portfolio contracts."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.portfolio import (
    CapacitySnapshot,
    CampaignReservation,
    PortfolioClosureReport,
    PortfolioDescriptor,
    PortfolioHealth,
    PortfolioPriority,
    PortfolioStatus,
    PreemptionPolicy,
    PreemptionRecord,
    QuotaReservation,
    ReservationType,
    ResourceClass,
    ResourceReservation,
    ScheduleWindow,
    SchedulingDecision,
    SchedulingMode,
    SchedulingVerdict,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc).isoformat()


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestPortfolioStatusEnum:
    def test_member_count(self):
        assert len(PortfolioStatus) == 6

    def test_values(self):
        expected = {"draft", "active", "paused", "rebalancing", "completed", "archived"}
        assert {m.value for m in PortfolioStatus} == expected

    def test_lookup_by_value(self):
        assert PortfolioStatus("active") is PortfolioStatus.ACTIVE


class TestPortfolioPriorityEnum:
    def test_member_count(self):
        assert len(PortfolioPriority) == 5

    def test_values(self):
        expected = {"low", "normal", "high", "urgent", "critical"}
        assert {m.value for m in PortfolioPriority} == expected


class TestSchedulingModeEnum:
    def test_member_count(self):
        assert len(SchedulingMode) == 6

    def test_values(self):
        expected = {"fifo", "priority", "deadline", "sla", "round_robin", "weighted"}
        assert {m.value for m in SchedulingMode} == expected


class TestReservationTypeEnum:
    def test_member_count(self):
        assert len(ReservationType) == 7

    def test_values(self):
        expected = {"worker", "team", "function", "connector", "channel", "quota", "time_window"}
        assert {m.value for m in ReservationType} == expected


class TestResourceClassEnum:
    def test_member_count(self):
        assert len(ResourceClass) == 6

    def test_values(self):
        expected = {"human", "system", "connector", "channel", "compute", "budget"}
        assert {m.value for m in ResourceClass} == expected


class TestPreemptionPolicyEnum:
    def test_member_count(self):
        assert len(PreemptionPolicy) == 5

    def test_values(self):
        expected = {"never", "priority_only", "deadline_critical", "always", "supervisor_approval"}
        assert {m.value for m in PreemptionPolicy} == expected


class TestSchedulingVerdictEnum:
    def test_member_count(self):
        assert len(SchedulingVerdict) == 6

    def test_values(self):
        expected = {"scheduled", "deferred", "preempted", "unschedulable", "escalated", "waiting"}
        assert {m.value for m in SchedulingVerdict} == expected


# ---------------------------------------------------------------------------
# PortfolioDescriptor
# ---------------------------------------------------------------------------


class TestPortfolioDescriptorConstruction:
    def test_valid_construction(self):
        ts = _ts()
        pd = PortfolioDescriptor(
            portfolio_id="pf-1",
            name="Test Portfolio",
            description="A test",
            created_at=ts,
        )
        assert pd.portfolio_id == "pf-1"
        assert pd.name == "Test Portfolio"
        assert pd.status is PortfolioStatus.DRAFT
        assert pd.priority is PortfolioPriority.NORMAL
        assert pd.scheduling_mode is SchedulingMode.PRIORITY
        assert pd.preemption_policy is PreemptionPolicy.PRIORITY_ONLY
        assert pd.max_concurrent == 10

    def test_missing_portfolio_id_raises(self):
        with pytest.raises(ValueError):
            PortfolioDescriptor(name="x", created_at=_ts())

    def test_missing_name_raises(self):
        with pytest.raises(ValueError):
            PortfolioDescriptor(portfolio_id="pf-1", created_at=_ts())

    def test_negative_max_concurrent_raises(self):
        with pytest.raises(ValueError):
            PortfolioDescriptor(portfolio_id="pf-1", name="x", max_concurrent=-1, created_at=_ts())

    def test_invalid_created_at_raises(self):
        with pytest.raises(ValueError):
            PortfolioDescriptor(portfolio_id="pf-1", name="x", created_at="not-a-date")

    def test_empty_created_at_raises(self):
        with pytest.raises(ValueError):
            PortfolioDescriptor(portfolio_id="pf-1", name="x", created_at="")

    def test_all_enum_fields_accept_correct_types(self):
        pd = PortfolioDescriptor(
            portfolio_id="pf-2",
            name="Full",
            status=PortfolioStatus.ACTIVE,
            priority=PortfolioPriority.CRITICAL,
            scheduling_mode=SchedulingMode.SLA,
            preemption_policy=PreemptionPolicy.ALWAYS,
            created_at=_ts(),
        )
        assert pd.status is PortfolioStatus.ACTIVE
        assert pd.priority is PortfolioPriority.CRITICAL


class TestPortfolioDescriptorFrozen:
    def test_cannot_mutate_name(self):
        pd = PortfolioDescriptor(portfolio_id="pf-1", name="x", created_at=_ts())
        with pytest.raises((TypeError, AttributeError)):
            pd.name = "changed"  # type: ignore[misc]

    def test_cannot_mutate_status(self):
        pd = PortfolioDescriptor(portfolio_id="pf-1", name="x", created_at=_ts())
        with pytest.raises((TypeError, AttributeError)):
            pd.status = PortfolioStatus.ACTIVE  # type: ignore[misc]


class TestPortfolioDescriptorFreezeValue:
    def test_campaign_ids_frozen_to_tuple(self):
        pd = PortfolioDescriptor(
            portfolio_id="pf-1", name="x",
            campaign_ids=["c1", "c2"],
            created_at=_ts(),
        )
        assert isinstance(pd.campaign_ids, tuple)
        assert pd.campaign_ids == ("c1", "c2")

    def test_tags_frozen_to_tuple(self):
        pd = PortfolioDescriptor(
            portfolio_id="pf-1", name="x",
            tags=["a", "b"],
            created_at=_ts(),
        )
        assert isinstance(pd.tags, tuple)

    def test_metadata_frozen_to_mapping_proxy(self):
        pd = PortfolioDescriptor(
            portfolio_id="pf-1", name="x",
            metadata={"key": "val"},
            created_at=_ts(),
        )
        assert isinstance(pd.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            pd.metadata["new"] = "fail"  # type: ignore[index]


class TestPortfolioDescriptorSerialization:
    def test_to_dict_preserves_enum_objects(self):
        pd = PortfolioDescriptor(
            portfolio_id="pf-1", name="x",
            status=PortfolioStatus.ACTIVE,
            created_at=_ts(),
        )
        d = pd.to_dict()
        # Enums are preserved as enum objects, not converted to .value strings
        assert d["status"] is PortfolioStatus.ACTIVE

    def test_to_dict_thaws_tuples_to_lists(self):
        pd = PortfolioDescriptor(
            portfolio_id="pf-1", name="x",
            campaign_ids=("c1",),
            created_at=_ts(),
        )
        d = pd.to_dict()
        assert isinstance(d["campaign_ids"], list)

    def test_to_dict_thaws_metadata_to_dict(self):
        pd = PortfolioDescriptor(
            portfolio_id="pf-1", name="x",
            metadata={"a": 1},
            created_at=_ts(),
        )
        d = pd.to_dict()
        assert isinstance(d["metadata"], dict)


# ---------------------------------------------------------------------------
# CampaignReservation
# ---------------------------------------------------------------------------


class TestCampaignReservationConstruction:
    def test_valid(self):
        cr = CampaignReservation(
            reservation_id="r1", portfolio_id="pf-1", campaign_id="c1",
            created_at=_ts(),
        )
        assert cr.reservation_id == "r1"
        assert cr.preemptible is True
        assert cr.waiting_on_human is False
        assert cr.scheduled is False
        assert cr.deferred is False

    def test_missing_reservation_id_raises(self):
        with pytest.raises(ValueError):
            CampaignReservation(portfolio_id="pf-1", campaign_id="c1", created_at=_ts())

    def test_missing_portfolio_id_raises(self):
        with pytest.raises(ValueError):
            CampaignReservation(reservation_id="r1", campaign_id="c1", created_at=_ts())

    def test_missing_campaign_id_raises(self):
        with pytest.raises(ValueError):
            CampaignReservation(reservation_id="r1", portfolio_id="pf-1", created_at=_ts())

    def test_negative_sla_seconds_raises(self):
        with pytest.raises(ValueError):
            CampaignReservation(
                reservation_id="r1", portfolio_id="pf-1", campaign_id="c1",
                sla_seconds=-1, created_at=_ts(),
            )

    def test_invalid_created_at_raises(self):
        with pytest.raises(ValueError):
            CampaignReservation(
                reservation_id="r1", portfolio_id="pf-1", campaign_id="c1",
                created_at="bad",
            )


class TestCampaignReservationFrozen:
    def test_cannot_mutate(self):
        cr = CampaignReservation(
            reservation_id="r1", portfolio_id="pf-1", campaign_id="c1",
            created_at=_ts(),
        )
        with pytest.raises((TypeError, AttributeError)):
            cr.scheduled = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ScheduleWindow
# ---------------------------------------------------------------------------


class TestScheduleWindowConstruction:
    def test_valid(self):
        ts = _ts()
        sw = ScheduleWindow(
            window_id="w1", resource_ref="worker-1",
            resource_class=ResourceClass.HUMAN,
            starts_at=ts, ends_at=ts,
        )
        assert sw.window_id == "w1"
        assert sw.capacity_units == 1
        assert sw.reserved_units == 0

    def test_missing_window_id_raises(self):
        ts = _ts()
        with pytest.raises(ValueError):
            ScheduleWindow(resource_ref="x", starts_at=ts, ends_at=ts)

    def test_invalid_resource_class_raises(self):
        ts = _ts()
        with pytest.raises(ValueError):
            ScheduleWindow(
                window_id="w1", resource_ref="x",
                resource_class="human",  # type: ignore[arg-type]
                starts_at=ts, ends_at=ts,
            )

    def test_negative_capacity_raises(self):
        ts = _ts()
        with pytest.raises(ValueError):
            ScheduleWindow(
                window_id="w1", resource_ref="x",
                starts_at=ts, ends_at=ts,
                capacity_units=-1,
            )


class TestScheduleWindowFrozen:
    def test_cannot_mutate(self):
        ts = _ts()
        sw = ScheduleWindow(
            window_id="w1", resource_ref="x", starts_at=ts, ends_at=ts,
        )
        with pytest.raises((TypeError, AttributeError)):
            sw.capacity_units = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# ResourceReservation
# ---------------------------------------------------------------------------


class TestResourceReservationConstruction:
    def test_valid(self):
        rr = ResourceReservation(
            reservation_id="rr1", portfolio_id="pf-1", campaign_id="c1",
            resource_ref="w-1", created_at=_ts(),
        )
        assert rr.resource_class is ResourceClass.HUMAN
        assert rr.reservation_type is ReservationType.WORKER
        assert rr.active is True

    def test_missing_resource_ref_raises(self):
        with pytest.raises(ValueError):
            ResourceReservation(
                reservation_id="rr1", portfolio_id="pf-1", campaign_id="c1",
                created_at=_ts(),
            )

    def test_invalid_reservation_type_raises(self):
        with pytest.raises(ValueError):
            ResourceReservation(
                reservation_id="rr1", portfolio_id="pf-1", campaign_id="c1",
                resource_ref="w-1", reservation_type="worker",  # type: ignore[arg-type]
                created_at=_ts(),
            )

    def test_negative_units_raises(self):
        with pytest.raises(ValueError):
            ResourceReservation(
                reservation_id="rr1", portfolio_id="pf-1", campaign_id="c1",
                resource_ref="w-1", units_reserved=-5, created_at=_ts(),
            )


class TestResourceReservationFrozen:
    def test_cannot_mutate(self):
        rr = ResourceReservation(
            reservation_id="rr1", portfolio_id="pf-1", campaign_id="c1",
            resource_ref="w-1", created_at=_ts(),
        )
        with pytest.raises((TypeError, AttributeError)):
            rr.active = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# QuotaReservation
# ---------------------------------------------------------------------------


class TestQuotaReservationConstruction:
    def test_valid(self):
        qr = QuotaReservation(
            reservation_id="qr1", portfolio_id="pf-1", campaign_id="c1",
            connector_id="conn-1", quota_units=100, quota_remaining=50,
            created_at=_ts(),
        )
        assert qr.quota_units == 100
        assert qr.quota_remaining == 50
        assert qr.active is True

    def test_missing_connector_id_raises(self):
        with pytest.raises(ValueError):
            QuotaReservation(
                reservation_id="qr1", portfolio_id="pf-1", campaign_id="c1",
                created_at=_ts(),
            )

    def test_negative_quota_units_raises(self):
        with pytest.raises(ValueError):
            QuotaReservation(
                reservation_id="qr1", portfolio_id="pf-1", campaign_id="c1",
                connector_id="conn-1", quota_units=-1, created_at=_ts(),
            )

    def test_negative_quota_remaining_raises(self):
        with pytest.raises(ValueError):
            QuotaReservation(
                reservation_id="qr1", portfolio_id="pf-1", campaign_id="c1",
                connector_id="conn-1", quota_remaining=-1, created_at=_ts(),
            )


class TestQuotaReservationFrozen:
    def test_cannot_mutate(self):
        qr = QuotaReservation(
            reservation_id="qr1", portfolio_id="pf-1", campaign_id="c1",
            connector_id="conn-1", created_at=_ts(),
        )
        with pytest.raises((TypeError, AttributeError)):
            qr.active = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# SchedulingDecision
# ---------------------------------------------------------------------------


class TestSchedulingDecisionConstruction:
    def test_valid(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            verdict=SchedulingVerdict.SCHEDULED,
            decided_at=_ts(),
        )
        assert sd.verdict is SchedulingVerdict.SCHEDULED
        assert sd.priority_score == 0.0

    def test_missing_decision_id_raises(self):
        with pytest.raises(ValueError):
            SchedulingDecision(
                portfolio_id="pf-1", campaign_id="c1", decided_at=_ts(),
            )

    def test_invalid_verdict_raises(self):
        with pytest.raises(ValueError):
            SchedulingDecision(
                decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
                verdict="scheduled",  # type: ignore[arg-type]
                decided_at=_ts(),
            )


class TestSchedulingDecisionFreezeValue:
    def test_resource_reservations_frozen_to_tuple(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            resource_reservations=["rr1", "rr2"],
            decided_at=_ts(),
        )
        assert isinstance(sd.resource_reservations, tuple)
        assert sd.resource_reservations == ("rr1", "rr2")

    def test_quota_reservations_frozen_to_tuple(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            quota_reservations=["qr1"],
            decided_at=_ts(),
        )
        assert isinstance(sd.quota_reservations, tuple)

    def test_metadata_frozen_to_mapping_proxy(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            metadata={"engine": "v2"},
            decided_at=_ts(),
        )
        assert isinstance(sd.metadata, MappingProxyType)


class TestSchedulingDecisionSerialization:
    def test_to_dict_preserves_verdict_enum(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            verdict=SchedulingVerdict.DEFERRED,
            decided_at=_ts(),
        )
        d = sd.to_dict()
        assert d["verdict"] is SchedulingVerdict.DEFERRED

    def test_to_dict_thaws_resource_reservations(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            resource_reservations=("rr1",),
            decided_at=_ts(),
        )
        d = sd.to_dict()
        assert isinstance(d["resource_reservations"], list)

    def test_to_dict_thaws_metadata(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            metadata={"k": "v"},
            decided_at=_ts(),
        )
        d = sd.to_dict()
        assert isinstance(d["metadata"], dict)


class TestSchedulingDecisionFrozen:
    def test_cannot_mutate(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            decided_at=_ts(),
        )
        with pytest.raises((TypeError, AttributeError)):
            sd.verdict = SchedulingVerdict.WAITING  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PreemptionRecord
# ---------------------------------------------------------------------------


class TestPreemptionRecordConstruction:
    def test_valid(self):
        pr = PreemptionRecord(
            preemption_id="pr1", portfolio_id="pf-1",
            preempting_campaign_id="c2", preempted_campaign_id="c1",
            reason="higher priority", priority_delta=5.0,
            preempted_at=_ts(),
        )
        assert pr.priority_delta == 5.0

    def test_missing_preemption_id_raises(self):
        with pytest.raises(ValueError):
            PreemptionRecord(
                portfolio_id="pf-1",
                preempting_campaign_id="c2", preempted_campaign_id="c1",
                preempted_at=_ts(),
            )

    def test_missing_preempting_campaign_raises(self):
        with pytest.raises(ValueError):
            PreemptionRecord(
                preemption_id="pr1", portfolio_id="pf-1",
                preempted_campaign_id="c1",
                preempted_at=_ts(),
            )

    def test_missing_preempted_campaign_raises(self):
        with pytest.raises(ValueError):
            PreemptionRecord(
                preemption_id="pr1", portfolio_id="pf-1",
                preempting_campaign_id="c2",
                preempted_at=_ts(),
            )

    def test_invalid_preempted_at_raises(self):
        with pytest.raises(ValueError):
            PreemptionRecord(
                preemption_id="pr1", portfolio_id="pf-1",
                preempting_campaign_id="c2", preempted_campaign_id="c1",
                preempted_at="nope",
            )


class TestPreemptionRecordFrozen:
    def test_cannot_mutate(self):
        pr = PreemptionRecord(
            preemption_id="pr1", portfolio_id="pf-1",
            preempting_campaign_id="c2", preempted_campaign_id="c1",
            preempted_at=_ts(),
        )
        with pytest.raises((TypeError, AttributeError)):
            pr.reason = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CapacitySnapshot
# ---------------------------------------------------------------------------


class TestCapacitySnapshotConstruction:
    def test_valid(self):
        cs = CapacitySnapshot(
            snapshot_id="snap1", portfolio_id="pf-1",
            total_workers=10, available_workers=5,
            captured_at=_ts(),
        )
        assert cs.total_workers == 10
        assert cs.available_workers == 5
        assert cs.total_teams == 0

    def test_missing_snapshot_id_raises(self):
        with pytest.raises(ValueError):
            CapacitySnapshot(portfolio_id="pf-1", captured_at=_ts())

    def test_negative_int_field_raises(self):
        with pytest.raises(ValueError):
            CapacitySnapshot(
                snapshot_id="snap1", portfolio_id="pf-1",
                total_workers=-1, captured_at=_ts(),
            )

    def test_all_int_fields_validated(self):
        """Each of the 11 int fields rejects negative values."""
        int_fields = [
            "total_workers", "available_workers", "total_teams",
            "available_teams", "total_connectors", "healthy_connectors",
            "total_quota_units", "available_quota_units",
            "active_campaigns", "deferred_campaigns", "blocked_campaigns",
        ]
        for fld in int_fields:
            with pytest.raises(ValueError):
                CapacitySnapshot(
                    snapshot_id="snap1", portfolio_id="pf-1",
                    captured_at=_ts(), **{fld: -1},
                )


class TestCapacitySnapshotFrozen:
    def test_cannot_mutate(self):
        cs = CapacitySnapshot(
            snapshot_id="snap1", portfolio_id="pf-1", captured_at=_ts(),
        )
        with pytest.raises((TypeError, AttributeError)):
            cs.total_workers = 99  # type: ignore[misc]


# ---------------------------------------------------------------------------
# PortfolioHealth
# ---------------------------------------------------------------------------


class TestPortfolioHealthConstruction:
    def test_valid(self):
        ph = PortfolioHealth(
            portfolio_id="pf-1",
            status=PortfolioStatus.ACTIVE,
            utilization=0.75,
            computed_at=_ts(),
        )
        assert ph.utilization == 0.75
        assert ph.status is PortfolioStatus.ACTIVE

    def test_missing_portfolio_id_raises(self):
        with pytest.raises(ValueError):
            PortfolioHealth(computed_at=_ts())

    def test_invalid_status_raises(self):
        with pytest.raises(ValueError):
            PortfolioHealth(
                portfolio_id="pf-1", status="active",  # type: ignore[arg-type]
                computed_at=_ts(),
            )

    def test_utilization_above_1_raises(self):
        with pytest.raises(ValueError):
            PortfolioHealth(
                portfolio_id="pf-1", utilization=1.5, computed_at=_ts(),
            )

    def test_utilization_below_0_raises(self):
        with pytest.raises(ValueError):
            PortfolioHealth(
                portfolio_id="pf-1", utilization=-0.1, computed_at=_ts(),
            )

    def test_utilization_boundary_0(self):
        ph = PortfolioHealth(portfolio_id="pf-1", utilization=0.0, computed_at=_ts())
        assert ph.utilization == 0.0

    def test_utilization_boundary_1(self):
        ph = PortfolioHealth(portfolio_id="pf-1", utilization=1.0, computed_at=_ts())
        assert ph.utilization == 1.0

    def test_negative_int_field_raises(self):
        with pytest.raises(ValueError):
            PortfolioHealth(
                portfolio_id="pf-1", total_campaigns=-1, computed_at=_ts(),
            )


class TestPortfolioHealthFrozen:
    def test_cannot_mutate(self):
        ph = PortfolioHealth(portfolio_id="pf-1", computed_at=_ts())
        with pytest.raises((TypeError, AttributeError)):
            ph.utilization = 0.5  # type: ignore[misc]


class TestPortfolioHealthSerialization:
    def test_to_dict_preserves_status_enum(self):
        ph = PortfolioHealth(portfolio_id="pf-1", computed_at=_ts())
        d = ph.to_dict()
        assert d["status"] is PortfolioStatus.ACTIVE


# ---------------------------------------------------------------------------
# PortfolioClosureReport
# ---------------------------------------------------------------------------


class TestPortfolioClosureReportConstruction:
    def test_valid(self):
        pcr = PortfolioClosureReport(
            report_id="rpt1", portfolio_id="pf-1",
            total_campaigns=10, completed_campaigns=8,
            failed_campaigns=1, deferred_campaigns=1,
            summary="Done",
            created_at=_ts(),
        )
        assert pcr.total_campaigns == 10
        assert pcr.completed_campaigns == 8

    def test_missing_report_id_raises(self):
        with pytest.raises(ValueError):
            PortfolioClosureReport(portfolio_id="pf-1", created_at=_ts())

    def test_missing_portfolio_id_raises(self):
        with pytest.raises(ValueError):
            PortfolioClosureReport(report_id="rpt1", created_at=_ts())

    def test_negative_int_field_raises(self):
        with pytest.raises(ValueError):
            PortfolioClosureReport(
                report_id="rpt1", portfolio_id="pf-1",
                total_campaigns=-1, created_at=_ts(),
            )

    def test_all_int_fields_validated(self):
        int_fields = [
            "total_campaigns", "completed_campaigns", "failed_campaigns",
            "deferred_campaigns", "preempted_campaigns",
            "total_scheduling_decisions", "total_preemptions",
            "total_resource_reservations", "total_quota_reservations",
        ]
        for fld in int_fields:
            with pytest.raises(ValueError):
                PortfolioClosureReport(
                    report_id="rpt1", portfolio_id="pf-1",
                    created_at=_ts(), **{fld: -1},
                )


class TestPortfolioClosureReportFrozen:
    def test_cannot_mutate(self):
        pcr = PortfolioClosureReport(
            report_id="rpt1", portfolio_id="pf-1", created_at=_ts(),
        )
        with pytest.raises((TypeError, AttributeError)):
            pcr.summary = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Cross-cutting: to_json round-trip (does not crash)
# ---------------------------------------------------------------------------


class TestToDictSmokeTests:
    """Verify that to_dict() produces correct dicts for representative records."""

    def test_portfolio_descriptor_to_dict(self):
        pd = PortfolioDescriptor(
            portfolio_id="pf-1", name="x", created_at=_ts(),
        )
        d = pd.to_dict()
        assert d["portfolio_id"] == "pf-1"
        # to_dict preserves enum objects
        assert d["status"] == PortfolioStatus.DRAFT

    def test_scheduling_decision_to_dict(self):
        sd = SchedulingDecision(
            decision_id="d1", portfolio_id="pf-1", campaign_id="c1",
            decided_at=_ts(),
        )
        d = sd.to_dict()
        assert d["decision_id"] == "d1"
        assert d["verdict"] == SchedulingVerdict.SCHEDULED

    def test_capacity_snapshot_to_dict(self):
        cs = CapacitySnapshot(
            snapshot_id="snap1", portfolio_id="pf-1", captured_at=_ts(),
        )
        d = cs.to_dict()
        assert d["snapshot_id"] == "snap1"
        assert isinstance(d["total_workers"], int)


# ---------------------------------------------------------------------------
# Edge-case validation tests
# ---------------------------------------------------------------------------


class TestEdgeCaseValidation:
    def test_whitespace_only_text_rejected(self):
        with pytest.raises(ValueError):
            PortfolioDescriptor(portfolio_id="   ", name="x", created_at=_ts())

    def test_bool_rejected_for_non_negative_int(self):
        """bool is a subclass of int but should be rejected by require_non_negative_int."""
        with pytest.raises(ValueError):
            PortfolioDescriptor(
                portfolio_id="pf-1", name="x", max_concurrent=True, created_at=_ts(),
            )

    def test_bool_rejected_for_utilization(self):
        """bool should be rejected by require_unit_float."""
        with pytest.raises(ValueError):
            PortfolioHealth(
                portfolio_id="pf-1", utilization=True, computed_at=_ts(),  # type: ignore[arg-type]
            )

    def test_campaign_reservation_bool_field_type_check(self):
        """Non-bool values for boolean fields are rejected."""
        with pytest.raises(ValueError):
            CampaignReservation(
                reservation_id="r1", portfolio_id="pf-1", campaign_id="c1",
                preemptible=1,  # type: ignore[arg-type]
                created_at=_ts(),
            )

    def test_resource_reservation_active_bool_check(self):
        with pytest.raises(ValueError):
            ResourceReservation(
                reservation_id="rr1", portfolio_id="pf-1", campaign_id="c1",
                resource_ref="w-1", active=1,  # type: ignore[arg-type]
                created_at=_ts(),
            )

    def test_quota_reservation_active_bool_check(self):
        with pytest.raises(ValueError):
            QuotaReservation(
                reservation_id="qr1", portfolio_id="pf-1", campaign_id="c1",
                connector_id="conn-1", active=1,  # type: ignore[arg-type]
                created_at=_ts(),
            )
