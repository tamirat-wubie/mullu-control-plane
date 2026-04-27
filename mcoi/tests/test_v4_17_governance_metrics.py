"""v4.17.0 — governance chain observability.

The v4.15 bridge gates writes; v4.16 gates domain runs. v4.17 makes the
chain visible: per-(surface, verdict) totals, per-(surface, tenant)
totals, per-blocking-guard denial counts, and a forensic ring buffer of
recent rejections. Exposed via ``/musia/governance/stats`` (admin scope).

These tests cover the registry contract directly, then the call-site
wiring (chain_to_validator and gate_domain_run both record), then the
HTTP surface.
"""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.domains import router as domains_router
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.musia_governance_bridge import (
    chain_to_validator,
    configure_musia_governance_chain,
    gate_domain_run,
)
from mcoi_runtime.app.routers.musia_governance_metrics import (
    REGISTRY as METRICS,
    SURFACE_DOMAIN_RUN,
    SURFACE_WRITE,
    VERDICT_ALLOWED,
    VERDICT_DENIED,
    VERDICT_EXCEPTION,
    MAX_RECENT_REJECTIONS,
    RejectionEvent,
    router as metrics_router,
)
from mcoi_runtime.core.governance_guard import (
    GovernanceGuard,
    GovernanceGuardChain,
    GuardResult,
)
from mcoi_runtime.substrate.phi_gov import (
    Authority,
    GovernanceContext,
    ProposedDelta,
)
from uuid import uuid4


# ============================================================
# Registry contract
# ============================================================


@pytest.fixture(autouse=True)
def _reset_metrics():
    METRICS.reset()
    yield
    METRICS.reset()


def test_empty_snapshot_has_zero_totals():
    snap = METRICS.snapshot()
    assert snap.total_runs() == 0
    assert snap.total_denials() == 0
    assert snap.runs_by_surface_verdict == {}
    assert snap.runs_by_surface_tenant == {}
    assert snap.denials_by_guard == {}
    assert snap.recent_rejections == ()


def test_record_allowed_increments_only_runs_counters():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme", allowed=True,
    )
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_verdict == {(SURFACE_WRITE, VERDICT_ALLOWED): 1}
    assert snap.runs_by_surface_tenant == {(SURFACE_WRITE, "acme"): 1}
    assert snap.denials_by_guard == {}
    assert snap.recent_rejections == ()
    assert snap.total_denials() == 0


def test_record_denied_increments_runs_and_guard_counters():
    METRICS.record(
        surface=SURFACE_WRITE,
        tenant_id="acme",
        allowed=False,
        blocking_guard="rate_limit",
        reason="rate limited",
    )
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_verdict == {(SURFACE_WRITE, VERDICT_DENIED): 1}
    assert snap.denials_by_guard == {"rate_limit": 1}
    assert len(snap.recent_rejections) == 1
    ev = snap.recent_rejections[0]
    assert ev.surface == SURFACE_WRITE
    assert ev.tenant_id == "acme"
    assert ev.blocking_guard == "rate_limit"
    assert ev.reason == "rate limited"


def test_record_denied_with_no_guard_name_uses_unknown():
    METRICS.record(
        surface=SURFACE_DOMAIN_RUN,
        tenant_id="acme",
        allowed=False,
        blocking_guard=None,
    )
    snap = METRICS.snapshot()
    assert snap.denials_by_guard == {"unknown": 1}


def test_record_exception_uses_exception_verdict():
    METRICS.record(
        surface=SURFACE_WRITE,
        tenant_id="acme",
        allowed=False,
        blocking_guard="RuntimeError",
        reason="chain_exception:RuntimeError",
        exception=True,
    )
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_verdict == {(SURFACE_WRITE, VERDICT_EXCEPTION): 1}
    # Exceptions surface in the rejection ring for forensic spotting
    assert len(snap.recent_rejections) == 1
    assert snap.recent_rejections[0].blocking_guard == "RuntimeError"
    # But are NOT counted under denials_by_guard (which is denial-only —
    # an exception-counting guard would distort the "this guard denied
    # most" view operators rely on for chain tuning)
    assert snap.denials_by_guard == {}


def test_record_invalid_surface_raises():
    with pytest.raises(ValueError, match="surface"):
        METRICS.record(surface="invalid", tenant_id="x", allowed=True)


def test_multiple_records_accumulate():
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="rate_limit", reason="x",
    )
    METRICS.record(
        surface=SURFACE_DOMAIN_RUN, tenant_id="bigco",
        allowed=False, blocking_guard="budget", reason="y",
    )
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_verdict == {
        (SURFACE_WRITE, VERDICT_ALLOWED): 2,
        (SURFACE_WRITE, VERDICT_DENIED): 1,
        (SURFACE_DOMAIN_RUN, VERDICT_DENIED): 1,
    }
    assert snap.runs_by_surface_tenant == {
        (SURFACE_WRITE, "acme"): 3,
        (SURFACE_DOMAIN_RUN, "bigco"): 1,
    }
    assert snap.denials_by_guard == {"rate_limit": 1, "budget": 1}
    assert snap.total_runs() == 4
    assert snap.total_denials() == 2


def test_recent_rejections_capped_at_max():
    """Ring buffer is hard-capped — denial-storms cannot OOM."""
    for i in range(MAX_RECENT_REJECTIONS + 10):
        METRICS.record(
            surface=SURFACE_WRITE,
            tenant_id=f"t-{i}",
            allowed=False,
            blocking_guard=f"g-{i}",
            reason=f"r-{i}",
        )
    snap = METRICS.snapshot()
    assert len(snap.recent_rejections) == MAX_RECENT_REJECTIONS
    # Oldest were evicted; newest remain. Ring is FIFO.
    last = snap.recent_rejections[-1]
    assert last.tenant_id == f"t-{MAX_RECENT_REJECTIONS + 9}"


def test_recent_rejections_preserve_chronology():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="a", allowed=False,
        blocking_guard="g1", now=1000.0,
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="b", allowed=False,
        blocking_guard="g2", now=2000.0,
    )
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="c", allowed=False,
        blocking_guard="g3", now=3000.0,
    )
    snap = METRICS.snapshot()
    # Oldest first
    assert [ev.timestamp for ev in snap.recent_rejections] == [1000.0, 2000.0, 3000.0]


def test_reset_clears_everything():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="g",
    )
    METRICS.reset()
    snap = METRICS.snapshot()
    assert snap.total_runs() == 0
    assert snap.recent_rejections == ()


def test_snapshot_is_immutable():
    """Mutating the snapshot's dicts must not affect future snapshots."""
    METRICS.record(surface=SURFACE_WRITE, tenant_id="acme", allowed=True)
    snap = METRICS.snapshot()
    snap.runs_by_surface_verdict[(SURFACE_WRITE, "fake_verdict")] = 999
    snap.denials_by_guard["fake_guard"] = 999
    fresh = METRICS.snapshot()
    assert (SURFACE_WRITE, "fake_verdict") not in fresh.runs_by_surface_verdict
    assert "fake_guard" not in fresh.denials_by_guard


def test_as_dict_flattens_tuple_keys():
    METRICS.record(
        surface=SURFACE_WRITE, tenant_id="acme",
        allowed=False, blocking_guard="rl", reason="r",
    )
    METRICS.record(surface=SURFACE_DOMAIN_RUN, tenant_id="acme", allowed=True)
    body = METRICS.snapshot().as_dict()
    # Keys are colon-flattened strings (JSON-friendly)
    assert f"{SURFACE_WRITE}:{VERDICT_DENIED}" in body["runs_by_surface_verdict"]
    assert f"{SURFACE_WRITE}:acme" in body["runs_by_surface_tenant"]
    assert body["total_runs"] == 2
    assert body["total_denials"] == 1
    assert len(body["recent_rejections"]) == 1


# ============================================================
# Bridge wiring — chain_to_validator records on every invocation
# ============================================================


def _delta() -> ProposedDelta:
    return ProposedDelta(
        construct_id=uuid4(),
        operation="create",
        payload={"type": "state", "tier": 1},
    )


def _ctx(tenant_id: str = "acme") -> GovernanceContext:
    return GovernanceContext(correlation_id="cid", tenant_id=tenant_id)


def _auth() -> Authority:
    return Authority(identifier="a", kind="agent")


def test_chain_to_validator_records_allow():
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok")))
    validator = chain_to_validator(chain)
    validator(_delta(), _ctx("acme"), _auth())
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_verdict[(SURFACE_WRITE, VERDICT_ALLOWED)] == 1
    assert snap.runs_by_surface_tenant[(SURFACE_WRITE, "acme")] == 1


def test_chain_to_validator_records_deny_with_guard_name():
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "rate_limit",
            lambda c: GuardResult(
                allowed=False, guard_name="rate_limit", reason="slow down",
            ),
        )
    )
    validator = chain_to_validator(chain)
    validator(_delta(), _ctx("acme"), _auth())
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_verdict[(SURFACE_WRITE, VERDICT_DENIED)] == 1
    assert snap.denials_by_guard == {"rate_limit": 1}
    assert snap.recent_rejections[0].reason == "slow down"


def test_chain_to_validator_records_exception_as_exception_verdict():
    """A guard that raises something GovernanceGuard's defensive wrapper
    doesn't catch trips the bridge's outer except — that path goes via
    the exception verdict, not the denial verdict."""

    class BadChain:
        guards = []  # type: ignore[var-annotated]

        def evaluate(self, ctx):
            raise RuntimeError("kaboom")

    validator = chain_to_validator(BadChain())  # type: ignore[arg-type]
    ok, reason = validator(_delta(), _ctx("acme"), _auth())
    assert ok is False
    snap = METRICS.snapshot()
    assert snap.runs_by_surface_verdict[(SURFACE_WRITE, VERDICT_EXCEPTION)] == 1
    # Exception is in the rejection ring (forensic visibility),
    # but NOT in denials_by_guard (denial-only)
    assert snap.denials_by_guard == {}
    assert len(snap.recent_rejections) == 1
    assert "RuntimeError" in snap.recent_rejections[0].blocking_guard


# ============================================================
# Bridge wiring — gate_domain_run records on every invocation
# ============================================================


def test_gate_domain_run_records_allow():
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok")))
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(domain="software_dev", tenant_id="acme", summary="x")
        snap = METRICS.snapshot()
        assert snap.runs_by_surface_verdict[(SURFACE_DOMAIN_RUN, VERDICT_ALLOWED)] == 1
        assert snap.runs_by_surface_tenant[(SURFACE_DOMAIN_RUN, "acme")] == 1
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_records_deny():
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "policy",
            lambda c: GuardResult(
                allowed=False, guard_name="policy", reason="frozen",
            ),
        )
    )
    configure_musia_governance_chain(chain)
    try:
        gate_domain_run(domain="healthcare", tenant_id="hospital", summary="x")
        snap = METRICS.snapshot()
        assert snap.runs_by_surface_verdict[(SURFACE_DOMAIN_RUN, VERDICT_DENIED)] == 1
        assert snap.denials_by_guard == {"policy": 1}
        assert snap.recent_rejections[0].surface == SURFACE_DOMAIN_RUN
        assert snap.recent_rejections[0].tenant_id == "hospital"
    finally:
        configure_musia_governance_chain(None)


def test_gate_domain_run_detached_does_not_record():
    """When the chain is detached, no chain invocation happens — and no
    counter is incremented. (Operators distinguish "chain attached and
    permissive" from "no chain installed" by absence of activity.)"""
    configure_musia_governance_chain(None)
    gate_domain_run(domain="software_dev", tenant_id="acme", summary="x")
    snap = METRICS.snapshot()
    assert snap.total_runs() == 0


def test_gate_domain_run_records_exception():
    class Boom:
        guards = []  # type: ignore[var-annotated]

        def evaluate(self, ctx):
            raise ValueError("crashy guard")

    configure_musia_governance_chain(Boom())  # type: ignore[arg-type]
    try:
        ok, _ = gate_domain_run(domain="software_dev", tenant_id="acme", summary="x")
        assert ok is False
        snap = METRICS.snapshot()
        assert snap.runs_by_surface_verdict[(SURFACE_DOMAIN_RUN, VERDICT_EXCEPTION)] == 1
    finally:
        configure_musia_governance_chain(None)


def test_metrics_separates_write_from_domain_run():
    """A chain that gates both surfaces — records them under separate
    surface buckets so per-surface analysis works."""
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok")))
    configure_musia_governance_chain(chain)
    try:
        # Domain runs (via gate_domain_run)
        gate_domain_run(domain="software_dev", tenant_id="acme", summary="a")
        gate_domain_run(domain="healthcare", tenant_id="acme", summary="b")
        # Construct writes (via chain_to_validator)
        validator = chain_to_validator(chain)
        validator(_delta(), _ctx("acme"), _auth())
        snap = METRICS.snapshot()
        assert snap.runs_by_surface_verdict[(SURFACE_DOMAIN_RUN, VERDICT_ALLOWED)] == 2
        assert snap.runs_by_surface_verdict[(SURFACE_WRITE, VERDICT_ALLOWED)] == 1
        assert snap.runs_by_surface_tenant[(SURFACE_DOMAIN_RUN, "acme")] == 2
        assert snap.runs_by_surface_tenant[(SURFACE_WRITE, "acme")] == 1
    finally:
        configure_musia_governance_chain(None)


# ============================================================
# HTTP surface
# ============================================================


@pytest.fixture
def http_app() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)
    configure_musia_governance_chain(None)
    app = FastAPI()
    app.include_router(constructs_router)
    app.include_router(domains_router)
    app.include_router(metrics_router)
    yield TestClient(app)
    configure_musia_governance_chain(None)
    reset_registry()


def test_get_stats_empty_returns_zeros(http_app):
    r = http_app.get("/musia/governance/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_runs"] == 0
    assert body["total_denials"] == 0
    assert body["recent_rejections"] == []


def test_get_stats_after_chain_activity(http_app):
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "deny_all",
            lambda c: GuardResult(
                allowed=False, guard_name="deny_all", reason="testing",
            ),
        )
    )
    configure_musia_governance_chain(chain)

    # One blocked write
    http_app.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    # One blocked domain run
    http_app.post(
        "/domains/software-dev/process",
        json={
            "kind": "bug_fix", "summary": "x", "repository": "r",
            "affected_files": ["a.py"], "acceptance_criteria": ["c"],
        },
    )

    r = http_app.get("/musia/governance/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total_runs"] == 2
    assert body["total_denials"] == 2
    # Both surfaces represented
    assert f"{SURFACE_WRITE}:{VERDICT_DENIED}" in body["runs_by_surface_verdict"]
    assert f"{SURFACE_DOMAIN_RUN}:{VERDICT_DENIED}" in body["runs_by_surface_verdict"]
    assert body["denials_by_guard"]["deny_all"] == 2
    assert len(body["recent_rejections"]) == 2


def test_post_stats_reset_clears_counters(http_app):
    chain = GovernanceGuardChain()
    chain.add(GovernanceGuard("ok", lambda c: GuardResult(allowed=True, guard_name="ok")))
    configure_musia_governance_chain(chain)

    http_app.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )

    r = http_app.get("/musia/governance/stats").json()
    assert r["total_runs"] >= 1

    reset = http_app.post("/musia/governance/stats/reset")
    assert reset.status_code == 204

    r = http_app.get("/musia/governance/stats").json()
    assert r["total_runs"] == 0


def test_recent_rejections_in_response_carry_full_detail(http_app):
    chain = GovernanceGuardChain()
    chain.add(
        GovernanceGuard(
            "boundary_lockdown",
            lambda c: GuardResult(
                allowed=False,
                guard_name="boundary_lockdown",
                reason="boundaries frozen by compliance",
            ),
        )
    )
    configure_musia_governance_chain(chain)

    http_app.post(
        "/constructs/boundary",
        headers={"X-Tenant-ID": "acme"},
        json={"inside_predicate": "scope"},
    )

    body = http_app.get("/musia/governance/stats").json()
    rej = body["recent_rejections"][0]
    assert rej["surface"] == SURFACE_WRITE
    assert rej["tenant_id"] == "acme"
    assert rej["blocking_guard"] == "boundary_lockdown"
    assert rej["reason"] == "boundaries frozen by compliance"
    assert isinstance(rej["timestamp"], (int, float))
