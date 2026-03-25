"""Comprehensive tests for self-tuning runtime contracts.

Covers every enum, every dataclass, field validation (happy + negative),
frozen immutability, to_dict() preservation, and edge cases.
"""

from __future__ import annotations

import pytest
from dataclasses import FrozenInstanceError

from mcoi_runtime.contracts.self_tuning import (
    ApprovalDisposition,
    ExecutionTuningRecord,
    ImprovementAssessment,
    ImprovementClosureReport,
    ImprovementDecision,
    ImprovementKind,
    ImprovementProposal,
    ImprovementRiskLevel,
    ImprovementScope,
    ImprovementSnapshot,
    ImprovementStatus,
    ImprovementViolation,
    LearningSignal,
    LearningSignalKind,
    ParameterAdjustment,
    PolicyTuningRecord,
)


# ===================================================================
# Constants
# ===================================================================

TS = "2025-06-01T00:00:00+00:00"
TS2 = "2025-07-01T12:00:00+00:00"
TENANT = "tenant-1"


# ===================================================================
# Helper factories
# ===================================================================


def _signal(**kw):
    defaults = dict(
        signal_id="sig-1",
        tenant_id=TENANT,
        kind=LearningSignalKind.EXECUTION_FAILURE,
        source_runtime="runtime-a",
        description="test signal",
        occurrence_count=1,
        first_seen_at=TS,
        last_seen_at=TS,
    )
    defaults.update(kw)
    return LearningSignal(**defaults)


def _proposal(**kw):
    defaults = dict(
        proposal_id="prop-1",
        tenant_id=TENANT,
        signal_ref="sig-1",
        kind=ImprovementKind.PARAMETER,
        scope=ImprovementScope.LOCAL,
        risk_level=ImprovementRiskLevel.LOW,
        status=ImprovementStatus.PROPOSED,
        description="test proposal",
        justification="test justification",
        created_at=TS,
    )
    defaults.update(kw)
    return ImprovementProposal(**defaults)


def _adjustment(**kw):
    defaults = dict(
        adjustment_id="adj-1",
        tenant_id=TENANT,
        proposal_ref="prop-1",
        target_component="comp-a",
        parameter_name="timeout",
        old_value="30",
        proposed_value="60",
        applied_at=TS,
    )
    defaults.update(kw)
    return ParameterAdjustment(**defaults)


def _policy_tuning(**kw):
    defaults = dict(
        tuning_id="pt-1",
        tenant_id=TENANT,
        proposal_ref="prop-1",
        rule_target="rule-x",
        previous_setting="on",
        proposed_setting="off",
        blast_radius=ImprovementScope.LOCAL,
        created_at=TS,
    )
    defaults.update(kw)
    return PolicyTuningRecord(**defaults)


def _exec_tuning(**kw):
    defaults = dict(
        tuning_id="et-1",
        tenant_id=TENANT,
        proposal_ref="prop-1",
        target_runtime="runtime-b",
        change_type="scale-up",
        expected_gain="20% throughput",
        expected_risk="none",
        created_at=TS,
    )
    defaults.update(kw)
    return ExecutionTuningRecord(**defaults)


def _decision(**kw):
    defaults = dict(
        decision_id="dec-1",
        tenant_id=TENANT,
        proposal_ref="prop-1",
        disposition=ApprovalDisposition.PENDING_APPROVAL,
        decided_by="approver-1",
        reason="looks good",
        decided_at=TS,
    )
    defaults.update(kw)
    return ImprovementDecision(**defaults)


def _assessment(**kw):
    defaults = dict(
        assessment_id="asm-1",
        tenant_id=TENANT,
        total_signals=5,
        total_proposals=3,
        total_applied=2,
        total_rolled_back=1,
        improvement_rate=0.5,
        assessed_at=TS,
    )
    defaults.update(kw)
    return ImprovementAssessment(**defaults)


def _violation(**kw):
    defaults = dict(
        violation_id="viol-1",
        tenant_id=TENANT,
        operation="unapproved_high_risk",
        reason="bad proposal",
        detected_at=TS,
    )
    defaults.update(kw)
    return ImprovementViolation(**defaults)


def _snapshot(**kw):
    defaults = dict(
        snapshot_id="snap-1",
        tenant_id=TENANT,
        total_signals=10,
        total_proposals=5,
        total_adjustments=3,
        total_policy_tunings=2,
        total_execution_tunings=1,
        total_decisions=4,
        total_violations=0,
        captured_at=TS,
    )
    defaults.update(kw)
    return ImprovementSnapshot(**defaults)


def _closure(**kw):
    defaults = dict(
        report_id="rpt-1",
        tenant_id=TENANT,
        total_signals=10,
        total_proposals=5,
        total_applied=3,
        total_rolled_back=1,
        total_violations=0,
        created_at=TS,
    )
    defaults.update(kw)
    return ImprovementClosureReport(**defaults)


# ===================================================================
# Enum tests
# ===================================================================


class TestImprovementStatus:
    def test_all_values(self):
        assert ImprovementStatus.PROPOSED.value == "proposed"
        assert ImprovementStatus.APPROVED.value == "approved"
        assert ImprovementStatus.REJECTED.value == "rejected"
        assert ImprovementStatus.DEFERRED.value == "deferred"
        assert ImprovementStatus.APPLIED.value == "applied"
        assert ImprovementStatus.ROLLED_BACK.value == "rolled_back"

    def test_member_count(self):
        assert len(ImprovementStatus) == 6

    def test_from_value(self):
        assert ImprovementStatus("proposed") is ImprovementStatus.PROPOSED

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ImprovementStatus("invalid")

    def test_uniqueness(self):
        vals = [m.value for m in ImprovementStatus]
        assert len(vals) == len(set(vals))

    def test_is_enum(self):
        for m in ImprovementStatus:
            assert isinstance(m, ImprovementStatus)


class TestImprovementKind:
    def test_all_values(self):
        assert ImprovementKind.PARAMETER.value == "parameter"
        assert ImprovementKind.POLICY.value == "policy"
        assert ImprovementKind.EXECUTION.value == "execution"
        assert ImprovementKind.ROUTING.value == "routing"
        assert ImprovementKind.THRESHOLD.value == "threshold"
        assert ImprovementKind.STAFFING.value == "staffing"

    def test_member_count(self):
        assert len(ImprovementKind) == 6

    def test_from_value(self):
        assert ImprovementKind("parameter") is ImprovementKind.PARAMETER

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ImprovementKind("nope")

    def test_uniqueness(self):
        vals = [m.value for m in ImprovementKind]
        assert len(vals) == len(set(vals))


class TestImprovementScope:
    def test_all_values(self):
        assert ImprovementScope.LOCAL.value == "local"
        assert ImprovementScope.RUNTIME.value == "runtime"
        assert ImprovementScope.TENANT.value == "tenant"
        assert ImprovementScope.PLATFORM.value == "platform"
        assert ImprovementScope.CONSTITUTIONAL.value == "constitutional"

    def test_member_count(self):
        assert len(ImprovementScope) == 5

    def test_from_value(self):
        assert ImprovementScope("constitutional") is ImprovementScope.CONSTITUTIONAL

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ImprovementScope("global")

    def test_uniqueness(self):
        vals = [m.value for m in ImprovementScope]
        assert len(vals) == len(set(vals))


class TestApprovalDisposition:
    def test_all_values(self):
        assert ApprovalDisposition.AUTO_APPLIED.value == "auto_applied"
        assert ApprovalDisposition.PENDING_APPROVAL.value == "pending_approval"
        assert ApprovalDisposition.APPROVED.value == "approved"
        assert ApprovalDisposition.REJECTED.value == "rejected"
        assert ApprovalDisposition.DEFERRED.value == "deferred"

    def test_member_count(self):
        assert len(ApprovalDisposition) == 5

    def test_from_value(self):
        assert ApprovalDisposition("approved") is ApprovalDisposition.APPROVED

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ApprovalDisposition("maybe")

    def test_uniqueness(self):
        vals = [m.value for m in ApprovalDisposition]
        assert len(vals) == len(set(vals))


class TestLearningSignalKind:
    def test_all_values(self):
        assert LearningSignalKind.EXECUTION_FAILURE.value == "execution_failure"
        assert LearningSignalKind.FORECAST_DRIFT.value == "forecast_drift"
        assert LearningSignalKind.WORKFORCE_OVERLOAD.value == "workforce_overload"
        assert LearningSignalKind.FINANCIAL_LOSS.value == "financial_loss"
        assert LearningSignalKind.CONSTITUTIONAL_VIOLATION.value == "constitutional_violation"
        assert LearningSignalKind.OBSERVABILITY_ANOMALY.value == "observability_anomaly"
        assert LearningSignalKind.POLICY_SIMULATION.value == "policy_simulation"

    def test_member_count(self):
        assert len(LearningSignalKind) == 7

    def test_from_value(self):
        assert LearningSignalKind("forecast_drift") is LearningSignalKind.FORECAST_DRIFT

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            LearningSignalKind("cpu_spike")

    def test_uniqueness(self):
        vals = [m.value for m in LearningSignalKind]
        assert len(vals) == len(set(vals))


class TestImprovementRiskLevel:
    def test_all_values(self):
        assert ImprovementRiskLevel.LOW.value == "low"
        assert ImprovementRiskLevel.MEDIUM.value == "medium"
        assert ImprovementRiskLevel.HIGH.value == "high"
        assert ImprovementRiskLevel.CRITICAL.value == "critical"

    def test_member_count(self):
        assert len(ImprovementRiskLevel) == 4

    def test_from_value(self):
        assert ImprovementRiskLevel("critical") is ImprovementRiskLevel.CRITICAL

    def test_invalid_value(self):
        with pytest.raises(ValueError):
            ImprovementRiskLevel("extreme")

    def test_uniqueness(self):
        vals = [m.value for m in ImprovementRiskLevel]
        assert len(vals) == len(set(vals))


# ===================================================================
# LearningSignal tests
# ===================================================================


class TestLearningSignal:
    def test_happy_path(self):
        s = _signal()
        assert s.signal_id == "sig-1"
        assert s.tenant_id == TENANT
        assert s.kind == LearningSignalKind.EXECUTION_FAILURE
        assert s.source_runtime == "runtime-a"
        assert s.description == "test signal"
        assert s.occurrence_count == 1
        assert s.first_seen_at == TS
        assert s.last_seen_at == TS

    def test_frozen(self):
        s = _signal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.signal_id = "other"

    def test_empty_signal_id(self):
        with pytest.raises(ValueError):
            _signal(signal_id="")

    def test_whitespace_signal_id(self):
        with pytest.raises(ValueError):
            _signal(signal_id="   ")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _signal(tenant_id="")

    def test_empty_source_runtime(self):
        with pytest.raises(ValueError):
            _signal(source_runtime="")

    def test_empty_description(self):
        with pytest.raises(ValueError):
            _signal(description="")

    def test_invalid_kind_string(self):
        with pytest.raises(ValueError):
            _signal(kind="execution_failure")

    def test_invalid_kind_int(self):
        with pytest.raises(ValueError):
            _signal(kind=42)

    def test_negative_occurrence_count(self):
        with pytest.raises(ValueError):
            _signal(occurrence_count=-1)

    def test_zero_occurrence_count(self):
        s = _signal(occurrence_count=0)
        assert s.occurrence_count == 0

    def test_bool_occurrence_count_rejected(self):
        with pytest.raises(ValueError):
            _signal(occurrence_count=True)

    def test_float_occurrence_count_rejected(self):
        with pytest.raises(ValueError):
            _signal(occurrence_count=1.5)

    def test_invalid_first_seen_at(self):
        with pytest.raises(ValueError):
            _signal(first_seen_at="not-a-date")

    def test_invalid_last_seen_at(self):
        with pytest.raises(ValueError):
            _signal(last_seen_at="nope")

    def test_empty_first_seen_at(self):
        with pytest.raises(ValueError):
            _signal(first_seen_at="")

    def test_empty_last_seen_at(self):
        with pytest.raises(ValueError):
            _signal(last_seen_at="")

    def test_metadata_frozen(self):
        s = _signal(metadata={"key": "val"})
        with pytest.raises(TypeError):
            s.metadata["new"] = "x"

    def test_metadata_default_empty(self):
        s = _signal()
        assert len(s.metadata) == 0

    def test_to_dict(self):
        s = _signal()
        d = s.to_dict()
        assert d["signal_id"] == "sig-1"
        assert d["kind"] == LearningSignalKind.EXECUTION_FAILURE
        assert isinstance(d, dict)

    def test_to_dict_preserves_enum(self):
        s = _signal()
        d = s.to_dict()
        assert isinstance(d["kind"], LearningSignalKind)

    def test_to_json_dict_converts_enum(self):
        s = _signal()
        d = s.to_json_dict()
        assert d["kind"] == "execution_failure"

    def test_all_signal_kinds(self):
        for kind in LearningSignalKind:
            s = _signal(kind=kind)
            assert s.kind == kind

    def test_large_occurrence_count(self):
        s = _signal(occurrence_count=999999)
        assert s.occurrence_count == 999999

    def test_different_timestamps(self):
        s = _signal(first_seen_at=TS, last_seen_at=TS2)
        assert s.first_seen_at == TS
        assert s.last_seen_at == TS2

    def test_metadata_nested_frozen(self):
        s = _signal(metadata={"nested": {"a": 1}})
        with pytest.raises(TypeError):
            s.metadata["nested"]["b"] = 2

    def test_none_signal_id(self):
        with pytest.raises(ValueError):
            _signal(signal_id=None)

    def test_int_signal_id(self):
        with pytest.raises(ValueError):
            _signal(signal_id=123)


# ===================================================================
# ImprovementProposal tests
# ===================================================================


class TestImprovementProposal:
    def test_happy_path(self):
        p = _proposal()
        assert p.proposal_id == "prop-1"
        assert p.tenant_id == TENANT
        assert p.signal_ref == "sig-1"
        assert p.kind == ImprovementKind.PARAMETER
        assert p.scope == ImprovementScope.LOCAL
        assert p.risk_level == ImprovementRiskLevel.LOW
        assert p.status == ImprovementStatus.PROPOSED
        assert p.description == "test proposal"
        assert p.justification == "test justification"
        assert p.created_at == TS

    def test_frozen(self):
        p = _proposal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.proposal_id = "other"

    def test_empty_proposal_id(self):
        with pytest.raises(ValueError):
            _proposal(proposal_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _proposal(tenant_id="")

    def test_empty_signal_ref(self):
        with pytest.raises(ValueError):
            _proposal(signal_ref="")

    def test_empty_description(self):
        with pytest.raises(ValueError):
            _proposal(description="")

    def test_empty_justification(self):
        with pytest.raises(ValueError):
            _proposal(justification="")

    def test_invalid_kind(self):
        with pytest.raises(ValueError):
            _proposal(kind="parameter")

    def test_invalid_scope(self):
        with pytest.raises(ValueError):
            _proposal(scope="local")

    def test_invalid_risk_level(self):
        with pytest.raises(ValueError):
            _proposal(risk_level="low")

    def test_invalid_status(self):
        with pytest.raises(ValueError):
            _proposal(status="proposed")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _proposal(created_at="bad-date")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _proposal(created_at="")

    def test_metadata_frozen(self):
        p = _proposal(metadata={"k": "v"})
        with pytest.raises(TypeError):
            p.metadata["new"] = "x"

    def test_to_dict_preserves_enum(self):
        p = _proposal()
        d = p.to_dict()
        assert isinstance(d["kind"], ImprovementKind)
        assert isinstance(d["scope"], ImprovementScope)
        assert isinstance(d["risk_level"], ImprovementRiskLevel)
        assert isinstance(d["status"], ImprovementStatus)

    def test_to_json_dict_converts_enums(self):
        p = _proposal()
        d = p.to_json_dict()
        assert d["kind"] == "parameter"
        assert d["scope"] == "local"
        assert d["risk_level"] == "low"
        assert d["status"] == "proposed"

    def test_all_kinds(self):
        for kind in ImprovementKind:
            p = _proposal(kind=kind)
            assert p.kind == kind

    def test_all_scopes(self):
        for scope in ImprovementScope:
            p = _proposal(scope=scope)
            assert p.scope == scope

    def test_all_risk_levels(self):
        for rl in ImprovementRiskLevel:
            p = _proposal(risk_level=rl)
            assert p.risk_level == rl

    def test_all_statuses(self):
        for st in ImprovementStatus:
            p = _proposal(status=st)
            assert p.status == st

    def test_none_proposal_id(self):
        with pytest.raises(ValueError):
            _proposal(proposal_id=None)

    def test_whitespace_justification(self):
        with pytest.raises(ValueError):
            _proposal(justification="   ")

    def test_metadata_default_empty(self):
        p = _proposal()
        assert len(p.metadata) == 0

    def test_frozen_status_field(self):
        p = _proposal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.status = ImprovementStatus.APPLIED


# ===================================================================
# ParameterAdjustment tests
# ===================================================================


class TestParameterAdjustment:
    def test_happy_path(self):
        a = _adjustment()
        assert a.adjustment_id == "adj-1"
        assert a.tenant_id == TENANT
        assert a.proposal_ref == "prop-1"
        assert a.target_component == "comp-a"
        assert a.parameter_name == "timeout"
        assert a.old_value == "30"
        assert a.proposed_value == "60"
        assert a.applied_at == TS

    def test_frozen(self):
        a = _adjustment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.adjustment_id = "other"

    def test_empty_adjustment_id(self):
        with pytest.raises(ValueError):
            _adjustment(adjustment_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _adjustment(tenant_id="")

    def test_empty_proposal_ref(self):
        with pytest.raises(ValueError):
            _adjustment(proposal_ref="")

    def test_empty_target_component(self):
        with pytest.raises(ValueError):
            _adjustment(target_component="")

    def test_empty_parameter_name(self):
        with pytest.raises(ValueError):
            _adjustment(parameter_name="")

    def test_empty_old_value(self):
        with pytest.raises(ValueError):
            _adjustment(old_value="")

    def test_empty_proposed_value(self):
        with pytest.raises(ValueError):
            _adjustment(proposed_value="")

    def test_applied_at_optional_empty(self):
        a = _adjustment(applied_at="")
        assert a.applied_at == ""

    def test_applied_at_valid_when_nonempty(self):
        a = _adjustment(applied_at=TS)
        assert a.applied_at == TS

    def test_applied_at_invalid_nonempty(self):
        with pytest.raises(ValueError):
            _adjustment(applied_at="not-a-date")

    def test_metadata_frozen(self):
        a = _adjustment(metadata={"k": "v"})
        with pytest.raises(TypeError):
            a.metadata["new"] = "x"

    def test_to_dict(self):
        a = _adjustment()
        d = a.to_dict()
        assert d["adjustment_id"] == "adj-1"
        assert d["parameter_name"] == "timeout"

    def test_none_adjustment_id(self):
        with pytest.raises(ValueError):
            _adjustment(adjustment_id=None)

    def test_whitespace_target_component(self):
        with pytest.raises(ValueError):
            _adjustment(target_component="   ")


# ===================================================================
# PolicyTuningRecord tests
# ===================================================================


class TestPolicyTuningRecord:
    def test_happy_path(self):
        pt = _policy_tuning()
        assert pt.tuning_id == "pt-1"
        assert pt.tenant_id == TENANT
        assert pt.proposal_ref == "prop-1"
        assert pt.rule_target == "rule-x"
        assert pt.previous_setting == "on"
        assert pt.proposed_setting == "off"
        assert pt.blast_radius == ImprovementScope.LOCAL
        assert pt.created_at == TS

    def test_frozen(self):
        pt = _policy_tuning()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            pt.tuning_id = "other"

    def test_empty_tuning_id(self):
        with pytest.raises(ValueError):
            _policy_tuning(tuning_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _policy_tuning(tenant_id="")

    def test_empty_proposal_ref(self):
        with pytest.raises(ValueError):
            _policy_tuning(proposal_ref="")

    def test_empty_rule_target(self):
        with pytest.raises(ValueError):
            _policy_tuning(rule_target="")

    def test_empty_previous_setting(self):
        with pytest.raises(ValueError):
            _policy_tuning(previous_setting="")

    def test_empty_proposed_setting(self):
        with pytest.raises(ValueError):
            _policy_tuning(proposed_setting="")

    def test_invalid_blast_radius(self):
        with pytest.raises(ValueError):
            _policy_tuning(blast_radius="local")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _policy_tuning(created_at="not-a-date")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _policy_tuning(created_at="")

    def test_metadata_frozen(self):
        pt = _policy_tuning(metadata={"k": "v"})
        with pytest.raises(TypeError):
            pt.metadata["new"] = "x"

    def test_to_dict_preserves_enum(self):
        pt = _policy_tuning()
        d = pt.to_dict()
        assert isinstance(d["blast_radius"], ImprovementScope)

    def test_all_blast_radii(self):
        for scope in ImprovementScope:
            pt = _policy_tuning(blast_radius=scope)
            assert pt.blast_radius == scope


# ===================================================================
# ExecutionTuningRecord tests
# ===================================================================


class TestExecutionTuningRecord:
    def test_happy_path(self):
        et = _exec_tuning()
        assert et.tuning_id == "et-1"
        assert et.tenant_id == TENANT
        assert et.proposal_ref == "prop-1"
        assert et.target_runtime == "runtime-b"
        assert et.change_type == "scale-up"
        assert et.expected_gain == "20% throughput"
        assert et.expected_risk == "none"
        assert et.created_at == TS

    def test_frozen(self):
        et = _exec_tuning()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            et.tuning_id = "other"

    def test_empty_tuning_id(self):
        with pytest.raises(ValueError):
            _exec_tuning(tuning_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _exec_tuning(tenant_id="")

    def test_empty_proposal_ref(self):
        with pytest.raises(ValueError):
            _exec_tuning(proposal_ref="")

    def test_empty_target_runtime(self):
        with pytest.raises(ValueError):
            _exec_tuning(target_runtime="")

    def test_empty_change_type(self):
        with pytest.raises(ValueError):
            _exec_tuning(change_type="")

    def test_empty_expected_gain(self):
        with pytest.raises(ValueError):
            _exec_tuning(expected_gain="")

    def test_empty_expected_risk(self):
        with pytest.raises(ValueError):
            _exec_tuning(expected_risk="")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _exec_tuning(created_at="bad")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _exec_tuning(created_at="")

    def test_metadata_frozen(self):
        et = _exec_tuning(metadata={"k": "v"})
        with pytest.raises(TypeError):
            et.metadata["new"] = "x"

    def test_to_dict(self):
        et = _exec_tuning()
        d = et.to_dict()
        assert d["tuning_id"] == "et-1"
        assert d["change_type"] == "scale-up"


# ===================================================================
# ImprovementDecision tests
# ===================================================================


class TestImprovementDecision:
    def test_happy_path(self):
        dec = _decision()
        assert dec.decision_id == "dec-1"
        assert dec.tenant_id == TENANT
        assert dec.proposal_ref == "prop-1"
        assert dec.disposition == ApprovalDisposition.PENDING_APPROVAL
        assert dec.decided_by == "approver-1"
        assert dec.reason == "looks good"
        assert dec.decided_at == TS

    def test_frozen(self):
        dec = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            dec.decision_id = "other"

    def test_empty_decision_id(self):
        with pytest.raises(ValueError):
            _decision(decision_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _decision(tenant_id="")

    def test_empty_proposal_ref(self):
        with pytest.raises(ValueError):
            _decision(proposal_ref="")

    def test_invalid_disposition(self):
        with pytest.raises(ValueError):
            _decision(disposition="approved")

    def test_empty_decided_by(self):
        with pytest.raises(ValueError):
            _decision(decided_by="")

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            _decision(reason="")

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at="bad")

    def test_empty_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at="")

    def test_metadata_frozen(self):
        dec = _decision(metadata={"k": "v"})
        with pytest.raises(TypeError):
            dec.metadata["new"] = "x"

    def test_to_dict_preserves_enum(self):
        dec = _decision()
        d = dec.to_dict()
        assert isinstance(d["disposition"], ApprovalDisposition)

    def test_all_dispositions(self):
        for disp in ApprovalDisposition:
            dec = _decision(disposition=disp)
            assert dec.disposition == disp

    def test_to_json_dict_converts_enum(self):
        dec = _decision()
        d = dec.to_json_dict()
        assert d["disposition"] == "pending_approval"


# ===================================================================
# ImprovementAssessment tests
# ===================================================================


class TestImprovementAssessment:
    def test_happy_path(self):
        asm = _assessment()
        assert asm.assessment_id == "asm-1"
        assert asm.tenant_id == TENANT
        assert asm.total_signals == 5
        assert asm.total_proposals == 3
        assert asm.total_applied == 2
        assert asm.total_rolled_back == 1
        assert asm.improvement_rate == 0.5
        assert asm.assessed_at == TS

    def test_frozen(self):
        asm = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            asm.assessment_id = "other"

    def test_empty_assessment_id(self):
        with pytest.raises(ValueError):
            _assessment(assessment_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _assessment(tenant_id="")

    def test_negative_total_signals(self):
        with pytest.raises(ValueError):
            _assessment(total_signals=-1)

    def test_negative_total_proposals(self):
        with pytest.raises(ValueError):
            _assessment(total_proposals=-1)

    def test_negative_total_applied(self):
        with pytest.raises(ValueError):
            _assessment(total_applied=-1)

    def test_negative_total_rolled_back(self):
        with pytest.raises(ValueError):
            _assessment(total_rolled_back=-1)

    def test_improvement_rate_below_zero(self):
        with pytest.raises(ValueError):
            _assessment(improvement_rate=-0.1)

    def test_improvement_rate_above_one(self):
        with pytest.raises(ValueError):
            _assessment(improvement_rate=1.1)

    def test_improvement_rate_zero(self):
        asm = _assessment(improvement_rate=0.0)
        assert asm.improvement_rate == 0.0

    def test_improvement_rate_one(self):
        asm = _assessment(improvement_rate=1.0)
        assert asm.improvement_rate == 1.0

    def test_improvement_rate_nan(self):
        with pytest.raises(ValueError):
            _assessment(improvement_rate=float("nan"))

    def test_improvement_rate_inf(self):
        with pytest.raises(ValueError):
            _assessment(improvement_rate=float("inf"))

    def test_improvement_rate_bool_rejected(self):
        with pytest.raises(ValueError):
            _assessment(improvement_rate=True)

    def test_invalid_assessed_at(self):
        with pytest.raises(ValueError):
            _assessment(assessed_at="bad")

    def test_zero_totals(self):
        asm = _assessment(total_signals=0, total_proposals=0, total_applied=0, total_rolled_back=0)
        assert asm.total_signals == 0

    def test_bool_total_signals_rejected(self):
        with pytest.raises(ValueError):
            _assessment(total_signals=True)

    def test_float_total_proposals_rejected(self):
        with pytest.raises(ValueError):
            _assessment(total_proposals=1.5)

    def test_metadata_frozen(self):
        asm = _assessment(metadata={"k": "v"})
        with pytest.raises(TypeError):
            asm.metadata["new"] = "x"

    def test_to_dict(self):
        asm = _assessment()
        d = asm.to_dict()
        assert d["assessment_id"] == "asm-1"
        assert d["improvement_rate"] == 0.5


# ===================================================================
# ImprovementViolation tests
# ===================================================================


class TestImprovementViolation:
    def test_happy_path(self):
        v = _violation()
        assert v.violation_id == "viol-1"
        assert v.tenant_id == TENANT
        assert v.operation == "unapproved_high_risk"
        assert v.reason == "bad proposal"
        assert v.detected_at == TS

    def test_frozen(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.violation_id = "other"

    def test_empty_violation_id(self):
        with pytest.raises(ValueError):
            _violation(violation_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _violation(tenant_id="")

    def test_empty_operation(self):
        with pytest.raises(ValueError):
            _violation(operation="")

    def test_empty_reason(self):
        with pytest.raises(ValueError):
            _violation(reason="")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at="bad")

    def test_empty_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at="")

    def test_metadata_frozen(self):
        v = _violation(metadata={"k": "v"})
        with pytest.raises(TypeError):
            v.metadata["new"] = "x"

    def test_to_dict(self):
        v = _violation()
        d = v.to_dict()
        assert d["violation_id"] == "viol-1"


# ===================================================================
# ImprovementSnapshot tests
# ===================================================================


class TestImprovementSnapshot:
    def test_happy_path(self):
        snap = _snapshot()
        assert snap.snapshot_id == "snap-1"
        assert snap.tenant_id == TENANT
        assert snap.total_signals == 10
        assert snap.total_proposals == 5
        assert snap.total_adjustments == 3
        assert snap.total_policy_tunings == 2
        assert snap.total_execution_tunings == 1
        assert snap.total_decisions == 4
        assert snap.total_violations == 0
        assert snap.captured_at == TS

    def test_frozen(self):
        snap = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            snap.snapshot_id = "other"

    def test_empty_snapshot_id(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _snapshot(tenant_id="")

    def test_negative_total_signals(self):
        with pytest.raises(ValueError):
            _snapshot(total_signals=-1)

    def test_negative_total_proposals(self):
        with pytest.raises(ValueError):
            _snapshot(total_proposals=-1)

    def test_negative_total_adjustments(self):
        with pytest.raises(ValueError):
            _snapshot(total_adjustments=-1)

    def test_negative_total_policy_tunings(self):
        with pytest.raises(ValueError):
            _snapshot(total_policy_tunings=-1)

    def test_negative_total_execution_tunings(self):
        with pytest.raises(ValueError):
            _snapshot(total_execution_tunings=-1)

    def test_negative_total_decisions(self):
        with pytest.raises(ValueError):
            _snapshot(total_decisions=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            _snapshot(total_violations=-1)

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")

    def test_empty_captured_at(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="")

    def test_zero_totals(self):
        snap = _snapshot(
            total_signals=0, total_proposals=0, total_adjustments=0,
            total_policy_tunings=0, total_execution_tunings=0,
            total_decisions=0, total_violations=0,
        )
        assert snap.total_signals == 0

    def test_bool_total_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_signals=True)

    def test_float_total_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_proposals=1.5)

    def test_metadata_frozen(self):
        snap = _snapshot(metadata={"k": "v"})
        with pytest.raises(TypeError):
            snap.metadata["new"] = "x"

    def test_to_dict(self):
        snap = _snapshot()
        d = snap.to_dict()
        assert d["snapshot_id"] == "snap-1"
        assert d["total_signals"] == 10


# ===================================================================
# ImprovementClosureReport tests
# ===================================================================


class TestImprovementClosureReport:
    def test_happy_path(self):
        r = _closure()
        assert r.report_id == "rpt-1"
        assert r.tenant_id == TENANT
        assert r.total_signals == 10
        assert r.total_proposals == 5
        assert r.total_applied == 3
        assert r.total_rolled_back == 1
        assert r.total_violations == 0
        assert r.created_at == TS

    def test_frozen(self):
        r = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            r.report_id = "other"

    def test_empty_report_id(self):
        with pytest.raises(ValueError):
            _closure(report_id="")

    def test_empty_tenant_id(self):
        with pytest.raises(ValueError):
            _closure(tenant_id="")

    def test_negative_total_signals(self):
        with pytest.raises(ValueError):
            _closure(total_signals=-1)

    def test_negative_total_proposals(self):
        with pytest.raises(ValueError):
            _closure(total_proposals=-1)

    def test_negative_total_applied(self):
        with pytest.raises(ValueError):
            _closure(total_applied=-1)

    def test_negative_total_rolled_back(self):
        with pytest.raises(ValueError):
            _closure(total_rolled_back=-1)

    def test_negative_total_violations(self):
        with pytest.raises(ValueError):
            _closure(total_violations=-1)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _closure(created_at="bad")

    def test_empty_created_at(self):
        with pytest.raises(ValueError):
            _closure(created_at="")

    def test_zero_totals(self):
        r = _closure(
            total_signals=0, total_proposals=0, total_applied=0,
            total_rolled_back=0, total_violations=0,
        )
        assert r.total_signals == 0

    def test_bool_total_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_signals=True)

    def test_float_total_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_proposals=1.5)

    def test_metadata_frozen(self):
        r = _closure(metadata={"k": "v"})
        with pytest.raises(TypeError):
            r.metadata["new"] = "x"

    def test_to_dict(self):
        r = _closure()
        d = r.to_dict()
        assert d["report_id"] == "rpt-1"
        assert d["total_applied"] == 3


# ===================================================================
# Cross-cutting / edge-case tests
# ===================================================================


class TestCrossCutting:
    """Tests spanning multiple contract types."""

    def test_signal_equality_same_fields(self):
        a = _signal()
        b = _signal()
        assert a == b

    def test_signal_inequality_different_id(self):
        a = _signal(signal_id="sig-1")
        b = _signal(signal_id="sig-2")
        assert a != b

    def test_proposal_equality(self):
        a = _proposal()
        b = _proposal()
        assert a == b

    def test_proposal_inequality_different_status(self):
        a = _proposal(status=ImprovementStatus.PROPOSED)
        b = _proposal(status=ImprovementStatus.APPLIED)
        assert a != b

    def test_adjustment_equality(self):
        a = _adjustment()
        b = _adjustment()
        assert a == b

    def test_decision_equality(self):
        a = _decision()
        b = _decision()
        assert a == b

    def test_violation_equality(self):
        a = _violation()
        b = _violation()
        assert a == b

    def test_snapshot_equality(self):
        a = _snapshot()
        b = _snapshot()
        assert a == b

    def test_closure_equality(self):
        a = _closure()
        b = _closure()
        assert a == b

    def test_policy_tuning_equality(self):
        a = _policy_tuning()
        b = _policy_tuning()
        assert a == b

    def test_exec_tuning_equality(self):
        a = _exec_tuning()
        b = _exec_tuning()
        assert a == b

    def test_iso_z_suffix_accepted(self):
        s = _signal(first_seen_at="2025-06-01T00:00:00Z", last_seen_at="2025-06-01T00:00:00Z")
        assert s.first_seen_at == "2025-06-01T00:00:00Z"

    def test_iso_no_timezone_accepted(self):
        s = _signal(first_seen_at="2025-06-01", last_seen_at="2025-06-01")
        assert s.first_seen_at == "2025-06-01"

    def test_metadata_with_nested_list(self):
        s = _signal(metadata={"items": [1, 2, 3]})
        d = s.to_dict()
        assert d["metadata"]["items"] == [1, 2, 3]

    def test_metadata_with_nested_dict(self):
        s = _signal(metadata={"outer": {"inner": "val"}})
        d = s.to_dict()
        assert d["metadata"]["outer"]["inner"] == "val"

    def test_all_contract_types_have_to_dict(self):
        records = [
            _signal(), _proposal(), _adjustment(), _policy_tuning(),
            _exec_tuning(), _decision(), _assessment(), _violation(),
            _snapshot(), _closure(),
        ]
        for r in records:
            d = r.to_dict()
            assert isinstance(d, dict)

    def test_all_contract_types_have_to_json_dict(self):
        records = [
            _signal(), _proposal(), _adjustment(), _policy_tuning(),
            _exec_tuning(), _decision(), _assessment(), _violation(),
            _snapshot(), _closure(),
        ]
        for r in records:
            d = r.to_json_dict()
            assert isinstance(d, dict)

    def test_all_contract_types_have_to_json(self):
        records = [
            _signal(), _proposal(), _adjustment(), _policy_tuning(),
            _exec_tuning(), _decision(), _assessment(), _violation(),
            _snapshot(), _closure(),
        ]
        for r in records:
            j = r.to_json()
            assert isinstance(j, str)
            assert len(j) > 0

    def test_to_json_roundtrip_no_crash(self):
        import json
        records = [
            _signal(), _proposal(), _adjustment(), _policy_tuning(),
            _exec_tuning(), _decision(), _assessment(), _violation(),
            _snapshot(), _closure(),
        ]
        for r in records:
            parsed = json.loads(r.to_json())
            assert isinstance(parsed, dict)


class TestSignalVariousDates:
    """Date validation edge cases."""

    def test_date_only(self):
        s = _signal(first_seen_at="2025-06-01", last_seen_at="2025-06-01")
        assert s.first_seen_at == "2025-06-01"

    def test_date_with_time(self):
        s = _signal(first_seen_at="2025-06-01T12:30:00", last_seen_at="2025-06-01T12:30:00")
        assert s.first_seen_at == "2025-06-01T12:30:00"

    def test_date_with_tz(self):
        s = _signal(first_seen_at="2025-06-01T12:30:00+05:30", last_seen_at="2025-06-01T12:30:00+05:30")
        assert s.first_seen_at == "2025-06-01T12:30:00+05:30"

    def test_date_with_z(self):
        s = _signal(first_seen_at="2025-06-01T00:00:00Z", last_seen_at="2025-06-01T00:00:00Z")
        assert s.first_seen_at == "2025-06-01T00:00:00Z"

    def test_date_with_neg_tz(self):
        s = _signal(first_seen_at="2025-06-01T00:00:00-08:00", last_seen_at="2025-06-01T00:00:00-08:00")
        assert s.first_seen_at == "2025-06-01T00:00:00-08:00"


class TestFrozenFieldsAllTypes:
    """Verify frozen on every field of every contract type."""

    def test_signal_frozen_tenant(self):
        s = _signal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.tenant_id = "other"

    def test_signal_frozen_kind(self):
        s = _signal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.kind = LearningSignalKind.FORECAST_DRIFT

    def test_signal_frozen_description(self):
        s = _signal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.description = "changed"

    def test_signal_frozen_occurrence_count(self):
        s = _signal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            s.occurrence_count = 99

    def test_proposal_frozen_kind(self):
        p = _proposal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.kind = ImprovementKind.POLICY

    def test_proposal_frozen_scope(self):
        p = _proposal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.scope = ImprovementScope.PLATFORM

    def test_proposal_frozen_risk_level(self):
        p = _proposal()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            p.risk_level = ImprovementRiskLevel.CRITICAL

    def test_adjustment_frozen_old_value(self):
        a = _adjustment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.old_value = "999"

    def test_adjustment_frozen_proposed_value(self):
        a = _adjustment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            a.proposed_value = "999"

    def test_decision_frozen_disposition(self):
        dec = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            dec.disposition = ApprovalDisposition.APPROVED

    def test_assessment_frozen_rate(self):
        asm = _assessment()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            asm.improvement_rate = 0.9

    def test_violation_frozen_operation(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            v.operation = "changed"

    def test_snapshot_frozen_total_signals(self):
        snap = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            snap.total_signals = 999

    def test_closure_frozen_total_applied(self):
        r = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            r.total_applied = 999

    def test_policy_tuning_frozen_rule_target(self):
        pt = _policy_tuning()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            pt.rule_target = "changed"

    def test_exec_tuning_frozen_change_type(self):
        et = _exec_tuning()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            et.change_type = "changed"
