"""Gateway worker mesh tests.

Purpose: verify worker dispatch remains lease-bound, budgeted, schema-backed,
and explicitly non-terminal.
Governance scope: worker lease admission, dispatch receipt evidence,
budget exhaustion, forbidden operations, and schema compatibility.
Dependencies: gateway.worker_mesh and schemas/worker_mesh.schema.json.
Invariants:
  - No dispatch reaches a handler without a valid active lease.
  - Forbidden operations override allowed operations.
  - Successful worker receipts require evidence refs and terminal closure.
  - Worker lease and receipt envelopes validate against the public schema.
"""

from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from gateway.worker_mesh import (
    NetworkedWorkerMesh,
    WorkerDispatchRequest,
    WorkerHandlerResult,
    WorkerLease,
    WorkerLeaseBudget,
    WorkerLeaseScope,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = ROOT / "schemas" / "worker_mesh.schema.json"


def test_worker_mesh_dispatch_emits_schema_valid_non_terminal_receipt() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(_lease(), _successful_handler)
    request = _request()
    receipt = mesh.dispatch(lease.lease_id, request)
    envelope = {"lease": asdict(lease), "request": asdict(request), "receipt": asdict(receipt)}

    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), envelope)

    assert errors == []
    assert lease.lease_hash
    assert receipt.status == "succeeded"
    assert receipt.receipt_id.startswith("worker-receipt-")
    assert receipt.terminal_closure_required is True
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True
    assert receipt.evidence_refs == ["worker:evidence:1"]
    assert envelope["request"]["estimated_cost"] == 0.0


def test_worker_mesh_rejects_forbidden_operation_before_handler() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")

    with pytest.raises(ValueError, match="operation_cannot_be_allowed_and_forbidden"):
        mesh.register_worker(
            replace(_lease(), allowed_operations=["write"], forbidden_operations=["write"]),
            lambda request: calls.append(request.operation) or _successful_handler(request),
        )

    assert calls == []


def test_worker_mesh_rejects_tenant_and_capability_mismatch() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(_lease(), _successful_handler)

    tenant_receipt = mesh.dispatch(lease.lease_id, replace(_request(), tenant_id="tenant-2"))
    capability_receipt = mesh.dispatch(lease.lease_id, replace(_request(), capability="docs.read"))

    assert tenant_receipt.status == "rejected"
    assert tenant_receipt.reason == "tenant_mismatch"
    assert capability_receipt.status == "rejected"
    assert capability_receipt.reason == "capability_mismatch"
    assert tenant_receipt.worker_id == "worker-1"
    assert capability_receipt.worker_id == "worker-1"


def test_worker_mesh_enforces_operation_and_cost_budgets() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        replace(_lease(), budget=WorkerLeaseBudget(max_operations=5, max_cost=1.0)),
        lambda _request: WorkerHandlerResult(
            status="succeeded",
            output={"accepted": True},
            evidence_refs=["worker:evidence:1"],
            cost=1.0,
        ),
    )

    first_receipt = mesh.dispatch(lease.lease_id, _request())
    second_receipt = mesh.dispatch(lease.lease_id, replace(_request(), request_id="worker-request-2"))
    read_model = mesh.read_model()

    assert first_receipt.status == "succeeded"
    assert second_receipt.status == "rejected"
    assert second_receipt.reason == "cost_budget_exhausted"
    assert read_model["worker_count"] == 1
    assert read_model["workers"][0]["operation_count"] == 1
    assert read_model["workers"][0]["cost_used"] == 1.0


def test_worker_mesh_rejects_negative_estimated_cost() -> None:
    with pytest.raises(ValueError) as exc:
        replace(_request(), estimated_cost=-0.01)

    assert str(exc.value) == "nonnegative_estimated_cost_required"
    assert WorkerLeaseBudget(max_operations=1, max_cost=0.0).max_operations == 1
    assert WorkerLeaseBudget(max_operations=1, max_cost=0.0).max_cost == 0.0


def test_worker_mesh_requires_evidence_for_successful_handler() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda _request: WorkerHandlerResult(status="succeeded", output={"accepted": True}),
    )

    receipt = mesh.dispatch(lease.lease_id, _request())

    assert receipt.status == "failed"
    assert receipt.reason == "worker_evidence_required"
    assert receipt.evidence_refs == []
    assert receipt.output_hash
    assert receipt.terminal_closure_required is True
    assert receipt.metadata["receipt_is_not_terminal_closure"] is True


def test_worker_mesh_fails_invalid_worker_status_before_receipt_publication() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda _request: WorkerHandlerResult(
            status="unknown",
            output={"accepted": True},
            evidence_refs=["worker:evidence:1"],
        ),
    )

    receipt = mesh.dispatch(lease.lease_id, _request())

    assert receipt.status == "failed"
    assert receipt.reason == "worker_status_invalid"
    assert receipt.metadata["worker_receipt_status"] == "failed"
    assert receipt.evidence_refs == ["worker:evidence:1"]
    assert receipt.terminal_closure_required is True


def test_worker_mesh_rejects_invalid_or_expired_leases() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")

    with pytest.raises(ValueError) as exc:
        mesh.register_worker(
            replace(_lease(), expires_at="2026-05-04T11:59:00+00:00"),
            _successful_handler,
        )
    expired = mesh.register_worker(
        replace(_lease(), lease_id="lease-expired", expires_at="2026-05-04T12:00:30+00:00"),
        _successful_handler,
    )
    receipt = mesh.dispatch(expired.lease_id, _request())

    assert str(exc.value) == "lease_expiry_must_follow_issue"
    assert receipt.status == "rejected"
    assert receipt.reason == "lease_expired"
    assert receipt.worker_id == "worker-1"
    assert receipt.receipt_hash
    assert receipt.terminal_closure_required is True


def test_worker_mesh_schema_rejects_terminal_closure_claim() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(_lease(), _successful_handler)
    request = _request()
    receipt = mesh.dispatch(lease.lease_id, request)
    envelope = {
        "lease": asdict(lease),
        "request": asdict(request),
        "receipt": {**asdict(receipt), "terminal_closure_required": False},
    }

    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), envelope)

    assert len(errors) == 1
    assert "$.receipt.terminal_closure_required" in errors[0]
    assert "expected" in errors[0]
    assert "True" in errors[0]
    assert envelope["receipt"]["receipt_id"].startswith("worker-receipt-")


def _lease() -> WorkerLease:
    return WorkerLease(
        worker_id="worker-1",
        capability="docs.write",
        tenant_id="tenant-1",
        lease_id="lease-1",
        allowed_operations=["draft"],
        forbidden_operations=[],
        budget=WorkerLeaseBudget(max_operations=2, max_cost=0.0),
        scope=WorkerLeaseScope(
            resource_refs=["doc:1"],
            data_classes=["workspace_doc"],
            network_allowlist=["docs.mullusi.com"],
        ),
        timeout_seconds=30,
        sandbox="restricted",
        policy_refs=["policy:worker:1"],
        receipt_schema_ref="urn:mullusi:schema:worker-mesh:1",
        verification_ref="verification:worker:1",
        recovery_ref="recovery:manual-review",
        expires_at="2026-05-04T12:30:00+00:00",
        issued_at="2026-05-04T12:00:00+00:00",
    )


def _request() -> WorkerDispatchRequest:
    return WorkerDispatchRequest(
        request_id="worker-request-1",
        tenant_id="tenant-1",
        capability="docs.write",
        operation="draft",
        command_id="cmd-1",
        input_hash="sha256:" + "1" * 64,
        payload={"title": "Draft"},
        requested_at="2026-05-04T12:00:30+00:00",
    )


def _successful_handler(_request: WorkerDispatchRequest) -> WorkerHandlerResult:
    return WorkerHandlerResult(
        status="succeeded",
        output={"accepted": True},
        evidence_refs=["worker:evidence:1"],
    )
