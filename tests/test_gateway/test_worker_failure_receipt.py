"""Worker failure receipt tests.

Purpose: verify worker failures and partial completions produce explicit,
schema-valid, non-terminal recovery receipts.
Governance scope: worker failure classification, recovery action selection,
source receipt hash binding, and terminal closure discipline.
Dependencies: gateway.worker_failure_receipt, gateway.worker_mesh, and
schemas/worker_failure_receipt.schema.json.
Invariants:
  - Failure receipts cannot be minted from successful worker receipts.
  - Partial completions require safe-halt recovery by default.
  - Rejected dispatches are classified before handler execution.
  - Failure receipt payloads validate against the public schema.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from gateway.worker_failure_receipt import build_worker_failure_receipt
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
SCHEMA_PATH = ROOT / "schemas" / "worker_failure_receipt.schema.json"


def test_worker_failure_receipt_validates_partial_completion() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T13:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda _request: WorkerHandlerResult(
            status="failed",
            error="worker_timeout",
            evidence_refs=["worker:evidence:partial"],
        ),
    )
    worker_receipt = mesh.dispatch(lease.lease_id, _request())

    failure_receipt = build_worker_failure_receipt(
        worker_receipt,
        attempted_units=5,
        completed_units=2,
        generated_at="2026-06-16T13:02:00+00:00",
    )
    errors = _validate_schema_instance(_load_schema(SCHEMA_PATH), failure_receipt.to_dict())

    assert errors == []
    assert failure_receipt.receipt_version == "worker_failure_receipt.v1"
    assert failure_receipt.receipt_state == "PARTIAL_EXECUTION_RECORDED"
    assert failure_receipt.effect_status == "partial_effect_recorded"
    assert failure_receipt.rollback_required is True
    assert failure_receipt.recovery_required is True
    assert failure_receipt.failure_state == "partial_completion"
    assert failure_receipt.recovery_action == "safe_halt"
    assert failure_receipt.source_receipt_hash == worker_receipt.receipt_hash
    assert failure_receipt.terminal_closure_required is True
    assert failure_receipt.governance_guards["terminal_closure"] is False


def test_worker_failure_receipt_classifies_rejected_before_handler() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T13:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda request: calls.append(request.operation) or WorkerHandlerResult(status="succeeded"),
    )
    worker_receipt = mesh.dispatch(
        lease.lease_id,
        replace(_request(), operation="write"),
    )

    failure_receipt = build_worker_failure_receipt(
        worker_receipt,
        generated_at="2026-06-16T13:02:00+00:00",
    )

    assert calls == []
    assert worker_receipt.status == "rejected"
    assert failure_receipt.receipt_state == "FAILED_BEFORE_EXECUTION"
    assert failure_receipt.effect_status == "no_effect_confirmed"
    assert failure_receipt.solver_outcome == "GovernanceBlocked"
    assert failure_receipt.recovery_required is False
    assert failure_receipt.failure_state == "rejected_before_handler"
    assert failure_receipt.recovery_action == "no_retry"
    assert failure_receipt.receipt_is_not_terminal_closure is True


def test_worker_failure_receipt_rejects_success_source() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T13:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda _request: WorkerHandlerResult(
            status="succeeded",
            output={"accepted": True},
            evidence_refs=["worker:evidence:success"],
        ),
    )
    worker_receipt = mesh.dispatch(lease.lease_id, _request())

    with pytest.raises(ValueError, match="failed_or_rejected"):
        build_worker_failure_receipt(worker_receipt)

    assert worker_receipt.status == "succeeded"
    assert worker_receipt.receipt_hash
    assert worker_receipt.terminal_closure_required is True


def test_worker_failure_receipt_rejects_impossible_unit_counts() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-06-16T13:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda _request: WorkerHandlerResult(status="failed", error="worker_timeout"),
    )
    worker_receipt = mesh.dispatch(lease.lease_id, _request())

    with pytest.raises(ValueError, match="completed_units_exceed_attempted"):
        build_worker_failure_receipt(worker_receipt, attempted_units=1, completed_units=2)

    assert worker_receipt.status == "failed"
    assert worker_receipt.reason == "worker_timeout"
    assert worker_receipt.receipt_hash


def _lease() -> WorkerLease:
    return WorkerLease(
        worker_id="worker-failure-test",
        capability="repository.inspect_read_only",
        tenant_id="tenant-worker-failure",
        lease_id="lease-worker-failure",
        allowed_operations=["inspect"],
        forbidden_operations=["write"],
        budget=WorkerLeaseBudget(max_operations=3, max_cost=0.0),
        scope=WorkerLeaseScope(
            resource_refs=["repository:local"],
            data_classes=["repository_metadata"],
            network_allowlist=[],
        ),
        timeout_seconds=30,
        sandbox="local-read-only-repository",
        policy_refs=["policy:worker-failure-test"],
        receipt_schema_ref="urn:mullusi:schema:worker-mesh:1",
        verification_ref="verification:worker-failure-test",
        recovery_ref="recovery:operator-review",
        expires_at="2026-06-16T13:30:00+00:00",
        issued_at="2026-06-16T13:00:00+00:00",
    )


def _request() -> WorkerDispatchRequest:
    return WorkerDispatchRequest(
        request_id="worker-failure-request",
        tenant_id="tenant-worker-failure",
        capability="repository.inspect_read_only",
        operation="inspect",
        command_id="cmd-worker-failure",
        input_hash="sha256:" + "8" * 64,
        requested_at="2026-06-16T13:01:00+00:00",
    )
