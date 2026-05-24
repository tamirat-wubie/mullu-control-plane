"""First built-in invariant validator — Change state-reference type integrity.

Validator: a ``Change``'s ``state_before`` / ``state_after`` must reference
``State`` constructs (``invariant_validators.change_state_refs_are_states``).

Proves the full detection pipeline with a REAL validator: when registered, a
``Change`` wired to a non-``State`` reference escalates and Φ_gov blocks
fail-closed (the A1 path); a correctly-wired ``Change`` passes. The validator
ships INERT (not registered in production) — these tests register it locally
and clear afterwards, so production behavior is unchanged.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.substrate.cascade import (
    CascadeEngine,
    DependencyGraph,
    clear_invariant_validators,
    register_invariant_validator,
    registry_dispatch_checker,
)
from mcoi_runtime.substrate.constructs import (
    Causation,
    Change,
    ConstructType,
    State,
)
from mcoi_runtime.substrate.invariant_validators import (
    change_state_refs_are_states,
)
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    PhiGov,
    ProofState,
    ProposedDelta,
)


@pytest.fixture(autouse=True)
def _clean_registry():
    clear_invariant_validators()
    yield
    clear_invariant_validators()


def _ctx() -> GovernanceContext:
    return GovernanceContext(correlation_id="cor-cr", tenant_id="t", endpoint="/x")


def _auth() -> Authority:
    return Authority(identifier="agent-cr", kind="agent")


# ---- predicate-level ----


def test_valid_state_reference_holds():
    s = State(configuration={})
    chg = Change(state_before_id=s.id, state_after_id=s.id, delta_vector={})
    assert change_state_refs_are_states(chg, s) is True


def test_non_state_reference_violates():
    # A Change wrongly referencing a Causation as its state_after.
    caus = Causation(mechanism="m")
    chg = Change(state_after_id=caus.id, delta_vector={})
    assert change_state_refs_are_states(chg, caus) is False


def test_unreferenced_changed_construct_is_ignored():
    s = State(configuration={})
    other = State(configuration={})  # not referenced by the change
    chg = Change(state_before_id=s.id, state_after_id=s.id, delta_vector={})
    assert change_state_refs_are_states(chg, other) is True


def test_non_change_dependent_is_total_and_permissive():
    # Defensive: called with a non-Change dependent, it stays total -> True.
    s1 = State(configuration={})
    s2 = State(configuration={})
    assert change_state_refs_are_states(s1, s2) is True


# ---- full pipeline (register -> cascade -> Phi_gov), then cleared ----


def test_corrupt_reference_escalates_and_phi_gov_blocks():
    g = DependencyGraph()
    caus = Causation(mechanism="m")
    g.register(caus)
    # Corrupt: a Change references the Causation as its state_after.
    chg = Change(state_after_id=caus.id, delta_vector={})
    g.register(chg, depends_on=(caus.id,))
    register_invariant_validator(ConstructType.CHANGE, change_state_refs_are_states)

    engine = CascadeEngine(g, invariant_checker=registry_dispatch_checker)
    phi = PhiGov(g, cascade_engine=engine)
    result = phi.evaluate(
        (ProposedDelta(construct_id=caus.id, operation="update"),), _ctx(), _auth()
    )

    assert result.judgment.state == ProofState.FAIL
    assert "escalated" in result.judgment.reason


def test_valid_reference_passes_through_gate():
    g = DependencyGraph()
    s = State(configuration={"x": 1})
    g.register(s)
    chg = Change(state_after_id=s.id, delta_vector={})
    g.register(chg, depends_on=(s.id,))
    register_invariant_validator(ConstructType.CHANGE, change_state_refs_are_states)

    engine = CascadeEngine(g, invariant_checker=registry_dispatch_checker)
    phi = PhiGov(g, cascade_engine=engine)
    result = phi.evaluate(
        (ProposedDelta(construct_id=s.id, operation="update"),), _ctx(), _auth()
    )

    assert result.judgment.state == ProofState.PASS
