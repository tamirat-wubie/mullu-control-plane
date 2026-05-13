"""Tenant-scoping tests for the god-mode subsystem.

When a ticket is issued with a non-empty tenant_id, the consume call must
pass an ``expected_tenant_id`` that matches; otherwise the call is rejected
as a cross-tenant violation. Tickets issued tenant-agnostic (empty
tenant_id) accept any caller.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.god_mode import router
from mcoi_runtime.contracts.god_mode import (
    GodCapability,
    GodCapabilityBlastRadius,
    GodReceiptOutcome,
)
from mcoi_runtime.core.god_mode_engine import (
    GodModeEngine,
    GodModeEngineError,
    requires_god_ticket,
    set_engine,
)
from mcoi_runtime.core.god_mode_integration import install_default_capabilities
from mcoi_runtime.core.god_mode_registry import GodModeRegistry, set_registry


_VERY_LONG = "x" * 130


@pytest.fixture
def armed_registry():
    reg = GodModeRegistry()
    reg.register_capability(
        GodCapability(
            module="data",
            name="purge_tenant_now",
            description="Delete tenant data.",
            blast_radius=GodCapabilityBlastRadius.PLATFORM,  # not catastrophic in fixture
            bypasses=("retention_window",),
            default_ttl_seconds=60,
        )
    )
    reg.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG,
    )
    return reg


@pytest.fixture
def engine(armed_registry):
    return GodModeEngine(registry=armed_registry)


# --- Contract: tenant_id field acceptance ---------------------------------


def test_ticket_default_tenant_id_empty(engine):
    ticket, agreement = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
    )
    assert ticket.tenant_id == ""
    assert agreement.tenant_id == ""


def test_ticket_with_tenant_id_propagates(engine):
    ticket, agreement = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        tenant_id="acme-7",
    )
    assert ticket.tenant_id == "acme-7"
    assert agreement.tenant_id == "acme-7"


# --- Engine consume cross-tenant rejection -------------------------------


def test_consume_rejects_cross_tenant(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        tenant_id="acme-7",
    )
    with pytest.raises(GodModeEngineError, match="bound to tenant"):
        engine.consume(
            ticket_id=ticket.ticket_id,
            outcome=GodReceiptOutcome.SUCCESS,
            pre_state=None,
            post_state=None,
            expected_tenant_id="globex-9",
        )


def test_consume_accepts_matching_tenant(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        tenant_id="acme-7",
    )
    receipt = engine.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
        expected_tenant_id="acme-7",
    )
    assert receipt.tenant_id == "acme-7"


def test_consume_tenant_agnostic_ticket_accepts_any(engine):
    """Empty ticket.tenant_id means anyone can consume, regardless of expected_tenant_id."""
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        # no tenant_id
    )
    receipt = engine.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
        expected_tenant_id="globex-9",
    )
    assert receipt.tenant_id == ""


def test_consume_cross_tenant_emits_metric(armed_registry):
    class MetricsStub:
        def __init__(self):
            self.counts = {}

        def inc(self, name, value=1):
            self.counts[name] = self.counts.get(name, 0) + value

    metrics = MetricsStub()
    eng = GodModeEngine(registry=armed_registry, metrics_sink=metrics)
    ticket, _ = eng.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        tenant_id="acme-7",
    )
    with pytest.raises(GodModeEngineError):
        eng.consume(
            ticket_id=ticket.ticket_id,
            outcome=GodReceiptOutcome.SUCCESS,
            pre_state=None,
            post_state=None,
            expected_tenant_id="globex-9",
        )
    assert metrics.counts.get("god_mode_consume_rejected_cross_tenant") == 1


def test_receipt_carries_tenant_id(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        tenant_id="acme-7",
    )
    receipt = engine.consume(
        ticket_id=ticket.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
        expected_tenant_id="acme-7",
    )
    assert receipt.tenant_id == "acme-7"


def test_revoked_ticket_preserves_tenant_id(engine):
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        tenant_id="acme-7",
    )
    revoked = engine.revoke(
        ticket_id=ticket.ticket_id,
        actor_id="auditor",
        reason="late",
    )
    assert revoked.tenant_id == "acme-7"


# --- list_tickets tenant filter ------------------------------------------


def test_list_tickets_filter_by_tenant(engine):
    engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        tenant_id="acme-7",
    )
    engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG,
        tenant_id="globex-9",
    )
    acme_only = engine.list_tickets(tenant_id="acme-7")
    assert len(acme_only) == 1
    assert acme_only[0].tenant_id == "acme-7"


# --- Decorator tenant binding --------------------------------------------


def test_decorator_rejects_when_tenant_scoped_ticket_called_without_expected(
    armed_registry,
):
    set_registry(armed_registry)
    set_engine(GodModeEngine(registry=armed_registry))
    try:

        @requires_god_ticket(module="data", name="purge_tenant_now")
        def _purge(*, tenant_id: str) -> str:
            return f"purged:{tenant_id}"

        from mcoi_runtime.core.god_mode_engine import get_engine as _get_engine

        ticket, _ = _get_engine().issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG,
            tenant_id="acme-7",
        )
        with pytest.raises(GodModeEngineError, match="tenant-scoped"):
            _purge(tenant_id="acme-7", ticket_id=ticket.ticket_id)
    finally:
        set_registry(None)
        set_engine(None)


def test_decorator_accepts_matching_expected_tenant(armed_registry):
    set_registry(armed_registry)
    set_engine(GodModeEngine(registry=armed_registry))
    try:

        @requires_god_ticket(module="data", name="purge_tenant_now")
        def _purge(*, tenant_id: str) -> str:
            return f"purged:{tenant_id}"

        from mcoi_runtime.core.god_mode_engine import get_engine as _get_engine

        ticket, _ = _get_engine().issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG,
            tenant_id="acme-7",
        )
        result = _purge(
            tenant_id="acme-7",
            ticket_id=ticket.ticket_id,
            expected_tenant_id="acme-7",
        )
        assert result == "purged:acme-7"
    finally:
        set_registry(None)
        set_engine(None)


def test_decorator_rejects_cross_tenant(armed_registry):
    set_registry(armed_registry)
    set_engine(GodModeEngine(registry=armed_registry))
    try:

        @requires_god_ticket(module="data", name="purge_tenant_now")
        def _purge(*, tenant_id: str) -> str:
            return f"purged:{tenant_id}"

        from mcoi_runtime.core.god_mode_engine import get_engine as _get_engine

        ticket, _ = _get_engine().issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG,
            tenant_id="acme-7",
        )
        with pytest.raises(GodModeEngineError, match="bound to tenant"):
            _purge(
                tenant_id="globex-9",
                ticket_id=ticket.ticket_id,
                expected_tenant_id="globex-9",
            )
    finally:
        set_registry(None)
        set_engine(None)


def test_decorator_tenant_agnostic_ticket_works_without_expected(armed_registry):
    set_registry(armed_registry)
    set_engine(GodModeEngine(registry=armed_registry))
    try:

        @requires_god_ticket(module="data", name="purge_tenant_now")
        def _act() -> str:
            return "ok"

        from mcoi_runtime.core.god_mode_engine import get_engine as _get_engine

        ticket, _ = _get_engine().issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG,
            # no tenant_id
        )
        # Empty ticket.tenant_id → no expected_tenant_id required
        assert _act(ticket_id=ticket.ticket_id) == "ok"
    finally:
        set_registry(None)
        set_engine(None)


# --- Router integration ---------------------------------------------------


def _client():
    fresh = GodModeRegistry()
    install_default_capabilities(fresh)
    set_registry(fresh)
    set_engine(GodModeEngine(registry=fresh))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_router_issue_ticket_with_tenant_id():
    client = _client()
    # Use rbac/impersonate_user — non-dual, non-catastrophic
    client.post(
        "/api/v1/god-mode/capabilities/rbac/impersonate_user/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG},
    )
    resp = client.post(
        "/api/v1/god-mode/capabilities/rbac/impersonate_user/issue-ticket",
        json={
            "actor_id": "alice",
            "justification": _VERY_LONG,
            "tenant_id": "acme-7",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ticket"]["tenant_id"] == "acme-7"
    assert body["agreement"]["tenant_id"] == "acme-7"


def test_router_consume_rejects_cross_tenant():
    client = _client()
    client.post(
        "/api/v1/god-mode/capabilities/rbac/impersonate_user/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG},
    )
    issue = client.post(
        "/api/v1/god-mode/capabilities/rbac/impersonate_user/issue-ticket",
        json={
            "actor_id": "alice",
            "justification": _VERY_LONG,
            "tenant_id": "acme-7",
        },
    )
    tid = issue.json()["ticket"]["ticket_id"]
    resp = client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={"outcome": "success", "expected_tenant_id": "globex-9"},
    )
    assert resp.status_code == 400
    assert "bound to tenant" in resp.json()["detail"]["error"]


def test_router_consume_accepts_matching_tenant():
    client = _client()
    client.post(
        "/api/v1/god-mode/capabilities/rbac/impersonate_user/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG},
    )
    issue = client.post(
        "/api/v1/god-mode/capabilities/rbac/impersonate_user/issue-ticket",
        json={
            "actor_id": "alice",
            "justification": _VERY_LONG,
            "tenant_id": "acme-7",
        },
    )
    tid = issue.json()["ticket"]["ticket_id"]
    resp = client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={"outcome": "success", "expected_tenant_id": "acme-7"},
    )
    assert resp.status_code == 200
    receipt = resp.json()["receipt"]
    assert receipt["tenant_id"] == "acme-7"


def test_router_list_tickets_filter_by_tenant():
    client = _client()
    client.post(
        "/api/v1/god-mode/capabilities/rbac/impersonate_user/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG},
    )
    for tid in ["acme-7", "globex-9"]:
        client.post(
            "/api/v1/god-mode/capabilities/rbac/impersonate_user/issue-ticket",
            json={
                "actor_id": "alice",
                "justification": _VERY_LONG,
                "tenant_id": tid,
            },
        )
    resp = client.get(
        "/api/v1/god-mode/tickets", params={"tenant_id": "acme-7"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["tickets"][0]["tenant_id"] == "acme-7"
