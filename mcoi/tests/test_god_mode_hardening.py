"""Tests for production-hardening additions to the god-mode subsystem.

Covers:
- Metrics sink wiring (issue + consume + rejection counters)
- Per-actor + per-capability sliding-window rate limit on issue_ticket
- `/api/v1/god-mode/health` operator visibility endpoint
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    set_engine,
)
from mcoi_runtime.core.god_mode_integration import install_default_capabilities
from mcoi_runtime.core.god_mode_registry import (
    GodModeRegistry,
    set_registry,
)


_VERY_LONG_JUST = "x" * 130


class MetricsStub:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}

    def inc(self, name: str, value: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + value


@pytest.fixture
def armed_registry() -> GodModeRegistry:
    reg = GodModeRegistry()
    reg.register_capability(
        GodCapability(
            module="data",
            name="purge_tenant_now",
            description="Delete tenant data.",
            blast_radius=GodCapabilityBlastRadius.CATASTROPHIC,
            bypasses=("retention_window",),
            default_ttl_seconds=60,
            min_justification_chars=120,
        )
    )
    reg.agree_to_register(
        module="data",
        name="purge_tenant_now",
        actor_id="alice",
        justification=_VERY_LONG_JUST,
    )
    return reg


# --- Metrics integration -----------------------------------------------------


def test_metrics_sink_counts_ticket_issuance(armed_registry):
    metrics = MetricsStub()
    engine = GodModeEngine(registry=armed_registry, metrics_sink=metrics)
    engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    assert metrics.counts.get("god_mode_ticket_issued") == 1
    assert metrics.counts.get("god_mode_ticket_issued_data_purge_tenant_now") == 1


def test_metrics_sink_counts_consume_outcomes(armed_registry):
    metrics = MetricsStub()
    engine = GodModeEngine(registry=armed_registry, metrics_sink=metrics)
    t1, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    engine.consume(
        ticket_id=t1.ticket_id,
        outcome=GodReceiptOutcome.SUCCESS,
        pre_state=None,
        post_state=None,
    )
    t2, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    engine.consume(
        ticket_id=t2.ticket_id,
        outcome=GodReceiptOutcome.FAILURE,
        pre_state=None,
        post_state=None,
        failure_reason="boom",
    )
    assert metrics.counts.get("god_mode_consume_success") == 1
    assert metrics.counts.get("god_mode_consume_failure") == 1


def test_metrics_sink_counts_dormant_rejection():
    reg = GodModeRegistry()
    reg.register_capability(
        GodCapability(
            module="rbac",
            name="impersonate_user",
            description="Act as another identity.",
            blast_radius=GodCapabilityBlastRadius.PLATFORM,
            bypasses=("identity_binding",),
            default_ttl_seconds=60,
        )
    )
    metrics = MetricsStub()
    engine = GodModeEngine(registry=reg, metrics_sink=metrics)
    with pytest.raises(GodModeEngineError):
        engine.issue_ticket(
            actor_id="alice",
            module="rbac",
            name="impersonate_user",
            justification=_VERY_LONG_JUST,
        )
    assert metrics.counts.get("god_mode_issue_rejected_dormant") == 1


def test_metrics_sink_counts_unknown_capability_rejection(armed_registry):
    metrics = MetricsStub()
    engine = GodModeEngine(registry=armed_registry, metrics_sink=metrics)
    with pytest.raises(GodModeEngineError):
        engine.issue_ticket(
            actor_id="alice",
            module="ghost",
            name="missing",
            justification=_VERY_LONG_JUST,
        )
    assert metrics.counts.get("god_mode_issue_rejected_unknown") == 1


def test_metrics_sink_exception_does_not_break_issue(armed_registry):
    class BadMetrics:
        def inc(self, name: str, value: int = 1) -> None:
            raise RuntimeError("metrics down")

    engine = GodModeEngine(registry=armed_registry, metrics_sink=BadMetrics())
    ticket, _ = engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    assert ticket.actor_id == "alice"


# --- Rate limiting ----------------------------------------------------------


def test_rate_limit_blocks_burst(armed_registry):
    engine = GodModeEngine(
        registry=armed_registry,
        rate_limit_tickets=3,
        rate_limit_window_seconds=300,
    )
    for _ in range(3):
        engine.issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG_JUST,
        )
    with pytest.raises(GodModeEngineError, match="rate limit"):
        engine.issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG_JUST,
        )


def test_rate_limit_per_actor_independent(armed_registry):
    engine = GodModeEngine(
        registry=armed_registry,
        rate_limit_tickets=1,
        rate_limit_window_seconds=300,
    )
    engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    # Bob has his own bucket and is unaffected.
    engine.issue_ticket(
        actor_id="bob",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    with pytest.raises(GodModeEngineError, match="rate limit"):
        engine.issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG_JUST,
        )


def test_rate_limit_window_eviction(armed_registry):
    """Stale entries outside the window must not count toward the budget."""
    engine = GodModeEngine(
        registry=armed_registry,
        rate_limit_tickets=2,
        rate_limit_window_seconds=300,
    )
    # Pre-seed the issue log with two entries that already aged out.
    stale = datetime.now(tz=timezone.utc) - timedelta(seconds=600)
    engine._issue_log[("alice", "data", "purge_tenant_now")] = [stale, stale]
    # Third issuance succeeds because the stale entries get evicted on check.
    engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )


def test_rate_limit_disabled_with_zero(armed_registry):
    engine = GodModeEngine(
        registry=armed_registry,
        rate_limit_tickets=0,
        rate_limit_window_seconds=300,
    )
    for _ in range(10):
        engine.issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG_JUST,
        )


def test_rate_limit_emits_metric(armed_registry):
    metrics = MetricsStub()
    engine = GodModeEngine(
        registry=armed_registry,
        metrics_sink=metrics,
        rate_limit_tickets=1,
        rate_limit_window_seconds=300,
    )
    engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    with pytest.raises(GodModeEngineError):
        engine.issue_ticket(
            actor_id="alice",
            module="data",
            name="purge_tenant_now",
            justification=_VERY_LONG_JUST,
        )
    assert metrics.counts.get("god_mode_issue_rejected_rate_limited") == 1


def test_issue_log_for_returns_iso_timestamps(armed_registry):
    engine = GodModeEngine(registry=armed_registry)
    engine.issue_ticket(
        actor_id="alice",
        module="data",
        name="purge_tenant_now",
        justification=_VERY_LONG_JUST,
    )
    log = engine.issue_log_for(
        actor_id="alice", module="data", name="purge_tenant_now"
    )
    assert len(log) == 1
    assert "T" in log[0]  # ISO 8601 sentinel


# --- Health endpoint -------------------------------------------------------


def _client():
    fresh = GodModeRegistry()
    install_default_capabilities(fresh)
    set_registry(fresh)
    set_engine(GodModeEngine(registry=fresh))
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_health_endpoint_initial_state():
    client = _client()
    resp = client.get("/api/v1/god-mode/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["governed"] is True
    assert body["capability_count"] >= 14
    assert body["by_state"]["dormant"] == body["capability_count"]
    assert body["by_state"]["armed"] == 0
    assert body["armed_by_blast_radius"] == {}
    assert body["active_ticket_count"] == 0
    assert body["receipt_count"] == 0


def test_health_endpoint_after_arm_and_issue():
    client = _client()
    # data/purge_tenant_now is dual-control catastrophic — needs two distinct actors.
    client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/agree-to-register",
        json={"actor_id": "bob", "justification": _VERY_LONG_JUST},
    )
    client.post(
        "/api/v1/god-mode/capabilities/data/purge_tenant_now/issue-ticket",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    body = client.get("/api/v1/god-mode/health").json()
    assert body["by_state"]["armed"] == 1
    assert body["armed_by_blast_radius"].get("catastrophic") == 1
    assert body["active_ticket_count"] == 1


def test_health_endpoint_counts_receipts():
    client = _client()
    client.post(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder/agree-to-register",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    issue = client.post(
        "/api/v1/god-mode/capabilities/replay/mutate_recorder/issue-ticket",
        json={"actor_id": "alice", "justification": _VERY_LONG_JUST},
    )
    tid = issue.json()["ticket"]["ticket_id"]
    client.post(
        f"/api/v1/god-mode/tickets/{tid}/consume",
        json={"outcome": "success"},
    )
    body = client.get("/api/v1/god-mode/health").json()
    assert body["receipt_count"] == 1
    assert body["active_ticket_count"] == 0
