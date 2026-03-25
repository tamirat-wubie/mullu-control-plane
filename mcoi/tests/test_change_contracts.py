"""Comprehensive tests for change_runtime contracts.

Covers:
  1. Enum member existence and count
  2. Valid construction of each dataclass
  3. Frozen immutability
  4. ContractRecord.to_dict() returns plain dict
  5. require_non_empty_text rejects ""
  6. require_unit_float rejects out-of-range
  7. require_non_negative_int rejects negative
  8. require_non_negative_float rejects negative
  9. require_datetime_text rejects invalid timestamps
 10. Enum-typed fields reject wrong types
 11. Bool-typed fields reject non-booleans
 12. metadata / step_ids / rollback_steps freeze (MappingProxyType, tuple)
 13. Cross-field: ChangeExecution steps_completed + steps_failed <= steps_total
 14. Default values work correctly
 15. Edge cases / boundary values
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.change_runtime import (
    ChangeApprovalBinding,
    ChangeEvidence,
    ChangeEvidenceKind,
    ChangeExecution,
    ChangeImpactAssessment,
    ChangeOutcome,
    ChangePlan,
    ChangeRequest,
    ChangeScope,
    ChangeStatus,
    ChangeStep,
    ChangeType,
    RollbackDisposition,
    RollbackPlan,
    RolloutMode,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ts(y: int = 2025, m: int = 6, d: int = 15, h: int = 10, mi: int = 0) -> str:
    return datetime(y, m, d, h, mi, tzinfo=timezone.utc).isoformat()


def _make_change_request(**overrides):
    defaults = dict(
        change_id="cr-1",
        title="Enable canary routing",
        change_type=ChangeType.ROUTING_RULE,
        scope=ChangeScope.CAMPAIGN,
        status=ChangeStatus.DRAFT,
        rollout_mode=RolloutMode.CANARY,
        approval_required=True,
        created_at=_ts(),
    )
    defaults.update(overrides)
    return ChangeRequest(**defaults)


def _make_change_plan(**overrides):
    defaults = dict(
        plan_id="pl-1",
        change_id="cr-1",
        title="Canary rollout plan",
        rollout_mode=RolloutMode.CANARY,
        estimated_duration_seconds=120.0,
        step_ids=("s1", "s2"),
        created_at=_ts(),
    )
    defaults.update(overrides)
    return ChangePlan(**defaults)


def _make_change_step(**overrides):
    defaults = dict(
        step_id="s-1",
        plan_id="pl-1",
        change_id="cr-1",
        ordinal=0,
        action="deploy",
        status=ChangeStatus.DRAFT,
    )
    defaults.update(overrides)
    return ChangeStep(**defaults)


def _make_change_execution(**overrides):
    defaults = dict(
        execution_id="ex-1",
        change_id="cr-1",
        plan_id="pl-1",
        status=ChangeStatus.IN_PROGRESS,
        rollout_mode=RolloutMode.CANARY,
        steps_total=5,
        steps_completed=2,
        steps_failed=1,
        started_at=_ts(),
    )
    defaults.update(overrides)
    return ChangeExecution(**defaults)


def _make_change_approval_binding(**overrides):
    defaults = dict(
        approval_id="ap-1",
        change_id="cr-1",
        approved_by="admin@example.com",
        approved=True,
        approved_at=_ts(),
    )
    defaults.update(overrides)
    return ChangeApprovalBinding(**defaults)


def _make_change_evidence(**overrides):
    defaults = dict(
        evidence_id="ev-1",
        change_id="cr-1",
        kind=ChangeEvidenceKind.LOG_ENTRY,
        collected_at=_ts(),
    )
    defaults.update(overrides)
    return ChangeEvidence(**defaults)


def _make_rollback_plan(**overrides):
    defaults = dict(
        rollback_id="rb-1",
        change_id="cr-1",
        disposition=RollbackDisposition.TRIGGERED,
        rollback_steps=("rs1", "rs2"),
        triggered_at=_ts(),
    )
    defaults.update(overrides)
    return RollbackPlan(**defaults)


def _make_change_outcome(**overrides):
    defaults = dict(
        outcome_id="oc-1",
        change_id="cr-1",
        execution_id="ex-1",
        status=ChangeStatus.COMPLETED,
        success=True,
        improvement_observed=True,
        rollback_disposition=RollbackDisposition.NOT_NEEDED,
        evidence_count=3,
        completed_at=_ts(),
    )
    defaults.update(overrides)
    return ChangeOutcome(**defaults)


def _make_change_impact_assessment(**overrides):
    defaults = dict(
        assessment_id="ia-1",
        change_id="cr-1",
        metric_name="latency_p99",
        confidence=0.95,
        assessment_window_seconds=3600.0,
        assessed_at=_ts(),
    )
    defaults.update(overrides)
    return ChangeImpactAssessment(**defaults)


# ===================================================================
# 1. Enum member existence and count
# ===================================================================


class TestChangeTypeEnum:
    EXPECTED = [
        "CONNECTOR_PREFERENCE", "BUDGET_THRESHOLD", "ESCALATION_TIMING",
        "SCHEDULE_POLICY", "CAMPAIGN_TEMPLATE_PATH", "DOMAIN_PACK_ACTIVATION",
        "FALLBACK_CHAIN", "ROUTING_RULE", "AVAILABILITY_POLICY", "CONFIGURATION",
    ]

    def test_member_count(self):
        assert len(ChangeType) == 10

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name):
        assert hasattr(ChangeType, name)

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_value_is_lowercase(self, name):
        assert ChangeType[name].value == name.lower()


class TestChangeScopeEnum:
    EXPECTED = [
        "GLOBAL", "PORTFOLIO", "CAMPAIGN", "CONNECTOR",
        "TEAM", "FUNCTION", "CHANNEL", "DOMAIN_PACK",
    ]

    def test_member_count(self):
        assert len(ChangeScope) == 8

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name):
        assert hasattr(ChangeScope, name)


class TestChangeStatusEnum:
    EXPECTED = [
        "DRAFT", "PENDING_APPROVAL", "APPROVED", "IN_PROGRESS",
        "PAUSED", "COMPLETED", "ABORTED", "ROLLED_BACK", "FAILED",
    ]

    def test_member_count(self):
        assert len(ChangeStatus) == 9

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name):
        assert hasattr(ChangeStatus, name)


class TestRolloutModeEnum:
    EXPECTED = [
        "IMMEDIATE", "CANARY", "PARTIAL", "PHASED", "FULL", "DRY_RUN",
    ]

    def test_member_count(self):
        assert len(RolloutMode) == 6

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name):
        assert hasattr(RolloutMode, name)


class TestRollbackDispositionEnum:
    EXPECTED = [
        "NOT_NEEDED", "TRIGGERED", "COMPLETED", "PARTIAL", "FAILED",
    ]

    def test_member_count(self):
        assert len(RollbackDisposition) == 5

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name):
        assert hasattr(RollbackDisposition, name)


class TestChangeEvidenceKindEnum:
    EXPECTED = [
        "METRIC_BEFORE", "METRIC_AFTER", "LOG_ENTRY", "EVENT_TRACE",
        "APPROVAL_RECORD", "ROLLBACK_RECORD", "IMPACT_ASSESSMENT", "USER_FEEDBACK",
    ]

    def test_member_count(self):
        assert len(ChangeEvidenceKind) == 8

    @pytest.mark.parametrize("name", EXPECTED)
    def test_member_exists(self, name):
        assert hasattr(ChangeEvidenceKind, name)


# ===================================================================
# 2. Valid construction
# ===================================================================


class TestValidConstruction:
    def test_change_request(self):
        cr = _make_change_request()
        assert cr.change_id == "cr-1"
        assert cr.title == "Enable canary routing"
        assert cr.change_type is ChangeType.ROUTING_RULE
        assert cr.scope is ChangeScope.CAMPAIGN
        assert cr.status is ChangeStatus.DRAFT
        assert cr.rollout_mode is RolloutMode.CANARY
        assert cr.approval_required is True

    def test_change_plan(self):
        cp = _make_change_plan()
        assert cp.plan_id == "pl-1"
        assert cp.change_id == "cr-1"
        assert cp.title == "Canary rollout plan"
        assert cp.estimated_duration_seconds == 120.0
        assert cp.step_ids == ("s1", "s2")

    def test_change_step(self):
        cs = _make_change_step()
        assert cs.step_id == "s-1"
        assert cs.ordinal == 0
        assert cs.action == "deploy"

    def test_change_execution(self):
        ce = _make_change_execution()
        assert ce.execution_id == "ex-1"
        assert ce.steps_total == 5
        assert ce.steps_completed == 2
        assert ce.steps_failed == 1

    def test_change_approval_binding(self):
        cab = _make_change_approval_binding()
        assert cab.approval_id == "ap-1"
        assert cab.approved is True

    def test_change_evidence(self):
        ev = _make_change_evidence()
        assert ev.evidence_id == "ev-1"
        assert ev.kind is ChangeEvidenceKind.LOG_ENTRY

    def test_rollback_plan(self):
        rb = _make_rollback_plan()
        assert rb.rollback_id == "rb-1"
        assert rb.rollback_steps == ("rs1", "rs2")

    def test_change_outcome(self):
        co = _make_change_outcome()
        assert co.outcome_id == "oc-1"
        assert co.success is True
        assert co.improvement_observed is True
        assert co.evidence_count == 3

    def test_change_impact_assessment(self):
        cia = _make_change_impact_assessment()
        assert cia.assessment_id == "ia-1"
        assert cia.confidence == 0.95
        assert cia.assessment_window_seconds == 3600.0


# ===================================================================
# 3. Frozen immutability
# ===================================================================


class TestFrozenImmutability:
    def test_change_request_frozen(self):
        cr = _make_change_request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cr.change_id = "other"  # type: ignore[misc]

    def test_change_plan_frozen(self):
        cp = _make_change_plan()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cp.plan_id = "other"  # type: ignore[misc]

    def test_change_step_frozen(self):
        cs = _make_change_step()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cs.step_id = "other"  # type: ignore[misc]

    def test_change_execution_frozen(self):
        ce = _make_change_execution()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ce.execution_id = "other"  # type: ignore[misc]

    def test_change_approval_binding_frozen(self):
        cab = _make_change_approval_binding()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cab.approval_id = "other"  # type: ignore[misc]

    def test_change_evidence_frozen(self):
        ev = _make_change_evidence()
        with pytest.raises(dataclasses.FrozenInstanceError):
            ev.evidence_id = "other"  # type: ignore[misc]

    def test_rollback_plan_frozen(self):
        rb = _make_rollback_plan()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rb.rollback_id = "other"  # type: ignore[misc]

    def test_change_outcome_frozen(self):
        co = _make_change_outcome()
        with pytest.raises(dataclasses.FrozenInstanceError):
            co.outcome_id = "other"  # type: ignore[misc]

    def test_change_impact_assessment_frozen(self):
        cia = _make_change_impact_assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            cia.assessment_id = "other"  # type: ignore[misc]


# ===================================================================
# 4. to_dict returns plain dict
# ===================================================================


class TestToDict:
    def test_change_request_to_dict(self):
        cr = _make_change_request(metadata={"key": "val"})
        d = cr.to_dict()
        assert isinstance(d, dict)
        assert d["change_id"] == "cr-1"
        assert isinstance(d["metadata"], dict)
        assert d["metadata"]["key"] == "val"

    def test_change_plan_to_dict(self):
        cp = _make_change_plan()
        d = cp.to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["step_ids"], list)

    def test_change_step_to_dict(self):
        d = _make_change_step().to_dict()
        assert isinstance(d, dict)

    def test_change_execution_to_dict(self):
        d = _make_change_execution().to_dict()
        assert isinstance(d, dict)

    def test_change_approval_binding_to_dict(self):
        d = _make_change_approval_binding().to_dict()
        assert isinstance(d, dict)

    def test_change_evidence_to_dict(self):
        d = _make_change_evidence().to_dict()
        assert isinstance(d, dict)

    def test_rollback_plan_to_dict(self):
        d = _make_rollback_plan().to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["rollback_steps"], list)

    def test_change_outcome_to_dict(self):
        d = _make_change_outcome().to_dict()
        assert isinstance(d, dict)

    def test_change_impact_assessment_to_dict(self):
        d = _make_change_impact_assessment().to_dict()
        assert isinstance(d, dict)

    def test_nested_metadata_thawed(self):
        cr = _make_change_request(metadata={"nested": {"a": 1}})
        d = cr.to_dict()
        assert isinstance(d["metadata"]["nested"], dict)


# ===================================================================
# 5. require_non_empty_text rejects ""
# ===================================================================


class TestNonEmptyTextValidation:
    @pytest.mark.parametrize("field_name", ["change_id", "title"])
    def test_change_request_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_request(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["change_id", "title"])
    def test_change_request_rejects_whitespace(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_request(**{field_name: "   "})

    @pytest.mark.parametrize("field_name", ["plan_id", "change_id", "title"])
    def test_change_plan_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_plan(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["step_id", "plan_id", "change_id", "action"])
    def test_change_step_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_step(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["execution_id", "change_id", "plan_id"])
    def test_change_execution_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_execution(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["approval_id", "change_id", "approved_by"])
    def test_change_approval_binding_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_approval_binding(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["evidence_id", "change_id"])
    def test_change_evidence_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_evidence(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["rollback_id", "change_id"])
    def test_rollback_plan_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_rollback_plan(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["outcome_id", "change_id", "execution_id"])
    def test_change_outcome_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_outcome(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["assessment_id", "change_id", "metric_name"])
    def test_change_impact_assessment_rejects_empty(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_impact_assessment(**{field_name: ""})


# ===================================================================
# 6. require_unit_float rejects out-of-range
# ===================================================================


class TestUnitFloatValidation:
    @pytest.mark.parametrize("bad_val", [-0.01, 1.01, -1.0, 2.0, 100.0])
    def test_confidence_rejects_out_of_range(self, bad_val):
        with pytest.raises(ValueError, match="confidence"):
            _make_change_impact_assessment(confidence=bad_val)

    def test_confidence_accepts_zero(self):
        cia = _make_change_impact_assessment(confidence=0.0)
        assert cia.confidence == 0.0

    def test_confidence_accepts_one(self):
        cia = _make_change_impact_assessment(confidence=1.0)
        assert cia.confidence == 1.0

    def test_confidence_accepts_midpoint(self):
        cia = _make_change_impact_assessment(confidence=0.5)
        assert cia.confidence == 0.5

    def test_confidence_rejects_nan(self):
        with pytest.raises(ValueError):
            _make_change_impact_assessment(confidence=float("nan"))

    def test_confidence_rejects_inf(self):
        with pytest.raises(ValueError):
            _make_change_impact_assessment(confidence=float("inf"))

    def test_confidence_rejects_bool(self):
        with pytest.raises(ValueError):
            _make_change_impact_assessment(confidence=True)


# ===================================================================
# 7. require_non_negative_int rejects negative
# ===================================================================


class TestNonNegativeIntValidation:
    def test_ordinal_rejects_negative(self):
        with pytest.raises(ValueError, match="ordinal"):
            _make_change_step(ordinal=-1)

    def test_ordinal_accepts_zero(self):
        cs = _make_change_step(ordinal=0)
        assert cs.ordinal == 0

    def test_ordinal_accepts_positive(self):
        cs = _make_change_step(ordinal=42)
        assert cs.ordinal == 42

    @pytest.mark.parametrize("field_name", ["steps_total", "steps_completed", "steps_failed"])
    def test_execution_rejects_negative_int(self, field_name):
        with pytest.raises(ValueError, match=field_name):
            _make_change_execution(**{field_name: -1})

    def test_evidence_count_rejects_negative(self):
        with pytest.raises(ValueError, match="evidence_count"):
            _make_change_outcome(evidence_count=-1)

    def test_evidence_count_accepts_zero(self):
        co = _make_change_outcome(evidence_count=0)
        assert co.evidence_count == 0

    def test_ordinal_rejects_bool(self):
        with pytest.raises(ValueError, match="ordinal"):
            _make_change_step(ordinal=True)

    def test_evidence_count_rejects_bool(self):
        with pytest.raises(ValueError, match="evidence_count"):
            _make_change_outcome(evidence_count=False)

    def test_steps_total_rejects_float(self):
        with pytest.raises((ValueError, TypeError)):
            _make_change_execution(steps_total=1.5)


# ===================================================================
# 8. require_non_negative_float rejects negative
# ===================================================================


class TestNonNegativeFloatValidation:
    def test_estimated_duration_rejects_negative(self):
        with pytest.raises(ValueError, match="estimated_duration_seconds"):
            _make_change_plan(estimated_duration_seconds=-1.0)

    def test_estimated_duration_accepts_zero(self):
        cp = _make_change_plan(estimated_duration_seconds=0.0)
        assert cp.estimated_duration_seconds == 0.0

    def test_estimated_duration_accepts_positive(self):
        cp = _make_change_plan(estimated_duration_seconds=999.9)
        assert cp.estimated_duration_seconds == 999.9

    def test_assessment_window_rejects_negative(self):
        with pytest.raises(ValueError, match="assessment_window_seconds"):
            _make_change_impact_assessment(assessment_window_seconds=-0.1)

    def test_assessment_window_accepts_zero(self):
        cia = _make_change_impact_assessment(assessment_window_seconds=0.0)
        assert cia.assessment_window_seconds == 0.0

    def test_estimated_duration_rejects_nan(self):
        with pytest.raises(ValueError):
            _make_change_plan(estimated_duration_seconds=float("nan"))

    def test_estimated_duration_rejects_inf(self):
        with pytest.raises(ValueError):
            _make_change_plan(estimated_duration_seconds=float("inf"))

    def test_estimated_duration_rejects_bool(self):
        with pytest.raises(ValueError):
            _make_change_plan(estimated_duration_seconds=True)

    def test_assessment_window_rejects_bool(self):
        with pytest.raises(ValueError):
            _make_change_impact_assessment(assessment_window_seconds=False)


# ===================================================================
# 9. require_datetime_text rejects invalid timestamps
# ===================================================================


class TestDatetimeTextValidation:
    INVALID_TIMESTAMPS = [
        "not-a-date",
        "2025-13-01T00:00:00+00:00",
        "yesterday",
        "12345",
    ]

    @pytest.mark.parametrize("bad_ts", INVALID_TIMESTAMPS)
    def test_change_request_created_at(self, bad_ts):
        with pytest.raises(ValueError):
            _make_change_request(created_at=bad_ts)

    @pytest.mark.parametrize("bad_ts", INVALID_TIMESTAMPS)
    def test_change_plan_created_at(self, bad_ts):
        with pytest.raises(ValueError):
            _make_change_plan(created_at=bad_ts)

    @pytest.mark.parametrize("bad_ts", INVALID_TIMESTAMPS)
    def test_change_execution_started_at(self, bad_ts):
        with pytest.raises(ValueError):
            _make_change_execution(started_at=bad_ts)

    @pytest.mark.parametrize("bad_ts", INVALID_TIMESTAMPS)
    def test_change_approval_binding_approved_at(self, bad_ts):
        with pytest.raises(ValueError):
            _make_change_approval_binding(approved_at=bad_ts)

    @pytest.mark.parametrize("bad_ts", INVALID_TIMESTAMPS)
    def test_change_evidence_collected_at(self, bad_ts):
        with pytest.raises(ValueError):
            _make_change_evidence(collected_at=bad_ts)

    @pytest.mark.parametrize("bad_ts", INVALID_TIMESTAMPS)
    def test_rollback_plan_triggered_at(self, bad_ts):
        with pytest.raises(ValueError):
            _make_rollback_plan(triggered_at=bad_ts)

    @pytest.mark.parametrize("bad_ts", INVALID_TIMESTAMPS)
    def test_change_outcome_completed_at(self, bad_ts):
        with pytest.raises(ValueError):
            _make_change_outcome(completed_at=bad_ts)

    @pytest.mark.parametrize("bad_ts", INVALID_TIMESTAMPS)
    def test_change_impact_assessment_assessed_at(self, bad_ts):
        with pytest.raises(ValueError):
            _make_change_impact_assessment(assessed_at=bad_ts)

    def test_accepts_iso_z_suffix(self):
        cr = _make_change_request(created_at="2025-06-15T10:00:00Z")
        assert cr.created_at == "2025-06-15T10:00:00Z"

    def test_accepts_iso_offset(self):
        cr = _make_change_request(created_at="2025-06-15T10:00:00+05:30")
        assert cr.created_at == "2025-06-15T10:00:00+05:30"

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError):
            _make_change_request(created_at="")


# ===================================================================
# 10. Enum-typed fields reject wrong types
# ===================================================================


class TestEnumTypeValidation:
    def test_change_request_change_type_rejects_string(self):
        with pytest.raises(ValueError, match="change_type"):
            _make_change_request(change_type="routing_rule")

    def test_change_request_scope_rejects_string(self):
        with pytest.raises(ValueError, match="scope"):
            _make_change_request(scope="global")

    def test_change_request_status_rejects_string(self):
        with pytest.raises(ValueError, match="status"):
            _make_change_request(status="draft")

    def test_change_request_rollout_mode_rejects_string(self):
        with pytest.raises(ValueError, match="rollout_mode"):
            _make_change_request(rollout_mode="canary")

    def test_change_plan_rollout_mode_rejects_string(self):
        with pytest.raises(ValueError, match="rollout_mode"):
            _make_change_plan(rollout_mode="immediate")

    def test_change_step_status_rejects_string(self):
        with pytest.raises(ValueError, match="status"):
            _make_change_step(status="draft")

    def test_change_execution_status_rejects_string(self):
        with pytest.raises(ValueError, match="status"):
            _make_change_execution(status="in_progress")

    def test_change_execution_rollout_mode_rejects_string(self):
        with pytest.raises(ValueError, match="rollout_mode"):
            _make_change_execution(rollout_mode="canary")

    def test_change_evidence_kind_rejects_string(self):
        with pytest.raises(ValueError, match="kind"):
            _make_change_evidence(kind="log_entry")

    def test_rollback_plan_disposition_rejects_string(self):
        with pytest.raises(ValueError, match="disposition"):
            _make_rollback_plan(disposition="triggered")

    def test_change_outcome_status_rejects_string(self):
        with pytest.raises(ValueError, match="status"):
            _make_change_outcome(status="completed")

    def test_change_outcome_rollback_disposition_rejects_string(self):
        with pytest.raises(ValueError, match="rollback_disposition"):
            _make_change_outcome(rollback_disposition="not_needed")

    def test_change_request_change_type_rejects_wrong_enum(self):
        with pytest.raises(ValueError, match="change_type"):
            _make_change_request(change_type=ChangeScope.GLOBAL)

    def test_change_request_scope_rejects_wrong_enum(self):
        with pytest.raises(ValueError, match="scope"):
            _make_change_request(scope=ChangeType.ROUTING_RULE)

    def test_change_request_status_rejects_int(self):
        with pytest.raises(ValueError, match="status"):
            _make_change_request(status=0)

    def test_change_request_rollout_mode_rejects_none(self):
        with pytest.raises(ValueError, match="rollout_mode"):
            _make_change_request(rollout_mode=None)


# ===================================================================
# 11. Bool-typed fields reject non-booleans
# ===================================================================


class TestBoolValidation:
    @pytest.mark.parametrize("bad_val", [0, 1, "true", "yes", None])
    def test_approval_required_rejects_non_bool(self, bad_val):
        with pytest.raises(ValueError, match="approval_required"):
            _make_change_request(approval_required=bad_val)

    @pytest.mark.parametrize("bad_val", [0, 1, "true", None])
    def test_approved_rejects_non_bool(self, bad_val):
        with pytest.raises(ValueError, match="approved"):
            _make_change_approval_binding(approved=bad_val)

    @pytest.mark.parametrize("bad_val", [0, 1, "true", None])
    def test_success_rejects_non_bool(self, bad_val):
        with pytest.raises(ValueError, match="success"):
            _make_change_outcome(success=bad_val)

    @pytest.mark.parametrize("bad_val", [0, 1, "false", None])
    def test_improvement_observed_rejects_non_bool(self, bad_val):
        with pytest.raises(ValueError, match="improvement_observed"):
            _make_change_outcome(improvement_observed=bad_val)

    def test_approval_required_accepts_true(self):
        cr = _make_change_request(approval_required=True)
        assert cr.approval_required is True

    def test_approval_required_accepts_false(self):
        cr = _make_change_request(approval_required=False)
        assert cr.approval_required is False

    def test_approved_accepts_true(self):
        cab = _make_change_approval_binding(approved=True)
        assert cab.approved is True

    def test_approved_accepts_false(self):
        cab = _make_change_approval_binding(approved=False)
        assert cab.approved is False

    def test_success_accepts_true(self):
        co = _make_change_outcome(success=True)
        assert co.success is True

    def test_success_accepts_false(self):
        co = _make_change_outcome(success=False)
        assert co.success is False

    def test_improvement_observed_accepts_true(self):
        co = _make_change_outcome(improvement_observed=True)
        assert co.improvement_observed is True

    def test_improvement_observed_accepts_false(self):
        co = _make_change_outcome(improvement_observed=False)
        assert co.improvement_observed is False


# ===================================================================
# 12. metadata / step_ids / rollback_steps freeze
# ===================================================================


class TestFreezeContainers:
    def test_change_request_metadata_is_mapping_proxy(self):
        cr = _make_change_request(metadata={"a": 1})
        assert isinstance(cr.metadata, MappingProxyType)

    def test_change_request_metadata_immutable(self):
        cr = _make_change_request(metadata={"a": 1})
        with pytest.raises(TypeError):
            cr.metadata["b"] = 2  # type: ignore[index]

    def test_change_plan_metadata_is_mapping_proxy(self):
        cp = _make_change_plan(metadata={"x": "y"})
        assert isinstance(cp.metadata, MappingProxyType)

    def test_change_plan_step_ids_is_tuple(self):
        cp = _make_change_plan(step_ids=["s1", "s2"])
        assert isinstance(cp.step_ids, tuple)
        assert cp.step_ids == ("s1", "s2")

    def test_change_step_metadata_is_mapping_proxy(self):
        cs = _make_change_step(metadata={"k": "v"})
        assert isinstance(cs.metadata, MappingProxyType)

    def test_change_execution_metadata_is_mapping_proxy(self):
        ce = _make_change_execution(metadata={"k": "v"})
        assert isinstance(ce.metadata, MappingProxyType)

    def test_change_evidence_metadata_is_mapping_proxy(self):
        ev = _make_change_evidence(metadata={"k": "v"})
        assert isinstance(ev.metadata, MappingProxyType)

    def test_rollback_plan_rollback_steps_is_tuple(self):
        rb = _make_rollback_plan(rollback_steps=["a", "b", "c"])
        assert isinstance(rb.rollback_steps, tuple)
        assert rb.rollback_steps == ("a", "b", "c")

    def test_change_outcome_metadata_is_mapping_proxy(self):
        co = _make_change_outcome(metadata={"k": "v"})
        assert isinstance(co.metadata, MappingProxyType)

    def test_nested_dict_in_metadata_frozen(self):
        cr = _make_change_request(metadata={"inner": {"deep": True}})
        assert isinstance(cr.metadata["inner"], MappingProxyType)

    def test_empty_metadata_is_mapping_proxy(self):
        cr = _make_change_request()
        assert isinstance(cr.metadata, MappingProxyType)

    def test_empty_step_ids_is_tuple(self):
        cp = _make_change_plan(step_ids=())
        assert isinstance(cp.step_ids, tuple)
        assert cp.step_ids == ()

    def test_empty_rollback_steps_is_tuple(self):
        rb = _make_rollback_plan(rollback_steps=())
        assert isinstance(rb.rollback_steps, tuple)
        assert rb.rollback_steps == ()


# ===================================================================
# 13. Cross-field: ChangeExecution steps_completed + steps_failed <= steps_total
# ===================================================================


class TestChangeExecutionCrossField:
    def test_valid_boundary_equal(self):
        ce = _make_change_execution(steps_total=5, steps_completed=3, steps_failed=2)
        assert ce.steps_completed + ce.steps_failed == ce.steps_total

    def test_valid_under_total(self):
        ce = _make_change_execution(steps_total=10, steps_completed=3, steps_failed=2)
        assert ce.steps_completed + ce.steps_failed < ce.steps_total

    def test_rejects_over_total(self):
        with pytest.raises(ValueError, match="steps_completed.*steps_failed.*steps_total"):
            _make_change_execution(steps_total=5, steps_completed=3, steps_failed=3)

    def test_rejects_completed_alone_exceeding(self):
        with pytest.raises(ValueError, match="steps_completed.*steps_failed.*steps_total"):
            _make_change_execution(steps_total=2, steps_completed=3, steps_failed=0)

    def test_rejects_failed_alone_exceeding(self):
        with pytest.raises(ValueError, match="steps_completed.*steps_failed.*steps_total"):
            _make_change_execution(steps_total=2, steps_completed=0, steps_failed=3)

    def test_all_zeros(self):
        ce = _make_change_execution(steps_total=0, steps_completed=0, steps_failed=0)
        assert ce.steps_total == 0


# ===================================================================
# 14. Default values work correctly
# ===================================================================


class TestDefaultValues:
    def test_change_request_defaults(self):
        cr = ChangeRequest(
            change_id="cr-d",
            title="default test",
            created_at=_ts(),
        )
        assert cr.change_type is ChangeType.CONFIGURATION
        assert cr.scope is ChangeScope.GLOBAL
        assert cr.status is ChangeStatus.DRAFT
        assert cr.rollout_mode is RolloutMode.IMMEDIATE
        assert cr.approval_required is True
        assert cr.priority == "normal"
        assert cr.recommendation_id == ""
        assert cr.scope_ref_id == ""
        assert cr.description == ""
        assert cr.requested_by == ""
        assert cr.reason == ""

    def test_change_plan_defaults(self):
        cp = ChangePlan(
            plan_id="pl-d",
            change_id="cr-d",
            title="default plan",
            created_at=_ts(),
        )
        assert cp.rollout_mode is RolloutMode.IMMEDIATE
        assert cp.estimated_duration_seconds == 0.0
        assert cp.step_ids == ()
        assert cp.rollback_plan_id == ""

    def test_change_step_defaults(self):
        cs = ChangeStep(
            step_id="st-d",
            plan_id="pl-d",
            change_id="cr-d",
            action="run",
        )
        assert cs.ordinal == 0
        assert cs.status is ChangeStatus.DRAFT
        assert cs.target_ref_id == ""
        assert cs.description == ""
        assert cs.started_at == ""
        assert cs.completed_at == ""

    def test_change_execution_defaults(self):
        ce = ChangeExecution(
            execution_id="ex-d",
            change_id="cr-d",
            plan_id="pl-d",
            started_at=_ts(),
        )
        assert ce.status is ChangeStatus.IN_PROGRESS
        assert ce.rollout_mode is RolloutMode.IMMEDIATE
        assert ce.steps_total == 0
        assert ce.steps_completed == 0
        assert ce.steps_failed == 0
        assert ce.completed_at == ""

    def test_change_approval_binding_defaults(self):
        cab = ChangeApprovalBinding(
            approval_id="ap-d",
            change_id="cr-d",
            approved_by="system",
            approved_at=_ts(),
        )
        assert cab.approved is False
        assert cab.reason == ""

    def test_change_evidence_defaults(self):
        ev = ChangeEvidence(
            evidence_id="ev-d",
            change_id="cr-d",
            collected_at=_ts(),
        )
        assert ev.kind is ChangeEvidenceKind.LOG_ENTRY
        assert ev.metric_name == ""
        assert ev.metric_value == 0.0
        assert ev.description == ""

    def test_rollback_plan_defaults(self):
        rb = RollbackPlan(
            rollback_id="rb-d",
            change_id="cr-d",
            triggered_at=_ts(),
        )
        assert rb.disposition is RollbackDisposition.NOT_NEEDED
        assert rb.rollback_steps == ()
        assert rb.reason == ""
        assert rb.completed_at == ""

    def test_change_outcome_defaults(self):
        co = ChangeOutcome(
            outcome_id="oc-d",
            change_id="cr-d",
            execution_id="ex-d",
            completed_at=_ts(),
        )
        assert co.status is ChangeStatus.COMPLETED
        assert co.success is True
        assert co.improvement_observed is False
        assert co.improvement_pct == 0.0
        assert co.rollback_disposition is RollbackDisposition.NOT_NEEDED
        assert co.evidence_count == 0

    def test_change_impact_assessment_defaults(self):
        cia = ChangeImpactAssessment(
            assessment_id="ia-d",
            change_id="cr-d",
            metric_name="latency",
            assessed_at=_ts(),
        )
        assert cia.baseline_value == 0.0
        assert cia.current_value == 0.0
        assert cia.improvement_pct == 0.0
        assert cia.confidence == 1.0
        assert cia.assessment_window_seconds == 0.0


# ===================================================================
# 15. Edge cases / boundary values
# ===================================================================


class TestEdgeCases:
    def test_single_char_ids(self):
        cr = _make_change_request(change_id="x", title="y")
        assert cr.change_id == "x"
        assert cr.title == "y"

    def test_very_long_id(self):
        long_id = "a" * 10_000
        cr = _make_change_request(change_id=long_id)
        assert cr.change_id == long_id

    def test_unicode_in_text_fields(self):
        cr = _make_change_request(
            change_id="cr-unicode",
            title="Enable \u00e9scalation \u2014 r\u00e8gle",
            description="\u4f60\u597d\u4e16\u754c",
        )
        assert "\u00e9" in cr.title
        assert cr.description == "\u4f60\u597d\u4e16\u754c"

    def test_change_execution_all_completed(self):
        ce = _make_change_execution(steps_total=100, steps_completed=100, steps_failed=0)
        assert ce.steps_completed == 100

    def test_change_execution_all_failed(self):
        ce = _make_change_execution(steps_total=100, steps_completed=0, steps_failed=100)
        assert ce.steps_failed == 100

    def test_zero_duration_plan(self):
        cp = _make_change_plan(estimated_duration_seconds=0.0)
        assert cp.estimated_duration_seconds == 0.0

    def test_large_duration_plan(self):
        cp = _make_change_plan(estimated_duration_seconds=1e12)
        assert cp.estimated_duration_seconds == 1e12

    def test_integer_accepted_for_non_negative_float(self):
        cp = _make_change_plan(estimated_duration_seconds=120)
        assert cp.estimated_duration_seconds == 120.0

    def test_integer_accepted_for_unit_float(self):
        cia = _make_change_impact_assessment(confidence=1)
        assert cia.confidence == 1.0

    def test_confidence_boundary_zero(self):
        cia = _make_change_impact_assessment(confidence=0.0)
        assert cia.confidence == 0.0

    def test_confidence_boundary_one(self):
        cia = _make_change_impact_assessment(confidence=1.0)
        assert cia.confidence == 1.0

    def test_confidence_just_below_zero(self):
        with pytest.raises(ValueError, match="confidence"):
            _make_change_impact_assessment(confidence=-0.0001)

    def test_confidence_just_above_one(self):
        with pytest.raises(ValueError, match="confidence"):
            _make_change_impact_assessment(confidence=1.0001)

    def test_metadata_with_list_values_frozen_to_tuple(self):
        cr = _make_change_request(metadata={"tags": ["a", "b"]})
        assert isinstance(cr.metadata["tags"], tuple)
        assert cr.metadata["tags"] == ("a", "b")

    def test_step_ids_from_list_input(self):
        cp = _make_change_plan(step_ids=["x", "y", "z"])
        assert cp.step_ids == ("x", "y", "z")

    def test_rollback_steps_from_list_input(self):
        rb = _make_rollback_plan(rollback_steps=["r1"])
        assert rb.rollback_steps == ("r1",)

    def test_all_change_types_accepted_in_change_request(self):
        for ct in ChangeType:
            cr = _make_change_request(change_type=ct)
            assert cr.change_type is ct

    def test_all_change_scopes_accepted_in_change_request(self):
        for cs in ChangeScope:
            cr = _make_change_request(scope=cs)
            assert cr.scope is cs

    def test_all_change_statuses_accepted_in_change_request(self):
        for st in ChangeStatus:
            cr = _make_change_request(status=st)
            assert cr.status is st

    def test_all_rollout_modes_accepted_in_change_request(self):
        for rm in RolloutMode:
            cr = _make_change_request(rollout_mode=rm)
            assert cr.rollout_mode is rm

    def test_all_rollback_dispositions_accepted_in_rollback_plan(self):
        for rd in RollbackDisposition:
            rb = _make_rollback_plan(disposition=rd)
            assert rb.disposition is rd

    def test_all_evidence_kinds_accepted_in_change_evidence(self):
        for ek in ChangeEvidenceKind:
            ev = _make_change_evidence(kind=ek)
            assert ev.kind is ek

    def test_to_dict_step_ids_becomes_list(self):
        cp = _make_change_plan(step_ids=("s1",))
        d = cp.to_dict()
        assert isinstance(d["step_ids"], list)

    def test_to_dict_rollback_steps_becomes_list(self):
        rb = _make_rollback_plan(rollback_steps=("r1",))
        d = rb.to_dict()
        assert isinstance(d["rollback_steps"], list)

    def test_to_dict_change_request_returns_dict(self):
        cr = _make_change_request()
        d = cr.to_dict()
        assert isinstance(d, dict)
        assert d["change_id"] == "cr-1"

    def test_change_request_metadata_not_shared_with_input(self):
        original = {"key": "val"}
        cr = _make_change_request(metadata=original)
        original["key"] = "modified"
        assert cr.metadata["key"] == "val"

    def test_change_plan_step_ids_not_shared_with_input(self):
        original = ["s1", "s2"]
        cp = _make_change_plan(step_ids=original)
        original.append("s3")
        assert cp.step_ids == ("s1", "s2")
