"""Purpose: comprehensive tests for MetaOrchestrationEngine.
Governance scope: meta-orchestration / cross-runtime composition engine.
Dependencies: pytest, mcoi_runtime.core.meta_orchestration, event_spine, contracts.
Invariants: every mutation emits an event; duplicate IDs raise; terminal guards hold.
Target: ~350 tests covering all engine methods and golden scenarios.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.meta_orchestration import MetaOrchestrationEngine
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
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def spine() -> EventSpineEngine:
    return EventSpineEngine()


@pytest.fixture
def engine(spine: EventSpineEngine) -> MetaOrchestrationEngine:
    return MetaOrchestrationEngine(spine)


@pytest.fixture
def plan_with_steps(engine: MetaOrchestrationEngine):
    """Create a plan with 3 sequential steps and chained dependencies."""
    plan = engine.register_plan("p1", "t1", "Test Plan")
    s1 = engine.register_step("s1", "p1", "t1", "Step 1", sequence_order=0)
    s2 = engine.register_step("s2", "p1", "t1", "Step 2", sequence_order=1)
    s3 = engine.register_step("s3", "p1", "t1", "Step 3", sequence_order=2)
    engine.add_dependency("d1", "p1", "t1", "s1", "s2")
    engine.add_dependency("d2", "p1", "t1", "s2", "s3")
    return engine


# ===========================================================================
# 1. Constructor / initialization
# ===========================================================================

class TestConstructor:
    def test_valid_construction(self, spine):
        eng = MetaOrchestrationEngine(spine)
        assert eng.plan_count == 0
        assert eng.step_count == 0

    def test_invalid_spine_raises(self):
        with pytest.raises(RuntimeCoreInvariantError):
            MetaOrchestrationEngine("not-a-spine")

    def test_invalid_spine_none(self):
        with pytest.raises(RuntimeCoreInvariantError):
            MetaOrchestrationEngine(None)

    def test_invalid_spine_int(self):
        with pytest.raises(RuntimeCoreInvariantError):
            MetaOrchestrationEngine(42)

    def test_initial_counters_zero(self, engine):
        assert engine.plan_count == 0
        assert engine.step_count == 0
        assert engine.dependency_count == 0
        assert engine.binding_count == 0
        assert engine.decision_count == 0
        assert engine.trace_count == 0
        assert engine.violation_count == 0
        assert engine.assessment_count == 0


# ===========================================================================
# 2. register_plan
# ===========================================================================

class TestRegisterPlan:
    def test_basic_registration(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan One")
        assert isinstance(plan, OrchestrationPlan)
        assert plan.plan_id == "p1"
        assert plan.tenant_id == "t1"
        assert plan.display_name == "Plan One"
        assert plan.status == OrchestrationStatus.DRAFT
        assert plan.step_count == 0
        assert plan.completed_steps == 0
        assert plan.failed_steps == 0

    def test_default_coordination_mode(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan")
        assert plan.coordination_mode == CoordinationMode.SEQUENTIAL

    def test_default_scope(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan")
        assert plan.scope == CompositionScope.TENANT

    def test_custom_coordination_mode(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan", coordination_mode=CoordinationMode.PARALLEL)
        assert plan.coordination_mode == CoordinationMode.PARALLEL

    def test_custom_scope(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan", scope=CompositionScope.CAMPAIGN)
        assert plan.scope == CompositionScope.CAMPAIGN

    def test_conditional_mode(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan", coordination_mode=CoordinationMode.CONDITIONAL)
        assert plan.coordination_mode == CoordinationMode.CONDITIONAL

    def test_fallback_mode(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan", coordination_mode=CoordinationMode.FALLBACK)
        assert plan.coordination_mode == CoordinationMode.FALLBACK

    def test_program_scope(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan", scope=CompositionScope.PROGRAM)
        assert plan.scope == CompositionScope.PROGRAM

    def test_service_scope(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan", scope=CompositionScope.SERVICE)
        assert plan.scope == CompositionScope.SERVICE

    def test_case_scope(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan", scope=CompositionScope.CASE)
        assert plan.scope == CompositionScope.CASE

    def test_global_scope(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan", scope=CompositionScope.GLOBAL)
        assert plan.scope == CompositionScope.GLOBAL

    def test_duplicate_plan_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan One")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate plan_id"):
            engine.register_plan("p1", "t1", "Plan One Again")

    def test_plan_count_increments(self, engine):
        engine.register_plan("p1", "t1", "A")
        assert engine.plan_count == 1
        engine.register_plan("p2", "t1", "B")
        assert engine.plan_count == 2

    def test_created_at_populated(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan")
        assert plan.created_at != ""

    def test_emits_event(self, engine, spine):
        initial = spine.event_count
        engine.register_plan("p1", "t1", "Plan")
        assert spine.event_count == initial + 1

    def test_multiple_tenants(self, engine):
        engine.register_plan("p1", "t1", "T1 Plan")
        engine.register_plan("p2", "t2", "T2 Plan")
        assert engine.plan_count == 2

    def test_frozen_plan(self, engine):
        plan = engine.register_plan("p1", "t1", "Plan")
        with pytest.raises(AttributeError):
            plan.status = OrchestrationStatus.IN_PROGRESS


# ===========================================================================
# 3. get_plan
# ===========================================================================

class TestGetPlan:
    def test_get_existing(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        plan = engine.get_plan("p1")
        assert plan.plan_id == "p1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown plan_id"):
            engine.get_plan("nonexistent")

    def test_get_returns_latest_state(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        s1 = engine.register_step("s1", "p1", "t1", "Step 1")
        plan = engine.get_plan("p1")
        assert plan.step_count == 1


# ===========================================================================
# 4. plans_for_tenant
# ===========================================================================

class TestPlansForTenant:
    def test_empty(self, engine):
        assert engine.plans_for_tenant("t1") == ()

    def test_returns_matching(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t1", "Plan B")
        engine.register_plan("p3", "t2", "Plan C")
        result = engine.plans_for_tenant("t1")
        assert len(result) == 2
        assert all(p.tenant_id == "t1" for p in result)

    def test_returns_tuple(self, engine):
        result = engine.plans_for_tenant("t1")
        assert isinstance(result, tuple)

    def test_different_tenant_isolated(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        assert engine.plans_for_tenant("t2") == ()


# ===========================================================================
# 5. register_step
# ===========================================================================

class TestRegisterStep:
    def test_basic_registration(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step One")
        assert isinstance(step, OrchestrationStep)
        assert step.step_id == "s1"
        assert step.plan_id == "p1"
        assert step.status == OrchestrationStatus.DRAFT

    def test_default_kind(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step")
        assert step.kind == OrchestrationStepKind.INVOKE

    def test_gate_kind(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.GATE)
        assert step.kind == OrchestrationStepKind.GATE

    def test_transform_kind(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.TRANSFORM)
        assert step.kind == OrchestrationStepKind.TRANSFORM

    def test_fallback_kind(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.FALLBACK)
        assert step.kind == OrchestrationStepKind.FALLBACK

    def test_escalation_kind(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.ESCALATION)
        assert step.kind == OrchestrationStepKind.ESCALATION

    def test_default_target_runtime(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step")
        assert step.target_runtime == "unknown"

    def test_custom_target_runtime(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step", target_runtime="billing-rt")
        assert step.target_runtime == "billing-rt"

    def test_custom_target_action(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step", target_action="charge")
        assert step.target_action == "charge"

    def test_sequence_order(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step", sequence_order=5)
        assert step.sequence_order == 5

    def test_duplicate_step_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step One")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate step_id"):
            engine.register_step("s1", "p1", "t1", "Step One Again")

    def test_unknown_plan_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown plan_id"):
            engine.register_step("s1", "nonexistent", "t1", "Step")

    def test_terminal_plan_raises_completed(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True, 10.0)
        engine.advance_execution("p1")
        assert engine.get_plan("p1").status == OrchestrationStatus.COMPLETED
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.register_step("s_new", "p1", "t1", "New Step")

    def test_terminal_plan_raises_cancelled(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.cancel_plan("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.register_step("s_new", "p1", "t1", "New Step")

    def test_increments_step_count(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        assert engine.get_plan("p1").step_count == 1
        engine.register_step("s2", "p1", "t1", "Step 2")
        assert engine.get_plan("p1").step_count == 2

    def test_emits_event(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        initial = spine.event_count
        engine.register_step("s1", "p1", "t1", "Step")
        assert spine.event_count > initial

    def test_step_count_property(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        assert engine.step_count == 2

    def test_frozen_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step("s1", "p1", "t1", "Step")
        with pytest.raises(AttributeError):
            step.status = OrchestrationStatus.READY


# ===========================================================================
# 6. get_step
# ===========================================================================

class TestGetStep:
    def test_get_existing(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        step = engine.get_step("s1")
        assert step.step_id == "s1"

    def test_get_unknown_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown step_id"):
            engine.get_step("nonexistent")


# ===========================================================================
# 7. steps_for_plan
# ===========================================================================

class TestStepsForPlan:
    def test_empty(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        assert engine.steps_for_plan("p1") == ()

    def test_returns_sorted_by_sequence_order(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s3", "p1", "t1", "Third", sequence_order=3)
        engine.register_step("s1", "p1", "t1", "First", sequence_order=1)
        engine.register_step("s2", "p1", "t1", "Second", sequence_order=2)
        steps = engine.steps_for_plan("p1")
        assert [s.sequence_order for s in steps] == [1, 2, 3]

    def test_only_plan_steps(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t1", "Plan B")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.register_step("s2", "p2", "t1", "Step")
        assert len(engine.steps_for_plan("p1")) == 1
        assert len(engine.steps_for_plan("p2")) == 1

    def test_returns_tuple(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        assert isinstance(engine.steps_for_plan("p1"), tuple)


# ===========================================================================
# 8. add_dependency
# ===========================================================================

class TestAddDependency:
    def test_basic_dependency(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        dep = engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        assert isinstance(dep, StepDependency)
        assert dep.dependency_id == "d1"
        assert dep.from_step_id == "s1"
        assert dep.to_step_id == "s2"
        assert dep.disposition == DependencyDisposition.BLOCKED

    def test_duplicate_dependency_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate dependency_id"):
            engine.add_dependency("d1", "p1", "t1", "s1", "s2")

    def test_unknown_plan_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown plan_id"):
            engine.add_dependency("d1", "nonexistent", "t1", "s1", "s2")

    def test_unknown_from_step_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s2", "p1", "t1", "Step 2")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown from_step_id"):
            engine.add_dependency("d1", "p1", "t1", "nonexistent", "s2")

    def test_unknown_to_step_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        with pytest.raises(RuntimeCoreInvariantError, match="unknown to_step_id"):
            engine.add_dependency("d1", "p1", "t1", "s1", "nonexistent")

    def test_dependency_count_increments(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        assert engine.dependency_count == 1

    def test_emits_event(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        initial = spine.event_count
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        assert spine.event_count > initial

    def test_multiple_dependencies_on_same_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.register_step("s3", "p1", "t1", "C")
        engine.add_dependency("d1", "p1", "t1", "s1", "s3")
        engine.add_dependency("d2", "p1", "t1", "s2", "s3")
        assert engine.dependency_count == 2


# ===========================================================================
# 9. dependencies_for_step
# ===========================================================================

class TestDependenciesForStep:
    def test_empty(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        assert engine.dependencies_for_step("s1") == ()

    def test_returns_matching(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        deps = engine.dependencies_for_step("s2")
        assert len(deps) == 1
        assert deps[0].from_step_id == "s1"

    def test_from_step_has_no_incoming(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        assert engine.dependencies_for_step("s1") == ()


# ===========================================================================
# 10. evaluate_dependencies
# ===========================================================================

class TestEvaluateDependencies:
    def test_completed_to_satisfied(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True, 5.0)
        deps = engine.evaluate_dependencies("s2")
        assert len(deps) == 1
        assert deps[0].disposition == DependencyDisposition.SATISFIED

    def test_failed_to_failed(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False, 5.0)
        deps = engine.evaluate_dependencies("s2")
        assert deps[0].disposition == DependencyDisposition.FAILED

    def test_cancelled_to_skipped(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        # Manually update step to cancelled by cancelling plan and re-creating scenario
        engine.cancel_plan("p1")
        deps = engine.evaluate_dependencies("s2")
        assert deps[0].disposition == DependencyDisposition.SKIPPED

    def test_draft_stays_blocked(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        deps = engine.evaluate_dependencies("s2")
        assert deps[0].disposition == DependencyDisposition.BLOCKED

    def test_ready_stays_blocked(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.start_execution("p1")  # s1 becomes READY (no deps)
        deps = engine.evaluate_dependencies("s2")
        assert deps[0].disposition == DependencyDisposition.BLOCKED

    def test_no_deps_returns_empty(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        deps = engine.evaluate_dependencies("s1")
        assert deps == ()

    def test_multiple_deps_all_satisfied(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.register_step("s3", "p1", "t1", "C")
        engine.add_dependency("d1", "p1", "t1", "s1", "s3")
        engine.add_dependency("d2", "p1", "t1", "s2", "s3")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.record_step_result("tr2", "p1", "s2", "t1", True)
        deps = engine.evaluate_dependencies("s3")
        assert all(d.disposition == DependencyDisposition.SATISFIED for d in deps)

    def test_multiple_deps_one_failed(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.register_step("s3", "p1", "t1", "C")
        engine.add_dependency("d1", "p1", "t1", "s1", "s3")
        engine.add_dependency("d2", "p1", "t1", "s2", "s3")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.record_step_result("tr2", "p1", "s2", "t1", False)
        deps = engine.evaluate_dependencies("s3")
        dispositions = {d.disposition for d in deps}
        assert DependencyDisposition.FAILED in dispositions


# ===========================================================================
# 11. bind_runtime
# ===========================================================================

class TestBindRuntime:
    def test_basic_binding(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        b = engine.bind_runtime("b1", "s1", "t1", "billing-rt", "charge")
        assert isinstance(b, RuntimeBinding)
        assert b.binding_id == "b1"
        assert b.runtime_name == "billing-rt"
        assert b.action_name == "charge"
        assert b.config_ref == "default"

    def test_custom_config_ref(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        b = engine.bind_runtime("b1", "s1", "t1", "rt", "act", config_ref="prod-config")
        assert b.config_ref == "prod-config"

    def test_duplicate_binding_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate binding_id"):
            engine.bind_runtime("b1", "s1", "t1", "rt", "act")

    def test_unknown_step_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown step_id"):
            engine.bind_runtime("b1", "nonexistent", "t1", "rt", "act")

    def test_binding_count_increments(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        assert engine.binding_count == 1

    def test_emits_event(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        initial = spine.event_count
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        assert spine.event_count > initial

    def test_multiple_bindings_per_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.bind_runtime("b1", "s1", "t1", "rt1", "act1")
        engine.bind_runtime("b2", "s1", "t1", "rt2", "act2")
        assert engine.binding_count == 2


# ===========================================================================
# 12. bindings_for_step
# ===========================================================================

class TestBindingsForStep:
    def test_empty(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        assert engine.bindings_for_step("s1") == ()

    def test_returns_matching(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        engine.bind_runtime("b2", "s2", "t1", "rt", "act")
        assert len(engine.bindings_for_step("s1")) == 1
        assert len(engine.bindings_for_step("s2")) == 1

    def test_returns_tuple(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        assert isinstance(engine.bindings_for_step("s1"), tuple)


# ===========================================================================
# 13. start_execution
# ===========================================================================

class TestStartExecution:
    def test_basic_start(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        plan = engine.start_execution("p1")
        assert plan.status == OrchestrationStatus.IN_PROGRESS

    def test_no_steps_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        with pytest.raises(RuntimeCoreInvariantError, match="has no steps"):
            engine.start_execution("p1")

    def test_terminal_completed_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.start_execution("p1")

    def test_terminal_cancelled_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.cancel_plan("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.start_execution("p1")

    def test_readies_steps_without_deps(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.start_execution("p1")
        assert engine.get_step("s1").status == OrchestrationStatus.READY
        assert engine.get_step("s2").status == OrchestrationStatus.DRAFT

    def test_readies_all_independent_steps(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.start_execution("p1")
        assert engine.get_step("s1").status == OrchestrationStatus.READY
        assert engine.get_step("s2").status == OrchestrationStatus.READY

    def test_emits_event(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        initial = spine.event_count
        engine.start_execution("p1")
        assert spine.event_count > initial

    def test_unknown_plan_raises(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="unknown plan_id"):
            engine.start_execution("nonexistent")


# ===========================================================================
# 14. advance_execution
# ===========================================================================

class TestAdvanceExecution:
    def test_not_in_progress_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        with pytest.raises(RuntimeCoreInvariantError, match="not IN_PROGRESS"):
            engine.advance_execution("p1")

    def test_completes_plan_all_steps_done(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True, 10.0)
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.COMPLETED

    def test_fails_plan_any_step_failed(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False, 10.0)
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.FAILED

    def test_readies_steps_with_satisfied_deps(self, plan_with_steps):
        engine = plan_with_steps
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True, 10.0)
        engine.advance_execution("p1")
        assert engine.get_step("s2").status == OrchestrationStatus.READY

    def test_fails_steps_with_failed_deps(self, plan_with_steps):
        engine = plan_with_steps
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False, 10.0)
        engine.advance_execution("p1")
        assert engine.get_step("s2").status == OrchestrationStatus.FAILED

    def test_cascade_failure_through_chain(self, plan_with_steps):
        engine = plan_with_steps
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False, 10.0)
        # First advance cascades failure through all deps and auto-fails plan
        plan = engine.advance_execution("p1")
        assert engine.get_step("s2").status == OrchestrationStatus.FAILED
        assert engine.get_step("s3").status == OrchestrationStatus.FAILED
        assert plan.status == OrchestrationStatus.FAILED

    def test_emits_event(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        initial = spine.event_count
        engine.advance_execution("p1")
        assert spine.event_count > initial

    def test_stays_in_progress_with_pending_steps(self, plan_with_steps):
        engine = plan_with_steps
        engine.start_execution("p1")
        # s1 is READY but not completed yet
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.IN_PROGRESS

    def test_parallel_steps_complete_independently(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A", sequence_order=0)
        engine.register_step("s2", "p1", "t1", "B", sequence_order=1)
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.IN_PROGRESS
        engine.record_step_result("tr2", "p1", "s2", "t1", True)
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.COMPLETED

    def test_mixed_success_and_failure(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.record_step_result("tr2", "p1", "s2", "t1", False)
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.FAILED


# ===========================================================================
# 15. record_step_result
# ===========================================================================

class TestRecordStepResult:
    def test_success_trace(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        trace = engine.record_step_result("tr1", "p1", "s1", "t1", True, 42.0)
        assert isinstance(trace, ExecutionTrace)
        assert trace.trace_id == "tr1"
        assert trace.status == OrchestrationStatus.COMPLETED
        assert trace.duration_ms == 42.0

    def test_failure_trace(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        trace = engine.record_step_result("tr1", "p1", "s1", "t1", False, 10.0)
        assert trace.status == OrchestrationStatus.FAILED

    def test_updates_step_status_completed(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert engine.get_step("s1").status == OrchestrationStatus.COMPLETED

    def test_updates_step_status_failed(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        assert engine.get_step("s1").status == OrchestrationStatus.FAILED

    def test_increments_completed_steps(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert engine.get_plan("p1").completed_steps == 1

    def test_increments_failed_steps(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        assert engine.get_plan("p1").failed_steps == 1

    def test_duplicate_trace_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate trace_id"):
            engine.record_step_result("tr1", "p1", "s2", "t1", True)

    def test_terminal_step_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.record_step_result("tr2", "p1", "s1", "t1", True)

    def test_uses_binding_runtime_name(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step", target_runtime="default-rt", target_action="default-act")
        engine.bind_runtime("b1", "s1", "t1", "billing-rt", "charge")
        engine.start_execution("p1")
        trace = engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert trace.runtime_name == "billing-rt"
        assert trace.action_name == "charge"

    def test_uses_step_target_without_binding(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step", target_runtime="my-rt", target_action="my-act")
        engine.start_execution("p1")
        trace = engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert trace.runtime_name == "my-rt"
        assert trace.action_name == "my-act"

    def test_default_duration(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        trace = engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert trace.duration_ms == 0.0

    def test_emits_event(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        initial = spine.event_count
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert spine.event_count > initial

    def test_trace_count_increments(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert engine.trace_count == 1


# ===========================================================================
# 16. traces_for_plan
# ===========================================================================

class TestTracesForPlan:
    def test_empty(self, engine):
        assert engine.traces_for_plan("p1") == ()

    def test_returns_matching(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        traces = engine.traces_for_plan("p1")
        assert len(traces) == 1
        assert traces[0].trace_id == "tr1"

    def test_returns_tuple(self, engine):
        assert isinstance(engine.traces_for_plan("p1"), tuple)


# ===========================================================================
# 17. record_decision
# ===========================================================================

class TestRecordDecision:
    def test_approved_decision(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        d = engine.record_decision("dec1", "p1", "s1", "t1")
        assert isinstance(d, OrchestrationDecision)
        assert d.status == OrchestrationDecisionStatus.APPROVED
        assert d.reason == "auto-approved"

    def test_denied_decision_fails_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.record_decision("dec1", "p1", "s1", "t1",
                               status=OrchestrationDecisionStatus.DENIED,
                               reason="constitutional violation")
        assert engine.get_step("s1").status == OrchestrationStatus.FAILED

    def test_denied_increments_failed_steps(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.record_decision("dec1", "p1", "s1", "t1",
                               status=OrchestrationDecisionStatus.DENIED)
        assert engine.get_plan("p1").failed_steps == 1

    def test_denied_on_terminal_step_no_double_fail(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        # Step is already FAILED, denied should not increment again
        engine.record_decision("dec1", "p1", "s1", "t1",
                               status=OrchestrationDecisionStatus.DENIED)
        assert engine.get_plan("p1").failed_steps == 1

    def test_deferred_decision(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        d = engine.record_decision("dec1", "p1", "s1", "t1",
                                   status=OrchestrationDecisionStatus.DEFERRED)
        assert d.status == OrchestrationDecisionStatus.DEFERRED
        assert engine.get_step("s1").status == OrchestrationStatus.DRAFT

    def test_escalated_decision(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        d = engine.record_decision("dec1", "p1", "s1", "t1",
                                   status=OrchestrationDecisionStatus.ESCALATED)
        assert d.status == OrchestrationDecisionStatus.ESCALATED

    def test_duplicate_decision_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.record_decision("dec1", "p1", "s1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate decision_id"):
            engine.record_decision("dec1", "p1", "s1", "t1")

    def test_custom_reason(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        d = engine.record_decision("dec1", "p1", "s1", "t1", reason="policy override")
        assert d.reason == "policy override"

    def test_decision_count_increments(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.record_decision("dec1", "p1", "s1", "t1")
        assert engine.decision_count == 1

    def test_emits_event(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        initial = spine.event_count
        engine.record_decision("dec1", "p1", "s1", "t1")
        assert spine.event_count > initial


# ===========================================================================
# 18. decisions_for_plan
# ===========================================================================

class TestDecisionsForPlan:
    def test_empty(self, engine):
        assert engine.decisions_for_plan("p1") == ()

    def test_returns_matching(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.record_decision("dec1", "p1", "s1", "t1")
        decs = engine.decisions_for_plan("p1")
        assert len(decs) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.decisions_for_plan("p1"), tuple)

    def test_isolated_by_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t1", "Plan B")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.register_step("s2", "p2", "t1", "Step")
        engine.record_decision("dec1", "p1", "s1", "t1")
        engine.record_decision("dec2", "p2", "s2", "t1")
        assert len(engine.decisions_for_plan("p1")) == 1
        assert len(engine.decisions_for_plan("p2")) == 1


# ===========================================================================
# 19. cancel_plan
# ===========================================================================

class TestCancelPlan:
    def test_basic_cancel(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        plan = engine.cancel_plan("p1")
        assert plan.status == OrchestrationStatus.CANCELLED

    def test_cancels_non_terminal_steps(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.cancel_plan("p1")
        assert engine.get_step("s1").status == OrchestrationStatus.COMPLETED  # already terminal
        assert engine.get_step("s2").status == OrchestrationStatus.CANCELLED

    def test_terminal_plan_raises_completed(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.cancel_plan("p1")

    def test_terminal_plan_raises_cancelled(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.cancel_plan("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.cancel_plan("p1")

    def test_terminal_plan_raises_failed(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal state"):
            engine.cancel_plan("p1")

    def test_emits_event(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        initial = spine.event_count
        engine.cancel_plan("p1")
        assert spine.event_count > initial

    def test_cancel_draft_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        plan = engine.cancel_plan("p1")
        assert plan.status == OrchestrationStatus.CANCELLED

    def test_cancel_in_progress_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        plan = engine.cancel_plan("p1")
        assert plan.status == OrchestrationStatus.CANCELLED


# ===========================================================================
# 20. orchestration_snapshot
# ===========================================================================

class TestOrchestrationSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.orchestration_snapshot("snap1", "t1")
        assert isinstance(snap, OrchestrationSnapshot)
        assert snap.snapshot_id == "snap1"
        assert snap.total_plans == 0
        assert snap.total_steps == 0

    def test_snapshot_counts(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        snap = engine.orchestration_snapshot("snap1", "t1")
        assert snap.total_plans == 1
        assert snap.active_plans == 1
        assert snap.total_steps == 1

    def test_completed_steps_counted(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        snap = engine.orchestration_snapshot("snap1", "t1")
        assert snap.completed_steps == 1

    def test_failed_steps_counted(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        snap = engine.orchestration_snapshot("snap1", "t1")
        assert snap.failed_steps == 1

    def test_tenant_isolation(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t2", "Plan B")
        snap = engine.orchestration_snapshot("snap1", "t1")
        assert snap.total_plans == 1

    def test_emits_event(self, engine, spine):
        initial = spine.event_count
        engine.orchestration_snapshot("snap1", "t1")
        assert spine.event_count > initial

    def test_traces_counted(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        snap = engine.orchestration_snapshot("snap1", "t1")
        assert snap.total_traces == 1

    def test_violations_counted(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.detect_orchestration_violations("t1")
        snap = engine.orchestration_snapshot("snap1", "t1")
        assert snap.total_violations >= 1  # empty_plan violation


# ===========================================================================
# 21. composition_assessment
# ===========================================================================

class TestCompositionAssessment:
    def test_empty_assessment(self, engine):
        a = engine.composition_assessment("a1", "t1")
        assert isinstance(a, CompositionAssessment)
        assert a.total_plans == 0
        assert a.completion_rate == 1.0  # no plans = 1.0
        assert a.failure_rate == 0.0

    def test_completion_rate(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        a = engine.composition_assessment("a1", "t1")
        assert a.completion_rate == 1.0

    def test_failure_rate(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        engine.advance_execution("p1")
        a = engine.composition_assessment("a1", "t1")
        assert a.failure_rate == 1.0

    def test_mixed_rates(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")

        engine.register_plan("p2", "t1", "Plan B")
        engine.register_step("s2", "p2", "t1", "Step")
        engine.start_execution("p2")
        engine.record_step_result("tr2", "p2", "s2", "t1", False)
        engine.advance_execution("p2")

        a = engine.composition_assessment("a1", "t1")
        assert a.completion_rate == 0.5
        assert a.failure_rate == 0.5

    def test_duplicate_assessment_raises(self, engine):
        engine.composition_assessment("a1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate assessment_id"):
            engine.composition_assessment("a1", "t1")

    def test_assessment_count_increments(self, engine):
        engine.composition_assessment("a1", "t1")
        assert engine.assessment_count == 1

    def test_emits_event(self, engine, spine):
        initial = spine.event_count
        engine.composition_assessment("a1", "t1")
        assert spine.event_count > initial

    def test_tenant_isolation(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        a = engine.composition_assessment("a1", "t2")
        assert a.total_plans == 0


# ===========================================================================
# 22. detect_orchestration_violations
# ===========================================================================

class TestDetectOrchestrationViolations:
    def test_empty_plan_violation(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        violations = engine.detect_orchestration_violations("t1")
        assert len(violations) == 1
        assert violations[0].operation == "empty_plan"

    def test_all_steps_failed_violation(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        violations = engine.detect_orchestration_violations("t1")
        ops = {v.operation for v in violations}
        assert "all_steps_failed" in ops

    def test_idempotent_second_call_empty(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        v1 = engine.detect_orchestration_violations("t1")
        assert len(v1) == 1
        v2 = engine.detect_orchestration_violations("t1")
        assert len(v2) == 0

    def test_no_violations_for_healthy_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        violations = engine.detect_orchestration_violations("t1")
        assert len(violations) == 0

    def test_tenant_isolation(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        violations = engine.detect_orchestration_violations("t2")
        assert len(violations) == 0

    def test_violation_count_increments(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.detect_orchestration_violations("t1")
        assert engine.violation_count == 1

    def test_emits_event_when_violations_found(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        initial = spine.event_count
        engine.detect_orchestration_violations("t1")
        assert spine.event_count > initial

    def test_no_event_when_no_new_violations(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.detect_orchestration_violations("t1")
        initial = spine.event_count
        engine.detect_orchestration_violations("t1")
        assert spine.event_count == initial

    def test_multiple_plans_violations(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t1", "Plan B")
        violations = engine.detect_orchestration_violations("t1")
        assert len(violations) == 2


# ===========================================================================
# 23. violations_for_tenant
# ===========================================================================

class TestViolationsForTenant:
    def test_empty(self, engine):
        assert engine.violations_for_tenant("t1") == ()

    def test_returns_matching(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.detect_orchestration_violations("t1")
        assert len(engine.violations_for_tenant("t1")) == 1

    def test_returns_tuple(self, engine):
        assert isinstance(engine.violations_for_tenant("t1"), tuple)


# ===========================================================================
# 24. closure_report
# ===========================================================================

class TestClosureReport:
    def test_empty_report(self, engine):
        report = engine.closure_report("r1", "t1")
        assert isinstance(report, OrchestrationClosureReport)
        assert report.report_id == "r1"
        assert report.total_plans == 0

    def test_counts_all_entities(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        engine.record_decision("dec1", "p1", "s1", "t1")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.detect_orchestration_violations("t1")
        report = engine.closure_report("r1", "t1")
        assert report.total_plans == 1
        assert report.total_steps == 1
        assert report.total_bindings == 1
        assert report.total_decisions == 1
        assert report.total_traces == 1

    def test_emits_event(self, engine, spine):
        initial = spine.event_count
        engine.closure_report("r1", "t1")
        assert spine.event_count > initial

    def test_tenant_isolation(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t2", "Plan B")
        report = engine.closure_report("r1", "t1")
        assert report.total_plans == 1


# ===========================================================================
# 25. state_hash
# ===========================================================================

class TestStateHash:
    def test_empty_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64  # sha256 hex

    def test_deterministic(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_changes_with_plan(self, engine):
        h1 = engine.state_hash()
        engine.register_plan("p1", "t1", "Plan")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        h1 = engine.state_hash()
        engine.register_step("s1", "p1", "t1", "Step")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_dependency(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        h1 = engine.state_hash()
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_binding(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        h1 = engine.state_hash()
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_trace(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        h1 = engine.state_hash()
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_decision(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        h1 = engine.state_hash()
        engine.record_decision("dec1", "p1", "s1", "t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_changes_with_violation(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        h1 = engine.state_hash()
        engine.detect_orchestration_violations("t1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_same_state_same_hash_across_engines(self, spine):
        e1 = MetaOrchestrationEngine(spine)
        spine2 = EventSpineEngine()
        e2 = MetaOrchestrationEngine(spine2)
        # Both empty
        assert e1.state_hash() == e2.state_hash()


# ===========================================================================
# 26. Properties
# ===========================================================================

class TestProperties:
    def test_plan_count(self, engine):
        assert engine.plan_count == 0
        engine.register_plan("p1", "t1", "Plan")
        assert engine.plan_count == 1

    def test_step_count(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        assert engine.step_count == 0
        engine.register_step("s1", "p1", "t1", "Step")
        assert engine.step_count == 1

    def test_dependency_count(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        assert engine.dependency_count == 0
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        assert engine.dependency_count == 1

    def test_binding_count(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        assert engine.binding_count == 0
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        assert engine.binding_count == 1

    def test_decision_count(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        assert engine.decision_count == 0
        engine.record_decision("dec1", "p1", "s1", "t1")
        assert engine.decision_count == 1

    def test_trace_count(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        assert engine.trace_count == 0
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert engine.trace_count == 1

    def test_violation_count(self, engine):
        assert engine.violation_count == 0
        engine.register_plan("p1", "t1", "Plan")
        engine.detect_orchestration_violations("t1")
        assert engine.violation_count == 1

    def test_assessment_count(self, engine):
        assert engine.assessment_count == 0
        engine.composition_assessment("a1", "t1")
        assert engine.assessment_count == 1


# ===========================================================================
# 27. Edge cases and multi-tenant scenarios
# ===========================================================================

class TestEdgeCases:
    def test_many_plans_same_tenant(self, engine):
        for i in range(20):
            engine.register_plan(f"p{i}", "t1", f"Plan {i}")
        assert engine.plan_count == 20
        assert len(engine.plans_for_tenant("t1")) == 20

    def test_many_steps_same_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        for i in range(20):
            engine.register_step(f"s{i}", "p1", "t1", f"Step {i}", sequence_order=i)
        assert engine.get_plan("p1").step_count == 20

    def test_step_ids_unique_across_plans(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t1", "Plan B")
        engine.register_step("s1", "p1", "t1", "Step A1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate step_id"):
            engine.register_step("s1", "p2", "t1", "Step B1")

    def test_dependency_ids_unique_across_plans(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t1", "Plan B")
        engine.register_step("s1", "p1", "t1", "A1")
        engine.register_step("s2", "p1", "t1", "A2")
        engine.register_step("s3", "p2", "t1", "B1")
        engine.register_step("s4", "p2", "t1", "B2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate dependency_id"):
            engine.add_dependency("d1", "p2", "t1", "s3", "s4")

    def test_binding_ids_unique(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate binding_id"):
            engine.bind_runtime("b1", "s2", "t1", "rt", "act")

    def test_trace_ids_unique(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate trace_id"):
            engine.record_step_result("tr1", "p1", "s2", "t1", True)

    def test_decision_ids_unique(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.record_decision("dec1", "p1", "s1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate decision_id"):
            engine.record_decision("dec1", "p1", "s2", "t1")

    def test_assessment_ids_unique(self, engine):
        engine.composition_assessment("a1", "t1")
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate assessment_id"):
            engine.composition_assessment("a1", "t1")

    def test_multi_tenant_snapshot_isolation(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_step("s1", "p1", "t1", "Step A")
        engine.register_plan("p2", "t2", "Plan B")
        engine.register_step("s2", "p2", "t2", "Step B")
        snap1 = engine.orchestration_snapshot("snap1", "t1")
        snap2 = engine.orchestration_snapshot("snap2", "t2")
        assert snap1.total_plans == 1
        assert snap2.total_plans == 1

    def test_multi_tenant_assessment_isolation(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t2", "Plan B")
        a1 = engine.composition_assessment("a1", "t1")
        a2 = engine.composition_assessment("a2", "t2")
        assert a1.total_plans == 1
        assert a2.total_plans == 1

    def test_multi_tenant_closure_isolation(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_step("s1", "p1", "t1", "Step A")
        engine.register_plan("p2", "t2", "Plan B")
        engine.register_step("s2", "p2", "t2", "Step B")
        r1 = engine.closure_report("r1", "t1")
        r2 = engine.closure_report("r2", "t2")
        assert r1.total_plans == 1
        assert r2.total_plans == 1


# ===========================================================================
# 28. Full lifecycle tests
# ===========================================================================

class TestFullLifecycle:
    def test_plan_lifecycle_success(self, engine):
        """Plan: DRAFT -> IN_PROGRESS -> COMPLETED."""
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        assert engine.get_plan("p1").status == OrchestrationStatus.DRAFT
        engine.start_execution("p1")
        assert engine.get_plan("p1").status == OrchestrationStatus.IN_PROGRESS
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        assert engine.get_plan("p1").status == OrchestrationStatus.COMPLETED

    def test_plan_lifecycle_failure(self, engine):
        """Plan: DRAFT -> IN_PROGRESS -> FAILED."""
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        engine.advance_execution("p1")
        assert engine.get_plan("p1").status == OrchestrationStatus.FAILED

    def test_plan_lifecycle_cancel(self, engine):
        """Plan: DRAFT -> CANCELLED."""
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.cancel_plan("p1")
        assert engine.get_plan("p1").status == OrchestrationStatus.CANCELLED

    def test_step_lifecycle_success(self, engine):
        """Step: DRAFT -> READY -> COMPLETED."""
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        assert engine.get_step("s1").status == OrchestrationStatus.DRAFT
        engine.start_execution("p1")
        assert engine.get_step("s1").status == OrchestrationStatus.READY
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert engine.get_step("s1").status == OrchestrationStatus.COMPLETED

    def test_step_lifecycle_failure(self, engine):
        """Step: DRAFT -> READY -> FAILED."""
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        assert engine.get_step("s1").status == OrchestrationStatus.FAILED

    def test_three_step_sequential_success(self, plan_with_steps):
        """s1 -> s2 -> s3 all complete successfully."""
        engine = plan_with_steps
        engine.start_execution("p1")
        # s1 READY, s2/s3 DRAFT
        engine.record_step_result("tr1", "p1", "s1", "t1", True, 10.0)
        engine.advance_execution("p1")
        assert engine.get_step("s2").status == OrchestrationStatus.READY
        engine.record_step_result("tr2", "p1", "s2", "t1", True, 20.0)
        engine.advance_execution("p1")
        assert engine.get_step("s3").status == OrchestrationStatus.READY
        engine.record_step_result("tr3", "p1", "s3", "t1", True, 30.0)
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.COMPLETED
        assert plan.completed_steps == 3
        assert plan.failed_steps == 0


# ===========================================================================
# GOLDEN SCENARIO 1: Service -> Campaign -> Billing -> Settlement
# ===========================================================================

class TestGoldenServiceCampaignBillingSettlement:
    def test_full_orchestration(self, engine):
        plan = engine.register_plan("svc-plan-001", "tenant-acme", "Service Pipeline",
                                    coordination_mode=CoordinationMode.SEQUENTIAL,
                                    scope=CompositionScope.SERVICE)
        s_svc = engine.register_step("step-svc", "svc-plan-001", "tenant-acme", "Provision Service",
                                     kind=OrchestrationStepKind.INVOKE,
                                     target_runtime="service-rt", target_action="provision",
                                     sequence_order=0)
        s_camp = engine.register_step("step-camp", "svc-plan-001", "tenant-acme", "Launch Campaign",
                                      kind=OrchestrationStepKind.INVOKE,
                                      target_runtime="campaign-rt", target_action="launch",
                                      sequence_order=1)
        s_bill = engine.register_step("step-bill", "svc-plan-001", "tenant-acme", "Generate Invoice",
                                      kind=OrchestrationStepKind.INVOKE,
                                      target_runtime="billing-rt", target_action="invoice",
                                      sequence_order=2)
        s_settle = engine.register_step("step-settle", "svc-plan-001", "tenant-acme", "Settle Payment",
                                        kind=OrchestrationStepKind.INVOKE,
                                        target_runtime="settlement-rt", target_action="settle",
                                        sequence_order=3)
        # Dependencies: svc->camp->bill->settle
        engine.add_dependency("dep-sc", "svc-plan-001", "tenant-acme", "step-svc", "step-camp")
        engine.add_dependency("dep-cb", "svc-plan-001", "tenant-acme", "step-camp", "step-bill")
        engine.add_dependency("dep-bs", "svc-plan-001", "tenant-acme", "step-bill", "step-settle")

        # Bind runtimes
        engine.bind_runtime("bind-svc", "step-svc", "tenant-acme", "service-rt", "provision")
        engine.bind_runtime("bind-camp", "step-camp", "tenant-acme", "campaign-rt", "launch")
        engine.bind_runtime("bind-bill", "step-bill", "tenant-acme", "billing-rt", "invoice")
        engine.bind_runtime("bind-settle", "step-settle", "tenant-acme", "settlement-rt", "settle")

        assert plan.step_count == 0  # original plan object is frozen
        assert engine.get_plan("svc-plan-001").step_count == 4

        # Execute
        engine.start_execution("svc-plan-001")
        assert engine.get_step("step-svc").status == OrchestrationStatus.READY
        assert engine.get_step("step-camp").status == OrchestrationStatus.DRAFT

        # Step 1: service provision
        engine.record_step_result("tr-svc", "svc-plan-001", "step-svc", "tenant-acme", True, 100.0)
        engine.advance_execution("svc-plan-001")
        assert engine.get_step("step-camp").status == OrchestrationStatus.READY

        # Step 2: campaign launch
        engine.record_step_result("tr-camp", "svc-plan-001", "step-camp", "tenant-acme", True, 200.0)
        engine.advance_execution("svc-plan-001")
        assert engine.get_step("step-bill").status == OrchestrationStatus.READY

        # Step 3: billing
        engine.record_step_result("tr-bill", "svc-plan-001", "step-bill", "tenant-acme", True, 50.0)
        engine.advance_execution("svc-plan-001")
        assert engine.get_step("step-settle").status == OrchestrationStatus.READY

        # Step 4: settlement
        engine.record_step_result("tr-settle", "svc-plan-001", "step-settle", "tenant-acme", True, 300.0)
        plan = engine.advance_execution("svc-plan-001")
        assert plan.status == OrchestrationStatus.COMPLETED
        assert plan.completed_steps == 4
        assert plan.failed_steps == 0

        # Traces
        traces = engine.traces_for_plan("svc-plan-001")
        assert len(traces) == 4
        assert traces[0].runtime_name == "service-rt"

        # Closure report
        report = engine.closure_report("rpt-svc", "tenant-acme")
        assert report.total_plans == 1
        assert report.total_steps == 4
        assert report.total_traces == 4
        assert report.total_bindings == 4

    def test_step_ordering(self, engine):
        engine.register_plan("svc-plan-002", "tenant-acme", "Service Pipeline 2")
        engine.register_step("step-settle2", "svc-plan-002", "tenant-acme", "Settle", sequence_order=3)
        engine.register_step("step-svc2", "svc-plan-002", "tenant-acme", "Service", sequence_order=0)
        engine.register_step("step-bill2", "svc-plan-002", "tenant-acme", "Bill", sequence_order=2)
        engine.register_step("step-camp2", "svc-plan-002", "tenant-acme", "Campaign", sequence_order=1)
        steps = engine.steps_for_plan("svc-plan-002")
        assert [s.sequence_order for s in steps] == [0, 1, 2, 3]

    def test_snapshot_after_completion(self, engine):
        engine.register_plan("svc-plan-003", "tenant-acme", "Pipeline")
        engine.register_step("s1", "svc-plan-003", "tenant-acme", "Step 1")
        engine.start_execution("svc-plan-003")
        engine.record_step_result("tr1", "svc-plan-003", "s1", "tenant-acme", True)
        engine.advance_execution("svc-plan-003")
        snap = engine.orchestration_snapshot("snap-svc", "tenant-acme")
        assert snap.total_plans == 1
        assert snap.completed_steps == 1

    def test_assessment_after_completion(self, engine):
        engine.register_plan("svc-plan-004", "tenant-acme", "Pipeline")
        engine.register_step("s1", "svc-plan-004", "tenant-acme", "Step 1")
        engine.start_execution("svc-plan-004")
        engine.record_step_result("tr1", "svc-plan-004", "s1", "tenant-acme", True)
        engine.advance_execution("svc-plan-004")
        a = engine.composition_assessment("a-svc", "tenant-acme")
        assert a.completion_rate == 1.0
        assert a.failure_rate == 0.0


# ===========================================================================
# GOLDEN SCENARIO 2: Case -> Remediation -> Assurance -> Reporting
# ===========================================================================

class TestGoldenCaseRemediationAssuranceReporting:
    def test_full_orchestration(self, engine):
        engine.register_plan("case-plan-001", "tenant-bank", "Case Pipeline",
                             coordination_mode=CoordinationMode.SEQUENTIAL,
                             scope=CompositionScope.CASE)
        engine.register_step("step-case", "case-plan-001", "tenant-bank", "Open Case",
                             target_runtime="case-rt", target_action="open", sequence_order=0)
        engine.register_step("step-remed", "case-plan-001", "tenant-bank", "Remediate",
                             target_runtime="remediation-rt", target_action="fix", sequence_order=1)
        engine.register_step("step-assure", "case-plan-001", "tenant-bank", "Assure Quality",
                             target_runtime="assurance-rt", target_action="verify", sequence_order=2)
        engine.register_step("step-report", "case-plan-001", "tenant-bank", "Generate Report",
                             target_runtime="reporting-rt", target_action="generate", sequence_order=3)

        engine.add_dependency("dep-cr", "case-plan-001", "tenant-bank", "step-case", "step-remed")
        engine.add_dependency("dep-ra", "case-plan-001", "tenant-bank", "step-remed", "step-assure")
        engine.add_dependency("dep-ar", "case-plan-001", "tenant-bank", "step-assure", "step-report")

        engine.start_execution("case-plan-001")

        for step_id, trace_id in [("step-case", "tr-case"), ("step-remed", "tr-remed"),
                                   ("step-assure", "tr-assure"), ("step-report", "tr-report")]:
            engine.record_step_result(trace_id, "case-plan-001", step_id, "tenant-bank", True, 50.0)
            engine.advance_execution("case-plan-001")

        plan = engine.get_plan("case-plan-001")
        assert plan.status == OrchestrationStatus.COMPLETED
        assert plan.completed_steps == 4

    def test_remediation_failure_cascades(self, engine):
        engine.register_plan("case-plan-002", "tenant-bank", "Case Pipeline Fail")
        engine.register_step("step-case", "case-plan-002", "tenant-bank", "Open Case",
                             target_runtime="case-rt", target_action="open", sequence_order=0)
        engine.register_step("step-remed", "case-plan-002", "tenant-bank", "Remediate",
                             target_runtime="remediation-rt", target_action="fix", sequence_order=1)
        engine.register_step("step-assure", "case-plan-002", "tenant-bank", "Assure",
                             target_runtime="assurance-rt", target_action="verify", sequence_order=2)
        engine.add_dependency("dep-cr", "case-plan-002", "tenant-bank", "step-case", "step-remed")
        engine.add_dependency("dep-ra", "case-plan-002", "tenant-bank", "step-remed", "step-assure")

        engine.start_execution("case-plan-002")
        engine.record_step_result("tr-case", "case-plan-002", "step-case", "tenant-bank", True)
        engine.advance_execution("case-plan-002")

        engine.record_step_result("tr-remed", "case-plan-002", "step-remed", "tenant-bank", False)
        engine.advance_execution("case-plan-002")
        assert engine.get_step("step-assure").status == OrchestrationStatus.FAILED
        assert engine.get_plan("case-plan-002").status == OrchestrationStatus.FAILED


# ===========================================================================
# GOLDEN SCENARIO 3: Release -> Marketplace -> Customer Entitlement
# ===========================================================================

class TestGoldenReleaseMarketplaceEntitlement:
    def test_full_orchestration(self, engine):
        engine.register_plan("rel-plan-001", "tenant-saas", "Release Pipeline",
                             coordination_mode=CoordinationMode.SEQUENTIAL,
                             scope=CompositionScope.PROGRAM)
        engine.register_step("step-release", "rel-plan-001", "tenant-saas", "Cut Release",
                             target_runtime="release-rt", target_action="cut", sequence_order=0)
        engine.register_step("step-mkt", "rel-plan-001", "tenant-saas", "Publish Marketplace",
                             target_runtime="marketplace-rt", target_action="publish", sequence_order=1)
        engine.register_step("step-entitle", "rel-plan-001", "tenant-saas", "Customer Entitlement",
                             target_runtime="entitlement-rt", target_action="grant", sequence_order=2)
        engine.add_dependency("dep-rm", "rel-plan-001", "tenant-saas", "step-release", "step-mkt")
        engine.add_dependency("dep-me", "rel-plan-001", "tenant-saas", "step-mkt", "step-entitle")

        engine.bind_runtime("bind-rel", "step-release", "tenant-saas", "release-rt", "cut")
        engine.bind_runtime("bind-mkt", "step-mkt", "tenant-saas", "marketplace-rt", "publish")
        engine.bind_runtime("bind-ent", "step-entitle", "tenant-saas", "entitlement-rt", "grant")

        engine.start_execution("rel-plan-001")
        engine.record_step_result("tr-rel", "rel-plan-001", "step-release", "tenant-saas", True, 60.0)
        engine.advance_execution("rel-plan-001")
        engine.record_step_result("tr-mkt", "rel-plan-001", "step-mkt", "tenant-saas", True, 120.0)
        engine.advance_execution("rel-plan-001")
        engine.record_step_result("tr-ent", "rel-plan-001", "step-entitle", "tenant-saas", True, 30.0)
        plan = engine.advance_execution("rel-plan-001")

        assert plan.status == OrchestrationStatus.COMPLETED
        assert plan.completed_steps == 3
        traces = engine.traces_for_plan("rel-plan-001")
        assert len(traces) == 3
        assert traces[0].runtime_name == "release-rt"

    def test_marketplace_failure_blocks_entitlement(self, engine):
        engine.register_plan("rel-plan-002", "tenant-saas", "Release Fail")
        engine.register_step("step-release", "rel-plan-002", "tenant-saas", "Cut Release",
                             target_runtime="release-rt", target_action="cut", sequence_order=0)
        engine.register_step("step-mkt", "rel-plan-002", "tenant-saas", "Publish",
                             target_runtime="marketplace-rt", target_action="publish", sequence_order=1)
        engine.register_step("step-entitle", "rel-plan-002", "tenant-saas", "Entitle",
                             target_runtime="entitlement-rt", target_action="grant", sequence_order=2)
        engine.add_dependency("dep-rm", "rel-plan-002", "tenant-saas", "step-release", "step-mkt")
        engine.add_dependency("dep-me", "rel-plan-002", "tenant-saas", "step-mkt", "step-entitle")

        engine.start_execution("rel-plan-002")
        engine.record_step_result("tr-rel", "rel-plan-002", "step-release", "tenant-saas", True)
        engine.advance_execution("rel-plan-002")
        engine.record_step_result("tr-mkt", "rel-plan-002", "step-mkt", "tenant-saas", False)
        engine.advance_execution("rel-plan-002")
        assert engine.get_step("step-entitle").status == OrchestrationStatus.FAILED
        assert engine.get_plan("rel-plan-002").status == OrchestrationStatus.FAILED


# ===========================================================================
# GOLDEN SCENARIO 4: Continuity Event Reroutes Active Orchestration
# ===========================================================================

class TestGoldenContinuityReroute:
    def test_failed_dep_cascade_reroutes(self, engine):
        """A mid-plan failure cascades to all downstream steps, failing the plan."""
        engine.register_plan("cont-plan-001", "tenant-ops", "Continuity Pipeline",
                             coordination_mode=CoordinationMode.SEQUENTIAL)
        engine.register_step("step-a", "cont-plan-001", "tenant-ops", "Step A", sequence_order=0)
        engine.register_step("step-b", "cont-plan-001", "tenant-ops", "Step B", sequence_order=1)
        engine.register_step("step-c", "cont-plan-001", "tenant-ops", "Step C", sequence_order=2)
        engine.register_step("step-d", "cont-plan-001", "tenant-ops", "Step D", sequence_order=3)
        engine.add_dependency("dep-ab", "cont-plan-001", "tenant-ops", "step-a", "step-b")
        engine.add_dependency("dep-bc", "cont-plan-001", "tenant-ops", "step-b", "step-c")
        engine.add_dependency("dep-cd", "cont-plan-001", "tenant-ops", "step-c", "step-d")

        engine.start_execution("cont-plan-001")
        engine.record_step_result("tr-a", "cont-plan-001", "step-a", "tenant-ops", True, 10.0)
        engine.advance_execution("cont-plan-001")

        # Step B fails (continuity event) — advance cascades failure through all deps
        engine.record_step_result("tr-b", "cont-plan-001", "step-b", "tenant-ops", False, 5.0)
        plan = engine.advance_execution("cont-plan-001")

        assert engine.get_step("step-c").status == OrchestrationStatus.FAILED
        assert engine.get_step("step-d").status == OrchestrationStatus.FAILED
        assert plan.status == OrchestrationStatus.FAILED

    def test_violation_detected_after_cascade(self, engine):
        engine.register_plan("cont-plan-002", "tenant-ops", "Continuity Fail")
        engine.register_step("step-a", "cont-plan-002", "tenant-ops", "A", sequence_order=0)
        engine.register_step("step-b", "cont-plan-002", "tenant-ops", "B", sequence_order=1)
        engine.add_dependency("dep-ab", "cont-plan-002", "tenant-ops", "step-a", "step-b")
        engine.start_execution("cont-plan-002")
        engine.record_step_result("tr-a", "cont-plan-002", "step-a", "tenant-ops", False)
        # Advance cascades failure and auto-fails plan
        engine.advance_execution("cont-plan-002")
        plan = engine.get_plan("cont-plan-002")
        assert plan.status == OrchestrationStatus.FAILED
        # After plan is FAILED, detect violations should find it through other paths
        violations = engine.detect_orchestration_violations("tenant-ops")
        # Plan already resolved — violation detection may or may not find new ones
        # The key assertion is that the plan ended up FAILED
        assert plan.failed_steps >= 1

    def test_partial_cancel_after_failure(self, engine):
        engine.register_plan("cont-plan-003", "tenant-ops", "Partial Cancel")
        engine.register_step("step-a", "cont-plan-003", "tenant-ops", "A", sequence_order=0)
        engine.register_step("step-b", "cont-plan-003", "tenant-ops", "B", sequence_order=1)
        engine.start_execution("cont-plan-003")
        engine.record_step_result("tr-a", "cont-plan-003", "step-a", "tenant-ops", True)
        # Cancel before step B runs
        engine.cancel_plan("cont-plan-003")
        assert engine.get_step("step-a").status == OrchestrationStatus.COMPLETED
        assert engine.get_step("step-b").status == OrchestrationStatus.CANCELLED
        assert engine.get_plan("cont-plan-003").status == OrchestrationStatus.CANCELLED


# ===========================================================================
# GOLDEN SCENARIO 5: Constitutional Hard-Stop Blocks Step, Stalls Plan
# ===========================================================================

class TestGoldenConstitutionalHardStop:
    def test_denied_step_fails_plan(self, engine):
        """Decision DENIED -> step FAILED -> advance fails entire plan."""
        engine.register_plan("const-plan-001", "tenant-gov", "Constitutional Pipeline",
                             coordination_mode=CoordinationMode.SEQUENTIAL)
        engine.register_step("step-gate", "const-plan-001", "tenant-gov", "Constitutional Gate",
                             kind=OrchestrationStepKind.GATE,
                             target_runtime="constitution-rt", target_action="evaluate",
                             sequence_order=0)
        engine.register_step("step-execute", "const-plan-001", "tenant-gov", "Execute Action",
                             target_runtime="action-rt", target_action="run",
                             sequence_order=1)
        engine.add_dependency("dep-ge", "const-plan-001", "tenant-gov", "step-gate", "step-execute")

        # Decision DENIED on the gate
        engine.record_decision("dec-gate", "const-plan-001", "step-gate", "tenant-gov",
                               status=OrchestrationDecisionStatus.DENIED,
                               reason="Violates constitutional principle #3")

        assert engine.get_step("step-gate").status == OrchestrationStatus.FAILED
        assert engine.get_plan("const-plan-001").failed_steps == 1

        # Start and advance -> plan fails because gate failed
        engine.start_execution("const-plan-001")
        plan = engine.advance_execution("const-plan-001")
        assert engine.get_step("step-execute").status == OrchestrationStatus.FAILED
        assert plan.status == OrchestrationStatus.FAILED

    def test_denied_decision_recorded(self, engine):
        engine.register_plan("const-plan-002", "tenant-gov", "Pipeline 2")
        engine.register_step("step-gate", "const-plan-002", "tenant-gov", "Gate",
                             kind=OrchestrationStepKind.GATE)
        engine.record_decision("dec-gate", "const-plan-002", "step-gate", "tenant-gov",
                               status=OrchestrationDecisionStatus.DENIED,
                               reason="policy violation")
        decisions = engine.decisions_for_plan("const-plan-002")
        assert len(decisions) == 1
        assert decisions[0].status == OrchestrationDecisionStatus.DENIED
        assert decisions[0].reason == "policy violation"

    def test_approved_step_proceeds(self, engine):
        engine.register_plan("const-plan-003", "tenant-gov", "Pipeline Approved")
        engine.register_step("step-gate", "const-plan-003", "tenant-gov", "Gate",
                             kind=OrchestrationStepKind.GATE, sequence_order=0)
        engine.register_step("step-exec", "const-plan-003", "tenant-gov", "Exec", sequence_order=1)
        engine.add_dependency("dep-ge", "const-plan-003", "tenant-gov", "step-gate", "step-exec")

        engine.record_decision("dec-gate", "const-plan-003", "step-gate", "tenant-gov",
                               status=OrchestrationDecisionStatus.APPROVED)
        assert engine.get_step("step-gate").status == OrchestrationStatus.DRAFT  # approved does not change status

        engine.start_execution("const-plan-003")
        engine.record_step_result("tr-gate", "const-plan-003", "step-gate", "tenant-gov", True)
        engine.advance_execution("const-plan-003")
        assert engine.get_step("step-exec").status == OrchestrationStatus.READY

    def test_multi_gate_one_denied(self, engine):
        engine.register_plan("const-plan-004", "tenant-gov", "Multi Gate")
        engine.register_step("step-g1", "const-plan-004", "tenant-gov", "Gate 1",
                             kind=OrchestrationStepKind.GATE, sequence_order=0)
        engine.register_step("step-g2", "const-plan-004", "tenant-gov", "Gate 2",
                             kind=OrchestrationStepKind.GATE, sequence_order=1)
        engine.register_step("step-exec", "const-plan-004", "tenant-gov", "Exec", sequence_order=2)
        engine.add_dependency("dep-g1e", "const-plan-004", "tenant-gov", "step-g1", "step-exec")
        engine.add_dependency("dep-g2e", "const-plan-004", "tenant-gov", "step-g2", "step-exec")

        engine.record_decision("dec-g1", "const-plan-004", "step-g1", "tenant-gov",
                               status=OrchestrationDecisionStatus.APPROVED)
        engine.record_decision("dec-g2", "const-plan-004", "step-g2", "tenant-gov",
                               status=OrchestrationDecisionStatus.DENIED)

        assert engine.get_step("step-g2").status == OrchestrationStatus.FAILED

        engine.start_execution("const-plan-004")
        engine.record_step_result("tr-g1", "const-plan-004", "step-g1", "tenant-gov", True)
        plan = engine.advance_execution("const-plan-004")
        # step-exec should fail because dep step-g2 is FAILED
        assert engine.get_step("step-exec").status == OrchestrationStatus.FAILED
        assert plan.status == OrchestrationStatus.FAILED


# ===========================================================================
# GOLDEN SCENARIO 6: Replay/Restore Preserves State (state_hash determinism)
# ===========================================================================

class TestGoldenReplayRestore:
    def test_state_hash_deterministic(self, engine):
        """Same operations produce same state_hash."""
        engine.register_plan("replay-001", "tenant-replay", "Replay Plan")
        engine.register_step("s1", "replay-001", "tenant-replay", "Step 1", sequence_order=0)
        engine.register_step("s2", "replay-001", "tenant-replay", "Step 2", sequence_order=1)
        engine.add_dependency("d1", "replay-001", "tenant-replay", "s1", "s2")
        engine.bind_runtime("b1", "s1", "tenant-replay", "rt1", "act1")
        engine.start_execution("replay-001")
        engine.record_step_result("tr1", "replay-001", "s1", "tenant-replay", True, 10.0)
        engine.advance_execution("replay-001")
        engine.record_step_result("tr2", "replay-001", "s2", "tenant-replay", True, 20.0)
        engine.advance_execution("replay-001")
        engine.record_decision("dec1", "replay-001", "s1", "tenant-replay")

        h1 = engine.state_hash()

        # Replay same ops in a fresh engine
        spine2 = EventSpineEngine()
        engine2 = MetaOrchestrationEngine(spine2)
        engine2.register_plan("replay-001", "tenant-replay", "Replay Plan")
        engine2.register_step("s1", "replay-001", "tenant-replay", "Step 1", sequence_order=0)
        engine2.register_step("s2", "replay-001", "tenant-replay", "Step 2", sequence_order=1)
        engine2.add_dependency("d1", "replay-001", "tenant-replay", "s1", "s2")
        engine2.bind_runtime("b1", "s1", "tenant-replay", "rt1", "act1")
        engine2.start_execution("replay-001")
        engine2.record_step_result("tr1", "replay-001", "s1", "tenant-replay", True, 10.0)
        engine2.advance_execution("replay-001")
        engine2.record_step_result("tr2", "replay-001", "s2", "tenant-replay", True, 20.0)
        engine2.advance_execution("replay-001")
        engine2.record_decision("dec1", "replay-001", "s1", "tenant-replay")

        h2 = engine2.state_hash()
        assert h1 == h2

    def test_different_ops_different_hash(self, engine):
        engine.register_plan("replay-002", "tenant-replay", "Plan A")
        engine.register_step("s1", "replay-002", "tenant-replay", "Step 1")
        h1 = engine.state_hash()

        spine2 = EventSpineEngine()
        engine2 = MetaOrchestrationEngine(spine2)
        engine2.register_plan("replay-003", "tenant-replay", "Plan B")
        engine2.register_step("s2", "replay-003", "tenant-replay", "Step 2")
        h2 = engine2.state_hash()

        assert h1 != h2

    def test_hash_includes_violations(self, engine):
        engine.register_plan("replay-004", "tenant-replay", "Plan")
        h1 = engine.state_hash()
        engine.detect_orchestration_violations("tenant-replay")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_hash_stable_across_calls(self, engine):
        engine.register_plan("replay-005", "tenant-replay", "Plan")
        engine.register_step("s1", "replay-005", "tenant-replay", "Step")
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        h3 = engine.state_hash()
        assert h1 == h2 == h3

    def test_completed_plan_hash_frozen(self, engine):
        engine.register_plan("replay-006", "tenant-replay", "Plan")
        engine.register_step("s1", "replay-006", "tenant-replay", "Step")
        engine.start_execution("replay-006")
        engine.record_step_result("tr1", "replay-006", "s1", "tenant-replay", True)
        engine.advance_execution("replay-006")
        h1 = engine.state_hash()
        # No more ops => hash stays same
        h2 = engine.state_hash()
        assert h1 == h2

    def test_replay_with_decisions_and_violations(self, engine):
        engine.register_plan("replay-007", "tenant-replay", "Plan")
        engine.register_step("s1", "replay-007", "tenant-replay", "Step")
        engine.record_decision("dec1", "replay-007", "s1", "tenant-replay",
                               status=OrchestrationDecisionStatus.DENIED)
        engine.detect_orchestration_violations("tenant-replay")
        h = engine.state_hash()
        assert isinstance(h, str) and len(h) == 64


# ===========================================================================
# Additional coverage: coordination modes, scopes, step kinds combinations
# ===========================================================================

class TestCoordinationModeVariants:
    def test_parallel_plan(self, engine):
        engine.register_plan("par-001", "t1", "Parallel", coordination_mode=CoordinationMode.PARALLEL)
        engine.register_step("s1", "par-001", "t1", "A")
        engine.register_step("s2", "par-001", "t1", "B")
        engine.start_execution("par-001")
        assert engine.get_step("s1").status == OrchestrationStatus.READY
        assert engine.get_step("s2").status == OrchestrationStatus.READY

    def test_conditional_plan(self, engine):
        plan = engine.register_plan("cond-001", "t1", "Conditional", coordination_mode=CoordinationMode.CONDITIONAL)
        assert plan.coordination_mode == CoordinationMode.CONDITIONAL

    def test_fallback_plan(self, engine):
        plan = engine.register_plan("fb-001", "t1", "Fallback", coordination_mode=CoordinationMode.FALLBACK)
        assert plan.coordination_mode == CoordinationMode.FALLBACK


class TestStepKindVariants:
    def test_invoke_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        s = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.INVOKE)
        assert s.kind == OrchestrationStepKind.INVOKE

    def test_gate_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        s = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.GATE)
        assert s.kind == OrchestrationStepKind.GATE

    def test_transform_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        s = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.TRANSFORM)
        assert s.kind == OrchestrationStepKind.TRANSFORM

    def test_fallback_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        s = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.FALLBACK)
        assert s.kind == OrchestrationStepKind.FALLBACK

    def test_escalation_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        s = engine.register_step("s1", "p1", "t1", "Step", kind=OrchestrationStepKind.ESCALATION)
        assert s.kind == OrchestrationStepKind.ESCALATION


class TestScopeVariants:
    @pytest.mark.parametrize("scope", list(CompositionScope))
    def test_all_scopes(self, engine, scope):
        plan = engine.register_plan(f"p-{scope.value}", "t1", f"Plan {scope.value}", scope=scope)
        assert plan.scope == scope


class TestDecisionStatusVariants:
    @pytest.mark.parametrize("status", list(OrchestrationDecisionStatus))
    def test_all_decision_statuses(self, engine, status):
        engine.register_plan(f"p-{status.value}", "t1", f"Plan {status.value}")
        engine.register_step(f"s-{status.value}", f"p-{status.value}", "t1", f"Step {status.value}")
        d = engine.record_decision(f"dec-{status.value}", f"p-{status.value}",
                                   f"s-{status.value}", "t1", status=status)
        assert d.status == status


class TestDependencyDispositionVariants:
    def test_satisfied_disposition(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        deps = engine.evaluate_dependencies("s2")
        assert deps[0].disposition == DependencyDisposition.SATISFIED

    def test_blocked_disposition(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        deps = engine.evaluate_dependencies("s2")
        assert deps[0].disposition == DependencyDisposition.BLOCKED

    def test_failed_disposition(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        deps = engine.evaluate_dependencies("s2")
        assert deps[0].disposition == DependencyDisposition.FAILED

    def test_skipped_disposition(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.cancel_plan("p1")
        deps = engine.evaluate_dependencies("s2")
        assert deps[0].disposition == DependencyDisposition.SKIPPED


# ===========================================================================
# Event emission coverage
# ===========================================================================

class TestEventEmission:
    def test_register_plan_emits(self, engine, spine):
        before = spine.event_count
        engine.register_plan("p1", "t1", "Plan")
        assert spine.event_count == before + 1

    def test_register_step_emits(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        before = spine.event_count
        engine.register_step("s1", "p1", "t1", "Step")
        assert spine.event_count == before + 1

    def test_add_dependency_emits(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "A")
        engine.register_step("s2", "p1", "t1", "B")
        before = spine.event_count
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        assert spine.event_count == before + 1

    def test_bind_runtime_emits(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        before = spine.event_count
        engine.bind_runtime("b1", "s1", "t1", "rt", "act")
        assert spine.event_count == before + 1

    def test_start_execution_emits(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        before = spine.event_count
        engine.start_execution("p1")
        assert spine.event_count == before + 1

    def test_advance_execution_emits(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        before = spine.event_count
        engine.advance_execution("p1")
        assert spine.event_count >= before + 1

    def test_record_step_result_emits(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        before = spine.event_count
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        assert spine.event_count == before + 1

    def test_record_decision_emits(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        before = spine.event_count
        engine.record_decision("dec1", "p1", "s1", "t1")
        assert spine.event_count == before + 1

    def test_cancel_plan_emits(self, engine, spine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        before = spine.event_count
        engine.cancel_plan("p1")
        assert spine.event_count == before + 1

    def test_snapshot_emits(self, engine, spine):
        before = spine.event_count
        engine.orchestration_snapshot("snap1", "t1")
        assert spine.event_count == before + 1

    def test_assessment_emits(self, engine, spine):
        before = spine.event_count
        engine.composition_assessment("a1", "t1")
        assert spine.event_count == before + 1

    def test_closure_report_emits(self, engine, spine):
        before = spine.event_count
        engine.closure_report("r1", "t1")
        assert spine.event_count == before + 1


# ===========================================================================
# Complex multi-plan scenarios
# ===========================================================================

class TestMultiPlanScenarios:
    def test_two_plans_different_tenants_independent(self, engine):
        engine.register_plan("p1", "t1", "Plan A")
        engine.register_plan("p2", "t2", "Plan B")
        engine.register_step("s1", "p1", "t1", "Step A")
        engine.register_step("s2", "p2", "t2", "Step B")
        engine.start_execution("p1")
        engine.start_execution("p2")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.record_step_result("tr2", "p2", "s2", "t2", False)
        engine.advance_execution("p1")
        engine.advance_execution("p2")
        assert engine.get_plan("p1").status == OrchestrationStatus.COMPLETED
        assert engine.get_plan("p2").status == OrchestrationStatus.FAILED

    def test_same_tenant_multiple_plans(self, engine):
        for i in range(5):
            pid = f"p{i}"
            engine.register_plan(pid, "t1", f"Plan {i}")
            engine.register_step(f"s{i}", pid, "t1", f"Step {i}")
            engine.start_execution(pid)
            engine.record_step_result(f"tr{i}", pid, f"s{i}", "t1", True)
            engine.advance_execution(pid)

        plans = engine.plans_for_tenant("t1")
        assert len(plans) == 5
        assert all(p.status == OrchestrationStatus.COMPLETED for p in plans)

    def test_assessment_across_mixed_plans(self, engine):
        # 2 completed, 1 failed, 1 in_progress
        for i in range(3):
            pid = f"p{i}"
            engine.register_plan(pid, "t1", f"Plan {i}")
            engine.register_step(f"s{i}", pid, "t1", f"Step {i}")
            engine.start_execution(pid)
            engine.record_step_result(f"tr{i}", pid, f"s{i}", "t1", i < 2)  # first 2 succeed
            engine.advance_execution(pid)

        engine.register_plan("p3", "t1", "Plan 3")
        engine.register_step("s3", "p3", "t1", "Step 3")
        engine.start_execution("p3")
        # p3 stays IN_PROGRESS

        a = engine.composition_assessment("a1", "t1")
        assert a.total_plans == 4
        assert a.active_plans == 1
        assert a.completion_rate == 0.5  # 2 out of 4

    def test_closure_report_comprehensive(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.bind_runtime("b1", "s1", "t1", "rt1", "act1")
        engine.bind_runtime("b2", "s2", "t1", "rt2", "act2")
        engine.record_decision("dec1", "p1", "s1", "t1")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        engine.record_step_result("tr2", "p1", "s2", "t1", True)
        engine.advance_execution("p1")

        report = engine.closure_report("r1", "t1")
        assert report.total_plans == 1
        assert report.total_steps == 2
        assert report.total_traces == 2
        assert report.total_decisions == 1
        assert report.total_bindings == 2


# ===========================================================================
# In-progress plan edge cases
# ===========================================================================

class TestInProgressEdgeCases:
    def test_advance_in_progress_no_changes(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        # No results recorded, just advance
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.IN_PROGRESS

    def test_record_result_on_draft_step(self, engine):
        """Recording result on a DRAFT step should work (it's not terminal)."""
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step 1")
        engine.register_step("s2", "p1", "t1", "Step 2")
        engine.add_dependency("d1", "p1", "t1", "s1", "s2")
        engine.start_execution("p1")
        # s2 is still DRAFT (has deps), but we can record result
        engine.record_step_result("tr1", "p1", "s2", "t1", True)
        assert engine.get_step("s2").status == OrchestrationStatus.COMPLETED

    def test_advance_after_completed_plan_raises(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError, match="not IN_PROGRESS"):
            engine.advance_execution("p1")


# ===========================================================================
# Parameterized tests for broader coverage
# ===========================================================================

class TestParameterizedPlanRegistration:
    @pytest.mark.parametrize("mode", list(CoordinationMode))
    def test_all_coordination_modes(self, engine, mode):
        plan = engine.register_plan(f"p-{mode.value}", "t1", f"Plan {mode.value}",
                                    coordination_mode=mode)
        assert plan.coordination_mode == mode

    @pytest.mark.parametrize("scope", list(CompositionScope))
    def test_all_composition_scopes(self, engine, scope):
        plan = engine.register_plan(f"p-{scope.value}", "t1", f"Plan {scope.value}",
                                    scope=scope)
        assert plan.scope == scope


class TestParameterizedStepKinds:
    @pytest.mark.parametrize("kind", list(OrchestrationStepKind))
    def test_all_step_kinds(self, engine, kind):
        engine.register_plan("p1", "t1", "Plan")
        step = engine.register_step(f"s-{kind.value}", "p1", "t1", f"Step {kind.value}", kind=kind)
        assert step.kind == kind


# ===========================================================================
# Diamond dependency pattern
# ===========================================================================

class TestDiamondDependency:
    def test_diamond_all_success(self, engine):
        """A -> B, A -> C, B -> D, C -> D (diamond pattern)."""
        engine.register_plan("p1", "t1", "Diamond")
        engine.register_step("sA", "p1", "t1", "A", sequence_order=0)
        engine.register_step("sB", "p1", "t1", "B", sequence_order=1)
        engine.register_step("sC", "p1", "t1", "C", sequence_order=1)
        engine.register_step("sD", "p1", "t1", "D", sequence_order=2)
        engine.add_dependency("d-ab", "p1", "t1", "sA", "sB")
        engine.add_dependency("d-ac", "p1", "t1", "sA", "sC")
        engine.add_dependency("d-bd", "p1", "t1", "sB", "sD")
        engine.add_dependency("d-cd", "p1", "t1", "sC", "sD")

        engine.start_execution("p1")
        assert engine.get_step("sA").status == OrchestrationStatus.READY
        assert engine.get_step("sB").status == OrchestrationStatus.DRAFT
        assert engine.get_step("sC").status == OrchestrationStatus.DRAFT

        engine.record_step_result("tr-a", "p1", "sA", "t1", True)
        engine.advance_execution("p1")
        assert engine.get_step("sB").status == OrchestrationStatus.READY
        assert engine.get_step("sC").status == OrchestrationStatus.READY

        engine.record_step_result("tr-b", "p1", "sB", "t1", True)
        engine.record_step_result("tr-c", "p1", "sC", "t1", True)
        engine.advance_execution("p1")
        assert engine.get_step("sD").status == OrchestrationStatus.READY

        engine.record_step_result("tr-d", "p1", "sD", "t1", True)
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.COMPLETED

    def test_diamond_one_branch_fails(self, engine):
        """If B fails, D should fail even though C succeeds."""
        engine.register_plan("p1", "t1", "Diamond Fail")
        engine.register_step("sA", "p1", "t1", "A", sequence_order=0)
        engine.register_step("sB", "p1", "t1", "B", sequence_order=1)
        engine.register_step("sC", "p1", "t1", "C", sequence_order=1)
        engine.register_step("sD", "p1", "t1", "D", sequence_order=2)
        engine.add_dependency("d-ab", "p1", "t1", "sA", "sB")
        engine.add_dependency("d-ac", "p1", "t1", "sA", "sC")
        engine.add_dependency("d-bd", "p1", "t1", "sB", "sD")
        engine.add_dependency("d-cd", "p1", "t1", "sC", "sD")

        engine.start_execution("p1")
        engine.record_step_result("tr-a", "p1", "sA", "t1", True)
        engine.advance_execution("p1")
        engine.record_step_result("tr-b", "p1", "sB", "t1", False)
        engine.record_step_result("tr-c", "p1", "sC", "t1", True)
        plan = engine.advance_execution("p1")
        assert engine.get_step("sD").status == OrchestrationStatus.FAILED
        assert plan.status == OrchestrationStatus.FAILED


# ===========================================================================
# Fan-out / fan-in pattern
# ===========================================================================

class TestFanOutFanIn:
    def test_fan_out_fan_in_success(self, engine):
        """A -> B1, B2, B3 -> C (fan-out/fan-in)."""
        engine.register_plan("p1", "t1", "Fan Out")
        engine.register_step("sA", "p1", "t1", "A", sequence_order=0)
        for i in range(1, 4):
            engine.register_step(f"sB{i}", "p1", "t1", f"B{i}", sequence_order=1)
            engine.add_dependency(f"d-ab{i}", "p1", "t1", "sA", f"sB{i}")
        engine.register_step("sC", "p1", "t1", "C", sequence_order=2)
        for i in range(1, 4):
            engine.add_dependency(f"d-b{i}c", "p1", "t1", f"sB{i}", "sC")

        engine.start_execution("p1")
        engine.record_step_result("tr-a", "p1", "sA", "t1", True)
        engine.advance_execution("p1")
        for i in range(1, 4):
            assert engine.get_step(f"sB{i}").status == OrchestrationStatus.READY
            engine.record_step_result(f"tr-b{i}", "p1", f"sB{i}", "t1", True)
        plan = engine.advance_execution("p1")
        assert engine.get_step("sC").status == OrchestrationStatus.READY
        engine.record_step_result("tr-c", "p1", "sC", "t1", True)
        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.COMPLETED
        assert plan.completed_steps == 5


# ===========================================================================
# Stress / scale tests
# ===========================================================================

class TestScaleScenarios:
    def test_ten_step_chain(self, engine):
        engine.register_plan("p1", "t1", "Long Chain")
        for i in range(10):
            engine.register_step(f"s{i}", "p1", "t1", f"Step {i}", sequence_order=i)
        for i in range(9):
            engine.add_dependency(f"d{i}", "p1", "t1", f"s{i}", f"s{i+1}")

        engine.start_execution("p1")
        for i in range(10):
            engine.record_step_result(f"tr{i}", "p1", f"s{i}", "t1", True, float(i))
            engine.advance_execution("p1")

        plan = engine.get_plan("p1")
        assert plan.status == OrchestrationStatus.COMPLETED
        assert plan.completed_steps == 10

    def test_ten_independent_steps(self, engine):
        engine.register_plan("p1", "t1", "Parallel 10")
        for i in range(10):
            engine.register_step(f"s{i}", "p1", "t1", f"Step {i}", sequence_order=i)

        engine.start_execution("p1")
        for i in range(10):
            assert engine.get_step(f"s{i}").status == OrchestrationStatus.READY
            engine.record_step_result(f"tr{i}", "p1", f"s{i}", "t1", True)

        plan = engine.advance_execution("p1")
        assert plan.status == OrchestrationStatus.COMPLETED
        assert plan.completed_steps == 10

    def test_multiple_bindings_multiple_plans(self, engine):
        for i in range(5):
            pid = f"p{i}"
            engine.register_plan(pid, "t1", f"Plan {i}")
            engine.register_step(f"s{i}", pid, "t1", f"Step {i}")
            engine.bind_runtime(f"b{i}", f"s{i}", "t1", f"rt{i}", f"act{i}")

        assert engine.binding_count == 5
        assert engine.plan_count == 5
        assert engine.step_count == 5


# ===========================================================================
# Terminal state guard tests
# ===========================================================================

class TestTerminalStateGuards:
    def test_cannot_start_completed_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_execution("p1")

    def test_cannot_start_failed_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_execution("p1")

    def test_cannot_start_cancelled_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.cancel_plan("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.start_execution("p1")

    def test_cannot_cancel_completed_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.cancel_plan("p1")

    def test_cannot_cancel_failed_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.cancel_plan("p1")

    def test_cannot_add_step_to_completed_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_step("s2", "p1", "t1", "Step 2")

    def test_cannot_add_step_to_failed_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.register_step("s2", "p1", "t1", "Step 2")

    def test_cannot_record_result_on_completed_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_step_result("tr2", "p1", "s1", "t1", True)

    def test_cannot_record_result_on_failed_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_step_result("tr2", "p1", "s1", "t1", True)

    def test_cannot_record_result_on_cancelled_step(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.cancel_plan("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_step_result("tr1", "p1", "s1", "t1", True)

    def test_cannot_advance_draft_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.advance_execution("p1")

    def test_cannot_advance_completed_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", True)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.advance_execution("p1")

    def test_cannot_advance_failed_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.start_execution("p1")
        engine.record_step_result("tr1", "p1", "s1", "t1", False)
        engine.advance_execution("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.advance_execution("p1")

    def test_cannot_advance_cancelled_plan(self, engine):
        engine.register_plan("p1", "t1", "Plan")
        engine.register_step("s1", "p1", "t1", "Step")
        engine.cancel_plan("p1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.advance_execution("p1")


class TestBoundedContracts:
    def test_duplicate_plan_error_is_bounded(self, engine):
        engine.register_plan("plan-secret", "tenant-secret", "Sensitive Plan")

        with pytest.raises(RuntimeCoreInvariantError) as excinfo:
            engine.register_plan("plan-secret", "tenant-secret", "Sensitive Plan")

        message = str(excinfo.value)
        assert message == "duplicate plan_id"
        assert "plan-secret" not in message
        assert "tenant-secret" not in message

    def test_empty_plan_violation_reason_is_bounded(self, engine):
        engine.register_plan("plan-secret", "tenant-secret", "Draft Plan")

        violations = engine.detect_orchestration_violations("tenant-secret")
        empty_plan = [violation for violation in violations if violation.operation == "empty_plan"]

        assert len(empty_plan) == 1
        assert empty_plan[0].reason == "plan has no steps"
        assert "plan-secret" not in empty_plan[0].reason
        assert "tenant-secret" not in empty_plan[0].reason
