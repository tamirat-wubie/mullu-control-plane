"""Shared helpers for LLM sub-routers."""
from __future__ import annotations

from typing import Any, NoReturn

from fastapi import HTTPException

from mcoi_runtime.app.routers.deps import deps


def _validate_or_raise(schema_id: str, data: dict[str, Any]) -> None:
    """Validate request data against a schema; raise 422 if invalid."""
    result = deps.input_validator.validate(schema_id, data)
    if not result.valid:
        raise HTTPException(422, detail={
            "error": "Validation failed",
            "validation_errors": result.to_dict()["errors"],
            "governed": True,
        })


def _raise_llm_service_unavailable(
    *,
    action: str,
    actor_id: str,
    tenant_id: str,
    target: str,
    exc: Exception,
) -> NoReturn:
    """Record internal LLM route failures and raise a sanitized HTTP error."""
    deps.llm_circuit.record_failure()
    deps.metrics.inc("errors_total")
    deps.audit_trail.record(
        action=action,
        actor_id=actor_id,
        tenant_id=tenant_id,
        target=target,
        outcome="error",
        detail={
            "error_type": type(exc).__name__,
            "reason": "llm_service_unavailable",
        },
    )
    raise HTTPException(
        503,
        detail={
            "error": "LLM service unavailable",
            "error_code": "llm_service_unavailable",
            "governed": True,
        },
    )


def _raise_governed_http_error(
    *,
    status_code: int,
    error: str,
    error_code: str,
) -> NoReturn:
    """Raise a structured governed HTTP error."""
    raise HTTPException(
        status_code,
        detail={
            "error": error,
            "error_code": error_code,
            "governed": True,
        },
    )


def _certify_action_proof(
    *,
    endpoint: str,
    tenant_id: str,
    actor_id: str,
    action: str,
    succeeded: bool,
) -> dict[str, str]:
    """Create a bounded response proof for a completed LLM action."""
    proof = deps.proof_bridge.certify_governance_decision(
        tenant_id=tenant_id or "system",
        endpoint=endpoint,
        guard_results=[
            {
                "guard_name": "llm_action_result",
                "allowed": succeeded,
                "reason": "llm action reached response boundary",
            }
        ],
        decision="allowed" if succeeded else "denied",
        actor_id=actor_id or "anonymous",
        reason="llm action response certified",
    )
    return {
        "proof_receipt_id": proof.capsule.receipt.receipt_id,
        "proof_hash": proof.receipt_hash,
        "proof_phase": action,
        "action": action,
        "succeeded": succeeded,
    }
