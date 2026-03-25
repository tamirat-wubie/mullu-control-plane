"""Tests for product operations contracts."""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.product_ops import (
    LifecycleMilestone,
    LifecycleStatus,
    ProductVersionRecord,
    PromotionDisposition,
    PromotionRecord,
    ReleaseAssessment,
    ReleaseClosureReport,
    ReleaseGate,
    ReleaseKind,
    ReleaseRecord,
    ReleaseRiskLevel,
    ReleaseSnapshot,
    ReleaseStatus,
    ReleaseViolation,
    RollbackRecord,
    RollbackStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-01T09:00:00+00:00"


def _product_version(**overrides) -> ProductVersionRecord:
    defaults = dict(
        version_id="ver-001",
        product_id="prod-001",
        tenant_id="t-001",
        version_label="1.0.0",
        lifecycle_status=LifecycleStatus.ACTIVE,
        created_at=TS,
    )
    defaults.update(overrides)
    return ProductVersionRecord(**defaults)


def _release(**overrides) -> ReleaseRecord:
    defaults = dict(
        release_id="rel-001",
        version_id="ver-001",
        tenant_id="t-001",
        kind=ReleaseKind.MINOR,
        status=ReleaseStatus.DRAFT,
        target_environment="staging",
        gate_count=3,
        gates_passed=1,
        created_at=TS,
    )
    defaults.update(overrides)
    return ReleaseRecord(**defaults)


def _gate(**overrides) -> ReleaseGate:
    defaults = dict(
        gate_id="gate-001",
        release_id="rel-001",
        tenant_id="t-001",
        gate_name="smoke-test",
        passed=True,
        reason="All checks green",
        evaluated_at=TS,
    )
    defaults.update(overrides)
    return ReleaseGate(**defaults)


def _promotion(**overrides) -> PromotionRecord:
    defaults = dict(
        promotion_id="promo-001",
        release_id="rel-001",
        tenant_id="t-001",
        from_environment="staging",
        to_environment="production",
        disposition=PromotionDisposition.PROMOTED,
        decided_at=TS,
    )
    defaults.update(overrides)
    return PromotionRecord(**defaults)


def _rollback(**overrides) -> RollbackRecord:
    defaults = dict(
        rollback_id="rb-001",
        release_id="rel-001",
        tenant_id="t-001",
        reason="Critical bug found",
        status=RollbackStatus.INITIATED,
        initiated_at=TS,
    )
    defaults.update(overrides)
    return RollbackRecord(**defaults)


def _milestone(**overrides) -> LifecycleMilestone:
    defaults = dict(
        milestone_id="ms-001",
        version_id="ver-001",
        tenant_id="t-001",
        from_status=LifecycleStatus.ACTIVE,
        to_status=LifecycleStatus.DEPRECATED,
        reason="Superseded by v2",
        recorded_at=TS,
    )
    defaults.update(overrides)
    return LifecycleMilestone(**defaults)


def _assessment(**overrides) -> ReleaseAssessment:
    defaults = dict(
        assessment_id="assess-001",
        release_id="rel-001",
        tenant_id="t-001",
        risk_level=ReleaseRiskLevel.LOW,
        readiness_score=0.9,
        customer_impact_score=0.1,
        assessed_at=TS,
    )
    defaults.update(overrides)
    return ReleaseAssessment(**defaults)


def _snapshot(**overrides) -> ReleaseSnapshot:
    defaults = dict(
        snapshot_id="snap-001",
        total_versions=5,
        total_releases=10,
        total_gates=20,
        total_promotions=8,
        total_rollbacks=2,
        total_milestones=4,
        total_assessments=6,
        total_violations=1,
        captured_at=TS,
    )
    defaults.update(overrides)
    return ReleaseSnapshot(**defaults)


def _violation(**overrides) -> ReleaseViolation:
    defaults = dict(
        violation_id="viol-001",
        tenant_id="t-001",
        release_id="rel-001",
        operation="promote",
        reason="Gates not passed",
        detected_at=TS,
    )
    defaults.update(overrides)
    return ReleaseViolation(**defaults)


def _closure(**overrides) -> ReleaseClosureReport:
    defaults = dict(
        report_id="rpt-001",
        tenant_id="t-001",
        total_versions=5,
        total_releases=10,
        total_promotions=8,
        total_rollbacks=2,
        total_milestones=4,
        total_violations=1,
        closed_at=TS,
    )
    defaults.update(overrides)
    return ReleaseClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestReleaseStatusEnum:
    def test_members(self):
        assert len(ReleaseStatus) == 6

    @pytest.mark.parametrize("member,value", [
        (ReleaseStatus.DRAFT, "draft"),
        (ReleaseStatus.READY, "ready"),
        (ReleaseStatus.IN_PROGRESS, "in_progress"),
        (ReleaseStatus.COMPLETED, "completed"),
        (ReleaseStatus.FAILED, "failed"),
        (ReleaseStatus.ROLLED_BACK, "rolled_back"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_lookup_by_value(self):
        assert ReleaseStatus("draft") is ReleaseStatus.DRAFT

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ReleaseStatus("unknown")


class TestReleaseKindEnum:
    def test_members(self):
        assert len(ReleaseKind) == 5

    @pytest.mark.parametrize("member,value", [
        (ReleaseKind.MAJOR, "major"),
        (ReleaseKind.MINOR, "minor"),
        (ReleaseKind.PATCH, "patch"),
        (ReleaseKind.HOTFIX, "hotfix"),
        (ReleaseKind.ROLLBACK, "rollback"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_lookup_by_value(self):
        assert ReleaseKind("hotfix") is ReleaseKind.HOTFIX

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ReleaseKind("nightly")


class TestPromotionDispositionEnum:
    def test_members(self):
        assert len(PromotionDisposition) == 4

    @pytest.mark.parametrize("member,value", [
        (PromotionDisposition.PROMOTED, "promoted"),
        (PromotionDisposition.BLOCKED, "blocked"),
        (PromotionDisposition.DEFERRED, "deferred"),
        (PromotionDisposition.ROLLED_BACK, "rolled_back"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_lookup_by_value(self):
        assert PromotionDisposition("blocked") is PromotionDisposition.BLOCKED

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            PromotionDisposition("cancelled")


class TestRollbackStatusEnum:
    def test_members(self):
        assert len(RollbackStatus) == 3

    @pytest.mark.parametrize("member,value", [
        (RollbackStatus.INITIATED, "initiated"),
        (RollbackStatus.COMPLETED, "completed"),
        (RollbackStatus.FAILED, "failed"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_lookup_by_value(self):
        assert RollbackStatus("completed") is RollbackStatus.COMPLETED

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            RollbackStatus("pending")


class TestLifecycleStatusEnum:
    def test_members(self):
        assert len(LifecycleStatus) == 4

    @pytest.mark.parametrize("member,value", [
        (LifecycleStatus.ACTIVE, "active"),
        (LifecycleStatus.DEPRECATED, "deprecated"),
        (LifecycleStatus.END_OF_LIFE, "end_of_life"),
        (LifecycleStatus.RETIRED, "retired"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_lookup_by_value(self):
        assert LifecycleStatus("retired") is LifecycleStatus.RETIRED

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            LifecycleStatus("archived")


class TestReleaseRiskLevelEnum:
    def test_members(self):
        assert len(ReleaseRiskLevel) == 4

    @pytest.mark.parametrize("member,value", [
        (ReleaseRiskLevel.LOW, "low"),
        (ReleaseRiskLevel.MEDIUM, "medium"),
        (ReleaseRiskLevel.HIGH, "high"),
        (ReleaseRiskLevel.CRITICAL, "critical"),
    ])
    def test_values(self, member, value):
        assert member.value == value

    def test_lookup_by_value(self):
        assert ReleaseRiskLevel("critical") is ReleaseRiskLevel.CRITICAL

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ReleaseRiskLevel("extreme")


# ===================================================================
# ProductVersionRecord
# ===================================================================


class TestProductVersionRecord:
    def test_valid_construction(self):
        r = _product_version()
        assert r.version_id == "ver-001"
        assert r.product_id == "prod-001"
        assert r.tenant_id == "t-001"
        assert r.version_label == "1.0.0"
        assert r.lifecycle_status is LifecycleStatus.ACTIVE
        assert r.created_at == TS

    def test_frozen(self):
        r = _product_version()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.version_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _product_version(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)
        with pytest.raises(TypeError):
            r.metadata["new"] = "x"  # type: ignore[index]

    def test_to_dict(self):
        r = _product_version(metadata={"a": 1})
        d = r.to_dict()
        assert d["version_id"] == "ver-001"
        assert d["metadata"] == {"a": 1}
        assert isinstance(d["lifecycle_status"], LifecycleStatus)

    def test_to_dict_returns_plain_dict_metadata(self):
        r = _product_version(metadata={"x": "y"})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field", [
        "version_id", "product_id", "tenant_id", "version_label",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _product_version(**{field: ""})

    @pytest.mark.parametrize("field", [
        "version_id", "product_id", "tenant_id", "version_label",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _product_version(**{field: "   "})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _product_version(created_at="not-a-date")

    def test_empty_datetime(self):
        with pytest.raises(ValueError):
            _product_version(created_at="")

    def test_invalid_lifecycle_status(self):
        with pytest.raises(ValueError):
            _product_version(lifecycle_status="active")  # type: ignore[arg-type]

    @pytest.mark.parametrize("status", list(LifecycleStatus))
    def test_all_lifecycle_statuses(self, status):
        r = _product_version(lifecycle_status=status)
        assert r.lifecycle_status is status

    def test_nested_metadata_frozen(self):
        r = _product_version(metadata={"nested": {"a": 1}})
        assert isinstance(r.metadata["nested"], MappingProxyType)

    def test_metadata_defaults_empty(self):
        r = _product_version()
        assert r.metadata == {}

    def test_iso_z_suffix_accepted(self):
        r = _product_version(created_at="2025-01-01T00:00:00Z")
        assert r.created_at == "2025-01-01T00:00:00Z"


# ===================================================================
# ReleaseRecord
# ===================================================================


class TestReleaseRecord:
    def test_valid_construction(self):
        r = _release()
        assert r.release_id == "rel-001"
        assert r.version_id == "ver-001"
        assert r.tenant_id == "t-001"
        assert r.kind is ReleaseKind.MINOR
        assert r.status is ReleaseStatus.DRAFT
        assert r.target_environment == "staging"
        assert r.gate_count == 3
        assert r.gates_passed == 1

    def test_frozen(self):
        r = _release()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.release_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _release(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _release().to_dict()
        assert d["release_id"] == "rel-001"
        assert isinstance(d["kind"], ReleaseKind)
        assert isinstance(d["status"], ReleaseStatus)

    @pytest.mark.parametrize("field", [
        "release_id", "version_id", "tenant_id", "target_environment",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _release(**{field: ""})

    @pytest.mark.parametrize("field", [
        "release_id", "version_id", "tenant_id", "target_environment",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _release(**{field: "   "})

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            _release(kind="minor")  # type: ignore[arg-type]

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _release(status="draft")  # type: ignore[arg-type]

    @pytest.mark.parametrize("kind", list(ReleaseKind))
    def test_all_kinds(self, kind):
        r = _release(kind=kind)
        assert r.kind is kind

    @pytest.mark.parametrize("status", list(ReleaseStatus))
    def test_all_statuses(self, status):
        r = _release(status=status)
        assert r.status is status

    def test_negative_gate_count_rejected(self):
        with pytest.raises(ValueError):
            _release(gate_count=-1)

    def test_negative_gates_passed_rejected(self):
        with pytest.raises(ValueError):
            _release(gates_passed=-1)

    def test_zero_gate_counts(self):
        r = _release(gate_count=0, gates_passed=0)
        assert r.gate_count == 0
        assert r.gates_passed == 0

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _release(created_at="nope")

    def test_bool_gate_count_rejected(self):
        with pytest.raises(ValueError):
            _release(gate_count=True)  # type: ignore[arg-type]

    def test_float_gate_count_rejected(self):
        with pytest.raises(ValueError):
            _release(gate_count=1.5)  # type: ignore[arg-type]


# ===================================================================
# ReleaseGate
# ===================================================================


class TestReleaseGate:
    def test_valid_construction(self):
        r = _gate()
        assert r.gate_id == "gate-001"
        assert r.release_id == "rel-001"
        assert r.tenant_id == "t-001"
        assert r.gate_name == "smoke-test"
        assert r.passed is True
        assert r.reason == "All checks green"

    def test_frozen(self):
        r = _gate()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.gate_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _gate(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _gate().to_dict()
        assert d["gate_id"] == "gate-001"
        assert d["passed"] is True
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field", [
        "gate_id", "release_id", "tenant_id", "gate_name",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _gate(**{field: ""})

    @pytest.mark.parametrize("field", [
        "gate_id", "release_id", "tenant_id", "gate_name",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _gate(**{field: "   "})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _gate(evaluated_at="bad")

    def test_passed_false(self):
        r = _gate(passed=False)
        assert r.passed is False

    def test_empty_reason_allowed(self):
        r = _gate(reason="")
        assert r.reason == ""

    def test_reason_with_content(self):
        r = _gate(reason="Failed: timeout")
        assert r.reason == "Failed: timeout"


# ===================================================================
# PromotionRecord
# ===================================================================


class TestPromotionRecord:
    def test_valid_construction(self):
        r = _promotion()
        assert r.promotion_id == "promo-001"
        assert r.release_id == "rel-001"
        assert r.tenant_id == "t-001"
        assert r.from_environment == "staging"
        assert r.to_environment == "production"
        assert r.disposition is PromotionDisposition.PROMOTED

    def test_frozen(self):
        r = _promotion()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.promotion_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _promotion(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _promotion().to_dict()
        assert d["promotion_id"] == "promo-001"
        assert isinstance(d["disposition"], PromotionDisposition)

    @pytest.mark.parametrize("field", [
        "promotion_id", "release_id", "tenant_id",
        "from_environment", "to_environment",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _promotion(**{field: ""})

    @pytest.mark.parametrize("field", [
        "promotion_id", "release_id", "tenant_id",
        "from_environment", "to_environment",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _promotion(**{field: "   "})

    def test_invalid_disposition(self):
        with pytest.raises(ValueError):
            _promotion(disposition="promoted")  # type: ignore[arg-type]

    @pytest.mark.parametrize("disp", list(PromotionDisposition))
    def test_all_dispositions(self, disp):
        r = _promotion(disposition=disp)
        assert r.disposition is disp

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _promotion(decided_at="nope")


# ===================================================================
# RollbackRecord
# ===================================================================


class TestRollbackRecord:
    def test_valid_construction(self):
        r = _rollback()
        assert r.rollback_id == "rb-001"
        assert r.release_id == "rel-001"
        assert r.tenant_id == "t-001"
        assert r.reason == "Critical bug found"
        assert r.status is RollbackStatus.INITIATED

    def test_frozen(self):
        r = _rollback()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.rollback_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _rollback(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _rollback().to_dict()
        assert d["rollback_id"] == "rb-001"
        assert isinstance(d["status"], RollbackStatus)

    @pytest.mark.parametrize("field", [
        "rollback_id", "release_id", "tenant_id", "reason",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _rollback(**{field: ""})

    @pytest.mark.parametrize("field", [
        "rollback_id", "release_id", "tenant_id", "reason",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _rollback(**{field: "   "})

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _rollback(status="initiated")  # type: ignore[arg-type]

    @pytest.mark.parametrize("status", list(RollbackStatus))
    def test_all_statuses(self, status):
        r = _rollback(status=status)
        assert r.status is status

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _rollback(initiated_at="bad")


# ===================================================================
# LifecycleMilestone
# ===================================================================


class TestLifecycleMilestone:
    def test_valid_construction(self):
        r = _milestone()
        assert r.milestone_id == "ms-001"
        assert r.version_id == "ver-001"
        assert r.tenant_id == "t-001"
        assert r.from_status is LifecycleStatus.ACTIVE
        assert r.to_status is LifecycleStatus.DEPRECATED
        assert r.reason == "Superseded by v2"

    def test_frozen(self):
        r = _milestone()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.milestone_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _milestone(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _milestone().to_dict()
        assert d["milestone_id"] == "ms-001"
        assert isinstance(d["from_status"], LifecycleStatus)
        assert isinstance(d["to_status"], LifecycleStatus)

    @pytest.mark.parametrize("field", [
        "milestone_id", "version_id", "tenant_id",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _milestone(**{field: ""})

    @pytest.mark.parametrize("field", [
        "milestone_id", "version_id", "tenant_id",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _milestone(**{field: "   "})

    def test_invalid_from_status(self):
        with pytest.raises(ValueError):
            _milestone(from_status="active")  # type: ignore[arg-type]

    def test_invalid_to_status(self):
        with pytest.raises(ValueError):
            _milestone(to_status="deprecated")  # type: ignore[arg-type]

    @pytest.mark.parametrize("status", list(LifecycleStatus))
    def test_all_from_statuses(self, status):
        r = _milestone(from_status=status)
        assert r.from_status is status

    @pytest.mark.parametrize("status", list(LifecycleStatus))
    def test_all_to_statuses(self, status):
        r = _milestone(to_status=status)
        assert r.to_status is status

    def test_empty_reason_allowed(self):
        r = _milestone(reason="")
        assert r.reason == ""

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _milestone(recorded_at="bad")

    def test_same_from_to_status(self):
        r = _milestone(from_status=LifecycleStatus.ACTIVE, to_status=LifecycleStatus.ACTIVE)
        assert r.from_status is r.to_status


# ===================================================================
# ReleaseAssessment
# ===================================================================


class TestReleaseAssessment:
    def test_valid_construction(self):
        r = _assessment()
        assert r.assessment_id == "assess-001"
        assert r.release_id == "rel-001"
        assert r.tenant_id == "t-001"
        assert r.risk_level is ReleaseRiskLevel.LOW
        assert r.readiness_score == 0.9
        assert r.customer_impact_score == 0.1

    def test_frozen(self):
        r = _assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.assessment_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _assessment(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _assessment().to_dict()
        assert d["assessment_id"] == "assess-001"
        assert isinstance(d["risk_level"], ReleaseRiskLevel)

    @pytest.mark.parametrize("field", [
        "assessment_id", "release_id", "tenant_id",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: ""})

    @pytest.mark.parametrize("field", [
        "assessment_id", "release_id", "tenant_id",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: "   "})

    def test_invalid_risk_level(self):
        with pytest.raises(ValueError):
            _assessment(risk_level="low")  # type: ignore[arg-type]

    @pytest.mark.parametrize("level", list(ReleaseRiskLevel))
    def test_all_risk_levels(self, level):
        r = _assessment(risk_level=level)
        assert r.risk_level is level

    def test_readiness_score_zero(self):
        r = _assessment(readiness_score=0.0)
        assert r.readiness_score == 0.0

    def test_readiness_score_one(self):
        r = _assessment(readiness_score=1.0)
        assert r.readiness_score == 1.0

    def test_readiness_score_negative(self):
        with pytest.raises(ValueError):
            _assessment(readiness_score=-0.1)

    def test_readiness_score_above_one(self):
        with pytest.raises(ValueError):
            _assessment(readiness_score=1.1)

    def test_customer_impact_zero(self):
        r = _assessment(customer_impact_score=0.0)
        assert r.customer_impact_score == 0.0

    def test_customer_impact_one(self):
        r = _assessment(customer_impact_score=1.0)
        assert r.customer_impact_score == 1.0

    def test_customer_impact_negative(self):
        with pytest.raises(ValueError):
            _assessment(customer_impact_score=-0.01)

    def test_customer_impact_above_one(self):
        with pytest.raises(ValueError):
            _assessment(customer_impact_score=1.01)

    def test_readiness_score_bool_rejected(self):
        with pytest.raises(ValueError):
            _assessment(readiness_score=True)  # type: ignore[arg-type]

    def test_customer_impact_bool_rejected(self):
        with pytest.raises(ValueError):
            _assessment(customer_impact_score=False)  # type: ignore[arg-type]

    def test_readiness_score_nan_rejected(self):
        with pytest.raises(ValueError):
            _assessment(readiness_score=float("nan"))

    def test_readiness_score_inf_rejected(self):
        with pytest.raises(ValueError):
            _assessment(readiness_score=float("inf"))

    def test_customer_impact_nan_rejected(self):
        with pytest.raises(ValueError):
            _assessment(customer_impact_score=float("nan"))

    def test_customer_impact_inf_rejected(self):
        with pytest.raises(ValueError):
            _assessment(customer_impact_score=float("inf"))

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at="bad")

    def test_int_readiness_score_accepted(self):
        r = _assessment(readiness_score=1)
        assert r.readiness_score == 1.0

    def test_int_customer_impact_accepted(self):
        r = _assessment(customer_impact_score=0)
        assert r.customer_impact_score == 0.0


# ===================================================================
# ReleaseSnapshot
# ===================================================================


class TestReleaseSnapshot:
    def test_valid_construction(self):
        r = _snapshot()
        assert r.snapshot_id == "snap-001"
        assert r.total_versions == 5
        assert r.total_releases == 10
        assert r.total_gates == 20
        assert r.total_promotions == 8
        assert r.total_rollbacks == 2
        assert r.total_milestones == 4
        assert r.total_assessments == 6
        assert r.total_violations == 1

    def test_frozen(self):
        r = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.snapshot_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _snapshot(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _snapshot().to_dict()
        assert d["snapshot_id"] == "snap-001"
        assert d["total_versions"] == 5
        assert isinstance(d["metadata"], dict)

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_whitespace_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="   ")

    @pytest.mark.parametrize("field", [
        "total_versions", "total_releases", "total_gates",
        "total_promotions", "total_rollbacks", "total_milestones",
        "total_assessments", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_versions", "total_releases", "total_gates",
        "total_promotions", "total_rollbacks", "total_milestones",
        "total_assessments", "total_violations",
    ])
    def test_zero_accepted(self, field):
        r = _snapshot(**{field: 0})
        assert getattr(r, field) == 0

    @pytest.mark.parametrize("field", [
        "total_versions", "total_releases", "total_gates",
        "total_promotions", "total_rollbacks", "total_milestones",
        "total_assessments", "total_violations",
    ])
    def test_bool_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_versions", "total_releases", "total_gates",
        "total_promotions", "total_rollbacks", "total_milestones",
        "total_assessments", "total_violations",
    ])
    def test_float_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: 1.5})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")

    def test_all_zeros(self):
        r = _snapshot(
            total_versions=0, total_releases=0, total_gates=0,
            total_promotions=0, total_rollbacks=0, total_milestones=0,
            total_assessments=0, total_violations=0,
        )
        assert r.total_versions == 0


# ===================================================================
# ReleaseViolation
# ===================================================================


class TestReleaseViolation:
    def test_valid_construction(self):
        r = _violation()
        assert r.violation_id == "viol-001"
        assert r.tenant_id == "t-001"
        assert r.release_id == "rel-001"
        assert r.operation == "promote"
        assert r.reason == "Gates not passed"

    def test_frozen(self):
        r = _violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.violation_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _violation(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _violation().to_dict()
        assert d["violation_id"] == "viol-001"
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "release_id", "operation", "reason",
    ])
    def test_empty_string_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: ""})

    @pytest.mark.parametrize("field", [
        "violation_id", "tenant_id", "release_id", "operation", "reason",
    ])
    def test_whitespace_only_rejected(self, field):
        with pytest.raises(ValueError):
            _violation(**{field: "   "})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _violation(detected_at="bad")


# ===================================================================
# ReleaseClosureReport
# ===================================================================


class TestReleaseClosureReport:
    def test_valid_construction(self):
        r = _closure()
        assert r.report_id == "rpt-001"
        assert r.tenant_id == "t-001"
        assert r.total_versions == 5
        assert r.total_releases == 10
        assert r.total_promotions == 8
        assert r.total_rollbacks == 2
        assert r.total_milestones == 4
        assert r.total_violations == 1

    def test_frozen(self):
        r = _closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.report_id = "other"  # type: ignore[misc]

    def test_metadata_frozen(self):
        r = _closure(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _closure().to_dict()
        assert d["report_id"] == "rpt-001"
        assert isinstance(d["metadata"], dict)

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            _closure(report_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _closure(tenant_id="")

    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError):
            _closure(report_id="   ")

    def test_whitespace_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _closure(tenant_id="   ")

    @pytest.mark.parametrize("field", [
        "total_versions", "total_releases", "total_promotions",
        "total_rollbacks", "total_milestones", "total_violations",
    ])
    def test_negative_int_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", [
        "total_versions", "total_releases", "total_promotions",
        "total_rollbacks", "total_milestones", "total_violations",
    ])
    def test_zero_accepted(self, field):
        r = _closure(**{field: 0})
        assert getattr(r, field) == 0

    @pytest.mark.parametrize("field", [
        "total_versions", "total_releases", "total_promotions",
        "total_rollbacks", "total_milestones", "total_violations",
    ])
    def test_bool_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: True})

    @pytest.mark.parametrize("field", [
        "total_versions", "total_releases", "total_promotions",
        "total_rollbacks", "total_milestones", "total_violations",
    ])
    def test_float_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: 1.0})

    def test_invalid_datetime(self):
        with pytest.raises(ValueError):
            _closure(closed_at="bad")

    def test_all_zeros(self):
        r = _closure(
            total_versions=0, total_releases=0, total_promotions=0,
            total_rollbacks=0, total_milestones=0, total_violations=0,
        )
        assert r.total_versions == 0


# ===================================================================
# Cross-cutting / integration
# ===================================================================


class TestCrossCutting:
    """Cross-cutting tests for shared patterns."""

    def test_product_version_slots(self):
        r = _product_version()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_release_slots(self):
        r = _release()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_gate_slots(self):
        r = _gate()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_promotion_slots(self):
        r = _promotion()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_rollback_slots(self):
        r = _rollback()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_milestone_slots(self):
        r = _milestone()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_assessment_slots(self):
        r = _assessment()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_snapshot_slots(self):
        r = _snapshot()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_violation_slots(self):
        r = _violation()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_closure_slots(self):
        r = _closure()
        assert hasattr(r, "__slots__") or "__slots__" in type(r).__dict__

    def test_product_version_equality(self):
        a = _product_version()
        b = _product_version()
        assert a == b

    def test_release_equality(self):
        a = _release()
        b = _release()
        assert a == b

    def test_gate_equality(self):
        a = _gate()
        b = _gate()
        assert a == b

    def test_promotion_equality(self):
        a = _promotion()
        b = _promotion()
        assert a == b

    def test_rollback_equality(self):
        a = _rollback()
        b = _rollback()
        assert a == b

    def test_milestone_equality(self):
        a = _milestone()
        b = _milestone()
        assert a == b

    def test_assessment_equality(self):
        a = _assessment()
        b = _assessment()
        assert a == b

    def test_snapshot_equality(self):
        a = _snapshot()
        b = _snapshot()
        assert a == b

    def test_violation_equality(self):
        a = _violation()
        b = _violation()
        assert a == b

    def test_closure_equality(self):
        a = _closure()
        b = _closure()
        assert a == b

    def test_product_version_inequality(self):
        a = _product_version(version_id="a")
        b = _product_version(version_id="b")
        assert a != b

    def test_release_inequality(self):
        a = _release(release_id="a")
        b = _release(release_id="b")
        assert a != b

    def test_to_dict_keys_product_version(self):
        d = _product_version().to_dict()
        expected = {"version_id", "product_id", "tenant_id", "version_label",
                    "lifecycle_status", "created_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_release(self):
        d = _release().to_dict()
        expected = {"release_id", "version_id", "tenant_id", "kind", "status",
                    "target_environment", "gate_count", "gates_passed",
                    "created_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_gate(self):
        d = _gate().to_dict()
        expected = {"gate_id", "release_id", "tenant_id", "gate_name",
                    "passed", "reason", "evaluated_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_promotion(self):
        d = _promotion().to_dict()
        expected = {"promotion_id", "release_id", "tenant_id",
                    "from_environment", "to_environment", "disposition",
                    "decided_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_rollback(self):
        d = _rollback().to_dict()
        expected = {"rollback_id", "release_id", "tenant_id", "reason",
                    "status", "initiated_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_milestone(self):
        d = _milestone().to_dict()
        expected = {"milestone_id", "version_id", "tenant_id", "from_status",
                    "to_status", "reason", "recorded_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_assessment(self):
        d = _assessment().to_dict()
        expected = {"assessment_id", "release_id", "tenant_id", "risk_level",
                    "readiness_score", "customer_impact_score", "assessed_at",
                    "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_snapshot(self):
        d = _snapshot().to_dict()
        expected = {"snapshot_id", "total_versions", "total_releases",
                    "total_gates", "total_promotions", "total_rollbacks",
                    "total_milestones", "total_assessments",
                    "total_violations", "captured_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_violation(self):
        d = _violation().to_dict()
        expected = {"violation_id", "tenant_id", "release_id", "operation",
                    "reason", "detected_at", "metadata"}
        assert set(d.keys()) == expected

    def test_to_dict_keys_closure(self):
        d = _closure().to_dict()
        expected = {"report_id", "tenant_id", "total_versions",
                    "total_releases", "total_promotions", "total_rollbacks",
                    "total_milestones", "total_violations", "closed_at",
                    "metadata"}
        assert set(d.keys()) == expected

    def test_nested_dict_metadata_product_version(self):
        r = _product_version(metadata={"a": {"b": [1, 2]}})
        assert isinstance(r.metadata["a"], MappingProxyType)
        assert r.metadata["a"]["b"] == (1, 2)

    def test_nested_dict_metadata_release(self):
        r = _release(metadata={"a": {"b": [1, 2]}})
        assert isinstance(r.metadata["a"], MappingProxyType)
        assert r.metadata["a"]["b"] == (1, 2)

    def test_list_in_metadata_frozen_to_tuple(self):
        r = _gate(metadata={"items": [1, 2, 3]})
        assert r.metadata["items"] == (1, 2, 3)

    def test_set_in_metadata_frozen_to_frozenset(self):
        r = _gate(metadata={"tags": {"a", "b"}})
        assert isinstance(r.metadata["tags"], frozenset)

    def test_iso_with_z_suffix_all_records(self):
        ts_z = "2025-01-01T00:00:00Z"
        _product_version(created_at=ts_z)
        _release(created_at=ts_z)
        _gate(evaluated_at=ts_z)
        _promotion(decided_at=ts_z)
        _rollback(initiated_at=ts_z)
        _milestone(recorded_at=ts_z)
        _assessment(assessed_at=ts_z)
        _snapshot(captured_at=ts_z)
        _violation(detected_at=ts_z)
        _closure(closed_at=ts_z)

    def test_iso_with_offset_all_records(self):
        ts_off = "2025-06-01T12:00:00-05:00"
        _product_version(created_at=ts_off)
        _release(created_at=ts_off)
        _gate(evaluated_at=ts_off)
        _promotion(decided_at=ts_off)
        _rollback(initiated_at=ts_off)
        _milestone(recorded_at=ts_off)
        _assessment(assessed_at=ts_off)
        _snapshot(captured_at=ts_off)
        _violation(detected_at=ts_off)
        _closure(closed_at=ts_off)

    def test_large_int_accepted_snapshot(self):
        r = _snapshot(total_versions=999999)
        assert r.total_versions == 999999

    def test_large_int_accepted_closure(self):
        r = _closure(total_versions=999999)
        assert r.total_versions == 999999
