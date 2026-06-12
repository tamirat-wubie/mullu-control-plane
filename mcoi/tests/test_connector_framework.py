"""Purpose: verify governed connector framework — core + HTTP endpoints.
Governance scope: connector framework tests only.
Dependencies: connector_framework module, FastAPI test client.
Invariants: all invocations governed; errors never propagate; history bounded.
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from mcoi_runtime.core.connector_framework import (
    ConnectorDefinition,
    ConnectorStatus,
    ConnectorType,
    GovernedConnectorFramework,
    InvocationOutcome,
)


_CLOCK = "2026-03-30T00:00:00+00:00"


def _make_framework(**kwargs) -> GovernedConnectorFramework:
    return GovernedConnectorFramework(clock=lambda: _CLOCK, **kwargs)


def _sample_connector(cid: str = "c1") -> ConnectorDefinition:
    return ConnectorDefinition(
        connector_id=cid,
        name="Test Connector",
        connector_type=ConnectorType.HTTP_API,
        base_url="https://api.example.com",
        capabilities=("read", "write"),
    )


# --- Core Engine Tests ---


def test_register_and_list() -> None:
    fw = _make_framework()
    fw.register(_sample_connector("c1"), lambda a, p: {"ok": True})
    fw.register(_sample_connector("c2"), lambda a, p: {"ok": True})
    assert len(fw.list_connectors()) == 2


def test_unregister() -> None:
    fw = _make_framework()
    fw.register(_sample_connector(), lambda a, p: {})
    assert fw.unregister("c1") is True
    assert fw.unregister("c1") is False


def test_disable_enable() -> None:
    fw = _make_framework()
    fw.register(_sample_connector(), lambda a, p: {})
    assert fw.disable("c1") is True
    assert fw.get_connector("c1").status == ConnectorStatus.DISABLED
    assert fw.enable("c1") is True
    assert fw.get_connector("c1").status == ConnectorStatus.HEALTHY


def test_invoke_success() -> None:
    fw = _make_framework()
    fw.register(_sample_connector(), lambda a, p: {"result": a})
    inv = fw.invoke("c1", "fetch", {"key": "val"})
    assert inv.outcome == InvocationOutcome.SUCCESS
    assert inv.error == ""


def test_invoke_records_audit_trail() -> None:
    records: list[dict[str, object]] = []

    class AuditTrail:
        def record(self, **kwargs):
            records.append(kwargs)

    fw = _make_framework(audit_trail=AuditTrail())
    fw.register(_sample_connector(), lambda a, p: {"result": a})

    inv = fw.invoke("c1", "fetch", {"key": "val"}, tenant_id="tenant-a", mission_id="mission-1", goal_id="goal-1")

    assert inv.outcome == InvocationOutcome.SUCCESS
    assert len(records) == 1
    assert records[0]["action"] == "connector.invoke.fetch"
    assert records[0]["actor_id"] == "connector:c1"
    assert records[0]["tenant_id"] == "tenant-a"
    assert records[0]["outcome"] == "success"
    assert records[0]["detail"]["mission_id"] == "mission-1"
    assert records[0]["detail"]["goal_id"] == "goal-1"


def test_invoke_disabled_denied() -> None:
    fw = _make_framework()
    fw.register(_sample_connector(), lambda a, p: {})
    fw.disable("c1")
    inv = fw.invoke("c1", "fetch", {})
    assert inv.outcome == InvocationOutcome.DENIED
    assert "disabled" in inv.error


def test_invoke_nonexistent_failure() -> None:
    fw = _make_framework()
    inv = fw.invoke("missing", "fetch", {})
    assert inv.outcome == InvocationOutcome.FAILURE
    assert "not found" in inv.error


def test_invoke_handler_raises() -> None:
    def bad_handler(a, p):
        raise RuntimeError("boom")

    fw = _make_framework()
    fw.register(_sample_connector(), bad_handler)
    inv = fw.invoke("c1", "fetch", {})
    assert inv.outcome == InvocationOutcome.FAILURE
    assert inv.error == "connector error (RuntimeError)"


def test_invoke_guard_denied_is_bounded() -> None:
    class GuardChain:
        def evaluate(self, ctx):
            return SimpleNamespace(allowed=False, reason="tenant t1 denied by secret policy")

    fw = _make_framework(guard_chain=GuardChain())
    fw.register(_sample_connector(), lambda a, p: {"ok": True})
    inv = fw.invoke("c1", "fetch", {})
    assert inv.outcome == InvocationOutcome.DENIED
    assert inv.error == "connector access denied"
    assert "tenant t1" not in inv.error
    assert "secret policy" not in inv.error


def test_history_bounded() -> None:
    fw = _make_framework()
    fw.register(_sample_connector(), lambda a, p: {})
    for _ in range(30):
        fw.invoke("c1", "ping", {})
    recent = fw.recent_invocations(limit=10)
    assert len(recent) == 10
    assert recent[0].invocation_id == "cinv-000030"
    assert fw.recent_invocations(limit=0) == []
    assert fw.recent_invocations(limit=-1) == []


@pytest.mark.parametrize("limit", [True, "1", None])
def test_history_rejects_invalid_limit_contract(limit) -> None:
    fw = _make_framework()
    fw.register(_sample_connector(), lambda a, p: {})
    fw.invoke("c1", "ping", {})

    with pytest.raises(ValueError, match="connector invocation history limit must be an integer"):
        fw.recent_invocations(limit=limit)
    assert fw.summary()["history_size"] == 1


def test_summary() -> None:
    fw = _make_framework()
    fw.register(_sample_connector(), lambda a, p: {})
    fw.invoke("c1", "ping", {})
    s = fw.summary()
    assert s["total_connectors"] == 1
    assert s["total_invocations"] == 1


# --- HTTP Endpoint Tests ---


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    from fastapi.testclient import TestClient
    return TestClient(app)


def test_register_connector_endpoint(client) -> None:
    resp = client.post("/api/v1/connectors/register", json={
        "connector_id": "http-test",
        "name": "HTTP Test",
        "connector_type": "http_api",
    })
    assert resp.status_code == 200
    assert resp.json()["governed"] is True
    assert resp.json()["status"] == "registered"


def test_invoke_connector_endpoint(client) -> None:
    client.post("/api/v1/connectors/register", json={
        "connector_id": "inv-test",
        "name": "Invoke Test",
        "connector_type": "http_api",
    })
    resp = client.post("/api/v1/connectors/invoke", json={
        "connector_id": "inv-test",
        "action": "fetch",
        "payload": {"url": "/data"},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["outcome"] == "success"
    assert data["governed"] is True


def test_list_connectors_endpoint(client) -> None:
    resp = client.get("/api/v1/connectors")
    assert resp.status_code == 200
    assert resp.json()["governed"] is True


def test_connectors_summary_endpoint(client) -> None:
    resp = client.get("/api/v1/connectors/summary")
    assert resp.status_code == 200
    assert "total_connectors" in resp.json()


def test_connector_lifecycle_and_history_endpoints(client) -> None:
    client.post("/api/v1/connectors/register", json={
        "connector_id": "life-test",
        "name": "Lifecycle Test",
        "connector_type": "http_api",
    })

    first_invocation = client.post("/api/v1/connectors/invoke", json={
        "connector_id": "life-test",
        "action": "fetch",
        "payload": {"url": "/before-disable"},
    })
    disabled = client.post("/api/v1/connectors/life-test/disable")
    denied = client.post("/api/v1/connectors/invoke", json={
        "connector_id": "life-test",
        "action": "fetch",
        "payload": {"url": "/while-disabled"},
    })
    enabled = client.post("/api/v1/connectors/life-test/enable")
    history = client.get("/api/v1/connectors/history?limit=5")

    assert first_invocation.status_code == 200
    assert first_invocation.json()["outcome"] == "success"
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    assert denied.status_code == 200
    assert denied.json()["outcome"] == "denied"
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "healthy"
    assert history.status_code == 200
    assert history.json()["governed"] is True
    assert history.json()["count"] >= 2


def test_connector_history_zero_limit_returns_empty_read(client) -> None:
    client.post("/api/v1/connectors/register", json={
        "connector_id": "history-zero",
        "name": "History Zero",
        "connector_type": "http_api",
    })
    client.post("/api/v1/connectors/invoke", json={
        "connector_id": "history-zero",
        "action": "fetch",
        "payload": {"url": "/history-zero"},
    })

    resp = client.get("/api/v1/connectors/history", params={"limit": "0"})
    data = resp.json()

    assert resp.status_code == 200
    assert data["governed"] is True
    assert data["invocations"] == []
    assert data["count"] == 0


@pytest.mark.parametrize("limit", ["-1", "not-a-limit", "501"])
def test_connector_history_rejects_invalid_limit(client, limit: str) -> None:
    resp = client.get("/api/v1/connectors/history", params={"limit": limit})
    detail = resp.json()["detail"]

    assert resp.status_code == 422
    assert detail["error"] == "invalid connector history request"
    assert detail["error_code"] == "connector_history_invalid_request"
    assert detail["governed"] is True


def test_invalid_connector_type_400(client) -> None:
    resp = client.post("/api/v1/connectors/register", json={
        "connector_id": "bad",
        "name": "Bad",
        "connector_type": "invalid",
    })
    assert resp.status_code == 400
