"""Dual-control (two-person rule) tests for the god-mode subsystem.

Verifies that capabilities flagged with `requires_dual_control=True`:
- Stay in PENDING_DUAL after one agreement
- Reject duplicate-actor agreements (two agreements from the same actor)
- Reach ARMED only after two distinct-actor agreements
- Drop back to PENDING_DUAL or DORMANT when one agreement is withdrawn
- Refuse ticket issuance while PENDING_DUAL
- Surface `pending_required_actors` count via the HTTP catalog
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.god_mode import router
from mcoi_runtime.contracts.god_mode import (
    GodCapability,
    GodCapabilityBlastRadius,
    GodCapabilityState,
)
from mcoi_runtime.core.god_mode_engine import (
    GodModeEngine,
    GodModeEngineError,
    set_engine,
)
from mcoi_runtime.core.god_mode_integration import install_default_capabilities
from mcoi_runtime.core.god_mode_registry import (
    GodModeRegistry,
    GodModeRegistryError,
    set_registry,
)


_VERY_LONG_JUST = "x" * 130


@pytest.fixture
def dual_capability() -> GodCapability:
    return GodCapability(
        module="data",
        name="purge_tenant_now",
        description="Delete all data for a tenant.",
        blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
        bypasses=("retention_window",),
        default_ttl_seconds=60,
        min_justification_chars=120,
        requires_dual_control=True,
    )


@pytest.fixture
def registry(dual_capability) -> GodModeRegistry:
    reg = GodModeRegistry()
    reg.register_capability(dual_capability)
    return reg


# --- Contract validation --------------------------------------------------


def test_capability_rejects_dual_control_min_below_two():
    with pytest.raises(ValueError):
        GodCapability(
            module="data",
            name="purge_tenant_now",
            description="x" * 30,
            blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
            bypasses=("retention_window",),
            default_ttl_seconds=60,
            min_justification_chars=120,
            requires_dual_control=True,
            dual_control_min_actors=1,
        )


def test_capability_rejects_dual_control_min_above_five():
    with pytest.raises(ValueError):
        GodCapability(
            module="data",
            name="purge_tenant_now",
            description="x" * 30,
            blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
            bypasses=("retention_window",),
            default_ttl_seconds=60,
            min_justification_chars=120,
            requires_dual_control=True,
            dual_control_min_actors=6,
        )


# --- State transitions ----------------------------------------------------


def test_one_agreement_yields_pending_dual(registry):
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    assert registry.state_of("data", "purge_tenant_now") == GodCapabilityState.PENDING_DUAL
    assert registry.pending_required_actors("data", "purge_tenant_now") == 1
    assert not registry.is_armed("data", "purge_tenant_now")


def test_two_distinct_agreements_arm_capability(registry):
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="bob",
        justification=_VERY_LONG_JUST,
    )
    assert registry.state_of("data", "purge_tenant_now") == GodCapabilityState.ARMED
    assert registry.pending_required_actors("data", "purge_tenant_now") == 0
    assert registry.is_armed("data", "purge_tenant_now")


def test_duplicate_actor_agreement_rejected(registry):
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    with pytest.raises(GodModeRegistryError, match="dual control"):
        registry.agree_to_register(
            module="data",
            name="purge_tenant_now",
            actor_id="alice",
            justification=_VERY_LONG_JUST,
        )


def test_withdraw_first_agreement_drops_to_dormant(registry):
    a = registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    registry.withdraw_registration(
        agreement_id=a.agreement_id, actor_id="alice", reason="rotated"
    )
    # No active agreements but one in history → WITHDRAWN
    assert registry.state_of("data", "purge_tenant_now") == GodCapabilityState.WITHDRAWN


def test_withdraw_one_of_two_agreements_drops_to_pending_dual(registry):
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    b = registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="bob",
        justification=_VERY_LONG_JUST,
    )
    assert registry.is_armed("data", "purge_tenant_now")
    registry.withdraw_registration(
        agreement_id=b.agreement_id, actor_id="bob", reason="rotated"
    )
    assert registry.state_of("data", "purge_tenant_now") == GodCapabilityState.PENDING_DUAL


def test_re_arm_after_withdrawal_with_distinct_third_actor(registry):
    a1 = registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="bob",
        justification=_VERY_LONG_JUST,
    )
    registry.withdraw_registration(
        agreement_id=a1.agreement_id, actor_id="alice", reason="rotated"
    )
    # Now back to PENDING_DUAL with only Bob active.
    assert registry.state_of("data", "purge_tenant_now") == GodCapabilityState.PENDING_DUAL
    # Carol re-arms.
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="carol",
        justification=_VERY_LONG_JUST,
    )
    assert registry.is_armed("data", "purge_tenant_now")


def test_three_actor_quorum():
    cap = GodCapability(
        module="secrets",
        name="reveal_redacted_in_audit",
        description="Reveal redacted secrets.",
        blast_radius=GodCapabilityBlastRadius.PLATFORM,
        bypasses=("secret_redaction",),
        default_ttl_seconds=60,
        min_justification_chars=200,
        requires_dual_control=True,
        dual_control_min_actors=3,
    )
    reg = GodModeRegistry()
    reg.register_capability(cap)
    just = "x" * 250
    reg.agree_to_register(
        module="secrets",
        name="reveal_redacted_in_audit",
        actor_id="alice",
        justification=just,
    )
    reg.agree_to_register(
        module="secrets",
        name="reveal_redacted_in_audit",
        actor_id="bob",
        justification=just,
    )
    assert reg.state_of("secrets", "reveal_redacted_in_audit") == GodCapabilityState.PENDING_DUAL
    assert reg.pending_required_actors("secrets", "reveal_redacted_in_audit") == 1
    reg.agree_to_register(
        module="secrets",
        name="reveal_redacted_in_audit",
        actor_id="carol",
        justification=just,
    )
    assert reg.is_armed("secrets", "reveal_redacted_in_audit")


# --- Engine ticket issuance against PENDING_DUAL ---------------------------


def test_engine_refuses_ticket_for_pending_dual(registry):
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    engine = GodModeEngine(registry=registry)
    with pytest.raises(GodModeEngineError, match="pending_dual"):
        engine.issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG_JUST,
        )


def test_engine_metric_for_pending_dual_rejection(registry):
    class MetricsStub:
        def __init__(self):
            self.counts = {}

        def inc(self, name, value=1):
            self.counts[name] = self.counts.get(name, 0) + value

    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    metrics = MetricsStub()
    engine = GodModeEngine(registry=registry, metrics_sink=metrics)
    with pytest.raises(GodModeEngineError):
        engine.issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG_JUST,
        )
    assert metrics.counts.get("god_mode_issue_rejected_pending_dual") == 1


def test_engine_issues_ticket_when_dual_control_satisfied(registry):
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    registry.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="bob",
        justification=_VERY_LONG_JUST,
    )
    engine = GodModeEngine(registry=registry)
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    assert ticket.actor_id == "alice"


# --- HTTP surface ---------------------------------------------------------


def _client():
    fresh = GodModeRegistry()
    install_default_capabilities(fresh)
    set_registry(fresh)
    set_engine(GodModeEngine(registry=fresh))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_router_one_agree_yields_pending_dual_for_catastrophic():
    client = _client()
    resp = client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "pending_dual"
    detail = client.get(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now"
    ).json()
    assert detail["state"] == "pending_dual"
    assert detail["pending_required_actors"] == 1


def test_router_second_distinct_agree_arms_capability():
    client = _client()
    client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    resp = client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "bob", "justification": _VERY_LONG_JUST},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "armed"
    detail = client.get(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now"
    ).json()
    assert detail["pending_required_actors"] == 0


def test_router_duplicate_actor_agree_rejected():
    client = _client()
    client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    resp = client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    assert resp.status_code == 400
    assert "dual control" in resp.json()["detail"]["error"].lower()


def test_router_issue_ticket_blocked_in_pending_dual():
    client = _client()
    client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    resp = client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/issue-ticket",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    assert resp.status_code == 400
    assert "pending_dual" in resp.json()["detail"]["error"]


def test_router_health_reflects_pending_dual_count():
    client = _client()
    client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    body = client.get("/api/v1/god-mode/health").json()
    assert body["by_state"]["pending_dual"] == 1
    assert body["by_state"]["armed"] == 0


# --- Non-dual capabilities still work the same ----------------------------


def test_non_dual_capability_arms_with_one_agreement():
    """Sanity: capabilities without requires_dual_control still arm in one shot."""
    client = _client()
    resp = client.post(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    assert resp.status_code == 200
    assert resp.json()["state"] == "armed"
    detail = client.get(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder"
    ).json()
    assert detail["pending_required_actors"] == 0
