"""Read-only InceptaDive Shadow Pass posture routes.

Purpose: expose health, console posture, and bounded request inspection for the
shadow interrogation layer without exposing raw requests, private memory, or
execution authority.
Governance scope: observability and advisory inspection only; routes cannot
mutate memory, approve actions, or execute candidate plans.
Dependencies: FastAPI router, dependency container, and shadow app facade.
Invariants: responses are bounded, redacted, deterministic in shape, and always
carry execution_authority=false.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.inceptadive_shadow_integration import (
    InceptaDiveShadowRuntime,
    build_inceptadive_shadow_runtime,
)
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowPassResult,
    ShadowReceipt,
    ShadowSeverity,
    ShadowStage,
)
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier

router = APIRouter()


class ShadowInspectRequest(BaseModel):
    """Request body for a redacted non-executing shadow inspection."""

    request_id: str = ""
    stage: str = ShadowStage.INTERPRETATION.value
    user_input: str = ""
    normal_intent: str = ""
    normal_plan: list[object] = Field(default_factory=list)
    candidate_action: str = ""
    explicit_target: str = ""
    scope: str = ""
    risk_level: str = ShadowSeverity.LOW.value
    external_side_effect: bool = False
    memory_contradiction: bool = False
    retrieval_receipt_ids: list[object] = Field(default_factory=list)
    required_evidence_refs: list[object] = Field(default_factory=list)
    created_at: str = ""


@router.get("/api/v1/health/shadow")
def shadow_health() -> dict[str, object]:
    """Read-only shadow subsystem health posture."""

    _inc_metric("requests_governed")
    runtime, registered = _shadow_runtime()
    posture = runtime.health_posture(created_at=_created_at()).to_dict()
    return {
        "governed": True,
        "registered": registered,
        "shadow": posture,
        "execution_authority": False,
        "raw_request_text_exposed": False,
        "private_memory_exposed": False,
    }


@router.post("/api/v1/shadow/inspect")
def shadow_inspect(req: ShadowInspectRequest) -> dict[str, object]:
    """Run a bounded shadow inspection and return a redacted advisory envelope."""

    _inc_metric("requests_governed")
    runtime, registered = _shadow_runtime()
    created_at = req.created_at.strip() or _created_at()
    try:
        stage = _shadow_stage(req.stage)
        context = ShadowContext(
            request_id=_inspect_request_id(req, created_at=created_at, stage=stage),
            stage=stage,
            user_input=req.user_input,
            normal_intent=req.normal_intent,
            normal_plan=_tuple_text(req.normal_plan),
            candidate_action=req.candidate_action,
            explicit_target=req.explicit_target,
            scope=req.scope,
            risk_level=_shadow_severity(req.risk_level),
            external_side_effect=req.external_side_effect,
            memory_contradiction=req.memory_contradiction,
            retrieval_receipt_ids=_tuple_text(req.retrieval_receipt_ids),
            created_at=created_at,
        ).with_integrity()
        if stage == ShadowStage.PREFLIGHT:
            result, receipt = runtime.preflight_action(
                context,
                required_evidence_refs=_tuple_text(req.required_evidence_refs),
            )
        else:
            result, receipt = runtime.inspect_request(context)
    except (RuntimeCoreInvariantError, ValueError) as exc:
        _inc_metric("requests_rejected")
        raise HTTPException(
            status_code=400,
            detail=_shadow_error_detail("invalid shadow inspect request", "invalid_shadow_inspect_request"),
        ) from exc

    recent_results, recent_receipts = runtime.recent_activity(limit=runtime.config.max_findings)
    return {
        "governed": True,
        "registered": registered,
        "result": _redacted_result(result),
        "receipt": _redacted_receipt(receipt),
        "recent_activity": {
            "result_count": len(recent_results),
            "receipt_count": len(recent_receipts),
        },
        "execution_authority": False,
        "raw_request_text_exposed": False,
        "private_memory_exposed": False,
    }


@router.get("/api/v1/console/shadow")
def shadow_console() -> dict[str, object]:
    """Read-only operator console summary for the shadow subsystem."""

    _inc_metric("requests_governed")
    runtime, registered = _shadow_runtime()
    created_at = _created_at()
    posture = runtime.health_posture(created_at=created_at).to_dict()
    summary = runtime.console_summary(created_at=created_at).to_dict()
    return {
        "governed": True,
        "registered": registered,
        "status": str(posture.get("status", "unknown")),
        "health": posture,
        "summary": summary,
        "execution_authority": False,
        "raw_request_text_exposed": False,
        "private_memory_exposed": False,
    }


def _shadow_runtime() -> tuple[InceptaDiveShadowRuntime, bool]:
    """Return registered runtime or a bounded env-derived fallback."""

    try:
        runtime = deps.get("inceptadive_shadow_runtime")
    except RuntimeError:
        return build_inceptadive_shadow_runtime(os.environ), False
    if not isinstance(runtime, InceptaDiveShadowRuntime):
        return build_inceptadive_shadow_runtime(os.environ), False
    return runtime, True


def _inspect_request_id(req: ShadowInspectRequest, *, created_at: str, stage: ShadowStage) -> str:
    """Return caller-provided id or a deterministic non-raw request reference."""

    if req.request_id.strip():
        return req.request_id.strip()
    return "shadow_request_" + stable_identifier(
        "shadow-inspect-request",
        {
            "stage": stage.value,
            "user_input": req.user_input,
            "candidate_action": req.candidate_action,
            "created_at": created_at,
        },
    )


def _shadow_stage(value: str) -> ShadowStage:
    try:
        return ShadowStage(str(value or "").strip().lower())
    except ValueError as exc:
        raise ValueError("invalid shadow stage") from exc


def _shadow_severity(value: str) -> ShadowSeverity:
    try:
        return ShadowSeverity(str(value or "").strip().lower())
    except ValueError as exc:
        raise ValueError("invalid shadow severity") from exc


def _tuple_text(values: list[object]) -> tuple[str, ...]:
    items: list[str] = []
    for value in values:
        if value is None:
            continue
        item = str(value).strip()
        if item:
            items.append(item)
    return tuple(items)


def _redacted_result(result: ShadowPassResult) -> dict[str, object]:
    """Return a result read model without raw context or evidence ref values."""

    return {
        "result_id": result.result_id,
        "request_id": result.request_id,
        "mode": result.mode.value,
        "stage": result.stage.value,
        "verdict": result.verdict.value,
        "findings": [
            {
                "finding_id": finding.finding_id,
                "kind": finding.kind.value,
                "severity": finding.severity.value,
                "summary": finding.summary,
                "evidence_ref_count": len(finding.evidence_refs),
                "source_note_count": len(finding.source_note_ids),
                "source_event_count": len(finding.source_event_ids),
                "confidence": finding.confidence,
                "constructive_delta": finding.constructive_delta,
                "fracture_delta": finding.fracture_delta,
                "repair_required": finding.repair_required,
                "recommended_action": finding.recommended_action,
                "created_at": finding.created_at,
            }
            for finding in result.findings
        ],
        "finding_count": len(result.findings),
        "constructive_delta_count": result.constructive_delta_count,
        "fracture_delta_count": result.fracture_delta_count,
        "needs_deep_pass": result.needs_deep_pass,
        "needs_repair": result.needs_repair,
        "needs_escalation": result.needs_escalation,
        "block_recommended": result.block_recommended,
        "repaired_plan_candidate_count": len(result.repaired_plan_candidate),
        "created_at": result.created_at,
        "snapshot_hash": result.snapshot_hash,
        "execution_authority": False,
    }


def _redacted_receipt(receipt: ShadowReceipt | None) -> dict[str, object] | None:
    if receipt is None:
        return None
    return {
        "receipt_id": receipt.receipt_id,
        "request_id": receipt.request_id,
        "mode": receipt.mode.value,
        "stage": receipt.stage.value,
        "context_hash": receipt.context_hash,
        "result_id": receipt.result_id,
        "finding_ids": list(receipt.finding_ids),
        "retrieval_receipt_count": len(receipt.retrieval_receipt_ids),
        "shadow_verdict": receipt.shadow_verdict.value,
        "governance_verdict": receipt.governance_verdict,
        "created_at": receipt.created_at,
        "snapshot_hash": receipt.snapshot_hash,
        "execution_authority": False,
    }


def _shadow_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _created_at() -> str:
    """Return registered server clock when available without requiring it."""

    try:
        clock = deps.get("clock")
    except RuntimeError:
        return "1970-01-01T00:00:00+00:00"
    try:
        value = clock() if callable(clock) else clock
    except (TypeError, ValueError):
        return "1970-01-01T00:00:00+00:00"
    return str(value or "1970-01-01T00:00:00+00:00")


def _inc_metric(name: str) -> None:
    """Increment metrics if the governed metrics dependency is registered."""

    try:
        metrics: Any = deps.get("metrics")
    except RuntimeError:
        return
    inc = getattr(metrics, "inc", None)
    if callable(inc):
        inc(name)
