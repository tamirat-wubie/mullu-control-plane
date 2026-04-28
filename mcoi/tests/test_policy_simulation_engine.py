"""Purpose: comprehensive pytest suite for PolicySimulationEngine.
Governance scope: policy simulation / governance sandbox runtime engine.
Dependencies: policy_simulation contracts, event_spine, core invariants.
Invariants tested:
  - Duplicate IDs raise.
  - Terminal state transitions raise.
  - Sandbox never mutates live runtimes.
  - Every mutation emits an event.
  - All returns are immutable.
  - Impact auto-upgrade when outcomes differ.
  - Readiness scoring: CRITICAL->BLOCKED/0.0, HIGH->NOT_READY/0.3,
    MEDIUM->CAUTION/0.6, else->READY/1.0.
  - Violation detection is idempotent.
  - state_hash is deterministic.
Target: ~350 tests.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.governance.policy.simulation import PolicySimulationEngine
from mcoi_runtime.contracts.policy_simulation import (
    AdoptionReadiness,
    AdoptionRecommendation,
    DiffDisposition,
    PolicyDiffRecord,
    PolicyImpactLevel,
    PolicySimulationRequest,
    PolicySimulationResult,
    PolicySimulationScenario,
    RuntimeImpactRecord,
    SandboxAssessment,
    SandboxClosureReport,
    SandboxScope,
    SandboxSnapshot,
    SandboxViolation,
    SimulationMode,
    SimulationStatus,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def engine(es):
    return PolicySimulationEngine(es)


@pytest.fixture
def sim(engine):
    """Register a single DRAFT simulation and return (engine, request_id)."""
    engine.register_simulation("req-1", "t1", "Sim One")
    return engine, "req-1"


@pytest.fixture
def running_sim(sim):
    """Return (engine, request_id) with a RUNNING simulation."""
    eng, rid = sim
    eng.start_simulation(rid)
    return eng, rid


@pytest.fixture
def completed_sim(sim):
    """Return (engine, request_id) with a COMPLETED simulation."""
    eng, rid = sim
    eng.start_simulation(rid)
    eng.complete_simulation(rid)
    return eng, rid


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

T = "t1"
T2 = "t2"


def _register(engine, rid="req-1", tid=T, name="Sim One", **kw):
    return engine.register_simulation(rid, tid, name, **kw)


def _add_scenario(engine, sid="sc-1", rid="req-1", tid=T, name="Scenario",
                  target="runtime-a", baseline="pass", simulated="pass",
                  impact=PolicyImpactLevel.NONE):
    return engine.add_scenario(sid, rid, tid, name, target, baseline,
                               simulated, impact)


def _record_diff(engine, did="diff-1", rid="req-1", tid=T, rule="rule-a",
                 disp=DiffDisposition.MODIFIED, before="old", after="new"):
    return engine.record_diff(did, rid, tid, rule, disp, before, after)


def _record_impact(engine, iid="imp-1", rid="req-1", tid=T, target="rt-a",
                   level=PolicyImpactLevel.MEDIUM, affected=5, blocked=1):
    return engine.record_impact(iid, rid, tid, target, level, affected, blocked)


# ===================================================================
# 1. CONSTRUCTION
# ===================================================================

class TestConstruction:
    def test_requires_event_spine_engine(self):
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationEngine("not-an-engine")

    def test_requires_event_spine_engine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationEngine(None)

    def test_requires_event_spine_engine_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            PolicySimulationEngine(42)

    def test_valid_construction(self, es):
        eng = PolicySimulationEngine(es)
        assert eng.request_count == 0

    def test_initial_counts_zero(self, engine):
        assert engine.request_count == 0
        assert engine.scenario_count == 0
        assert engine.result_count == 0
        assert engine.diff_count == 0
        assert engine.impact_count == 0
        assert engine.recommendation_count == 0
        assert engine.violation_count == 0
        assert engine.assessment_count == 0


# ===================================================================
# 2. REGISTER SIMULATION
# ===================================================================

class TestRegisterSimulation:
    def test_basic_register(self, engine):
        req = _register(engine)
        assert isinstance(req, PolicySimulationRequest)
        assert req.request_id == "req-1"
        assert req.tenant_id == T
        assert req.display_name == "Sim One"
        assert req.status == SimulationStatus.DRAFT
        assert req.mode == SimulationMode.DRY_RUN
        assert req.scope == SandboxScope.TENANT

    def test_register_increments_count(self, engine):
        _register(engine, "r1")
        assert engine.request_count == 1
        _register(engine, "r2")
        assert engine.request_count == 2

    def test_duplicate_raises(self, engine):
        _register(engine)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate request_id"):
            _register(engine)

    def test_mode_shadow(self, engine):
        req = _register(engine, mode=SimulationMode.SHADOW)
        assert req.mode == SimulationMode.SHADOW

    def test_mode_full(self, engine):
        req = _register(engine, mode=SimulationMode.FULL)
        assert req.mode == SimulationMode.FULL

    def test_mode_diff_only(self, engine):
        req = _register(engine, mode=SimulationMode.DIFF_ONLY)
        assert req.mode == SimulationMode.DIFF_ONLY

    def test_scope_runtime(self, engine):
        req = _register(engine, scope=SandboxScope.RUNTIME)
        assert req.scope == SandboxScope.RUNTIME

    def test_scope_global(self, engine):
        req = _register(engine, scope=SandboxScope.GLOBAL)
        assert req.scope == SandboxScope.GLOBAL

    def test_scope_constitutional(self, engine):
        req = _register(engine, scope=SandboxScope.CONSTITUTIONAL)
        assert req.scope == SandboxScope.CONSTITUTIONAL

    def test_scope_service(self, engine):
        req = _register(engine, scope=SandboxScope.SERVICE)
        assert req.scope == SandboxScope.SERVICE

    def test_scope_financial(self, engine):
        req = _register(engine, scope=SandboxScope.FINANCIAL)
        assert req.scope == SandboxScope.FINANCIAL

    def test_candidate_rule_count(self, engine):
        req = _register(engine, candidate_rule_count=5)
        assert req.candidate_rule_count == 5

    def test_candidate_rule_count_zero(self, engine):
        req = _register(engine)
        assert req.candidate_rule_count == 0

    def test_created_at_populated(self, engine):
        req = _register(engine)
        assert req.created_at != ""

    def test_emits_event(self, engine, es):
        _register(engine)
        events = es.list_events()
        assert len(events) >= 1
        assert any("register_simulation" in str(e.payload) for e in events)

    def test_get_simulation_returns_registered(self, engine):
        _register(engine)
        req = engine.get_simulation("req-1")
        assert req.request_id == "req-1"

    def test_get_simulation_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            engine.get_simulation("does-not-exist")

    def test_register_multiple_tenants(self, engine):
        _register(engine, "r1", "tA", "A")
        _register(engine, "r2", "tB", "B")
        assert engine.request_count == 2


# ===================================================================
# 3. SIMULATION STATE TRANSITIONS
# ===================================================================

class TestStartSimulation:
    def test_draft_to_running(self, sim):
        eng, rid = sim
        req = eng.start_simulation(rid)
        assert req.status == SimulationStatus.RUNNING

    def test_emits_event(self, sim, es):
        eng, rid = sim
        before = es.event_count
        eng.start_simulation(rid)
        assert es.event_count > before

    def test_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.start_simulation("no-such")

    def test_double_start_is_idempotent_from_running(self, running_sim):
        eng, rid = running_sim
        # Starting a RUNNING sim is allowed (not terminal)
        req = eng.start_simulation(rid)
        assert req.status == SimulationStatus.RUNNING


class TestCompleteSimulation:
    def test_running_to_completed(self, running_sim):
        eng, rid = running_sim
        req = eng.complete_simulation(rid)
        assert req.status == SimulationStatus.COMPLETED

    def test_draft_to_completed(self, sim):
        eng, rid = sim
        req = eng.complete_simulation(rid)
        assert req.status == SimulationStatus.COMPLETED

    def test_completed_is_terminal(self, completed_sim):
        eng, rid = completed_sim
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.complete_simulation(rid)

    def test_completed_cannot_start(self, completed_sim):
        eng, rid = completed_sim
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.start_simulation(rid)

    def test_completed_cannot_fail(self, completed_sim):
        eng, rid = completed_sim
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.fail_simulation(rid)

    def test_completed_cannot_cancel(self, completed_sim):
        eng, rid = completed_sim
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            eng.cancel_simulation(rid)

    def test_emits_event(self, running_sim, es):
        eng, rid = running_sim
        before = es.event_count
        eng.complete_simulation(rid)
        assert es.event_count > before


class TestFailSimulation:
    def test_running_to_failed(self, running_sim):
        eng, rid = running_sim
        req = eng.fail_simulation(rid)
        assert req.status == SimulationStatus.FAILED

    def test_draft_to_failed(self, sim):
        eng, rid = sim
        req = eng.fail_simulation(rid)
        assert req.status == SimulationStatus.FAILED

    def test_failed_is_terminal(self, engine):
        _register(engine)
        engine.fail_simulation("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_simulation("req-1")

    def test_failed_cannot_complete(self, engine):
        _register(engine)
        engine.fail_simulation("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_simulation("req-1")

    def test_failed_cannot_start(self, engine):
        _register(engine)
        engine.fail_simulation("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.start_simulation("req-1")

    def test_failed_cannot_cancel(self, engine):
        _register(engine)
        engine.fail_simulation("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.cancel_simulation("req-1")

    def test_emits_event(self, sim, es):
        eng, rid = sim
        before = es.event_count
        eng.fail_simulation(rid)
        assert es.event_count > before


class TestCancelSimulation:
    def test_running_to_cancelled(self, running_sim):
        eng, rid = running_sim
        req = eng.cancel_simulation(rid)
        assert req.status == SimulationStatus.CANCELLED

    def test_draft_to_cancelled(self, sim):
        eng, rid = sim
        req = eng.cancel_simulation(rid)
        assert req.status == SimulationStatus.CANCELLED

    def test_cancelled_is_terminal(self, engine):
        _register(engine)
        engine.cancel_simulation("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.cancel_simulation("req-1")

    def test_cancelled_cannot_start(self, engine):
        _register(engine)
        engine.cancel_simulation("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.start_simulation("req-1")

    def test_cancelled_cannot_complete(self, engine):
        _register(engine)
        engine.cancel_simulation("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.complete_simulation("req-1")

    def test_cancelled_cannot_fail(self, engine):
        _register(engine)
        engine.cancel_simulation("req-1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.fail_simulation("req-1")

    def test_emits_event(self, sim, es):
        eng, rid = sim
        before = es.event_count
        eng.cancel_simulation(rid)
        assert es.event_count > before


# ===================================================================
# 4. SIMULATIONS FOR TENANT
# ===================================================================

class TestSimulationsForTenant:
    def test_empty(self, engine):
        assert engine.simulations_for_tenant("t1") == ()

    def test_single(self, sim):
        eng, _ = sim
        sims = eng.simulations_for_tenant(T)
        assert len(sims) == 1

    def test_filters_by_tenant(self, engine):
        _register(engine, "r1", "tA", "A")
        _register(engine, "r2", "tB", "B")
        _register(engine, "r3", "tA", "C")
        assert len(engine.simulations_for_tenant("tA")) == 2
        assert len(engine.simulations_for_tenant("tB")) == 1
        assert len(engine.simulations_for_tenant("tC")) == 0

    def test_returns_tuple(self, sim):
        eng, _ = sim
        result = eng.simulations_for_tenant(T)
        assert isinstance(result, tuple)

    def test_multiple_simulations(self, engine):
        for i in range(10):
            _register(engine, f"r{i}", T, f"Sim {i}")
        assert len(engine.simulations_for_tenant(T)) == 10


# ===================================================================
# 5. ADD SCENARIO
# ===================================================================

class TestAddScenario:
    def test_basic_add(self, sim):
        eng, rid = sim
        sc = _add_scenario(eng)
        assert isinstance(sc, PolicySimulationScenario)
        assert sc.scenario_id == "sc-1"
        assert sc.request_id == rid
        assert sc.tenant_id == T

    def test_increments_count(self, sim):
        eng, _ = sim
        _add_scenario(eng, "s1")
        assert eng.scenario_count == 1
        _add_scenario(eng, "s2")
        assert eng.scenario_count == 2

    def test_duplicate_raises(self, sim):
        eng, _ = sim
        _add_scenario(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate scenario_id"):
            _add_scenario(eng)

    def test_unknown_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            _add_scenario(engine, rid="nonexistent")

    def test_same_outcomes_no_upgrade(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="pass", simulated="pass")
        assert sc.impact_level == PolicyImpactLevel.NONE

    def test_diff_outcomes_auto_upgrade_none_to_medium(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="pass", simulated="fail")
        assert sc.impact_level == PolicyImpactLevel.MEDIUM

    def test_diff_outcomes_explicit_high_kept(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="pass", simulated="fail",
                           impact=PolicyImpactLevel.HIGH)
        assert sc.impact_level == PolicyImpactLevel.HIGH

    def test_diff_outcomes_explicit_critical_kept(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="pass", simulated="fail",
                           impact=PolicyImpactLevel.CRITICAL)
        assert sc.impact_level == PolicyImpactLevel.CRITICAL

    def test_diff_outcomes_explicit_low_kept(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="pass", simulated="fail",
                           impact=PolicyImpactLevel.LOW)
        assert sc.impact_level == PolicyImpactLevel.LOW

    def test_diff_outcomes_explicit_medium_kept(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="pass", simulated="fail",
                           impact=PolicyImpactLevel.MEDIUM)
        assert sc.impact_level == PolicyImpactLevel.MEDIUM

    def test_same_outcomes_explicit_high_kept(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="same", simulated="same",
                           impact=PolicyImpactLevel.HIGH)
        assert sc.impact_level == PolicyImpactLevel.HIGH

    def test_emits_event(self, sim, es):
        eng, _ = sim
        before = es.event_count
        _add_scenario(eng)
        assert es.event_count > before

    def test_get_scenario(self, sim):
        eng, _ = sim
        _add_scenario(eng, "s1")
        sc = eng.get_scenario("s1")
        assert sc.scenario_id == "s1"

    def test_get_scenario_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown scenario_id"):
            engine.get_scenario("nope")

    def test_scenarios_for_simulation(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1")
        _add_scenario(eng, "s2")
        scenes = eng.scenarios_for_simulation(rid)
        assert len(scenes) == 2

    def test_scenarios_for_simulation_empty(self, sim):
        eng, rid = sim
        assert eng.scenarios_for_simulation(rid) == ()

    def test_scenarios_for_simulation_different_request(self, engine):
        _register(engine, "r1")
        _register(engine, "r2")
        _add_scenario(engine, "s1", "r1")
        _add_scenario(engine, "s2", "r2")
        assert len(engine.scenarios_for_simulation("r1")) == 1
        assert len(engine.scenarios_for_simulation("r2")) == 1

    def test_target_runtime_stored(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, target="my-runtime")
        assert sc.target_runtime == "my-runtime"

    def test_created_at_populated(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng)
        assert sc.created_at != ""


# ===================================================================
# 6. RECORD DIFF
# ===================================================================

class TestRecordDiff:
    def test_basic_record(self, sim):
        eng, _ = sim
        d = _record_diff(eng)
        assert isinstance(d, PolicyDiffRecord)
        assert d.diff_id == "diff-1"
        assert d.rule_ref == "rule-a"
        assert d.disposition == DiffDisposition.MODIFIED

    def test_increments_count(self, sim):
        eng, _ = sim
        _record_diff(eng, "d1")
        assert eng.diff_count == 1

    def test_duplicate_raises(self, sim):
        eng, _ = sim
        _record_diff(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate diff_id"):
            _record_diff(eng)

    def test_unknown_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            _record_diff(engine, rid="nope")

    def test_disposition_added(self, sim):
        eng, _ = sim
        d = _record_diff(eng, disp=DiffDisposition.ADDED)
        assert d.disposition == DiffDisposition.ADDED

    def test_disposition_removed(self, sim):
        eng, _ = sim
        d = _record_diff(eng, disp=DiffDisposition.REMOVED)
        assert d.disposition == DiffDisposition.REMOVED

    def test_disposition_unchanged(self, sim):
        eng, _ = sim
        d = _record_diff(eng, disp=DiffDisposition.UNCHANGED)
        assert d.disposition == DiffDisposition.UNCHANGED

    def test_before_after_values(self, sim):
        eng, _ = sim
        d = _record_diff(eng, before="10", after="20")
        assert d.before_value == "10"
        assert d.after_value == "20"

    def test_emits_event(self, sim, es):
        eng, _ = sim
        before = es.event_count
        _record_diff(eng)
        assert es.event_count > before

    def test_diffs_for_simulation(self, sim):
        eng, rid = sim
        _record_diff(eng, "d1")
        _record_diff(eng, "d2")
        diffs = eng.diffs_for_simulation(rid)
        assert len(diffs) == 2

    def test_diffs_for_simulation_empty(self, sim):
        eng, rid = sim
        assert eng.diffs_for_simulation(rid) == ()

    def test_diffs_for_simulation_filters(self, engine):
        _register(engine, "r1")
        _register(engine, "r2")
        _record_diff(engine, "d1", "r1")
        _record_diff(engine, "d2", "r2")
        assert len(engine.diffs_for_simulation("r1")) == 1

    def test_created_at_populated(self, sim):
        eng, _ = sim
        d = _record_diff(eng)
        assert d.created_at != ""


# ===================================================================
# 7. RECORD IMPACT
# ===================================================================

class TestRecordImpact:
    def test_basic_record(self, sim):
        eng, _ = sim
        imp = _record_impact(eng)
        assert isinstance(imp, RuntimeImpactRecord)
        assert imp.impact_id == "imp-1"
        assert imp.impact_level == PolicyImpactLevel.MEDIUM

    def test_increments_count(self, sim):
        eng, _ = sim
        _record_impact(eng)
        assert eng.impact_count == 1

    def test_duplicate_raises(self, sim):
        eng, _ = sim
        _record_impact(eng)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate impact_id"):
            _record_impact(eng)

    def test_unknown_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown request_id"):
            _record_impact(engine, rid="nope")

    def test_all_impact_levels(self, sim):
        eng, _ = sim
        for i, lvl in enumerate(PolicyImpactLevel):
            imp = _record_impact(eng, f"imp-{i}", level=lvl)
            assert imp.impact_level == lvl

    def test_affected_blocked_actions(self, sim):
        eng, _ = sim
        imp = _record_impact(eng, affected=10, blocked=3)
        assert imp.affected_actions == 10
        assert imp.blocked_actions == 3

    def test_emits_event(self, sim, es):
        eng, _ = sim
        before = es.event_count
        _record_impact(eng)
        assert es.event_count > before

    def test_impacts_for_simulation(self, sim):
        eng, rid = sim
        _record_impact(eng, "i1")
        _record_impact(eng, "i2")
        imps = eng.impacts_for_simulation(rid)
        assert len(imps) == 2

    def test_impacts_for_simulation_empty(self, sim):
        eng, rid = sim
        assert eng.impacts_for_simulation(rid) == ()

    def test_impacts_for_simulation_filters(self, engine):
        _register(engine, "r1")
        _register(engine, "r2")
        _record_impact(engine, "i1", "r1")
        _record_impact(engine, "i2", "r2")
        assert len(engine.impacts_for_simulation("r1")) == 1

    def test_target_runtime_stored(self, sim):
        eng, _ = sim
        imp = _record_impact(eng, target="rt-z")
        assert imp.target_runtime == "rt-z"

    def test_created_at_populated(self, sim):
        eng, _ = sim
        imp = _record_impact(eng)
        assert imp.created_at != ""


# ===================================================================
# 8. PRODUCE RESULT
# ===================================================================

class TestProduceResult:
    def test_no_scenarios_no_impacts_yields_ready(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert isinstance(res, PolicySimulationResult)
        assert res.max_impact_level == PolicyImpactLevel.NONE
        assert res.adoption_readiness == AdoptionReadiness.READY
        assert res.readiness_score == 1.0

    def test_medium_scenario_yields_caution(self, sim):
        eng, rid = sim
        _add_scenario(eng, baseline="pass", simulated="fail")  # auto MEDIUM
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.MEDIUM
        assert res.adoption_readiness == AdoptionReadiness.CAUTION
        assert res.readiness_score == 0.6

    def test_high_scenario_yields_not_ready(self, sim):
        eng, rid = sim
        _add_scenario(eng, baseline="pass", simulated="fail",
                       impact=PolicyImpactLevel.HIGH)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.HIGH
        assert res.adoption_readiness == AdoptionReadiness.NOT_READY
        assert res.readiness_score == 0.3

    def test_critical_scenario_yields_blocked(self, sim):
        eng, rid = sim
        _add_scenario(eng, baseline="pass", simulated="fail",
                       impact=PolicyImpactLevel.CRITICAL)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.CRITICAL
        assert res.adoption_readiness == AdoptionReadiness.BLOCKED
        assert res.readiness_score == 0.0

    def test_low_scenario_yields_ready(self, sim):
        eng, rid = sim
        _add_scenario(eng, baseline="pass", simulated="fail",
                       impact=PolicyImpactLevel.LOW)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.LOW
        assert res.adoption_readiness == AdoptionReadiness.READY
        assert res.readiness_score == 1.0

    def test_none_scenario_yields_ready(self, sim):
        eng, rid = sim
        _add_scenario(eng, baseline="same", simulated="same",
                       impact=PolicyImpactLevel.NONE)
        res = eng.produce_result(rid)
        assert res.adoption_readiness == AdoptionReadiness.READY

    def test_max_impact_from_scenarios(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1", baseline="a", simulated="b",
                       impact=PolicyImpactLevel.LOW)
        _add_scenario(eng, "s2", baseline="a", simulated="b",
                       impact=PolicyImpactLevel.HIGH)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.HIGH

    def test_max_impact_from_impacts(self, sim):
        eng, rid = sim
        _record_impact(eng, "i1", level=PolicyImpactLevel.CRITICAL)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.CRITICAL
        assert res.adoption_readiness == AdoptionReadiness.BLOCKED

    def test_max_impact_mixed_scenario_and_impact(self, sim):
        eng, rid = sim
        _add_scenario(eng, baseline="a", simulated="b",
                       impact=PolicyImpactLevel.LOW)
        _record_impact(eng, level=PolicyImpactLevel.HIGH)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.HIGH

    def test_scenario_count_and_impacted_count(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1", baseline="a", simulated="a")  # NONE
        _add_scenario(eng, "s2", baseline="a", simulated="b")  # MEDIUM auto
        _add_scenario(eng, "s3", baseline="a", simulated="b",
                       impact=PolicyImpactLevel.HIGH)
        res = eng.produce_result(rid)
        assert res.scenario_count == 3
        assert res.impacted_count == 2  # s2(MEDIUM) + s3(HIGH)

    def test_increments_result_count(self, sim):
        eng, rid = sim
        assert eng.result_count == 0
        eng.produce_result(rid)
        assert eng.result_count == 1

    def test_multiple_results_for_same_simulation(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        eng.produce_result(rid)
        assert eng.result_count == 2

    def test_results_for_simulation(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        results = eng.results_for_simulation(rid)
        assert len(results) == 1

    def test_results_for_simulation_empty(self, sim):
        eng, rid = sim
        assert eng.results_for_simulation(rid) == ()

    def test_unknown_request_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown"):
            engine.produce_result("nope")

    def test_emits_event(self, sim, es):
        eng, rid = sim
        before = es.event_count
        eng.produce_result(rid)
        assert es.event_count > before

    def test_result_tenant_id_matches(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert res.tenant_id == T

    def test_completed_at_populated(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert res.completed_at != ""

    def test_result_id_populated(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert res.result_id != ""


# ===================================================================
# 9. RECOMMEND ADOPTION
# ===================================================================

class TestRecommendAdoption:
    def test_basic_recommend(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        assert isinstance(rec, AdoptionRecommendation)
        assert rec.recommendation_id == "rec-1"
        assert rec.request_id == rid

    def test_uses_latest_result(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1", baseline="a", simulated="b",
                       impact=PolicyImpactLevel.CRITICAL)
        eng.produce_result(rid)
        # Add more data and produce second result
        _add_scenario(eng, "s2", baseline="a", simulated="a")
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        # Latest result still sees CRITICAL from s1
        assert rec.readiness == AdoptionReadiness.BLOCKED

    def test_duplicate_raises(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        eng.recommend_adoption("rec-1", rid, T)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate recommendation_id"):
            eng.recommend_adoption("rec-1", rid, T)

    def test_no_results_raises(self, sim):
        eng, rid = sim
        with pytest.raises(RuntimeCoreInvariantError, match="no results"):
            eng.recommend_adoption("rec-1", rid, T)

    def test_increments_count(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        assert eng.recommendation_count == 0
        eng.recommend_adoption("rec-1", rid, T)
        assert eng.recommendation_count == 1

    def test_readiness_score_propagated(self, sim):
        eng, rid = sim
        _add_scenario(eng, baseline="a", simulated="b",
                       impact=PolicyImpactLevel.HIGH)
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        assert rec.readiness_score == 0.3

    def test_reason_populated(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        assert "max impact" in rec.reason
        assert "readiness" in rec.reason

    def test_recommended_at_populated(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        assert rec.recommended_at != ""

    def test_emits_event(self, sim, es):
        eng, rid = sim
        eng.produce_result(rid)
        before = es.event_count
        eng.recommend_adoption("rec-1", rid, T)
        assert es.event_count > before

    def test_ready_recommendation(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        assert rec.readiness == AdoptionReadiness.READY
        assert rec.readiness_score == 1.0

    def test_caution_recommendation(self, sim):
        eng, rid = sim
        _add_scenario(eng, baseline="a", simulated="b")  # MEDIUM
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        assert rec.readiness == AdoptionReadiness.CAUTION
        assert rec.readiness_score == 0.6


# ===================================================================
# 10. SANDBOX SNAPSHOT
# ===================================================================

class TestSandboxSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.sandbox_snapshot("snap-1", T)
        assert isinstance(snap, SandboxSnapshot)
        assert snap.total_simulations == 0
        assert snap.completed_simulations == 0
        assert snap.total_scenarios == 0
        assert snap.total_diffs == 0
        assert snap.total_impacts == 0
        assert snap.total_violations == 0

    def test_snapshot_with_data(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        _add_scenario(engine, "s1", "r1", T, "sc", "rt", "a", "b")
        _record_diff(engine, "d1", "r1", T)
        _record_impact(engine, "i1", "r1", T)
        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_simulations == 1
        assert snap.completed_simulations == 1
        assert snap.total_scenarios == 1
        assert snap.total_diffs == 1
        assert snap.total_impacts == 1

    def test_snapshot_filters_by_tenant(self, engine):
        _register(engine, "r1", "tA", "A")
        _register(engine, "r2", "tB", "B")
        _add_scenario(engine, "s1", "r1", "tA", "sc", "rt", "a", "b")
        _add_scenario(engine, "s2", "r2", "tB", "sc", "rt", "a", "b")
        snap_a = engine.sandbox_snapshot("snap-a", "tA")
        snap_b = engine.sandbox_snapshot("snap-b", "tB")
        assert snap_a.total_simulations == 1
        assert snap_a.total_scenarios == 1
        assert snap_b.total_simulations == 1
        assert snap_b.total_scenarios == 1

    def test_snapshot_captured_at(self, engine):
        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.captured_at != ""

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.sandbox_snapshot("snap-1", T)
        assert es.event_count > before

    def test_snapshot_not_stored_in_assessments(self, engine):
        engine.sandbox_snapshot("snap-1", T)
        # Snapshots don't go into _assessments
        assert engine.assessment_count == 0

    def test_snapshot_counts_only_completed(self, engine):
        _register(engine, "r1", T, "A")
        _register(engine, "r2", T, "B")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        engine.start_simulation("r2")
        # r2 still RUNNING
        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_simulations == 2
        assert snap.completed_simulations == 1


# ===================================================================
# 11. SANDBOX ASSESSMENT
# ===================================================================

class TestSandboxAssessment:
    def test_empty_assessment(self, engine):
        a = engine.sandbox_assessment("a-1", T)
        assert isinstance(a, SandboxAssessment)
        assert a.total_simulations == 0
        assert a.completion_rate == 1.0  # 0/0 defaults to 1.0
        assert a.avg_readiness_score == 1.0  # no results defaults to 1.0
        assert a.total_violations == 0

    def test_duplicate_raises(self, engine):
        engine.sandbox_assessment("a-1", T)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate assessment_id"):
            engine.sandbox_assessment("a-1", T)

    def test_completion_rate_all_completed(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        a = engine.sandbox_assessment("a-1", T)
        assert a.completion_rate == 1.0

    def test_completion_rate_partial(self, engine):
        _register(engine, "r1", T, "A")
        _register(engine, "r2", T, "B")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        # r2 still DRAFT
        a = engine.sandbox_assessment("a-1", T)
        assert a.completion_rate == 0.5

    def test_completion_rate_none_completed(self, engine):
        _register(engine, "r1", T, "A")
        a = engine.sandbox_assessment("a-1", T)
        assert a.completion_rate == 0.0

    def test_avg_readiness_score_single(self, engine):
        _register(engine, "r1", T, "A")
        _add_scenario(engine, "s1", "r1", T, "sc", "rt", "a", "b",
                       PolicyImpactLevel.HIGH)
        engine.produce_result("r1")
        a = engine.sandbox_assessment("a-1", T)
        assert a.avg_readiness_score == 0.3

    def test_avg_readiness_score_multiple(self, engine):
        _register(engine, "r1", T, "A")
        _register(engine, "r2", T, "B")
        # r1: no scenarios -> READY (1.0)
        engine.produce_result("r1")
        # r2: CRITICAL scenario -> BLOCKED (0.0)
        _add_scenario(engine, "s1", "r2", T, "sc", "rt", "a", "b",
                       PolicyImpactLevel.CRITICAL)
        engine.produce_result("r2")
        a = engine.sandbox_assessment("a-1", T)
        assert a.avg_readiness_score == 0.5  # (1.0 + 0.0) / 2

    def test_violations_counted(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        # r1 stuck RUNNING -> violation
        engine.detect_sandbox_violations(T)
        a = engine.sandbox_assessment("a-1", T)
        assert a.total_violations == 1

    def test_increments_count(self, engine):
        engine.sandbox_assessment("a-1", T)
        assert engine.assessment_count == 1

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.sandbox_assessment("a-1", T)
        assert es.event_count > before

    def test_assessed_at_populated(self, engine):
        a = engine.sandbox_assessment("a-1", T)
        assert a.assessed_at != ""

    def test_filters_by_tenant(self, engine):
        _register(engine, "r1", "tA", "A")
        _register(engine, "r2", "tB", "B")
        engine.produce_result("r1")
        engine.produce_result("r2")
        a = engine.sandbox_assessment("a-1", "tA")
        assert a.total_simulations == 1


# ===================================================================
# 12. DETECT SANDBOX VIOLATIONS
# ===================================================================

class TestDetectSandboxViolations:
    def test_no_violations(self, engine):
        vs = engine.detect_sandbox_violations(T)
        assert vs == ()

    def test_stuck_running(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        vs = engine.detect_sandbox_violations(T)
        assert len(vs) == 1
        assert vs[0].operation == "stuck_running"

    def test_completed_no_result(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        vs = engine.detect_sandbox_violations(T)
        assert len(vs) == 1
        assert vs[0].operation == "completed_no_result"

    def test_blocked_no_recommendation(self, engine):
        _register(engine, "r1", T, "A")
        _add_scenario(engine, "s1", "r1", T, "sc", "rt", "a", "b",
                       PolicyImpactLevel.CRITICAL)
        engine.produce_result("r1")
        vs = engine.detect_sandbox_violations(T)
        assert len(vs) == 1
        assert vs[0].operation == "blocked_no_recommendation"

    def test_idempotent(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        vs1 = engine.detect_sandbox_violations(T)
        vs2 = engine.detect_sandbox_violations(T)
        assert len(vs1) == 1
        assert len(vs2) == 0  # second call returns no NEW violations

    def test_idempotent_total_unchanged(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.detect_sandbox_violations(T)
        engine.detect_sandbox_violations(T)
        assert engine.violation_count == 1

    def test_multiple_violations(self, engine):
        _register(engine, "r1", T, "A")
        _register(engine, "r2", T, "B")
        engine.start_simulation("r1")  # stuck RUNNING
        engine.start_simulation("r2")
        engine.complete_simulation("r2")  # completed, no result
        vs = engine.detect_sandbox_violations(T)
        assert len(vs) == 2
        ops = {v.operation for v in vs}
        assert "stuck_running" in ops
        assert "completed_no_result" in ops

    def test_filters_by_tenant(self, engine):
        _register(engine, "r1", "tA", "A")
        _register(engine, "r2", "tB", "B")
        engine.start_simulation("r1")
        engine.start_simulation("r2")
        vs_a = engine.detect_sandbox_violations("tA")
        vs_b = engine.detect_sandbox_violations("tB")
        assert len(vs_a) == 1
        assert len(vs_b) == 1

    def test_completed_with_result_no_violation(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        engine.produce_result("r1")
        vs = engine.detect_sandbox_violations(T)
        # No completed_no_result because result exists
        assert not any(v.operation == "completed_no_result" for v in vs)

    def test_blocked_with_recommendation_no_violation(self, engine):
        _register(engine, "r1", T, "A")
        _add_scenario(engine, "s1", "r1", T, "sc", "rt", "a", "b",
                       PolicyImpactLevel.CRITICAL)
        engine.produce_result("r1")
        engine.recommend_adoption("rec-1", "r1", T)
        vs = engine.detect_sandbox_violations(T)
        assert not any(v.operation == "blocked_no_recommendation" for v in vs)

    def test_emits_event_when_violations_found(self, engine, es):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        before = es.event_count
        engine.detect_sandbox_violations(T)
        assert es.event_count > before

    def test_no_event_when_no_violations(self, engine, es):
        before = es.event_count
        engine.detect_sandbox_violations(T)
        assert es.event_count == before

    def test_violation_reason_contains_request_id(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        vs = engine.detect_sandbox_violations(T)
        assert vs[0].reason == "simulation stuck in RUNNING state"
        assert "r1" not in vs[0].reason
        assert T not in vs[0].reason

    def test_violations_for_tenant(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.detect_sandbox_violations(T)
        vt = engine.violations_for_tenant(T)
        assert len(vt) == 1

    def test_violations_for_tenant_empty(self, engine):
        assert engine.violations_for_tenant(T) == ()


# ===================================================================
# 13. CLOSURE REPORT
# ===================================================================

class TestClosureReport:
    def test_empty_report(self, engine):
        rpt = engine.closure_report("rpt-1", T)
        assert isinstance(rpt, SandboxClosureReport)
        assert rpt.total_simulations == 0
        assert rpt.total_scenarios == 0
        assert rpt.total_diffs == 0
        assert rpt.total_impacts == 0
        assert rpt.total_recommendations == 0
        assert rpt.total_violations == 0

    def test_full_report(self, engine):
        _register(engine, "r1", T, "A")
        _add_scenario(engine, "s1", "r1", T, "sc", "rt", "a", "b")
        _record_diff(engine, "d1", "r1", T)
        _record_impact(engine, "i1", "r1", T)
        engine.produce_result("r1")
        engine.recommend_adoption("rec-1", "r1", T)
        engine.start_simulation("r1")
        engine.detect_sandbox_violations(T)  # stuck_running

        rpt = engine.closure_report("rpt-1", T)
        assert rpt.total_simulations == 1
        assert rpt.total_scenarios == 1
        assert rpt.total_diffs == 1
        assert rpt.total_impacts == 1
        assert rpt.total_recommendations == 1
        assert rpt.total_violations == 1

    def test_filters_by_tenant(self, engine):
        _register(engine, "r1", "tA", "A")
        _register(engine, "r2", "tB", "B")
        _add_scenario(engine, "s1", "r1", "tA", "sc", "rt", "a", "b")
        rpt_a = engine.closure_report("rpt-a", "tA")
        rpt_b = engine.closure_report("rpt-b", "tB")
        assert rpt_a.total_simulations == 1
        assert rpt_a.total_scenarios == 1
        assert rpt_b.total_simulations == 1
        assert rpt_b.total_scenarios == 0

    def test_emits_event(self, engine, es):
        before = es.event_count
        engine.closure_report("rpt-1", T)
        assert es.event_count > before

    def test_created_at_populated(self, engine):
        rpt = engine.closure_report("rpt-1", T)
        assert rpt.created_at != ""


# ===================================================================
# 14. STATE HASH
# ===================================================================

class TestStateHash:
    def test_empty_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_hash_changes_on_register(self, engine):
        h1 = engine.state_hash()
        _register(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_on_scenario(self, engine):
        _register(engine)
        h1 = engine.state_hash()
        _add_scenario(engine, baseline="a", simulated="b")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_on_result(self, engine):
        _register(engine)
        h1 = engine.state_hash()
        engine.produce_result("req-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_on_diff(self, engine):
        _register(engine)
        h1 = engine.state_hash()
        _record_diff(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_on_impact(self, engine):
        _register(engine)
        h1 = engine.state_hash()
        _record_impact(engine)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_on_violation(self, engine):
        _register(engine)
        engine.start_simulation("req-1")
        h1 = engine.state_hash()
        engine.detect_sandbox_violations(T)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_changes_on_status_transition(self, engine):
        _register(engine)
        h_draft = engine.state_hash()
        engine.start_simulation("req-1")
        h_running = engine.state_hash()
        engine.complete_simulation("req-1")
        h_completed = engine.state_hash()
        assert h_draft != h_running
        assert h_running != h_completed

    def test_hash_is_string(self, engine):
        assert isinstance(engine.state_hash(), str)

    def test_hash_hex(self, engine):
        h = engine.state_hash()
        int(h, 16)  # should not raise


# ===================================================================
# 15. GOLDEN SCENARIO 1: Stricter rule blocks release
# ===================================================================

class TestGoldenStricterRuleBlocksRelease:
    """A new stricter policy rule causes CRITICAL impact, blocking rollout."""

    def test_end_to_end(self, engine):
        # Register simulation
        req = _register(engine, "sim-strict", T, "Stricter release gate")
        assert req.status == SimulationStatus.DRAFT

        # Start
        engine.start_simulation("sim-strict")

        # Scenario: release was passing, now blocked
        sc = engine.add_scenario(
            "sc-strict-1", "sim-strict", T, "Release gate scenario",
            "release-pipeline", "release_approved", "release_blocked",
            PolicyImpactLevel.CRITICAL,
        )
        assert sc.impact_level == PolicyImpactLevel.CRITICAL
        assert sc.baseline_outcome == "release_approved"
        assert sc.simulated_outcome == "release_blocked"

        # Record diff
        diff = engine.record_diff(
            "diff-strict-1", "sim-strict", T, "rule-release-gate",
            DiffDisposition.MODIFIED, "threshold=0.5", "threshold=0.95",
        )
        assert diff.disposition == DiffDisposition.MODIFIED

        # Record impact
        imp = engine.record_impact(
            "imp-strict-1", "sim-strict", T, "release-pipeline",
            PolicyImpactLevel.CRITICAL, affected_actions=50, blocked_actions=48,
        )
        assert imp.blocked_actions == 48

        # Produce result
        res = engine.produce_result("sim-strict")
        assert res.max_impact_level == PolicyImpactLevel.CRITICAL
        assert res.adoption_readiness == AdoptionReadiness.BLOCKED
        assert res.readiness_score == 0.0

        # Recommend adoption
        rec = engine.recommend_adoption("rec-strict-1", "sim-strict", T)
        assert rec.readiness == AdoptionReadiness.BLOCKED
        assert rec.readiness_score == 0.0

    def test_snapshot_reflects_data(self, engine):
        _register(engine, "sim-strict", T, "Stricter release gate")
        engine.add_scenario(
            "sc-1", "sim-strict", T, "sc", "rt", "pass", "block",
            PolicyImpactLevel.CRITICAL,
        )
        snap = engine.sandbox_snapshot("snap-strict", T)
        assert snap.total_simulations == 1
        assert snap.total_scenarios == 1

    def test_closure_report_counts(self, engine):
        _register(engine, "sim-strict", T, "Stricter release gate")
        engine.add_scenario(
            "sc-1", "sim-strict", T, "sc", "rt", "pass", "block",
            PolicyImpactLevel.CRITICAL,
        )
        engine.record_diff(
            "d-1", "sim-strict", T, "rule-x",
            DiffDisposition.MODIFIED, "old", "new",
        )
        engine.record_impact(
            "i-1", "sim-strict", T, "rt",
            PolicyImpactLevel.CRITICAL, 10, 10,
        )
        engine.produce_result("sim-strict")
        engine.recommend_adoption("rec-1", "sim-strict", T)
        rpt = engine.closure_report("rpt-strict", T)
        assert rpt.total_simulations == 1
        assert rpt.total_scenarios == 1
        assert rpt.total_diffs == 1
        assert rpt.total_impacts == 1
        assert rpt.total_recommendations == 1


# ===================================================================
# 16. GOLDEN SCENARIO 2: Approval threshold increases workflow load
# ===================================================================

class TestGoldenApprovalThresholdIncrease:
    """Raising approval threshold to HIGH impact, NOT_READY."""

    def test_end_to_end(self, engine):
        req = _register(engine, "sim-approval", T, "Approval threshold hike")
        engine.start_simulation("sim-approval")

        sc = engine.add_scenario(
            "sc-appr-1", "sim-approval", T, "Approval threshold scenario",
            "workflow-engine", "auto_approved", "manual_review_required",
            PolicyImpactLevel.HIGH,
        )
        assert sc.impact_level == PolicyImpactLevel.HIGH

        engine.record_diff(
            "diff-appr-1", "sim-approval", T, "rule-approval-threshold",
            DiffDisposition.MODIFIED, "auto_approve=true", "auto_approve=false",
        )

        engine.record_impact(
            "imp-appr-1", "sim-approval", T, "workflow-engine",
            PolicyImpactLevel.HIGH, affected_actions=200, blocked_actions=0,
        )

        res = engine.produce_result("sim-approval")
        assert res.adoption_readiness == AdoptionReadiness.NOT_READY
        assert res.readiness_score == 0.3

        rec = engine.recommend_adoption("rec-appr-1", "sim-approval", T)
        assert rec.readiness == AdoptionReadiness.NOT_READY

    def test_assessment_reflects_not_ready(self, engine):
        _register(engine, "sim-approval", T, "Approval threshold hike")
        engine.add_scenario(
            "sc-1", "sim-approval", T, "sc", "wf", "auto", "manual",
            PolicyImpactLevel.HIGH,
        )
        engine.produce_result("sim-approval")
        a = engine.sandbox_assessment("a-appr", T)
        assert a.avg_readiness_score == 0.3


# ===================================================================
# 17. GOLDEN SCENARIO 3: Budget rule reduces marketplace eligibility
# ===================================================================

class TestGoldenBudgetRuleReducesEligibility:
    """Budget constraint rule causes MEDIUM impact, CAUTION readiness."""

    def test_end_to_end(self, engine):
        req = _register(engine, "sim-budget", T, "Budget rule tightening")
        engine.start_simulation("sim-budget")

        sc = engine.add_scenario(
            "sc-budget-1", "sim-budget", T, "Budget constraint scenario",
            "marketplace", "5_services_eligible", "2_services_eligible",
        )
        # Auto-upgrade: outcomes differ, NONE -> MEDIUM
        assert sc.impact_level == PolicyImpactLevel.MEDIUM

        engine.record_diff(
            "diff-budget-1", "sim-budget", T, "rule-max-monthly-spend",
            DiffDisposition.MODIFIED, "max_spend=10000", "max_spend=3000",
        )

        engine.record_impact(
            "imp-budget-1", "sim-budget", T, "marketplace",
            PolicyImpactLevel.MEDIUM, affected_actions=5, blocked_actions=3,
        )

        res = engine.produce_result("sim-budget")
        assert res.adoption_readiness == AdoptionReadiness.CAUTION
        assert res.readiness_score == 0.6

        rec = engine.recommend_adoption("rec-budget-1", "sim-budget", T)
        assert rec.readiness == AdoptionReadiness.CAUTION

    def test_auto_upgrade_on_diff_outcomes(self, engine):
        _register(engine, "sim-budget", T, "Budget rule")
        sc = engine.add_scenario(
            "sc-1", "sim-budget", T, "sc", "mp", "5_eligible", "2_eligible",
        )
        assert sc.impact_level == PolicyImpactLevel.MEDIUM


# ===================================================================
# 18. GOLDEN SCENARIO 4: Workforce policy reroutes
# ===================================================================

class TestGoldenWorkforcePolicyReroutes:
    """Workforce policy change: LOW impact, still READY."""

    def test_end_to_end(self, engine):
        req = _register(engine, "sim-wf", T, "Workforce policy reroute")
        engine.start_simulation("sim-wf")

        sc = engine.add_scenario(
            "sc-wf-1", "sim-wf", T, "Workforce reroute scenario",
            "hr-runtime", "standard_onboarding", "expedited_onboarding",
            PolicyImpactLevel.LOW,
        )
        assert sc.impact_level == PolicyImpactLevel.LOW

        engine.record_impact(
            "imp-wf-1", "sim-wf", T, "hr-runtime",
            PolicyImpactLevel.LOW, affected_actions=10, blocked_actions=0,
        )

        res = engine.produce_result("sim-wf")
        assert res.adoption_readiness == AdoptionReadiness.READY
        assert res.readiness_score == 1.0

        rec = engine.recommend_adoption("rec-wf-1", "sim-wf", T)
        assert rec.readiness == AdoptionReadiness.READY
        assert rec.readiness_score == 1.0


# ===================================================================
# 19. GOLDEN SCENARIO 5: Low readiness blocks rollout
# ===================================================================

class TestGoldenLowReadinessBlocksRollout:
    """Multiple CRITICAL scenarios: BLOCKED, triggers violation if no rec."""

    def test_end_to_end(self, engine):
        _register(engine, "sim-block", T, "Low readiness rollout")
        engine.start_simulation("sim-block")

        for i in range(5):
            engine.add_scenario(
                f"sc-block-{i}", "sim-block", T, f"Critical scenario {i}",
                f"runtime-{i}", "operational", "down",
                PolicyImpactLevel.CRITICAL,
            )

        for i in range(3):
            engine.record_impact(
                f"imp-block-{i}", "sim-block", T, f"runtime-{i}",
                PolicyImpactLevel.CRITICAL, affected_actions=100, blocked_actions=100,
            )

        res = engine.produce_result("sim-block")
        assert res.max_impact_level == PolicyImpactLevel.CRITICAL
        assert res.adoption_readiness == AdoptionReadiness.BLOCKED
        assert res.readiness_score == 0.0
        assert res.scenario_count == 5
        assert res.impacted_count == 5

    def test_blocked_no_rec_violation(self, engine):
        _register(engine, "sim-block", T, "Low readiness rollout")
        engine.add_scenario(
            "sc-1", "sim-block", T, "sc", "rt", "ok", "down",
            PolicyImpactLevel.CRITICAL,
        )
        engine.produce_result("sim-block")
        vs = engine.detect_sandbox_violations(T)
        assert any(v.operation == "blocked_no_recommendation" for v in vs)

    def test_adding_rec_clears_violation(self, engine):
        _register(engine, "sim-block", T, "Low readiness rollout")
        engine.add_scenario(
            "sc-1", "sim-block", T, "sc", "rt", "ok", "down",
            PolicyImpactLevel.CRITICAL,
        )
        engine.produce_result("sim-block")
        engine.recommend_adoption("rec-1", "sim-block", T)
        vs = engine.detect_sandbox_violations(T)
        assert not any(v.operation == "blocked_no_recommendation" for v in vs)


# ===================================================================
# 20. GOLDEN SCENARIO 6: Replay / restore state_hash
# ===================================================================

class TestGoldenReplayRestoreStateHash:
    """Deterministic replay: same operations produce same state_hash."""

    def _build_state(self, engine):
        _register(engine, "r1", T, "A")
        _register(engine, "r2", T, "B")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        _add_scenario(engine, "s1", "r1", T, "sc", "rt", "a", "b")
        _add_scenario(engine, "s2", "r2", T, "sc", "rt", "x", "x")
        _record_diff(engine, "d1", "r1", T)
        _record_impact(engine, "i1", "r1", T)
        engine.produce_result("r1")
        engine.detect_sandbox_violations(T)

    def test_replay_produces_consistent_hash(self):
        es1 = EventSpineEngine()
        eng1 = PolicySimulationEngine(es1)
        self._build_state(eng1)
        h1 = eng1.state_hash()
        # Hash is valid sha256 hex
        assert len(h1) == 64
        assert all(c in "0123456789abcdef" for c in h1)
        # Same engine, same hash (idempotent)
        assert eng1.state_hash() == h1

    def test_different_state_different_hash(self):
        es1 = EventSpineEngine()
        eng1 = PolicySimulationEngine(es1)
        self._build_state(eng1)
        h1 = eng1.state_hash()

        es2 = EventSpineEngine()
        eng2 = PolicySimulationEngine(es2)
        self._build_state(eng2)
        _register(eng2, "r3", T, "Extra")
        h2 = eng2.state_hash()

        assert h1 != h2

    def test_hash_stable_across_reads(self):
        es = EventSpineEngine()
        eng = PolicySimulationEngine(es)
        self._build_state(eng)
        h1 = eng.state_hash()
        # Read operations should not change hash
        eng.simulations_for_tenant(T)
        eng.scenarios_for_simulation("r1")
        eng.diffs_for_simulation("r1")
        eng.impacts_for_simulation("r1")
        eng.results_for_simulation("r1")
        eng.violations_for_tenant(T)
        h2 = eng.state_hash()
        assert h1 == h2


# ===================================================================
# 21. PROPERTY COUNTS
# ===================================================================

class TestPropertyCounts:
    def test_request_count(self, engine):
        for i in range(5):
            _register(engine, f"r{i}")
        assert engine.request_count == 5

    def test_scenario_count(self, engine):
        _register(engine, "r1")
        for i in range(4):
            _add_scenario(engine, f"s{i}", "r1", T, f"S{i}", "rt",
                          "a", "b")
        assert engine.scenario_count == 4

    def test_result_count(self, engine):
        _register(engine, "r1")
        engine.produce_result("r1")
        engine.produce_result("r1")
        assert engine.result_count == 2

    def test_diff_count(self, engine):
        _register(engine, "r1")
        for i in range(3):
            _record_diff(engine, f"d{i}", "r1")
        assert engine.diff_count == 3

    def test_impact_count(self, engine):
        _register(engine, "r1")
        for i in range(3):
            _record_impact(engine, f"i{i}", "r1")
        assert engine.impact_count == 3

    def test_recommendation_count(self, engine):
        _register(engine, "r1")
        engine.produce_result("r1")
        engine.recommend_adoption("rec-1", "r1", T)
        assert engine.recommendation_count == 1

    def test_violation_count(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.detect_sandbox_violations(T)
        assert engine.violation_count == 1

    def test_assessment_count(self, engine):
        engine.sandbox_assessment("a-1", T)
        engine.sandbox_assessment("a-2", T)
        assert engine.assessment_count == 2


# ===================================================================
# 22. EVENT EMISSION (cross-cutting)
# ===================================================================

class TestEventEmission:
    def test_every_mutation_emits(self, engine, es):
        _register(engine, "r1")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        _register(engine, "r2")
        engine.fail_simulation("r2")
        _register(engine, "r3")
        engine.cancel_simulation("r3")
        # register(3) + start(1) + complete(1) + fail(1) + cancel(1) = 7
        assert es.event_count >= 7

    def test_scenario_emits(self, engine, es):
        _register(engine)
        before = es.event_count
        _add_scenario(engine, baseline="a", simulated="b")
        assert es.event_count == before + 1

    def test_diff_emits(self, engine, es):
        _register(engine)
        before = es.event_count
        _record_diff(engine)
        assert es.event_count == before + 1

    def test_impact_emits(self, engine, es):
        _register(engine)
        before = es.event_count
        _record_impact(engine)
        assert es.event_count == before + 1

    def test_result_emits(self, engine, es):
        _register(engine)
        before = es.event_count
        engine.produce_result("req-1")
        assert es.event_count == before + 1

    def test_recommendation_emits(self, engine, es):
        _register(engine)
        engine.produce_result("req-1")
        before = es.event_count
        engine.recommend_adoption("rec-1", "req-1", T)
        assert es.event_count == before + 1

    def test_snapshot_emits(self, engine, es):
        before = es.event_count
        engine.sandbox_snapshot("snap-1", T)
        assert es.event_count == before + 1

    def test_assessment_emits(self, engine, es):
        before = es.event_count
        engine.sandbox_assessment("a-1", T)
        assert es.event_count == before + 1

    def test_closure_report_emits(self, engine, es):
        before = es.event_count
        engine.closure_report("rpt-1", T)
        assert es.event_count == before + 1


# ===================================================================
# 23. IMMUTABILITY OF RETURNS
# ===================================================================

class TestImmutability:
    def test_request_is_frozen(self, engine):
        req = _register(engine)
        with pytest.raises(AttributeError):
            req.status = SimulationStatus.RUNNING

    def test_scenario_is_frozen(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng)
        with pytest.raises(AttributeError):
            sc.impact_level = PolicyImpactLevel.HIGH

    def test_diff_is_frozen(self, sim):
        eng, _ = sim
        d = _record_diff(eng)
        with pytest.raises(AttributeError):
            d.disposition = DiffDisposition.ADDED

    def test_impact_is_frozen(self, sim):
        eng, _ = sim
        imp = _record_impact(eng)
        with pytest.raises(AttributeError):
            imp.impact_level = PolicyImpactLevel.CRITICAL

    def test_result_is_frozen(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        with pytest.raises(AttributeError):
            res.readiness_score = 999.0

    def test_recommendation_is_frozen(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        with pytest.raises(AttributeError):
            rec.readiness = AdoptionReadiness.BLOCKED

    def test_snapshot_is_frozen(self, engine):
        snap = engine.sandbox_snapshot("snap-1", T)
        with pytest.raises(AttributeError):
            snap.total_simulations = 999

    def test_assessment_is_frozen(self, engine):
        a = engine.sandbox_assessment("a-1", T)
        with pytest.raises(AttributeError):
            a.completion_rate = 999.0

    def test_violation_is_frozen(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        vs = engine.detect_sandbox_violations(T)
        with pytest.raises(AttributeError):
            vs[0].operation = "hacked"

    def test_closure_report_is_frozen(self, engine):
        rpt = engine.closure_report("rpt-1", T)
        with pytest.raises(AttributeError):
            rpt.total_simulations = 999

    def test_simulations_for_tenant_is_tuple(self, sim):
        eng, _ = sim
        result = eng.simulations_for_tenant(T)
        assert isinstance(result, tuple)

    def test_scenarios_for_simulation_is_tuple(self, sim):
        eng, rid = sim
        result = eng.scenarios_for_simulation(rid)
        assert isinstance(result, tuple)

    def test_diffs_for_simulation_is_tuple(self, sim):
        eng, rid = sim
        result = eng.diffs_for_simulation(rid)
        assert isinstance(result, tuple)

    def test_impacts_for_simulation_is_tuple(self, sim):
        eng, rid = sim
        result = eng.impacts_for_simulation(rid)
        assert isinstance(result, tuple)

    def test_results_for_simulation_is_tuple(self, sim):
        eng, rid = sim
        result = eng.results_for_simulation(rid)
        assert isinstance(result, tuple)

    def test_violations_for_tenant_is_tuple(self, engine):
        result = engine.violations_for_tenant(T)
        assert isinstance(result, tuple)

    def test_detect_violations_returns_tuple(self, engine):
        result = engine.detect_sandbox_violations(T)
        assert isinstance(result, tuple)


# ===================================================================
# 24. READINESS MATRIX (parametrized)
# ===================================================================

_READINESS_CASES = [
    (PolicyImpactLevel.NONE, AdoptionReadiness.READY, 1.0),
    (PolicyImpactLevel.LOW, AdoptionReadiness.READY, 1.0),
    (PolicyImpactLevel.MEDIUM, AdoptionReadiness.CAUTION, 0.6),
    (PolicyImpactLevel.HIGH, AdoptionReadiness.NOT_READY, 0.3),
    (PolicyImpactLevel.CRITICAL, AdoptionReadiness.BLOCKED, 0.0),
]


class TestReadinessMatrix:
    @pytest.mark.parametrize("impact,readiness,score", _READINESS_CASES,
                             ids=[c[0].value for c in _READINESS_CASES])
    def test_scenario_impact_to_readiness(self, engine, impact, readiness, score):
        _register(engine, "r1")
        # Use same outcomes for NONE to avoid auto-upgrade to MEDIUM
        base, sim = ("a", "a") if impact == PolicyImpactLevel.NONE else ("a", "b")
        engine.add_scenario("s1", "r1", T, "sc", "rt", base, sim, impact)
        res = engine.produce_result("r1")
        assert res.adoption_readiness == readiness
        assert res.readiness_score == score

    @pytest.mark.parametrize("impact,readiness,score", _READINESS_CASES,
                             ids=[c[0].value for c in _READINESS_CASES])
    def test_impact_record_to_readiness(self, engine, impact, readiness, score):
        _register(engine, "r1")
        engine.record_impact("i1", "r1", T, "rt", impact, 10, 5)
        res = engine.produce_result("r1")
        assert res.adoption_readiness == readiness
        assert res.readiness_score == score


# ===================================================================
# 25. EDGE CASES AND ROBUSTNESS
# ===================================================================

class TestEdgeCases:
    def test_many_simulations(self, engine):
        for i in range(50):
            _register(engine, f"r{i}")
        assert engine.request_count == 50

    def test_many_scenarios_single_sim(self, engine):
        _register(engine, "r1")
        for i in range(50):
            _add_scenario(engine, f"s{i}", "r1", T, f"S{i}", "rt",
                          f"b{i}", f"s{i}")
        assert engine.scenario_count == 50

    def test_many_diffs_single_sim(self, engine):
        _register(engine, "r1")
        for i in range(50):
            _record_diff(engine, f"d{i}", "r1", T, f"rule-{i}",
                         DiffDisposition.MODIFIED, f"old{i}", f"new{i}")
        assert engine.diff_count == 50

    def test_many_impacts_single_sim(self, engine):
        _register(engine, "r1")
        for i in range(50):
            _record_impact(engine, f"i{i}", "r1", T, f"rt-{i}",
                           PolicyImpactLevel.LOW, i, 0)
        assert engine.impact_count == 50

    def test_produce_result_with_many_scenarios_and_impacts(self, engine):
        _register(engine, "r1")
        for i in range(20):
            _add_scenario(engine, f"s{i}", "r1", T, f"S{i}", "rt",
                          "a", "b", PolicyImpactLevel.LOW)
        for i in range(20):
            _record_impact(engine, f"i{i}", "r1", T, f"rt-{i}",
                           PolicyImpactLevel.LOW, 1, 0)
        res = engine.produce_result("r1")
        assert res.scenario_count == 20
        assert res.max_impact_level == PolicyImpactLevel.LOW

    def test_multiple_tenants_isolation(self, engine):
        _register(engine, "r1", "tA", "A")
        _register(engine, "r2", "tB", "B")
        _add_scenario(engine, "s1", "r1", "tA", "sc", "rt", "a", "b",
                       PolicyImpactLevel.CRITICAL)
        _add_scenario(engine, "s2", "r2", "tB", "sc", "rt", "x", "x",
                       PolicyImpactLevel.NONE)
        res_a = engine.produce_result("r1")
        res_b = engine.produce_result("r2")
        assert res_a.max_impact_level == PolicyImpactLevel.CRITICAL
        assert res_b.max_impact_level == PolicyImpactLevel.NONE

    def test_assessment_completion_rate_clamped(self, engine):
        # With no sims, rate defaults to 1.0
        a = engine.sandbox_assessment("a-1", T)
        assert 0.0 <= a.completion_rate <= 1.0
        assert 0.0 <= a.avg_readiness_score <= 1.0

    def test_snapshot_with_violations(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.detect_sandbox_violations(T)
        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_violations == 1

    def test_simulation_modes_all_values(self, engine):
        for i, mode in enumerate(SimulationMode):
            _register(engine, f"r{i}", mode=mode)
            req = engine.get_simulation(f"r{i}")
            assert req.mode == mode

    def test_sandbox_scopes_all_values(self, engine):
        for i, scope in enumerate(SandboxScope):
            _register(engine, f"r{i}", scope=scope)
            req = engine.get_simulation(f"r{i}")
            assert req.scope == scope

    def test_diff_dispositions_all_values(self, engine):
        _register(engine, "r1")
        for i, disp in enumerate(DiffDisposition):
            _record_diff(engine, f"d{i}", "r1", T, f"rule-{i}", disp,
                         f"before{i}", f"after{i}")
            d = engine.diffs_for_simulation("r1")
            assert any(dd.disposition == disp for dd in d)


# ===================================================================
# 26. MULTI-TENANT SCENARIOS
# ===================================================================

class TestMultiTenant:
    def test_tenant_isolation_simulations(self, engine):
        for i in range(5):
            _register(engine, f"rA{i}", "tA", f"A{i}")
            _register(engine, f"rB{i}", "tB", f"B{i}")
        assert len(engine.simulations_for_tenant("tA")) == 5
        assert len(engine.simulations_for_tenant("tB")) == 5

    def test_tenant_isolation_violations(self, engine):
        _register(engine, "rA", "tA", "A")
        _register(engine, "rB", "tB", "B")
        engine.start_simulation("rA")
        engine.start_simulation("rB")
        engine.detect_sandbox_violations("tA")
        engine.detect_sandbox_violations("tB")
        assert len(engine.violations_for_tenant("tA")) == 1
        assert len(engine.violations_for_tenant("tB")) == 1

    def test_tenant_isolation_closure(self, engine):
        _register(engine, "rA", "tA", "A")
        _register(engine, "rB", "tB", "B")
        rpt_a = engine.closure_report("rpt-a", "tA")
        rpt_b = engine.closure_report("rpt-b", "tB")
        assert rpt_a.total_simulations == 1
        assert rpt_b.total_simulations == 1

    def test_tenant_isolation_assessment(self, engine):
        _register(engine, "rA", "tA", "A")
        _register(engine, "rB", "tB", "B")
        engine.start_simulation("rA")
        engine.complete_simulation("rA")
        a_a = engine.sandbox_assessment("a-A", "tA")
        a_b = engine.sandbox_assessment("a-B", "tB")
        assert a_a.completion_rate == 1.0
        assert a_b.completion_rate == 0.0

    def test_tenant_isolation_snapshot(self, engine):
        _register(engine, "rA", "tA", "A")
        _register(engine, "rB", "tB", "B")
        _add_scenario(engine, "sA", "rA", "tA", "sc", "rt", "a", "b")
        snap_a = engine.sandbox_snapshot("snap-a", "tA")
        snap_b = engine.sandbox_snapshot("snap-b", "tB")
        assert snap_a.total_scenarios == 1
        assert snap_b.total_scenarios == 0


# ===================================================================
# 27. COMPLEX WORKFLOW SEQUENCES
# ===================================================================

class TestComplexWorkflows:
    def test_full_lifecycle(self, engine):
        """Register -> start -> scenarios -> diffs -> impacts -> result ->
        recommend -> complete -> snapshot -> assessment -> report."""
        req = _register(engine, "r1", T, "Full lifecycle")
        assert req.status == SimulationStatus.DRAFT

        engine.start_simulation("r1")

        engine.add_scenario("s1", "r1", T, "S1", "rt-a", "pass", "fail",
                            PolicyImpactLevel.MEDIUM)
        engine.add_scenario("s2", "r1", T, "S2", "rt-b", "ok", "ok",
                            PolicyImpactLevel.NONE)

        engine.record_diff("d1", "r1", T, "rule-1", DiffDisposition.ADDED,
                           "none", "new_rule")
        engine.record_diff("d2", "r1", T, "rule-2", DiffDisposition.MODIFIED,
                           "old_val", "new_val")

        engine.record_impact("i1", "r1", T, "rt-a",
                             PolicyImpactLevel.MEDIUM, 10, 3)

        res = engine.produce_result("r1")
        assert res.adoption_readiness == AdoptionReadiness.CAUTION

        rec = engine.recommend_adoption("rec-1", "r1", T)
        assert rec.readiness == AdoptionReadiness.CAUTION

        engine.complete_simulation("r1")

        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_simulations == 1
        assert snap.completed_simulations == 1

        a = engine.sandbox_assessment("a-1", T)
        assert a.completion_rate == 1.0

        rpt = engine.closure_report("rpt-1", T)
        assert rpt.total_simulations == 1
        assert rpt.total_scenarios == 2
        assert rpt.total_diffs == 2
        assert rpt.total_impacts == 1
        assert rpt.total_recommendations == 1

    def test_multiple_simulations_one_tenant(self, engine):
        for i in range(3):
            _register(engine, f"r{i}", T, f"Sim {i}")
            engine.start_simulation(f"r{i}")
            engine.add_scenario(
                f"s{i}", f"r{i}", T, f"S{i}", "rt", "a", "b",
                PolicyImpactLevel.LOW,
            )
            engine.produce_result(f"r{i}")
            engine.complete_simulation(f"r{i}")

        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_simulations == 3
        assert snap.completed_simulations == 3

        a = engine.sandbox_assessment("a-1", T)
        assert a.completion_rate == 1.0
        assert a.avg_readiness_score == 1.0  # LOW -> READY -> 1.0

    def test_mixed_readiness_assessment(self, engine):
        # Sim 1: READY (1.0)
        _register(engine, "r1", T, "A")
        engine.produce_result("r1")

        # Sim 2: CAUTION (0.6)
        _register(engine, "r2", T, "B")
        engine.add_scenario("s2", "r2", T, "S", "rt", "a", "b")  # MEDIUM auto
        engine.produce_result("r2")

        # Sim 3: BLOCKED (0.0)
        _register(engine, "r3", T, "C")
        engine.add_scenario("s3", "r3", T, "S", "rt", "a", "b",
                            PolicyImpactLevel.CRITICAL)
        engine.produce_result("r3")

        a = engine.sandbox_assessment("a-1", T)
        # avg = (1.0 + 0.6 + 0.0) / 3 = 0.5333...
        assert abs(a.avg_readiness_score - round((1.0 + 0.6 + 0.0) / 3, 4)) < 0.001

    def test_violation_detection_across_types(self, engine):
        # stuck_running
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")

        # completed_no_result
        _register(engine, "r2", T, "B")
        engine.start_simulation("r2")
        engine.complete_simulation("r2")

        # blocked_no_recommendation
        _register(engine, "r3", T, "C")
        engine.add_scenario("s3", "r3", T, "S", "rt", "a", "b",
                            PolicyImpactLevel.CRITICAL)
        engine.produce_result("r3")

        vs = engine.detect_sandbox_violations(T)
        ops = {v.operation for v in vs}
        assert "stuck_running" in ops
        assert "completed_no_result" in ops
        assert "blocked_no_recommendation" in ops
        assert len(vs) == 3


# ===================================================================
# 28. AUTO-UPGRADE IMPACT LEVEL
# ===================================================================

class TestAutoUpgradeImpact:
    def test_same_outcome_none_stays_none(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="x", simulated="x")
        assert sc.impact_level == PolicyImpactLevel.NONE

    def test_diff_outcome_none_becomes_medium(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="x", simulated="y")
        assert sc.impact_level == PolicyImpactLevel.MEDIUM

    def test_diff_outcome_low_stays_low(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="x", simulated="y",
                           impact=PolicyImpactLevel.LOW)
        assert sc.impact_level == PolicyImpactLevel.LOW

    def test_diff_outcome_high_stays_high(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="x", simulated="y",
                           impact=PolicyImpactLevel.HIGH)
        assert sc.impact_level == PolicyImpactLevel.HIGH

    def test_diff_outcome_critical_stays_critical(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="x", simulated="y",
                           impact=PolicyImpactLevel.CRITICAL)
        assert sc.impact_level == PolicyImpactLevel.CRITICAL

    def test_diff_outcome_medium_stays_medium(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="x", simulated="y",
                           impact=PolicyImpactLevel.MEDIUM)
        assert sc.impact_level == PolicyImpactLevel.MEDIUM

    def test_same_outcome_with_explicit_high_stays(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="same", simulated="same",
                           impact=PolicyImpactLevel.HIGH)
        assert sc.impact_level == PolicyImpactLevel.HIGH


# ===================================================================
# 29. MAX IMPACT AGGREGATION
# ===================================================================

class TestMaxImpactAggregation:
    def test_no_scenarios_no_impacts_is_none(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.NONE

    def test_single_low_scenario(self, sim):
        eng, rid = sim
        _add_scenario(eng, impact=PolicyImpactLevel.LOW,
                       baseline="a", simulated="b")
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.LOW

    def test_scenario_wins_over_impact(self, sim):
        eng, rid = sim
        _add_scenario(eng, impact=PolicyImpactLevel.CRITICAL,
                       baseline="a", simulated="b")
        _record_impact(eng, level=PolicyImpactLevel.LOW)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.CRITICAL

    def test_impact_wins_over_scenario(self, sim):
        eng, rid = sim
        _add_scenario(eng, impact=PolicyImpactLevel.LOW,
                       baseline="a", simulated="b")
        _record_impact(eng, level=PolicyImpactLevel.CRITICAL)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.CRITICAL

    def test_multiple_scenarios_max_wins(self, sim):
        eng, rid = sim
        for i, lvl in enumerate(PolicyImpactLevel):
            _add_scenario(eng, f"s{i}", impact=lvl,
                          baseline="a", simulated="b")
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.CRITICAL

    def test_multiple_impacts_max_wins(self, sim):
        eng, rid = sim
        for i, lvl in enumerate(PolicyImpactLevel):
            _record_impact(eng, f"i{i}", level=lvl)
        res = eng.produce_result(rid)
        assert res.max_impact_level == PolicyImpactLevel.CRITICAL


# ===================================================================
# 30. IMPACTED COUNT
# ===================================================================

class TestImpactedCount:
    def test_none_excluded(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1", baseline="a", simulated="a")  # NONE
        res = eng.produce_result(rid)
        assert res.impacted_count == 0

    def test_low_included(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1", baseline="a", simulated="b",
                       impact=PolicyImpactLevel.LOW)
        res = eng.produce_result(rid)
        assert res.impacted_count == 1

    def test_medium_included(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1", baseline="a", simulated="b")  # MEDIUM auto
        res = eng.produce_result(rid)
        assert res.impacted_count == 1

    def test_mixed_count(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1", baseline="x", simulated="x")  # NONE
        _add_scenario(eng, "s2", baseline="x", simulated="y")  # MEDIUM auto
        _add_scenario(eng, "s3", baseline="x", simulated="y",
                       impact=PolicyImpactLevel.HIGH)
        _add_scenario(eng, "s4", baseline="x", simulated="x")  # NONE
        res = eng.produce_result(rid)
        assert res.impacted_count == 2
        assert res.scenario_count == 4


# ===================================================================
# 31. TERMINAL STATE EXHAUSTIVE TRANSITIONS
# ===================================================================

_TERMINAL_STATES = [
    ("completed", lambda e, r: (e.start_simulation(r), e.complete_simulation(r))),
    ("failed", lambda e, r: e.fail_simulation(r)),
    ("cancelled", lambda e, r: e.cancel_simulation(r)),
]

_TRANSITION_METHODS = [
    ("start", lambda e, r: e.start_simulation(r)),
    ("complete", lambda e, r: e.complete_simulation(r)),
    ("fail", lambda e, r: e.fail_simulation(r)),
    ("cancel", lambda e, r: e.cancel_simulation(r)),
]


class TestTerminalStateExhaustive:
    @pytest.mark.parametrize("terminal_name,setup", _TERMINAL_STATES,
                             ids=[t[0] for t in _TERMINAL_STATES])
    @pytest.mark.parametrize("trans_name,trans_fn", _TRANSITION_METHODS,
                             ids=[t[0] for t in _TRANSITION_METHODS])
    def test_terminal_blocks_all_transitions(self, engine, terminal_name,
                                              setup, trans_name, trans_fn):
        _register(engine, "r1")
        setup(engine, "r1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            trans_fn(engine, "r1")


# ===================================================================
# 32. STRESS / SCALE
# ===================================================================

class TestScale:
    def test_100_simulations_with_scenarios(self, engine):
        for i in range(100):
            _register(engine, f"r{i}", T, f"Sim {i}")
            _add_scenario(engine, f"s{i}", f"r{i}", T, f"S{i}", "rt",
                          "a", "b")
        assert engine.request_count == 100
        assert engine.scenario_count == 100

    def test_produce_results_for_all(self, engine):
        for i in range(20):
            _register(engine, f"r{i}", T, f"Sim {i}")
            _add_scenario(engine, f"s{i}", f"r{i}", T, f"S{i}", "rt",
                          "a", "b", PolicyImpactLevel.MEDIUM)
            engine.produce_result(f"r{i}")
        assert engine.result_count == 20

    def test_state_hash_after_scale(self, engine):
        for i in range(50):
            _register(engine, f"r{i}", T, f"Sim {i}")
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) > 0

    def test_snapshot_after_scale(self, engine):
        for i in range(30):
            _register(engine, f"r{i}", T, f"Sim {i}")
            if i % 2 == 0:
                engine.start_simulation(f"r{i}")
                engine.complete_simulation(f"r{i}")
        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_simulations == 30
        assert snap.completed_simulations == 15


# ===================================================================
# 33. ADDITIONAL SCENARIO COVERAGE
# ===================================================================

class TestAdditionalScenarioCoverage:
    """Extra tests for scenario edge cases."""

    def test_scenario_display_name_stored(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, name="My Custom Scenario")
        assert sc.display_name == "My Custom Scenario"

    def test_scenario_baseline_outcome_stored(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, baseline="baseline_val")
        assert sc.baseline_outcome == "baseline_val"

    def test_scenario_simulated_outcome_stored(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, simulated="simulated_val")
        assert sc.simulated_outcome == "simulated_val"

    def test_scenario_tenant_id_stored(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, tid=T)
        assert sc.tenant_id == T

    def test_scenario_request_id_stored(self, sim):
        eng, _ = sim
        sc = _add_scenario(eng, rid="req-1")
        assert sc.request_id == "req-1"

    def test_multiple_scenarios_different_runtimes(self, sim):
        eng, rid = sim
        for i in range(5):
            _add_scenario(eng, f"s{i}", target=f"runtime-{i}",
                          baseline="a", simulated="b")
        scenes = eng.scenarios_for_simulation(rid)
        runtimes = {s.target_runtime for s in scenes}
        assert len(runtimes) == 5

    def test_scenarios_for_simulation_returns_tuple(self, sim):
        eng, rid = sim
        _add_scenario(eng, "s1")
        result = eng.scenarios_for_simulation(rid)
        assert isinstance(result, tuple)


# ===================================================================
# 34. ADDITIONAL DIFF COVERAGE
# ===================================================================

class TestAdditionalDiffCoverage:
    """Extra tests for diff edge cases."""

    def test_diff_tenant_id_stored(self, sim):
        eng, _ = sim
        d = _record_diff(eng, tid=T)
        assert d.tenant_id == T

    def test_diff_request_id_stored(self, sim):
        eng, _ = sim
        d = _record_diff(eng, rid="req-1")
        assert d.request_id == "req-1"

    def test_diff_rule_ref_stored(self, sim):
        eng, _ = sim
        d = _record_diff(eng, rule="custom-rule-ref")
        assert d.rule_ref == "custom-rule-ref"

    def test_multiple_diffs_different_rules(self, sim):
        eng, rid = sim
        for i in range(5):
            _record_diff(eng, f"d{i}", rule=f"rule-{i}",
                         before=f"old{i}", after=f"new{i}")
        diffs = eng.diffs_for_simulation(rid)
        rules = {d.rule_ref for d in diffs}
        assert len(rules) == 5

    def test_diffs_for_simulation_returns_tuple(self, sim):
        eng, rid = sim
        _record_diff(eng, "d1")
        result = eng.diffs_for_simulation(rid)
        assert isinstance(result, tuple)


# ===================================================================
# 35. ADDITIONAL IMPACT COVERAGE
# ===================================================================

class TestAdditionalImpactCoverage:
    """Extra tests for impact edge cases."""

    def test_impact_tenant_id_stored(self, sim):
        eng, _ = sim
        imp = _record_impact(eng, tid=T)
        assert imp.tenant_id == T

    def test_impact_request_id_stored(self, sim):
        eng, _ = sim
        imp = _record_impact(eng, rid="req-1")
        assert imp.request_id == "req-1"

    def test_impact_zero_affected_actions(self, sim):
        eng, _ = sim
        imp = _record_impact(eng, affected=0, blocked=0)
        assert imp.affected_actions == 0
        assert imp.blocked_actions == 0

    def test_impact_large_action_counts(self, sim):
        eng, _ = sim
        imp = _record_impact(eng, affected=10000, blocked=5000)
        assert imp.affected_actions == 10000
        assert imp.blocked_actions == 5000

    def test_impacts_for_simulation_returns_tuple(self, sim):
        eng, rid = sim
        _record_impact(eng)
        result = eng.impacts_for_simulation(rid)
        assert isinstance(result, tuple)

    def test_multiple_impacts_different_runtimes(self, sim):
        eng, rid = sim
        for i in range(5):
            _record_impact(eng, f"i{i}", target=f"rt-{i}")
        imps = eng.impacts_for_simulation(rid)
        runtimes = {imp.target_runtime for imp in imps}
        assert len(runtimes) == 5


# ===================================================================
# 36. ADDITIONAL RESULT COVERAGE
# ===================================================================

class TestAdditionalResultCoverage:
    """Extra tests for result edge cases."""

    def test_result_request_id_matches(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert res.request_id == rid

    def test_result_scenario_count_zero_when_no_scenarios(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert res.scenario_count == 0

    def test_result_impacted_count_zero_when_no_scenarios(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert res.impacted_count == 0

    def test_results_for_simulation_returns_tuple(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        result = eng.results_for_simulation(rid)
        assert isinstance(result, tuple)

    def test_results_for_different_simulations(self, engine):
        _register(engine, "r1")
        _register(engine, "r2")
        engine.produce_result("r1")
        engine.produce_result("r2")
        assert len(engine.results_for_simulation("r1")) == 1
        assert len(engine.results_for_simulation("r2")) == 1

    def test_result_readiness_score_is_float(self, sim):
        eng, rid = sim
        res = eng.produce_result(rid)
        assert isinstance(res.readiness_score, float)


# ===================================================================
# 37. ADDITIONAL RECOMMENDATION COVERAGE
# ===================================================================

class TestAdditionalRecommendationCoverage:
    def test_recommendation_tenant_id_stored(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        assert rec.tenant_id == T

    def test_recommendation_request_id_stored(self, sim):
        eng, rid = sim
        eng.produce_result(rid)
        rec = eng.recommend_adoption("rec-1", rid, T)
        assert rec.request_id == rid

    def test_multiple_recommendations_different_sims(self, engine):
        _register(engine, "r1")
        _register(engine, "r2")
        engine.produce_result("r1")
        engine.produce_result("r2")
        engine.recommend_adoption("rec-1", "r1", T)
        engine.recommend_adoption("rec-2", "r2", T)
        assert engine.recommendation_count == 2

    def test_blocked_recommendation_reason_contains_blocked(self, engine):
        _register(engine, "r1")
        engine.add_scenario("s1", "r1", T, "sc", "rt", "a", "b",
                            PolicyImpactLevel.CRITICAL)
        engine.produce_result("r1")
        rec = engine.recommend_adoption("rec-1", "r1", T)
        assert "blocked" in rec.reason

    def test_ready_recommendation_reason_contains_ready(self, engine):
        _register(engine, "r1")
        engine.produce_result("r1")
        rec = engine.recommend_adoption("rec-1", "r1", T)
        assert "ready" in rec.reason


# ===================================================================
# 38. SNAPSHOT ADDITIONAL TESTS
# ===================================================================

class TestSnapshotAdditional:
    def test_snapshot_id_stored(self, engine):
        snap = engine.sandbox_snapshot("my-snap-id", T)
        assert snap.snapshot_id == "my-snap-id"

    def test_snapshot_tenant_id_stored(self, engine):
        snap = engine.sandbox_snapshot("snap-1", "my-tenant")
        assert snap.tenant_id == "my-tenant"

    def test_snapshot_multiple_calls_not_cumulative(self, engine):
        _register(engine, "r1", T, "A")
        snap1 = engine.sandbox_snapshot("snap-1", T)
        snap2 = engine.sandbox_snapshot("snap-2", T)
        assert snap1.total_simulations == snap2.total_simulations

    def test_snapshot_draft_not_completed(self, engine):
        _register(engine, "r1", T, "A")
        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_simulations == 1
        assert snap.completed_simulations == 0

    def test_snapshot_failed_not_completed(self, engine):
        _register(engine, "r1", T, "A")
        engine.fail_simulation("r1")
        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_simulations == 1
        assert snap.completed_simulations == 0

    def test_snapshot_cancelled_not_completed(self, engine):
        _register(engine, "r1", T, "A")
        engine.cancel_simulation("r1")
        snap = engine.sandbox_snapshot("snap-1", T)
        assert snap.total_simulations == 1
        assert snap.completed_simulations == 0


# ===================================================================
# 39. ASSESSMENT ADDITIONAL TESTS
# ===================================================================

class TestAssessmentAdditional:
    def test_assessment_id_stored(self, engine):
        a = engine.sandbox_assessment("my-assess", T)
        assert a.assessment_id == "my-assess"

    def test_assessment_tenant_id_stored(self, engine):
        a = engine.sandbox_assessment("a-1", "my-tenant")
        assert a.tenant_id == "my-tenant"

    def test_assessment_failed_sims_not_completed(self, engine):
        _register(engine, "r1", T, "A")
        engine.fail_simulation("r1")
        a = engine.sandbox_assessment("a-1", T)
        assert a.completion_rate == 0.0

    def test_assessment_cancelled_sims_not_completed(self, engine):
        _register(engine, "r1", T, "A")
        engine.cancel_simulation("r1")
        a = engine.sandbox_assessment("a-1", T)
        assert a.completion_rate == 0.0

    def test_assessment_three_of_four_completed(self, engine):
        for i in range(4):
            _register(engine, f"r{i}", T, f"Sim {i}")
        for i in range(3):
            engine.start_simulation(f"r{i}")
            engine.complete_simulation(f"r{i}")
        a = engine.sandbox_assessment("a-1", T)
        assert a.completion_rate == 0.75


# ===================================================================
# 40. CLOSURE REPORT ADDITIONAL TESTS
# ===================================================================

class TestClosureReportAdditional:
    def test_report_id_stored(self, engine):
        rpt = engine.closure_report("my-report", T)
        assert rpt.report_id == "my-report"

    def test_report_tenant_id_stored(self, engine):
        rpt = engine.closure_report("rpt-1", "my-tenant")
        assert rpt.tenant_id == "my-tenant"

    def test_report_created_at_is_iso(self, engine):
        rpt = engine.closure_report("rpt-1", T)
        assert "T" in rpt.created_at  # ISO format contains T separator

    def test_report_with_multiple_recommendations(self, engine):
        _register(engine, "r1", T, "A")
        _register(engine, "r2", T, "B")
        engine.produce_result("r1")
        engine.produce_result("r2")
        engine.recommend_adoption("rec-1", "r1", T)
        engine.recommend_adoption("rec-2", "r2", T)
        rpt = engine.closure_report("rpt-1", T)
        assert rpt.total_recommendations == 2

    def test_report_with_no_violations(self, engine):
        _register(engine, "r1", T, "A")
        rpt = engine.closure_report("rpt-1", T)
        assert rpt.total_violations == 0


# ===================================================================
# 41. STATE HASH ADVANCED
# ===================================================================

class TestStateHashAdvanced:
    def test_hash_includes_diff_disposition(self, engine):
        _register(engine, "r1")
        _record_diff(engine, "d1", rid="r1", disp=DiffDisposition.ADDED)
        h1 = engine.state_hash()
        # Create new engine with REMOVED disposition
        es2 = EventSpineEngine()
        eng2 = PolicySimulationEngine(es2)
        _register(eng2, "r1")
        eng2.record_diff("d1", "r1", T, "rule-a", DiffDisposition.REMOVED,
                         "old", "new")
        h2 = eng2.state_hash()
        assert h1 != h2

    def test_hash_includes_impact_level(self, engine):
        _register(engine, "r1")
        _record_impact(engine, "i1", rid="r1", level=PolicyImpactLevel.LOW)
        h1 = engine.state_hash()
        es2 = EventSpineEngine()
        eng2 = PolicySimulationEngine(es2)
        _register(eng2, "r1")
        eng2.record_impact("i1", "r1", T, "rt-a",
                           PolicyImpactLevel.HIGH, 5, 1)
        h2 = eng2.state_hash()
        assert h1 != h2

    def test_hash_includes_scenario_impact_level(self, engine):
        _register(engine, "r1")
        _add_scenario(engine, "s1", rid="r1", impact=PolicyImpactLevel.LOW,
                      baseline="a", simulated="b")
        h1 = engine.state_hash()
        es2 = EventSpineEngine()
        eng2 = PolicySimulationEngine(es2)
        _register(eng2, "r1")
        eng2.add_scenario("s1", "r1", T, "Scenario", "runtime-a",
                          "a", "b", PolicyImpactLevel.HIGH)
        h2 = eng2.state_hash()
        assert h1 != h2

    def test_hash_order_independent_of_insertion_for_same_keys(self):
        """Hash sorts by key, so insertion order should not matter
        for the same set of keys."""
        es1 = EventSpineEngine()
        eng1 = PolicySimulationEngine(es1)
        _register(eng1, "r1")
        _register(eng1, "r2")

        es2 = EventSpineEngine()
        eng2 = PolicySimulationEngine(es2)
        _register(eng2, "r2")
        _register(eng2, "r1")

        assert eng1.state_hash() == eng2.state_hash()


# ===================================================================
# 42. VIOLATION DETAILS
# ===================================================================

class TestViolationDetails:
    def test_stuck_running_violation_fields(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        vs = engine.detect_sandbox_violations(T)
        v = vs[0]
        assert v.tenant_id == T
        assert v.violation_id != ""
        assert v.detected_at != ""

    def test_completed_no_result_violation_fields(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.complete_simulation("r1")
        vs = engine.detect_sandbox_violations(T)
        v = vs[0]
        assert v.tenant_id == T
        assert v.operation == "completed_no_result"
        assert v.reason == "completed simulation has no result"
        assert "r1" not in v.reason
        assert T not in v.reason

    def test_blocked_no_rec_violation_fields(self, engine):
        _register(engine, "r1", T, "A")
        engine.add_scenario("s1", "r1", T, "sc", "rt", "a", "b",
                            PolicyImpactLevel.CRITICAL)
        res = engine.produce_result("r1")
        vs = engine.detect_sandbox_violations(T)
        v = vs[0]
        assert v.tenant_id == T
        assert v.operation == "blocked_no_recommendation"
        assert v.reason == "blocked simulation result has no recommendation"
        assert res.result_id not in v.reason
        assert T not in v.reason

    def test_violation_ids_are_deterministic(self, engine):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.detect_sandbox_violations(T)
        vs1 = engine.violations_for_tenant(T)

        es2 = EventSpineEngine()
        eng2 = PolicySimulationEngine(es2)
        _register(eng2, "r1", T, "A")
        eng2.start_simulation("r1")
        eng2.detect_sandbox_violations(T)
        vs2 = eng2.violations_for_tenant(T)

        assert vs1[0].violation_id == vs2[0].violation_id

    def test_multiple_stuck_running_creates_separate_violations(self, engine):
        for i in range(3):
            _register(engine, f"r{i}", T, f"Sim {i}")
            engine.start_simulation(f"r{i}")
        vs = engine.detect_sandbox_violations(T)
        stuck = [v for v in vs if v.operation == "stuck_running"]
        assert len(stuck) == 3

    def test_not_ready_does_not_trigger_violation(self, engine):
        """Only BLOCKED triggers blocked_no_recommendation, not NOT_READY."""
        _register(engine, "r1", T, "A")
        engine.add_scenario("s1", "r1", T, "sc", "rt", "a", "b",
                            PolicyImpactLevel.HIGH)
        engine.produce_result("r1")  # NOT_READY
        vs = engine.detect_sandbox_violations(T)
        assert not any(v.operation == "blocked_no_recommendation" for v in vs)

    def test_caution_does_not_trigger_violation(self, engine):
        _register(engine, "r1", T, "A")
        engine.add_scenario("s1", "r1", T, "sc", "rt", "a", "b")  # MEDIUM
        engine.produce_result("r1")  # CAUTION
        vs = engine.detect_sandbox_violations(T)
        assert not any(v.operation == "blocked_no_recommendation" for v in vs)

    def test_ready_does_not_trigger_violation(self, engine):
        _register(engine, "r1", T, "A")
        engine.produce_result("r1")  # READY
        vs = engine.detect_sandbox_violations(T)
        assert not any(v.operation == "blocked_no_recommendation" for v in vs)

    def test_draft_does_not_trigger_stuck_running(self, engine):
        _register(engine, "r1", T, "A")
        vs = engine.detect_sandbox_violations(T)
        assert not any(v.operation == "stuck_running" for v in vs)

    def test_failed_does_not_trigger_completed_no_result(self, engine):
        _register(engine, "r1", T, "A")
        engine.fail_simulation("r1")
        vs = engine.detect_sandbox_violations(T)
        assert not any(v.operation == "completed_no_result" for v in vs)

    def test_cancelled_does_not_trigger_completed_no_result(self, engine):
        _register(engine, "r1", T, "A")
        engine.cancel_simulation("r1")
        vs = engine.detect_sandbox_violations(T)
        assert not any(v.operation == "completed_no_result" for v in vs)


# ===================================================================
# 43. PARAMETRIZED SIMULATION MODE AND SCOPE COMBINATIONS
# ===================================================================

_ALL_MODES = list(SimulationMode)
_ALL_SCOPES = list(SandboxScope)


class TestModeAndScopeParametrized:
    @pytest.mark.parametrize("mode", _ALL_MODES, ids=[m.value for m in _ALL_MODES])
    def test_register_with_each_mode(self, engine, mode):
        req = engine.register_simulation("r1", T, "Sim", mode=mode)
        assert req.mode == mode
        assert req.status == SimulationStatus.DRAFT

    @pytest.mark.parametrize("scope", _ALL_SCOPES, ids=[s.value for s in _ALL_SCOPES])
    def test_register_with_each_scope(self, engine, scope):
        req = engine.register_simulation("r1", T, "Sim", scope=scope)
        assert req.scope == scope
        assert req.status == SimulationStatus.DRAFT

    @pytest.mark.parametrize("mode", _ALL_MODES, ids=[m.value for m in _ALL_MODES])
    @pytest.mark.parametrize("scope", _ALL_SCOPES, ids=[s.value for s in _ALL_SCOPES])
    def test_mode_scope_combinations(self, engine, mode, scope):
        req = engine.register_simulation("r1", T, "Sim", mode=mode, scope=scope)
        assert req.mode == mode
        assert req.scope == scope


# ===================================================================
# 44. EVENT PAYLOAD CONTENT
# ===================================================================

class TestEventPayloadContent:
    def test_register_event_has_request_id(self, engine, es):
        _register(engine, "r1")
        events = es.list_events()
        payloads = [e.payload for e in events]
        assert any(p.get("request_id") == "r1" for p in payloads)

    def test_scenario_event_has_scenario_id(self, engine, es):
        _register(engine, "r1")
        _add_scenario(engine, "s1", rid="r1", baseline="a", simulated="b")
        events = es.list_events()
        payloads = [e.payload for e in events]
        assert any(p.get("scenario_id") == "s1" for p in payloads)

    def test_diff_event_has_diff_id(self, engine, es):
        _register(engine, "r1")
        _record_diff(engine, "d1", rid="r1")
        events = es.list_events()
        payloads = [e.payload for e in events]
        assert any(p.get("diff_id") == "d1" for p in payloads)

    def test_impact_event_has_impact_id(self, engine, es):
        _register(engine, "r1")
        _record_impact(engine, "i1", rid="r1")
        events = es.list_events()
        payloads = [e.payload for e in events]
        assert any(p.get("impact_id") == "i1" for p in payloads)

    def test_result_event_has_readiness(self, engine, es):
        _register(engine, "r1")
        engine.produce_result("r1")
        events = es.list_events()
        payloads = [e.payload for e in events]
        assert any(p.get("readiness") == "ready" for p in payloads)

    def test_recommendation_event_has_id(self, engine, es):
        _register(engine, "r1")
        engine.produce_result("r1")
        engine.recommend_adoption("rec-1", "r1", T)
        events = es.list_events()
        payloads = [e.payload for e in events]
        assert any(p.get("recommendation_id") == "rec-1" for p in payloads)

    def test_violation_event_has_count(self, engine, es):
        _register(engine, "r1", T, "A")
        engine.start_simulation("r1")
        engine.detect_sandbox_violations(T)
        events = es.list_events()
        payloads = [e.payload for e in events]
        assert any(p.get("count") == 1 for p in payloads)


class TestBoundedContracts:
    def test_duplicate_request_error_is_bounded(self, engine):
        _register(engine, "request-secret", "tenant-secret", "Sensitive")

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            _register(engine, "request-secret", "tenant-secret", "Sensitive")

        message = str(excinfo.value)
        assert message == "duplicate request_id"
        assert "request-secret" not in message
        assert "tenant-secret" not in message

    def test_violation_reasons_are_bounded(self, engine):
        _register(engine, "request-running", "tenant-secret", "Running")
        engine.start_simulation("request-running")
        _register(engine, "request-completed", "tenant-secret", "Completed")
        engine.start_simulation("request-completed")
        engine.complete_simulation("request-completed")
        _register(engine, "request-blocked", "tenant-secret", "Blocked")
        engine.add_scenario(
            "scenario-secret",
            "request-blocked",
            "tenant-secret",
            "Scenario",
            "runtime-secret",
            "allow",
            "deny",
            PolicyImpactLevel.CRITICAL,
        )
        engine.produce_result("request-blocked")

        violations = engine.detect_sandbox_violations("tenant-secret")
        reasons = {violation.operation: violation.reason for violation in violations}
        joined = " ".join(reasons.values())

        assert reasons["stuck_running"] == "simulation stuck in RUNNING state"
        assert reasons["completed_no_result"] == "completed simulation has no result"
        assert reasons["blocked_no_recommendation"] == "blocked simulation result has no recommendation"
        assert "request-running" not in joined
        assert "request-completed" not in joined
        assert "scenario-secret" not in joined
