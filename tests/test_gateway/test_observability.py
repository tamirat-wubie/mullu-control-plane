"""Gateway observability tests.

Purpose: verify governed gateway runs emit bounded metrics and trace witnesses.
Governance scope: observability summary and retained trace read models only.
Dependencies: FastAPI TestClient, gateway router, and schema validator.
Invariants:
  - Observability never stores raw message bodies or response bodies.
  - Missing production signals are explicit as not_observed.
  - Operator endpoints expose summary and trace read models.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.router import GatewayMessage, TenantMapping  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


OBSERVABILITY_SCHEMA = _ROOT / "schemas" / "gateway_observability_snapshot.schema.json"


class StubPlatform:
    """Minimal governed platform fixture for observability tests."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):
        return type("Result", (), {"content": "observed reply", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def test_router_observability_records_successful_governed_run() -> None:
    app = create_gateway_app(platform=StubPlatform())
    router = app.state.router
    router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="user-1",
        tenant_id="tenant-a",
        identity_id="actor-a",
    ))

    response = router.handle_message(GatewayMessage(
        message_id="msg-observe-1",
        channel="web",
        sender_id="user-1",
        body="summarize governed status",
    ))
    snapshot = router.observability_snapshot()

    assert response.metadata["terminal_certificate_id"]
    assert snapshot["enabled"] is True
    assert snapshot["retained_trace_count"] == 1
    assert snapshot["metrics"]["request_count"] == 1
    assert snapshot["metrics"]["capability_receipt_rate"] == 1.0
    assert snapshot["metrics"]["p95_latency"] >= 0
    assert snapshot["metrics"]["cost_per_tenant"]["tenant-a"] == 0
    assert snapshot["metrics"]["cost_per_capability"]["llm_completion"] == 0
    assert snapshot["metrics"]["missing_signal_count"] >= 2
    assert _validate_schema_instance(_load_schema(OBSERVABILITY_SCHEMA), snapshot) == []


def test_operator_observability_endpoints_expose_summary_and_trace() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    router = app.state.router
    router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="user-2",
        tenant_id="tenant-b",
        identity_id="actor-b",
    ))
    router.handle_message(GatewayMessage(
        message_id="msg-observe-2",
        channel="web",
        sender_id="user-2",
        body="show production witness",
    ))

    summary = client.get("/observability/summary").json()
    trace_id = summary["latest_trace_ids"][-1]
    trace = client.get(f"/observability/traces/{trace_id}").json()

    assert summary["metrics"]["request_count"] == 1
    assert trace["trace_id"] == trace_id
    assert trace["tenant_id"] == "tenant-b"
    assert trace["actor_id"] == "actor-b"
    assert trace["message_id"] == "msg-observe-2"
    assert "show production witness" not in str(trace)
    assert "observed reply" not in str(trace)
    assert [stage["name"] for stage in trace["stages"]][-1] == "terminal_certificate_emitted"


def test_trace_endpoint_fails_closed_for_unknown_trace() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)

    response = client.get("/observability/traces/trace-missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "trace not found"
    assert app.state.router.observability_snapshot()["metrics"]["request_count"] == 0
