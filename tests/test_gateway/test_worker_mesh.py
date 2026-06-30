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
    PHYSICAL_ACTION_RECEIPT_PAYLOAD_KEY,
    NetworkedWorkerMesh,
    WorkerDispatchRequest,
    WorkerHandlerResult,
    WorkerLease,
    WorkerLeaseBudget,
    WorkerLeaseScope,
)
from gateway.physical_action_boundary import PhysicalActionBoundary, PhysicalActionRequest
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


def test_worker_mesh_rejects_schema_misaligned_lease_fields() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")

    with pytest.raises(ValueError, match="resource_refs_0_required"):
        replace(
            _lease(),
            scope=WorkerLeaseScope(resource_refs=[""], data_classes=[], network_allowlist=[]),
        )

    with pytest.raises(ValueError, match="allowed_operations_0_required"):
        replace(_lease(), allowed_operations=[" "])

    with pytest.raises(ValueError, match="policy_refs_0_required"):
        replace(_lease(), policy_refs=[""])

    with pytest.raises(ValueError, match="receipt_schema_ref_invalid"):
        mesh.register_worker(
            replace(_lease(), receipt_schema_ref="urn:mullusi:schema:other-worker:1"),
            _successful_handler,
        )


def test_worker_mesh_binds_physical_receipt_to_dispatch_identity() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        replace(
            _lease(),
            capability="physical.sandbox_replay",
            allowed_operations=["sandbox_replay"],
            physical_action_boundary_required=True,
        ),
        lambda request: calls.append(request.request_id) or _successful_handler(request),
    )
    receipt = PhysicalActionBoundary().evaluate(_physical_request()).to_json_dict()
    mismatched_tenant_receipt = {**receipt, "tenant_id": "tenant-other"}
    tenant_mismatch = mesh.dispatch(
        lease.lease_id,
        replace(
            _physical_dispatch_request(),
            payload={PHYSICAL_ACTION_RECEIPT_PAYLOAD_KEY: mismatched_tenant_receipt},
        ),
    )
    command_mismatch = mesh.dispatch(
        lease.lease_id,
        replace(
            _physical_dispatch_request(),
            command_id="cmd-other",
            payload={PHYSICAL_ACTION_RECEIPT_PAYLOAD_KEY: receipt},
        ),
    )

    assert calls == []
    assert tenant_mismatch.status == "rejected"
    assert tenant_mismatch.reason == "physical_action_receipt_tenant_mismatch"
    assert command_mismatch.status == "rejected"
    assert command_mismatch.reason == "physical_action_receipt_command_mismatch"


def test_worker_mesh_rejects_tampered_physical_receipt_hash() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        replace(
            _lease(),
            capability="physical.sandbox_replay",
            allowed_operations=["sandbox_replay"],
            physical_action_boundary_required=True,
        ),
        lambda request: calls.append(request.request_id) or _successful_handler(request),
    )
    receipt = PhysicalActionBoundary().evaluate(_physical_request()).to_json_dict()
    tampered_receipt = {**receipt, "actuator_id": "actuator:tampered"}

    dispatch_receipt = mesh.dispatch(
        lease.lease_id,
        replace(
            _physical_dispatch_request(),
            payload={PHYSICAL_ACTION_RECEIPT_PAYLOAD_KEY: tampered_receipt},
        ),
    )

    assert calls == []
    assert dispatch_receipt.status == "rejected"
    assert dispatch_receipt.reason == "physical_action_receipt_hash_mismatch"
    assert dispatch_receipt.metadata["physical_action_receipt_validated"] is False


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


def test_worker_mesh_rejects_stale_resource_versions_before_handler() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    versioned_scope = WorkerLeaseScope(
        resource_refs=["doc:1"],
        data_classes=["workspace_doc"],
        network_allowlist=[],
        resource_versions={"doc:1": "version:1"},
        access_mode="WRITE",
        conflict_class="WRITE_EXCLUSIVE",
    )
    lease = mesh.register_worker(
        replace(_lease(), scope=versioned_scope, minimum_evidence_stage="VALIDATED"),
        lambda request: calls.append(request.request_id)
        or WorkerHandlerResult(
            status="succeeded",
            output={"accepted": True},
            evidence_refs=["worker:evidence:versioned"],
            evidence_stage="VALIDATED",
            resource_versions_after={"doc:1": "version:2"},
            candidate_delta_hash="sha256:" + "a" * 64,
            validation_refs=["validator:resource-version"],
        ),
    )

    missing_receipt = mesh.dispatch(
        lease.lease_id,
        replace(_request(), request_id="worker-request-missing-version"),
    )
    stale_receipt = mesh.dispatch(
        lease.lease_id,
        replace(
            _request(),
            request_id="worker-request-stale-version",
            resource_versions={"doc:1": "version:0"},
        ),
    )
    accepted_receipt = mesh.dispatch(
        lease.lease_id,
        replace(
            _request(),
            request_id="worker-request-current-version",
            resource_versions={"doc:1": "version:1"},
        ),
    )

    assert calls == ["worker-request-current-version"]
    assert missing_receipt.reason == "resource_version_required"
    assert stale_receipt.reason == "resource_version_mismatch"
    assert accepted_receipt.status == "succeeded"
    assert accepted_receipt.resource_versions_before == {"doc:1": "version:1"}
    assert accepted_receipt.resource_versions_after == {"doc:1": "version:2"}


def test_worker_mesh_blocks_duplicate_idempotency_key_before_handler() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda request: calls.append(request.request_id) or _successful_handler(request),
    )
    first_request = replace(
        _request(),
        idempotency_key="draft-doc-1",
        idempotency_class="SAFE_WITH_KEY",
    )
    duplicate_request = replace(first_request, request_id="worker-request-duplicate")

    first_receipt = mesh.dispatch(lease.lease_id, first_request)
    duplicate_receipt = mesh.dispatch(lease.lease_id, duplicate_request)
    read_model = mesh.read_model()

    assert first_receipt.status == "succeeded"
    assert duplicate_receipt.status == "rejected"
    assert duplicate_receipt.reason == "duplicate_idempotency_key"
    assert calls == ["worker-request-1"]
    assert read_model["workers"][0]["operation_count"] == 1
    assert read_model["workers"][0]["idempotency_key_count"] == 1


def test_worker_mesh_requires_commit_ready_progressive_evidence() -> None:
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        replace(_lease(), minimum_evidence_stage="VALIDATED"),
        lambda _request: WorkerHandlerResult(
            status="succeeded",
            output={"accepted": True},
            evidence_refs=["worker:evidence:checkpoint"],
            evidence_stage="CHECKPOINT",
        ),
    )

    receipt = mesh.dispatch(lease.lease_id, _request())

    assert receipt.status == "failed"
    assert receipt.reason == "worker_progressive_evidence_incomplete"
    assert receipt.evidence_stage == "CHECKPOINT"
    assert receipt.progressive_evidence_complete is False
    assert receipt.metadata["minimum_evidence_stage"] == "VALIDATED"
    assert receipt.metadata["progressive_evidence_complete"] is False


def test_worker_mesh_conflict_freezes_until_repair_receipt() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda request: calls.append(request.request_id) or _successful_handler(request),
    )

    conflict = mesh.record_conflict(
        lease.lease_id,
        conflict_ref="conflict://doc/1/version-fork",
        scope="RESOURCE_BRANCH",
    )
    frozen = mesh.dispatch(lease.lease_id, replace(_request(), request_id="worker-request-frozen"))
    repair = mesh.resolve_conflict(
        lease.lease_id,
        repair_ref="repair://doc/1/rebased",
    )
    resumed = mesh.dispatch(lease.lease_id, replace(_request(), request_id="worker-request-resumed"))
    read_model = mesh.read_model()

    assert conflict["status"] == "recorded"
    assert frozen.status == "rejected"
    assert frozen.reason == "unresolved_conflict"
    assert repair["metadata"]["resolved_conflict_refs"] == ["conflict://doc/1/version-fork"]
    assert resumed.status == "succeeded"
    assert calls == ["worker-request-resumed"]
    assert read_model["workers"][0]["repair_refs"] == ["repair://doc/1/rebased"]


def test_worker_mesh_cancellation_blocks_late_worker_action() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda request: calls.append(request.request_id) or _successful_handler(request),
    )

    cancellation = mesh.cancel_lease(
        lease.lease_id,
        reason="operator_superseded_goal",
        cancelled_at="2026-05-04T12:02:00+00:00",
    )
    receipt = mesh.dispatch(lease.lease_id, _request())
    read_model = mesh.read_model()

    assert cancellation["status"] == "recorded"
    assert cancellation["reason"] == "lease_cancelled"
    assert receipt.status == "rejected"
    assert receipt.reason == "lease_cancelled"
    assert calls == []
    assert read_model["workers"][0]["status"] == "cancelled"
    assert read_model["backpressure"]["cancelled_leases"] == [lease.lease_id]


def test_worker_mesh_requires_approval_and_safe_retry_for_irreversible_effects() -> None:
    calls: list[str] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T12:01:00+00:00")
    lease = mesh.register_worker(
        _lease(),
        lambda request: calls.append(request.request_id) or _successful_handler(request),
    )

    missing_approval = mesh.dispatch(
        lease.lease_id,
        replace(
            _request(),
            request_id="worker-request-irreversible-missing-approval",
            side_effect_class="EXTERNAL_IRREVERSIBLE",
            idempotency_class="MANUAL_RETRY_ONLY",
        ),
    )
    unsafe_retry = mesh.dispatch(
        lease.lease_id,
        replace(
            _request(),
            request_id="worker-request-irreversible-unsafe-retry",
            side_effect_class="EXTERNAL_IRREVERSIBLE",
            approval_ref="approval://operator/1",
            idempotency_class="SAFE_REPEAT",
        ),
    )
    approved = mesh.dispatch(
        lease.lease_id,
        replace(
            _request(),
            request_id="worker-request-irreversible-approved",
            side_effect_class="EXTERNAL_IRREVERSIBLE",
            approval_ref="approval://operator/1",
            idempotency_class="MANUAL_RETRY_ONLY",
        ),
    )

    assert missing_approval.status == "rejected"
    assert missing_approval.reason == "approval_ref_required_for_irreversible_side_effect"
    assert unsafe_retry.status == "rejected"
    assert unsafe_retry.reason == "irreversible_retry_policy_invalid"
    assert approved.status == "succeeded"
    assert approved.side_effect_class == "EXTERNAL_IRREVERSIBLE"
    assert calls == ["worker-request-irreversible-approved"]


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


def _physical_request() -> PhysicalActionRequest:
    return PhysicalActionRequest(
        request_id="physical-action-test",
        tenant_id="tenant-1",
        command_id="cmd-1",
        actuator_id="actuator:sandbox-1",
        action="sandbox_replay",
        effect_mode="sandbox",
        safety_envelope_ref="safety-envelope:test",
        environment_ref="environment:sandbox",
        risk_level="high",
        simulation_passed=True,
        operator_approval_ref="approval:test",
        manual_override_ref="manual-override:test",
        emergency_stop_ref="emergency-stop:test",
        sensor_confirmation_ref="sensor:test",
        evidence_refs=("proof://physical/simulation",),
    )


def _physical_dispatch_request() -> WorkerDispatchRequest:
    return WorkerDispatchRequest(
        request_id="physical-worker-request-1",
        tenant_id="tenant-1",
        capability="physical.sandbox_replay",
        operation="sandbox_replay",
        command_id="cmd-1",
        input_hash="sha256:" + "2" * 64,
        payload={},
        requested_at="2026-05-04T12:00:30+00:00",
    )
