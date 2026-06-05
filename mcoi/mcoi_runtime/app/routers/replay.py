"""Replay determinism endpoints.

Purpose: expose replay report generation and report history for completed traces.
Governance scope: completed ReplayTrace reconstruction using bounded local
operation specifications only.
Dependencies: FastAPI, replay recorder dependency, replay determinism harness,
replay report store.
Invariants: missing traces fail closed; operation specs cannot invoke external
effects; replay reports carry deterministic hashes and bounded reason codes;
report persistence errors fail closed at the HTTP boundary.
"""

from __future__ import annotations

from typing import Any, Callable, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.replay_determinism_harness import ReplayDeterminismHarness
from mcoi_runtime.persistence.errors import PersistenceError
from mcoi_runtime.persistence.replay_report_store import ReplayReportStore

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


def _bounded_http_error(summary: str, exc: Exception) -> dict[str, Any]:
    return {
        "error": summary,
        "error_code": summary.replace(" ", "_"),
        "reason": type(exc).__name__,
        "governed": True,
    }


def _report_store() -> ReplayReportStore:
    return deps.replay_report_store


@router.get("/api/v1/replay/reports")
def list_replay_reports(limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
    """Return stored replay determinism reports for operator history queries."""
    try:
        reports = _report_store().list_reports(limit=limit)
    except PersistenceError as exc:
        raise HTTPException(
            500,
            detail=_bounded_http_error("replay report history unavailable", exc),
        ) from exc
    return {
        "reports": [report.to_dict() for report in reports],
        "count": len(reports),
        "governed": True,
    }


@router.get("/api/v1/replay/reports/{replay_id}")
def get_replay_report(replay_id: str) -> dict[str, Any]:
    """Return one stored replay determinism report by replay id."""
    try:
        report = _report_store().get(replay_id)
    except PersistenceError as exc:
        raise HTTPException(
            400,
            detail=_bounded_http_error("replay report lookup failed", exc),
        ) from exc
    if report is None:
        raise HTTPException(404, detail={
            "error": "replay report not found",
            "error_code": "replay_report_not_found",
            "governed": True,
        })
    return {"report": report.to_dict(), "governed": True}


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
    try:
        _report_store().append(report)
    except PersistenceError as exc:
        raise HTTPException(
            500,
            detail=_bounded_http_error("replay report persistence failed", exc),
        ) from exc
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
