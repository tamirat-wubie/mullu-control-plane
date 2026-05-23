"""Per-type invariant validator registry — infrastructure tests (USCL v3.3).

The registry is opt-in and default-off: an empty registry behaves exactly like
the permissive default, so wiring it into the write path is behavior-preserving
until a type is registered. These tests prove:
  (a) the registry is empty by default and dispatch is permissive when empty;
  (b) a registered validator is dispatched;
  (c) the cascade is unchanged with an empty registry;
  (d) a registered strict validator escalates and Φ_gov blocks via the A1
      fail-closed path.

No construct type is enabled in production by this change.
See docs/INVARIANT_VALIDATOR_ROLLOUT_PROPOSAL.md.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.substrate.cascade import (
    INVARIANT_VALIDATORS,
    CascadeEngine,
    DependencyGraph,
    clear_invariant_validators,
    default_invariant_checker,
    register_invariant_validator,
    registry_dispatch_checker,
    unregister_invariant_validator,
)
from mcoi_runtime.substrate.constructs import State
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    PhiGov,
    ProofState,
    ProposedDelta,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    """Keep the global registry empty around every test (isolation)."""
    clear_invariant_validators()
    yield
    clear_invariant_validators()


def _ctx() -> GovernanceContext:
    return GovernanceContext(correlation_id="cor-vr", tenant_id="t", endpoint="/x")


def _auth() -> Authority:
    return Authority(identifier="agent-vr", kind="agent")


# ---- empty by default / behavior-preserving ----


def test_registry_empty_by_default():
    assert INVARIANT_VALIDATORS == {}


def test_empty_registry_dispatch_is_permissive():
    s1 = State(configuration={"x": 1})
    s2 = State(configuration={"x": 2})
    # Empty registry => dispatch is exactly the permissive default.
    assert registry_dispatch_checker(s1, s2) is True
    assert default_invariant_checker(s1, s2) is True


def test_cascade_with_empty_registry_preserves():
    g = DependencyGraph()
    root = State(configuration={"x": 0})
    g.register(root)
    dep = State(configuration={"x": 1})
    g.register(dep, depends_on=(root.id,))
    engine = CascadeEngine(g, invariant_checker=registry_dispatch_checker)
    result = engine.cascade(root.id)
    # Empty registry => permissive => preserved, no escalation/rejection.
    assert result.preserved == 1
    assert result.escalations == 0
    assert not result.rejected


# ---- registration lifecycle + dispatch ----


def test_register_unregister_clear_lifecycle():
    s = State(configuration={})
    register_invariant_validator(s.type, lambda d, c: False)
    assert s.type in INVARIANT_VALIDATORS
    unregister_invariant_validator(s.type)
    assert s.type not in INVARIANT_VALIDATORS
    register_invariant_validator(s.type, lambda d, c: False)
    clear_invariant_validators()
    assert INVARIANT_VALIDATORS == {}


def test_registered_validator_is_dispatched():
    s1 = State(configuration={"x": 1})
    s2 = State(configuration={"x": 2})
    assert registry_dispatch_checker(s1, s2) is True  # no registration: permissive
    register_invariant_validator(s1.type, lambda d, c: False)
    assert registry_dispatch_checker(s1, s2) is False  # registered validator used


# ---- registered strict validator escalates -> Phi_gov blocks (A1 path) ----


def test_registered_validator_escalates_and_phi_gov_blocks():
    g = DependencyGraph()
    root = State(configuration={"x": 0})
    g.register(root)
    dep = State(configuration={"x": 1})
    g.register(dep, depends_on=(root.id,))
    # Invariant violated, no auto-repairer -> ESCALATED.
    register_invariant_validator(root.type, lambda d, c: False)
    engine = CascadeEngine(g, invariant_checker=registry_dispatch_checker)
    phi = PhiGov(g, cascade_engine=engine)
    delta = ProposedDelta(construct_id=root.id, operation="update")

    result = phi.evaluate((delta,), _ctx(), _auth())

    # ESCALATED -> A1 fail-closed -> FAIL with the escalation reason.
    assert result.judgment.state == ProofState.FAIL
    assert "escalated" in result.judgment.reason
