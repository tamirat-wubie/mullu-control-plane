"""Replay determinism endpoints.

Purpose: expose read-only deterministic replay reports for completed traces.
Governance scope: completed ReplayTrace reconstruction using bounded local
operation specifications only.
Dependencies: FastAPI, replay recorder dependency, replay determinism harness.
Invariants: missing traces fail closed; operation specs cannot invoke external
effects; replay reports carry deterministic hashes and bounded reason codes.
"""

from __future__ import annotations

from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.replay_determinism_harness import ReplayDeterminismHarness

router = APIRouter()

OperationKind = Literal["add_numbers", "echo_field", "constant_object"]


class ReplayOperationSpec(BaseModel):
    kind: OperationKind
    left_field: str = "a"
    right_field: str = "b"
    result_field: str = "result"
    field: str = "value"
    value: dict[str, Any] = Field(default_factory=dict)


class ReplayDeterminismRequest(BaseModel):
    operations: dict[str, ReplayOperationSpec] = Field(default_factory=dict)
    replay_id: str = ""


def _operation_from_spec(spec: ReplayOperationSpec) -> Callable[[dict[str, Any]], dict[str, Any]]:
    if spec.kind == "add_numbers":
        return lambda payload: {
            spec.result_field: payload[spec.left_field] + payload[spec.right_field],
        }
    if spec.kind == "echo_field":
        return lambda payload: {spec.field: payload[spec.field]}
    if spec.kind == "constant_object":
        return lambda _payload: dict(spec.value)
    raise ValueError("unsupported replay operation kind")


@router.post("/api/v1/replay/{trace_id}/determinism")
def replay_determinism_report(trace_id: str, req: ReplayDeterminismRequest) -> dict[str, Any]:
    """Replay a completed trace with bounded deterministic operation specs."""
    deps.metrics.inc("requests_governed")
    trace = deps.replay_recorder.get_trace(trace_id)
    if trace is None:
        raise HTTPException(404, detail={
            "error": "trace not found",
            "error_code": "replay_trace_not_found",
            "governed": True,
        })
    try:
        harness = ReplayDeterminismHarness({
            operation_name: _operation_from_spec(spec)
            for operation_name, spec in req.operations.items()
        })
        report = harness.replay(trace, replay_id=req.replay_id or None)
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, detail={
            "error": "replay operation specification failed",
            "error_code": "replay_operation_spec_failed",
            "reason": type(exc).__name__,
            "governed": True,
        }) from exc
    deps.audit_trail.record(
        action="replay.determinism",
        actor_id="api",
        tenant_id="system",
        target=trace_id,
        outcome="success" if report.deterministic else "mismatch",
        detail={
            "replay_id": report.replay_id,
            "report_hash": report.report_hash,
            "reason_codes": list(report.reason_codes),
        },
    )
    return {"report": report.to_dict(), "governed": True}
