"""Shared helpers for data-plane sub-routers."""
from __future__ import annotations

from mcoi_runtime.app.routers.deps import deps


def _data_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _certify_action_proof(
    *,
    endpoint: str,
    tenant_id: str,
    actor_id: str,
    target: str,
    action: str,
    succeeded: bool,
) -> dict[str, object]:
    """Certify a data-plane action response with a proof bridge receipt."""
    proof = deps.proof_bridge.certify_governance_decision(
        tenant_id=tenant_id or "system",
        endpoint=endpoint,
        guard_results=[
            {
                "guard_name": "data_action_closure",
                "allowed": True,
                "reason": "data action reached response boundary",
            }
        ],
        decision="allowed",
        actor_id=actor_id or "anonymous",
        reason="data action response certified",
    )
    return {
        "endpoint": endpoint,
        "target": target,
        "proof_phase": action,
        "succeeded": succeeded,
        "proof_receipt_id": proof.capsule.receipt.receipt_id,
        "proof_hash": proof.receipt_hash,
    }
