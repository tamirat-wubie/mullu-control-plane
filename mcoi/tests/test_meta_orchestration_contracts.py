"""Comprehensive tests for meta-orchestration contracts.

Covers all 6 enums (member count, values, lookup) and all 10 frozen
dataclasses (valid construction, frozen immutability, metadata as
MappingProxyType, to_dict(), empty-string rejection, invalid-datetime
rejection, non_negative_int validation, unit_float validation,
ExecutionTrace duration_ms custom validation).
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.meta_orchestration import (
    CompositionAssessment,
    CompositionScope,
    CoordinationMode,
    DependencyDisposition,
    ExecutionTrace,
    OrchestrationClosureReport,
    OrchestrationDecision,
    OrchestrationDecisionStatus,
    OrchestrationPlan,
    OrchestrationSnapshot,
    OrchestrationStatus,
    OrchestrationStep,
    OrchestrationStepKind,
    OrchestrationViolation,
    RuntimeBinding,
    StepDependency,
)

# =========================================================================
# Constants — valid datetime for reuse
# =========================================================================

TS = "2025-06-01T12:00:00+00:00"
TS_SHORT = "2025-06-01"


# =========================================================================
# Section 1: Enum tests
# =========================================================================


class TestOrchestrationStatus:
    def test_member_count(self):
        assert len(OrchestrationStatus) == 6

    @pytest.mark.parametrize(
        "member,value",
        [
            (OrchestrationStatus.DRAFT, "draft"),
            (OrchestrationStatus.READY, "ready"),
            (OrchestrationStatus.IN_PROGRESS, "in_progress"),
            (OrchestrationStatus.COMPLETED, "completed"),
            (OrchestrationStatus.FAILED, "failed"),
            (OrchestrationStatus.CANCELLED, "cancelled"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["draft", "ready", "in_progress", "completed", "failed", "cancelled"])
    def test_lookup_by_value(self, value):
        assert OrchestrationStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            OrchestrationStatus("nonexistent")


class TestOrchestrationStepKind:
    def test_member_count(self):
        assert len(OrchestrationStepKind) == 5

    @pytest.mark.parametrize(
        "member,value",
        [
            (OrchestrationStepKind.INVOKE, "invoke"),
            (OrchestrationStepKind.GATE, "gate"),
            (OrchestrationStepKind.TRANSFORM, "transform"),
            (OrchestrationStepKind.FALLBACK, "fallback"),
            (OrchestrationStepKind.ESCALATION, "escalation"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["invoke", "gate", "transform", "fallback", "escalation"])
    def test_lookup_by_value(self, value):
        assert OrchestrationStepKind(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            OrchestrationStepKind("nope")


class TestDependencyDisposition:
    def test_member_count(self):
        assert len(DependencyDisposition) == 4

    @pytest.mark.parametrize(
        "member,value",
        [
            (DependencyDisposition.SATISFIED, "satisfied"),
            (DependencyDisposition.BLOCKED, "blocked"),
            (DependencyDisposition.SKIPPED, "skipped"),
            (DependencyDisposition.FAILED, "failed"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["satisfied", "blocked", "skipped", "failed"])
    def test_lookup_by_value(self, value):
        assert DependencyDisposition(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            DependencyDisposition("xyz")


class TestCoordinationMode:
    def test_member_count(self):
        assert len(CoordinationMode) == 4

    @pytest.mark.parametrize(
        "member,value",
        [
            (CoordinationMode.SEQUENTIAL, "sequential"),
            (CoordinationMode.PARALLEL, "parallel"),
            (CoordinationMode.CONDITIONAL, "conditional"),
            (CoordinationMode.FALLBACK, "fallback"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["sequential", "parallel", "conditional", "fallback"])
    def test_lookup_by_value(self, value):
        assert CoordinationMode(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            CoordinationMode("xyz")


class TestCompositionScope:
    def test_member_count(self):
        assert len(CompositionScope) == 6

    @pytest.mark.parametrize(
        "member,value",
        [
            (CompositionScope.TENANT, "tenant"),
            (CompositionScope.PROGRAM, "program"),
            (CompositionScope.CAMPAIGN, "campaign"),
            (CompositionScope.SERVICE, "service"),
            (CompositionScope.CASE, "case"),
            (CompositionScope.GLOBAL, "global"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["tenant", "program", "campaign", "service", "case", "global"])
    def test_lookup_by_value(self, value):
        assert CompositionScope(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            CompositionScope("xyz")


class TestOrchestrationDecisionStatus:
    def test_member_count(self):
        assert len(OrchestrationDecisionStatus) == 4

    @pytest.mark.parametrize(
        "member,value",
        [
            (OrchestrationDecisionStatus.APPROVED, "approved"),
            (OrchestrationDecisionStatus.DENIED, "denied"),
            (OrchestrationDecisionStatus.DEFERRED, "deferred"),
            (OrchestrationDecisionStatus.ESCALATED, "escalated"),
        ],
    )
    def test_values(self, member, value):
        assert member.value == value

    @pytest.mark.parametrize("value", ["approved", "denied", "deferred", "escalated"])
    def test_lookup_by_value(self, value):
        assert OrchestrationDecisionStatus(value).value == value

    def test_invalid_lookup(self):
        with pytest.raises(ValueError):
            OrchestrationDecisionStatus("xyz")


# =========================================================================
# Section 2: Dataclass tests
# =========================================================================

# ---- OrchestrationPlan ------------------------------------------------


class TestOrchestrationPlan:
    def _make(self, **overrides):
        defaults = dict(
            plan_id="plan-1",
            tenant_id="t-1",
            display_name="My Plan",
            status=OrchestrationStatus.DRAFT,
            coordination_mode=CoordinationMode.SEQUENTIAL,
            scope=CompositionScope.TENANT,
            step_count=3,
            completed_steps=1,
            failed_steps=0,
            created_at=TS,
            metadata={"k": "v"},
        )
        defaults.update(overrides)
        return OrchestrationPlan(**defaults)

    def test_valid_construction(self):
        p = self._make()
        assert p.plan_id == "plan-1"
        assert p.tenant_id == "t-1"
        assert p.display_name == "My Plan"
        assert p.status is OrchestrationStatus.DRAFT
        assert p.coordination_mode is CoordinationMode.SEQUENTIAL
        assert p.scope is CompositionScope.TENANT
        assert p.step_count == 3
        assert p.completed_steps == 1
        assert p.failed_steps == 0

    def test_frozen(self):
        p = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.plan_id = "other"

    def test_metadata_is_mapping_proxy(self):
        p = self._make()
        assert isinstance(p.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        p = self._make()
        d = p.to_dict()
        assert d["status"] is OrchestrationStatus.DRAFT
        assert d["coordination_mode"] is CoordinationMode.SEQUENTIAL
        assert d["scope"] is CompositionScope.TENANT
        assert isinstance(d["metadata"], dict)

    def test_to_dict_metadata_thawed(self):
        p = self._make(metadata={"nested": {"a": 1}})
        d = p.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["nested"], dict)

    def test_short_date_accepted(self):
        p = self._make(created_at=TS_SHORT)
        assert p.created_at == TS_SHORT

    @pytest.mark.parametrize("field_name", ["plan_id", "tenant_id", "display_name"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["plan_id", "tenant_id", "display_name"])
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: "   "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="not-a-date")

    @pytest.mark.parametrize("field_name", ["step_count", "completed_steps", "failed_steps"])
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: -1})

    @pytest.mark.parametrize("field_name", ["step_count", "completed_steps", "failed_steps"])
    def test_bool_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: True})

    @pytest.mark.parametrize("field_name", ["step_count", "completed_steps", "failed_steps"])
    def test_float_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: 1.5})

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            self._make(status="draft")

    def test_invalid_coordination_mode_type(self):
        with pytest.raises(ValueError):
            self._make(coordination_mode="sequential")

    def test_invalid_scope_type(self):
        with pytest.raises(ValueError):
            self._make(scope="tenant")

    @pytest.mark.parametrize("val", [0, 100])
    def test_zero_and_large_int_accepted(self, val):
        p = self._make(step_count=val)
        assert p.step_count == val


# ---- OrchestrationStep ------------------------------------------------


class TestOrchestrationStep:
    def _make(self, **overrides):
        defaults = dict(
            step_id="step-1",
            plan_id="plan-1",
            tenant_id="t-1",
            display_name="Step A",
            kind=OrchestrationStepKind.INVOKE,
            target_runtime="runtime-a",
            target_action="action-a",
            status=OrchestrationStatus.DRAFT,
            sequence_order=0,
            created_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return OrchestrationStep(**defaults)

    def test_valid_construction(self):
        s = self._make()
        assert s.step_id == "step-1"
        assert s.kind is OrchestrationStepKind.INVOKE

    def test_frozen(self):
        s = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.step_id = "x"

    def test_metadata_is_mapping_proxy(self):
        s = self._make(metadata={"a": 1})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        s = self._make()
        d = s.to_dict()
        assert d["kind"] is OrchestrationStepKind.INVOKE
        assert d["status"] is OrchestrationStatus.DRAFT

    @pytest.mark.parametrize(
        "field_name",
        ["step_id", "plan_id", "tenant_id", "display_name", "target_runtime", "target_action"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name",
        ["step_id", "plan_id", "tenant_id", "display_name", "target_runtime", "target_action"],
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: "  "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="bad")

    def test_negative_sequence_order(self):
        with pytest.raises(ValueError):
            self._make(sequence_order=-1)

    def test_bool_sequence_order(self):
        with pytest.raises(ValueError):
            self._make(sequence_order=True)

    def test_invalid_kind_type(self):
        with pytest.raises(ValueError):
            self._make(kind="invoke")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            self._make(status="draft")

    def test_short_date_accepted(self):
        s = self._make(created_at=TS_SHORT)
        assert s.created_at == TS_SHORT

    @pytest.mark.parametrize("kind", list(OrchestrationStepKind))
    def test_all_step_kinds(self, kind):
        s = self._make(kind=kind)
        assert s.kind is kind


# ---- StepDependency ---------------------------------------------------


class TestStepDependency:
    def _make(self, **overrides):
        defaults = dict(
            dependency_id="dep-1",
            plan_id="plan-1",
            tenant_id="t-1",
            from_step_id="step-1",
            to_step_id="step-2",
            disposition=DependencyDisposition.BLOCKED,
            created_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return StepDependency(**defaults)

    def test_valid_construction(self):
        d = self._make()
        assert d.dependency_id == "dep-1"
        assert d.disposition is DependencyDisposition.BLOCKED

    def test_frozen(self):
        d = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.dependency_id = "x"

    def test_metadata_is_mapping_proxy(self):
        d = self._make(metadata={"x": 1})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = self._make()
        assert d.to_dict()["disposition"] is DependencyDisposition.BLOCKED

    @pytest.mark.parametrize(
        "field_name",
        ["dependency_id", "plan_id", "tenant_id", "from_step_id", "to_step_id"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="nope")

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            self._make(disposition="blocked")

    @pytest.mark.parametrize("disp", list(DependencyDisposition))
    def test_all_dispositions(self, disp):
        d = self._make(disposition=disp)
        assert d.disposition is disp


# ---- RuntimeBinding ---------------------------------------------------


class TestRuntimeBinding:
    def _make(self, **overrides):
        defaults = dict(
            binding_id="bind-1",
            step_id="step-1",
            tenant_id="t-1",
            runtime_name="rt",
            action_name="act",
            config_ref="cfg",
            created_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return RuntimeBinding(**defaults)

    def test_valid_construction(self):
        b = self._make()
        assert b.binding_id == "bind-1"
        assert b.runtime_name == "rt"

    def test_frozen(self):
        b = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            b.binding_id = "x"

    def test_metadata_is_mapping_proxy(self):
        b = self._make(metadata={"z": 2})
        assert isinstance(b.metadata, MappingProxyType)

    def test_to_dict_metadata_thawed(self):
        b = self._make(metadata={"z": 2})
        d = b.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize(
        "field_name",
        ["binding_id", "step_id", "tenant_id", "runtime_name", "action_name", "config_ref"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name",
        ["binding_id", "step_id", "tenant_id", "runtime_name", "action_name", "config_ref"],
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: " "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="bad")

    def test_short_date_accepted(self):
        b = self._make(created_at=TS_SHORT)
        assert b.created_at == TS_SHORT


# ---- OrchestrationDecision --------------------------------------------


class TestOrchestrationDecision:
    def _make(self, **overrides):
        defaults = dict(
            decision_id="dec-1",
            plan_id="plan-1",
            step_id="step-1",
            tenant_id="t-1",
            status=OrchestrationDecisionStatus.APPROVED,
            reason="ok",
            decided_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return OrchestrationDecision(**defaults)

    def test_valid_construction(self):
        d = self._make()
        assert d.decision_id == "dec-1"
        assert d.status is OrchestrationDecisionStatus.APPROVED

    def test_frozen(self):
        d = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.decision_id = "x"

    def test_metadata_is_mapping_proxy(self):
        d = self._make(metadata={"a": 1})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        d = self._make()
        assert d.to_dict()["status"] is OrchestrationDecisionStatus.APPROVED

    @pytest.mark.parametrize(
        "field_name",
        ["decision_id", "plan_id", "step_id", "tenant_id"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(decided_at="nope")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            self._make(status="approved")

    @pytest.mark.parametrize("status", list(OrchestrationDecisionStatus))
    def test_all_statuses(self, status):
        d = self._make(status=status)
        assert d.status is status

    def test_short_date_accepted(self):
        d = self._make(decided_at=TS_SHORT)
        assert d.decided_at == TS_SHORT


# ---- ExecutionTrace ---------------------------------------------------


class TestExecutionTrace:
    def _make(self, **overrides):
        defaults = dict(
            trace_id="tr-1",
            plan_id="plan-1",
            step_id="step-1",
            tenant_id="t-1",
            runtime_name="rt",
            action_name="act",
            status=OrchestrationStatus.COMPLETED,
            duration_ms=42.5,
            created_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return ExecutionTrace(**defaults)

    def test_valid_construction(self):
        t = self._make()
        assert t.trace_id == "tr-1"
        assert t.duration_ms == 42.5

    def test_frozen(self):
        t = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.trace_id = "x"

    def test_metadata_is_mapping_proxy(self):
        t = self._make(metadata={"a": 1})
        assert isinstance(t.metadata, MappingProxyType)

    def test_to_dict_preserves_enum(self):
        t = self._make()
        assert t.to_dict()["status"] is OrchestrationStatus.COMPLETED

    @pytest.mark.parametrize(
        "field_name",
        ["trace_id", "plan_id", "step_id", "tenant_id", "runtime_name", "action_name"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="bad")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            self._make(status="completed")

    # duration_ms custom validation
    def test_duration_ms_zero_accepted(self):
        t = self._make(duration_ms=0.0)
        assert t.duration_ms == 0.0

    def test_duration_ms_int_accepted(self):
        t = self._make(duration_ms=100)
        assert t.duration_ms == 100

    def test_duration_ms_negative_rejected(self):
        with pytest.raises(ValueError, match="duration_ms must be non-negative"):
            self._make(duration_ms=-1.0)

    def test_duration_ms_bool_rejected(self):
        with pytest.raises(ValueError, match="duration_ms must be a number"):
            self._make(duration_ms=True)

    def test_duration_ms_false_bool_rejected(self):
        with pytest.raises(ValueError, match="duration_ms must be a number"):
            self._make(duration_ms=False)

    def test_duration_ms_string_rejected(self):
        with pytest.raises(ValueError):
            self._make(duration_ms="42")

    def test_duration_ms_none_rejected(self):
        with pytest.raises(ValueError):
            self._make(duration_ms=None)

    def test_short_date_accepted(self):
        t = self._make(created_at=TS_SHORT)
        assert t.created_at == TS_SHORT


# ---- OrchestrationSnapshot -------------------------------------------


class TestOrchestrationSnapshot:
    def _make(self, **overrides):
        defaults = dict(
            snapshot_id="snap-1",
            tenant_id="t-1",
            total_plans=5,
            active_plans=2,
            total_steps=10,
            completed_steps=7,
            failed_steps=1,
            total_traces=20,
            total_violations=0,
            captured_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return OrchestrationSnapshot(**defaults)

    def test_valid_construction(self):
        s = self._make()
        assert s.snapshot_id == "snap-1"
        assert s.total_plans == 5

    def test_frozen(self):
        s = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            s.snapshot_id = "x"

    def test_metadata_is_mapping_proxy(self):
        s = self._make(metadata={"a": 1})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict_metadata_thawed(self):
        s = self._make(metadata={"a": 1})
        d = s.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field_name", ["snapshot_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(captured_at="bad")

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_plans",
            "active_plans",
            "total_steps",
            "completed_steps",
            "failed_steps",
            "total_traces",
            "total_violations",
        ],
    )
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: -1})

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_plans",
            "active_plans",
            "total_steps",
            "completed_steps",
            "failed_steps",
            "total_traces",
            "total_violations",
        ],
    )
    def test_bool_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: True})

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_plans",
            "active_plans",
            "total_steps",
            "completed_steps",
            "failed_steps",
            "total_traces",
            "total_violations",
        ],
    )
    def test_float_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: 1.0})

    def test_short_date_accepted(self):
        s = self._make(captured_at=TS_SHORT)
        assert s.captured_at == TS_SHORT


# ---- OrchestrationViolation ------------------------------------------


class TestOrchestrationViolation:
    def _make(self, **overrides):
        defaults = dict(
            violation_id="viol-1",
            plan_id="plan-1",
            tenant_id="t-1",
            operation="op",
            reason="bad",
            detected_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return OrchestrationViolation(**defaults)

    def test_valid_construction(self):
        v = self._make()
        assert v.violation_id == "viol-1"
        assert v.reason == "bad"

    def test_frozen(self):
        v = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            v.violation_id = "x"

    def test_metadata_is_mapping_proxy(self):
        v = self._make(metadata={"a": 1})
        assert isinstance(v.metadata, MappingProxyType)

    def test_to_dict_metadata_thawed(self):
        v = self._make(metadata={"nested": {"b": 2}})
        d = v.to_dict()
        assert isinstance(d["metadata"]["nested"], dict)

    @pytest.mark.parametrize(
        "field_name",
        ["violation_id", "plan_id", "tenant_id", "operation", "reason"],
    )
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    @pytest.mark.parametrize(
        "field_name",
        ["violation_id", "plan_id", "tenant_id", "operation", "reason"],
    )
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: "  "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(detected_at="bad")

    def test_short_date_accepted(self):
        v = self._make(detected_at=TS_SHORT)
        assert v.detected_at == TS_SHORT


# ---- CompositionAssessment -------------------------------------------


class TestCompositionAssessment:
    def _make(self, **overrides):
        defaults = dict(
            assessment_id="assess-1",
            tenant_id="t-1",
            total_plans=10,
            active_plans=3,
            completion_rate=0.7,
            failure_rate=0.1,
            total_violations=2,
            assessed_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return CompositionAssessment(**defaults)

    def test_valid_construction(self):
        a = self._make()
        assert a.assessment_id == "assess-1"
        assert a.completion_rate == 0.7
        assert a.failure_rate == 0.1

    def test_frozen(self):
        a = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            a.assessment_id = "x"

    def test_metadata_is_mapping_proxy(self):
        a = self._make(metadata={"a": 1})
        assert isinstance(a.metadata, MappingProxyType)

    def test_to_dict_metadata_thawed(self):
        a = self._make(metadata={"a": 1})
        d = a.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field_name", ["assessment_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(assessed_at="bad")

    @pytest.mark.parametrize("field_name", ["total_plans", "active_plans", "total_violations"])
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: -1})

    @pytest.mark.parametrize("field_name", ["total_plans", "active_plans", "total_violations"])
    def test_bool_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: True})

    @pytest.mark.parametrize("field_name", ["total_plans", "active_plans", "total_violations"])
    def test_float_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: 1.0})

    # unit_float validation for completion_rate / failure_rate
    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_zero(self, field_name):
        a = self._make(**{field_name: 0.0})
        assert getattr(a, field_name) == 0.0

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_one(self, field_name):
        a = self._make(**{field_name: 1.0})
        assert getattr(a, field_name) == 1.0

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_mid(self, field_name):
        a = self._make(**{field_name: 0.5})
        assert getattr(a, field_name) == 0.5

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_negative_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: -0.1})

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_above_one_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: 1.01})

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_bool_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: True})

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: "0.5"})

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_inf_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: float("inf")})

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_nan_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: float("nan")})

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_int_zero_accepted(self, field_name):
        a = self._make(**{field_name: 0})
        assert getattr(a, field_name) == 0.0

    @pytest.mark.parametrize("field_name", ["completion_rate", "failure_rate"])
    def test_unit_float_int_one_accepted(self, field_name):
        a = self._make(**{field_name: 1})
        assert getattr(a, field_name) == 1.0

    def test_short_date_accepted(self):
        a = self._make(assessed_at=TS_SHORT)
        assert a.assessed_at == TS_SHORT


# ---- OrchestrationClosureReport --------------------------------------


class TestOrchestrationClosureReport:
    def _make(self, **overrides):
        defaults = dict(
            report_id="rpt-1",
            tenant_id="t-1",
            total_plans=5,
            total_steps=20,
            total_traces=30,
            total_decisions=10,
            total_violations=2,
            total_bindings=8,
            created_at=TS,
            metadata={},
        )
        defaults.update(overrides)
        return OrchestrationClosureReport(**defaults)

    def test_valid_construction(self):
        r = self._make()
        assert r.report_id == "rpt-1"
        assert r.total_plans == 5

    def test_frozen(self):
        r = self._make()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.report_id = "x"

    def test_metadata_is_mapping_proxy(self):
        r = self._make(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_metadata_thawed(self):
        r = self._make(metadata={"a": 1})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_empty_string_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: ""})

    @pytest.mark.parametrize("field_name", ["report_id", "tenant_id"])
    def test_whitespace_only_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: "  "})

    def test_invalid_datetime_rejected(self):
        with pytest.raises(ValueError):
            self._make(created_at="bad")

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_plans",
            "total_steps",
            "total_traces",
            "total_decisions",
            "total_violations",
            "total_bindings",
        ],
    )
    def test_negative_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: -1})

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_plans",
            "total_steps",
            "total_traces",
            "total_decisions",
            "total_violations",
            "total_bindings",
        ],
    )
    def test_bool_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: True})

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_plans",
            "total_steps",
            "total_traces",
            "total_decisions",
            "total_violations",
            "total_bindings",
        ],
    )
    def test_float_int_rejected(self, field_name):
        with pytest.raises(ValueError):
            self._make(**{field_name: 1.0})

    @pytest.mark.parametrize(
        "field_name",
        [
            "total_plans",
            "total_steps",
            "total_traces",
            "total_decisions",
            "total_violations",
            "total_bindings",
        ],
    )
    def test_zero_int_accepted(self, field_name):
        r = self._make(**{field_name: 0})
        assert getattr(r, field_name) == 0

    def test_short_date_accepted(self):
        r = self._make(created_at=TS_SHORT)
        assert r.created_at == TS_SHORT


# =========================================================================
# Section 3: Parametrized boundary / cross-cutting tests
# =========================================================================


class TestDatetimeBoundaries:
    """Verify various ISO 8601 formats across all dataclasses with datetime fields."""

    VALID_DATETIMES = [
        "2025-06-01",
        "2025-06-01T00:00:00",
        "2025-06-01T12:30:45+05:30",
        "2025-06-01T12:30:45Z",
        "2025-06-01T12:30:45.123456+00:00",
    ]

    INVALID_DATETIMES = [
        "",
        "   ",
        "not-a-date",
        "2025/06/01",
        "June 1, 2025",
        "12345",
    ]

    @pytest.mark.parametrize("dt", VALID_DATETIMES)
    def test_plan_valid_datetimes(self, dt):
        p = OrchestrationPlan(
            plan_id="p", tenant_id="t", display_name="d",
            created_at=dt,
        )
        assert p.created_at == dt

    @pytest.mark.parametrize("dt", INVALID_DATETIMES)
    def test_plan_invalid_datetimes(self, dt):
        with pytest.raises(ValueError):
            OrchestrationPlan(
                plan_id="p", tenant_id="t", display_name="d",
                created_at=dt,
            )

    @pytest.mark.parametrize("dt", VALID_DATETIMES)
    def test_step_valid_datetimes(self, dt):
        s = OrchestrationStep(
            step_id="s", plan_id="p", tenant_id="t", display_name="d",
            target_runtime="r", target_action="a", created_at=dt,
        )
        assert s.created_at == dt

    @pytest.mark.parametrize("dt", INVALID_DATETIMES)
    def test_step_invalid_datetimes(self, dt):
        with pytest.raises(ValueError):
            OrchestrationStep(
                step_id="s", plan_id="p", tenant_id="t", display_name="d",
                target_runtime="r", target_action="a", created_at=dt,
            )

    @pytest.mark.parametrize("dt", VALID_DATETIMES)
    def test_trace_valid_datetimes(self, dt):
        t = ExecutionTrace(
            trace_id="t", plan_id="p", step_id="s", tenant_id="t",
            runtime_name="r", action_name="a", created_at=dt,
        )
        assert t.created_at == dt

    @pytest.mark.parametrize("dt", INVALID_DATETIMES)
    def test_trace_invalid_datetimes(self, dt):
        with pytest.raises(ValueError):
            ExecutionTrace(
                trace_id="t", plan_id="p", step_id="s", tenant_id="t",
                runtime_name="r", action_name="a", created_at=dt,
            )


class TestMetadataFreezing:
    """Verify metadata deeply frozen and thawed across dataclass types."""

    def test_plan_nested_metadata_frozen(self):
        p = OrchestrationPlan(
            plan_id="p", tenant_id="t", display_name="d",
            created_at=TS, metadata={"nested": {"k": [1, 2]}},
        )
        assert isinstance(p.metadata, MappingProxyType)
        assert isinstance(p.metadata["nested"], MappingProxyType)
        # lists become tuples
        assert p.metadata["nested"]["k"] == (1, 2)

    def test_plan_nested_metadata_thawed(self):
        p = OrchestrationPlan(
            plan_id="p", tenant_id="t", display_name="d",
            created_at=TS, metadata={"nested": {"k": [1, 2]}},
        )
        d = p.to_dict()
        assert isinstance(d["metadata"]["nested"], dict)
        assert isinstance(d["metadata"]["nested"]["k"], list)

    def test_step_empty_metadata(self):
        s = OrchestrationStep(
            step_id="s", plan_id="p", tenant_id="t", display_name="d",
            target_runtime="r", target_action="a", created_at=TS,
        )
        assert isinstance(s.metadata, MappingProxyType)
        assert len(s.metadata) == 0

    def test_violation_metadata_mutation_blocked(self):
        v = OrchestrationViolation(
            violation_id="v", plan_id="p", tenant_id="t",
            operation="op", reason="r", detected_at=TS,
            metadata={"a": 1},
        )
        with pytest.raises(TypeError):
            v.metadata["a"] = 2


class TestNonNegativeIntBoundaries:
    """Cross-cutting parametrized tests for int fields across multiple classes."""

    @pytest.mark.parametrize("val", [-1, -100])
    def test_snapshot_total_plans_negative(self, val):
        with pytest.raises(ValueError):
            OrchestrationSnapshot(
                snapshot_id="s", tenant_id="t", captured_at=TS,
                total_plans=val,
            )

    @pytest.mark.parametrize("val", [0, 1, 999])
    def test_snapshot_total_plans_valid(self, val):
        s = OrchestrationSnapshot(
            snapshot_id="s", tenant_id="t", captured_at=TS,
            total_plans=val,
        )
        assert s.total_plans == val

    def test_closure_report_none_int_rejected(self):
        with pytest.raises(ValueError):
            OrchestrationClosureReport(
                report_id="r", tenant_id="t", created_at=TS,
                total_plans=None,
            )

    def test_plan_string_int_rejected(self):
        with pytest.raises(ValueError):
            OrchestrationPlan(
                plan_id="p", tenant_id="t", display_name="d",
                created_at=TS, step_count="3",
            )


class TestUnitFloatBoundaries:
    """Cross-cutting parametrized tests for unit-float fields."""

    @pytest.mark.parametrize("val", [0.0, 0.5, 1.0, 0, 1])
    def test_completion_rate_valid(self, val):
        a = CompositionAssessment(
            assessment_id="a", tenant_id="t", assessed_at=TS,
            completion_rate=val,
        )
        assert 0.0 <= a.completion_rate <= 1.0

    @pytest.mark.parametrize("val", [-0.001, 1.001, 2.0, -1.0])
    def test_completion_rate_out_of_range(self, val):
        with pytest.raises(ValueError):
            CompositionAssessment(
                assessment_id="a", tenant_id="t", assessed_at=TS,
                completion_rate=val,
            )

    @pytest.mark.parametrize("val", [float("inf"), float("-inf"), float("nan")])
    def test_failure_rate_non_finite_rejected(self, val):
        with pytest.raises(ValueError):
            CompositionAssessment(
                assessment_id="a", tenant_id="t", assessed_at=TS,
                failure_rate=val,
            )

    def test_failure_rate_none_rejected(self):
        with pytest.raises(ValueError):
            CompositionAssessment(
                assessment_id="a", tenant_id="t", assessed_at=TS,
                failure_rate=None,
            )


class TestToDictCompleteness:
    """Ensure to_dict returns all fields for every dataclass."""

    def test_plan_to_dict_keys(self):
        p = OrchestrationPlan(
            plan_id="p", tenant_id="t", display_name="d", created_at=TS,
        )
        keys = set(p.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(p)}
        assert keys == field_names

    def test_step_to_dict_keys(self):
        s = OrchestrationStep(
            step_id="s", plan_id="p", tenant_id="t", display_name="d",
            target_runtime="r", target_action="a", created_at=TS,
        )
        keys = set(s.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(s)}
        assert keys == field_names

    def test_dependency_to_dict_keys(self):
        d = StepDependency(
            dependency_id="d", plan_id="p", tenant_id="t",
            from_step_id="s1", to_step_id="s2", created_at=TS,
        )
        keys = set(d.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(d)}
        assert keys == field_names

    def test_binding_to_dict_keys(self):
        b = RuntimeBinding(
            binding_id="b", step_id="s", tenant_id="t",
            runtime_name="r", action_name="a", config_ref="c", created_at=TS,
        )
        keys = set(b.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(b)}
        assert keys == field_names

    def test_decision_to_dict_keys(self):
        d = OrchestrationDecision(
            decision_id="d", plan_id="p", step_id="s", tenant_id="t",
            reason="r", decided_at=TS,
        )
        keys = set(d.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(d)}
        assert keys == field_names

    def test_trace_to_dict_keys(self):
        t = ExecutionTrace(
            trace_id="t", plan_id="p", step_id="s", tenant_id="t",
            runtime_name="r", action_name="a", created_at=TS,
        )
        keys = set(t.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(t)}
        assert keys == field_names

    def test_snapshot_to_dict_keys(self):
        s = OrchestrationSnapshot(
            snapshot_id="s", tenant_id="t", captured_at=TS,
        )
        keys = set(s.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(s)}
        assert keys == field_names

    def test_violation_to_dict_keys(self):
        v = OrchestrationViolation(
            violation_id="v", plan_id="p", tenant_id="t",
            operation="o", reason="r", detected_at=TS,
        )
        keys = set(v.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(v)}
        assert keys == field_names

    def test_assessment_to_dict_keys(self):
        a = CompositionAssessment(
            assessment_id="a", tenant_id="t", assessed_at=TS,
        )
        keys = set(a.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(a)}
        assert keys == field_names

    def test_closure_to_dict_keys(self):
        r = OrchestrationClosureReport(
            report_id="r", tenant_id="t", created_at=TS,
        )
        keys = set(r.to_dict().keys())
        field_names = {f.name for f in dataclasses.fields(r)}
        assert keys == field_names


class TestEnumFieldsPreservedInToDict:
    """Verify enum values are preserved (not serialised to strings) in to_dict."""

    def test_plan_enums_preserved(self):
        p = OrchestrationPlan(
            plan_id="p", tenant_id="t", display_name="d", created_at=TS,
            status=OrchestrationStatus.FAILED,
            coordination_mode=CoordinationMode.PARALLEL,
            scope=CompositionScope.GLOBAL,
        )
        d = p.to_dict()
        assert isinstance(d["status"], OrchestrationStatus)
        assert isinstance(d["coordination_mode"], CoordinationMode)
        assert isinstance(d["scope"], CompositionScope)

    def test_step_enums_preserved(self):
        s = OrchestrationStep(
            step_id="s", plan_id="p", tenant_id="t", display_name="d",
            target_runtime="r", target_action="a", created_at=TS,
            kind=OrchestrationStepKind.GATE,
            status=OrchestrationStatus.IN_PROGRESS,
        )
        d = s.to_dict()
        assert isinstance(d["kind"], OrchestrationStepKind)
        assert isinstance(d["status"], OrchestrationStatus)

    def test_dependency_enum_preserved(self):
        dep = StepDependency(
            dependency_id="d", plan_id="p", tenant_id="t",
            from_step_id="s1", to_step_id="s2", created_at=TS,
            disposition=DependencyDisposition.SATISFIED,
        )
        d = dep.to_dict()
        assert isinstance(d["disposition"], DependencyDisposition)

    def test_decision_enum_preserved(self):
        dec = OrchestrationDecision(
            decision_id="d", plan_id="p", step_id="s", tenant_id="t",
            reason="r", decided_at=TS,
            status=OrchestrationDecisionStatus.ESCALATED,
        )
        d = dec.to_dict()
        assert isinstance(d["status"], OrchestrationDecisionStatus)

    def test_trace_enum_preserved(self):
        t = ExecutionTrace(
            trace_id="t", plan_id="p", step_id="s", tenant_id="t",
            runtime_name="r", action_name="a", created_at=TS,
            status=OrchestrationStatus.FAILED,
        )
        d = t.to_dict()
        assert isinstance(d["status"], OrchestrationStatus)


class TestAllEnumValuesInDataclasses:
    """Parametrize through all enum members to ensure they are accepted."""

    @pytest.mark.parametrize("status", list(OrchestrationStatus))
    def test_plan_all_statuses(self, status):
        p = OrchestrationPlan(
            plan_id="p", tenant_id="t", display_name="d",
            created_at=TS, status=status,
        )
        assert p.status is status

    @pytest.mark.parametrize("mode", list(CoordinationMode))
    def test_plan_all_coordination_modes(self, mode):
        p = OrchestrationPlan(
            plan_id="p", tenant_id="t", display_name="d",
            created_at=TS, coordination_mode=mode,
        )
        assert p.coordination_mode is mode

    @pytest.mark.parametrize("scope", list(CompositionScope))
    def test_plan_all_scopes(self, scope):
        p = OrchestrationPlan(
            plan_id="p", tenant_id="t", display_name="d",
            created_at=TS, scope=scope,
        )
        assert p.scope is scope

    @pytest.mark.parametrize("status", list(OrchestrationStatus))
    def test_step_all_statuses(self, status):
        s = OrchestrationStep(
            step_id="s", plan_id="p", tenant_id="t", display_name="d",
            target_runtime="r", target_action="a", created_at=TS,
            status=status,
        )
        assert s.status is status

    @pytest.mark.parametrize("status", list(OrchestrationStatus))
    def test_trace_all_statuses(self, status):
        t = ExecutionTrace(
            trace_id="t", plan_id="p", step_id="s", tenant_id="t",
            runtime_name="r", action_name="a", created_at=TS,
            status=status,
        )
        assert t.status is status
