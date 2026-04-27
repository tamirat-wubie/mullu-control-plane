"""Φ_gov call contract tests."""
from __future__ import annotations

from uuid import uuid4

import pytest

from mcoi_runtime.substrate.cascade import DependencyGraph
from mcoi_runtime.substrate.constructs import State
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    Judgment,
    PhiAgentFilter,
    PhiAgentLevel,
    PhiGov,
    ProofState,
    ProposedDelta,
)


def _ctx() -> GovernanceContext:
    return GovernanceContext(
        correlation_id="cor-test",
        tenant_id="tenant-1",
        endpoint="/x",
    )


def _auth() -> Authority:
    return Authority(identifier="agent-test", kind="agent")


# ---- ProposedDelta ----


def test_proposed_delta_validates_operation():
    with pytest.raises(ValueError):
        ProposedDelta(construct_id=uuid4(), operation="invent")


def test_proposed_delta_valid_operations():
    for op in ("create", "update", "delete"):
        d = ProposedDelta(construct_id=uuid4(), operation=op)
        assert d.operation == op


# ---- Authority ----


def test_authority_requires_identifier():
    with pytest.raises(ValueError):
        Authority(identifier="")


def test_authority_invalid_kind():
    with pytest.raises(ValueError):
        Authority(identifier="x", kind="god")


# ---- Judgment ----


def test_judgment_fail_requires_reason():
    with pytest.raises(ValueError, match="reason"):
        Judgment(state=ProofState.FAIL, reason="")


def test_judgment_pass_no_reason_required():
    j = Judgment(state=ProofState.PASS)
    assert j.state == ProofState.PASS


# ---- PhiAgentFilter ----


def test_phi_agent_default_passes_all_levels():
    f = PhiAgentFilter()
    delta = ProposedDelta(construct_id=uuid4(), operation="create")
    passed, level = f.evaluate(delta, _ctx(), _auth())
    assert passed is True
    assert level == PhiAgentLevel.L5_OPTIMIZATION


def test_phi_agent_blocks_at_specific_level():
    """L2 (Survival) blocks; we should see L2 returned."""
    f = PhiAgentFilter(
        l2=lambda d, c, a: False,
    )
    delta = ProposedDelta(construct_id=uuid4(), operation="create")
    passed, level = f.evaluate(delta, _ctx(), _auth())
    assert passed is False
    assert level == PhiAgentLevel.L2_SURVIVAL


def test_phi_agent_l0_blocks_short_circuits():
    f = PhiAgentFilter(l0=lambda d, c, a: False)
    delta = ProposedDelta(construct_id=uuid4(), operation="create")
    passed, level = f.evaluate(delta, _ctx(), _auth())
    assert passed is False
    assert level == PhiAgentLevel.L0_PHYSICAL_LOGICAL


# ---- PhiGov ----


def test_phi_gov_empty_batch_passes():
    g = DependencyGraph()
    phi = PhiGov(g)
    result = phi.evaluate((), _ctx(), _auth())
    assert result.judgment.state == ProofState.PASS
    assert result.rejected_deltas == ()


def test_phi_gov_approves_when_all_filters_pass():
    g = DependencyGraph()
    s = State(configuration={"x": 1})
    g.register(s)
    delta = ProposedDelta(construct_id=s.id, operation="update")
    phi = PhiGov(g)
    result = phi.evaluate((delta,), _ctx(), _auth())
    assert result.judgment.state == ProofState.PASS
    assert result.rejected_deltas == ()


def test_phi_gov_rejects_when_phi_agent_blocks():
    g = DependencyGraph()
    s = State(configuration={"x": 1})
    g.register(s)
    delta = ProposedDelta(construct_id=s.id, operation="update")
    phi = PhiGov(
        g,
        phi_agent=PhiAgentFilter(l3=lambda d, c, a: False),
    )
    result = phi.evaluate((delta,), _ctx(), _auth())
    assert result.judgment.state == ProofState.FAIL
    assert len(result.rejected_deltas) == 1
    assert result.judgment.phi_agent_level_passed == PhiAgentLevel.L3_NORMATIVE


def test_phi_gov_rejects_when_external_validator_blocks():
    g = DependencyGraph()
    s = State(configuration={"x": 1})
    g.register(s)
    delta = ProposedDelta(construct_id=s.id, operation="update")

    def deny(delta, ctx, auth):
        return (False, "policy_violation")

    phi = PhiGov(g, external_validators=(deny,))
    result = phi.evaluate((delta,), _ctx(), _auth())
    assert result.judgment.state == ProofState.FAIL
    # v4.15.0 contract: the specific validator reason surfaces in the
    # judgment, so callers can attribute the denial without parsing
    # rejected_deltas.
    assert "policy_violation" in result.judgment.reason


def test_phi_gov_partial_rejection():
    """Half of deltas rejected → judgment is FAIL with mixed counts."""
    g = DependencyGraph()
    s1 = State(configuration={"x": 1})
    s2 = State(configuration={"x": 2})
    g.register(s1)
    g.register(s2)

    d_ok = ProposedDelta(construct_id=s1.id, operation="update")
    d_block = ProposedDelta(construct_id=s2.id, operation="update")

    blocked_ids = {s2.id}
    phi = PhiGov(
        g,
        phi_agent=PhiAgentFilter(
            l3=lambda d, c, a: d.construct_id not in blocked_ids
        ),
    )
    result = phi.evaluate((d_ok, d_block), _ctx(), _auth())
    assert result.judgment.state == ProofState.FAIL
    assert len(result.rejected_deltas) == 1
    assert result.rejected_deltas[0].construct_id == s2.id


def test_phi_gov_judgment_records_cascade():
    g = DependencyGraph()
    s = State(configuration={"x": 1})
    g.register(s)
    delta = ProposedDelta(construct_id=s.id, operation="update")
    phi = PhiGov(g)
    result = phi.evaluate((delta,), _ctx(), _auth())
    # Even with no dependents, a cascade summary must be recorded
    assert len(result.judgment.cascade_summaries) == 1
    assert "root" in result.judgment.cascade_summaries[0]


def test_phi_gov_rejection_records_deltas_in_judgment():
    g = DependencyGraph()
    s = State(configuration={"x": 1})
    g.register(s)
    delta = ProposedDelta(construct_id=s.id, operation="update")
    phi = PhiGov(
        g,
        phi_agent=PhiAgentFilter(l1=lambda d, c, a: False),
    )
    result = phi.evaluate((delta,), _ctx(), _auth())
    # Δ_reject must be in judgment, not just in result.rejected_deltas
    assert len(result.judgment.rejected_deltas) == 1
    assert result.judgment.rejected_deltas[0] == delta
