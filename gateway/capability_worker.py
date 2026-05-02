"""Gateway Capability Worker - restricted capability execution endpoint.

Purpose: Hosts the restricted worker HTTP surface used by the gateway control
    plane for dangerous capability execution.
Governance scope: signed capability request verification, bounded skill
    dispatch, signed execution receipt response.
Dependencies: FastAPI, capability isolation contracts, skill dispatcher.
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
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from gateway.capability_isolation import (
    CapabilityExecutionResponse,
    LocalCapabilityExecutionWorker,
    capability_execution_request_from_mapping,
    capability_execution_response_payload,
    sign_capability_payload,
    verify_capability_signature,
)
from gateway.skill_dispatch import SkillDispatcher, SkillIntent, build_skill_dispatcher_from_platform


def create_capability_worker_app(
    *,
    dispatcher: SkillDispatcher | None = None,
    platform: Any = None,
    signing_secret: str | None = None,
    worker_id: str = "restricted-capability-worker",
) -> FastAPI:
    """Create the restricted capability worker FastAPI app."""
    secret = signing_secret if signing_secret is not None else os.environ.get("MULLU_CAPABILITY_WORKER_SECRET", "")
    if not secret:
        raise ValueError("capability worker signing secret is required")
    resolved_dispatcher = dispatcher or build_skill_dispatcher_from_platform(platform)
    worker = LocalCapabilityExecutionWorker(resolved_dispatcher, worker_id=worker_id)
    app = FastAPI(title="Mullu Capability Worker", version="1.0.0")

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
            intent = SkillIntent(
                str(execution_request.intent["skill"]),
                str(execution_request.intent["action"]),
                dict(execution_request.intent.get("params", {})),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, RuntimeError) as exc:
            raise HTTPException(422, detail=str(exc)) from exc

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


def _default_app() -> FastAPI:
    environment = os.environ.get("MULLU_ENV", "local_dev").strip().lower()
    secret = os.environ.get("MULLU_CAPABILITY_WORKER_SECRET", "")
    if not secret and environment in {"local_dev", "test"}:
        secret = "local-capability-worker-secret"
    dispatcher = None
    if environment in {"local_dev", "test"} and _truthy(os.environ.get("MULLU_CAPABILITY_WORKER_ENABLE_SMOKE_STUB", "")):
        dispatcher = SkillDispatcher(payment_executor=_SmokePaymentExecutor())
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
