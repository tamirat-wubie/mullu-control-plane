"""Tests for experiment runtime contracts (Phase 114).

Covers: ExperimentDesign, ExperimentVariable, ControlGroup, ExperimentResult,
        FalsificationRecord, ReplicationRecord, ExperimentDecision,
        ExperimentAssessment, ExperimentSnapshot, ExperimentClosureReport,
        and all related enums.
"""

import json
import math

import pytest
from dataclasses import FrozenInstanceError

from mcoi_runtime.contracts.experiment_runtime import (
    ControlGroup,
    ExperimentAssessment,
    ExperimentClosureReport,
    ExperimentDecision,
    ExperimentDesign,
    ExperimentPhase,
    ExperimentResult,
    ExperimentRiskLevel,
    ExperimentSnapshot,
    ExperimentVariable,
    FalsificationRecord,
    FalsificationStatus,
    ReplicationRecord,
    ReplicationStatus,
    ResultSignificance,
    VariableRole,
)


TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-01T13:00:00+00:00"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _design(**kw):
    defaults = dict(
        design_id="d-001", tenant_id="t-1", hypothesis_ref="h-001",
        display_name="Test Design", phase=ExperimentPhase.DESIGN,
        variable_count=0, created_at=TS,
    )
    defaults.update(kw)
    return ExperimentDesign(**defaults)


def _variable(**kw):
    defaults = dict(
        variable_id="v-001", tenant_id="t-1", design_ref="d-001",
        name="Temperature", role=VariableRole.INDEPENDENT, unit="C",
        created_at=TS,
    )
    defaults.update(kw)
    return ExperimentVariable(**defaults)


def _group(**kw):
    defaults = dict(
        group_id="g-001", tenant_id="t-1", design_ref="d-001",
        display_name="Control A", sample_size=30, created_at=TS,
    )
    defaults.update(kw)
    return ControlGroup(**defaults)


def _result(**kw):
    defaults = dict(
        result_id="r-001", tenant_id="t-1", design_ref="d-001",
        significance=ResultSignificance.SIGNIFICANT, effect_size=0.5,
        p_value=0.05, created_at=TS,
    )
    defaults.update(kw)
    return ExperimentResult(**defaults)


def _falsification(**kw):
    defaults = dict(
        record_id="f-001", tenant_id="t-1", hypothesis_ref="h-001",
        status=FalsificationStatus.UNFALSIFIED, evidence_ref="e-001",
        created_at=TS,
    )
    defaults.update(kw)
    return FalsificationRecord(**defaults)


def _replication(**kw):
    defaults = dict(
        replication_id="rep-001", tenant_id="t-1", original_ref="d-001",
        status=ReplicationStatus.PENDING, confidence=0.5, created_at=TS,
    )
    defaults.update(kw)
    return ReplicationRecord(**defaults)


def _decision(**kw):
    defaults = dict(
        decision_id="dec-001", tenant_id="t-1", design_ref="d-001",
        disposition="continue", reason="Results promising", decided_at=TS,
    )
    defaults.update(kw)
    return ExperimentDecision(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="a-001", tenant_id="t-1", total_designs=5,
        total_results=10, total_replications=3, success_rate=0.6,
        assessed_at=TS,
    )
    defaults.update(kw)
    return ExperimentAssessment(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-001", tenant_id="t-1", total_designs=5,
        total_variables=10, total_groups=3, total_results=8,
        total_falsifications=2, total_violations=1, captured_at=TS,
    )
    defaults.update(kw)
    return ExperimentSnapshot(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="cr-001", tenant_id="t-1", total_designs=5,
        total_results=10, total_replications=3, total_violations=1,
        created_at=TS,
    )
    defaults.update(kw)
    return ExperimentClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================

class TestExperimentPhaseEnum:
    def test_all_values(self):
        assert set(e.value for e in ExperimentPhase) == {
            "design", "setup", "running", "analysis", "completed", "failed",
        }

    def test_member_count(self):
        assert len(ExperimentPhase) == 6

    @pytest.mark.parametrize("member", list(ExperimentPhase))
    def test_value_is_string(self, member):
        assert isinstance(member.value, str)


class TestVariableRoleEnum:
    def test_all_values(self):
        assert set(e.value for e in VariableRole) == {
            "independent", "dependent", "control", "confounding",
        }

    def test_member_count(self):
        assert len(VariableRole) == 4


class TestFalsificationStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in FalsificationStatus) == {
            "unfalsified", "falsified", "inconclusive", "replicated",
        }

    def test_member_count(self):
        assert len(FalsificationStatus) == 4


class TestReplicationStatusEnum:
    def test_all_values(self):
        assert set(e.value for e in ReplicationStatus) == {
            "pending", "successful", "failed", "partial",
        }

    def test_member_count(self):
        assert len(ReplicationStatus) == 4


class TestResultSignificanceEnum:
    def test_all_values(self):
        assert set(e.value for e in ResultSignificance) == {
            "significant", "marginal", "insignificant", "undetermined",
        }

    def test_member_count(self):
        assert len(ResultSignificance) == 4


class TestExperimentRiskLevelEnum:
    def test_all_values(self):
        assert set(e.value for e in ExperimentRiskLevel) == {
            "low", "medium", "high", "critical",
        }

    def test_member_count(self):
        assert len(ExperimentRiskLevel) == 4


# ===================================================================
# ExperimentDesign
# ===================================================================

class TestExperimentDesign:
    def test_happy_path(self):
        d = _design()
        assert d.design_id == "d-001"
        assert d.tenant_id == "t-1"
        assert d.hypothesis_ref == "h-001"
        assert d.display_name == "Test Design"
        assert d.phase == ExperimentPhase.DESIGN
        assert d.variable_count == 0
        assert d.created_at == TS

    def test_frozen(self):
        d = _design()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "design_id", "x")

    def test_to_dict_preserves_enum(self):
        d = _design()
        data = d.to_dict()
        assert data["phase"] is ExperimentPhase.DESIGN

    def test_to_json_dict_serializes_enum(self):
        d = _design()
        data = d.to_json_dict()
        assert data["phase"] == "design"

    def test_to_json_roundtrip(self):
        d = _design()
        raw = d.to_json()
        parsed = json.loads(raw)
        assert parsed["design_id"] == "d-001"

    def test_metadata_frozen(self):
        d = _design(metadata={"k": "v"})
        with pytest.raises(TypeError):
            d.metadata["k2"] = "v2"

    @pytest.mark.parametrize("field,val", [
        ("design_id", ""), ("tenant_id", "  "), ("hypothesis_ref", ""),
        ("display_name", ""),
    ])
    def test_empty_text_rejected(self, field, val):
        with pytest.raises(ValueError):
            _design(**{field: val})

    def test_invalid_phase(self):
        with pytest.raises(ValueError):
            _design(phase="not_a_phase")

    def test_negative_variable_count(self):
        with pytest.raises(ValueError):
            _design(variable_count=-1)

    def test_bool_variable_count_rejected(self):
        with pytest.raises(ValueError):
            _design(variable_count=True)

    def test_bad_created_at(self):
        with pytest.raises(ValueError):
            _design(created_at="not-a-date")

    @pytest.mark.parametrize("phase", list(ExperimentPhase))
    def test_all_phases_accepted(self, phase):
        d = _design(phase=phase)
        assert d.phase is phase

    def test_metadata_default_empty(self):
        d = _design()
        assert len(d.metadata) == 0

    def test_nested_metadata_frozen(self):
        d = _design(metadata={"a": {"b": 1}})
        with pytest.raises(TypeError):
            d.metadata["a"]["c"] = 2

    def test_two_designs_equal(self):
        d1 = _design()
        d2 = _design()
        assert d1 == d2

    def test_design_not_equal_different_id(self):
        d1 = _design()
        d2 = _design(design_id="d-002")
        assert d1 != d2

    def test_zero_variable_count(self):
        d = _design(variable_count=0)
        assert d.variable_count == 0

    def test_large_variable_count(self):
        d = _design(variable_count=99999)
        assert d.variable_count == 99999


# ===================================================================
# ExperimentVariable
# ===================================================================

class TestExperimentVariable:
    def test_happy_path(self):
        v = _variable()
        assert v.variable_id == "v-001"
        assert v.role == VariableRole.INDEPENDENT

    def test_frozen(self):
        v = _variable()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "name", "x")

    @pytest.mark.parametrize("role", list(VariableRole))
    def test_all_roles(self, role):
        v = _variable(role=role)
        assert v.role is role

    def test_invalid_role(self):
        with pytest.raises(ValueError):
            _variable(role="bad")

    @pytest.mark.parametrize("field", ["variable_id", "tenant_id", "design_ref", "name"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _variable(**{field: ""})

    def test_to_dict(self):
        v = _variable()
        data = v.to_dict()
        assert data["role"] is VariableRole.INDEPENDENT

    def test_to_json(self):
        v = _variable()
        raw = v.to_json()
        parsed = json.loads(raw)
        assert parsed["role"] == "independent"

    def test_metadata_frozen(self):
        v = _variable(metadata={"x": 1})
        with pytest.raises(TypeError):
            v.metadata["y"] = 2

    def test_bad_created_at(self):
        with pytest.raises(ValueError):
            _variable(created_at="nope")

    def test_unit_preserved(self):
        v = _variable(unit="kg")
        assert v.unit == "kg"

    def test_equal_variables(self):
        assert _variable() == _variable()

    def test_unequal_variables(self):
        assert _variable() != _variable(variable_id="v-002")


# ===================================================================
# ControlGroup
# ===================================================================

class TestControlGroup:
    def test_happy_path(self):
        g = _group()
        assert g.group_id == "g-001"
        assert g.sample_size == 30

    def test_frozen(self):
        g = _group()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(g, "group_id", "x")

    @pytest.mark.parametrize("field", ["group_id", "tenant_id", "design_ref", "display_name"])
    def test_empty_fields_rejected(self, field):
        with pytest.raises(ValueError):
            _group(**{field: ""})

    def test_negative_sample_size(self):
        with pytest.raises(ValueError):
            _group(sample_size=-1)

    def test_bool_sample_size(self):
        with pytest.raises(ValueError):
            _group(sample_size=True)

    def test_zero_sample_size(self):
        g = _group(sample_size=0)
        assert g.sample_size == 0

    def test_to_dict(self):
        g = _group()
        data = g.to_dict()
        assert data["sample_size"] == 30

    def test_to_json(self):
        g = _group()
        parsed = json.loads(g.to_json())
        assert parsed["group_id"] == "g-001"

    def test_metadata_frozen(self):
        g = _group(metadata={"a": 1})
        with pytest.raises(TypeError):
            g.metadata["b"] = 2


# ===================================================================
# ExperimentResult
# ===================================================================

class TestExperimentResult:
    def test_happy_path(self):
        r = _result()
        assert r.result_id == "r-001"
        assert r.significance == ResultSignificance.SIGNIFICANT
        assert r.effect_size == 0.5
        assert r.p_value == 0.05

    def test_frozen(self):
        r = _result()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "result_id", "x")

    @pytest.mark.parametrize("sig", list(ResultSignificance))
    def test_all_significance_levels(self, sig):
        r = _result(significance=sig)
        assert r.significance is sig

    def test_invalid_significance(self):
        with pytest.raises(ValueError):
            _result(significance="bad")

    def test_effect_size_bounds(self):
        _result(effect_size=0.0)
        _result(effect_size=1.0)

    def test_effect_size_over_1_rejected(self):
        with pytest.raises(ValueError):
            _result(effect_size=1.1)

    def test_effect_size_negative_rejected(self):
        with pytest.raises(ValueError):
            _result(effect_size=-0.1)

    def test_effect_size_bool_rejected(self):
        with pytest.raises(ValueError):
            _result(effect_size=True)

    def test_effect_size_nan_rejected(self):
        with pytest.raises(ValueError):
            _result(effect_size=float("nan"))

    def test_effect_size_inf_rejected(self):
        with pytest.raises(ValueError):
            _result(effect_size=float("inf"))

    def test_p_value_bounds(self):
        _result(p_value=0.0)
        _result(p_value=1.0)

    def test_p_value_over_rejected(self):
        with pytest.raises(ValueError):
            _result(p_value=1.1)

    def test_p_value_negative_rejected(self):
        with pytest.raises(ValueError):
            _result(p_value=-0.01)

    @pytest.mark.parametrize("field", ["result_id", "tenant_id", "design_ref"])
    def test_empty_fields(self, field):
        with pytest.raises(ValueError):
            _result(**{field: ""})

    def test_to_dict(self):
        r = _result()
        data = r.to_dict()
        assert data["significance"] is ResultSignificance.SIGNIFICANT

    def test_to_json(self):
        r = _result()
        parsed = json.loads(r.to_json())
        assert parsed["significance"] == "significant"

    def test_metadata_frozen(self):
        r = _result(metadata={"k": "v"})
        with pytest.raises(TypeError):
            r.metadata["k2"] = "v2"


# ===================================================================
# FalsificationRecord
# ===================================================================

class TestFalsificationRecord:
    def test_happy_path(self):
        f = _falsification()
        assert f.record_id == "f-001"
        assert f.status == FalsificationStatus.UNFALSIFIED

    def test_frozen(self):
        f = _falsification()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(f, "record_id", "x")

    @pytest.mark.parametrize("status", list(FalsificationStatus))
    def test_all_statuses(self, status):
        f = _falsification(status=status)
        assert f.status is status

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _falsification(status="bad")

    @pytest.mark.parametrize("field", ["record_id", "tenant_id", "hypothesis_ref", "evidence_ref"])
    def test_empty_fields(self, field):
        with pytest.raises(ValueError):
            _falsification(**{field: ""})

    def test_to_dict(self):
        data = _falsification().to_dict()
        assert data["status"] is FalsificationStatus.UNFALSIFIED

    def test_to_json(self):
        parsed = json.loads(_falsification().to_json())
        assert parsed["status"] == "unfalsified"


# ===================================================================
# ReplicationRecord
# ===================================================================

class TestReplicationRecord:
    def test_happy_path(self):
        r = _replication()
        assert r.replication_id == "rep-001"
        assert r.confidence == 0.5

    def test_frozen(self):
        r = _replication()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "replication_id", "x")

    @pytest.mark.parametrize("status", list(ReplicationStatus))
    def test_all_statuses(self, status):
        r = _replication(status=status)
        assert r.status is status

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _replication(status="bad")

    def test_confidence_bounds(self):
        _replication(confidence=0.0)
        _replication(confidence=1.0)

    def test_confidence_over_rejected(self):
        with pytest.raises(ValueError):
            _replication(confidence=1.1)

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError):
            _replication(confidence=-0.1)

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError):
            _replication(confidence=True)

    @pytest.mark.parametrize("field", ["replication_id", "tenant_id", "original_ref"])
    def test_empty_fields(self, field):
        with pytest.raises(ValueError):
            _replication(**{field: ""})

    def test_to_dict(self):
        data = _replication().to_dict()
        assert data["status"] is ReplicationStatus.PENDING

    def test_to_json(self):
        parsed = json.loads(_replication().to_json())
        assert parsed["status"] == "pending"


# ===================================================================
# ExperimentDecision
# ===================================================================

class TestExperimentDecision:
    def test_happy_path(self):
        d = _decision()
        assert d.decision_id == "dec-001"
        assert d.disposition == "continue"

    def test_frozen(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "x")

    @pytest.mark.parametrize("field", [
        "decision_id", "tenant_id", "design_ref", "disposition", "reason",
    ])
    def test_empty_fields(self, field):
        with pytest.raises(ValueError):
            _decision(**{field: ""})

    def test_bad_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at="bad")

    def test_to_dict(self):
        data = _decision().to_dict()
        assert data["disposition"] == "continue"

    def test_to_json(self):
        parsed = json.loads(_decision().to_json())
        assert parsed["reason"] == "Results promising"


# ===================================================================
# ExperimentAssessment
# ===================================================================

class TestExperimentAssessment:
    def test_happy_path(self):
        a = _assessment()
        assert a.assessment_id == "a-001"
        assert a.total_designs == 5
        assert a.success_rate == 0.6

    def test_frozen(self):
        a = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(a, "assessment_id", "x")

    def test_success_rate_bounds(self):
        _assessment(success_rate=0.0)
        _assessment(success_rate=1.0)

    def test_success_rate_over_rejected(self):
        with pytest.raises(ValueError):
            _assessment(success_rate=1.1)

    def test_success_rate_negative_rejected(self):
        with pytest.raises(ValueError):
            _assessment(success_rate=-0.1)

    def test_negative_totals_rejected(self):
        with pytest.raises(ValueError):
            _assessment(total_designs=-1)

    def test_bool_totals_rejected(self):
        with pytest.raises(ValueError):
            _assessment(total_designs=True)

    @pytest.mark.parametrize("field", ["assessment_id", "tenant_id"])
    def test_empty_fields(self, field):
        with pytest.raises(ValueError):
            _assessment(**{field: ""})

    def test_to_dict(self):
        data = _assessment().to_dict()
        assert data["total_results"] == 10

    def test_to_json(self):
        parsed = json.loads(_assessment().to_json())
        assert parsed["success_rate"] == 0.6


# ===================================================================
# ExperimentSnapshot
# ===================================================================

class TestExperimentSnapshot:
    def test_happy_path(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.total_designs == 5

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "x")

    @pytest.mark.parametrize("field", [
        "total_designs", "total_variables", "total_groups",
        "total_results", "total_falsifications", "total_violations",
    ])
    def test_negative_totals_rejected(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: -1})

    @pytest.mark.parametrize("field", ["snapshot_id", "tenant_id"])
    def test_empty_fields(self, field):
        with pytest.raises(ValueError):
            _snapshot(**{field: ""})

    def test_to_dict(self):
        data = _snapshot().to_dict()
        assert data["total_violations"] == 1

    def test_to_json(self):
        parsed = json.loads(_snapshot().to_json())
        assert parsed["total_groups"] == 3


# ===================================================================
# ExperimentClosureReport
# ===================================================================

class TestExperimentClosureReport:
    def test_happy_path(self):
        c = _closure()
        assert c.report_id == "cr-001"
        assert c.total_violations == 1

    def test_frozen(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "report_id", "x")

    @pytest.mark.parametrize("field", [
        "total_designs", "total_results", "total_replications", "total_violations",
    ])
    def test_negative_totals_rejected(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: -1})

    @pytest.mark.parametrize("field", ["report_id", "tenant_id"])
    def test_empty_fields(self, field):
        with pytest.raises(ValueError):
            _closure(**{field: ""})

    def test_to_dict(self):
        data = _closure().to_dict()
        assert data["total_replications"] == 3

    def test_to_json(self):
        parsed = json.loads(_closure().to_json())
        assert parsed["report_id"] == "cr-001"
