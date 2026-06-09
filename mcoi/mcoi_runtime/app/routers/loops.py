"""Purpose: expose governed loop contract summaries as a read-only HTTP surface.
Governance scope: holistic loop manifests, blocker-aware status, and bounded
read-model projection.
Dependencies: FastAPI and the holistic loop registry.
Invariants:
  - Route handlers do not execute or mutate registered loops.
  - Missing required evidence remains visible as blockers.
  - Output is bounded and explicitly non-terminal.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from mcoi_runtime.core.holistic_loop_registry import build_default_loop_read_model

router = APIRouter(prefix="/api/v1/loops", tags=["loops"])


@router.get("/read-model")
def holistic_loop_read_model(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """Return the bounded holistic loop read model without changing behavior."""

    try:
        read_model = build_default_loop_read_model(limit=limit)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid loop read-model request",
                "error_code": "invalid_loop_read_model_request",
                "governed": True,
            },
        ) from exc
    loops = read_model.to_json_dict()["loops"]
    blocked_count = sum(1 for loop in loops if loop["status"] == "blocked")
    verified_count = sum(1 for loop in loops if loop["status"] == "verified")
    return {
        "read_model_id": "holistic_loop_read_model",
        "read_model_version": "holistic_loop_kernel.v1",
        "generated_at": read_model.generated_at,
        "status": "blocked" if blocked_count else "verified",
        "loops": loops,
        "total_count": read_model.total_count,
        "returned_count": read_model.returned_count,
        "blocked_count": blocked_count,
        "verified_count": verified_count,
        "truncated": read_model.truncated,
        "governed": True,
        "read_only": True,
        "report_is_not_terminal_closure": True,
        "terminal_closure_required": True,
    }
