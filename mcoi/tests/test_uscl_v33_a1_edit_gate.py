"""USCL v3.3 / A1 — edit-gate completeness obligation harness.

Encodes the A1 amendment obligations (docs/USCL_v3.3_AMENDMENT_CANDIDATES.md)
against the LIVE edit gate: substrate/cascade.py + substrate/phi_gov.py.

Two obligations are ALREADY MET by the current code and are LOCKED here:
  - depth-bounded propagation FAILS CLOSED: a cascade exceeding
    MAX_CASCADE_DEPTH rejects the delta and records the cutoff in the
    judgment; it does NOT silently treat the unresolved tail as no-fracture.

Two obligations are NOT YET MET and are encoded as `xfail(strict=True)` so the
harness documents exactly what "A1 done" requires WITHOUT changing kernel
semantics on the way in. When the kernel is hardened these will xpass and
strict-fail, forcing the xfail marker to be removed and the assertion kept:
  - escalations must BLOCK (no fail-open): PhiGov.evaluate inspects only
    cascade.rejected and ignores cascade.escalations, so an unrepaired
    invariant violation (ESCALATED) passes the gate. Latent today because the
    default invariant checker is permissive; real per-type checkers expose it.
  - escalate-then-fail-closed (no self-DoS): a chain deeper than the default
    budget should escalate to a finite B_ceiling before rejecting, not
    flat-reject on the first budget breach.
"""
from __future__ import annotations

import pytest

from mcoi_runtime.substrate.cascade import (
    MAX_CASCADE_DEPTH,
    CascadeEngine,
    DependencyGraph,
)
from mcoi_runtime.substrate.constructs import State
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    PhiGov,
    ProofState,
    ProposedDelta,
)


def _ctx() -> GovernanceContext:
    return GovernanceContext(correlation_id="cor-a1", tenant_id="t", endpoint="/x")


def _auth() -> Authority:
    return Authority(identifier="agent-a1", kind="agent")


def _chain(graph: DependencyGraph, length: int) -> State:
    """Register a root plus `length` dependents in a straight chain, each
    depending on the previous. cascade(root.id) descends one level per
    AUTO_REPAIR, so a checker that violates + a repairer that succeeds drives
    the walk to arbitrary depth."""
    root = State(configuration={"n": 0})
    graph.register(root)
    prev = root
    for i in range(1, length + 1):
        node = State(configuration={"n": i})
        graph.register(node, depends_on=(prev.id,))
        prev = node
    return root


# --------------------------------------------------------------------------
# MET obligation: depth-bounded propagation fails CLOSED (locked)
# --------------------------------------------------------------------------


def test_a1_depth_exhaustion_fails_closed():
    """A propagation chain deeper than MAX_CASCADE_DEPTH must REJECT the delta
    and surface the cutoff — never silently pass."""
    g = DependencyGraph()
    root = _chain(g, MAX_CASCADE_DEPTH + 4)
    engine = CascadeEngine(
        g,
        invariant_checker=lambda dep, ch: False,      # invariant violated
        auto_repairer=lambda dep, ch: "auto-repaired",  # repair => recurse deeper
        max_depth=MAX_CASCADE_DEPTH,
    )
    phi = PhiGov(g, cascade_engine=engine)
    delta = ProposedDelta(construct_id=root.id, operation="update")

    result = phi.evaluate((delta,), _ctx(), _auth())

    assert result.judgment.state == ProofState.FAIL
    assert len(result.rejected_deltas) == 1
    summary = result.judgment.cascade_summaries[0]
    assert summary["truncated_at_depth"] is True
    assert summary["rejected"] is True


def test_a1_within_budget_is_admitted():
    """A chain that stays within budget is not depth-rejected — guards against a
    regression that over-rejects valid edits."""
    g = DependencyGraph()
    root = _chain(g, 3)
    engine = CascadeEngine(
        g,
        invariant_checker=lambda dep, ch: False,
        auto_repairer=lambda dep, ch: "auto-repaired",
        max_depth=MAX_CASCADE_DEPTH,
    )
    phi = PhiGov(g, cascade_engine=engine)
    delta = ProposedDelta(construct_id=root.id, operation="update")

    result = phi.evaluate((delta,), _ctx(), _auth())

    assert result.judgment.state == ProofState.PASS
    assert result.judgment.cascade_summaries[0]["truncated_at_depth"] is False


# --------------------------------------------------------------------------
# UNMET obligations: encoded as strict xfail (no kernel-semantics change here)
# --------------------------------------------------------------------------


@pytest.mark.xfail(
    reason="A1: an unresolved invariant violation (ESCALATED) must BLOCK the "
    "edit. PhiGov.evaluate currently checks only cascade.rejected and ignores "
    "cascade.escalations -> latent fail-open.",
    strict=True,
)
def test_a1_escalation_must_block():
    """One dependent whose invariant is violated with NO auto-repair => ESCALATED.
    A1 requires the edit to be blocked; today it is approved."""
    g = DependencyGraph()
    root = State(configuration={"n": 0})
    g.register(root)
    dep = State(configuration={"n": 1})
    g.register(dep, depends_on=(root.id,))
    engine = CascadeEngine(
        g,
        invariant_checker=lambda d, ch: False,  # invariant violated
        auto_repairer=lambda d, ch: None,       # no repair => escalate
        max_depth=MAX_CASCADE_DEPTH,
    )
    phi = PhiGov(g, cascade_engine=engine)
    delta = ProposedDelta(construct_id=root.id, operation="update")

    result = phi.evaluate((delta,), _ctx(), _auth())

    assert result.judgment.state == ProofState.FAIL


@pytest.mark.xfail(
    reason="A1: depth exhaustion should ESCALATE to a finite B_ceiling before "
    "rejecting (no self-DoS). No escalation ladder exists, so a deep chain is "
    "flat-rejected on the first budget breach.",
    strict=True,
)
def test_a1_escalates_before_rejecting():
    """A1: a valid-but-deep chain should be admitted via escalation (or routed to
    authority) rather than flat-rejected at the first budget breach."""
    g = DependencyGraph()
    root = _chain(g, MAX_CASCADE_DEPTH + 2)
    engine = CascadeEngine(
        g,
        invariant_checker=lambda dep, ch: False,
        auto_repairer=lambda dep, ch: "auto-repaired",
        max_depth=MAX_CASCADE_DEPTH,
    )
    phi = PhiGov(g, cascade_engine=engine)
    delta = ProposedDelta(construct_id=root.id, operation="update")

    result = phi.evaluate((delta,), _ctx(), _auth())

    assert result.judgment.cascade_summaries[0]["truncated_at_depth"] is False
