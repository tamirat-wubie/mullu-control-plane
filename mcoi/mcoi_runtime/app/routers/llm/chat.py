"""Conversation-aware chat, streaming chat, and chat-triggered workflow endpoints."""
from __future__ import annotations

import os
from collections.abc import Iterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from mcoi_runtime.app.inceptadive_assistant_response_embedding import (
    build_assistant_response_shadow_advisory,
)
from mcoi_runtime.app.inceptadive_shadow_integration import (
    InceptaDiveShadowRuntime,
    build_inceptadive_shadow_runtime,
)
from mcoi_runtime.app.streaming import StreamEvent
from mcoi_runtime.app.routers.llm._common import (
    _raise_governed_http_error,
    _raise_llm_service_unavailable,
    deps,
)
from mcoi_runtime.app.routers.llm._models import ChatRequest, ChatWorkflowRequest
from mcoi_runtime.core.agent_protocol import AgentCapability
from mcoi_runtime.core.invariants import stable_identifier

router = APIRouter()
_MAX_CHAT_WORKFLOW_HISTORY_READ_LIMIT = 500


def _chat_workflow_history_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _coerce_chat_workflow_history_limit(limit: object) -> int:
    if isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    if isinstance(limit, int):
        value = limit
    elif isinstance(limit, str):
        normalized = limit.strip()
        if not normalized.isdecimal():
            raise ValueError("limit must be an integer")
        value = int(normalized)
    else:
        raise ValueError("limit must be an integer")
    if value < 0 or value > _MAX_CHAT_WORKFLOW_HISTORY_READ_LIMIT:
        raise ValueError("limit is outside the allowed range")
    return value


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
    try:
        result = deps.llm_bridge.chat(
            conv.to_chat_messages(),
            model_name=req.model_name,
            budget_id=req.budget_id,
            tenant_id=req.tenant_id,
        )
    except Exception as exc:
        _raise_llm_service_unavailable(
            action="llm.chat",
            actor_id=req.actor_id,
            tenant_id=req.tenant_id,
            target=req.model_name,
            exc=exc,
        )

    if result.succeeded:
        conv.add_assistant(result.content)
        deps.metrics.inc("llm_calls_succeeded")
        deps.cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)
    else:
        deps.metrics.inc("llm_calls_failed")

    shadow_advisory = build_assistant_response_shadow_advisory(
        _shadow_runtime(),
        request_id=_assistant_response_shadow_request_id(
            route="/api/v1/chat",
            conversation_id=conv.conversation_id,
            response_ref=str(conv.message_count),
            model_or_capability=result.model_name,
        ),
        user_input=req.message,
        assistant_content=result.content,
        route="/api/v1/chat",
        tenant_id=req.tenant_id,
        model_name=result.model_name,
        succeeded=result.succeeded,
        created_at=_created_at(),
    )

    return {
        "conversation_id": conv.conversation_id,
        "content": result.content,
        "model": result.model_name,
        "tokens": result.total_tokens,
        "cost": result.cost,
        "succeeded": result.succeeded,
        "message_count": conv.message_count,
        "inceptadive_shadow_advisory": shadow_advisory,
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
    try:
        result = deps.llm_bridge.chat(
            conv.to_chat_messages(), model_name=req.model_name,
            budget_id=req.budget_id, tenant_id=req.tenant_id,
        )
    except Exception as exc:
        _raise_llm_service_unavailable(
            action="llm.chat.stream",
            actor_id=req.actor_id,
            tenant_id=req.tenant_id,
            target=req.model_name,
            exc=exc,
        )

    if result.succeeded:
        conv.add_assistant(result.content)
        deps.cost_analytics.record(req.tenant_id, req.model_name, result.cost, result.total_tokens)

    stream_request_id = f"chat-{req.conversation_id}"
    shadow_advisory = build_assistant_response_shadow_advisory(
        _shadow_runtime(),
        request_id=_assistant_response_shadow_request_id(
            route="/api/v1/chat/stream",
            conversation_id=conv.conversation_id,
            response_ref=str(conv.message_count),
            model_or_capability=result.model_name,
        ),
        user_input=req.message,
        assistant_content=result.content,
        route="/api/v1/chat/stream",
        tenant_id=req.tenant_id,
        model_name=result.model_name,
        succeeded=result.succeeded,
        created_at=_created_at(),
    )

    # Stream as SSE. The advisory wrapper preserves existing meta/token/done
    # events and inserts one redacted, advisory-only metadata event.
    return StreamingResponse(
        _stream_with_shadow_advisory(
            deps.streaming_adapter.stream_to_sse(
                result,
                request_id=stream_request_id,
                tenant_id=req.tenant_id,
                budget_id=req.budget_id,
                estimated_input_tokens=result.input_tokens,
            ),
            shadow_advisory,
        ),
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
        _raise_governed_http_error(
            status_code=400,
            error="Unknown agent capability",
            error_code="invalid_capability",
        )

    try:
        result = deps.chat_workflow.execute(
            conversation_id=req.conversation_id,
            message=req.message,
            tenant_id=req.tenant_id,
            capability=cap,
            system_prompt=req.system_prompt,
            budget_id=req.budget_id,
        )
    except Exception as exc:
        _raise_llm_service_unavailable(
            action="llm.chat.workflow",
            actor_id=req.actor_id,
            tenant_id=req.tenant_id,
            target=req.capability,
            exc=exc,
        )
    shadow_advisory = build_assistant_response_shadow_advisory(
        _shadow_runtime(),
        request_id=_assistant_response_shadow_request_id(
            route="/api/v1/chat/workflow",
            conversation_id=result.conversation_id,
            response_ref=result.workflow_id,
            model_or_capability=req.capability,
        ),
        user_input=req.message,
        assistant_content=result.response_content,
        route="/api/v1/chat/workflow",
        tenant_id=req.tenant_id,
        model_name=req.capability,
        succeeded=result.status == "completed",
        created_at=_created_at(),
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
        "inceptadive_shadow_advisory": shadow_advisory,
        "governed": True,
    }


@router.get("/api/v1/chat/workflow/history")
def chat_workflow_history(limit: str = "50"):
    """Chat workflow execution history."""
    try:
        read_limit = _coerce_chat_workflow_history_limit(limit)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail=_chat_workflow_history_error_detail(
                "invalid chat workflow history request",
                "chat_workflow_history_invalid_request",
            ),
        ) from error
    return {
        "history": [
            {"conversation": r.conversation_id, "workflow": r.workflow_id,
             "status": r.status, "cost": r.cost}
            for r in deps.chat_workflow.history(limit=read_limit)
        ],
        "summary": deps.chat_workflow.summary(),
    }


def _shadow_runtime() -> InceptaDiveShadowRuntime:
    """Return the registered shadow runtime or an env-derived fallback."""

    try:
        runtime = deps.get("inceptadive_shadow_runtime")
    except RuntimeError:
        return build_inceptadive_shadow_runtime(os.environ)
    if isinstance(runtime, InceptaDiveShadowRuntime):
        return runtime
    return build_inceptadive_shadow_runtime(os.environ)


def _created_at() -> str:
    try:
        clock = deps.get("clock")
    except RuntimeError:
        return "1970-01-01T00:00:00+00:00"
    try:
        value = clock() if callable(clock) else clock
    except (TypeError, ValueError):
        return "1970-01-01T00:00:00+00:00"
    return str(value or "1970-01-01T00:00:00+00:00")


def _assistant_response_shadow_request_id(
    *,
    route: str,
    conversation_id: str,
    response_ref: str,
    model_or_capability: str,
) -> str:
    return "assistant_response_shadow_" + stable_identifier(
        "assistant-response-shadow",
        {
            "route": route,
            "conversation_id": conversation_id,
            "response_ref": response_ref,
            "model_or_capability": model_or_capability,
        },
    )


def _stream_with_shadow_advisory(
    sse_events: Iterator[str],
    advisory: dict[str, object],
) -> Iterator[str]:
    """Insert one redacted advisory SSE event without changing stream payloads."""

    inserted = False
    advisory_event = StreamEvent(event_type="inceptadive_shadow_advisory", data=advisory).to_sse()
    for event in sse_events:
        yield event
        if not inserted and event.startswith("event: meta"):
            yield advisory_event
            inserted = True
    if not inserted:
        yield advisory_event
