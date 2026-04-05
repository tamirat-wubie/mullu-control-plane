"""Tests for experiment runtime engine (Phase 114).

Covers: ExperimentRuntimeEngine lifecycle, violation detection, snapshots,
        state hashing, replay, and golden scenarios.
"""

import pytest

from mcoi_runtime.core.engine_protocol import FixedClock, MonotonicClock
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.experiment_runtime import ExperimentRuntimeEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.contracts.experiment_runtime import (
    ExperimentPhase,
    FalsificationStatus,
    ReplicationStatus,
    ResultSignificance,
    VariableRole,
)


FIXED_TS = "2026-01-01T00:00:00+00:00"


def _make_engine(*, clock=None):
    es = EventSpineEngine()
    clk = clock or FixedClock(FIXED_TS)
    eng = ExperimentRuntimeEngine(es, clock=clk)
    return eng, es


# ===================================================================
# Constructor
# ===================================================================

class TestConstructor:
    def test_valid_event_spine(self):
        eng, _ = _make_engine()
        assert eng.design_count == 0

    def test_invalid_event_spine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            ExperimentRuntimeEngine("not_an_engine")

    def test_default_clock(self):
        es = EventSpineEngine()
        eng = ExperimentRuntimeEngine(es)
        assert eng.design_count == 0

    def test_fixed_clock_injected(self):
        eng, _ = _make_engine(clock=FixedClock("2025-01-01T00:00:00+00:00"))
        d = eng.register_design("d1", "t1", "h1", "Design 1")
        assert d.created_at == "2025-01-01T00:00:00+00:00"


# ===================================================================
# Design registration
# ===================================================================

class TestDesignRegistration:
    def test_register_design(self):
        eng, _ = _make_engine()
        d = eng.register_design("d1", "t1", "h1", "Design 1")
        assert d.design_id == "d1"
        assert d.phase == ExperimentPhase.DESIGN
        assert eng.design_count == 1

    def test_duplicate_design_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.register_design("d1", "t1", "h1", "Design 1")

    def test_get_design(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        d = eng.get_design("d1")
        assert d.design_id == "d1"

    def test_get_unknown_design(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.get_design("nonexistent")

    def test_design_emits_event(self):
        eng, es = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        assert es.event_count >= 1


# ===================================================================
# Variables
# ===================================================================

class TestVariables:
    def test_add_variable(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        v = eng.add_variable("v1", "t1", "d1", "Temp")
        assert v.variable_id == "v1"
        assert eng.variable_count == 1

    def test_variable_updates_design_count(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.add_variable("v1", "t1", "d1", "Temp")
        d = eng.get_design("d1")
        assert d.variable_count == 1

    def test_duplicate_variable_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.add_variable("v1", "t1", "d1", "Temp")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.add_variable("v1", "t1", "d1", "Temp")

    def test_variable_unknown_design(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.add_variable("v1", "t1", "nope", "Temp")

    def test_variable_on_terminal_design_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        eng.analyze_experiment("d1")
        eng.complete_experiment("d1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal experiment"):
            eng.add_variable("v1", "t1", "d1", "Temp")

    def test_variable_with_role(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        v = eng.add_variable("v1", "t1", "d1", "Temp", role=VariableRole.DEPENDENT)
        assert v.role == VariableRole.DEPENDENT

    def test_variable_emits_event(self):
        eng, es = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        before = es.event_count
        eng.add_variable("v1", "t1", "d1", "Temp")
        assert es.event_count > before


# ===================================================================
# Control Groups
# ===================================================================

class TestControlGroups:
    def test_add_control_group(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        g = eng.add_control_group("g1", "t1", "d1", "Control A")
        assert g.group_id == "g1"
        assert eng.group_count == 1

    def test_duplicate_group_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.add_control_group("g1", "t1", "d1", "Control A")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.add_control_group("g1", "t1", "d1", "Control A")

    def test_group_unknown_design(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.add_control_group("g1", "t1", "nope", "Control A")

    def test_group_on_terminal_design_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        eng.analyze_experiment("d1")
        eng.complete_experiment("d1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal experiment"):
            eng.add_control_group("g1", "t1", "d1", "Control A")

    def test_group_with_sample_size(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        g = eng.add_control_group("g1", "t1", "d1", "Control A", sample_size=50)
        assert g.sample_size == 50


# ===================================================================
# Phase transitions
# ===================================================================

class TestPhaseTransitions:
    def test_start_experiment(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        d = eng.start_experiment("d1")
        assert d.phase == ExperimentPhase.RUNNING

    def test_start_non_design_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        with pytest.raises(RuntimeCoreInvariantError, match="DESIGN"):
            eng.start_experiment("d1")

    def test_analyze_experiment(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        d = eng.analyze_experiment("d1")
        assert d.phase == ExperimentPhase.ANALYSIS

    def test_analyze_non_running_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        with pytest.raises(RuntimeCoreInvariantError, match="RUNNING"):
            eng.analyze_experiment("d1")

    def test_complete_experiment(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        eng.analyze_experiment("d1")
        d = eng.complete_experiment("d1")
        assert d.phase == ExperimentPhase.COMPLETED

    def test_complete_non_analysis_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        with pytest.raises(RuntimeCoreInvariantError, match="ANALYSIS"):
            eng.complete_experiment("d1")

    def test_fail_experiment(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        d = eng.fail_experiment("d1")
        assert d.phase == ExperimentPhase.FAILED

    def test_fail_terminal_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.fail_experiment("d1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.fail_experiment("d1")

    def test_full_lifecycle(self):
        eng, es = _make_engine()
        d = eng.register_design("d1", "t1", "h1", "Design 1")
        assert d.phase == ExperimentPhase.DESIGN
        d = eng.start_experiment("d1")
        assert d.phase == ExperimentPhase.RUNNING
        d = eng.analyze_experiment("d1")
        assert d.phase == ExperimentPhase.ANALYSIS
        d = eng.complete_experiment("d1")
        assert d.phase == ExperimentPhase.COMPLETED
        assert es.event_count >= 4


# ===================================================================
# Results
# ===================================================================

class TestResults:
    def test_record_result(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        r = eng.record_result("r1", "t1", "d1")
        assert r.result_id == "r1"
        assert eng.result_count == 1

    def test_duplicate_result_rejected(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.record_result("r1", "t1", "d1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.record_result("r1", "t1", "d1")

    def test_result_unknown_design(self):
        eng, _ = _make_engine()
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            eng.record_result("r1", "t1", "nope")

    def test_result_with_significance(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        r = eng.record_result("r1", "t1", "d1", significance=ResultSignificance.SIGNIFICANT)
        assert r.significance == ResultSignificance.SIGNIFICANT

    def test_result_emits_event(self):
        eng, es = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        before = es.event_count
        eng.record_result("r1", "t1", "d1")
        assert es.event_count > before


# ===================================================================
# Falsification
# ===================================================================

class TestFalsification:
    def test_record_falsification(self):
        eng, _ = _make_engine()
        f = eng.record_falsification("f1", "t1", "h1", "e1")
        assert f.record_id == "f1"
        assert eng.falsification_count == 1

    def test_duplicate_falsification_rejected(self):
        eng, _ = _make_engine()
        eng.record_falsification("f1", "t1", "h1", "e1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.record_falsification("f1", "t1", "h1", "e1")

    def test_falsification_with_status(self):
        eng, _ = _make_engine()
        f = eng.record_falsification("f1", "t1", "h1", "e1", status=FalsificationStatus.FALSIFIED)
        assert f.status == FalsificationStatus.FALSIFIED


# ===================================================================
# Replication
# ===================================================================

class TestReplication:
    def test_record_replication(self):
        eng, _ = _make_engine()
        r = eng.record_replication("rep1", "t1", "d1")
        assert r.replication_id == "rep1"
        assert eng.replication_count == 1

    def test_duplicate_replication_rejected(self):
        eng, _ = _make_engine()
        eng.record_replication("rep1", "t1", "d1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            eng.record_replication("rep1", "t1", "d1")

    def test_replication_with_status(self):
        eng, _ = _make_engine()
        r = eng.record_replication("rep1", "t1", "d1", status=ReplicationStatus.SUCCESSFUL)
        assert r.status == ReplicationStatus.SUCCESSFUL


# ===================================================================
# Assessment
# ===================================================================

class TestAssessment:
    def test_basic_assessment(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        a = eng.experiment_assessment("a1", "t1")
        assert a.assessment_id == "a1"
        assert a.total_designs == 1

    def test_assessment_success_rate(self):
        eng, _ = _make_engine()
        eng.record_replication("rep1", "t1", "d1", status=ReplicationStatus.SUCCESSFUL)
        eng.record_replication("rep2", "t1", "d1", status=ReplicationStatus.FAILED)
        a = eng.experiment_assessment("a1", "t1")
        assert a.success_rate == 0.5

    def test_assessment_zero_replications(self):
        eng, _ = _make_engine()
        a = eng.experiment_assessment("a1", "t1")
        assert a.success_rate == 0.0


# ===================================================================
# Snapshot
# ===================================================================

class TestSnapshot:
    def test_basic_snapshot(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        s = eng.experiment_snapshot("s1", "t1")
        assert s.snapshot_id == "s1"
        assert s.total_designs == 1

    def test_engine_snapshot_dict(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        snap = eng.snapshot()
        assert "designs" in snap
        assert "_state_hash" in snap


# ===================================================================
# Closure Report
# ===================================================================

class TestClosureReport:
    def test_basic_closure(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        c = eng.experiment_closure_report("cr1", "t1")
        assert c.report_id == "cr1"
        assert c.total_designs == 1


# ===================================================================
# Violation detection
# ===================================================================

class TestViolationDetection:
    def test_no_violations_empty(self):
        eng, _ = _make_engine()
        v = eng.detect_experiment_violations()
        assert len(v) == 0

    def test_no_control_group_violation(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        v = eng.detect_experiment_violations()
        assert any(x["operation"] == "no_control_group" for x in v)

    def test_no_variables_violation(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        v = eng.detect_experiment_violations()
        assert any(x["operation"] == "no_variables" for x in v)

    def test_result_without_analysis_violation(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        eng.record_result("r1", "t1", "d1")
        v = eng.detect_experiment_violations()
        assert any(x["operation"] == "result_without_analysis" for x in v)

    def test_idempotency(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        v1 = eng.detect_experiment_violations()
        assert len(v1) > 0
        v2 = eng.detect_experiment_violations()
        assert len(v2) == 0

    def test_violation_count_incremented(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        eng.detect_experiment_violations()
        assert eng.violation_count > 0

    def test_tenant_filter(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        v = eng.detect_experiment_violations(tenant_id="t2")
        assert len(v) == 0


# ===================================================================
# State hash
# ===================================================================

class TestStateHash:
    def test_deterministic(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        assert eng1.state_hash() == eng2.state_hash()

    def test_changes_after_mutation(self):
        eng, _ = _make_engine()
        h1 = eng.state_hash()
        eng.register_design("d1", "t1", "h1", "Design 1")
        h2 = eng.state_hash()
        assert h1 != h2

    def test_same_state_same_hash(self):
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        eng1.register_design("d1", "t1", "h1", "Design 1")
        eng2.register_design("d1", "t1", "h1", "Design 1")
        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# Golden scenarios
# ===================================================================

class TestGoldenScenarios:
    def test_happy_path_lifecycle(self):
        """Full experiment lifecycle: DESIGN -> RUNNING -> ANALYSIS -> COMPLETED."""
        eng, es = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.add_variable("v1", "t1", "d1", "Temp")
        eng.add_control_group("g1", "t1", "d1", "Control A", sample_size=30)
        eng.start_experiment("d1")
        eng.analyze_experiment("d1")
        eng.record_result("r1", "t1", "d1", significance=ResultSignificance.SIGNIFICANT)
        eng.complete_experiment("d1")
        d = eng.get_design("d1")
        assert d.phase == ExperimentPhase.COMPLETED
        assert es.event_count >= 6

    def test_cross_tenant_denied(self):
        """Violation detection filters by tenant."""
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        v = eng.detect_experiment_violations(tenant_id="t-other")
        assert len(v) == 0

    def test_terminal_state_blocking(self):
        """COMPLETED blocks further mutations."""
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        eng.analyze_experiment("d1")
        eng.complete_experiment("d1")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.add_variable("v1", "t1", "d1", "Temp")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.add_control_group("g1", "t1", "d1", "Control")
        with pytest.raises(RuntimeCoreInvariantError):
            eng.fail_experiment("d1")

    def test_violation_detection_idempotency(self):
        """First call detects, second returns empty."""
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.start_experiment("d1")
        v1 = eng.detect_experiment_violations()
        assert len(v1) > 0
        v2 = eng.detect_experiment_violations()
        assert len(v2) == 0

    def test_state_hash_determinism(self):
        """Two engines with identical operations produce identical state hashes."""
        eng1, _ = _make_engine()
        eng2, _ = _make_engine()
        for eng in (eng1, eng2):
            eng.register_design("d1", "t1", "h1", "Design 1")
            eng.add_variable("v1", "t1", "d1", "Temp")
            eng.start_experiment("d1")
        assert eng1.state_hash() == eng2.state_hash()

    def test_replay_consistency(self):
        """Replay with MonotonicClock produces consistent state."""
        clk = MonotonicClock()
        eng1, es1 = _make_engine(clock=clk)
        eng1.register_design("d1", "t1", "h1", "Design 1")
        eng1.add_variable("v1", "t1", "d1", "Temp")
        eng1.start_experiment("d1")
        snap1 = eng1.snapshot()
        # Replay with same clock
        clk2 = MonotonicClock()
        eng2, es2 = _make_engine(clock=clk2)
        eng2.register_design("d1", "t1", "h1", "Design 1")
        eng2.add_variable("v1", "t1", "d1", "Temp")
        eng2.start_experiment("d1")
        snap2 = eng2.snapshot()
        assert snap1["_state_hash"] == snap2["_state_hash"]


class TestBoundedContracts:
    def test_duplicate_design_message_bounded(self):
        eng, _ = _make_engine()
        eng.register_design("design-secret", "t1", "h1", "Design 1")

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            eng.register_design("design-secret", "t1", "h1", "Design 1")

        assert str(excinfo.value) == "Duplicate design_id"
        assert "design-secret" not in str(excinfo.value)

    def test_terminal_variable_guard_message_bounded(self):
        eng, _ = _make_engine()
        eng.register_design("d1", "t1", "h1", "Design 1")
        eng.fail_experiment("d1")

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            eng.add_variable("var-1", "t1", "d1", "Temperature")

        assert str(excinfo.value) == "Cannot add variable to terminal experiment"
        assert "FAILED" not in str(excinfo.value)

    def test_violation_reasons_bounded(self):
        eng, _ = _make_engine()
        eng.register_design("design-secret", "t1", "h1", "Design 1")
        eng.start_experiment("design-secret")
        eng.record_result("result-secret", "t1", "design-secret")

        violations = eng.detect_experiment_violations("t1")
        reasons = {v["reason"] for v in violations}

        assert "experiment has no control group" in reasons
        assert "experiment has no variables defined" in reasons
        assert "result recorded before analysis phase" in reasons
        assert all("design-secret" not in reason for reason in reasons)
        assert all("result-secret" not in reason for reason in reasons)
