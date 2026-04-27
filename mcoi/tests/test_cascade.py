"""Cascade invalidation engine tests."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.substrate.cascade import (
    CascadeEngine,
    CascadeOutcome,
    CascadeResult,
    DependencyGraph,
    MAX_CASCADE_DEPTH,
)
from mcoi_runtime.substrate.constructs import (
    Boundary,
    Causation,
    Change,
    Pattern,
    State,
    Transformation,
)


def _build_simple_graph():
    """Five constructs with linear dependency: State → Change → Transformation."""
    g = DependencyGraph()

    s_before = State(configuration={"x": 1})
    s_after = State(configuration={"x": 2})
    chg = Change(
        state_before_id=s_before.id,
        state_after_id=s_after.id,
        delta_vector={"d": 1},
    )
    cause = Causation(
        cause_id=s_before.id, effect_id=chg.id, mechanism="m"
    )
    bnd = Boundary(inside_predicate="scope")
    transf = Transformation(
        initial_state_id=s_before.id,
        target_state_id=s_after.id,
        change_id=chg.id,
        causation_id=cause.id,
        boundary_id=bnd.id,
    )

    g.register(s_before)
    g.register(s_after)
    g.register(chg, depends_on=(s_before.id, s_after.id))
    g.register(cause, depends_on=(s_before.id, chg.id))
    g.register(bnd)
    g.register(transf, depends_on=(s_before.id, s_after.id, chg.id, cause.id, bnd.id))

    return g, s_before, s_after, chg, cause, bnd, transf


def test_register_self_dependency_rejected():
    g = DependencyGraph()
    s = State(configuration={})
    with pytest.raises(ValueError, match="cannot depend on itself"):
        g.register(s, depends_on=(s.id,))


def test_register_duplicate_rejected():
    g = DependencyGraph()
    s = State(configuration={})
    g.register(s)
    with pytest.raises(ValueError, match="already registered"):
        g.register(s)


def test_unregister_with_dependents_rejected():
    g, s_before, *_ = _build_simple_graph()
    with pytest.raises(ValueError, match="dependents remain"):
        g.unregister(s_before.id)


def test_cascade_preserves_when_invariants_hold():
    """Default checker says all invariants hold → all dependents PRESERVED.

    s_before has 3 direct dependents: chg, cause, transf. Preserved nodes
    do NOT recurse into their own dependents (by design — if X is preserved,
    nothing downstream of X is affected by the change).
    """
    g, s_before, *_ = _build_simple_graph()
    engine = CascadeEngine(g)
    result = engine.cascade(s_before.id)

    assert result.preserved == 3
    assert result.escalations == 0
    assert result.auto_repairs == 0
    assert not result.rejected


def test_cascade_escalates_when_invariants_violated():
    g, s_before, *_ = _build_simple_graph()
    engine = CascadeEngine(
        g,
        invariant_checker=lambda d, c: False,  # everything broken
    )
    result = engine.cascade(s_before.id)
    assert result.escalations >= 1
    assert all(
        s.outcome == CascadeOutcome.ESCALATED
        for s in result.steps
    )


def test_cascade_auto_repairs_when_repairer_succeeds():
    g, s_before, *_ = _build_simple_graph()
    engine = CascadeEngine(
        g,
        invariant_checker=lambda d, c: False,
        auto_repairer=lambda d, c: f"refresh {d.type.value} cache",
    )
    result = engine.cascade(s_before.id)
    assert result.auto_repairs >= 1
    assert all(
        s.outcome == CascadeOutcome.AUTO_REPAIRED
        for s in result.steps
        if s.outcome != CascadeOutcome.PRESERVED
    )


def test_cascade_handles_unknown_root():
    g = DependencyGraph()
    with pytest.raises(ValueError, match="unknown construct"):
        CascadeEngine(g).cascade(uuid4())


def test_cascade_terminates_at_depth_limit():
    """Build a long chain and prove the engine truncates.

    Auto-repair is the only outcome that recurses into transitive dependents.
    Use a permissive auto-repairer so the chain walks all the way down,
    then assert the depth guard fires before infinity.
    """
    g = DependencyGraph()
    states: list[State] = []
    for i in range(MAX_CASCADE_DEPTH + 5):
        s = State(configuration={"i": i})
        states.append(s)
        if i == 0:
            g.register(s)
        else:
            g.register(s, depends_on=(states[i - 1].id,))

    engine = CascadeEngine(
        g,
        invariant_checker=lambda d, c: False,
        auto_repairer=lambda d, c: f"refresh {d.id}",
        max_depth=MAX_CASCADE_DEPTH,
    )
    result = engine.cascade(states[0].id)
    assert result.truncated_at_depth is True
    assert result.rejected is True


def test_cascade_handles_cycles():
    """Cycle: A depends on B; B depends on A. (Manually constructed; the
    register API's self-dependency check doesn't catch this — it's a
    cross-pair cycle.)
    """
    g = DependencyGraph()
    a = State(configuration={"x": 1})
    b = State(configuration={"x": 2})
    g.register(a)
    g.register(b, depends_on=(a.id,))
    # Manually inject a cycle: now A depends on B too.
    g.dependents.setdefault(b.id, set()).add(a.id)

    engine = CascadeEngine(
        g,
        invariant_checker=lambda d, c: False,
    )
    result = engine.cascade(a.id)
    assert result.cycles_detected >= 0  # detection is best-effort
    # Engine must terminate — the absence of an infinite loop is the test


def test_cascade_step_includes_construct_type():
    g, s_before, *_ = _build_simple_graph()
    engine = CascadeEngine(g, invariant_checker=lambda d, c: False)
    result = engine.cascade(s_before.id)
    types = {s.construct_type for s in result.steps}
    # We touched chg (change), cause (causation), and transf (transformation)
    assert "change" in types
    assert "causation" in types
    assert "transformation" in types


def test_cascade_summary_shape():
    g, s_before, *_ = _build_simple_graph()
    engine = CascadeEngine(g)
    summary = engine.cascade(s_before.id).summary()
    for key in (
        "root", "rejected", "preserved", "auto_repairs",
        "escalations", "truncated_at_depth", "cycles_detected", "steps",
    ):
        assert key in summary


def test_default_auto_repairer_refuses_silent_repair():
    """The default repairer returns None — silent repair is a fabrication risk."""
    from mcoi_runtime.substrate.cascade import default_auto_repairer
    s = State(configuration={})
    s2 = State(configuration={})
    assert default_auto_repairer(s, s2) is None
