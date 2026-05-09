"""Completion endpoints: governed, streaming, circuit-breaker-protected, auto-routed."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from mcoi_runtime.app.routers.llm._common import (
    _certify_action_proof,
    _raise_governed_http_error,
    _raise_llm_service_unavailable,
    _validate_or_raise,
    deps,
)
from mcoi_runtime.app.routers.llm._models import (
    AutoCompleteRequest,
    CompletionRequest,
)

router = APIRouter()


# ═══ Phase 199A — LLM Completion Endpoint ═══


@router.post("/api/v1/complete")
def complete(req: CompletionRequest):
    """Governed LLM completion — budgeted, ledgered, circuit-protected."""
    deps.metrics.inc("requests_governed")
    _validate_or_raise("completion", req.model_dump())
    if not deps.llm_circuit.allow_request():
        deps.metrics.inc("requests_rejected")
        raise HTTPException(503, detail={
            "error": "LLM circuit breaker is open",
            "circuit_state": deps.llm_circuit.state.value, "governed": True,
        })
    try:
        result = deps.llm_bridge.complete(
            req.prompt,
            model_name=req.model_name,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            tenant_id=req.tenant_id,
            budget_id=req.budget_id,
            system=req.system,
        )
        if result.succeeded:
            deps.llm_circuit.record_success()
            deps.cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)
            deps.audit_trail.record(
                action="llm.complete", actor_id=req.actor_id,
                tenant_id=req.tenant_id, target=req.model_name,
                outcome="success", detail={"cost": result.cost, "tokens": result.total_tokens},
            )
        else:
            deps.llm_circuit.record_failure()
            _raise_governed_http_error(
                status_code=503,
                error=result.error or "LLM completion failed",
                error_code="llm_completion_failed",
            )
    except HTTPException:
        raise
    except Exception as exc:
        _raise_llm_service_unavailable(
            action="llm.complete",
            actor_id=req.actor_id,
            tenant_id=req.tenant_id,
            target=req.model_name,
            exc=exc,
        )
    return {
        "content": result.content,
        "model": result.model_name,
        "provider": result.provider.value,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost": result.cost,
        "circuit_state": deps.llm_circuit.state.value,
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/complete",
            tenant_id=req.tenant_id,
            actor_id=req.actor_id,
            action="llm.complete",
            succeeded=True,
        ),
    }


# ═══ Phase 200C — Streaming Completion Endpoint ═══


@router.post("/api/v1/stream")
def stream_completion(req: CompletionRequest):
    """SSE streaming LLM completion — governed, budgeted, circuit-protected."""
    deps.metrics.inc("requests_governed")
    _validate_or_raise("completion", req.model_dump())
    if not deps.llm_circuit.allow_request():
        deps.metrics.inc("requests_rejected")
        raise HTTPException(503, detail={
            "error": "LLM circuit breaker is open",
            "circuit_state": deps.llm_circuit.state.value, "governed": True,
        })
    try:
        result = deps.llm_bridge.complete(
            req.prompt,
            model_name=req.model_name,
            max_tokens=req.max_tokens,
            temperature=req.temperature,
            tenant_id=req.tenant_id,
            budget_id=req.budget_id,
            system=req.system,
        )
        if result.succeeded:
            deps.llm_circuit.record_success()
            deps.audit_trail.record(
                action="llm.stream", actor_id=req.actor_id,
                tenant_id=req.tenant_id, target=req.model_name,
                outcome="success",
            )
        else:
            deps.llm_circuit.record_failure()
    except Exception as exc:
        _raise_llm_service_unavailable(
            action="llm.stream",
            actor_id=req.actor_id,
            tenant_id=req.tenant_id,
            target=req.model_name,
            exc=exc,
        )
    return StreamingResponse(
        deps.streaming_adapter.stream_to_sse(
            result,
            request_id=f"stream-{id(req)}",
            tenant_id=req.tenant_id,
            budget_id=req.budget_id,
            estimated_input_tokens=result.input_tokens,
            estimated_output_tokens=req.max_tokens,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ═══ Phase 213A — Circuit-Breaker Protected LLM Completion ═══


@router.post("/api/v1/complete/safe")
def safe_completion(req: CompletionRequest):
    """LLM completion with circuit-breaker protection."""
    deps.metrics.inc("requests_governed")
    if not deps.llm_circuit.allow_request():
        deps.metrics.inc("requests_rejected")
        raise HTTPException(503, detail={
            "error": "LLM circuit breaker is open — service temporarily unavailable",
            "circuit_state": deps.llm_circuit.state.value,
            "governed": True,
        })

    try:
        result = deps.llm_bridge.complete(
            req.prompt, model_name=req.model_name, max_tokens=req.max_tokens,
            temperature=req.temperature, tenant_id=req.tenant_id,
            budget_id=req.budget_id, system=req.system,
        )
        if result.succeeded:
            deps.llm_circuit.record_success()
            deps.metrics.inc("llm_calls_succeeded")
            deps.cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)
        else:
            deps.llm_circuit.record_failure()
            deps.metrics.inc("llm_calls_failed")

        return {
            "content": result.content, "model": result.model_name,
            "provider": result.provider.value, "tokens": result.total_tokens,
            "cost": result.cost, "succeeded": result.succeeded,
            "circuit_state": deps.llm_circuit.state.value, "governed": True,
            "action_proof": _certify_action_proof(
                endpoint="/api/v1/complete/safe",
                tenant_id=req.tenant_id,
                actor_id=req.actor_id,
                action="llm.complete.safe",
                succeeded=result.succeeded,
            ),
        }
    except Exception as exc:
        _raise_llm_service_unavailable(
            action="llm.complete.safe",
            actor_id=req.actor_id,
            tenant_id=req.tenant_id,
            target=req.model_name,
            exc=exc,
        )


# ═══ Phase 214A — Auto-Routed Completion ═══


@router.post("/api/v1/complete/auto")
def auto_routed_completion(req: AutoCompleteRequest):
    """LLM completion with automatic model routing."""
    deps.metrics.inc("requests_governed")
    decision = deps.model_router.route(
        req.prompt, max_tokens=req.max_tokens,
        max_cost=req.max_cost, preferred_speed=req.preferred_speed,
        force_model=req.force_model,
    )
    if not decision.model_id:
        _raise_governed_http_error(
            status_code=503,
            error="No models available for routing",
            error_code="no_routable_model",
        )

    try:
        result = deps.llm_bridge.complete(
            req.prompt, model_name=decision.model_id,
            max_tokens=req.max_tokens, tenant_id=req.tenant_id,
            budget_id=req.budget_id,
        )
    except Exception as exc:
        _raise_llm_service_unavailable(
            action="llm.complete.auto",
            actor_id=req.actor_id,
            tenant_id=req.tenant_id,
            target=decision.model_id,
            exc=exc,
        )
    if result.succeeded:
        deps.cost_analytics.record(req.tenant_id, decision.model_id, result.cost, result.total_tokens)

    return {
        "content": result.content,
        "model": decision.model_id,
        "routing": {
            "reason": decision.reason,
            "complexity": decision.complexity.value,
            "estimated_cost": decision.estimated_cost,
            "alternatives": list(decision.alternatives),
        },
        "tokens": result.total_tokens,
        "cost": result.cost,
        "succeeded": result.succeeded,
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/complete/auto",
            tenant_id=req.tenant_id,
            actor_id=req.actor_id,
            action="llm.complete.auto",
            succeeded=result.succeeded,
        ),
    }
