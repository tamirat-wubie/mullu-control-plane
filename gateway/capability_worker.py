"""Gateway Capability Worker - restricted capability execution endpoint.

Purpose: Hosts the restricted worker HTTP surface used by the gateway control
    plane for dangerous capability execution.
Governance scope: signed capability request verification, bounded capability
    dispatch, signed execution receipt response.
Dependencies: FastAPI, capability isolation contracts, capability dispatcher.
Invariants:
  - Unsigned or incorrectly signed requests are rejected before dispatch.
  - Worker responses carry execution receipts with evidence references.
  - Response payloads are signed before returning to the control plane.
  - The worker executes only the request payload it can hash-verify.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from gateway.receipt_middleware import GatewayReceiptMiddleware
from gateway.capability_isolation import (
    CapabilityExecutionResponse,
    LocalCapabilityExecutionWorker,
    capability_execution_request_from_mapping,
    capability_execution_response_payload,
    sign_capability_payload,
    verify_capability_signature,
)
from gateway.capability_dispatch import (
    CapabilityDispatcher,
    CapabilityIntent,
    build_capability_dispatcher_from_platform,
)


_CAPABILITY_WORKER_ERROR_CODES = {
    "capability request body must be an object": (
        "invalid capability request body",
        "invalid_capability_request_body",
    ),
    "capability request requires boundary": (
        "invalid capability request boundary",
        "invalid_capability_request_boundary",
    ),
    "capability request requires intent": (
        "invalid capability request intent",
        "invalid_capability_request_intent",
    ),
    "capability request is malformed": (
        "malformed capability request",
        "malformed_capability_request",
    ),
    "capability request input hash mismatch": (
        "capability request input hash mismatch",
        "capability_input_hash_mismatch",
    ),
    "restricted worker requires an isolated capability boundary": (
        "isolated capability boundary required",
        "isolated_capability_boundary_required",
    ),
    "restricted worker requires isolated_worker execution plane": (
        "isolated worker execution plane required",
        "isolated_worker_execution_plane_required",
    ),
}


def _capability_worker_error_detail(exc: BaseException) -> dict[str, object]:
    error, error_code = _CAPABILITY_WORKER_ERROR_CODES.get(
        str(exc),
        ("invalid capability execution request", "invalid_capability_execution_request"),
    )
    return {"error": error, "error_code": error_code, "governed": True}


def create_capability_worker_app(
    *,
    dispatcher: CapabilityDispatcher | None = None,
    platform: Any = None,
    proof_bridge: Any | None = None,
    signing_secret: str | None = None,
    worker_id: str = "restricted-capability-worker",
) -> FastAPI:
    """Create the restricted capability worker FastAPI app."""
    secret = signing_secret if signing_secret is not None else os.environ.get("MULLU_CAPABILITY_WORKER_SECRET", "")
    if not secret:
        raise ValueError("capability worker signing secret is required")
    resolved_dispatcher = dispatcher or build_capability_dispatcher_from_platform(platform)
    resolved_proof_bridge = proof_bridge
    if resolved_proof_bridge is None and platform is not None:
        resolved_proof_bridge = getattr(platform, "proof_bridge", None)
    if resolved_proof_bridge is None:
        from mcoi_runtime.core.proof_bridge import ProofBridge

        resolved_proof_bridge = ProofBridge(clock=_utc_timestamp)
    worker = LocalCapabilityExecutionWorker(resolved_dispatcher, worker_id=worker_id)
    app = FastAPI(title="Mullu Capability Worker", version="1.0.0")
    app.add_middleware(
        GatewayReceiptMiddleware,
        proof_bridge=resolved_proof_bridge,
        certified_prefixes=("/capability/",),
    )

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "worker_id": worker_id,
            "governed": True,
        }

    @app.post("/capability/execute")
    async def execute_capability(request: Request) -> Response:
        body = await request.body()
        signature = request.headers.get("X-Mullu-Capability-Signature", "")
        if not verify_capability_signature(body, signature, secret):
            raise HTTPException(403, detail="invalid capability request signature")
        try:
            raw = json.loads(body.decode("utf-8"))
            if not isinstance(raw, dict):
                raise RuntimeError("capability request body must be an object")
            execution_request = capability_execution_request_from_mapping(raw)
            if not execution_request.boundary.isolation_required:
                raise RuntimeError("restricted worker requires an isolated capability boundary")
            if execution_request.boundary.execution_plane != "isolated_worker":
                raise RuntimeError("restricted worker requires isolated_worker execution plane")
            intent = CapabilityIntent(
                str(execution_request.intent["skill"]),
                str(execution_request.intent["action"]),
                dict(execution_request.intent.get("params", {})),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
            raise HTTPException(422, detail=_capability_worker_error_detail(exc)) from exc

        result, receipt = worker.execute(
            intent=intent,
            tenant_id=execution_request.tenant_id,
            identity_id=execution_request.identity_id,
            boundary=execution_request.boundary,
            command_id=execution_request.command_id,
            conversation_id=execution_request.conversation_id,
            metadata=execution_request.metadata,
        )
        transport_result = _transport_result(result)
        status = "succeeded" if isinstance(transport_result, dict) else "failed"
        response = CapabilityExecutionResponse(
            request_id=execution_request.request_id,
            status=status,
            result=transport_result,
            receipt=receipt,
            error="" if status == "succeeded" else "capability dispatch returned no result",
        )
        response_body = json.dumps(
            capability_execution_response_payload(response),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        response_signature = sign_capability_payload(response_body, secret)
        return Response(
            content=response_body,
            media_type="application/json",
            headers={"X-Mullu-Capability-Response-Signature": response_signature},
        )

    app.state.worker_id = worker_id
    app.state.dispatcher = resolved_dispatcher
    app.state.proof_bridge = resolved_proof_bridge
    return app


def _transport_result(result: dict[str, Any] | None) -> dict[str, Any] | None:
    """Strip local worker metadata that the control plane reattaches."""
    if not isinstance(result, dict):
        return None
    return {
        key: value
        for key, value in result.items()
        if key not in {
            "capability_execution_boundary",
            "capability_execution_receipt",
            "capability_execution_request_id",
        }
    }


def _utc_timestamp() -> str:
    """Return an ISO-8601 UTC timestamp for worker-local receipts."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _default_app() -> FastAPI:
    environment = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    secret = os.environ.get("MULLU_CAPABILITY_WORKER_SECRET", "")
    if not secret and environment in {"local_dev", "test"}:
        secret = "local-capability-worker-secret"
    dispatcher = None
    if environment in {"local_dev", "test"} and _truthy(os.environ.get("MULLU_CAPABILITY_WORKER_ENABLE_SMOKE_STUB", "")):
        dispatcher = CapabilityDispatcher(payment_executor=_SmokePaymentExecutor())
    return create_capability_worker_app(dispatcher=dispatcher, signing_secret=secret)


@dataclass(frozen=True, slots=True)
class _SmokePaymentResult:
    """Deterministic local/test payment result for signed smoke probes."""

    success: bool
    tx_id: str
    state: str
    amount: str
    currency: str
    provider_tx_id: str = ""
    requires_approval: bool = False
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class _SmokePaymentExecutor:
    """Local/test-only executor used by runtime smoke probes."""

    def initiate_payment(self, *, tenant_id, amount, currency, destination, actor_id, description=""):
        return _SmokePaymentResult(
            success=True,
            tx_id="tx-smoke-1",
            state="pending_approval",
            amount=str(amount),
            currency=currency,
            requires_approval=True,
        )

    def approve_and_execute(self, tx_id, *, approver_id="", api_key=""):
        return _SmokePaymentResult(
            success=True,
            tx_id=tx_id,
            state="settled",
            amount="50",
            currency="USD",
            provider_tx_id="provider-smoke-1",
            metadata={
                "ledger_hash": "ledger-smoke-proof",
                "recipient_hash": "recipient-smoke-proof",
                "recipient_ref": "dest:smoke",
            },
        )


def _truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


app = _default_app()
