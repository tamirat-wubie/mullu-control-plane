"""Tests for continuity runtime contracts.

Governance scope: comprehensive coverage for all enums, dataclasses,
validation rules, immutability invariants, metadata freezing, and
serialization in the continuity_runtime contract module.
"""

import math
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.continuity_runtime import (
    ContinuityClosureReport,
    ContinuityPlan,
    ContinuityScope,
    ContinuitySnapshot,
    ContinuityStatus,
    ContinuityViolation,
    DisruptionEvent,
    DisruptionSeverity,
    FailoverDisposition,
    FailoverRecord,
    RecoveryExecution,
    RecoveryObjective,
    RecoveryPlan,
    RecoveryStatus,
    RecoveryVerificationStatus,
    VerificationRecord,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = "2025-06-01T12:00:00+00:00"
_LATER = "2025-06-02T08:00:00+00:00"


def _plan(**overrides) -> ContinuityPlan:
    defaults = dict(
        plan_id="plan-001",
        name="DR Plan Alpha",
        tenant_id="tenant-1",
        scope=ContinuityScope.SERVICE,
        status=ContinuityStatus.DRAFT,
        scope_ref_id="svc-ref-1",
        rto_minutes=30,
        rpo_minutes=15,
        failover_target_ref="target-1",
        owner_ref="owner-1",
        created_at=_NOW,
    )
    defaults.update(overrides)
    return ContinuityPlan(**defaults)


def _recovery_plan(**overrides) -> RecoveryPlan:
    defaults = dict(
        recovery_plan_id="rp-001",
        plan_id="plan-001",
        name="Recovery Alpha",
        tenant_id="tenant-1",
        status=RecoveryStatus.PENDING,
        priority=1,
        description="Primary recovery plan",
        created_at=_NOW,
    )
    defaults.update(overrides)
    return RecoveryPlan(**defaults)


def _failover(**overrides) -> FailoverRecord:
    defaults = dict(
        failover_id="fo-001",
        plan_id="plan-001",
        disruption_id="dis-001",
        disposition=FailoverDisposition.INITIATED,
        source_ref="src-1",
        target_ref="tgt-1",
        initiated_at=_NOW,
        completed_at="",
    )
    defaults.update(overrides)
    return FailoverRecord(**defaults)


def _disruption(**overrides) -> DisruptionEvent:
    defaults = dict(
        disruption_id="dis-001",
        tenant_id="tenant-1",
        scope=ContinuityScope.SERVICE,
        scope_ref_id="svc-ref-1",
        severity=DisruptionSeverity.MEDIUM,
        description="Service outage",
        detected_at=_NOW,
        resolved_at="",
    )
    defaults.update(overrides)
    return DisruptionEvent(**defaults)


def _objective(**overrides) -> RecoveryObjective:
    defaults = dict(
        objective_id="obj-001",
        plan_id="plan-001",
        name="RTO Target",
        target_minutes=30,
        actual_minutes=25,
        met=True,
        evaluated_at=_NOW,
    )
    defaults.update(overrides)
    return RecoveryObjective(**defaults)


def _execution(**overrides) -> RecoveryExecution:
    defaults = dict(
        execution_id="exec-001",
        recovery_plan_id="rp-001",
        disruption_id="dis-001",
        status=RecoveryStatus.IN_PROGRESS,
        executed_by="operator-1",
        started_at=_NOW,
        completed_at="",
    )
    defaults.update(overrides)
    return RecoveryExecution(**defaults)


def _verification(**overrides) -> VerificationRecord:
    defaults = dict(
        verification_id="ver-001",
        execution_id="exec-001",
        status=RecoveryVerificationStatus.PENDING,
        verified_by="verifier-1",
        confidence=0.95,
        reason="All checks passed",
        verified_at=_NOW,
    )
    defaults.update(overrides)
    return VerificationRecord(**defaults)


def _snapshot(**overrides) -> ContinuitySnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        total_plans=5,
        total_active_plans=3,
        total_recovery_plans=2,
        total_disruptions=1,
        total_failovers=1,
        total_recoveries=1,
        total_verifications=1,
        total_violations=0,
        total_objectives=4,
        captured_at=_NOW,
    )
    defaults.update(overrides)
    return ContinuitySnapshot(**defaults)


def _violation(**overrides) -> ContinuityViolation:
    defaults = dict(
        violation_id="vio-001",
        plan_id="plan-001",
        tenant_id="tenant-1",
        operation="reopen_completed_recovery",
        reason="Completed recoveries cannot be re-opened",
        detected_at=_NOW,
    )
    defaults.update(overrides)
    return ContinuityViolation(**defaults)


def _closure(**overrides) -> ContinuityClosureReport:
    defaults = dict(
        report_id="rpt-001",
        tenant_id="tenant-1",
        total_plans=5,
        total_disruptions=2,
        total_failovers=1,
        total_recoveries=2,
        total_verifications_passed=3,
        total_verifications_failed=0,
        total_violations=1,
        closed_at=_NOW,
    )
    defaults.update(overrides)
    return ContinuityClosureReport(**defaults)


# ===================================================================
# Enum coverage
# ===================================================================


class TestContinuityStatus:
    def test_active_value(self):
        assert ContinuityStatus.ACTIVE.value == "active"

    def test_draft_value(self):
        assert ContinuityStatus.DRAFT.value == "draft"

    def test_activated_value(self):
        assert ContinuityStatus.ACTIVATED.value == "activated"

    def test_suspended_value(self):
        assert ContinuityStatus.SUSPENDED.value == "suspended"

    def test_retired_value(self):
        assert ContinuityStatus.RETIRED.value == "retired"

    def test_member_count(self):
        assert len(ContinuityStatus) == 5

    def test_all_members_are_instances(self):
        for member in ContinuityStatus:
            assert isinstance(member, ContinuityStatus)

    def test_lookup_by_value(self):
        assert ContinuityStatus("active") is ContinuityStatus.ACTIVE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ContinuityStatus("nonexistent")


class TestRecoveryStatus:
    def test_pending_value(self):
        assert RecoveryStatus.PENDING.value == "pending"

    def test_in_progress_value(self):
        assert RecoveryStatus.IN_PROGRESS.value == "in_progress"

    def test_completed_value(self):
        assert RecoveryStatus.COMPLETED.value == "completed"

    def test_failed_value(self):
        assert RecoveryStatus.FAILED.value == "failed"

    def test_cancelled_value(self):
        assert RecoveryStatus.CANCELLED.value == "cancelled"

    def test_member_count(self):
        assert len(RecoveryStatus) == 5

    def test_all_members_are_instances(self):
        for member in RecoveryStatus:
            assert isinstance(member, RecoveryStatus)

    def test_lookup_by_value(self):
        assert RecoveryStatus("in_progress") is RecoveryStatus.IN_PROGRESS

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            RecoveryStatus("unknown")


class TestDisruptionSeverity:
    def test_low_value(self):
        assert DisruptionSeverity.LOW.value == "low"

    def test_medium_value(self):
        assert DisruptionSeverity.MEDIUM.value == "medium"

    def test_high_value(self):
        assert DisruptionSeverity.HIGH.value == "high"

    def test_critical_value(self):
        assert DisruptionSeverity.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(DisruptionSeverity) == 4

    def test_all_members_are_instances(self):
        for member in DisruptionSeverity:
            assert isinstance(member, DisruptionSeverity)

    def test_lookup_by_value(self):
        assert DisruptionSeverity("critical") is DisruptionSeverity.CRITICAL

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            DisruptionSeverity("extreme")


class TestContinuityScope:
    def test_environment_value(self):
        assert ContinuityScope.ENVIRONMENT.value == "environment"

    def test_service_value(self):
        assert ContinuityScope.SERVICE.value == "service"

    def test_connector_value(self):
        assert ContinuityScope.CONNECTOR.value == "connector"

    def test_asset_value(self):
        assert ContinuityScope.ASSET.value == "asset"

    def test_workspace_value(self):
        assert ContinuityScope.WORKSPACE.value == "workspace"

    def test_tenant_value(self):
        assert ContinuityScope.TENANT.value == "tenant"

    def test_member_count(self):
        assert len(ContinuityScope) == 6

    def test_all_members_are_instances(self):
        for member in ContinuityScope:
            assert isinstance(member, ContinuityScope)

    def test_lookup_by_value(self):
        assert ContinuityScope("workspace") is ContinuityScope.WORKSPACE

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            ContinuityScope("cluster")


class TestFailoverDisposition:
    def test_initiated_value(self):
        assert FailoverDisposition.INITIATED.value == "initiated"

    def test_completed_value(self):
        assert FailoverDisposition.COMPLETED.value == "completed"

    def test_failed_value(self):
        assert FailoverDisposition.FAILED.value == "failed"

    def test_rolled_back_value(self):
        assert FailoverDisposition.ROLLED_BACK.value == "rolled_back"

    def test_member_count(self):
        assert len(FailoverDisposition) == 4

    def test_all_members_are_instances(self):
        for member in FailoverDisposition:
            assert isinstance(member, FailoverDisposition)

    def test_lookup_by_value(self):
        assert FailoverDisposition("rolled_back") is FailoverDisposition.ROLLED_BACK

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            FailoverDisposition("aborted")


class TestRecoveryVerificationStatus:
    def test_pending_value(self):
        assert RecoveryVerificationStatus.PENDING.value == "pending"

    def test_passed_value(self):
        assert RecoveryVerificationStatus.PASSED.value == "passed"

    def test_failed_value(self):
        assert RecoveryVerificationStatus.FAILED.value == "failed"

    def test_skipped_value(self):
        assert RecoveryVerificationStatus.SKIPPED.value == "skipped"

    def test_member_count(self):
        assert len(RecoveryVerificationStatus) == 4

    def test_all_members_are_instances(self):
        for member in RecoveryVerificationStatus:
            assert isinstance(member, RecoveryVerificationStatus)

    def test_lookup_by_value(self):
        assert RecoveryVerificationStatus("skipped") is RecoveryVerificationStatus.SKIPPED

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            RecoveryVerificationStatus("deferred")


# ===================================================================
# ContinuityPlan
# ===================================================================


class TestContinuityPlanConstruction:
    def test_valid_construction(self):
        p = _plan()
        assert p.plan_id == "plan-001"
        assert p.name == "DR Plan Alpha"
        assert p.tenant_id == "tenant-1"
        assert p.scope is ContinuityScope.SERVICE
        assert p.status is ContinuityStatus.DRAFT
        assert p.rto_minutes == 30
        assert p.rpo_minutes == 15

    def test_all_scopes_accepted(self):
        for scope in ContinuityScope:
            p = _plan(scope=scope)
            assert p.scope is scope

    def test_all_statuses_accepted(self):
        for status in ContinuityStatus:
            p = _plan(status=status)
            assert p.status is status

    def test_zero_rto_accepted(self):
        p = _plan(rto_minutes=0)
        assert p.rto_minutes == 0

    def test_zero_rpo_accepted(self):
        p = _plan(rpo_minutes=0)
        assert p.rpo_minutes == 0

    def test_date_only_accepted(self):
        p = _plan(created_at="2025-06-01")
        assert p.created_at == "2025-06-01"

    def test_datetime_with_z_accepted(self):
        p = _plan(created_at="2025-06-01T12:00:00Z")
        assert p.created_at == "2025-06-01T12:00:00Z"


class TestContinuityPlanValidation:
    def test_empty_plan_id_rejected(self):
        with pytest.raises(ValueError, match="plan_id"):
            _plan(plan_id="")

    def test_whitespace_plan_id_rejected(self):
        with pytest.raises(ValueError, match="plan_id"):
            _plan(plan_id="   ")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _plan(name="")

    def test_whitespace_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _plan(name="  \t  ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _plan(tenant_id="")

    def test_invalid_scope_string_rejected(self):
        with pytest.raises(ValueError, match="scope"):
            _plan(scope="global")  # type: ignore[arg-type]

    def test_invalid_scope_int_rejected(self):
        with pytest.raises(ValueError, match="scope"):
            _plan(scope=42)  # type: ignore[arg-type]

    def test_invalid_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _plan(status="running")  # type: ignore[arg-type]

    def test_invalid_status_int_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _plan(status=0)  # type: ignore[arg-type]

    def test_negative_rto_rejected(self):
        with pytest.raises(ValueError, match="rto_minutes"):
            _plan(rto_minutes=-1)

    def test_negative_rpo_rejected(self):
        with pytest.raises(ValueError, match="rpo_minutes"):
            _plan(rpo_minutes=-5)

    def test_float_rto_rejected(self):
        with pytest.raises(ValueError, match="rto_minutes"):
            _plan(rto_minutes=1.5)  # type: ignore[arg-type]

    def test_float_rpo_rejected(self):
        with pytest.raises(ValueError, match="rpo_minutes"):
            _plan(rpo_minutes=2.5)  # type: ignore[arg-type]

    def test_bool_rto_rejected(self):
        with pytest.raises(ValueError, match="rto_minutes"):
            _plan(rto_minutes=True)  # type: ignore[arg-type]

    def test_bool_rpo_rejected(self):
        with pytest.raises(ValueError, match="rpo_minutes"):
            _plan(rpo_minutes=False)  # type: ignore[arg-type]

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _plan(created_at="not-a-date")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _plan(created_at="")


class TestContinuityPlanFrozen:
    def test_cannot_set_plan_id(self):
        p = _plan()
        with pytest.raises(AttributeError):
            p.plan_id = "other"  # type: ignore[misc]

    def test_cannot_set_name(self):
        p = _plan()
        with pytest.raises(AttributeError):
            p.name = "other"  # type: ignore[misc]

    def test_cannot_set_rto(self):
        p = _plan()
        with pytest.raises(AttributeError):
            p.rto_minutes = 999  # type: ignore[misc]

    def test_cannot_set_status(self):
        p = _plan()
        with pytest.raises(AttributeError):
            p.status = ContinuityStatus.ACTIVE  # type: ignore[misc]


class TestContinuityPlanMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        p = _plan()
        assert isinstance(p.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        p = _plan(metadata={"key": "value"})
        assert p.metadata["key"] == "value"
        with pytest.raises(TypeError):
            p.metadata["new"] = "x"  # type: ignore[index]

    def test_nested_metadata_frozen(self):
        p = _plan(metadata={"nested": {"a": 1}})
        assert isinstance(p.metadata["nested"], MappingProxyType)

    def test_list_in_metadata_becomes_tuple(self):
        p = _plan(metadata={"items": [1, 2, 3]})
        assert isinstance(p.metadata["items"], tuple)
        assert p.metadata["items"] == (1, 2, 3)


class TestContinuityPlanSerialization:
    def test_to_dict_returns_dict(self):
        d = _plan().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _plan().to_dict()
        expected = {
            "plan_id", "name", "tenant_id", "scope", "status",
            "scope_ref_id", "rto_minutes", "rpo_minutes",
            "failover_target_ref", "owner_ref", "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_preserves_enum(self):
        d = _plan().to_dict()
        assert d["scope"] is ContinuityScope.SERVICE
        assert d["status"] is ContinuityStatus.DRAFT


    def test_to_dict_metadata_thawed(self):
        d = _plan(metadata={"k": [1, 2]}).to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["k"], list)


# ===================================================================
# RecoveryPlan
# ===================================================================


class TestRecoveryPlanConstruction:
    def test_valid_construction(self):
        rp = _recovery_plan()
        assert rp.recovery_plan_id == "rp-001"
        assert rp.plan_id == "plan-001"
        assert rp.name == "Recovery Alpha"
        assert rp.tenant_id == "tenant-1"
        assert rp.status is RecoveryStatus.PENDING
        assert rp.priority == 1

    def test_all_statuses_accepted(self):
        for status in RecoveryStatus:
            rp = _recovery_plan(status=status)
            assert rp.status is status

    def test_zero_priority_accepted(self):
        rp = _recovery_plan(priority=0)
        assert rp.priority == 0

    def test_date_only_accepted(self):
        rp = _recovery_plan(created_at="2025-06-01")
        assert rp.created_at == "2025-06-01"


class TestRecoveryPlanValidation:
    def test_empty_recovery_plan_id_rejected(self):
        with pytest.raises(ValueError, match="recovery_plan_id"):
            _recovery_plan(recovery_plan_id="")

    def test_empty_plan_id_rejected(self):
        with pytest.raises(ValueError, match="plan_id"):
            _recovery_plan(plan_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _recovery_plan(name="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _recovery_plan(tenant_id="")

    def test_invalid_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _recovery_plan(status="active")  # type: ignore[arg-type]

    def test_negative_priority_rejected(self):
        with pytest.raises(ValueError, match="priority"):
            _recovery_plan(priority=-1)

    def test_float_priority_rejected(self):
        with pytest.raises(ValueError, match="priority"):
            _recovery_plan(priority=1.5)  # type: ignore[arg-type]

    def test_bool_priority_rejected(self):
        with pytest.raises(ValueError, match="priority"):
            _recovery_plan(priority=True)  # type: ignore[arg-type]

    def test_invalid_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _recovery_plan(created_at="bad-date")

    def test_empty_created_at_rejected(self):
        with pytest.raises(ValueError, match="created_at"):
            _recovery_plan(created_at="")

    def test_whitespace_recovery_plan_id_rejected(self):
        with pytest.raises(ValueError, match="recovery_plan_id"):
            _recovery_plan(recovery_plan_id="   ")

    def test_whitespace_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _recovery_plan(name="  \t")


class TestRecoveryPlanFrozen:
    def test_cannot_set_recovery_plan_id(self):
        rp = _recovery_plan()
        with pytest.raises(AttributeError):
            rp.recovery_plan_id = "other"  # type: ignore[misc]

    def test_cannot_set_priority(self):
        rp = _recovery_plan()
        with pytest.raises(AttributeError):
            rp.priority = 99  # type: ignore[misc]


class TestRecoveryPlanMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        rp = _recovery_plan()
        assert isinstance(rp.metadata, MappingProxyType)

    def test_metadata_frozen_immutable(self):
        rp = _recovery_plan(metadata={"x": 1})
        with pytest.raises(TypeError):
            rp.metadata["y"] = 2  # type: ignore[index]

    def test_list_in_metadata_becomes_tuple(self):
        rp = _recovery_plan(metadata={"items": [10, 20]})
        assert isinstance(rp.metadata["items"], tuple)


class TestRecoveryPlanSerialization:
    def test_to_dict_returns_dict(self):
        d = _recovery_plan().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _recovery_plan().to_dict()
        expected = {
            "recovery_plan_id", "plan_id", "name", "tenant_id",
            "status", "priority", "description", "created_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_preserves_enum(self):
        d = _recovery_plan().to_dict()
        assert d["status"] is RecoveryStatus.PENDING


# ===================================================================
# FailoverRecord
# ===================================================================


class TestFailoverRecordConstruction:
    def test_valid_construction(self):
        fo = _failover()
        assert fo.failover_id == "fo-001"
        assert fo.plan_id == "plan-001"
        assert fo.disruption_id == "dis-001"
        assert fo.disposition is FailoverDisposition.INITIATED
        assert fo.completed_at == ""

    def test_all_dispositions_accepted(self):
        for disp in FailoverDisposition:
            fo = _failover(disposition=disp)
            assert fo.disposition is disp

    def test_completed_at_optional_empty(self):
        fo = _failover(completed_at="")
        assert fo.completed_at == ""

    def test_completed_at_with_valid_date(self):
        fo = _failover(completed_at=_LATER)
        assert fo.completed_at == _LATER

    def test_completed_at_date_only(self):
        fo = _failover(completed_at="2025-06-02")
        assert fo.completed_at == "2025-06-02"


class TestFailoverRecordValidation:
    def test_empty_failover_id_rejected(self):
        with pytest.raises(ValueError, match="failover_id"):
            _failover(failover_id="")

    def test_empty_plan_id_rejected(self):
        with pytest.raises(ValueError, match="plan_id"):
            _failover(plan_id="")

    def test_empty_disruption_id_rejected(self):
        with pytest.raises(ValueError, match="disruption_id"):
            _failover(disruption_id="")

    def test_invalid_disposition_string_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _failover(disposition="cancelled")  # type: ignore[arg-type]

    def test_invalid_disposition_int_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _failover(disposition=1)  # type: ignore[arg-type]

    def test_invalid_initiated_at_rejected(self):
        with pytest.raises(ValueError, match="initiated_at"):
            _failover(initiated_at="bad-date")

    def test_empty_initiated_at_rejected(self):
        with pytest.raises(ValueError, match="initiated_at"):
            _failover(initiated_at="")

    def test_invalid_completed_at_rejected(self):
        with pytest.raises(ValueError, match="completed_at"):
            _failover(completed_at="bad-date")

    def test_whitespace_failover_id_rejected(self):
        with pytest.raises(ValueError, match="failover_id"):
            _failover(failover_id="  ")


class TestFailoverRecordFrozen:
    def test_cannot_set_failover_id(self):
        fo = _failover()
        with pytest.raises(AttributeError):
            fo.failover_id = "other"  # type: ignore[misc]

    def test_cannot_set_disposition(self):
        fo = _failover()
        with pytest.raises(AttributeError):
            fo.disposition = FailoverDisposition.COMPLETED  # type: ignore[misc]


class TestFailoverRecordMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        fo = _failover()
        assert isinstance(fo.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        fo = _failover(metadata={"a": "b"})
        with pytest.raises(TypeError):
            fo.metadata["c"] = "d"  # type: ignore[index]


class TestFailoverRecordSerialization:
    def test_to_dict_returns_dict(self):
        d = _failover().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _failover().to_dict()
        expected = {
            "failover_id", "plan_id", "disruption_id", "disposition",
            "source_ref", "target_ref", "initiated_at", "completed_at",
            "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_preserves_enum(self):
        d = _failover().to_dict()
        assert d["disposition"] is FailoverDisposition.INITIATED


# ===================================================================
# DisruptionEvent
# ===================================================================


class TestDisruptionEventConstruction:
    def test_valid_construction(self):
        de = _disruption()
        assert de.disruption_id == "dis-001"
        assert de.tenant_id == "tenant-1"
        assert de.scope is ContinuityScope.SERVICE
        assert de.severity is DisruptionSeverity.MEDIUM
        assert de.resolved_at == ""

    def test_all_scopes_accepted(self):
        for scope in ContinuityScope:
            de = _disruption(scope=scope)
            assert de.scope is scope

    def test_all_severities_accepted(self):
        for sev in DisruptionSeverity:
            de = _disruption(severity=sev)
            assert de.severity is sev

    def test_resolved_at_optional_empty(self):
        de = _disruption(resolved_at="")
        assert de.resolved_at == ""

    def test_resolved_at_with_valid_date(self):
        de = _disruption(resolved_at=_LATER)
        assert de.resolved_at == _LATER

    def test_resolved_at_date_only(self):
        de = _disruption(resolved_at="2025-06-02")
        assert de.resolved_at == "2025-06-02"


class TestDisruptionEventValidation:
    def test_empty_disruption_id_rejected(self):
        with pytest.raises(ValueError, match="disruption_id"):
            _disruption(disruption_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _disruption(tenant_id="")

    def test_invalid_scope_string_rejected(self):
        with pytest.raises(ValueError, match="scope"):
            _disruption(scope="region")  # type: ignore[arg-type]

    def test_invalid_severity_string_rejected(self):
        with pytest.raises(ValueError, match="severity"):
            _disruption(severity="extreme")  # type: ignore[arg-type]

    def test_invalid_severity_int_rejected(self):
        with pytest.raises(ValueError, match="severity"):
            _disruption(severity=5)  # type: ignore[arg-type]

    def test_invalid_detected_at_rejected(self):
        with pytest.raises(ValueError, match="detected_at"):
            _disruption(detected_at="not-valid")

    def test_empty_detected_at_rejected(self):
        with pytest.raises(ValueError, match="detected_at"):
            _disruption(detected_at="")

    def test_invalid_resolved_at_rejected(self):
        with pytest.raises(ValueError, match="resolved_at"):
            _disruption(resolved_at="bad-date")

    def test_whitespace_disruption_id_rejected(self):
        with pytest.raises(ValueError, match="disruption_id"):
            _disruption(disruption_id="  \t")

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _disruption(tenant_id="  ")


class TestDisruptionEventFrozen:
    def test_cannot_set_disruption_id(self):
        de = _disruption()
        with pytest.raises(AttributeError):
            de.disruption_id = "other"  # type: ignore[misc]

    def test_cannot_set_severity(self):
        de = _disruption()
        with pytest.raises(AttributeError):
            de.severity = DisruptionSeverity.CRITICAL  # type: ignore[misc]

    def test_cannot_set_scope(self):
        de = _disruption()
        with pytest.raises(AttributeError):
            de.scope = ContinuityScope.TENANT  # type: ignore[misc]


class TestDisruptionEventMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        de = _disruption()
        assert isinstance(de.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        de = _disruption(metadata={"x": 1})
        with pytest.raises(TypeError):
            de.metadata["y"] = 2  # type: ignore[index]

    def test_list_in_metadata_becomes_tuple(self):
        de = _disruption(metadata={"tags": ["a", "b"]})
        assert isinstance(de.metadata["tags"], tuple)


class TestDisruptionEventSerialization:
    def test_to_dict_returns_dict(self):
        d = _disruption().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _disruption().to_dict()
        expected = {
            "disruption_id", "tenant_id", "scope", "scope_ref_id",
            "severity", "description", "detected_at", "resolved_at",
            "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_preserves_enums(self):
        d = _disruption().to_dict()
        assert d["scope"] is ContinuityScope.SERVICE
        assert d["severity"] is DisruptionSeverity.MEDIUM


# ===================================================================
# RecoveryObjective
# ===================================================================


class TestRecoveryObjectiveConstruction:
    def test_valid_construction(self):
        obj = _objective()
        assert obj.objective_id == "obj-001"
        assert obj.plan_id == "plan-001"
        assert obj.name == "RTO Target"
        assert obj.target_minutes == 30
        assert obj.actual_minutes == 25
        assert obj.met is True

    def test_met_false(self):
        obj = _objective(met=False)
        assert obj.met is False

    def test_zero_target_minutes(self):
        obj = _objective(target_minutes=0)
        assert obj.target_minutes == 0

    def test_zero_actual_minutes(self):
        obj = _objective(actual_minutes=0)
        assert obj.actual_minutes == 0

    def test_date_only_accepted(self):
        obj = _objective(evaluated_at="2025-06-01")
        assert obj.evaluated_at == "2025-06-01"


class TestRecoveryObjectiveValidation:
    def test_empty_objective_id_rejected(self):
        with pytest.raises(ValueError, match="objective_id"):
            _objective(objective_id="")

    def test_empty_plan_id_rejected(self):
        with pytest.raises(ValueError, match="plan_id"):
            _objective(plan_id="")

    def test_empty_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _objective(name="")

    def test_negative_target_minutes_rejected(self):
        with pytest.raises(ValueError, match="target_minutes"):
            _objective(target_minutes=-1)

    def test_negative_actual_minutes_rejected(self):
        with pytest.raises(ValueError, match="actual_minutes"):
            _objective(actual_minutes=-10)

    def test_float_target_minutes_rejected(self):
        with pytest.raises(ValueError, match="target_minutes"):
            _objective(target_minutes=1.5)  # type: ignore[arg-type]

    def test_float_actual_minutes_rejected(self):
        with pytest.raises(ValueError, match="actual_minutes"):
            _objective(actual_minutes=2.5)  # type: ignore[arg-type]

    def test_bool_target_minutes_rejected(self):
        with pytest.raises(ValueError, match="target_minutes"):
            _objective(target_minutes=True)  # type: ignore[arg-type]

    def test_bool_actual_minutes_rejected(self):
        with pytest.raises(ValueError, match="actual_minutes"):
            _objective(actual_minutes=False)  # type: ignore[arg-type]

    def test_invalid_evaluated_at_rejected(self):
        with pytest.raises(ValueError, match="evaluated_at"):
            _objective(evaluated_at="not-a-date")

    def test_empty_evaluated_at_rejected(self):
        with pytest.raises(ValueError, match="evaluated_at"):
            _objective(evaluated_at="")

    def test_whitespace_objective_id_rejected(self):
        with pytest.raises(ValueError, match="objective_id"):
            _objective(objective_id="   ")

    def test_whitespace_name_rejected(self):
        with pytest.raises(ValueError, match="name"):
            _objective(name="  \t")


class TestRecoveryObjectiveFrozen:
    def test_cannot_set_objective_id(self):
        obj = _objective()
        with pytest.raises(AttributeError):
            obj.objective_id = "other"  # type: ignore[misc]

    def test_cannot_set_met(self):
        obj = _objective()
        with pytest.raises(AttributeError):
            obj.met = False  # type: ignore[misc]

    def test_cannot_set_target_minutes(self):
        obj = _objective()
        with pytest.raises(AttributeError):
            obj.target_minutes = 999  # type: ignore[misc]


class TestRecoveryObjectiveMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        obj = _objective()
        assert isinstance(obj.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        obj = _objective(metadata={"k": "v"})
        with pytest.raises(TypeError):
            obj.metadata["new"] = "x"  # type: ignore[index]


class TestRecoveryObjectiveSerialization:
    def test_to_dict_returns_dict(self):
        d = _objective().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _objective().to_dict()
        expected = {
            "objective_id", "plan_id", "name", "target_minutes",
            "actual_minutes", "met", "evaluated_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_met_is_bool(self):
        d = _objective(met=True).to_dict()
        assert d["met"] is True


# ===================================================================
# RecoveryExecution
# ===================================================================


class TestRecoveryExecutionConstruction:
    def test_valid_construction(self):
        ex = _execution()
        assert ex.execution_id == "exec-001"
        assert ex.recovery_plan_id == "rp-001"
        assert ex.disruption_id == "dis-001"
        assert ex.status is RecoveryStatus.IN_PROGRESS
        assert ex.executed_by == "operator-1"
        assert ex.completed_at == ""

    def test_all_statuses_accepted(self):
        for status in RecoveryStatus:
            ex = _execution(status=status)
            assert ex.status is status

    def test_completed_at_optional_empty(self):
        ex = _execution(completed_at="")
        assert ex.completed_at == ""

    def test_completed_at_with_valid_date(self):
        ex = _execution(completed_at=_LATER)
        assert ex.completed_at == _LATER

    def test_completed_at_date_only(self):
        ex = _execution(completed_at="2025-06-02")
        assert ex.completed_at == "2025-06-02"


class TestRecoveryExecutionValidation:
    def test_empty_execution_id_rejected(self):
        with pytest.raises(ValueError, match="execution_id"):
            _execution(execution_id="")

    def test_empty_recovery_plan_id_rejected(self):
        with pytest.raises(ValueError, match="recovery_plan_id"):
            _execution(recovery_plan_id="")

    def test_empty_disruption_id_rejected(self):
        with pytest.raises(ValueError, match="disruption_id"):
            _execution(disruption_id="")

    def test_invalid_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _execution(status="running")  # type: ignore[arg-type]

    def test_empty_executed_by_rejected(self):
        with pytest.raises(ValueError, match="executed_by"):
            _execution(executed_by="")

    def test_invalid_started_at_rejected(self):
        with pytest.raises(ValueError, match="started_at"):
            _execution(started_at="not-a-date")

    def test_empty_started_at_rejected(self):
        with pytest.raises(ValueError, match="started_at"):
            _execution(started_at="")

    def test_invalid_completed_at_rejected(self):
        with pytest.raises(ValueError, match="completed_at"):
            _execution(completed_at="bad-date")

    def test_whitespace_execution_id_rejected(self):
        with pytest.raises(ValueError, match="execution_id"):
            _execution(execution_id="  ")

    def test_whitespace_executed_by_rejected(self):
        with pytest.raises(ValueError, match="executed_by"):
            _execution(executed_by="  \t")


class TestRecoveryExecutionFrozen:
    def test_cannot_set_execution_id(self):
        ex = _execution()
        with pytest.raises(AttributeError):
            ex.execution_id = "other"  # type: ignore[misc]

    def test_cannot_set_status(self):
        ex = _execution()
        with pytest.raises(AttributeError):
            ex.status = RecoveryStatus.COMPLETED  # type: ignore[misc]

    def test_cannot_set_executed_by(self):
        ex = _execution()
        with pytest.raises(AttributeError):
            ex.executed_by = "someone-else"  # type: ignore[misc]


class TestRecoveryExecutionMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        ex = _execution()
        assert isinstance(ex.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        ex = _execution(metadata={"a": 1})
        with pytest.raises(TypeError):
            ex.metadata["b"] = 2  # type: ignore[index]


class TestRecoveryExecutionSerialization:
    def test_to_dict_returns_dict(self):
        d = _execution().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _execution().to_dict()
        expected = {
            "execution_id", "recovery_plan_id", "disruption_id",
            "status", "executed_by", "started_at", "completed_at",
            "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_preserves_enum(self):
        d = _execution().to_dict()
        assert d["status"] is RecoveryStatus.IN_PROGRESS


# ===================================================================
# VerificationRecord
# ===================================================================


class TestVerificationRecordConstruction:
    def test_valid_construction(self):
        vr = _verification()
        assert vr.verification_id == "ver-001"
        assert vr.execution_id == "exec-001"
        assert vr.status is RecoveryVerificationStatus.PENDING
        assert vr.verified_by == "verifier-1"
        assert vr.confidence == 0.95
        assert vr.reason == "All checks passed"

    def test_all_statuses_accepted(self):
        for status in RecoveryVerificationStatus:
            vr = _verification(status=status)
            assert vr.status is status

    def test_confidence_zero(self):
        vr = _verification(confidence=0.0)
        assert vr.confidence == 0.0

    def test_confidence_one(self):
        vr = _verification(confidence=1.0)
        assert vr.confidence == 1.0

    def test_confidence_half(self):
        vr = _verification(confidence=0.5)
        assert vr.confidence == 0.5

    def test_confidence_int_zero(self):
        vr = _verification(confidence=0)
        assert vr.confidence == 0.0

    def test_confidence_int_one(self):
        vr = _verification(confidence=1)
        assert vr.confidence == 1.0

    def test_date_only_accepted(self):
        vr = _verification(verified_at="2025-06-01")
        assert vr.verified_at == "2025-06-01"


class TestVerificationRecordValidation:
    def test_empty_verification_id_rejected(self):
        with pytest.raises(ValueError, match="verification_id"):
            _verification(verification_id="")

    def test_empty_execution_id_rejected(self):
        with pytest.raises(ValueError, match="execution_id"):
            _verification(execution_id="")

    def test_invalid_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _verification(status="approved")  # type: ignore[arg-type]

    def test_empty_verified_by_rejected(self):
        with pytest.raises(ValueError, match="verified_by"):
            _verification(verified_by="")

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence=-0.1)

    def test_confidence_above_one_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence=1.01)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence=float("nan"))

    def test_confidence_inf_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence=float("inf"))

    def test_confidence_neg_inf_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence=float("-inf"))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence=True)  # type: ignore[arg-type]

    def test_confidence_string_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence="0.5")  # type: ignore[arg-type]

    def test_invalid_verified_at_rejected(self):
        with pytest.raises(ValueError, match="verified_at"):
            _verification(verified_at="not-a-date")

    def test_empty_verified_at_rejected(self):
        with pytest.raises(ValueError, match="verified_at"):
            _verification(verified_at="")

    def test_whitespace_verification_id_rejected(self):
        with pytest.raises(ValueError, match="verification_id"):
            _verification(verification_id="   ")

    def test_whitespace_verified_by_rejected(self):
        with pytest.raises(ValueError, match="verified_by"):
            _verification(verified_by="  ")

    def test_confidence_large_positive_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence=100.0)

    def test_confidence_large_negative_rejected(self):
        with pytest.raises(ValueError, match="confidence"):
            _verification(confidence=-100.0)


class TestVerificationRecordFrozen:
    def test_cannot_set_verification_id(self):
        vr = _verification()
        with pytest.raises(AttributeError):
            vr.verification_id = "other"  # type: ignore[misc]

    def test_cannot_set_confidence(self):
        vr = _verification()
        with pytest.raises(AttributeError):
            vr.confidence = 0.0  # type: ignore[misc]

    def test_cannot_set_status(self):
        vr = _verification()
        with pytest.raises(AttributeError):
            vr.status = RecoveryVerificationStatus.PASSED  # type: ignore[misc]


class TestVerificationRecordMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        vr = _verification()
        assert isinstance(vr.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        vr = _verification(metadata={"check": "ok"})
        with pytest.raises(TypeError):
            vr.metadata["new"] = "x"  # type: ignore[index]

    def test_nested_dict_in_metadata_frozen(self):
        vr = _verification(metadata={"details": {"step": 1}})
        assert isinstance(vr.metadata["details"], MappingProxyType)


class TestVerificationRecordSerialization:
    def test_to_dict_returns_dict(self):
        d = _verification().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _verification().to_dict()
        expected = {
            "verification_id", "execution_id", "status", "verified_by",
            "confidence", "reason", "verified_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_dict_preserves_enum(self):
        d = _verification().to_dict()
        assert d["status"] is RecoveryVerificationStatus.PENDING

    def test_to_dict_confidence_is_float(self):
        d = _verification().to_dict()
        assert isinstance(d["confidence"], float)


# ===================================================================
# ContinuitySnapshot
# ===================================================================


class TestContinuitySnapshotConstruction:
    def test_valid_construction(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.total_plans == 5
        assert s.total_active_plans == 3
        assert s.total_recovery_plans == 2
        assert s.total_disruptions == 1
        assert s.total_failovers == 1
        assert s.total_recoveries == 1
        assert s.total_verifications == 1
        assert s.total_violations == 0
        assert s.total_objectives == 4

    def test_all_zero_counts_accepted(self):
        s = _snapshot(
            total_plans=0, total_active_plans=0, total_recovery_plans=0,
            total_disruptions=0, total_failovers=0, total_recoveries=0,
            total_verifications=0, total_violations=0, total_objectives=0,
        )
        assert s.total_plans == 0

    def test_large_counts_accepted(self):
        s = _snapshot(total_plans=1_000_000)
        assert s.total_plans == 1_000_000

    def test_date_only_accepted(self):
        s = _snapshot(captured_at="2025-06-01")
        assert s.captured_at == "2025-06-01"


class TestContinuitySnapshotValidation:
    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="   ")

    def test_negative_total_plans_rejected(self):
        with pytest.raises(ValueError, match="total_plans"):
            _snapshot(total_plans=-1)

    def test_negative_total_active_plans_rejected(self):
        with pytest.raises(ValueError, match="total_active_plans"):
            _snapshot(total_active_plans=-1)

    def test_negative_total_recovery_plans_rejected(self):
        with pytest.raises(ValueError, match="total_recovery_plans"):
            _snapshot(total_recovery_plans=-1)

    def test_negative_total_disruptions_rejected(self):
        with pytest.raises(ValueError, match="total_disruptions"):
            _snapshot(total_disruptions=-1)

    def test_negative_total_failovers_rejected(self):
        with pytest.raises(ValueError, match="total_failovers"):
            _snapshot(total_failovers=-1)

    def test_negative_total_recoveries_rejected(self):
        with pytest.raises(ValueError, match="total_recoveries"):
            _snapshot(total_recoveries=-1)

    def test_negative_total_verifications_rejected(self):
        with pytest.raises(ValueError, match="total_verifications"):
            _snapshot(total_verifications=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _snapshot(total_violations=-1)

    def test_negative_total_objectives_rejected(self):
        with pytest.raises(ValueError, match="total_objectives"):
            _snapshot(total_objectives=-1)

    def test_float_total_plans_rejected(self):
        with pytest.raises(ValueError, match="total_plans"):
            _snapshot(total_plans=1.5)  # type: ignore[arg-type]

    def test_float_total_active_plans_rejected(self):
        with pytest.raises(ValueError, match="total_active_plans"):
            _snapshot(total_active_plans=2.0)  # type: ignore[arg-type]

    def test_float_total_recovery_plans_rejected(self):
        with pytest.raises(ValueError, match="total_recovery_plans"):
            _snapshot(total_recovery_plans=3.3)  # type: ignore[arg-type]

    def test_float_total_disruptions_rejected(self):
        with pytest.raises(ValueError, match="total_disruptions"):
            _snapshot(total_disruptions=0.5)  # type: ignore[arg-type]

    def test_float_total_failovers_rejected(self):
        with pytest.raises(ValueError, match="total_failovers"):
            _snapshot(total_failovers=1.1)  # type: ignore[arg-type]

    def test_float_total_recoveries_rejected(self):
        with pytest.raises(ValueError, match="total_recoveries"):
            _snapshot(total_recoveries=0.9)  # type: ignore[arg-type]

    def test_float_total_verifications_rejected(self):
        with pytest.raises(ValueError, match="total_verifications"):
            _snapshot(total_verifications=1.2)  # type: ignore[arg-type]

    def test_float_total_violations_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _snapshot(total_violations=0.1)  # type: ignore[arg-type]

    def test_float_total_objectives_rejected(self):
        with pytest.raises(ValueError, match="total_objectives"):
            _snapshot(total_objectives=4.4)  # type: ignore[arg-type]

    def test_bool_total_plans_rejected(self):
        with pytest.raises(ValueError, match="total_plans"):
            _snapshot(total_plans=True)  # type: ignore[arg-type]

    def test_bool_total_disruptions_rejected(self):
        with pytest.raises(ValueError, match="total_disruptions"):
            _snapshot(total_disruptions=False)  # type: ignore[arg-type]

    def test_invalid_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="bad-date")

    def test_empty_captured_at_rejected(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="")


class TestContinuitySnapshotFrozen:
    def test_cannot_set_snapshot_id(self):
        s = _snapshot()
        with pytest.raises(AttributeError):
            s.snapshot_id = "other"  # type: ignore[misc]

    def test_cannot_set_total_plans(self):
        s = _snapshot()
        with pytest.raises(AttributeError):
            s.total_plans = 999  # type: ignore[misc]

    def test_cannot_set_total_violations(self):
        s = _snapshot()
        with pytest.raises(AttributeError):
            s.total_violations = 10  # type: ignore[misc]


class TestContinuitySnapshotMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        s = _snapshot()
        assert isinstance(s.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        s = _snapshot(metadata={"env": "prod"})
        with pytest.raises(TypeError):
            s.metadata["new"] = "x"  # type: ignore[index]

    def test_list_in_metadata_becomes_tuple(self):
        s = _snapshot(metadata={"ids": [1, 2, 3]})
        assert isinstance(s.metadata["ids"], tuple)


class TestContinuitySnapshotSerialization:
    def test_to_dict_returns_dict(self):
        d = _snapshot().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _snapshot().to_dict()
        expected = {
            "snapshot_id", "total_plans", "total_active_plans",
            "total_recovery_plans", "total_disruptions", "total_failovers",
            "total_recoveries", "total_verifications", "total_violations",
            "total_objectives", "captured_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_json_produces_string(self):
        j = _snapshot().to_json()
        assert isinstance(j, str)
        assert '"snapshot_id"' in j


# ===================================================================
# ContinuityViolation
# ===================================================================


class TestContinuityViolationConstruction:
    def test_valid_construction(self):
        v = _violation()
        assert v.violation_id == "vio-001"
        assert v.plan_id == "plan-001"
        assert v.tenant_id == "tenant-1"
        assert v.operation == "reopen_completed_recovery"
        assert v.reason == "Completed recoveries cannot be re-opened"

    def test_date_only_accepted(self):
        v = _violation(detected_at="2025-06-01")
        assert v.detected_at == "2025-06-01"

    def test_datetime_with_z_accepted(self):
        v = _violation(detected_at="2025-06-01T00:00:00Z")
        assert v.detected_at == "2025-06-01T00:00:00Z"


class TestContinuityViolationValidation:
    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _violation(violation_id="")

    def test_empty_plan_id_rejected(self):
        with pytest.raises(ValueError, match="plan_id"):
            _violation(plan_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _violation(tenant_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _violation(operation="")

    def test_invalid_detected_at_rejected(self):
        with pytest.raises(ValueError, match="detected_at"):
            _violation(detected_at="not-a-date")

    def test_empty_detected_at_rejected(self):
        with pytest.raises(ValueError, match="detected_at"):
            _violation(detected_at="")

    def test_whitespace_violation_id_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _violation(violation_id="   ")

    def test_whitespace_plan_id_rejected(self):
        with pytest.raises(ValueError, match="plan_id"):
            _violation(plan_id="  \t")

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _violation(tenant_id="  ")

    def test_whitespace_operation_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _violation(operation="\t  ")


class TestContinuityViolationFrozen:
    def test_cannot_set_violation_id(self):
        v = _violation()
        with pytest.raises(AttributeError):
            v.violation_id = "other"  # type: ignore[misc]

    def test_cannot_set_plan_id(self):
        v = _violation()
        with pytest.raises(AttributeError):
            v.plan_id = "other"  # type: ignore[misc]

    def test_cannot_set_operation(self):
        v = _violation()
        with pytest.raises(AttributeError):
            v.operation = "other"  # type: ignore[misc]


class TestContinuityViolationMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        v = _violation()
        assert isinstance(v.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        v = _violation(metadata={"ctx": "test"})
        with pytest.raises(TypeError):
            v.metadata["new"] = "x"  # type: ignore[index]

    def test_nested_dict_in_metadata_frozen(self):
        v = _violation(metadata={"nested": {"a": 1}})
        assert isinstance(v.metadata["nested"], MappingProxyType)


class TestContinuityViolationSerialization:
    def test_to_dict_returns_dict(self):
        d = _violation().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _violation().to_dict()
        expected = {
            "violation_id", "plan_id", "tenant_id", "operation",
            "reason", "detected_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_json_produces_string(self):
        j = _violation().to_json()
        assert isinstance(j, str)
        assert '"violation_id"' in j


# ===================================================================
# ContinuityClosureReport
# ===================================================================


class TestContinuityClosureReportConstruction:
    def test_valid_construction(self):
        c = _closure()
        assert c.report_id == "rpt-001"
        assert c.tenant_id == "tenant-1"
        assert c.total_plans == 5
        assert c.total_disruptions == 2
        assert c.total_failovers == 1
        assert c.total_recoveries == 2
        assert c.total_verifications_passed == 3
        assert c.total_verifications_failed == 0
        assert c.total_violations == 1

    def test_all_zero_counts_accepted(self):
        c = _closure(
            total_plans=0, total_disruptions=0, total_failovers=0,
            total_recoveries=0, total_verifications_passed=0,
            total_verifications_failed=0, total_violations=0,
        )
        assert c.total_plans == 0

    def test_large_counts_accepted(self):
        c = _closure(total_plans=500_000)
        assert c.total_plans == 500_000

    def test_date_only_accepted(self):
        c = _closure(closed_at="2025-06-01")
        assert c.closed_at == "2025-06-01"

    def test_datetime_with_z_accepted(self):
        c = _closure(closed_at="2025-06-01T00:00:00Z")
        assert c.closed_at == "2025-06-01T00:00:00Z"


class TestContinuityClosureReportValidation:
    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _closure(tenant_id="")

    def test_negative_total_plans_rejected(self):
        with pytest.raises(ValueError, match="total_plans"):
            _closure(total_plans=-1)

    def test_negative_total_disruptions_rejected(self):
        with pytest.raises(ValueError, match="total_disruptions"):
            _closure(total_disruptions=-1)

    def test_negative_total_failovers_rejected(self):
        with pytest.raises(ValueError, match="total_failovers"):
            _closure(total_failovers=-1)

    def test_negative_total_recoveries_rejected(self):
        with pytest.raises(ValueError, match="total_recoveries"):
            _closure(total_recoveries=-1)

    def test_negative_total_verifications_passed_rejected(self):
        with pytest.raises(ValueError, match="total_verifications_passed"):
            _closure(total_verifications_passed=-1)

    def test_negative_total_verifications_failed_rejected(self):
        with pytest.raises(ValueError, match="total_verifications_failed"):
            _closure(total_verifications_failed=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _closure(total_violations=-1)

    def test_float_total_plans_rejected(self):
        with pytest.raises(ValueError, match="total_plans"):
            _closure(total_plans=1.5)  # type: ignore[arg-type]

    def test_float_total_disruptions_rejected(self):
        with pytest.raises(ValueError, match="total_disruptions"):
            _closure(total_disruptions=2.0)  # type: ignore[arg-type]

    def test_float_total_failovers_rejected(self):
        with pytest.raises(ValueError, match="total_failovers"):
            _closure(total_failovers=0.5)  # type: ignore[arg-type]

    def test_float_total_recoveries_rejected(self):
        with pytest.raises(ValueError, match="total_recoveries"):
            _closure(total_recoveries=1.1)  # type: ignore[arg-type]

    def test_float_total_verifications_passed_rejected(self):
        with pytest.raises(ValueError, match="total_verifications_passed"):
            _closure(total_verifications_passed=3.3)  # type: ignore[arg-type]

    def test_float_total_verifications_failed_rejected(self):
        with pytest.raises(ValueError, match="total_verifications_failed"):
            _closure(total_verifications_failed=0.1)  # type: ignore[arg-type]

    def test_float_total_violations_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _closure(total_violations=1.9)  # type: ignore[arg-type]

    def test_bool_total_plans_rejected(self):
        with pytest.raises(ValueError, match="total_plans"):
            _closure(total_plans=True)  # type: ignore[arg-type]

    def test_bool_total_disruptions_rejected(self):
        with pytest.raises(ValueError, match="total_disruptions"):
            _closure(total_disruptions=False)  # type: ignore[arg-type]

    def test_invalid_closed_at_rejected(self):
        with pytest.raises(ValueError, match="closed_at"):
            _closure(closed_at="bad-date")

    def test_empty_closed_at_rejected(self):
        with pytest.raises(ValueError, match="closed_at"):
            _closure(closed_at="")

    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="   ")

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _closure(tenant_id="  \t")


class TestContinuityClosureReportFrozen:
    def test_cannot_set_report_id(self):
        c = _closure()
        with pytest.raises(AttributeError):
            c.report_id = "other"  # type: ignore[misc]

    def test_cannot_set_total_plans(self):
        c = _closure()
        with pytest.raises(AttributeError):
            c.total_plans = 999  # type: ignore[misc]

    def test_cannot_set_total_violations(self):
        c = _closure()
        with pytest.raises(AttributeError):
            c.total_violations = 100  # type: ignore[misc]

    def test_cannot_set_tenant_id(self):
        c = _closure()
        with pytest.raises(AttributeError):
            c.tenant_id = "other"  # type: ignore[misc]


class TestContinuityClosureReportMetadata:
    def test_default_metadata_is_mapping_proxy(self):
        c = _closure()
        assert isinstance(c.metadata, MappingProxyType)

    def test_metadata_frozen(self):
        c = _closure(metadata={"summary": "done"})
        with pytest.raises(TypeError):
            c.metadata["new"] = "x"  # type: ignore[index]

    def test_list_in_metadata_becomes_tuple(self):
        c = _closure(metadata={"ids": [10, 20, 30]})
        assert isinstance(c.metadata["ids"], tuple)
        assert c.metadata["ids"] == (10, 20, 30)

    def test_nested_dict_in_metadata_frozen(self):
        c = _closure(metadata={"stats": {"mean": 42}})
        assert isinstance(c.metadata["stats"], MappingProxyType)


class TestContinuityClosureReportSerialization:
    def test_to_dict_returns_dict(self):
        d = _closure().to_dict()
        assert isinstance(d, dict)

    def test_to_dict_contains_all_keys(self):
        d = _closure().to_dict()
        expected = {
            "report_id", "tenant_id", "total_plans", "total_disruptions",
            "total_failovers", "total_recoveries",
            "total_verifications_passed", "total_verifications_failed",
            "total_violations", "closed_at", "metadata",
        }
        assert set(d.keys()) == expected

    def test_to_json_produces_string(self):
        j = _closure().to_json()
        assert isinstance(j, str)
        assert '"report_id"' in j

    def test_to_dict_metadata_thawed(self):
        d = _closure(metadata={"k": [1]}).to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["k"], list)


# ===================================================================
# Cross-cutting: parametrized enum isinstance checks
# ===================================================================


@pytest.mark.parametrize("member", list(ContinuityStatus))
def test_continuity_status_isinstance(member):
    assert isinstance(member, ContinuityStatus)


@pytest.mark.parametrize("member", list(RecoveryStatus))
def test_recovery_status_isinstance(member):
    assert isinstance(member, RecoveryStatus)


@pytest.mark.parametrize("member", list(DisruptionSeverity))
def test_disruption_severity_isinstance(member):
    assert isinstance(member, DisruptionSeverity)


@pytest.mark.parametrize("member", list(ContinuityScope))
def test_continuity_scope_isinstance(member):
    assert isinstance(member, ContinuityScope)


@pytest.mark.parametrize("member", list(FailoverDisposition))
def test_failover_disposition_isinstance(member):
    assert isinstance(member, FailoverDisposition)


@pytest.mark.parametrize("member", list(RecoveryVerificationStatus))
def test_recovery_verification_status_isinstance(member):
    assert isinstance(member, RecoveryVerificationStatus)


# ===================================================================
# Cross-cutting: parametrized scope/status on ContinuityPlan
# ===================================================================


@pytest.mark.parametrize("scope", list(ContinuityScope))
def test_continuity_plan_accepts_each_scope(scope):
    p = _plan(scope=scope)
    assert p.scope is scope


@pytest.mark.parametrize("status", list(ContinuityStatus))
def test_continuity_plan_accepts_each_status(status):
    p = _plan(status=status)
    assert p.status is status


@pytest.mark.parametrize("scope", list(ContinuityScope))
def test_disruption_event_accepts_each_scope(scope):
    de = _disruption(scope=scope)
    assert de.scope is scope


@pytest.mark.parametrize("severity", list(DisruptionSeverity))
def test_disruption_event_accepts_each_severity(severity):
    de = _disruption(severity=severity)
    assert de.severity is severity


@pytest.mark.parametrize("disp", list(FailoverDisposition))
def test_failover_record_accepts_each_disposition(disp):
    fo = _failover(disposition=disp)
    assert fo.disposition is disp


@pytest.mark.parametrize("status", list(RecoveryStatus))
def test_recovery_plan_accepts_each_status(status):
    rp = _recovery_plan(status=status)
    assert rp.status is status


@pytest.mark.parametrize("status", list(RecoveryStatus))
def test_recovery_execution_accepts_each_status(status):
    ex = _execution(status=status)
    assert ex.status is status


@pytest.mark.parametrize("status", list(RecoveryVerificationStatus))
def test_verification_record_accepts_each_status(status):
    vr = _verification(status=status)
    assert vr.status is status


# ===================================================================
# Cross-cutting: wrong enum type on enum-validated fields
# ===================================================================


class TestWrongEnumTypeRejected:
    def test_plan_scope_wrong_enum(self):
        with pytest.raises(ValueError, match="scope"):
            _plan(scope=DisruptionSeverity.HIGH)  # type: ignore[arg-type]

    def test_plan_status_wrong_enum(self):
        with pytest.raises(ValueError, match="status"):
            _plan(status=RecoveryStatus.PENDING)  # type: ignore[arg-type]

    def test_recovery_plan_status_wrong_enum(self):
        with pytest.raises(ValueError, match="status"):
            _recovery_plan(status=ContinuityStatus.ACTIVE)  # type: ignore[arg-type]

    def test_failover_disposition_wrong_enum(self):
        with pytest.raises(ValueError, match="disposition"):
            _failover(disposition=RecoveryStatus.COMPLETED)  # type: ignore[arg-type]

    def test_disruption_scope_wrong_enum(self):
        with pytest.raises(ValueError, match="scope"):
            _disruption(scope=FailoverDisposition.INITIATED)  # type: ignore[arg-type]

    def test_disruption_severity_wrong_enum(self):
        with pytest.raises(ValueError, match="severity"):
            _disruption(severity=ContinuityScope.ASSET)  # type: ignore[arg-type]

    def test_execution_status_wrong_enum(self):
        with pytest.raises(ValueError, match="status"):
            _execution(status=FailoverDisposition.FAILED)  # type: ignore[arg-type]

    def test_verification_status_wrong_enum(self):
        with pytest.raises(ValueError, match="status"):
            _verification(status=RecoveryStatus.FAILED)  # type: ignore[arg-type]


# ===================================================================
# Cross-cutting: None for required string fields
# ===================================================================


class TestNoneForRequiredStrings:
    def test_plan_none_plan_id(self):
        with pytest.raises((ValueError, TypeError)):
            _plan(plan_id=None)  # type: ignore[arg-type]

    def test_plan_none_name(self):
        with pytest.raises((ValueError, TypeError)):
            _plan(name=None)  # type: ignore[arg-type]

    def test_plan_none_tenant_id(self):
        with pytest.raises((ValueError, TypeError)):
            _plan(tenant_id=None)  # type: ignore[arg-type]

    def test_recovery_plan_none_recovery_plan_id(self):
        with pytest.raises((ValueError, TypeError)):
            _recovery_plan(recovery_plan_id=None)  # type: ignore[arg-type]

    def test_failover_none_failover_id(self):
        with pytest.raises((ValueError, TypeError)):
            _failover(failover_id=None)  # type: ignore[arg-type]

    def test_disruption_none_disruption_id(self):
        with pytest.raises((ValueError, TypeError)):
            _disruption(disruption_id=None)  # type: ignore[arg-type]

    def test_objective_none_objective_id(self):
        with pytest.raises((ValueError, TypeError)):
            _objective(objective_id=None)  # type: ignore[arg-type]

    def test_execution_none_execution_id(self):
        with pytest.raises((ValueError, TypeError)):
            _execution(execution_id=None)  # type: ignore[arg-type]

    def test_verification_none_verification_id(self):
        with pytest.raises((ValueError, TypeError)):
            _verification(verification_id=None)  # type: ignore[arg-type]

    def test_snapshot_none_snapshot_id(self):
        with pytest.raises((ValueError, TypeError)):
            _snapshot(snapshot_id=None)  # type: ignore[arg-type]

    def test_violation_none_violation_id(self):
        with pytest.raises((ValueError, TypeError)):
            _violation(violation_id=None)  # type: ignore[arg-type]

    def test_closure_none_report_id(self):
        with pytest.raises((ValueError, TypeError)):
            _closure(report_id=None)  # type: ignore[arg-type]


# ===================================================================
# Cross-cutting: empty metadata default on all dataclasses
# ===================================================================


class TestEmptyMetadataDefault:
    def test_plan_default_metadata_empty(self):
        p = _plan()
        assert len(p.metadata) == 0

    def test_recovery_plan_default_metadata_empty(self):
        rp = _recovery_plan()
        assert len(rp.metadata) == 0

    def test_failover_default_metadata_empty(self):
        fo = _failover()
        assert len(fo.metadata) == 0

    def test_disruption_default_metadata_empty(self):
        de = _disruption()
        assert len(de.metadata) == 0

    def test_objective_default_metadata_empty(self):
        obj = _objective()
        assert len(obj.metadata) == 0

    def test_execution_default_metadata_empty(self):
        ex = _execution()
        assert len(ex.metadata) == 0

    def test_verification_default_metadata_empty(self):
        vr = _verification()
        assert len(vr.metadata) == 0

    def test_snapshot_default_metadata_empty(self):
        s = _snapshot()
        assert len(s.metadata) == 0

    def test_violation_default_metadata_empty(self):
        v = _violation()
        assert len(v.metadata) == 0

    def test_closure_default_metadata_empty(self):
        c = _closure()
        assert len(c.metadata) == 0
