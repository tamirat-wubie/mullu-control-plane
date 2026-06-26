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
from collections.abc import Iterable
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.inceptadive_shadow_integration import (
    InceptaDiveShadowRuntime,
    build_inceptadive_shadow_runtime,
)
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.inceptadive_external_effect_boundary import ExternalEffectBoundaryAdvisory
from mcoi_runtime.core.inceptadive_shadow_types import (
    ShadowContext,
    ShadowFindingKind,
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


class ExternalEffectAdvisoryRequest(ShadowInspectRequest):
    """Request body for a redacted external-effect boundary advisory."""

    authority_receipt_refs: list[object] = Field(default_factory=list)


class ShadowHealthResponse(BaseModel):
    """OpenAPI response contract for the read-only shadow health posture."""

    governed: bool
    registered: bool
    shadow: dict[str, object]
    execution_authority: bool
    raw_request_text_exposed: bool
    private_memory_exposed: bool


class ShadowRecentActivityResponse(BaseModel):
    """OpenAPI response contract for redacted recent activity counts."""

    result_count: int
    receipt_count: int


class ShadowInspectResponse(BaseModel):
    """OpenAPI response contract for redacted shadow inspection results."""

    governed: bool
    registered: bool
    result: dict[str, object]
    receipt: dict[str, object] | None
    recent_activity: ShadowRecentActivityResponse
    execution_authority: bool
    raw_request_text_exposed: bool
    private_memory_exposed: bool


class ShadowExternalEffectAdvisoryResponse(BaseModel):
    """OpenAPI response contract for non-executing external-effect advisories."""

    governed: bool
    registered: bool
    advisory: dict[str, object]
    execution_authority: bool
    connector_dispatch_authority: bool
    memory_write_authority: bool
    governance_verdict_authority: bool
    raw_request_text_exposed: bool
    private_memory_exposed: bool


class ShadowConsoleResponse(BaseModel):
    """OpenAPI response contract for read-only shadow console summaries."""

    governed: bool
    registered: bool
    status: str
    health: dict[str, object]
    summary: dict[str, object]
    execution_authority: bool
    raw_request_text_exposed: bool
    private_memory_exposed: bool


class ShadowEvidenceRecentResultResponse(BaseModel):
    """OpenAPI response contract for redacted recent shadow result evidence."""

    result_id: str
    request_id: str
    mode: str
    stage: str
    verdict: str
    finding_count: int
    repair_required_count: int
    escalation_required_count: int
    block_recommended: bool
    needs_repair: bool
    needs_escalation: bool
    needs_deep_pass: bool
    created_at: str
    snapshot_hash: str
    execution_authority: bool


class ShadowEvidenceRecentReceiptResponse(BaseModel):
    """OpenAPI response contract for redacted recent shadow receipt evidence."""

    receipt_id: str
    request_id: str
    mode: str
    stage: str
    shadow_verdict: str
    governance_verdict: str
    finding_count: int
    retrieval_receipt_count: int
    created_at: str
    snapshot_hash: str
    execution_authority: bool


class ShadowEvidenceRecentAdvisoryResponse(BaseModel):
    """OpenAPI response contract for redacted recent advisory obligations."""

    advisory_id: str
    request_id: str
    context_hash: str
    action_families: list[str]
    missing_authority_obligation_count: int
    missing_evidence_obligation_count: int
    required_evidence_ref_count: int
    authority_receipt_count: int
    retrieval_receipt_count: int
    external_side_effect: bool
    strict_preflight_required: bool
    awaiting_evidence: bool
    recommended_outcome: str
    execution_authority: bool
    connector_dispatch_authority: bool
    memory_write_authority: bool
    governance_verdict_authority: bool


class ShadowConsoleEvidenceResponse(BaseModel):
    """OpenAPI response contract for read-only shadow evidence summaries."""

    governed: bool
    registered: bool
    status: str
    created_at: str
    recent_result_count: int
    receipt_count: int
    verdict_counts: dict[str, int]
    mode_counts: dict[str, int]
    repair_required_count: int
    escalation_required_count: int
    block_recommended_count: int
    missing_authority_obligation_count: int
    missing_evidence_obligation_count: int
    recent_advisory_count: int
    obligation_history_available: bool
    obligation_history_unavailable_reason: str
    recent_results: list[ShadowEvidenceRecentResultResponse]
    recent_receipts: list[ShadowEvidenceRecentReceiptResponse]
    recent_external_effect_advisories: list[ShadowEvidenceRecentAdvisoryResponse]
    execution_authority: bool
    connector_dispatch_authority: bool
    memory_write_authority: bool
    governance_verdict_authority: bool
    raw_request_text_exposed: bool
    private_memory_exposed: bool
    raw_evidence_refs_exposed: bool


@router.get("/api/v1/health/shadow", response_model=ShadowHealthResponse)
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


@router.post("/api/v1/shadow/inspect", response_model=ShadowInspectResponse)
def shadow_inspect(req: ShadowInspectRequest) -> dict[str, object]:
    """Run a bounded shadow inspection and return a redacted advisory envelope."""

    _inc_metric("requests_governed")
    runtime, registered = _shadow_runtime()
    created_at = req.created_at.strip() or _created_at()
    try:
        stage = _shadow_stage(req.stage)
        context = _shadow_context_from_request(req, created_at=created_at, stage=stage)
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


@router.post(
    "/api/v1/shadow/external-effect/advisory",
    response_model=ShadowExternalEffectAdvisoryResponse,
)
def shadow_external_effect_advisory(req: ExternalEffectAdvisoryRequest) -> dict[str, object]:
    """Return redacted external-effect authority and evidence obligations."""

    _inc_metric("requests_governed")
    runtime, registered = _shadow_runtime()
    created_at = req.created_at.strip() or _created_at()
    try:
        stage = _shadow_stage(req.stage)
        context = _shadow_context_from_request(req, created_at=created_at, stage=stage)
        advisory = runtime.external_effect_advisory(
            context,
            required_evidence_refs=_tuple_text(req.required_evidence_refs),
            authority_receipt_refs=_tuple_text(req.authority_receipt_refs),
        )
    except (RuntimeCoreInvariantError, ValueError) as exc:
        _inc_metric("requests_rejected")
        raise HTTPException(
            status_code=400,
            detail=_shadow_error_detail(
                "invalid external-effect advisory request",
                "invalid_external_effect_advisory_request",
            ),
        ) from exc

    return {
        "governed": True,
        "registered": registered,
        "advisory": advisory.to_dict(),
        "execution_authority": False,
        "connector_dispatch_authority": False,
        "memory_write_authority": False,
        "governance_verdict_authority": False,
        "raw_request_text_exposed": False,
        "private_memory_exposed": False,
    }


@router.get("/api/v1/console/shadow", response_model=ShadowConsoleResponse)
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


@router.get("/api/v1/console/shadow/evidence", response_model=ShadowConsoleEvidenceResponse)
def shadow_console_evidence() -> dict[str, object]:
    """Read-only operator evidence view for recent shadow receipts."""

    _inc_metric("requests_governed")
    runtime, registered = _shadow_runtime()
    created_at = _created_at()
    posture = runtime.health_posture(created_at=created_at).to_dict()
    recent_results, recent_receipts = runtime.recent_activity(limit=runtime.config.max_findings)
    recent_advisories = runtime.recent_external_effect_advisories(limit=runtime.config.max_findings)
    redacted_results = [_redacted_evidence_result(result) for result in recent_results]
    redacted_receipts = [_redacted_evidence_receipt(receipt) for receipt in recent_receipts]
    redacted_advisories = [_redacted_evidence_advisory(advisory) for advisory in recent_advisories]
    obligation_history_available = runtime.receipt_store is not None
    return {
        "governed": True,
        "registered": registered,
        "status": str(posture.get("status", "unknown")),
        "created_at": created_at,
        "recent_result_count": len(redacted_results),
        "receipt_count": len(redacted_receipts),
        "verdict_counts": _count_by(str(result["verdict"]) for result in redacted_results),
        "mode_counts": _count_by(str(result["mode"]) for result in redacted_results),
        "repair_required_count": sum(int(result["repair_required_count"]) for result in redacted_results),
        "escalation_required_count": sum(int(result["escalation_required_count"]) for result in redacted_results),
        "block_recommended_count": sum(1 for result in redacted_results if result["block_recommended"]),
        "missing_authority_obligation_count": sum(
            int(advisory["missing_authority_obligation_count"]) for advisory in redacted_advisories
        ),
        "missing_evidence_obligation_count": sum(
            int(advisory["missing_evidence_obligation_count"]) for advisory in redacted_advisories
        ),
        "recent_advisory_count": len(redacted_advisories),
        "obligation_history_available": obligation_history_available,
        "obligation_history_unavailable_reason": ""
        if obligation_history_available
        else "shadow_receipt_store_unavailable",
        "recent_results": redacted_results,
        "recent_receipts": redacted_receipts,
        "recent_external_effect_advisories": redacted_advisories,
        "execution_authority": False,
        "connector_dispatch_authority": False,
        "memory_write_authority": False,
        "governance_verdict_authority": False,
        "raw_request_text_exposed": False,
        "private_memory_exposed": False,
        "raw_evidence_refs_exposed": False,
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


def _shadow_context_from_request(req: ShadowInspectRequest, *, created_at: str, stage: ShadowStage) -> ShadowContext:
    return ShadowContext(
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


def _redacted_evidence_result(result: ShadowPassResult) -> dict[str, object]:
    """Return recent result evidence without finding summaries or raw refs."""

    return {
        "result_id": result.result_id,
        "request_id": result.request_id,
        "mode": result.mode.value,
        "stage": result.stage.value,
        "verdict": result.verdict.value,
        "finding_count": len(result.findings),
        "repair_required_count": sum(1 for finding in result.findings if finding.repair_required),
        "escalation_required_count": sum(
            1
            for finding in result.findings
            if finding.kind == ShadowFindingKind.ESCALATION_REQUIRED
        ),
        "block_recommended": result.block_recommended,
        "needs_repair": result.needs_repair,
        "needs_escalation": result.needs_escalation,
        "needs_deep_pass": result.needs_deep_pass,
        "created_at": result.created_at,
        "snapshot_hash": result.snapshot_hash,
        "execution_authority": False,
    }


def _redacted_evidence_receipt(receipt: ShadowReceipt) -> dict[str, object]:
    """Return recent receipt evidence without raw retrieval receipt ids."""

    return {
        "receipt_id": receipt.receipt_id,
        "request_id": receipt.request_id,
        "mode": receipt.mode.value,
        "stage": receipt.stage.value,
        "shadow_verdict": receipt.shadow_verdict.value,
        "governance_verdict": receipt.governance_verdict,
        "finding_count": len(receipt.finding_ids),
        "retrieval_receipt_count": len(receipt.retrieval_receipt_ids),
        "created_at": receipt.created_at,
        "snapshot_hash": receipt.snapshot_hash,
        "execution_authority": False,
    }


def _redacted_evidence_advisory(advisory: ExternalEffectBoundaryAdvisory) -> dict[str, object]:
    """Return recent advisory evidence without raw request or ref values."""

    return {
        "advisory_id": advisory.advisory_id,
        "request_id": advisory.request_id,
        "context_hash": advisory.context_hash,
        "action_families": list(advisory.action_families),
        "missing_authority_obligation_count": len(advisory.missing_authority_obligations),
        "missing_evidence_obligation_count": len(advisory.missing_evidence_obligations),
        "required_evidence_ref_count": advisory.required_evidence_ref_count,
        "authority_receipt_count": advisory.authority_receipt_count,
        "retrieval_receipt_count": advisory.retrieval_receipt_count,
        "external_side_effect": advisory.external_side_effect,
        "strict_preflight_required": advisory.strict_preflight_required,
        "awaiting_evidence": advisory.awaiting_evidence,
        "recommended_outcome": advisory.recommended_outcome,
        "execution_authority": False,
        "connector_dispatch_authority": False,
        "memory_write_authority": False,
        "governance_verdict_authority": False,
    }


def _count_by(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


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
