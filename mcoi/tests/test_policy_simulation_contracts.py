"""Comprehensive tests for policy simulation contracts.

Covers enums, dataclass construction, validation, immutability,
freeze_value behavior, default values, and to_dict serialization.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.policy_simulation import (
    SimulationStatus,
    SimulationMode,
    PolicyImpactLevel,
    DiffDisposition,
    AdoptionReadiness,
    SandboxScope,
    PolicySimulationRequest,
    PolicySimulationScenario,
    PolicySimulationResult,
    PolicyDiffRecord,
    RuntimeImpactRecord,
    AdoptionRecommendation,
    SandboxSnapshot,
    SandboxViolation,
    SandboxAssessment,
    SandboxClosureReport,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-07-01T08:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers -- minimal-valid constructors with override support
# ---------------------------------------------------------------------------


def _request(**kw):
    defaults = dict(
        request_id="req-1",
        tenant_id="ten-1",
        display_name="Sim A",
        created_at=TS,
    )
    defaults.update(kw)
    return PolicySimulationRequest(**defaults)


def _scenario(**kw):
    defaults = dict(
        scenario_id="scn-1",
        request_id="req-1",
        tenant_id="ten-1",
        display_name="Scenario A",
        target_runtime="rt-1",
        baseline_outcome="pass",
        simulated_outcome="fail",
        created_at=TS,
    )
    defaults.update(kw)
    return PolicySimulationScenario(**defaults)


def _result(**kw):
    defaults = dict(
        result_id="res-1",
        request_id="req-1",
        tenant_id="ten-1",
        completed_at=TS,
    )
    defaults.update(kw)
    return PolicySimulationResult(**defaults)


def _diff(**kw):
    defaults = dict(
        diff_id="dif-1",
        request_id="req-1",
        tenant_id="ten-1",
        rule_ref="rule-1",
        before_value="old",
        after_value="new",
        created_at=TS,
    )
    defaults.update(kw)
    return PolicyDiffRecord(**defaults)


def _impact(**kw):
    defaults = dict(
        impact_id="imp-1",
        request_id="req-1",
        tenant_id="ten-1",
        target_runtime="rt-1",
        created_at=TS,
    )
    defaults.update(kw)
    return RuntimeImpactRecord(**defaults)


def _recommendation(**kw):
    defaults = dict(
        recommendation_id="rec-1",
        request_id="req-1",
        tenant_id="ten-1",
        recommended_at=TS,
    )
    defaults.update(kw)
    return AdoptionRecommendation(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-1",
        tenant_id="ten-1",
        captured_at=TS,
    )
    defaults.update(kw)
    return SandboxSnapshot(**defaults)


def _violation(**kw):
    defaults = dict(
        violation_id="vio-1",
        tenant_id="ten-1",
        operation="write",
        reason="not allowed",
        detected_at=TS,
    )
    defaults.update(kw)
    return SandboxViolation(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="asm-1",
        tenant_id="ten-1",
        assessed_at=TS,
    )
    defaults.update(kw)
    return SandboxAssessment(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="rpt-1",
        tenant_id="ten-1",
        created_at=TS,
    )
    defaults.update(kw)
    return SandboxClosureReport(**defaults)


# ===================================================================
# ENUM TESTS
# ===================================================================


class TestSimulationStatus:
    def test_member_count(self):
        assert len(SimulationStatus) == 5

    def test_values(self):
        assert SimulationStatus.DRAFT.value == "draft"
        assert SimulationStatus.RUNNING.value == "running"
        assert SimulationStatus.COMPLETED.value == "completed"
        assert SimulationStatus.FAILED.value == "failed"
        assert SimulationStatus.CANCELLED.value == "cancelled"

    def test_members_are_unique(self):
        values = [m.value for m in SimulationStatus]
        assert len(values) == len(set(values))


class TestSimulationMode:
    def test_member_count(self):
        assert len(SimulationMode) == 4

    def test_values(self):
        assert SimulationMode.DRY_RUN.value == "dry_run"
        assert SimulationMode.SHADOW.value == "shadow"
        assert SimulationMode.FULL.value == "full"
        assert SimulationMode.DIFF_ONLY.value == "diff_only"

    def test_members_are_unique(self):
        values = [m.value for m in SimulationMode]
        assert len(values) == len(set(values))


class TestPolicyImpactLevel:
    def test_member_count(self):
        assert len(PolicyImpactLevel) == 5

    def test_values(self):
        assert PolicyImpactLevel.NONE.value == "none"
        assert PolicyImpactLevel.LOW.value == "low"
        assert PolicyImpactLevel.MEDIUM.value == "medium"
        assert PolicyImpactLevel.HIGH.value == "high"
        assert PolicyImpactLevel.CRITICAL.value == "critical"

    def test_members_are_unique(self):
        values = [m.value for m in PolicyImpactLevel]
        assert len(values) == len(set(values))


class TestDiffDisposition:
    def test_member_count(self):
        assert len(DiffDisposition) == 4

    def test_values(self):
        assert DiffDisposition.ADDED.value == "added"
        assert DiffDisposition.REMOVED.value == "removed"
        assert DiffDisposition.MODIFIED.value == "modified"
        assert DiffDisposition.UNCHANGED.value == "unchanged"

    def test_members_are_unique(self):
        values = [m.value for m in DiffDisposition]
        assert len(values) == len(set(values))


class TestAdoptionReadiness:
    def test_member_count(self):
        assert len(AdoptionReadiness) == 4

    def test_values(self):
        assert AdoptionReadiness.READY.value == "ready"
        assert AdoptionReadiness.CAUTION.value == "caution"
        assert AdoptionReadiness.NOT_READY.value == "not_ready"
        assert AdoptionReadiness.BLOCKED.value == "blocked"

    def test_members_are_unique(self):
        values = [m.value for m in AdoptionReadiness]
        assert len(values) == len(set(values))


class TestSandboxScope:
    def test_member_count(self):
        assert len(SandboxScope) == 6

    def test_values(self):
        assert SandboxScope.TENANT.value == "tenant"
        assert SandboxScope.RUNTIME.value == "runtime"
        assert SandboxScope.GLOBAL.value == "global"
        assert SandboxScope.CONSTITUTIONAL.value == "constitutional"
        assert SandboxScope.SERVICE.value == "service"
        assert SandboxScope.FINANCIAL.value == "financial"

    def test_members_are_unique(self):
        values = [m.value for m in SandboxScope]
        assert len(values) == len(set(values))


# ===================================================================
# PolicySimulationRequest TESTS
# ===================================================================


class TestPolicySimulationRequest:
    def test_minimal_construction(self):
        r = _request()
        assert r.request_id == "req-1"
        assert r.tenant_id == "ten-1"
        assert r.display_name == "Sim A"
        assert r.created_at == TS

    def test_defaults(self):
        r = _request()
        assert r.mode is SimulationMode.DRY_RUN
        assert r.scope is SandboxScope.TENANT
        assert r.status is SimulationStatus.DRAFT
        assert r.candidate_rule_count == 0
        assert r.metadata == {}

    def test_full_construction(self):
        r = _request(
            mode=SimulationMode.FULL,
            scope=SandboxScope.GLOBAL,
            status=SimulationStatus.RUNNING,
            candidate_rule_count=10,
            metadata={"key": "val"},
        )
        assert r.mode is SimulationMode.FULL
        assert r.scope is SandboxScope.GLOBAL
        assert r.status is SimulationStatus.RUNNING
        assert r.candidate_rule_count == 10
        assert r.metadata["key"] == "val"

    def test_frozen(self):
        r = _request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.request_id = "other"

    def test_frozen_tenant_id(self):
        r = _request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.tenant_id = "other"

    def test_frozen_display_name(self):
        r = _request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.display_name = "other"

    def test_frozen_mode(self):
        r = _request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.mode = SimulationMode.SHADOW

    def test_frozen_metadata(self):
        r = _request()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.metadata = {}

    def test_request_id_empty_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _request(request_id="")

    def test_request_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _request(request_id="   ")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _request(tenant_id="")

    def test_tenant_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _request(tenant_id="  \t ")

    def test_display_name_empty_rejected(self):
        with pytest.raises(ValueError, match="display_name"):
            _request(display_name="")

    def test_display_name_whitespace_rejected(self):
        with pytest.raises(ValueError, match="display_name"):
            _request(display_name="   ")

    def test_created_at_invalid(self):
        with pytest.raises(ValueError, match="created_at"):
            _request(created_at="not-a-date")

    def test_created_at_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _request(created_at="")

    def test_mode_string_rejected(self):
        with pytest.raises(ValueError, match="mode"):
            _request(mode="dry_run")

    def test_scope_string_rejected(self):
        with pytest.raises(ValueError, match="scope"):
            _request(scope="tenant")

    def test_status_string_rejected(self):
        with pytest.raises(ValueError, match="status"):
            _request(status="draft")

    def test_candidate_rule_count_negative_rejected(self):
        with pytest.raises(ValueError, match="candidate_rule_count"):
            _request(candidate_rule_count=-1)

    def test_candidate_rule_count_bool_rejected(self):
        with pytest.raises(ValueError, match="candidate_rule_count"):
            _request(candidate_rule_count=True)

    def test_candidate_rule_count_float_rejected(self):
        with pytest.raises(ValueError, match="candidate_rule_count"):
            _request(candidate_rule_count=1.5)

    def test_candidate_rule_count_zero_ok(self):
        r = _request(candidate_rule_count=0)
        assert r.candidate_rule_count == 0

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _request(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _request(metadata={"tags": [1, 2, 3]})
        assert isinstance(r.metadata["tags"], tuple)
        assert r.metadata["tags"] == (1, 2, 3)

    def test_to_dict_preserves_enums(self):
        r = _request()
        d = r.to_dict()
        assert d["mode"] is SimulationMode.DRY_RUN
        assert d["scope"] is SandboxScope.TENANT
        assert d["status"] is SimulationStatus.DRAFT

    def test_to_dict_metadata_thawed(self):
        r = _request(metadata={"x": [1, 2]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["x"], list)

    def test_to_dict_returns_all_fields(self):
        r = _request()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names

    def test_short_datetime_accepted(self):
        r = _request(created_at="2025-06-01")
        assert r.created_at == "2025-06-01"

    def test_all_modes(self):
        for mode in SimulationMode:
            r = _request(mode=mode)
            assert r.mode is mode

    def test_all_scopes(self):
        for scope in SandboxScope:
            r = _request(scope=scope)
            assert r.scope is scope

    def test_all_statuses(self):
        for status in SimulationStatus:
            r = _request(status=status)
            assert r.status is status


# ===================================================================
# PolicySimulationScenario TESTS
# ===================================================================


class TestPolicySimulationScenario:
    def test_minimal_construction(self):
        r = _scenario()
        assert r.scenario_id == "scn-1"
        assert r.request_id == "req-1"
        assert r.tenant_id == "ten-1"
        assert r.display_name == "Scenario A"
        assert r.target_runtime == "rt-1"
        assert r.baseline_outcome == "pass"
        assert r.simulated_outcome == "fail"
        assert r.created_at == TS

    def test_defaults(self):
        r = _scenario()
        assert r.impact_level is PolicyImpactLevel.NONE
        assert r.metadata == {}

    def test_full_construction(self):
        r = _scenario(
            impact_level=PolicyImpactLevel.HIGH,
            metadata={"k": "v"},
        )
        assert r.impact_level is PolicyImpactLevel.HIGH
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _scenario()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.scenario_id = "other"

    def test_frozen_request_id(self):
        r = _scenario()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.request_id = "other"

    def test_frozen_target_runtime(self):
        r = _scenario()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.target_runtime = "other"

    def test_scenario_id_empty_rejected(self):
        with pytest.raises(ValueError, match="scenario_id"):
            _scenario(scenario_id="")

    def test_scenario_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="scenario_id"):
            _scenario(scenario_id="   ")

    def test_request_id_empty_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _scenario(request_id="")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _scenario(tenant_id="")

    def test_display_name_empty_rejected(self):
        with pytest.raises(ValueError, match="display_name"):
            _scenario(display_name="")

    def test_target_runtime_empty_rejected(self):
        with pytest.raises(ValueError, match="target_runtime"):
            _scenario(target_runtime="")

    def test_target_runtime_whitespace_rejected(self):
        with pytest.raises(ValueError, match="target_runtime"):
            _scenario(target_runtime="  ")

    def test_baseline_outcome_empty_rejected(self):
        with pytest.raises(ValueError, match="baseline_outcome"):
            _scenario(baseline_outcome="")

    def test_simulated_outcome_empty_rejected(self):
        with pytest.raises(ValueError, match="simulated_outcome"):
            _scenario(simulated_outcome="")

    def test_created_at_invalid(self):
        with pytest.raises(ValueError, match="created_at"):
            _scenario(created_at="bad")

    def test_created_at_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _scenario(created_at="")

    def test_impact_level_string_rejected(self):
        with pytest.raises(ValueError, match="impact_level"):
            _scenario(impact_level="none")

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _scenario(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _scenario(metadata={"lst": [4, 5]})
        assert isinstance(r.metadata["lst"], tuple)

    def test_to_dict_preserves_enums(self):
        r = _scenario()
        d = r.to_dict()
        assert d["impact_level"] is PolicyImpactLevel.NONE

    def test_to_dict_metadata_thawed(self):
        r = _scenario(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["x"], list)

    def test_to_dict_returns_all_fields(self):
        r = _scenario()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names

    def test_all_impact_levels(self):
        for level in PolicyImpactLevel:
            r = _scenario(impact_level=level)
            assert r.impact_level is level


# ===================================================================
# PolicySimulationResult TESTS
# ===================================================================


class TestPolicySimulationResult:
    def test_minimal_construction(self):
        r = _result()
        assert r.result_id == "res-1"
        assert r.request_id == "req-1"
        assert r.tenant_id == "ten-1"
        assert r.completed_at == TS

    def test_defaults(self):
        r = _result()
        assert r.scenario_count == 0
        assert r.impacted_count == 0
        assert r.max_impact_level is PolicyImpactLevel.NONE
        assert r.adoption_readiness is AdoptionReadiness.READY
        assert r.readiness_score == 0.0
        assert r.metadata == {}

    def test_full_construction(self):
        r = _result(
            scenario_count=5,
            impacted_count=2,
            max_impact_level=PolicyImpactLevel.CRITICAL,
            adoption_readiness=AdoptionReadiness.BLOCKED,
            readiness_score=0.75,
            metadata={"k": "v"},
        )
        assert r.scenario_count == 5
        assert r.impacted_count == 2
        assert r.max_impact_level is PolicyImpactLevel.CRITICAL
        assert r.adoption_readiness is AdoptionReadiness.BLOCKED
        assert r.readiness_score == 0.75
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _result()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.result_id = "other"

    def test_frozen_request_id(self):
        r = _result()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.request_id = "other"

    def test_frozen_readiness_score(self):
        r = _result()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.readiness_score = 0.5

    def test_result_id_empty_rejected(self):
        with pytest.raises(ValueError, match="result_id"):
            _result(result_id="")

    def test_result_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="result_id"):
            _result(result_id="   ")

    def test_request_id_empty_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _result(request_id="")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _result(tenant_id="")

    def test_completed_at_invalid(self):
        with pytest.raises(ValueError, match="completed_at"):
            _result(completed_at="bad")

    def test_completed_at_empty(self):
        with pytest.raises(ValueError, match="completed_at"):
            _result(completed_at="")

    def test_scenario_count_negative_rejected(self):
        with pytest.raises(ValueError, match="scenario_count"):
            _result(scenario_count=-1)

    def test_scenario_count_bool_rejected(self):
        with pytest.raises(ValueError, match="scenario_count"):
            _result(scenario_count=True)

    def test_impacted_count_negative_rejected(self):
        with pytest.raises(ValueError, match="impacted_count"):
            _result(impacted_count=-1)

    def test_impacted_count_bool_rejected(self):
        with pytest.raises(ValueError, match="impacted_count"):
            _result(impacted_count=True)

    def test_max_impact_level_string_rejected(self):
        with pytest.raises(ValueError, match="max_impact_level"):
            _result(max_impact_level="none")

    def test_adoption_readiness_string_rejected(self):
        with pytest.raises(ValueError, match="adoption_readiness"):
            _result(adoption_readiness="ready")

    def test_readiness_score_negative_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _result(readiness_score=-0.1)

    def test_readiness_score_above_one_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _result(readiness_score=1.1)

    def test_readiness_score_bool_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _result(readiness_score=True)

    def test_readiness_score_zero_ok(self):
        r = _result(readiness_score=0.0)
        assert r.readiness_score == 0.0

    def test_readiness_score_one_ok(self):
        r = _result(readiness_score=1.0)
        assert r.readiness_score == 1.0

    def test_readiness_score_mid_ok(self):
        r = _result(readiness_score=0.5)
        assert r.readiness_score == 0.5

    def test_readiness_score_int_zero_ok(self):
        r = _result(readiness_score=0)
        assert r.readiness_score == 0.0

    def test_readiness_score_int_one_ok(self):
        r = _result(readiness_score=1)
        assert r.readiness_score == 1.0

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _result(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        r = _result()
        d = r.to_dict()
        assert d["max_impact_level"] is PolicyImpactLevel.NONE
        assert d["adoption_readiness"] is AdoptionReadiness.READY

    def test_to_dict_metadata_thawed(self):
        r = _result(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["x"], list)

    def test_to_dict_returns_all_fields(self):
        r = _result()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names

    def test_all_impact_levels(self):
        for level in PolicyImpactLevel:
            r = _result(max_impact_level=level)
            assert r.max_impact_level is level

    def test_all_adoption_readiness(self):
        for readiness in AdoptionReadiness:
            r = _result(adoption_readiness=readiness)
            assert r.adoption_readiness is readiness


# ===================================================================
# PolicyDiffRecord TESTS
# ===================================================================


class TestPolicyDiffRecord:
    def test_minimal_construction(self):
        r = _diff()
        assert r.diff_id == "dif-1"
        assert r.request_id == "req-1"
        assert r.tenant_id == "ten-1"
        assert r.rule_ref == "rule-1"
        assert r.before_value == "old"
        assert r.after_value == "new"
        assert r.created_at == TS

    def test_defaults(self):
        r = _diff()
        assert r.disposition is DiffDisposition.UNCHANGED
        assert r.metadata == {}

    def test_full_construction(self):
        r = _diff(
            disposition=DiffDisposition.ADDED,
            metadata={"k": "v"},
        )
        assert r.disposition is DiffDisposition.ADDED
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _diff()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.diff_id = "other"

    def test_frozen_rule_ref(self):
        r = _diff()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.rule_ref = "other"

    def test_frozen_before_value(self):
        r = _diff()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.before_value = "other"

    def test_diff_id_empty_rejected(self):
        with pytest.raises(ValueError, match="diff_id"):
            _diff(diff_id="")

    def test_diff_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="diff_id"):
            _diff(diff_id="   ")

    def test_request_id_empty_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _diff(request_id="")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _diff(tenant_id="")

    def test_rule_ref_empty_rejected(self):
        with pytest.raises(ValueError, match="rule_ref"):
            _diff(rule_ref="")

    def test_rule_ref_whitespace_rejected(self):
        with pytest.raises(ValueError, match="rule_ref"):
            _diff(rule_ref="  \t ")

    def test_before_value_empty_rejected(self):
        with pytest.raises(ValueError, match="before_value"):
            _diff(before_value="")

    def test_after_value_empty_rejected(self):
        with pytest.raises(ValueError, match="after_value"):
            _diff(after_value="")

    def test_created_at_invalid(self):
        with pytest.raises(ValueError, match="created_at"):
            _diff(created_at="bad")

    def test_created_at_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _diff(created_at="")

    def test_disposition_string_rejected(self):
        with pytest.raises(ValueError, match="disposition"):
            _diff(disposition="added")

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _diff(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _diff(metadata={"lst": [1, 2]})
        assert isinstance(r.metadata["lst"], tuple)

    def test_to_dict_preserves_enums(self):
        r = _diff()
        d = r.to_dict()
        assert d["disposition"] is DiffDisposition.UNCHANGED

    def test_to_dict_metadata_thawed(self):
        r = _diff(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_returns_all_fields(self):
        r = _diff()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names

    def test_all_dispositions(self):
        for disp in DiffDisposition:
            r = _diff(disposition=disp)
            assert r.disposition is disp


# ===================================================================
# RuntimeImpactRecord TESTS
# ===================================================================


class TestRuntimeImpactRecord:
    def test_minimal_construction(self):
        r = _impact()
        assert r.impact_id == "imp-1"
        assert r.request_id == "req-1"
        assert r.tenant_id == "ten-1"
        assert r.target_runtime == "rt-1"
        assert r.created_at == TS

    def test_defaults(self):
        r = _impact()
        assert r.impact_level is PolicyImpactLevel.NONE
        assert r.affected_actions == 0
        assert r.blocked_actions == 0
        assert r.metadata == {}

    def test_full_construction(self):
        r = _impact(
            impact_level=PolicyImpactLevel.MEDIUM,
            affected_actions=10,
            blocked_actions=3,
            metadata={"k": "v"},
        )
        assert r.impact_level is PolicyImpactLevel.MEDIUM
        assert r.affected_actions == 10
        assert r.blocked_actions == 3
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _impact()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.impact_id = "other"

    def test_frozen_target_runtime(self):
        r = _impact()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.target_runtime = "other"

    def test_frozen_affected_actions(self):
        r = _impact()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.affected_actions = 99

    def test_impact_id_empty_rejected(self):
        with pytest.raises(ValueError, match="impact_id"):
            _impact(impact_id="")

    def test_impact_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="impact_id"):
            _impact(impact_id="   ")

    def test_request_id_empty_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _impact(request_id="")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _impact(tenant_id="")

    def test_target_runtime_empty_rejected(self):
        with pytest.raises(ValueError, match="target_runtime"):
            _impact(target_runtime="")

    def test_target_runtime_whitespace_rejected(self):
        with pytest.raises(ValueError, match="target_runtime"):
            _impact(target_runtime="  ")

    def test_created_at_invalid(self):
        with pytest.raises(ValueError, match="created_at"):
            _impact(created_at="bad")

    def test_created_at_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _impact(created_at="")

    def test_impact_level_string_rejected(self):
        with pytest.raises(ValueError, match="impact_level"):
            _impact(impact_level="none")

    def test_affected_actions_negative_rejected(self):
        with pytest.raises(ValueError, match="affected_actions"):
            _impact(affected_actions=-1)

    def test_affected_actions_bool_rejected(self):
        with pytest.raises(ValueError, match="affected_actions"):
            _impact(affected_actions=True)

    def test_blocked_actions_negative_rejected(self):
        with pytest.raises(ValueError, match="blocked_actions"):
            _impact(blocked_actions=-1)

    def test_blocked_actions_bool_rejected(self):
        with pytest.raises(ValueError, match="blocked_actions"):
            _impact(blocked_actions=True)

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _impact(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _impact(metadata={"lst": [1, 2]})
        assert isinstance(r.metadata["lst"], tuple)

    def test_to_dict_preserves_enums(self):
        r = _impact()
        d = r.to_dict()
        assert d["impact_level"] is PolicyImpactLevel.NONE

    def test_to_dict_metadata_thawed(self):
        r = _impact(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_returns_all_fields(self):
        r = _impact()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names

    def test_all_impact_levels(self):
        for level in PolicyImpactLevel:
            r = _impact(impact_level=level)
            assert r.impact_level is level


# ===================================================================
# AdoptionRecommendation TESTS
# ===================================================================


class TestAdoptionRecommendation:
    def test_minimal_construction(self):
        r = _recommendation()
        assert r.recommendation_id == "rec-1"
        assert r.request_id == "req-1"
        assert r.tenant_id == "ten-1"
        assert r.recommended_at == TS

    def test_defaults(self):
        r = _recommendation()
        assert r.readiness is AdoptionReadiness.READY
        assert r.readiness_score == 0.0
        assert r.reason == ""
        assert r.metadata == {}

    def test_full_construction(self):
        r = _recommendation(
            readiness=AdoptionReadiness.CAUTION,
            readiness_score=0.65,
            reason="some concern",
            metadata={"k": "v"},
        )
        assert r.readiness is AdoptionReadiness.CAUTION
        assert r.readiness_score == 0.65
        assert r.reason == "some concern"
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _recommendation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.recommendation_id = "other"

    def test_frozen_readiness(self):
        r = _recommendation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.readiness = AdoptionReadiness.BLOCKED

    def test_frozen_readiness_score(self):
        r = _recommendation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.readiness_score = 0.5

    def test_recommendation_id_empty_rejected(self):
        with pytest.raises(ValueError, match="recommendation_id"):
            _recommendation(recommendation_id="")

    def test_recommendation_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="recommendation_id"):
            _recommendation(recommendation_id="   ")

    def test_request_id_empty_rejected(self):
        with pytest.raises(ValueError, match="request_id"):
            _recommendation(request_id="")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _recommendation(tenant_id="")

    def test_recommended_at_invalid(self):
        with pytest.raises(ValueError, match="recommended_at"):
            _recommendation(recommended_at="bad")

    def test_recommended_at_empty(self):
        with pytest.raises(ValueError, match="recommended_at"):
            _recommendation(recommended_at="")

    def test_readiness_string_rejected(self):
        with pytest.raises(ValueError, match="readiness"):
            _recommendation(readiness="ready")

    def test_readiness_score_negative_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _recommendation(readiness_score=-0.01)

    def test_readiness_score_above_one_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _recommendation(readiness_score=1.01)

    def test_readiness_score_bool_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _recommendation(readiness_score=True)

    def test_readiness_score_zero_ok(self):
        r = _recommendation(readiness_score=0.0)
        assert r.readiness_score == 0.0

    def test_readiness_score_one_ok(self):
        r = _recommendation(readiness_score=1.0)
        assert r.readiness_score == 1.0

    def test_readiness_score_int_zero_ok(self):
        r = _recommendation(readiness_score=0)
        assert r.readiness_score == 0.0

    def test_readiness_score_int_one_ok(self):
        r = _recommendation(readiness_score=1)
        assert r.readiness_score == 1.0

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _recommendation(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict_preserves_enums(self):
        r = _recommendation()
        d = r.to_dict()
        assert d["readiness"] is AdoptionReadiness.READY

    def test_to_dict_metadata_thawed(self):
        r = _recommendation(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_returns_all_fields(self):
        r = _recommendation()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names

    def test_all_readiness_levels(self):
        for readiness in AdoptionReadiness:
            r = _recommendation(readiness=readiness)
            assert r.readiness is readiness


# ===================================================================
# SandboxSnapshot TESTS
# ===================================================================


class TestSandboxSnapshot:
    def test_minimal_construction(self):
        r = _snapshot()
        assert r.snapshot_id == "snap-1"
        assert r.tenant_id == "ten-1"
        assert r.captured_at == TS

    def test_defaults(self):
        r = _snapshot()
        assert r.total_simulations == 0
        assert r.completed_simulations == 0
        assert r.total_scenarios == 0
        assert r.total_diffs == 0
        assert r.total_impacts == 0
        assert r.total_violations == 0
        assert r.metadata == {}

    def test_full_construction(self):
        r = _snapshot(
            total_simulations=10,
            completed_simulations=7,
            total_scenarios=20,
            total_diffs=5,
            total_impacts=3,
            total_violations=1,
            metadata={"k": "v"},
        )
        assert r.total_simulations == 10
        assert r.completed_simulations == 7
        assert r.total_scenarios == 20
        assert r.total_diffs == 5
        assert r.total_impacts == 3
        assert r.total_violations == 1
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.snapshot_id = "other"

    def test_frozen_total_simulations(self):
        r = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.total_simulations = 99

    def test_frozen_tenant_id(self):
        r = _snapshot()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.tenant_id = "other"

    def test_snapshot_id_empty_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="")

    def test_snapshot_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="snapshot_id"):
            _snapshot(snapshot_id="   ")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _snapshot(tenant_id="")

    def test_captured_at_invalid(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="bad")

    def test_captured_at_empty(self):
        with pytest.raises(ValueError, match="captured_at"):
            _snapshot(captured_at="")

    def test_total_simulations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_simulations"):
            _snapshot(total_simulations=-1)

    def test_total_simulations_bool_rejected(self):
        with pytest.raises(ValueError, match="total_simulations"):
            _snapshot(total_simulations=True)

    def test_completed_simulations_negative_rejected(self):
        with pytest.raises(ValueError, match="completed_simulations"):
            _snapshot(completed_simulations=-1)

    def test_completed_simulations_bool_rejected(self):
        with pytest.raises(ValueError, match="completed_simulations"):
            _snapshot(completed_simulations=True)

    def test_total_scenarios_negative_rejected(self):
        with pytest.raises(ValueError, match="total_scenarios"):
            _snapshot(total_scenarios=-1)

    def test_total_scenarios_bool_rejected(self):
        with pytest.raises(ValueError, match="total_scenarios"):
            _snapshot(total_scenarios=True)

    def test_total_diffs_negative_rejected(self):
        with pytest.raises(ValueError, match="total_diffs"):
            _snapshot(total_diffs=-1)

    def test_total_diffs_bool_rejected(self):
        with pytest.raises(ValueError, match="total_diffs"):
            _snapshot(total_diffs=True)

    def test_total_impacts_negative_rejected(self):
        with pytest.raises(ValueError, match="total_impacts"):
            _snapshot(total_impacts=-1)

    def test_total_impacts_bool_rejected(self):
        with pytest.raises(ValueError, match="total_impacts"):
            _snapshot(total_impacts=True)

    def test_total_violations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _snapshot(total_violations=-1)

    def test_total_violations_bool_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _snapshot(total_violations=True)

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _snapshot(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _snapshot(metadata={"lst": [1, 2]})
        assert isinstance(r.metadata["lst"], tuple)

    def test_to_dict_metadata_thawed(self):
        r = _snapshot(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["x"], list)

    def test_to_dict_returns_all_fields(self):
        r = _snapshot()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names


# ===================================================================
# SandboxViolation TESTS
# ===================================================================


class TestSandboxViolation:
    def test_minimal_construction(self):
        r = _violation()
        assert r.violation_id == "vio-1"
        assert r.tenant_id == "ten-1"
        assert r.operation == "write"
        assert r.reason == "not allowed"
        assert r.detected_at == TS

    def test_defaults(self):
        r = _violation()
        assert r.metadata == {}

    def test_full_construction(self):
        r = _violation(metadata={"k": "v"})
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.violation_id = "other"

    def test_frozen_operation(self):
        r = _violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.operation = "other"

    def test_frozen_reason(self):
        r = _violation()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.reason = "other"

    def test_violation_id_empty_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _violation(violation_id="")

    def test_violation_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="violation_id"):
            _violation(violation_id="   ")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _violation(tenant_id="")

    def test_operation_empty_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _violation(operation="")

    def test_operation_whitespace_rejected(self):
        with pytest.raises(ValueError, match="operation"):
            _violation(operation="  ")

    def test_reason_empty_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _violation(reason="")

    def test_reason_whitespace_rejected(self):
        with pytest.raises(ValueError, match="reason"):
            _violation(reason="  \t ")

    def test_detected_at_invalid(self):
        with pytest.raises(ValueError, match="detected_at"):
            _violation(detected_at="bad")

    def test_detected_at_empty(self):
        with pytest.raises(ValueError, match="detected_at"):
            _violation(detected_at="")

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _violation(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _violation(metadata={"lst": [1]})
        assert isinstance(r.metadata["lst"], tuple)

    def test_to_dict_metadata_thawed(self):
        r = _violation(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)

    def test_to_dict_returns_all_fields(self):
        r = _violation()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names


# ===================================================================
# SandboxAssessment TESTS
# ===================================================================


class TestSandboxAssessment:
    def test_minimal_construction(self):
        r = _assessment()
        assert r.assessment_id == "asm-1"
        assert r.tenant_id == "ten-1"
        assert r.assessed_at == TS

    def test_defaults(self):
        r = _assessment()
        assert r.total_simulations == 0
        assert r.completion_rate == 0.0
        assert r.avg_readiness_score == 0.0
        assert r.total_violations == 0
        assert r.metadata == {}

    def test_full_construction(self):
        r = _assessment(
            total_simulations=10,
            completion_rate=0.8,
            avg_readiness_score=0.75,
            total_violations=2,
            metadata={"k": "v"},
        )
        assert r.total_simulations == 10
        assert r.completion_rate == 0.8
        assert r.avg_readiness_score == 0.75
        assert r.total_violations == 2
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.assessment_id = "other"

    def test_frozen_completion_rate(self):
        r = _assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.completion_rate = 0.5

    def test_frozen_avg_readiness_score(self):
        r = _assessment()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.avg_readiness_score = 0.5

    def test_assessment_id_empty_rejected(self):
        with pytest.raises(ValueError, match="assessment_id"):
            _assessment(assessment_id="")

    def test_assessment_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="assessment_id"):
            _assessment(assessment_id="   ")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _assessment(tenant_id="")

    def test_assessed_at_invalid(self):
        with pytest.raises(ValueError, match="assessed_at"):
            _assessment(assessed_at="bad")

    def test_assessed_at_empty(self):
        with pytest.raises(ValueError, match="assessed_at"):
            _assessment(assessed_at="")

    def test_total_simulations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_simulations"):
            _assessment(total_simulations=-1)

    def test_total_simulations_bool_rejected(self):
        with pytest.raises(ValueError, match="total_simulations"):
            _assessment(total_simulations=True)

    def test_total_violations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _assessment(total_violations=-1)

    def test_total_violations_bool_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _assessment(total_violations=True)

    def test_completion_rate_negative_rejected(self):
        with pytest.raises(ValueError, match="completion_rate"):
            _assessment(completion_rate=-0.01)

    def test_completion_rate_above_one_rejected(self):
        with pytest.raises(ValueError, match="completion_rate"):
            _assessment(completion_rate=1.01)

    def test_completion_rate_bool_rejected(self):
        with pytest.raises(ValueError, match="completion_rate"):
            _assessment(completion_rate=True)

    def test_completion_rate_zero_ok(self):
        r = _assessment(completion_rate=0.0)
        assert r.completion_rate == 0.0

    def test_completion_rate_one_ok(self):
        r = _assessment(completion_rate=1.0)
        assert r.completion_rate == 1.0

    def test_completion_rate_int_zero_ok(self):
        r = _assessment(completion_rate=0)
        assert r.completion_rate == 0.0

    def test_completion_rate_int_one_ok(self):
        r = _assessment(completion_rate=1)
        assert r.completion_rate == 1.0

    def test_avg_readiness_score_negative_rejected(self):
        with pytest.raises(ValueError, match="avg_readiness_score"):
            _assessment(avg_readiness_score=-0.01)

    def test_avg_readiness_score_above_one_rejected(self):
        with pytest.raises(ValueError, match="avg_readiness_score"):
            _assessment(avg_readiness_score=1.01)

    def test_avg_readiness_score_bool_rejected(self):
        with pytest.raises(ValueError, match="avg_readiness_score"):
            _assessment(avg_readiness_score=True)

    def test_avg_readiness_score_zero_ok(self):
        r = _assessment(avg_readiness_score=0.0)
        assert r.avg_readiness_score == 0.0

    def test_avg_readiness_score_one_ok(self):
        r = _assessment(avg_readiness_score=1.0)
        assert r.avg_readiness_score == 1.0

    def test_avg_readiness_score_int_zero_ok(self):
        r = _assessment(avg_readiness_score=0)
        assert r.avg_readiness_score == 0.0

    def test_avg_readiness_score_int_one_ok(self):
        r = _assessment(avg_readiness_score=1)
        assert r.avg_readiness_score == 1.0

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _assessment(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _assessment(metadata={"lst": [1, 2]})
        assert isinstance(r.metadata["lst"], tuple)

    def test_to_dict_metadata_thawed(self):
        r = _assessment(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["x"], list)

    def test_to_dict_returns_all_fields(self):
        r = _assessment()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names


# ===================================================================
# SandboxClosureReport TESTS
# ===================================================================


class TestSandboxClosureReport:
    def test_minimal_construction(self):
        r = _closure()
        assert r.report_id == "rpt-1"
        assert r.tenant_id == "ten-1"
        assert r.created_at == TS

    def test_defaults(self):
        r = _closure()
        assert r.total_simulations == 0
        assert r.total_scenarios == 0
        assert r.total_diffs == 0
        assert r.total_impacts == 0
        assert r.total_recommendations == 0
        assert r.total_violations == 0
        assert r.metadata == {}

    def test_full_construction(self):
        r = _closure(
            total_simulations=10,
            total_scenarios=20,
            total_diffs=5,
            total_impacts=3,
            total_recommendations=2,
            total_violations=1,
            metadata={"k": "v"},
        )
        assert r.total_simulations == 10
        assert r.total_scenarios == 20
        assert r.total_diffs == 5
        assert r.total_impacts == 3
        assert r.total_recommendations == 2
        assert r.total_violations == 1
        assert r.metadata["k"] == "v"

    def test_frozen(self):
        r = _closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.report_id = "other"

    def test_frozen_tenant_id(self):
        r = _closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.tenant_id = "other"

    def test_frozen_total_simulations(self):
        r = _closure()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.total_simulations = 99

    def test_report_id_empty_rejected(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="")

    def test_report_id_whitespace_rejected(self):
        with pytest.raises(ValueError, match="report_id"):
            _closure(report_id="   ")

    def test_tenant_id_empty_rejected(self):
        with pytest.raises(ValueError, match="tenant_id"):
            _closure(tenant_id="")

    def test_created_at_invalid(self):
        with pytest.raises(ValueError, match="created_at"):
            _closure(created_at="bad")

    def test_created_at_empty(self):
        with pytest.raises(ValueError, match="created_at"):
            _closure(created_at="")

    def test_total_simulations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_simulations"):
            _closure(total_simulations=-1)

    def test_total_simulations_bool_rejected(self):
        with pytest.raises(ValueError, match="total_simulations"):
            _closure(total_simulations=True)

    def test_total_scenarios_negative_rejected(self):
        with pytest.raises(ValueError, match="total_scenarios"):
            _closure(total_scenarios=-1)

    def test_total_scenarios_bool_rejected(self):
        with pytest.raises(ValueError, match="total_scenarios"):
            _closure(total_scenarios=True)

    def test_total_diffs_negative_rejected(self):
        with pytest.raises(ValueError, match="total_diffs"):
            _closure(total_diffs=-1)

    def test_total_diffs_bool_rejected(self):
        with pytest.raises(ValueError, match="total_diffs"):
            _closure(total_diffs=True)

    def test_total_impacts_negative_rejected(self):
        with pytest.raises(ValueError, match="total_impacts"):
            _closure(total_impacts=-1)

    def test_total_impacts_bool_rejected(self):
        with pytest.raises(ValueError, match="total_impacts"):
            _closure(total_impacts=True)

    def test_total_recommendations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_recommendations"):
            _closure(total_recommendations=-1)

    def test_total_recommendations_bool_rejected(self):
        with pytest.raises(ValueError, match="total_recommendations"):
            _closure(total_recommendations=True)

    def test_total_violations_negative_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _closure(total_violations=-1)

    def test_total_violations_bool_rejected(self):
        with pytest.raises(ValueError, match="total_violations"):
            _closure(total_violations=True)

    def test_metadata_frozen_to_mapping_proxy(self):
        r = _closure(metadata={"a": 1})
        assert isinstance(r.metadata, MappingProxyType)

    def test_metadata_nested_list_frozen(self):
        r = _closure(metadata={"lst": [1, 2]})
        assert isinstance(r.metadata["lst"], tuple)

    def test_to_dict_metadata_thawed(self):
        r = _closure(metadata={"x": [1]})
        d = r.to_dict()
        assert isinstance(d["metadata"], dict)
        assert isinstance(d["metadata"]["x"], list)

    def test_to_dict_returns_all_fields(self):
        r = _closure()
        d = r.to_dict()
        field_names = {f.name for f in dataclasses.fields(r)}
        assert set(d.keys()) == field_names


# ===================================================================
# CROSS-CUTTING / EDGE-CASE TESTS
# ===================================================================


class TestUnitFloatEdgeCases:
    """Extra edge cases for require_unit_float fields."""

    def test_readiness_score_inf_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _result(readiness_score=float("inf"))

    def test_readiness_score_neg_inf_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _result(readiness_score=float("-inf"))

    def test_readiness_score_nan_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _result(readiness_score=float("nan"))

    def test_completion_rate_inf_rejected(self):
        with pytest.raises(ValueError, match="completion_rate"):
            _assessment(completion_rate=float("inf"))

    def test_completion_rate_nan_rejected(self):
        with pytest.raises(ValueError, match="completion_rate"):
            _assessment(completion_rate=float("nan"))

    def test_avg_readiness_score_inf_rejected(self):
        with pytest.raises(ValueError, match="avg_readiness_score"):
            _assessment(avg_readiness_score=float("inf"))

    def test_avg_readiness_score_nan_rejected(self):
        with pytest.raises(ValueError, match="avg_readiness_score"):
            _assessment(avg_readiness_score=float("nan"))

    def test_recommendation_readiness_score_inf_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _recommendation(readiness_score=float("inf"))

    def test_recommendation_readiness_score_nan_rejected(self):
        with pytest.raises(ValueError, match="readiness_score"):
            _recommendation(readiness_score=float("nan"))


class TestMetadataMutationBlocked:
    """Verify that frozen metadata cannot be mutated."""

    def test_request_metadata_immutable(self):
        r = _request(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_scenario_metadata_immutable(self):
        r = _scenario(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_result_metadata_immutable(self):
        r = _result(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_diff_metadata_immutable(self):
        r = _diff(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_impact_metadata_immutable(self):
        r = _impact(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2

    def test_violation_metadata_immutable(self):
        r = _violation(metadata={"a": 1})
        with pytest.raises(TypeError):
            r.metadata["b"] = 2


class TestDatetimeEdgeCases:
    """Additional datetime format acceptance tests."""

    def test_request_z_suffix_accepted(self):
        r = _request(created_at="2025-06-01T12:00:00Z")
        assert r.created_at == "2025-06-01T12:00:00Z"

    def test_scenario_short_date_accepted(self):
        r = _scenario(created_at="2025-06-01")
        assert r.created_at == "2025-06-01"

    def test_diff_z_suffix_accepted(self):
        r = _diff(created_at="2025-06-01T00:00:00Z")
        assert r.created_at == "2025-06-01T00:00:00Z"

    def test_impact_ts2_accepted(self):
        r = _impact(created_at=TS2)
        assert r.created_at == TS2

    def test_violation_short_date_accepted(self):
        r = _violation(detected_at="2025-06-01")
        assert r.detected_at == "2025-06-01"
