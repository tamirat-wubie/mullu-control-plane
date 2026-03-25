"""Comprehensive tests for the SelfTuningEngine.

Covers construction, learning signals, proposals, approvals, rejections,
deferrals, parameter adjustments, policy tunings, execution tunings,
rollbacks, assessments, snapshots, violation detection, state_hash,
golden scenarios, and deterministic replay with FixedClock.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.self_tuning import (
    ApprovalDisposition,
    ImprovementKind,
    ImprovementRiskLevel,
    ImprovementScope,
    ImprovementStatus,
    LearningSignalKind,
)
from mcoi_runtime.core.engine_protocol import FixedClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.self_tuning import SelfTuningEngine


# ===================================================================
# Fixtures
# ===================================================================

FIXED_TIME = "2026-01-01T00:00:00+00:00"
TENANT = "tenant-1"
TENANT2 = "tenant-2"


@pytest.fixture
def clock():
    return FixedClock(FIXED_TIME)


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def engine(es, clock):
    return SelfTuningEngine(es, clock=clock)


def _register_signal(eng, signal_id="sig-1", tenant_id=TENANT,
                      kind=LearningSignalKind.EXECUTION_FAILURE,
                      source_runtime="rt-a", description="test signal",
                      occurrence_count=1):
    return eng.register_learning_signal(
        signal_id=signal_id, tenant_id=tenant_id, kind=kind,
        source_runtime=source_runtime, description=description,
        occurrence_count=occurrence_count,
    )


def _propose(eng, proposal_id="prop-1", tenant_id=TENANT, signal_ref="sig-1",
             kind=ImprovementKind.PARAMETER, scope=ImprovementScope.LOCAL,
             risk_level=ImprovementRiskLevel.LOW, description="test proposal",
             justification="test justification"):
    return eng.propose_improvement(
        proposal_id=proposal_id, tenant_id=tenant_id, signal_ref=signal_ref,
        kind=kind, scope=scope, risk_level=risk_level,
        description=description, justification=justification,
    )


# ===================================================================
# Construction
# ===================================================================


class TestConstruction:
    def test_valid_construction(self, es, clock):
        eng = SelfTuningEngine(es, clock=clock)
        assert eng.signal_count == 0

    def test_default_clock(self, es):
        eng = SelfTuningEngine(es)
        assert eng.signal_count == 0

    def test_invalid_event_spine_string(self):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningEngine("not-an-event-spine")

    def test_invalid_event_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningEngine(None)

    def test_invalid_event_spine_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            SelfTuningEngine(42)

    def test_initial_counts_all_zero(self, engine):
        assert engine.signal_count == 0
        assert engine.proposal_count == 0
        assert engine.adjustment_count == 0
        assert engine.policy_tuning_count == 0
        assert engine.execution_tuning_count == 0
        assert engine.decision_count == 0
        assert engine.violation_count == 0


# ===================================================================
# Learning Signals
# ===================================================================


class TestLearningSignals:
    def test_register_signal(self, engine):
        sig = _register_signal(engine)
        assert sig.signal_id == "sig-1"
        assert sig.tenant_id == TENANT
        assert sig.kind == LearningSignalKind.EXECUTION_FAILURE
        assert engine.signal_count == 1

    def test_register_multiple_signals(self, engine):
        _register_signal(engine, signal_id="sig-1")
        _register_signal(engine, signal_id="sig-2")
        _register_signal(engine, signal_id="sig-3")
        assert engine.signal_count == 3

    def test_duplicate_signal_id(self, engine):
        _register_signal(engine, signal_id="sig-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate signal_id"):
            _register_signal(engine, signal_id="sig-1")

    def test_get_signal(self, engine):
        _register_signal(engine, signal_id="sig-1")
        s = engine.get_signal("sig-1")
        assert s.signal_id == "sig-1"

    def test_get_signal_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown signal_id"):
            engine.get_signal("nonexistent")

    def test_signals_for_tenant(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-2", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-3", tenant_id=TENANT2)
        sigs = engine.signals_for_tenant(TENANT)
        assert len(sigs) == 2

    def test_signals_for_tenant_empty(self, engine):
        assert len(engine.signals_for_tenant(TENANT)) == 0

    def test_signals_by_kind(self, engine):
        _register_signal(engine, signal_id="sig-1", kind=LearningSignalKind.EXECUTION_FAILURE)
        _register_signal(engine, signal_id="sig-2", kind=LearningSignalKind.FORECAST_DRIFT)
        _register_signal(engine, signal_id="sig-3", kind=LearningSignalKind.EXECUTION_FAILURE)
        result = engine.signals_by_kind(TENANT, LearningSignalKind.EXECUTION_FAILURE)
        assert len(result) == 2

    def test_signals_by_kind_no_match(self, engine):
        _register_signal(engine, signal_id="sig-1", kind=LearningSignalKind.EXECUTION_FAILURE)
        result = engine.signals_by_kind(TENANT, LearningSignalKind.FORECAST_DRIFT)
        assert len(result) == 0

    def test_all_signal_kinds_accepted(self, engine):
        for i, kind in enumerate(LearningSignalKind):
            _register_signal(engine, signal_id=f"sig-{i}", kind=kind)
        assert engine.signal_count == len(LearningSignalKind)

    def test_signal_emits_event(self, engine, es):
        before = es.event_count
        _register_signal(engine)
        assert es.event_count > before

    def test_signal_occurrence_count(self, engine):
        sig = _register_signal(engine, occurrence_count=10)
        assert sig.occurrence_count == 10

    def test_signal_timestamps_from_clock(self, engine):
        sig = _register_signal(engine)
        assert sig.first_seen_at == FIXED_TIME
        assert sig.last_seen_at == FIXED_TIME

    def test_signal_return_is_frozen(self, engine):
        sig = _register_signal(engine)
        with pytest.raises((AttributeError, Exception)):
            sig.signal_id = "changed"

    def test_signals_for_tenant_returns_tuple(self, engine):
        _register_signal(engine)
        result = engine.signals_for_tenant(TENANT)
        assert isinstance(result, tuple)

    def test_signals_by_kind_returns_tuple(self, engine):
        result = engine.signals_by_kind(TENANT, LearningSignalKind.EXECUTION_FAILURE)
        assert isinstance(result, tuple)


# ===================================================================
# Proposals — LOW risk auto-applies
# ===================================================================


class TestProposalsLowRisk:
    def test_low_risk_auto_applies(self, engine):
        _register_signal(engine)
        p = _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        assert p.status == ImprovementStatus.APPLIED

    def test_low_risk_creates_auto_decision(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        assert engine.decision_count == 1

    def test_low_risk_decision_is_auto_applied(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        # Check via snapshot
        snap = engine.snapshot()
        decisions = snap["decisions"]
        assert len(decisions) == 1
        dec = list(decisions.values())[0]
        assert dec["disposition"] == ApprovalDisposition.AUTO_APPLIED

    def test_low_risk_emits_event(self, engine, es):
        _register_signal(engine)
        before = es.event_count
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        assert es.event_count > before


# ===================================================================
# Proposals — MEDIUM+ requires approval
# ===================================================================


class TestProposalsMediumPlus:
    def test_medium_risk_stays_proposed(self, engine):
        _register_signal(engine)
        p = _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        assert p.status == ImprovementStatus.PROPOSED

    def test_high_risk_stays_proposed(self, engine):
        _register_signal(engine)
        p = _propose(engine, risk_level=ImprovementRiskLevel.HIGH)
        assert p.status == ImprovementStatus.PROPOSED

    def test_critical_risk_stays_proposed(self, engine):
        _register_signal(engine)
        p = _propose(engine, risk_level=ImprovementRiskLevel.CRITICAL)
        assert p.status == ImprovementStatus.PROPOSED

    def test_medium_no_auto_decision(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        assert engine.decision_count == 0

    def test_high_no_auto_decision(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.HIGH)
        assert engine.decision_count == 0


# ===================================================================
# Proposals — CONSTITUTIONAL always CRITICAL
# ===================================================================


class TestProposalsConstitutional:
    def test_constitutional_scope_overrides_to_critical(self, engine):
        _register_signal(engine)
        p = _propose(engine, scope=ImprovementScope.CONSTITUTIONAL,
                     risk_level=ImprovementRiskLevel.LOW)
        assert p.risk_level == ImprovementRiskLevel.CRITICAL

    def test_constitutional_stays_proposed(self, engine):
        _register_signal(engine)
        p = _propose(engine, scope=ImprovementScope.CONSTITUTIONAL,
                     risk_level=ImprovementRiskLevel.LOW)
        assert p.status == ImprovementStatus.PROPOSED

    def test_constitutional_medium_overrides_to_critical(self, engine):
        _register_signal(engine)
        p = _propose(engine, scope=ImprovementScope.CONSTITUTIONAL,
                     risk_level=ImprovementRiskLevel.MEDIUM)
        assert p.risk_level == ImprovementRiskLevel.CRITICAL

    def test_constitutional_high_overrides_to_critical(self, engine):
        _register_signal(engine)
        p = _propose(engine, scope=ImprovementScope.CONSTITUTIONAL,
                     risk_level=ImprovementRiskLevel.HIGH)
        assert p.risk_level == ImprovementRiskLevel.CRITICAL

    def test_constitutional_critical_stays_critical(self, engine):
        _register_signal(engine)
        p = _propose(engine, scope=ImprovementScope.CONSTITUTIONAL,
                     risk_level=ImprovementRiskLevel.CRITICAL)
        assert p.risk_level == ImprovementRiskLevel.CRITICAL

    def test_constitutional_no_auto_decision(self, engine):
        _register_signal(engine)
        _propose(engine, scope=ImprovementScope.CONSTITUTIONAL,
                 risk_level=ImprovementRiskLevel.LOW)
        assert engine.decision_count == 0


# ===================================================================
# Proposal get / query
# ===================================================================


class TestProposalQuery:
    def test_get_proposal(self, engine):
        _register_signal(engine)
        _propose(engine)
        p = engine.get_proposal("prop-1")
        assert p.proposal_id == "prop-1"

    def test_get_proposal_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown proposal_id"):
            engine.get_proposal("nonexistent")

    def test_proposals_for_tenant(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-2", tenant_id=TENANT2)
        _propose(engine, proposal_id="p1", signal_ref="sig-1", tenant_id=TENANT)
        _propose(engine, proposal_id="p2", signal_ref="sig-2", tenant_id=TENANT2)
        result = engine.proposals_for_tenant(TENANT)
        assert len(result) == 1

    def test_proposals_for_tenant_empty(self, engine):
        assert len(engine.proposals_for_tenant(TENANT)) == 0

    def test_proposals_for_tenant_returns_tuple(self, engine):
        result = engine.proposals_for_tenant(TENANT)
        assert isinstance(result, tuple)

    def test_duplicate_proposal_id(self, engine):
        _register_signal(engine)
        _propose(engine, proposal_id="prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate proposal_id"):
            _propose(engine, proposal_id="prop-1", signal_ref="sig-1")

    def test_proposal_emits_event(self, engine, es):
        _register_signal(engine)
        before = es.event_count
        _propose(engine)
        assert es.event_count > before

    def test_all_kinds_accepted(self, engine):
        for i, kind in enumerate(ImprovementKind):
            _register_signal(engine, signal_id=f"sig-{i}")
            _propose(engine, proposal_id=f"prop-{i}", signal_ref=f"sig-{i}", kind=kind)
        assert engine.proposal_count == len(ImprovementKind)

    def test_all_scopes_accepted(self, engine):
        for i, scope in enumerate(ImprovementScope):
            _register_signal(engine, signal_id=f"sig-{i}")
            _propose(engine, proposal_id=f"prop-{i}", signal_ref=f"sig-{i}",
                     scope=scope, risk_level=ImprovementRiskLevel.MEDIUM)
        assert engine.proposal_count == len(ImprovementScope)


# ===================================================================
# Approval / Rejection / Deferral
# ===================================================================


class TestApproval:
    def test_approve_proposed(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        p = engine.approve_improvement("prop-1")
        assert p.status == ImprovementStatus.APPROVED

    def test_approve_creates_decision(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        assert engine.decision_count == 1

    def test_approve_emits_event(self, engine, es):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        before = es.event_count
        engine.approve_improvement("prop-1")
        assert es.event_count > before

    def test_approve_deferred(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.defer_improvement("prop-1")
        p = engine.approve_improvement("prop-1")
        assert p.status == ImprovementStatus.APPROVED


class TestRejection:
    def test_reject_proposed(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        p = engine.reject_improvement("prop-1")
        assert p.status == ImprovementStatus.REJECTED

    def test_reject_creates_decision(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.reject_improvement("prop-1")
        assert engine.decision_count == 1

    def test_reject_deferred(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.defer_improvement("prop-1")
        p = engine.reject_improvement("prop-1")
        assert p.status == ImprovementStatus.REJECTED

    def test_reject_emits_event(self, engine, es):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        before = es.event_count
        engine.reject_improvement("prop-1")
        assert es.event_count > before


class TestDeferral:
    def test_defer_proposed(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        p = engine.defer_improvement("prop-1")
        assert p.status == ImprovementStatus.DEFERRED

    def test_defer_creates_decision(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.defer_improvement("prop-1")
        assert engine.decision_count == 1

    def test_defer_emits_event(self, engine, es):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        before = es.event_count
        engine.defer_improvement("prop-1")
        assert es.event_count > before

    def test_cannot_defer_already_deferred(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.defer_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot transition"):
            engine.defer_improvement("prop-1")


# ===================================================================
# Terminal states block transitions
# ===================================================================


class TestTerminalStates:
    def test_applied_blocks_approve(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)  # auto-applied
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.approve_improvement("prop-1")

    def test_applied_blocks_reject(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.reject_improvement("prop-1")

    def test_applied_blocks_defer(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.defer_improvement("prop-1")

    def test_rejected_blocks_approve(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.reject_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.approve_improvement("prop-1")

    def test_rejected_blocks_reject(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.reject_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.reject_improvement("prop-1")

    def test_rejected_blocks_defer(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.reject_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.defer_improvement("prop-1")

    def test_rolled_back_blocks_approve(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.approve_improvement("prop-1")

    def test_rolled_back_blocks_reject(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.reject_improvement("prop-1")

    def test_rolled_back_blocks_defer(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.defer_improvement("prop-1")


# ===================================================================
# Parameter adjustments
# ===================================================================


class TestParameterAdjustments:
    def test_apply_from_auto_applied(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)  # auto-applied
        adj = engine.apply_parameter_adjustment(
            "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
        )
        assert adj.adjustment_id == "adj-1"
        assert adj.applied_at == FIXED_TIME
        assert engine.adjustment_count == 1

    def test_apply_from_approved(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        adj = engine.apply_parameter_adjustment(
            "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
        )
        assert adj.adjustment_id == "adj-1"

    def test_apply_marks_proposal_applied(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        engine.apply_parameter_adjustment(
            "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
        )
        p = engine.get_proposal("prop-1")
        assert p.status == ImprovementStatus.APPLIED

    def test_cannot_apply_from_proposed(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        with pytest.raises(RuntimeCoreInvariantError, match="must be APPROVED or APPLIED"):
            engine.apply_parameter_adjustment(
                "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
            )

    def test_cannot_apply_from_rejected(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.reject_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="must be APPROVED or APPLIED"):
            engine.apply_parameter_adjustment(
                "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
            )

    def test_duplicate_adjustment_id(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.apply_parameter_adjustment(
            "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate adjustment_id"):
            engine.apply_parameter_adjustment(
                "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
            )

    def test_adjustment_emits_event(self, engine, es):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        before = es.event_count
        engine.apply_parameter_adjustment(
            "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
        )
        assert es.event_count > before

    def test_multiple_adjustments_same_proposal(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.apply_parameter_adjustment(
            "adj-1", TENANT, "prop-1", "comp-a", "timeout", "30", "60",
        )
        engine.apply_parameter_adjustment(
            "adj-2", TENANT, "prop-1", "comp-b", "retries", "3", "5",
        )
        assert engine.adjustment_count == 2


# ===================================================================
# Policy tunings
# ===================================================================


class TestPolicyTunings:
    def test_apply_policy_tuning(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        pt = engine.apply_policy_tuning(
            "pt-1", TENANT, "prop-1", "rule-x", "on", "off",
            ImprovementScope.LOCAL,
        )
        assert pt.tuning_id == "pt-1"
        assert engine.policy_tuning_count == 1

    def test_apply_policy_tuning_from_approved(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        pt = engine.apply_policy_tuning(
            "pt-1", TENANT, "prop-1", "rule-x", "on", "off",
            ImprovementScope.TENANT,
        )
        assert pt.tuning_id == "pt-1"

    def test_cannot_apply_from_proposed(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.apply_policy_tuning(
                "pt-1", TENANT, "prop-1", "rule-x", "on", "off",
                ImprovementScope.LOCAL,
            )

    def test_duplicate_tuning_id(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.apply_policy_tuning(
            "pt-1", TENANT, "prop-1", "rule-x", "on", "off",
            ImprovementScope.LOCAL,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate tuning_id"):
            engine.apply_policy_tuning(
                "pt-1", TENANT, "prop-1", "rule-y", "on", "off",
                ImprovementScope.LOCAL,
            )

    def test_policy_tuning_emits_event(self, engine, es):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        before = es.event_count
        engine.apply_policy_tuning(
            "pt-1", TENANT, "prop-1", "rule-x", "on", "off",
            ImprovementScope.LOCAL,
        )
        assert es.event_count > before

    def test_policy_tuning_marks_applied(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        engine.apply_policy_tuning(
            "pt-1", TENANT, "prop-1", "rule-x", "on", "off",
            ImprovementScope.LOCAL,
        )
        p = engine.get_proposal("prop-1")
        assert p.status == ImprovementStatus.APPLIED


# ===================================================================
# Execution tunings
# ===================================================================


class TestExecutionTunings:
    def test_apply_execution_tuning(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        et = engine.apply_execution_tuning(
            "et-1", TENANT, "prop-1", "rt-b", "scale-up", "20%", "none",
        )
        assert et.tuning_id == "et-1"
        assert engine.execution_tuning_count == 1

    def test_apply_from_approved(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        et = engine.apply_execution_tuning(
            "et-1", TENANT, "prop-1", "rt-b", "scale-up", "20%", "none",
        )
        assert et.tuning_id == "et-1"

    def test_cannot_apply_from_proposed(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.apply_execution_tuning(
                "et-1", TENANT, "prop-1", "rt-b", "scale-up", "20%", "none",
            )

    def test_duplicate_tuning_id(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.apply_execution_tuning(
            "et-1", TENANT, "prop-1", "rt-b", "scale-up", "20%", "none",
        )
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate tuning_id"):
            engine.apply_execution_tuning(
                "et-1", TENANT, "prop-1", "rt-c", "scale-down", "10%", "minimal",
            )

    def test_execution_tuning_emits_event(self, engine, es):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        before = es.event_count
        engine.apply_execution_tuning(
            "et-1", TENANT, "prop-1", "rt-b", "scale-up", "20%", "none",
        )
        assert es.event_count > before

    def test_execution_tuning_marks_applied(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        engine.apply_execution_tuning(
            "et-1", TENANT, "prop-1", "rt-b", "scale-up", "20%", "none",
        )
        p = engine.get_proposal("prop-1")
        assert p.status == ImprovementStatus.APPLIED


# ===================================================================
# Rollback
# ===================================================================


class TestRollback:
    def test_rollback_applied(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        p = engine.rollback_improvement("prop-1")
        assert p.status == ImprovementStatus.ROLLED_BACK

    def test_rollback_creates_decision(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        before = engine.decision_count
        engine.rollback_improvement("prop-1")
        assert engine.decision_count > before

    def test_rollback_emits_event(self, engine, es):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        before = es.event_count
        engine.rollback_improvement("prop-1")
        assert es.event_count > before

    def test_cannot_rollback_proposed(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        with pytest.raises(RuntimeCoreInvariantError, match="Can only rollback APPLIED"):
            engine.rollback_improvement("prop-1")

    def test_cannot_rollback_approved(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only rollback APPLIED"):
            engine.rollback_improvement("prop-1")

    def test_cannot_rollback_rejected(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.reject_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only rollback APPLIED"):
            engine.rollback_improvement("prop-1")

    def test_cannot_rollback_deferred(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.defer_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only rollback APPLIED"):
            engine.rollback_improvement("prop-1")

    def test_double_rollback_blocked(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Can only rollback APPLIED"):
            engine.rollback_improvement("prop-1")

    def test_rollback_unknown_proposal(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown proposal_id"):
            engine.rollback_improvement("nonexistent")


# ===================================================================
# Assessment
# ===================================================================


class TestAssessment:
    def test_empty_assessment(self, engine):
        asm = engine.improvement_assessment("asm-1", TENANT)
        assert asm.total_signals == 0
        assert asm.total_proposals == 0
        assert asm.total_applied == 0
        assert asm.total_rolled_back == 0
        assert asm.improvement_rate == 1.0  # 0/0 -> 1.0

    def test_assessment_with_data(self, engine):
        _register_signal(engine, signal_id="sig-1")
        _register_signal(engine, signal_id="sig-2")
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 risk_level=ImprovementRiskLevel.LOW)
        _propose(engine, proposal_id="p2", signal_ref="sig-2",
                 risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("p1")
        asm = engine.improvement_assessment("asm-1", TENANT)
        assert asm.total_signals == 2
        assert asm.total_proposals == 2
        assert asm.total_applied == 1
        assert asm.total_rolled_back == 1
        assert asm.improvement_rate == 0.5

    def test_assessment_emits_event(self, engine, es):
        before = es.event_count
        engine.improvement_assessment("asm-1", TENANT)
        assert es.event_count > before

    def test_assessment_timestamp(self, engine):
        asm = engine.improvement_assessment("asm-1", TENANT)
        assert asm.assessed_at == FIXED_TIME

    def test_assessment_tenant_isolation(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-2", tenant_id=TENANT2)
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 tenant_id=TENANT, risk_level=ImprovementRiskLevel.LOW)
        _propose(engine, proposal_id="p2", signal_ref="sig-2",
                 tenant_id=TENANT2, risk_level=ImprovementRiskLevel.LOW)
        asm = engine.improvement_assessment("asm-1", TENANT)
        assert asm.total_signals == 1
        assert asm.total_proposals == 1

    def test_assessment_rate_all_applied(self, engine):
        _register_signal(engine, signal_id="sig-1")
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 risk_level=ImprovementRiskLevel.LOW)
        asm = engine.improvement_assessment("asm-1", TENANT)
        assert asm.improvement_rate == 1.0

    def test_assessment_rate_all_rolled_back(self, engine):
        _register_signal(engine, signal_id="sig-1")
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("p1")
        asm = engine.improvement_assessment("asm-1", TENANT)
        assert asm.improvement_rate == 0.0


# ===================================================================
# Snapshot
# ===================================================================


class TestSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.improvement_snapshot("snap-1", TENANT)
        assert snap.total_signals == 0
        assert snap.total_proposals == 0
        assert snap.total_adjustments == 0
        assert snap.total_policy_tunings == 0
        assert snap.total_execution_tunings == 0
        assert snap.total_decisions == 0
        assert snap.total_violations == 0

    def test_snapshot_with_data(self, engine):
        _register_signal(engine, signal_id="sig-1")
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 risk_level=ImprovementRiskLevel.LOW)
        engine.apply_parameter_adjustment(
            "adj-1", TENANT, "p1", "comp-a", "timeout", "30", "60",
        )
        snap = engine.improvement_snapshot("snap-1", TENANT)
        assert snap.total_signals == 1
        assert snap.total_proposals == 1
        assert snap.total_adjustments == 1
        assert snap.total_decisions == 1  # auto-applied decision

    def test_snapshot_timestamp(self, engine):
        snap = engine.improvement_snapshot("snap-1", TENANT)
        assert snap.captured_at == FIXED_TIME

    def test_snapshot_tenant_isolation(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-2", tenant_id=TENANT2)
        snap = engine.improvement_snapshot("snap-1", TENANT)
        assert snap.total_signals == 1


# ===================================================================
# Violation detection
# ===================================================================


class TestViolationDetection:
    def test_no_violations(self, engine):
        viols = engine.detect_improvement_violations(TENANT)
        assert len(viols) == 0

    def test_idempotent(self, engine):
        v1 = engine.detect_improvement_violations(TENANT)
        v2 = engine.detect_improvement_violations(TENANT)
        assert v1 == v2

    def test_excessive_rollbacks(self, engine):
        # Need more rollbacks than applied
        _register_signal(engine, signal_id="sig-1")
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("p1")
        viols = engine.detect_improvement_violations(TENANT)
        assert any(v.operation == "excessive_rollbacks" for v in viols)

    def test_excessive_rollbacks_idempotent(self, engine):
        _register_signal(engine, signal_id="sig-1")
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("p1")
        v1 = engine.detect_improvement_violations(TENANT)
        assert len(v1) >= 1
        v2 = engine.detect_improvement_violations(TENANT)
        assert len(v2) == 0  # idempotent — already stored

    def test_violation_detection_increments_violation_count(self, engine):
        _register_signal(engine, signal_id="sig-1")
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("p1")
        before = engine.violation_count
        engine.detect_improvement_violations(TENANT)
        assert engine.violation_count > before

    def test_second_call_does_not_add_duplicates(self, engine):
        _register_signal(engine, signal_id="sig-1")
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("p1")
        engine.detect_improvement_violations(TENANT)
        count_after_first = engine.violation_count
        engine.detect_improvement_violations(TENANT)
        assert engine.violation_count == count_after_first

    def test_violation_returns_tuple(self, engine):
        result = engine.detect_improvement_violations(TENANT)
        assert isinstance(result, tuple)

    def test_tenant_isolation(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 tenant_id=TENANT, risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("p1")
        viols_t1 = engine.detect_improvement_violations(TENANT)
        viols_t2 = engine.detect_improvement_violations(TENANT2)
        assert len(viols_t1) > 0
        assert len(viols_t2) == 0


# ===================================================================
# State hash
# ===================================================================


class TestStateHash:
    def test_empty_state_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_state_hash_changes_on_signal(self, engine):
        h1 = engine.state_hash()
        _register_signal(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_changes_on_proposal(self, engine):
        _register_signal(engine)
        h1 = engine.state_hash()
        _propose(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_state_hash_deterministic(self, engine):
        _register_signal(engine)
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


# ===================================================================
# Engine snapshot (full)
# ===================================================================


class TestEngineSnapshot:
    def test_snapshot_keys(self, engine):
        snap = engine.snapshot()
        assert "signals" in snap
        assert "proposals" in snap
        assert "adjustments" in snap
        assert "policy_tunings" in snap
        assert "execution_tunings" in snap
        assert "decisions" in snap
        assert "violations" in snap
        assert "_state_hash" in snap

    def test_snapshot_empty(self, engine):
        snap = engine.snapshot()
        assert len(snap["signals"]) == 0
        assert len(snap["proposals"]) == 0

    def test_snapshot_with_data(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        snap = engine.snapshot()
        assert len(snap["signals"]) == 1
        assert len(snap["proposals"]) == 1
        assert len(snap["decisions"]) == 1


# ===================================================================
# Golden Scenarios
# ===================================================================


class TestGoldenScenario1ExecutionTimeout:
    """Repeated execution timeout -> signal -> LOW risk proposal -> auto-applies."""

    def test_full_flow(self, engine, es):
        sig = engine.register_learning_signal(
            signal_id="sig-timeout-1",
            tenant_id=TENANT,
            kind=LearningSignalKind.EXECUTION_FAILURE,
            source_runtime="execution-engine",
            description="Repeated execution timeout on task-queue",
            occurrence_count=5,
        )
        assert sig.kind == LearningSignalKind.EXECUTION_FAILURE
        assert sig.occurrence_count == 5

        prop = engine.propose_improvement(
            proposal_id="prop-timeout-1",
            tenant_id=TENANT,
            signal_ref="sig-timeout-1",
            kind=ImprovementKind.PARAMETER,
            scope=ImprovementScope.LOCAL,
            risk_level=ImprovementRiskLevel.LOW,
            description="Increase timeout from 30s to 60s",
            justification="5 consecutive timeouts detected",
        )
        assert prop.status == ImprovementStatus.APPLIED
        assert prop.risk_level == ImprovementRiskLevel.LOW
        assert engine.decision_count == 1

        assert es.event_count >= 2  # signal + proposal events


class TestGoldenScenario2WorkforceOverload:
    """Workforce overload -> signal -> MEDIUM risk -> requires approval -> approve -> apply."""

    def test_full_flow(self, engine, es):
        engine.register_learning_signal(
            signal_id="sig-overload-1",
            tenant_id=TENANT,
            kind=LearningSignalKind.WORKFORCE_OVERLOAD,
            source_runtime="workforce-engine",
            description="Agent pool at 95% capacity",
        )

        prop = engine.propose_improvement(
            proposal_id="prop-overload-1",
            tenant_id=TENANT,
            signal_ref="sig-overload-1",
            kind=ImprovementKind.STAFFING,
            scope=ImprovementScope.TENANT,
            risk_level=ImprovementRiskLevel.MEDIUM,
            description="Add 2 agents to pool",
            justification="Sustained overload detected",
        )
        assert prop.status == ImprovementStatus.PROPOSED
        assert engine.decision_count == 0

        approved = engine.approve_improvement("prop-overload-1")
        assert approved.status == ImprovementStatus.APPROVED
        assert engine.decision_count == 1

        adj = engine.apply_parameter_adjustment(
            "adj-overload-1", TENANT, "prop-overload-1",
            "agent-pool", "pool_size", "10", "12",
        )
        assert adj.applied_at == FIXED_TIME
        assert engine.get_proposal("prop-overload-1").status == ImprovementStatus.APPLIED


class TestGoldenScenario3ForecastDrift:
    """Forecast drift -> signal -> parameter adjustment applied with rollback point."""

    def test_full_flow(self, engine):
        engine.register_learning_signal(
            signal_id="sig-drift-1",
            tenant_id=TENANT,
            kind=LearningSignalKind.FORECAST_DRIFT,
            source_runtime="forecasting-engine",
            description="Revenue forecast drifted 15%",
        )

        prop = engine.propose_improvement(
            proposal_id="prop-drift-1",
            tenant_id=TENANT,
            signal_ref="sig-drift-1",
            kind=ImprovementKind.PARAMETER,
            scope=ImprovementScope.RUNTIME,
            risk_level=ImprovementRiskLevel.LOW,
            description="Adjust forecast weight",
            justification="Forecast drift exceeded threshold",
        )
        assert prop.status == ImprovementStatus.APPLIED

        adj = engine.apply_parameter_adjustment(
            "adj-drift-1", TENANT, "prop-drift-1",
            "forecaster", "weight", "0.8", "0.65",
        )
        assert adj.old_value == "0.8"
        assert adj.proposed_value == "0.65"

        # Rollback point exists
        rolled = engine.rollback_improvement("prop-drift-1")
        assert rolled.status == ImprovementStatus.ROLLED_BACK


class TestGoldenScenario4ConstitutionalViolation:
    """Constitutional violation -> CRITICAL proposal -> requires approval -> cannot auto-apply."""

    def test_full_flow(self, engine):
        engine.register_learning_signal(
            signal_id="sig-const-1",
            tenant_id=TENANT,
            kind=LearningSignalKind.CONSTITUTIONAL_VIOLATION,
            source_runtime="constitutional-engine",
            description="Unauthorized data access pattern",
        )

        prop = engine.propose_improvement(
            proposal_id="prop-const-1",
            tenant_id=TENANT,
            signal_ref="sig-const-1",
            kind=ImprovementKind.POLICY,
            scope=ImprovementScope.CONSTITUTIONAL,
            risk_level=ImprovementRiskLevel.LOW,  # Will be overridden to CRITICAL
            description="Restrict data access policy",
            justification="Constitutional violation detected",
        )
        assert prop.risk_level == ImprovementRiskLevel.CRITICAL
        assert prop.status == ImprovementStatus.PROPOSED
        assert engine.decision_count == 0

        # Requires explicit approval
        approved = engine.approve_improvement("prop-const-1")
        assert approved.status == ImprovementStatus.APPROVED


class TestGoldenScenario5AutoApplyAndRollback:
    """Approved LOW-risk tuning auto-applies and stores rollback point; then rollback succeeds."""

    def test_full_flow(self, engine):
        engine.register_learning_signal(
            signal_id="sig-tune-1",
            tenant_id=TENANT,
            kind=LearningSignalKind.OBSERVABILITY_ANOMALY,
            source_runtime="observability-engine",
            description="Latency spike detected",
        )

        prop = engine.propose_improvement(
            proposal_id="prop-tune-1",
            tenant_id=TENANT,
            signal_ref="sig-tune-1",
            kind=ImprovementKind.EXECUTION,
            scope=ImprovementScope.LOCAL,
            risk_level=ImprovementRiskLevel.LOW,
            description="Adjust cache TTL",
            justification="Latency spike detected",
        )
        assert prop.status == ImprovementStatus.APPLIED

        adj = engine.apply_parameter_adjustment(
            "adj-tune-1", TENANT, "prop-tune-1",
            "cache", "ttl", "60", "120",
        )
        assert adj.adjustment_id == "adj-tune-1"

        # Rollback succeeds
        rolled = engine.rollback_improvement("prop-tune-1")
        assert rolled.status == ImprovementStatus.ROLLED_BACK

        # Verify rollback is terminal
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.approve_improvement("prop-tune-1")


class TestGoldenScenario6ReplayDeterminism:
    """Replay with FixedClock: same ops -> same state_hash."""

    def test_full_flow(self):
        def _run():
            es = EventSpineEngine()
            clk = FixedClock(FIXED_TIME)
            eng = SelfTuningEngine(es, clock=clk)
            eng.register_learning_signal(
                signal_id="sig-r1", tenant_id=TENANT,
                kind=LearningSignalKind.EXECUTION_FAILURE,
                source_runtime="rt", description="fail",
            )
            eng.propose_improvement(
                proposal_id="prop-r1", tenant_id=TENANT, signal_ref="sig-r1",
                kind=ImprovementKind.PARAMETER, scope=ImprovementScope.LOCAL,
                risk_level=ImprovementRiskLevel.MEDIUM,
                description="fix", justification="because",
            )
            eng.approve_improvement("prop-r1")
            eng.apply_parameter_adjustment(
                "adj-r1", TENANT, "prop-r1", "comp", "p", "old", "new",
            )
            return eng.state_hash()

        h1 = _run()
        h2 = _run()
        assert h1 == h2


# ===================================================================
# Edge cases: multiple tenants
# ===================================================================


class TestMultiTenant:
    def test_signals_isolated(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-2", tenant_id=TENANT2)
        assert len(engine.signals_for_tenant(TENANT)) == 1
        assert len(engine.signals_for_tenant(TENANT2)) == 1

    def test_proposals_isolated(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-2", tenant_id=TENANT2)
        _propose(engine, proposal_id="p1", signal_ref="sig-1", tenant_id=TENANT)
        _propose(engine, proposal_id="p2", signal_ref="sig-2", tenant_id=TENANT2)
        assert len(engine.proposals_for_tenant(TENANT)) == 1
        assert len(engine.proposals_for_tenant(TENANT2)) == 1

    def test_snapshots_isolated(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-2", tenant_id=TENANT2)
        snap1 = engine.improvement_snapshot("snap-1", TENANT)
        snap2 = engine.improvement_snapshot("snap-2", TENANT2)
        assert snap1.total_signals == 1
        assert snap2.total_signals == 1

    def test_violations_isolated(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 tenant_id=TENANT, risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("p1")
        viols_t1 = engine.detect_improvement_violations(TENANT)
        viols_t2 = engine.detect_improvement_violations(TENANT2)
        assert len(viols_t1) > 0
        assert len(viols_t2) == 0

    def test_assessment_isolated(self, engine):
        _register_signal(engine, signal_id="sig-1", tenant_id=TENANT)
        _register_signal(engine, signal_id="sig-2", tenant_id=TENANT2)
        _propose(engine, proposal_id="p1", signal_ref="sig-1",
                 tenant_id=TENANT, risk_level=ImprovementRiskLevel.LOW)
        asm1 = engine.improvement_assessment("asm-1", TENANT)
        asm2 = engine.improvement_assessment("asm-2", TENANT2)
        assert asm1.total_proposals == 1
        assert asm2.total_proposals == 0


# ===================================================================
# Edge cases: transition validity
# ===================================================================


class TestTransitionValidity:
    def test_approve_from_proposed_ok(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        p = engine.approve_improvement("prop-1")
        assert p.status == ImprovementStatus.APPROVED

    def test_approve_from_deferred_ok(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.defer_improvement("prop-1")
        p = engine.approve_improvement("prop-1")
        assert p.status == ImprovementStatus.APPROVED

    def test_reject_from_proposed_ok(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        p = engine.reject_improvement("prop-1")
        assert p.status == ImprovementStatus.REJECTED

    def test_reject_from_deferred_ok(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.defer_improvement("prop-1")
        p = engine.reject_improvement("prop-1")
        assert p.status == ImprovementStatus.REJECTED

    def test_defer_from_proposed_ok(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        p = engine.defer_improvement("prop-1")
        assert p.status == ImprovementStatus.DEFERRED

    def test_cannot_approve_from_approved(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot transition"):
            engine.approve_improvement("prop-1")

    def test_cannot_defer_from_approved(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot transition"):
            engine.defer_improvement("prop-1")

    def test_cannot_reject_from_approved(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot transition"):
            engine.reject_improvement("prop-1")


# ===================================================================
# Edge cases: clock injection
# ===================================================================


class TestClockInjection:
    def test_fixed_clock_timestamps(self, engine):
        sig = _register_signal(engine)
        assert sig.first_seen_at == FIXED_TIME
        assert sig.last_seen_at == FIXED_TIME

    def test_advanced_clock(self, es):
        clk = FixedClock(FIXED_TIME)
        eng = SelfTuningEngine(es, clock=clk)
        sig1 = _register_signal(eng, signal_id="sig-1")
        assert sig1.first_seen_at == FIXED_TIME

        clk.advance("2026-06-01T12:00:00+00:00")
        sig2 = _register_signal(eng, signal_id="sig-2")
        assert sig2.first_seen_at == "2026-06-01T12:00:00+00:00"

    def test_wall_clock_used_by_default(self, es):
        eng = SelfTuningEngine(es)
        sig = eng.register_learning_signal(
            signal_id="sig-1", tenant_id=TENANT,
            kind=LearningSignalKind.EXECUTION_FAILURE,
            source_runtime="rt", description="test",
        )
        assert sig.first_seen_at != ""
        assert "T" in sig.first_seen_at or "-" in sig.first_seen_at


# ===================================================================
# Stress / bulk tests
# ===================================================================


class TestBulkOperations:
    def test_many_signals(self, engine):
        for i in range(50):
            _register_signal(engine, signal_id=f"sig-{i}")
        assert engine.signal_count == 50

    def test_many_proposals(self, engine):
        for i in range(50):
            _register_signal(engine, signal_id=f"sig-{i}")
            _propose(engine, proposal_id=f"prop-{i}", signal_ref=f"sig-{i}",
                     risk_level=ImprovementRiskLevel.LOW)
        assert engine.proposal_count == 50
        assert engine.decision_count == 50  # all auto-applied

    def test_many_adjustments(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        for i in range(20):
            engine.apply_parameter_adjustment(
                f"adj-{i}", TENANT, "prop-1", f"comp-{i}", "param", "old", "new",
            )
        assert engine.adjustment_count == 20

    def test_state_hash_stable_under_bulk(self, engine):
        for i in range(10):
            _register_signal(engine, signal_id=f"sig-{i}")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2


# ===================================================================
# Properties
# ===================================================================


class TestProperties:
    def test_signal_count(self, engine):
        assert engine.signal_count == 0
        _register_signal(engine)
        assert engine.signal_count == 1

    def test_proposal_count(self, engine):
        assert engine.proposal_count == 0
        _register_signal(engine)
        _propose(engine)
        assert engine.proposal_count == 1

    def test_adjustment_count(self, engine):
        assert engine.adjustment_count == 0
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.apply_parameter_adjustment(
            "adj-1", TENANT, "prop-1", "comp", "p", "old", "new",
        )
        assert engine.adjustment_count == 1

    def test_policy_tuning_count(self, engine):
        assert engine.policy_tuning_count == 0
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.apply_policy_tuning(
            "pt-1", TENANT, "prop-1", "rule", "on", "off",
            ImprovementScope.LOCAL,
        )
        assert engine.policy_tuning_count == 1

    def test_execution_tuning_count(self, engine):
        assert engine.execution_tuning_count == 0
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.apply_execution_tuning(
            "et-1", TENANT, "prop-1", "rt", "scale", "gain", "risk",
        )
        assert engine.execution_tuning_count == 1

    def test_decision_count(self, engine):
        assert engine.decision_count == 0
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        assert engine.decision_count == 1

    def test_violation_count(self, engine):
        assert engine.violation_count == 0
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.LOW)
        engine.rollback_improvement("prop-1")
        engine.detect_improvement_violations(TENANT)
        assert engine.violation_count >= 1


# ===================================================================
# Mixed workflow: approve then apply then rollback
# ===================================================================


class TestApproveApplyRollback:
    def test_medium_approve_adjust_rollback(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        engine.apply_parameter_adjustment(
            "adj-1", TENANT, "prop-1", "comp", "p", "old", "new",
        )
        assert engine.get_proposal("prop-1").status == ImprovementStatus.APPLIED
        rolled = engine.rollback_improvement("prop-1")
        assert rolled.status == ImprovementStatus.ROLLED_BACK

    def test_approve_policy_tuning_rollback(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        engine.apply_policy_tuning(
            "pt-1", TENANT, "prop-1", "rule", "on", "off",
            ImprovementScope.LOCAL,
        )
        assert engine.get_proposal("prop-1").status == ImprovementStatus.APPLIED
        rolled = engine.rollback_improvement("prop-1")
        assert rolled.status == ImprovementStatus.ROLLED_BACK

    def test_approve_execution_tuning_rollback(self, engine):
        _register_signal(engine)
        _propose(engine, risk_level=ImprovementRiskLevel.MEDIUM)
        engine.approve_improvement("prop-1")
        engine.apply_execution_tuning(
            "et-1", TENANT, "prop-1", "rt", "scale", "gain", "risk",
        )
        assert engine.get_proposal("prop-1").status == ImprovementStatus.APPLIED
        rolled = engine.rollback_improvement("prop-1")
        assert rolled.status == ImprovementStatus.ROLLED_BACK


# ===================================================================
# collections / snapshot internals
# ===================================================================


class TestCollections:
    def test_collections_returns_dict(self, engine):
        c = engine._collections()
        assert isinstance(c, dict)
        assert "signals" in c
        assert "proposals" in c

    def test_snapshot_includes_state_hash(self, engine):
        snap = engine.snapshot()
        assert "_state_hash" in snap
        assert isinstance(snap["_state_hash"], str)

    def test_snapshot_signals_dict(self, engine):
        _register_signal(engine)
        snap = engine.snapshot()
        assert "sig-1" in snap["signals"]

    def test_snapshot_proposals_dict(self, engine):
        _register_signal(engine)
        _propose(engine)
        snap = engine.snapshot()
        assert "prop-1" in snap["proposals"]
