"""Agent-centric endpoints: registry, webhooks, replay, chains, queues,
memory, request tracing, and orchestration.

Extracted from workflow.py to keep router files focused.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.webhook_system import WebhookSubscription

router = APIRouter()


# ── Pydantic request models ──────────────────────────────────────────────


class WebhookSubscribeRequest(BaseModel):
    subscription_id: str
    tenant_id: str
    url: str
    events: list[str]
    secret: str = ""


class ChainStepRequest(BaseModel):
    step_id: str
    name: str
    prompt_template: str
    on_failure: str = "halt"


class ChainRequest(BaseModel):
    steps: list[ChainStepRequest]
    initial_input: str = ""
    tenant_id: str = ""


class QueueSubmitRequest(BaseModel):
    task_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    tenant_id: str = ""


class MemoryStoreRequest(BaseModel):
    agent_id: str
    tenant_id: str
    category: str = "fact"
    content: str = ""
    keywords: list[str] | None = None
    confidence: float = 1.0


class MemorySearchRequest(BaseModel):
    agent_id: str
    tenant_id: str
    query: str
    limit: int = 5


class OrchestrationPlanRequest(BaseModel):
    initiator_id: str
    goal: str


class HandoffRequest(BaseModel):
    from_agent: str
    to_agent: str
    required_capabilities: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)


# ═══ Agent Registry ══════════════════════════════════════════════════════


@router.get("/api/v1/agents")
def list_agents():
    """List registered agents and their capabilities."""
    agents = deps.agent_registry.list_agents()
    return {
        "agents": [
            {"id": a.agent_id, "name": a.name, "capabilities": [c.value for c in a.capabilities], "enabled": a.enabled}
            for a in agents
        ],
        "count": len(agents),
    }


@router.get("/api/v1/agents/{agent_id}/tasks")
def agent_tasks(agent_id: str):
    """Get tasks assigned to an agent."""
    deps.metrics.inc("requests_governed")
    return {"agent_id": agent_id, "task_count": deps.task_manager.task_count, "summary": deps.task_manager.summary()}


# ═══ Webhook Endpoints ═══════════════════════════════════════════════════


@router.post("/api/v1/webhooks/subscribe")
def webhook_subscribe(req: WebhookSubscribeRequest):
    """Subscribe to webhook events."""
    deps.metrics.inc("requests_governed")
    sub = WebhookSubscription(
        subscription_id=req.subscription_id, tenant_id=req.tenant_id,
        url=req.url, events=tuple(req.events), secret=req.secret,
    )
    deps.webhook_manager.subscribe(sub)
    deps.audit_trail.record(
        action="webhook.subscribe", actor_id="system",
        tenant_id=req.tenant_id, target=req.subscription_id, outcome="success",
    )
    return {"subscription_id": sub.subscription_id, "events": list(sub.events)}


@router.get("/api/v1/webhooks")
def list_webhooks(tenant_id: str | None = None):
    """List webhook subscriptions."""
    subs = deps.webhook_manager.list_subscriptions(tenant_id=tenant_id)
    return {
        "subscriptions": [
            {"id": s.subscription_id, "tenant": s.tenant_id, "url": s.url, "events": list(s.events), "enabled": s.enabled}
            for s in subs
        ],
        "count": len(subs),
    }


@router.get("/api/v1/webhooks/deliveries")
def webhook_deliveries(limit: int = 50):
    """Recent webhook delivery history."""
    return {
        "deliveries": [
            {"id": d.delivery_id, "subscription": d.subscription_id, "event": d.event, "status": d.status, "at": d.created_at}
            for d in deps.webhook_manager.delivery_history(limit=limit)
        ],
    }


@router.get("/api/v1/webhooks/retry/summary")
def get_webhook_retry_summary():
    """Return webhook retry engine summary."""
    deps.metrics.inc("requests_governed")
    return {"webhook_retry": deps.webhook_retry.summary(), "governed": True}


@router.get("/api/v1/webhooks/retry/dead-letters")
def get_dead_letters():
    """Return dead-lettered webhook deliveries."""
    deps.metrics.inc("requests_governed")
    return {
        "dead_letters": [d.to_dict() for d in deps.webhook_retry.dead_letters],
        "count": deps.webhook_retry.dead_letter_count,
        "governed": True,
    }


# ═══ Replay Traces ═══════════════════════════════════════════════════════


@router.get("/api/v1/replay/traces")
def list_traces(limit: int = 50):
    """Execution replay traces."""
    traces = deps.replay_recorder.list_traces(limit=limit)
    return {
        "traces": [
            {"id": t.trace_id, "frames": len(t.frames), "hash": t.trace_hash[:16], "at": t.recorded_at}
            for t in traces
        ],
        "count": len(traces),
        "summary": deps.replay_recorder.summary(),
    }


# ═══ Agent Chain ═════════════════════════════════════════════════════════


@router.post("/api/v1/chain/execute")
def execute_chain(req: ChainRequest):
    """Execute a multi-agent chain."""
    from mcoi_runtime.core.agent_chain import ChainStep
    deps.metrics.inc("requests_governed")
    steps = [ChainStep(step_id=s.step_id, name=s.name, prompt_template=s.prompt_template, on_failure=s.on_failure) for s in req.steps]
    result = deps.agent_chain.execute(steps, initial_input=req.initial_input)
    deps.event_bus.publish("chain.completed" if result.succeeded else "chain.failed",
                           tenant_id=req.tenant_id, source="agent_chain",
                           payload={"chain_id": result.chain_id, "succeeded": result.succeeded})
    return {
        "chain_id": result.chain_id, "succeeded": result.succeeded,
        "steps": [{"id": s.step_id, "name": s.name, "succeeded": s.succeeded, "cost": s.cost} for s in result.steps],
        "final_output": result.final_output, "total_cost": result.total_cost,
        "error": result.error, "governed": True,
    }


@router.get("/api/v1/chain/history")
def chain_history(limit: int = 50):
    """Agent chain execution history."""
    return {"chains": [
        {"id": c.chain_id, "succeeded": c.succeeded, "steps": len(c.steps), "cost": c.total_cost}
        for c in deps.agent_chain.history(limit=limit)
    ], "summary": deps.agent_chain.summary()}


# ═══ Task Queue ══════════════════════════════════════════════════════════


@router.post("/api/v1/queue/submit")
def queue_submit(req: QueueSubmitRequest):
    """Submit a task to the async queue."""
    deps.metrics.inc("requests_governed")
    task = deps.task_queue.submit(req.task_id, req.payload, priority=req.priority, tenant_id=req.tenant_id)
    return {"task_id": task.task_id, "priority": task.priority, "queued_at": task.submitted_at}


@router.post("/api/v1/queue/process")
def queue_process():
    """Process one task from the queue."""
    deps.metrics.inc("requests_governed")
    result = deps.task_queue.process_one(lambda payload: {"processed": True, **payload})
    if result is None:
        return {"processed": False, "reason": "queue empty"}
    return {"processed": True, "task_id": result.task_id, "succeeded": result.succeeded, "output": result.output}


@router.get("/api/v1/queue/status")
def queue_status():
    """Task queue status."""
    return deps.task_queue.summary()


@router.get("/api/v1/queue/result/{task_id}")
def queue_result(task_id: str):
    """Get task result."""
    result = deps.task_queue.get_result(task_id)
    if result is None:
        raise HTTPException(404, detail="task result not found")
    return {"task_id": result.task_id, "output": result.output, "succeeded": result.succeeded}


# ═══ Agent Memory ════════════════════════════════════════════════════════


@router.post("/api/v1/memory/store")
def store_memory(req: MemoryStoreRequest):
    """Store a long-term memory for an agent."""
    deps.metrics.inc("requests_governed")
    entry = deps.agent_memory.store(
        req.agent_id, req.tenant_id, req.category,
        req.content, keywords=req.keywords, confidence=req.confidence,
    )
    return {"memory_id": entry.memory_id, "agent_id": entry.agent_id, "category": entry.category}


@router.post("/api/v1/memory/search")
def search_memory(req: MemorySearchRequest):
    """Search agent memories by relevance."""
    results = deps.agent_memory.search(req.agent_id, req.tenant_id, req.query, limit=req.limit)
    return {
        "results": [
            {"memory_id": r.memory.memory_id, "content": r.memory.content,
             "category": r.memory.category, "relevance": r.relevance_score}
            for r in results
        ],
        "count": len(results),
    }


@router.get("/api/v1/memory/summary")
def memory_summary():
    """Agent memory summary."""
    return deps.agent_memory.summary()


# ═══ Request Tracing ════════════════════════════════════════════════════


@router.get("/api/v1/traces")
def get_tracing_summary():
    """Return tracing summary statistics."""
    deps.metrics.inc("requests_governed")
    return {"tracing": deps.request_tracer.summary(), "governed": True}


@router.get("/api/v1/traces/{trace_id}")
def get_trace(trace_id: str):
    """Return spans for a specific trace."""
    deps.metrics.inc("requests_governed")
    spans = deps.request_tracer.get_trace(trace_id)
    if not spans:
        raise HTTPException(404, detail=f"Trace not found: {trace_id}")
    return {
        "trace_id": trace_id,
        "spans": [s.to_dict() for s in spans],
        "governed": True,
    }


@router.get("/api/v1/traces/slow")
def get_slow_traces(threshold_ms: float = 1000.0):
    """Return traces exceeding latency threshold."""
    deps.metrics.inc("requests_governed")
    return {"slow_traces": deps.request_tracer.slow_traces(threshold_ms), "governed": True}


# ═══ Agent Orchestration ═════════════════════════════════════════════════


@router.get("/api/v1/orchestration")
def get_orchestration_summary():
    """Return orchestration summary."""
    deps.metrics.inc("requests_governed")
    return {"orchestration": deps.agent_orchestrator.summary(), "governed": True}


@router.post("/api/v1/orchestration/plans")
def create_orchestration_plan(req: OrchestrationPlanRequest):
    """Create a new multi-agent orchestration plan."""
    deps.metrics.inc("requests_governed")
    try:
        plan = deps.agent_orchestrator.create_plan(req.initiator_id, req.goal)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {"plan": plan.to_dict(), "governed": True}


@router.get("/api/v1/orchestration/plans/{plan_id}")
def get_orchestration_plan(plan_id: str):
    """Get orchestration plan details."""
    deps.metrics.inc("requests_governed")
    plan = deps.agent_orchestrator.get_plan(plan_id)
    if not plan:
        raise HTTPException(404, detail=f"Plan not found: {plan_id}")
    return {"plan": plan.to_dict(), "governed": True}


@router.post("/api/v1/orchestration/handoff")
def agent_handoff(req: HandoffRequest):
    """Execute an agent-to-agent handoff."""
    deps.metrics.inc("requests_governed")
    result = deps.agent_orchestrator.handoff(
        req.from_agent, req.to_agent,
        required_capabilities=tuple(req.required_capabilities),
        payload=req.payload,
    )
    return {
        "from_agent": result.from_agent,
        "to_agent": result.to_agent,
        "success": result.success,
        "error": result.error,
        "governed": True,
    }
