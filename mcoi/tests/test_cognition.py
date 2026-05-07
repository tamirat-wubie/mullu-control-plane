"""SCCCE cognitive cycle — symbol field, tension, convergence, full cycle."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.cognition import (
    ConvergenceDetector,
    ConvergenceReason,
    CycleStep,
    SCCCECycle,
    SymbolField,
    TensionCalculator,
    TensionWeights,
)
from mcoi_runtime.substrate.constructs import (
    Boundary,
    Causation,
    Change,
    Constraint,
    ConstructType,
    Execution,
    Pattern,
    State,
    Tier,
    Transformation,
    Validation,
)


# ---- SymbolField ----


def test_symbol_field_register_and_index():
    f = SymbolField()
    s = State(configuration={"x": 1})
    f.register(s)
    assert f.size == 1
    assert s in f.of_tier(Tier.FOUNDATIONAL)
    assert s in f.of_type(ConstructType.STATE)


def test_symbol_field_unregister_clears_indices():
    f = SymbolField()
    s = State(configuration={"x": 1})
    f.register(s)
    f.unregister(s.id)
    assert f.size == 0
    assert s not in f.of_tier(Tier.FOUNDATIONAL)
    assert s not in f.of_type(ConstructType.STATE)


def test_symbol_field_type_counts_for_adapter():
    f = SymbolField()
    f.register(State(configuration={}))
    f.register(State(configuration={}))
    f.register(Pattern(template_state_id=uuid4()))
    counts = f.type_counts()
    assert counts.get("state") == 2
    assert counts.get("pattern") == 1


def test_symbol_field_tier_sizes():
    f = SymbolField()
    f.register(State(configuration={}))
    f.register(Pattern(template_state_id=uuid4()))
    sizes = f.tier_sizes()
    assert sizes[Tier.FOUNDATIONAL] == 1
    assert sizes[Tier.STRUCTURAL] == 1


# ---- TensionCalculator ----


def test_tension_zero_on_empty_field():
    f = SymbolField()
    calc = TensionCalculator()
    snap = calc.compute(f)
    assert snap.total == 0.0
    assert snap.foundational == 0.0
    assert snap.cognitive == 0.0


def test_tension_dangling_causation_increments_foundational():
    f = SymbolField()
    # Causation referencing IDs that aren't in the field
    cause = Causation(
        cause_id=uuid4(),
        effect_id=uuid4(),
        mechanism="m",
    )
    f.register(cause)
    snap = TensionCalculator().compute(f)
    assert snap.foundational == 2.0  # both cause_id and effect_id dangle


def test_tension_pending_validation_increments_governance():
    f = SymbolField()
    f.register(
        Validation(
            target_pattern_id=uuid4(),
            criteria=("c1",),
            decision="unknown",
        )
    )
    snap = TensionCalculator().compute(f)
    assert snap.governance == 1.0


def test_tension_pending_execution_increments_cognitive():
    f = SymbolField()
    f.register(
        Execution(
            plan_description="p",
            decision_id=uuid4(),
            completion_state="pending",
        )
    )
    snap = TensionCalculator().compute(f)
    assert snap.cognitive == 1.0


def test_tension_weights_apply_correctly():
    f = SymbolField()
    f.register(
        Validation(
            target_pattern_id=uuid4(),
            criteria=("c",),
            decision="unknown",
        )
    )
    calc = TensionCalculator(
        weights=TensionWeights(governance=2.5),
    )
    snap = calc.compute(f)
    assert snap.governance == 1.0
    assert snap.total == 2.5


def test_tension_weight_negative_rejected():
    with pytest.raises(ValueError):
        TensionWeights(governance=-1.0)


# ---- ConvergenceDetector ----


def test_convergence_zero_tension_terminates_immediately():
    det = ConvergenceDetector()
    from mcoi_runtime.cognition.tension import TensionSnapshot
    snap = TensionSnapshot(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    state = det.evaluate(snap)
    assert state.converged
    assert state.reason == ConvergenceReason.ZERO_TENSION


def test_convergence_stable_after_n_iterations():
    det = ConvergenceDetector(stable_iterations=3, epsilon=0.01)
    from mcoi_runtime.cognition.tension import TensionSnapshot
    state = None
    # Walk: 5.0, 3.0, 3.0, 3.0, 3.0 — stable for last 3 deltas
    for total in (5.0, 3.0, 3.0, 3.0, 3.0):
        snap = TensionSnapshot(0, 0, 0, 0, 0, total)
        state = det.evaluate(snap, state)
    assert state is not None
    assert state.converged
    assert state.reason == ConvergenceReason.STABLE


def test_convergence_max_iterations_exhausted():
    det = ConvergenceDetector(max_iterations=3, stable_iterations=10)
    from mcoi_runtime.cognition.tension import TensionSnapshot
    state = None
    for i in range(5):
        snap = TensionSnapshot(0, 0, 0, 0, 0, float(i + 5))  # always changing
        state = det.evaluate(snap, state)
        if state.converged:
            break
    assert state is not None
    assert state.converged
    assert state.reason == ConvergenceReason.MAX_ITERATIONS


def test_convergence_invalid_params_rejected():
    with pytest.raises(ValueError):
        ConvergenceDetector(epsilon=-1)
    with pytest.raises(ValueError):
        ConvergenceDetector(max_iterations=0)


# ---- SCCCECycle ----


def test_cycle_runs_with_default_no_op_steps():
    """Empty field, default no-op steps → converges immediately on zero tension."""
    cycle = SCCCECycle()
    field = SymbolField()
    result = cycle.run(field)
    assert result.converged
    assert result.reason == ConvergenceReason.ZERO_TENSION
    # 15 steps still execute even on zero-tension start
    assert len(result.step_records) == 15


def test_cycle_produces_15_step_records_per_iteration():
    cycle = SCCCECycle()
    field = SymbolField()

    # Force at least one iteration by injecting non-zero tension that doesn't resolve
    pending = Validation(
        target_pattern_id=uuid4(),
        criteria=("c",),
        decision="unknown",
    )
    field.register(pending)

    # Cap iterations short to keep the test bounded
    cycle.convergence = ConvergenceDetector(max_iterations=2, stable_iterations=10)
    result = cycle.run(field)

    assert result.iterations == 2
    # Each iteration runs 15 steps
    assert len(result.step_records) == 15 * 2
    iterations = {r.iteration for r in result.step_records}
    assert iterations == {1, 2}


def test_cycle_converges_when_step_resolves_tension():
    """A step that resolves tension causes the cycle to converge."""
    field = SymbolField()
    pending = Validation(
        target_pattern_id=uuid4(),
        criteria=("c",),
        evidence_refs=("e",),
        decision="unknown",
    )
    field.register(pending)

    def resolve_in_validation_step(f: SymbolField, ctx: dict) -> bool:
        # Replace the unknown validation with a passing one
        for v in list(f.of_type(ConstructType.VALIDATION)):
            if v.decision == "unknown":
                f.unregister(v.id)
                f.register(
                    Validation(
                        target_pattern_id=v.target_pattern_id,
                        criteria=v.criteria,
                        evidence_refs=("e",),
                        decision="pass",
                    )
                )
        return True

    cycle = SCCCECycle(step_quality_monitoring=resolve_in_validation_step)
    result = cycle.run(field)
    assert result.converged
    assert result.reason == ConvergenceReason.ZERO_TENSION


def test_cycle_aborts_on_step_failure():
    """A step returning False aborts the cycle at that step."""

    def failing_step(f: SymbolField, ctx: dict) -> bool:
        return False

    cycle = SCCCECycle(step_goal_activation=failing_step)
    result = cycle.run(SymbolField())
    assert result.aborted_at_step == CycleStep.GOAL_ACTIVATION
    assert result.to_universal_result_kwargs()["proof_state"] == "Fail"


def test_cycle_max_iterations_yields_budget_unknown():
    field = SymbolField()
    # Permanent pending validation — tension never decreases
    field.register(
        Validation(
            target_pattern_id=uuid4(),
            criteria=("c",),
            decision="unknown",
        )
    )
    cycle = SCCCECycle(
        convergence=ConvergenceDetector(max_iterations=3, stable_iterations=100),
    )
    result = cycle.run(field)
    assert result.converged
    assert result.reason == ConvergenceReason.MAX_ITERATIONS
    assert result.to_universal_result_kwargs()["proof_state"] == "BudgetUnknown"


def test_cycle_universal_result_kwargs_match_adapter_shape():
    cycle = SCCCECycle()
    field = SymbolField()
    field.register(State(configuration={}))
    field.register(
        Transformation(
            initial_state_id=uuid4(),
            target_state_id=uuid4(),
            change_id=uuid4(),
            causation_id=uuid4(),
            boundary_id=uuid4(),
        )
    )
    result = cycle.run(field)
    kwargs = result.to_universal_result_kwargs()
    assert "construct_graph_summary" in kwargs
    assert "cognitive_cycles_run" in kwargs
    assert "converged" in kwargs
    assert "proof_state" in kwargs
    # The transformation Tier 2 stub the software_dev adapter checks for
    summary = kwargs["construct_graph_summary"]
    assert summary.get("transformation", 0) >= 1
