"""Physical worker canary.

Purpose: prove that physical-capability workers fail closed without a
    physical-action receipt and execute only a sandbox replay when the boundary
    receipt is valid.
Governance scope: worker lease admission, physical-action boundary receipts,
    sandbox-only dispatch, and non-terminal worker receipts.
Dependencies: physical_action_boundary, worker_mesh, and command-spine hashing.
Invariants:
  - A missing physical-action receipt blocks before handler execution.
  - An admitted sandbox replay calls the handler exactly once.
  - The sandbox handler reports that no physical effect was applied.
  - The canary artifact is hash-bound for runtime conformance.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping

from gateway.command_spine import canonical_hash
from gateway.physical_action_boundary import PhysicalActionBoundary, PhysicalActionRequest
from gateway.worker_mesh import (
    PHYSICAL_ACTION_RECEIPT_PAYLOAD_KEY,
    NetworkedWorkerMesh,
    WorkerDispatchRequest,
    WorkerHandlerResult,
    WorkerLease,
    WorkerLeaseBudget,
    WorkerLeaseScope,
)


@dataclass(frozen=True, slots=True)
class PhysicalWorkerCanaryArtifact:
    """Hash-bound canary artifact projected into runtime conformance."""

    canary_id: str
    status: str
    blockers: tuple[str, ...]
    boundary_receipt: dict[str, Any]
    blocked_dispatch_receipt: dict[str, Any]
    worker_mesh_envelope: dict[str, Any]
    sandbox_output: dict[str, Any]
    handler_calls: int
    evidence_refs: tuple[str, ...]
    artifact_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        """Return whether the canary satisfied every invariant."""
        return self.status == "passed" and not self.blockers

    def to_json_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible canary artifact."""
        return _json_ready(asdict(self))


def run_physical_worker_canary() -> PhysicalWorkerCanaryArtifact:
    """Run the sandbox physical worker canary and return its artifact."""
    calls: list[dict[str, Any]] = []
    mesh = NetworkedWorkerMesh(clock=lambda: "2026-05-04T15:00:00+00:00")
    lease = mesh.register_worker(_lease(), lambda request: _sandbox_handler(request, calls))

    blocked_request = _dispatch_request(request_id="physical-canary-missing-receipt")
    blocked_receipt = mesh.dispatch(lease.lease_id, blocked_request)

    boundary_receipt = PhysicalActionBoundary().evaluate(_physical_request())
    admitted_request = _dispatch_request(
        request_id="physical-canary-admitted",
        payload={PHYSICAL_ACTION_RECEIPT_PAYLOAD_KEY: boundary_receipt.to_json_dict()},
    )
    admitted_receipt = mesh.dispatch(lease.lease_id, admitted_request)
    sandbox_output = dict(calls[0]) if calls else {}

    blockers = _canary_blockers(
        boundary_receipt=boundary_receipt.to_json_dict(),
        blocked_dispatch_receipt=asdict(blocked_receipt),
        admitted_dispatch_receipt=asdict(admitted_receipt),
        sandbox_output=sandbox_output,
        handler_calls=len(calls),
    )
    evidence_refs = (
        f"physical_action_receipt:{boundary_receipt.receipt_id}",
        f"worker_dispatch_receipt:{blocked_receipt.receipt_id}",
        f"worker_dispatch_receipt:{admitted_receipt.receipt_id}",
    )
    artifact = PhysicalWorkerCanaryArtifact(
        canary_id="pending",
        status="passed" if not blockers else "failed",
        blockers=tuple(blockers),
        boundary_receipt=boundary_receipt.to_json_dict(),
        blocked_dispatch_receipt=asdict(blocked_receipt),
        worker_mesh_envelope={
            "lease": asdict(lease),
            "request": asdict(admitted_request),
            "receipt": asdict(admitted_receipt),
        },
        sandbox_output=sandbox_output,
        handler_calls=len(calls),
        evidence_refs=evidence_refs,
        metadata={
            "physical_worker_claim": "sandbox_only",
            "production_admissible": False,
            "no_physical_effect_applied": sandbox_output.get("physical_effect_applied") is False,
        },
    )
    artifact_hash = canonical_hash(asdict(replace(artifact, canary_id="pending", artifact_hash="")))
    return replace(
        artifact,
        canary_id=f"physical-worker-canary-{artifact_hash[:16]}",
        artifact_hash=artifact_hash,
    )


def _lease() -> WorkerLease:
    return WorkerLease(
        worker_id="physical-worker-canary",
        capability="physical.sandbox_replay",
        tenant_id="tenant-physical-canary",
        lease_id="physical-lease-canary",
        allowed_operations=["sandbox_replay"],
        forbidden_operations=["dispatch_live_signal"],
        budget=WorkerLeaseBudget(max_operations=2, max_cost=0.0),
        scope=WorkerLeaseScope(
            resource_refs=["actuator:sandbox-door-1"],
            data_classes=["physical_control"],
            network_allowlist=[],
        ),
        timeout_seconds=10,
        sandbox="physical-sandbox",
        policy_refs=["policy:physical-safety-envelope"],
        receipt_schema_ref="urn:mullusi:schema:worker-mesh:1",
        verification_ref="verification:physical-worker-canary",
        recovery_ref="recovery:operator-review",
        expires_at="2026-05-04T15:05:00+00:00",
        issued_at="2026-05-04T14:59:00+00:00",
        physical_action_boundary_required=True,
    )


def _physical_request() -> PhysicalActionRequest:
    return PhysicalActionRequest(
        request_id="physical-action-canary",
        tenant_id="tenant-physical-canary",
        command_id="cmd-physical-canary",
        actuator_id="actuator:sandbox-door-1",
        action="sandbox_replay",
        effect_mode="sandbox",
        safety_envelope_ref="safety-envelope:physical-canary",
        environment_ref="environment:physical-sandbox",
        risk_level="high",
        simulation_passed=True,
        operator_approval_ref="approval:physical-canary",
        manual_override_ref="manual-override:physical-canary",
        emergency_stop_ref="emergency-stop:physical-canary",
        sensor_confirmation_ref="sensor-confirmation:physical-canary",
        evidence_refs=(
            "proof://physical/simulation-pass",
            "proof://physical/manual-override",
            "proof://physical/emergency-stop",
            "proof://physical/sensor-confirmation",
        ),
    )


def _dispatch_request(
    *,
    request_id: str,
    payload: dict[str, Any] | None = None,
) -> WorkerDispatchRequest:
    return WorkerDispatchRequest(
        request_id=request_id,
        tenant_id="tenant-physical-canary",
        capability="physical.sandbox_replay",
        operation="sandbox_replay",
        command_id="cmd-physical-canary",
        input_hash="sha256:" + "7" * 64,
        payload=payload or {},
        requested_at="2026-05-04T15:00:00+00:00",
    )


def _sandbox_handler(request: WorkerDispatchRequest, calls: list[dict[str, Any]]) -> WorkerHandlerResult:
    output = {
        "request_id": request.request_id,
        "sandbox_replay": True,
        "physical_effect_applied": False,
        "actuator_command_dispatched": False,
    }
    calls.append(output)
    return WorkerHandlerResult(
        status="succeeded",
        output=output,
        evidence_refs=[
            "physical-worker-canary:sandbox-handler",
            f"physical-worker-canary:request:{request.request_id}",
        ],
    )


def _canary_blockers(
    *,
    boundary_receipt: dict[str, Any],
    blocked_dispatch_receipt: dict[str, Any],
    admitted_dispatch_receipt: dict[str, Any],
    sandbox_output: dict[str, Any],
    handler_calls: int,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if boundary_receipt.get("status") != "allowed":
        blockers.append("physical_boundary_receipt_not_allowed")
    if blocked_dispatch_receipt.get("status") != "rejected":
        blockers.append("missing_receipt_did_not_reject")
    if blocked_dispatch_receipt.get("reason") != "physical_action_receipt_required":
        blockers.append("missing_receipt_reason_not_preserved")
    if admitted_dispatch_receipt.get("status") != "succeeded":
        blockers.append("admitted_physical_dispatch_not_succeeded")
    if handler_calls != 1:
        blockers.append("physical_handler_call_count_invalid")
    if sandbox_output.get("physical_effect_applied") is not False:
        blockers.append("sandbox_physical_effect_not_blocked")
    if admitted_dispatch_receipt.get("metadata", {}).get("physical_action_receipt_validated") is not True:
        blockers.append("worker_mesh_did_not_mark_physical_receipt_validation")
    return tuple(blockers)


def _json_ready(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, tuple | list):
        return [_json_ready(item) for item in value]
    return value
