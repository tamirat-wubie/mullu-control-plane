"""LLM / completion-related endpoints extracted from server.py.

Covers governed completion, streaming, chat, cost analytics, model routing,
circuit-breaker status, A/B testing, and bootstrap info.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.agent_protocol import AgentCapability

router = APIRouter()


# ── Pydantic request models ──────────────────────────────────────────────


class CompletionRequest(BaseModel):
    prompt: str
    model_name: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    temperature: float = 0.0
    tenant_id: str = "system"
    budget_id: str = "default"
    system: str = ""


class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    tenant_id: str = "system"
    budget_id: str = "default"
    model_name: str = "claude-sonnet-4-20250514"
    system_prompt: str = ""


class ChatWorkflowRequest(BaseModel):
    conversation_id: str
    message: str
    tenant_id: str = "system"
    capability: str = "llm.completion"
    system_prompt: str = ""
    budget_id: str = "default"


class AutoCompleteRequest(BaseModel):
    prompt: str
    max_tokens: int = 1024
    max_cost: float = 0.0
    preferred_speed: str = ""
    force_model: str = ""
    tenant_id: str = "system"
    budget_id: str = "default"


class ABTestRequest(BaseModel):
    prompt: str
    model_ids: list[str] = []
    criteria: str = "cost"


# ── Helpers ───────────────────────────────────────────────────────────────


def _validate_or_raise(schema_id: str, data: dict[str, Any]) -> None:
    """Validate request data against a schema; raise 422 if invalid."""
    result = deps.input_validator.validate(schema_id, data)
    if not result.valid:
        raise HTTPException(422, detail={
            "error": "Validation failed",
            "validation_errors": result.to_dict()["errors"],
            "governed": True,
        })


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
                action="llm.complete", actor_id=req.tenant_id,
                tenant_id=req.tenant_id, target=req.model_name,
                outcome="success", detail={"cost": result.cost, "tokens": result.total_tokens},
            )
        else:
            deps.llm_circuit.record_failure()
            raise HTTPException(status_code=503, detail={"error": result.error, "governed": True})
    except HTTPException:
        raise
    except Exception as exc:
        deps.llm_circuit.record_failure()
        deps.metrics.inc("errors_total")
        raise HTTPException(503, detail={"error": str(exc), "governed": True})
    return {
        "content": result.content,
        "model": result.model_name,
        "provider": result.provider.value,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "cost": result.cost,
        "circuit_state": deps.llm_circuit.state.value,
        "governed": True,
    }


# ═══ Budget & History ═══


@router.get("/api/v1/budget")
def budget_summary():
    """Budget status for all registered LLM budgets."""
    return deps.llm_bridge.budget_summary()


@router.get("/api/v1/llm/history")
def llm_history(limit: int = 50):
    """Recent LLM invocation history."""
    return {"invocations": deps.llm_bridge.invocation_history(limit=limit)}


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
                action="llm.stream", actor_id=req.tenant_id,
                tenant_id=req.tenant_id, target=req.model_name,
                outcome="success",
            )
        else:
            deps.llm_circuit.record_failure()
    except Exception as exc:
        deps.llm_circuit.record_failure()
        deps.metrics.inc("errors_total")
        raise HTTPException(503, detail={"error": str(exc), "governed": True})
    return StreamingResponse(
        deps.streaming_adapter.stream_to_sse(result, request_id=f"stream-{id(req)}"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ═══ Phase 200A — Bootstrap Info Endpoint ═══


@router.get("/api/v1/bootstrap")
def bootstrap_info():
    """LLM bootstrap configuration and registered backends."""
    return {
        "default_backend": deps.llm_bootstrap_result.default_backend_name,
        "available_backends": list(deps.llm_bootstrap_result.backends.keys()),
        "registered_models": deps.llm_bootstrap_result.registered_models,
        "registered_providers": deps.llm_bootstrap_result.registered_providers,
        "config": {
            "default_model": deps.llm_bootstrap_result.config.default_model,
            "default_budget_max_cost": deps.llm_bootstrap_result.config.default_budget_max_cost,
            "max_tokens_per_call": deps.llm_bootstrap_result.config.max_tokens_per_call,
        },
    }


# ═══ Phase 209A — Conversation-Aware Chat Endpoint ═══


@router.post("/api/v1/chat")
def chat_completion(req: ChatRequest):
    """Multi-turn chat — uses conversation history for context."""
    deps.metrics.inc("requests_governed")
    deps.metrics.inc("llm_calls_total")

    conv = deps.conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)

    # Add system prompt on first message
    if req.system_prompt and conv.message_count == 0:
        conv.add_system(req.system_prompt)

    # Add user message
    conv.add_user(req.message)

    # Call LLM with full conversation history
    result = deps.llm_bridge.chat(
        conv.to_chat_messages(),
        model_name=req.model_name,
        budget_id=req.budget_id,
        tenant_id=req.tenant_id,
    )

    if result.succeeded:
        conv.add_assistant(result.content)
        deps.metrics.inc("llm_calls_succeeded")
        # Record cost analytics
        deps.cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)
    else:
        deps.metrics.inc("llm_calls_failed")

    return {
        "conversation_id": conv.conversation_id,
        "content": result.content,
        "model": result.model_name,
        "tokens": result.total_tokens,
        "cost": result.cost,
        "succeeded": result.succeeded,
        "message_count": conv.message_count,
        "governed": True,
    }


# ═══ Phase 213C — Streaming Chat Endpoint (SSE + Conversation) ═══


@router.post("/api/v1/chat/stream")
def streaming_chat(req: ChatRequest):
    """Streaming chat — SSE with conversation history (feature-gated)."""
    deps.metrics.inc("requests_governed")
    if not deps.feature_flags.is_enabled("streaming_v2", tenant_id=req.tenant_id):
        raise HTTPException(403, detail={
            "error": "Feature 'streaming_v2' is not enabled for this tenant",
            "governed": True,
        })
    conv = deps.conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)

    if req.system_prompt and conv.message_count == 0:
        conv.add_system(req.system_prompt)
    conv.add_user(req.message)

    # Get completion (non-streaming internally, streamed to client)
    result = deps.llm_bridge.chat(
        conv.to_chat_messages(), model_name=req.model_name,
        budget_id=req.budget_id, tenant_id=req.tenant_id,
    )

    if result.succeeded:
        conv.add_assistant(result.content)
        deps.cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)

    # Stream as SSE
    return StreamingResponse(
        deps.streaming_adapter.stream_to_sse(result, request_id=f"chat-{req.conversation_id}"),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ═══ Phase 210A — Chat Workflow Endpoint ═══


@router.post("/api/v1/chat/workflow")
def chat_workflow_endpoint(req: ChatWorkflowRequest):
    """Chat-triggered governed workflow — conversation + agent + trace."""
    deps.metrics.inc("requests_governed")
    try:
        cap = AgentCapability(req.capability)
    except ValueError:
        raise HTTPException(400, detail=f"unknown capability: {req.capability}")

    result = deps.chat_workflow.execute(
        conversation_id=req.conversation_id,
        message=req.message,
        tenant_id=req.tenant_id,
        capability=cap,
        system_prompt=req.system_prompt,
        budget_id=req.budget_id,
    )
    return {
        "conversation_id": result.conversation_id,
        "workflow_id": result.workflow_id,
        "agent_id": result.agent_id,
        "status": result.status,
        "response": result.response_content,
        "trace_id": result.trace_id,
        "message_count": result.message_count,
        "cost": result.cost,
        "governed": True,
    }


@router.get("/api/v1/chat/workflow/history")
def chat_workflow_history(limit: int = 50):
    """Chat workflow execution history."""
    return {
        "history": [
            {"conversation": r.conversation_id, "workflow": r.workflow_id,
             "status": r.status, "cost": r.cost}
            for r in deps.chat_workflow.history(limit=limit)
        ],
        "summary": deps.chat_workflow.summary(),
    }


# ═══ Phase 209D — Cost Analytics Endpoints ═══


@router.get("/api/v1/costs")
def cost_summary():
    """Overall cost analytics summary."""
    return deps.cost_analytics.summary()


@router.get("/api/v1/costs/top-spenders")
def top_spenders(limit: int = 10):
    """Top spending tenants."""
    return {
        "spenders": [
            {"tenant_id": b.tenant_id, "total_cost": b.total_cost, "calls": b.call_count}
            for b in deps.cost_analytics.top_spenders(limit=limit)
        ],
    }


@router.get("/api/v1/costs/by-model")
def costs_by_model():
    """Cost breakdown by LLM model."""
    return {"models": deps.cost_analytics.model_usage()}


@router.get("/api/v1/costs/{tenant_id}")
def tenant_costs(tenant_id: str):
    """Cost breakdown for a specific tenant."""
    breakdown = deps.cost_analytics.tenant_breakdown(tenant_id)
    return {
        "tenant_id": breakdown.tenant_id,
        "total_cost": breakdown.total_cost,
        "total_tokens": breakdown.total_tokens,
        "call_count": breakdown.call_count,
        "avg_cost_per_call": breakdown.avg_cost_per_call,
        "by_model": breakdown.by_model,
        "most_expensive_model": breakdown.most_expensive_model,
    }


@router.get("/api/v1/costs/{tenant_id}/projection")
def cost_projection(tenant_id: str, budget: float = 0.0, days_elapsed: float = 1.0):
    """Cost projection for a tenant."""
    proj = deps.cost_analytics.project(tenant_id, budget=budget, days_elapsed=days_elapsed)
    return {
        "tenant_id": proj.tenant_id,
        "current_daily_rate": proj.current_daily_rate,
        "projected_monthly": proj.projected_monthly,
        "budget_remaining": proj.budget_remaining,
        "days_until_exhaustion": proj.days_until_exhaustion,
    }


# ═══ Circuit Breaker Status ═══


@router.get("/api/v1/circuit-breaker")
def circuit_breaker_status():
    """LLM circuit breaker status."""
    return deps.llm_circuit.status()


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
        }
    except Exception as exc:
        deps.llm_circuit.record_failure()
        deps.metrics.inc("errors_total")
        raise HTTPException(503, detail={"error": str(exc), "governed": True})


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
        raise HTTPException(503, detail="no models available for routing")

    result = deps.llm_bridge.complete(
        req.prompt, model_name=decision.model_id,
        max_tokens=req.max_tokens, tenant_id=req.tenant_id,
        budget_id=req.budget_id,
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
    }


# ═══ List Models ═══


@router.get("/api/v1/models")
def list_models():
    """List available models for routing."""
    return {
        "models": [
            {"id": p.model_id, "name": p.name, "provider": p.provider,
             "speed": p.speed_tier, "capability": p.capability_tier, "enabled": p.enabled}
            for p in sorted(deps.model_router._profiles.values(), key=lambda p: p.model_id)
        ],
        "summary": deps.model_router.summary(),
    }


# ═══ Phase 216B — A/B Testing Endpoint ═══


@router.post("/api/v1/ab-test")
def run_ab_test(req: ABTestRequest):
    """Run an A/B test across models."""
    deps.metrics.inc("requests_governed")
    model_fns = {}
    for mid in (req.model_ids or ["default"]):
        model_fns[mid] = lambda p, m=mid: deps.llm_bridge.complete(p, model_name=m, budget_id="default")

    result = deps.ab_engine.run_experiment(req.prompt, model_fns, criteria=req.criteria)
    return {
        "experiment_id": result.experiment_id,
        "winner": result.winner,
        "criteria": result.criteria,
        "variants": [
            {"id": v.variant_id, "model": v.model_id, "cost": v.cost,
             "tokens": v.tokens, "latency_ms": v.latency_ms, "succeeded": v.succeeded}
            for v in result.variants
        ],
    }


@router.get("/api/v1/ab-test/summary")
def ab_test_summary():
    """A/B testing summary with win rates."""
    return deps.ab_engine.summary()
