"""v4.15.0 — bridge GovernanceGuardChain into Φ_gov external_validators."""
from __future__ import annotations

from typing import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.constructs import (
    reset_registry,
    router as constructs_router,
)
from mcoi_runtime.app.routers.musia_auth import configure_musia_auth
from mcoi_runtime.app.routers.musia_governance_bridge import (
    chain_to_validator,
    configure_musia_governance_chain,
    configured_chain,
    installed_validator_or_none,
)
from mcoi_runtime.governance.guards.chain import (
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
# Bridge unit tests
# ============================================================


def _make_chain(*guards: GovernanceGuard) -> GovernanceGuardChain:
    chain = GovernanceGuardChain()
    for g in guards:
        chain.add(g)
    return chain


def _delta() -> ProposedDelta:
    return ProposedDelta(
        construct_id=uuid4(),
        operation="create",
        payload={"type": "state", "tier": 1},
    )


def _ctx(tenant_id: str = "acme") -> GovernanceContext:
    return GovernanceContext(correlation_id="test-cid", tenant_id=tenant_id)


def _auth() -> Authority:
    return Authority(identifier="agent-test", kind="agent")


def test_validator_returns_true_for_empty_chain():
    """A chain with no guards is permissive."""
    chain = GovernanceGuardChain()
    validator = chain_to_validator(chain)
    ok, reason = validator(_delta(), _ctx(), _auth())
    assert ok is True
    assert reason == ""


def test_validator_returns_true_when_all_guards_pass():
    chain = _make_chain(
        GovernanceGuard("always_ok", lambda ctx: GuardResult(allowed=True, guard_name="always_ok"))
    )
    validator = chain_to_validator(chain)
    ok, reason = validator(_delta(), _ctx(), _auth())
    assert ok is True


def test_validator_returns_false_with_blocking_guard_in_reason():
    chain = _make_chain(
        GovernanceGuard(
            "deny_all",
            lambda ctx: GuardResult(
                allowed=False,
                guard_name="deny_all",
                reason="universal denial",
            ),
        )
    )
    validator = chain_to_validator(chain)
    ok, reason = validator(_delta(), _ctx(), _auth())
    assert ok is False
    assert "deny_all" in reason
    assert "universal denial" in reason


def test_validator_chain_passes_tenant_id_to_guards():
    """The bridge populates guard_ctx['tenant_id'] from GovernanceContext."""
    seen_tenants: list[str] = []

    def capture(ctx: dict) -> GuardResult:
        seen_tenants.append(ctx.get("tenant_id", ""))
        return GuardResult(allowed=True, guard_name="capture")

    chain = _make_chain(GovernanceGuard("capture", capture))
    validator = chain_to_validator(chain)
    validator(_delta(), _ctx(tenant_id="acme-corp"), _auth())
    validator(_delta(), _ctx(tenant_id="foo-llc"), _auth())
    assert seen_tenants == ["acme-corp", "foo-llc"]


def test_validator_passes_authenticated_subject_from_authority():
    seen: list[str] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append(ctx.get("authenticated_subject", ""))
        return GuardResult(allowed=True, guard_name="capture")

    chain = _make_chain(GovernanceGuard("capture", capture))
    validator = chain_to_validator(chain)
    validator(_delta(), _ctx(), Authority(identifier="agent-x", kind="agent"))
    assert seen == ["agent-x"]


def test_validator_passes_construct_metadata():
    seen: list[dict] = []

    def capture(ctx: dict) -> GuardResult:
        seen.append({
            "construct_type": ctx.get("construct_type"),
            "construct_tier": ctx.get("construct_tier"),
            "operation": ctx.get("operation"),
        })
        return GuardResult(allowed=True, guard_name="capture")

    chain = _make_chain(GovernanceGuard("capture", capture))
    validator = chain_to_validator(chain)
    delta = ProposedDelta(
        construct_id=uuid4(),
        operation="update",
        payload={"type": "transformation", "tier": 2},
    )
    validator(delta, _ctx(), _auth())
    assert seen == [{
        "construct_type": "transformation",
        "construct_tier": 2,
        "operation": "update",
    }]


def test_validator_handles_guard_exception_as_denial():
    """A guard that raises is treated as denial, not propagated."""
    def explode(ctx: dict) -> GuardResult:
        raise RuntimeError("boom")

    chain = GovernanceGuardChain()
    # Manually bypass the GovernanceGuard's own try/except by making a
    # naked guard whose check_fn raises BEFORE GovernanceGuard wraps it
    # (which it does via guard.check). Note: GovernanceGuard.check
    # already catches exceptions. So we expect it to come back as a
    # GuardResult(allowed=False) and the chain to deny normally.
    chain.add(GovernanceGuard("explode", explode))

    validator = chain_to_validator(chain)
    ok, reason = validator(_delta(), _ctx(), _auth())
    assert ok is False  # GovernanceGuard catches RuntimeError → denial


# ============================================================
# Configuration plumbing
# ============================================================


def test_configure_install_and_uninstall():
    chain = GovernanceGuardChain()
    configure_musia_governance_chain(chain)
    assert configured_chain() is chain
    configure_musia_governance_chain(None)
    assert configured_chain() is None


def test_installed_validator_or_none_when_detached():
    configure_musia_governance_chain(None)
    assert installed_validator_or_none() is None


def test_installed_validator_or_none_when_attached():
    chain = GovernanceGuardChain()
    configure_musia_governance_chain(chain)
    try:
        v = installed_validator_or_none()
        assert v is not None
        # And it works
        ok, _ = v(_delta(), _ctx(), _auth())
        assert ok is True
    finally:
        configure_musia_governance_chain(None)


# ============================================================
# Integration with /constructs/* write path
# ============================================================


@pytest.fixture
def client() -> Iterator[TestClient]:
    reset_registry()
    configure_musia_auth(None)
    configure_musia_governance_chain(None)
    app = FastAPI()
    app.include_router(constructs_router)
    yield TestClient(app)
    configure_musia_governance_chain(None)
    reset_registry()


def test_constructs_write_passes_when_chain_detached(client):
    """Default behavior: no chain installed → MUSIA writes pass."""
    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 201


def test_constructs_write_passes_when_chain_allows(client):
    chain = _make_chain(
        GovernanceGuard("ok", lambda ctx: GuardResult(allowed=True, guard_name="ok"))
    )
    configure_musia_governance_chain(chain)

    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 201


def test_constructs_write_blocked_when_chain_denies(client):
    chain = _make_chain(
        GovernanceGuard(
            "deny_all",
            lambda ctx: GuardResult(
                allowed=False,
                guard_name="deny_all",
                reason="testing block",
            ),
        ),
    )
    configure_musia_governance_chain(chain)

    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 403
    detail = r.json()["detail"]
    # The judgment carries the chain's blocking guard in the reason
    assert "deny_all" in detail.get("reason", "")


def test_constructs_write_blocked_does_not_register(client):
    chain = _make_chain(
        GovernanceGuard(
            "deny_all",
            lambda ctx: GuardResult(
                allowed=False, guard_name="deny_all", reason="x",
            ),
        )
    )
    configure_musia_governance_chain(chain)

    pre = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
    ).json()["total"]
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    post = client.get(
        "/constructs",
        headers={"X-Tenant-ID": "acme"},
    ).json()["total"]
    assert pre == post  # nothing registered


def test_chain_runs_alongside_quota(client):
    """Both quota and chain are checked. Quota is cheaper (first); a
    quota violation surfaces as quota error, not chain error."""
    # Create a tenant first by writing one construct
    client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    # Lower the quota below current count
    from mcoi_runtime.substrate.registry_store import STORE, TenantQuota
    STORE.get("acme").quota = TenantQuota(max_constructs=1)

    chain = _make_chain(
        GovernanceGuard(
            "deny_all",
            lambda ctx: GuardResult(
                allowed=False, guard_name="deny_all", reason="x",
            ),
        )
    )
    configure_musia_governance_chain(chain)

    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    # Quota fires first (429), not chain (403)
    assert r.status_code == 429
    assert "quota" in r.json()["detail"]["error"]


def test_chain_specific_guards_can_inspect_construct_type(client):
    """A guard that blocks only certain construct types (e.g., 'no Boundary
    creates from non-admin') passes for State and rejects for Boundary."""

    def block_boundary(ctx: dict) -> GuardResult:
        if ctx.get("construct_type") == "boundary":
            return GuardResult(
                allowed=False,
                guard_name="boundary_policy",
                reason="boundary writes restricted in this tenant",
            )
        return GuardResult(allowed=True, guard_name="boundary_policy")

    chain = _make_chain(GovernanceGuard("boundary_policy", block_boundary))
    configure_musia_governance_chain(chain)

    # State: passes
    r_state = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r_state.status_code == 201

    # Boundary: blocked
    r_bnd = client.post(
        "/constructs/boundary",
        headers={"X-Tenant-ID": "acme"},
        json={"inside_predicate": "scope"},
    )
    assert r_bnd.status_code == 403
    assert "boundary_policy" in r_bnd.json()["detail"]["reason"]


def test_chain_with_multiple_guards_first_failure_blocks(client):
    """The chain's existing first-failure-stops semantics carry through to MUSIA."""
    seen_2nd = [False]

    def first_denies(ctx: dict) -> GuardResult:
        return GuardResult(allowed=False, guard_name="first", reason="nope")

    def second_should_not_run(ctx: dict) -> GuardResult:
        seen_2nd[0] = True
        return GuardResult(allowed=True, guard_name="second")

    chain = _make_chain(
        GovernanceGuard("first", first_denies),
        GovernanceGuard("second", second_should_not_run),
    )
    configure_musia_governance_chain(chain)

    r = client.post(
        "/constructs/state",
        headers={"X-Tenant-ID": "acme"},
        json={"configuration": {}},
    )
    assert r.status_code == 403
    assert "first" in r.json()["detail"]["reason"]
    # The chain stopped at first; second never ran
    assert seen_2nd[0] is False
