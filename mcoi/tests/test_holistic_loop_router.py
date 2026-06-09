"""Purpose: verify the holistic loop read-model HTTP router.
Governance scope: read-only loop registry exposure, blocker preservation, and
default router mounting.
Dependencies: FastAPI TestClient and holistic loop router.
Invariants:
  - The HTTP surface exposes registered loops without mutation routes.
  - Missing evidence is reported as blockers, not verified closure.
  - Default router mounting includes the loop read model.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.loops import router
from mcoi_runtime.app.server_http import include_default_routers


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_loop_read_model_exposes_registered_blocked_loops() -> None:
    client = _client()

    response = client.get("/api/v1/loops/read-model")
    payload = response.json()

    assert response.status_code == 200
    assert payload["read_model_id"] == "holistic_loop_read_model"
    assert payload["status"] == "blocked"
    assert payload["blocked_count"] == 4
    assert payload["returned_count"] == 4
    assert {loop["loop_id"] for loop in payload["loops"]} == {
        "deployment_witness_loop",
        "runtime_conformance_loop",
        "cognitive_outcome_loop",
        "governed_code_change_loop",
    }
    assert all(loop["open_blockers"] for loop in payload["loops"])
    assert all(loop["evidence_bindings"] for loop in payload["loops"])
    assert all(loop["step_receipts"] for loop in payload["loops"])
    assert all(
        {binding["evidence_ref"] for binding in loop["evidence_bindings"]}
        == set(loop["required_evidence"])
        for loop in payload["loops"]
    )
    assert all(
        binding["read_only"] is True and binding["terminal_closure"] is False
        for loop in payload["loops"]
        for binding in loop["evidence_bindings"]
    )
    assert all(
        receipt["metadata"]["read_only"] is True
        and receipt["metadata"]["synthetic_projection"] is True
        and receipt["metadata"]["terminal_closure"] is False
        for loop in payload["loops"]
        for receipt in loop["step_receipts"]
    )
    assert all(
        set(receipt["errors"]) == set(loop["open_blockers"])
        for loop in payload["loops"]
        for receipt in loop["step_receipts"]
    )
    assert all(loop["closure_report"]["closed"] is False for loop in payload["loops"])
    assert all(
        set(loop["closure_report"]["unresolved_gaps"]) == set(loop["open_blockers"])
        for loop in payload["loops"]
    )
    assert payload["read_only"] is True
    assert payload["report_is_not_terminal_closure"] is True


def test_loop_read_model_limit_is_bounded_and_truncated() -> None:
    client = _client()

    response = client.get("/api/v1/loops/read-model", params={"limit": 2})
    payload = response.json()

    assert response.status_code == 200
    assert payload["returned_count"] == 2
    assert payload["total_count"] == 4
    assert payload["truncated"] is True
    assert payload["blocked_count"] == 2
    assert len(payload["loops"]) == 2


def test_loop_read_model_rejects_invalid_limit_without_server_error() -> None:
    client = _client()

    response = client.get("/api/v1/loops/read-model", params={"limit": 0})
    payload = response.json()

    assert response.status_code == 422
    assert "detail" in payload
    assert "Traceback" not in response.text


def test_loop_read_model_has_no_mutation_companion() -> None:
    client = _client()

    post_response = client.post("/api/v1/loops/read-model", json={})
    put_response = client.put("/api/v1/loops/read-model", json={})
    delete_response = client.delete("/api/v1/loops/read-model")

    assert post_response.status_code == 405
    assert put_response.status_code == 405
    assert delete_response.status_code == 405
    assert "Traceback" not in post_response.text


def test_default_router_mounts_loop_read_model() -> None:
    app = FastAPI()
    include_default_routers(app)
    client = TestClient(app)

    response = client.get("/api/v1/loops/read-model", params={"limit": 1})
    payload = response.json()

    assert response.status_code == 200
    assert payload["read_model_id"] == "holistic_loop_read_model"
    assert payload["returned_count"] == 1
    assert payload["governed"] is True
