"""Comprehensive tests for workforce_runtime contracts.

Covers all 6 enums (membership counts, value strings), all 10 frozen
dataclasses (valid construction, frozen immutability, to_dict, field
validators, metadata freezing, boundary values).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.workforce_runtime import (
    AssignmentDecision,
    AssignmentDisposition,
    AssignmentRequest,
    CapacityStatus,
    CoverageGap,
    CoverageStatus,
    EscalationMode,
    LoadBand,
    LoadSnapshot,
    RoleCapacityRecord,
    TeamCapacityRecord,
    WorkerRecord,
    WorkerStatus,
    WorkforceAssessment,
    WorkforceClosureReport,
    WorkforceViolation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

NOW = datetime.now(timezone.utc).isoformat()


def _worker(**overrides):
    defaults = dict(
        worker_id="w1", tenant_id="t1", role_ref="r1", team_ref="tm1",
        display_name="Alice", status=WorkerStatus.ACTIVE,
        max_assignments=5, current_assignments=2, created_at=NOW,
        metadata={"k": "v"},
    )
    defaults.update(overrides)
    return WorkerRecord(**defaults)


def _role_capacity(**overrides):
    defaults = dict(
        capacity_id="rc1", tenant_id="t1", role_ref="r1",
        total_workers=10, available_workers=8, total_capacity=100,
        used_capacity=40, utilization=0.4, status=CapacityStatus.NOMINAL,
        assessed_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return RoleCapacityRecord(**defaults)


def _team_capacity(**overrides):
    defaults = dict(
        capacity_id="tc1", tenant_id="t1", team_ref="tm1",
        total_members=6, available_members=5, total_capacity=60,
        used_capacity=20, utilization=0.33, status=CapacityStatus.NOMINAL,
        assessed_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return TeamCapacityRecord(**defaults)


def _assignment_request(**overrides):
    defaults = dict(
        request_id="ar1", tenant_id="t1", scope_ref_id="s1",
        role_ref="r1", priority=3, source_type="manual",
        requested_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return AssignmentRequest(**defaults)


def _assignment_decision(**overrides):
    defaults = dict(
        decision_id="ad1", request_id="ar1", worker_id="w1",
        disposition=AssignmentDisposition.ASSIGNED, reason="best fit",
        decided_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return AssignmentDecision(**defaults)


def _coverage_gap(**overrides):
    defaults = dict(
        gap_id="cg1", tenant_id="t1", role_ref="r1", team_ref="tm1",
        status=CoverageStatus.GAP, available_workers=1,
        required_workers=3, escalation_mode=EscalationMode.MANAGER,
        detected_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return CoverageGap(**defaults)


def _load_snapshot(**overrides):
    defaults = dict(
        snapshot_id="ls1", tenant_id="t1", total_workers=20,
        active_workers=15, total_assignments=50, total_capacity=200,
        used_capacity=80, utilization=0.4, load_band=LoadBand.MODERATE,
        captured_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return LoadSnapshot(**defaults)


def _workforce_assessment(**overrides):
    defaults = dict(
        assessment_id="wa1", tenant_id="t1", total_workers=30,
        active_workers=25, total_roles=5, total_teams=3,
        total_requests=100, total_decisions=95, total_gaps=2,
        total_violations=1, assessed_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return WorkforceAssessment(**defaults)


def _workforce_violation(**overrides):
    defaults = dict(
        violation_id="wv1", tenant_id="t1", operation="assign",
        reason="over capacity", detected_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return WorkforceViolation(**defaults)


def _workforce_closure(**overrides):
    defaults = dict(
        report_id="wcr1", tenant_id="t1", total_workers=30,
        total_role_capacities=5, total_team_capacities=3,
        total_requests=100, total_decisions=95, total_gaps=2,
        total_violations=1, closed_at=NOW, metadata={},
    )
    defaults.update(overrides)
    return WorkforceClosureReport(**defaults)


# ===================================================================
# 1. Enum membership counts and .value strings
# ===================================================================

class TestWorkerStatusEnum:
    def test_member_count(self):
        assert len(WorkerStatus) == 5

    @pytest.mark.parametrize("member,value", [
        (WorkerStatus.ACTIVE, "active"),
        (WorkerStatus.ON_LEAVE, "on_leave"),
        (WorkerStatus.UNAVAILABLE, "unavailable"),
        (WorkerStatus.SUSPENDED, "suspended"),
        (WorkerStatus.OFFBOARDED, "offboarded"),
    ])
    def test_values(self, member, value):
        assert member.value == value


class TestCapacityStatusEnum:
    def test_member_count(self):
        assert len(CapacityStatus) == 5

    @pytest.mark.parametrize("member,value", [
        (CapacityStatus.NOMINAL, "nominal"),
        (CapacityStatus.STRAINED, "strained"),
        (CapacityStatus.OVERLOADED, "overloaded"),
        (CapacityStatus.CRITICAL, "critical"),
        (CapacityStatus.EMPTY, "empty"),
    ])
    def test_values(self, member, value):
        assert member.value == value


class TestAssignmentDispositionEnum:
    def test_member_count(self):
        assert len(AssignmentDisposition) == 4

    @pytest.mark.parametrize("member,value", [
        (AssignmentDisposition.ASSIGNED, "assigned"),
        (AssignmentDisposition.DEFERRED, "deferred"),
        (AssignmentDisposition.REJECTED, "rejected"),
        (AssignmentDisposition.ESCALATED, "escalated"),
    ])
    def test_values(self, member, value):
        assert member.value == value


class TestEscalationModeEnum:
    def test_member_count(self):
        assert len(EscalationMode) == 4

    @pytest.mark.parametrize("member,value", [
        (EscalationMode.MANAGER, "manager"),
        (EscalationMode.BACKUP, "backup"),
        (EscalationMode.POOL, "pool"),
        (EscalationMode.EXTERNAL, "external"),
    ])
    def test_values(self, member, value):
        assert member.value == value


class TestLoadBandEnum:
    def test_member_count(self):
        assert len(LoadBand) == 5

    @pytest.mark.parametrize("member,value", [
        (LoadBand.IDLE, "idle"),
        (LoadBand.LOW, "low"),
        (LoadBand.MODERATE, "moderate"),
        (LoadBand.HIGH, "high"),
        (LoadBand.OVERLOADED, "overloaded"),
    ])
    def test_values(self, member, value):
        assert member.value == value


class TestCoverageStatusEnum:
    def test_member_count(self):
        assert len(CoverageStatus) == 4

    @pytest.mark.parametrize("member,value", [
        (CoverageStatus.COVERED, "covered"),
        (CoverageStatus.PARTIAL, "partial"),
        (CoverageStatus.GAP, "gap"),
        (CoverageStatus.CRITICAL_GAP, "critical_gap"),
    ])
    def test_values(self, member, value):
        assert member.value == value


# ===================================================================
# 2. Valid construction
# ===================================================================

class TestWorkerRecordConstruction:
    def test_valid(self):
        rec = _worker()
        assert rec.worker_id == "w1"
        assert rec.tenant_id == "t1"
        assert rec.role_ref == "r1"
        assert rec.team_ref == "tm1"
        assert rec.display_name == "Alice"
        assert rec.status is WorkerStatus.ACTIVE
        assert rec.max_assignments == 5
        assert rec.current_assignments == 2
        assert rec.created_at == NOW

    def test_all_worker_statuses(self):
        for s in WorkerStatus:
            rec = _worker(status=s)
            assert rec.status is s

    def test_min_valid_assignments(self):
        rec = _worker(max_assignments=1, current_assignments=0)
        assert rec.max_assignments == 1
        assert rec.current_assignments == 0


class TestRoleCapacityRecordConstruction:
    def test_valid(self):
        rec = _role_capacity()
        assert rec.capacity_id == "rc1"
        assert rec.utilization == pytest.approx(0.4)
        assert rec.status is CapacityStatus.NOMINAL

    def test_all_capacity_statuses(self):
        for s in CapacityStatus:
            rec = _role_capacity(status=s)
            assert rec.status is s

    def test_zero_utilization(self):
        rec = _role_capacity(utilization=0.0)
        assert rec.utilization == 0.0

    def test_full_utilization(self):
        rec = _role_capacity(utilization=1.0)
        assert rec.utilization == 1.0


class TestTeamCapacityRecordConstruction:
    def test_valid(self):
        rec = _team_capacity()
        assert rec.capacity_id == "tc1"
        assert rec.team_ref == "tm1"
        assert rec.status is CapacityStatus.NOMINAL

    def test_all_capacity_statuses(self):
        for s in CapacityStatus:
            rec = _team_capacity(status=s)
            assert rec.status is s


class TestAssignmentRequestConstruction:
    def test_valid(self):
        rec = _assignment_request()
        assert rec.request_id == "ar1"
        assert rec.priority == 3
        assert rec.source_type == "manual"

    def test_min_priority(self):
        rec = _assignment_request(priority=1)
        assert rec.priority == 1


class TestAssignmentDecisionConstruction:
    def test_valid(self):
        rec = _assignment_decision()
        assert rec.decision_id == "ad1"
        assert rec.disposition is AssignmentDisposition.ASSIGNED
        assert rec.reason == "best fit"

    def test_empty_reason_allowed(self):
        rec = _assignment_decision(reason="")
        assert rec.reason == ""

    def test_all_dispositions(self):
        for d in AssignmentDisposition:
            rec = _assignment_decision(disposition=d)
            assert rec.disposition is d


class TestCoverageGapConstruction:
    def test_valid(self):
        rec = _coverage_gap()
        assert rec.gap_id == "cg1"
        assert rec.status is CoverageStatus.GAP
        assert rec.escalation_mode is EscalationMode.MANAGER

    def test_all_coverage_statuses(self):
        for s in CoverageStatus:
            rec = _coverage_gap(status=s)
            assert rec.status is s

    def test_all_escalation_modes(self):
        for m in EscalationMode:
            rec = _coverage_gap(escalation_mode=m)
            assert rec.escalation_mode is m


class TestLoadSnapshotConstruction:
    def test_valid(self):
        rec = _load_snapshot()
        assert rec.snapshot_id == "ls1"
        assert rec.load_band is LoadBand.MODERATE

    def test_all_load_bands(self):
        for lb in LoadBand:
            rec = _load_snapshot(load_band=lb)
            assert rec.load_band is lb


class TestWorkforceAssessmentConstruction:
    def test_valid(self):
        rec = _workforce_assessment()
        assert rec.assessment_id == "wa1"
        assert rec.total_workers == 30
        assert rec.total_violations == 1


class TestWorkforceViolationConstruction:
    def test_valid(self):
        rec = _workforce_violation()
        assert rec.violation_id == "wv1"
        assert rec.operation == "assign"
        assert rec.reason == "over capacity"


class TestWorkforceClosureReportConstruction:
    def test_valid(self):
        rec = _workforce_closure()
        assert rec.report_id == "wcr1"
        assert rec.total_workers == 30
        assert rec.total_violations == 1


# ===================================================================
# 3. Frozen immutability
# ===================================================================

class TestFrozenImmutability:
    def test_worker_record_frozen(self):
        rec = _worker()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.worker_id = "other"

    def test_role_capacity_frozen(self):
        rec = _role_capacity()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.capacity_id = "other"

    def test_team_capacity_frozen(self):
        rec = _team_capacity()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.capacity_id = "other"

    def test_assignment_request_frozen(self):
        rec = _assignment_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.request_id = "other"

    def test_assignment_decision_frozen(self):
        rec = _assignment_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.decision_id = "other"

    def test_coverage_gap_frozen(self):
        rec = _coverage_gap()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.gap_id = "other"

    def test_load_snapshot_frozen(self):
        rec = _load_snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.snapshot_id = "other"

    def test_workforce_assessment_frozen(self):
        rec = _workforce_assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.assessment_id = "other"

    def test_workforce_violation_frozen(self):
        rec = _workforce_violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.violation_id = "other"

    def test_workforce_closure_frozen(self):
        rec = _workforce_closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.report_id = "other"

    # Additional frozen fields per dataclass
    def test_worker_frozen_status(self):
        rec = _worker()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.status = WorkerStatus.SUSPENDED

    def test_role_capacity_frozen_utilization(self):
        rec = _role_capacity()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.utilization = 0.9

    def test_team_capacity_frozen_team_ref(self):
        rec = _team_capacity()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.team_ref = "other"

    def test_assignment_request_frozen_priority(self):
        rec = _assignment_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.priority = 10

    def test_assignment_decision_frozen_disposition(self):
        rec = _assignment_decision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.disposition = AssignmentDisposition.REJECTED

    def test_coverage_gap_frozen_escalation(self):
        rec = _coverage_gap()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.escalation_mode = EscalationMode.EXTERNAL

    def test_load_snapshot_frozen_load_band(self):
        rec = _load_snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.load_band = LoadBand.HIGH

    def test_workforce_assessment_frozen_total_gaps(self):
        rec = _workforce_assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.total_gaps = 99

    def test_workforce_violation_frozen_reason(self):
        rec = _workforce_violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.reason = "different"

    def test_workforce_closure_frozen_total_requests(self):
        rec = _workforce_closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rec.total_requests = 999


# ===================================================================
# 4. to_dict returns dict, preserves enum objects
# ===================================================================

class TestToDictWorkerRecord:
    def test_returns_dict(self):
        d = _worker().to_dict()
        assert isinstance(d, dict)

    def test_preserves_enum(self):
        d = _worker().to_dict()
        assert d["status"] is WorkerStatus.ACTIVE

    def test_has_all_fields(self):
        d = _worker().to_dict()
        field_names = {f.name for f in dataclasses.fields(WorkerRecord)}
        assert set(d.keys()) == field_names


class TestToDictRoleCapacity:
    def test_returns_dict(self):
        assert isinstance(_role_capacity().to_dict(), dict)

    def test_preserves_enum(self):
        d = _role_capacity().to_dict()
        assert d["status"] is CapacityStatus.NOMINAL


class TestToDictTeamCapacity:
    def test_returns_dict(self):
        assert isinstance(_team_capacity().to_dict(), dict)

    def test_preserves_enum(self):
        d = _team_capacity().to_dict()
        assert d["status"] is CapacityStatus.NOMINAL


class TestToDictAssignmentRequest:
    def test_returns_dict(self):
        assert isinstance(_assignment_request().to_dict(), dict)

    def test_has_all_fields(self):
        d = _assignment_request().to_dict()
        field_names = {f.name for f in dataclasses.fields(AssignmentRequest)}
        assert set(d.keys()) == field_names


class TestToDictAssignmentDecision:
    def test_returns_dict(self):
        assert isinstance(_assignment_decision().to_dict(), dict)

    def test_preserves_enum(self):
        d = _assignment_decision().to_dict()
        assert d["disposition"] is AssignmentDisposition.ASSIGNED


class TestToDictCoverageGap:
    def test_returns_dict(self):
        assert isinstance(_coverage_gap().to_dict(), dict)

    def test_preserves_status_enum(self):
        d = _coverage_gap().to_dict()
        assert d["status"] is CoverageStatus.GAP

    def test_preserves_escalation_enum(self):
        d = _coverage_gap().to_dict()
        assert d["escalation_mode"] is EscalationMode.MANAGER


class TestToDictLoadSnapshot:
    def test_returns_dict(self):
        assert isinstance(_load_snapshot().to_dict(), dict)

    def test_preserves_enum(self):
        d = _load_snapshot().to_dict()
        assert d["load_band"] is LoadBand.MODERATE


class TestToDictWorkforceAssessment:
    def test_returns_dict(self):
        assert isinstance(_workforce_assessment().to_dict(), dict)

    def test_has_all_fields(self):
        d = _workforce_assessment().to_dict()
        field_names = {f.name for f in dataclasses.fields(WorkforceAssessment)}
        assert set(d.keys()) == field_names


class TestToDictWorkforceViolation:
    def test_returns_dict(self):
        assert isinstance(_workforce_violation().to_dict(), dict)


class TestToDictWorkforceClosureReport:
    def test_returns_dict(self):
        assert isinstance(_workforce_closure().to_dict(), dict)

    def test_has_all_fields(self):
        d = _workforce_closure().to_dict()
        field_names = {f.name for f in dataclasses.fields(WorkforceClosureReport)}
        assert set(d.keys()) == field_names


# ===================================================================
# 5. Field validators
# ===================================================================

# -- WorkerRecord validators --

class TestWorkerRecordValidators:
    @pytest.mark.parametrize("field_name", [
        "worker_id", "tenant_id", "role_ref", "team_ref", "display_name",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _worker(**{field_name: ""})

    @pytest.mark.parametrize("field_name", [
        "worker_id", "tenant_id", "role_ref", "team_ref", "display_name",
    ])
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            _worker(**{field_name: "   "})

    def test_max_assignments_zero_rejected(self):
        with pytest.raises(ValueError):
            _worker(max_assignments=0)

    def test_max_assignments_negative_rejected(self):
        with pytest.raises(ValueError):
            _worker(max_assignments=-1)

    def test_current_assignments_negative_rejected(self):
        with pytest.raises(ValueError):
            _worker(current_assignments=-1)

    def test_current_assignments_zero_accepted(self):
        rec = _worker(current_assignments=0)
        assert rec.current_assignments == 0

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _worker(created_at="not-a-date")


# -- RoleCapacityRecord validators --

class TestRoleCapacityValidators:
    @pytest.mark.parametrize("field_name", [
        "capacity_id", "tenant_id", "role_ref",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _role_capacity(**{field_name: ""})

    @pytest.mark.parametrize("int_field", [
        "total_workers", "available_workers", "total_capacity", "used_capacity",
    ])
    def test_negative_int_rejected(self, int_field):
        with pytest.raises(ValueError):
            _role_capacity(**{int_field: -1})

    @pytest.mark.parametrize("int_field", [
        "total_workers", "available_workers", "total_capacity", "used_capacity",
    ])
    def test_zero_int_accepted(self, int_field):
        rec = _role_capacity(**{int_field: 0})
        assert getattr(rec, int_field) == 0

    def test_utilization_negative_rejected(self):
        with pytest.raises(ValueError):
            _role_capacity(utilization=-0.1)

    def test_utilization_above_one_rejected(self):
        with pytest.raises(ValueError):
            _role_capacity(utilization=1.1)

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _role_capacity(assessed_at="nope")


# -- TeamCapacityRecord validators --

class TestTeamCapacityValidators:
    @pytest.mark.parametrize("field_name", [
        "capacity_id", "tenant_id", "team_ref",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _team_capacity(**{field_name: ""})

    @pytest.mark.parametrize("int_field", [
        "total_members", "available_members", "total_capacity", "used_capacity",
    ])
    def test_negative_int_rejected(self, int_field):
        with pytest.raises(ValueError):
            _team_capacity(**{int_field: -1})

    @pytest.mark.parametrize("int_field", [
        "total_members", "available_members", "total_capacity", "used_capacity",
    ])
    def test_zero_int_accepted(self, int_field):
        rec = _team_capacity(**{int_field: 0})
        assert getattr(rec, int_field) == 0

    def test_utilization_negative_rejected(self):
        with pytest.raises(ValueError):
            _team_capacity(utilization=-0.1)

    def test_utilization_above_one_rejected(self):
        with pytest.raises(ValueError):
            _team_capacity(utilization=1.1)

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _team_capacity(assessed_at="xyz")


# -- AssignmentRequest validators --

class TestAssignmentRequestValidators:
    @pytest.mark.parametrize("field_name", [
        "request_id", "tenant_id", "scope_ref_id", "role_ref", "source_type",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _assignment_request(**{field_name: ""})

    def test_priority_zero_rejected(self):
        with pytest.raises(ValueError):
            _assignment_request(priority=0)

    def test_priority_negative_rejected(self):
        with pytest.raises(ValueError):
            _assignment_request(priority=-1)

    def test_priority_one_accepted(self):
        rec = _assignment_request(priority=1)
        assert rec.priority == 1

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _assignment_request(requested_at="bad")


# -- AssignmentDecision validators --

class TestAssignmentDecisionValidators:
    @pytest.mark.parametrize("field_name", [
        "decision_id", "request_id", "worker_id",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _assignment_decision(**{field_name: ""})

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _assignment_decision(decided_at="bad")


# -- CoverageGap validators --

class TestCoverageGapValidators:
    @pytest.mark.parametrize("field_name", [
        "gap_id", "tenant_id", "role_ref", "team_ref",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _coverage_gap(**{field_name: ""})

    def test_available_workers_negative_rejected(self):
        with pytest.raises(ValueError):
            _coverage_gap(available_workers=-1)

    def test_available_workers_zero_accepted(self):
        rec = _coverage_gap(available_workers=0)
        assert rec.available_workers == 0

    def test_required_workers_zero_rejected(self):
        with pytest.raises(ValueError):
            _coverage_gap(required_workers=0)

    def test_required_workers_negative_rejected(self):
        with pytest.raises(ValueError):
            _coverage_gap(required_workers=-1)

    def test_required_workers_one_accepted(self):
        rec = _coverage_gap(required_workers=1)
        assert rec.required_workers == 1

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _coverage_gap(detected_at="bad")


# -- LoadSnapshot validators --

class TestLoadSnapshotValidators:
    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _load_snapshot(**{field_name: ""})

    @pytest.mark.parametrize("int_field", [
        "total_workers", "active_workers", "total_assignments",
        "total_capacity", "used_capacity",
    ])
    def test_negative_int_rejected(self, int_field):
        with pytest.raises(ValueError):
            _load_snapshot(**{int_field: -1})

    @pytest.mark.parametrize("int_field", [
        "total_workers", "active_workers", "total_assignments",
        "total_capacity", "used_capacity",
    ])
    def test_zero_int_accepted(self, int_field):
        rec = _load_snapshot(**{int_field: 0})
        assert getattr(rec, int_field) == 0

    def test_utilization_negative_rejected(self):
        with pytest.raises(ValueError):
            _load_snapshot(utilization=-0.1)

    def test_utilization_above_one_rejected(self):
        with pytest.raises(ValueError):
            _load_snapshot(utilization=1.1)

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _load_snapshot(captured_at="nope")


# -- WorkforceAssessment validators --

class TestWorkforceAssessmentValidators:
    @pytest.mark.parametrize("field_name", ["assessment_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _workforce_assessment(**{field_name: ""})

    @pytest.mark.parametrize("int_field", [
        "total_workers", "active_workers", "total_roles", "total_teams",
        "total_requests", "total_decisions", "total_gaps", "total_violations",
    ])
    def test_negative_int_rejected(self, int_field):
        with pytest.raises(ValueError):
            _workforce_assessment(**{int_field: -1})

    @pytest.mark.parametrize("int_field", [
        "total_workers", "active_workers", "total_roles", "total_teams",
        "total_requests", "total_decisions", "total_gaps", "total_violations",
    ])
    def test_zero_int_accepted(self, int_field):
        rec = _workforce_assessment(**{int_field: 0})
        assert getattr(rec, int_field) == 0

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _workforce_assessment(assessed_at="bad")


# -- WorkforceViolation validators --

class TestWorkforceViolationValidators:
    @pytest.mark.parametrize("field_name", [
        "violation_id", "tenant_id", "operation", "reason",
    ])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _workforce_violation(**{field_name: ""})

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _workforce_violation(detected_at="bad")


# -- WorkforceClosureReport validators --

class TestWorkforceClosureReportValidators:
    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            _workforce_closure(**{field_name: ""})

    @pytest.mark.parametrize("int_field", [
        "total_workers", "total_role_capacities", "total_team_capacities",
        "total_requests", "total_decisions", "total_gaps", "total_violations",
    ])
    def test_negative_int_rejected(self, int_field):
        with pytest.raises(ValueError):
            _workforce_closure(**{int_field: -1})

    @pytest.mark.parametrize("int_field", [
        "total_workers", "total_role_capacities", "total_team_capacities",
        "total_requests", "total_decisions", "total_gaps", "total_violations",
    ])
    def test_zero_int_accepted(self, int_field):
        rec = _workforce_closure(**{int_field: 0})
        assert getattr(rec, int_field) == 0

    def test_bad_datetime_rejected(self):
        with pytest.raises(ValueError):
            _workforce_closure(closed_at="bad")


# ===================================================================
# 6. Metadata freezing (MappingProxyType)
# ===================================================================

class TestMetadataFreezing:
    def test_worker_metadata_frozen(self):
        rec = _worker(metadata={"a": 1})
        assert isinstance(rec.metadata, MappingProxyType)
        assert rec.metadata["a"] == 1
        with pytest.raises(TypeError):
            rec.metadata["b"] = 2  # type: ignore[index]

    def test_role_capacity_metadata_frozen(self):
        rec = _role_capacity(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_team_capacity_metadata_frozen(self):
        rec = _team_capacity(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_assignment_request_metadata_frozen(self):
        rec = _assignment_request(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_assignment_decision_metadata_frozen(self):
        rec = _assignment_decision(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_coverage_gap_metadata_frozen(self):
        rec = _coverage_gap(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_load_snapshot_metadata_frozen(self):
        rec = _load_snapshot(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_workforce_assessment_metadata_frozen(self):
        rec = _workforce_assessment(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_workforce_violation_metadata_frozen(self):
        rec = _workforce_violation(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_workforce_closure_metadata_frozen(self):
        rec = _workforce_closure(metadata={"x": "y"})
        assert isinstance(rec.metadata, MappingProxyType)

    def test_nested_metadata_frozen(self):
        rec = _worker(metadata={"outer": {"inner": 42}})
        assert isinstance(rec.metadata["outer"], MappingProxyType)
        assert rec.metadata["outer"]["inner"] == 42

    def test_empty_metadata_frozen(self):
        rec = _worker(metadata={})
        assert isinstance(rec.metadata, MappingProxyType)
        assert len(rec.metadata) == 0

    def test_metadata_thawed_in_to_dict(self):
        rec = _worker(metadata={"a": 1})
        d = rec.to_dict()
        assert isinstance(d["metadata"], dict)
        assert d["metadata"]["a"] == 1

    def test_original_dict_not_mutated(self):
        original = {"key": "val"}
        rec = _worker(metadata=original)
        original["key"] = "changed"
        assert rec.metadata["key"] == "val"


# ===================================================================
# 7. Parametrized boundary values
# ===================================================================

# -- Non-negative int boundaries --

class TestNonNegativeIntBoundaries:
    @pytest.mark.parametrize("cls,factory,field_name", [
        ("RoleCapacityRecord", _role_capacity, "total_workers"),
        ("RoleCapacityRecord", _role_capacity, "available_workers"),
        ("RoleCapacityRecord", _role_capacity, "total_capacity"),
        ("RoleCapacityRecord", _role_capacity, "used_capacity"),
        ("TeamCapacityRecord", _team_capacity, "total_members"),
        ("TeamCapacityRecord", _team_capacity, "available_members"),
        ("TeamCapacityRecord", _team_capacity, "total_capacity"),
        ("TeamCapacityRecord", _team_capacity, "used_capacity"),
        ("LoadSnapshot", _load_snapshot, "total_workers"),
        ("LoadSnapshot", _load_snapshot, "active_workers"),
        ("LoadSnapshot", _load_snapshot, "total_assignments"),
        ("LoadSnapshot", _load_snapshot, "total_capacity"),
        ("LoadSnapshot", _load_snapshot, "used_capacity"),
        ("WorkforceAssessment", _workforce_assessment, "total_workers"),
        ("WorkforceAssessment", _workforce_assessment, "active_workers"),
        ("WorkforceAssessment", _workforce_assessment, "total_roles"),
        ("WorkforceAssessment", _workforce_assessment, "total_teams"),
        ("WorkforceAssessment", _workforce_assessment, "total_requests"),
        ("WorkforceAssessment", _workforce_assessment, "total_decisions"),
        ("WorkforceAssessment", _workforce_assessment, "total_gaps"),
        ("WorkforceAssessment", _workforce_assessment, "total_violations"),
        ("WorkforceClosureReport", _workforce_closure, "total_workers"),
        ("WorkforceClosureReport", _workforce_closure, "total_role_capacities"),
        ("WorkforceClosureReport", _workforce_closure, "total_team_capacities"),
        ("WorkforceClosureReport", _workforce_closure, "total_requests"),
        ("WorkforceClosureReport", _workforce_closure, "total_decisions"),
        ("WorkforceClosureReport", _workforce_closure, "total_gaps"),
        ("WorkforceClosureReport", _workforce_closure, "total_violations"),
        ("CoverageGap", _coverage_gap, "available_workers"),
        ("WorkerRecord", _worker, "current_assignments"),
    ], ids=lambda x: f"{x}" if isinstance(x, str) else "")
    def test_zero_accepted(self, cls, factory, field_name):
        rec = factory(**{field_name: 0})
        assert getattr(rec, field_name) == 0

    @pytest.mark.parametrize("cls,factory,field_name", [
        ("RoleCapacityRecord", _role_capacity, "total_workers"),
        ("RoleCapacityRecord", _role_capacity, "available_workers"),
        ("RoleCapacityRecord", _role_capacity, "total_capacity"),
        ("RoleCapacityRecord", _role_capacity, "used_capacity"),
        ("TeamCapacityRecord", _team_capacity, "total_members"),
        ("TeamCapacityRecord", _team_capacity, "available_members"),
        ("TeamCapacityRecord", _team_capacity, "total_capacity"),
        ("TeamCapacityRecord", _team_capacity, "used_capacity"),
        ("LoadSnapshot", _load_snapshot, "total_workers"),
        ("LoadSnapshot", _load_snapshot, "active_workers"),
        ("LoadSnapshot", _load_snapshot, "total_assignments"),
        ("LoadSnapshot", _load_snapshot, "total_capacity"),
        ("LoadSnapshot", _load_snapshot, "used_capacity"),
        ("WorkforceAssessment", _workforce_assessment, "total_workers"),
        ("WorkforceAssessment", _workforce_assessment, "active_workers"),
        ("WorkforceAssessment", _workforce_assessment, "total_roles"),
        ("WorkforceAssessment", _workforce_assessment, "total_teams"),
        ("WorkforceAssessment", _workforce_assessment, "total_requests"),
        ("WorkforceAssessment", _workforce_assessment, "total_decisions"),
        ("WorkforceAssessment", _workforce_assessment, "total_gaps"),
        ("WorkforceAssessment", _workforce_assessment, "total_violations"),
        ("WorkforceClosureReport", _workforce_closure, "total_workers"),
        ("WorkforceClosureReport", _workforce_closure, "total_role_capacities"),
        ("WorkforceClosureReport", _workforce_closure, "total_team_capacities"),
        ("WorkforceClosureReport", _workforce_closure, "total_requests"),
        ("WorkforceClosureReport", _workforce_closure, "total_decisions"),
        ("WorkforceClosureReport", _workforce_closure, "total_gaps"),
        ("WorkforceClosureReport", _workforce_closure, "total_violations"),
        ("CoverageGap", _coverage_gap, "available_workers"),
        ("WorkerRecord", _worker, "current_assignments"),
    ], ids=lambda x: f"{x}" if isinstance(x, str) else "")
    def test_minus_one_rejected(self, cls, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: -1})

    @pytest.mark.parametrize("cls,factory,field_name", [
        ("RoleCapacityRecord", _role_capacity, "total_workers"),
        ("TeamCapacityRecord", _team_capacity, "total_members"),
        ("LoadSnapshot", _load_snapshot, "total_workers"),
        ("WorkforceAssessment", _workforce_assessment, "total_workers"),
        ("WorkforceClosureReport", _workforce_closure, "total_workers"),
        ("CoverageGap", _coverage_gap, "available_workers"),
        ("WorkerRecord", _worker, "current_assignments"),
    ], ids=lambda x: f"{x}" if isinstance(x, str) else "")
    def test_one_accepted(self, cls, factory, field_name):
        rec = factory(**{field_name: 1})
        assert getattr(rec, field_name) == 1


# -- Positive int boundaries --

class TestPositiveIntBoundaries:
    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "max_assignments"),
        (_assignment_request, "priority"),
        (_coverage_gap, "required_workers"),
    ])
    def test_one_accepted(self, factory, field_name):
        rec = factory(**{field_name: 1})
        assert getattr(rec, field_name) == 1

    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "max_assignments"),
        (_assignment_request, "priority"),
        (_coverage_gap, "required_workers"),
    ])
    def test_zero_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: 0})

    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "max_assignments"),
        (_assignment_request, "priority"),
        (_coverage_gap, "required_workers"),
    ])
    def test_minus_one_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: -1})

    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "max_assignments"),
        (_assignment_request, "priority"),
        (_coverage_gap, "required_workers"),
    ])
    def test_large_value_accepted(self, factory, field_name):
        rec = factory(**{field_name: 9999})
        assert getattr(rec, field_name) == 9999


# -- Unit float boundaries --

class TestUnitFloatBoundaries:
    @pytest.mark.parametrize("factory,field_name", [
        (_role_capacity, "utilization"),
        (_team_capacity, "utilization"),
        (_load_snapshot, "utilization"),
    ])
    def test_zero_accepted(self, factory, field_name):
        rec = factory(**{field_name: 0.0})
        assert getattr(rec, field_name) == 0.0

    @pytest.mark.parametrize("factory,field_name", [
        (_role_capacity, "utilization"),
        (_team_capacity, "utilization"),
        (_load_snapshot, "utilization"),
    ])
    def test_one_accepted(self, factory, field_name):
        rec = factory(**{field_name: 1.0})
        assert getattr(rec, field_name) == 1.0

    @pytest.mark.parametrize("factory,field_name", [
        (_role_capacity, "utilization"),
        (_team_capacity, "utilization"),
        (_load_snapshot, "utilization"),
    ])
    def test_half_accepted(self, factory, field_name):
        rec = factory(**{field_name: 0.5})
        assert getattr(rec, field_name) == pytest.approx(0.5)

    @pytest.mark.parametrize("factory,field_name", [
        (_role_capacity, "utilization"),
        (_team_capacity, "utilization"),
        (_load_snapshot, "utilization"),
    ])
    def test_negative_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: -0.1})

    @pytest.mark.parametrize("factory,field_name", [
        (_role_capacity, "utilization"),
        (_team_capacity, "utilization"),
        (_load_snapshot, "utilization"),
    ])
    def test_above_one_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: 1.1})

    @pytest.mark.parametrize("factory,field_name", [
        (_role_capacity, "utilization"),
        (_team_capacity, "utilization"),
        (_load_snapshot, "utilization"),
    ])
    def test_negative_one_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: -1.0})

    @pytest.mark.parametrize("factory,field_name", [
        (_role_capacity, "utilization"),
        (_team_capacity, "utilization"),
        (_load_snapshot, "utilization"),
    ])
    def test_two_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: 2.0})


# -- datetime text boundaries --

class TestDatetimeTextBoundaries:
    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "created_at"),
        (_role_capacity, "assessed_at"),
        (_team_capacity, "assessed_at"),
        (_assignment_request, "requested_at"),
        (_assignment_decision, "decided_at"),
        (_coverage_gap, "detected_at"),
        (_load_snapshot, "captured_at"),
        (_workforce_assessment, "assessed_at"),
        (_workforce_violation, "detected_at"),
        (_workforce_closure, "closed_at"),
    ])
    def test_valid_iso_datetime_accepted(self, factory, field_name):
        ts = datetime.now(timezone.utc).isoformat()
        rec = factory(**{field_name: ts})
        assert getattr(rec, field_name) == ts

    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "created_at"),
        (_role_capacity, "assessed_at"),
        (_team_capacity, "assessed_at"),
        (_assignment_request, "requested_at"),
        (_assignment_decision, "decided_at"),
        (_coverage_gap, "detected_at"),
        (_load_snapshot, "captured_at"),
        (_workforce_assessment, "assessed_at"),
        (_workforce_violation, "detected_at"),
        (_workforce_closure, "closed_at"),
    ])
    def test_empty_datetime_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: ""})

    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "created_at"),
        (_role_capacity, "assessed_at"),
        (_team_capacity, "assessed_at"),
        (_assignment_request, "requested_at"),
        (_assignment_decision, "decided_at"),
        (_coverage_gap, "detected_at"),
        (_load_snapshot, "captured_at"),
        (_workforce_assessment, "assessed_at"),
        (_workforce_violation, "detected_at"),
        (_workforce_closure, "closed_at"),
    ])
    def test_garbage_datetime_rejected(self, factory, field_name):
        with pytest.raises(ValueError):
            factory(**{field_name: "not-a-date"})

    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "created_at"),
        (_role_capacity, "assessed_at"),
    ])
    def test_zulu_suffix_accepted(self, factory, field_name):
        ts = "2025-06-15T10:30:00Z"
        rec = factory(**{field_name: ts})
        assert getattr(rec, field_name) == ts

    @pytest.mark.parametrize("factory,field_name", [
        (_worker, "created_at"),
        (_role_capacity, "assessed_at"),
    ])
    def test_offset_accepted(self, factory, field_name):
        ts = "2025-06-15T10:30:00+05:30"
        rec = factory(**{field_name: ts})
        assert getattr(rec, field_name) == ts
