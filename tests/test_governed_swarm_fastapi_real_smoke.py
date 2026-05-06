"""Optional real FastAPI smoke test for governed swarm routing.

Purpose: verify the enabled governed swarm router works through FastAPI and
TestClient when gateway dependencies are installed.
Governance scope: real HTTP adapter boundary, explicit runtime path bridge,
append-only audit persistence, and governed response envelopes.
Dependencies: optional fastapi/httpx stack, governed swarm runtime path, and
control-plane integration bridge.
Invariants: HTTP calls preserve the same governed envelope semantics as the
framework-neutral runtime and do not bypass audit persistence.
"""

from __future__ import annotations

from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
testclient_module = pytest.importorskip("fastapi.testclient")

from mcoi_runtime.app.governed_swarm_integration import extend_runtime_package_path  # noqa: E402  # noqa: E402


def _payload() -> dict[str, object]:
    return {
        "run_id": "run_real_fastapi_invoice_001",
        "goal_id": "goal_real_fastapi_invoice_001",
        "tenant_id": "tenant_a",
        "invoice_ref": "invoice_real_fastapi_001",
        "invoice_amount_usd": "88.00",
        "vendor_verified": True,
        "duplicate_found": False,
        "budget_available": True,
        "policy_requires_approval": True,
        "human_approved": True,
    }


def test_real_fastapi_router_serves_governed_invoice_run(tmp_path: Path) -> None:
    runtime_root = Path(__file__).resolve().parents[1].parent / "mcoi"
    extend_runtime_package_path(runtime_root)
    from mcoi_runtime.swarm import InvoiceSwarmRuntime, create_fastapi_router

    app = fastapi.FastAPI()
    runtime = InvoiceSwarmRuntime.from_path(tmp_path / "swarm-runs.jsonl")
    app.include_router(create_fastapi_router(runtime))
    client = testclient_module.TestClient(app)

    run_response = client.post("/api/v1/swarm/invoice-runs", json=_payload())
    get_response = client.get("/api/v1/swarm/runs/run_real_fastapi_invoice_001")
    list_response = client.get("/api/v1/swarm/runs")

    assert run_response.status_code == 200
    assert run_response.json()["governed"] is True
    assert run_response.json()["status"] == "closed"
    assert get_response.status_code == 200
    assert get_response.json()["payload"]["record"]["run_id"] == "run_real_fastapi_invoice_001"
    assert list_response.status_code == 200
    assert list_response.json()["payload"]["count"] == 1

