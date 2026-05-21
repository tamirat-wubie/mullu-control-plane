"""Tests for the operational mathematics autonomous loop."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.operational_math import (
    OperationalMathControl,
    OperationalMathLoopStatus,
    OperationalMathPrinciple,
    OperationalMathPriority,
    OperationalMathRole,
    OperationalMathTarget,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.operational_math_loop import (
    OperationalMathLoopEngine,
    default_operational_math_principles,
)

EXPECTED_PRIORITY_ORDER = ("F1", "F2", "F3", "F5", "F9", "F4", "F8", "F10", "F6", "F7")
FIXED_TS = "2026-05-18T12:00:00+00:00"


def _ts() -> str:
    return FIXED_TS


def test_operational_math_loop_applies_all_audit_principles() -> None:
    event_spine = EventSpineEngine()
    engine = OperationalMathLoopEngine(event_spine=event_spine, clock=_ts)
    target = OperationalMathTarget(
        target_id="math-core",
        title="Teach Mullu Core Math Principles",
        problem_class="operational mathematical cognition",
        max_iterations=16,
        created_at=_ts(),
    )

    result = engine.apply_all(target)

    assert result.status is OperationalMathLoopStatus.SATURATED
    assert result.solver_outcome == "SolvedVerified"
    assert result.unresolved_principle_ids == ()
    assert result.applied_principle_ids == EXPECTED_PRIORITY_ORDER
    assert OperationalMathRole.COMPLEXITY_BOUND in result.final_roles
    assert OperationalMathRole.RESOURCE_BOUND in result.final_roles
    assert OperationalMathRole.DECISION_RULE in result.final_roles
    assert OperationalMathRole.ADVERSARIAL_GUARD in result.final_roles
    assert OperationalMathControl.EXECUTABLE_SOLVER in result.final_controls
    assert OperationalMathControl.NUMERICAL_STABILITY_BOUND in result.final_controls
    assert result.started_at == FIXED_TS
    assert result.completed_at == FIXED_TS
    assert event_spine.event_count == len(result.iterations) + 1
    assert all(event.emitted_at == FIXED_TS for event in event_spine.list_events())


def test_operational_math_loop_stops_at_iteration_budget_with_open_gaps() -> None:
    engine = OperationalMathLoopEngine()
    target = OperationalMathTarget(
        target_id="bounded-math-core",
        title="Bounded Math Core",
        problem_class="resource bounded operational math",
        max_iterations=2,
        created_at=_ts(),
    )

    result = engine.apply_all(target)

    assert result.status is OperationalMathLoopStatus.MAX_ITERATIONS_REACHED
    assert result.solver_outcome == "AwaitingEvidence"
    assert len(result.iterations) == 2
    assert result.unresolved_principle_ids
    assert result.iterations[0].tension_after < result.iterations[0].tension_before
    assert result.iterations[1].tension_after < result.iterations[1].tension_before
    assert result.applied_principle_ids == ("F1", "F2")


def test_operational_math_loop_accepts_existing_roles_and_only_adds_missing_controls() -> None:
    engine = OperationalMathLoopEngine()
    target = OperationalMathTarget(
        target_id="partial-math-core",
        title="Partial Math Core",
        problem_class="existing symbolic structure",
        current_roles=(
            OperationalMathRole.CONSTRAINT,
            OperationalMathRole.TRANSFORMATION,
            OperationalMathRole.INVARIANT,
        ),
        current_controls=(),
        max_iterations=1,
        created_at=_ts(),
    )

    result = engine.apply_all(target)

    assert result.status is OperationalMathLoopStatus.MAX_ITERATIONS_REACHED
    assert result.applied_principle_ids == ("F1",)
    assert result.iterations[0].added_roles == ()
    assert result.iterations[0].added_controls == (OperationalMathControl.PROOF_RECEIPT,)
    assert OperationalMathRole.CONSTRAINT in result.final_roles
    assert OperationalMathControl.PROOF_RECEIPT in result.final_controls


def test_operational_math_contracts_reject_non_executable_principles() -> None:
    with pytest.raises(ValueError):
        OperationalMathPrinciple(
            principle_id="bad",
            priority=OperationalMathPriority.P0,
            title="decorative math",
            math_area="notation only",
            operational_definition="no executable surface",
            required_roles=(),
            required_controls=(OperationalMathControl.PROOF_RECEIPT,),
            failure_prevented="none",
            evidence_refs=("test",),
        )

    with pytest.raises(ValueError):
        OperationalMathTarget(
            target_id="bad-target",
            title="Bad Target",
            problem_class="invalid loop ceiling",
            max_iterations=0,
            created_at=_ts(),
        )


def test_default_operational_math_catalog_is_deterministic_and_complete() -> None:
    first_catalog = default_operational_math_principles()
    second_catalog = default_operational_math_principles()
    engine = OperationalMathLoopEngine(clock=_ts)

    assert first_catalog == second_catalog
    assert tuple(principle.principle_id for principle in first_catalog) == EXPECTED_PRIORITY_ORDER
    assert all(principle.required_roles for principle in first_catalog)
    assert all(principle.required_controls for principle in first_catalog)
    assert first_catalog[0].priority is OperationalMathPriority.P0
    assert engine.state_hash() == OperationalMathLoopEngine(clock=_ts).state_hash()
    assert len(engine.state_hash()) == 64
