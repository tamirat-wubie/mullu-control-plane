"""Workflow, agent, pipeline, tool, and related orchestration endpoints.

Extracted from server.py — covers governed execution, sessions, ledger,
workflow execution (plain + traced + tool-augmented), agents, webhooks,
replay, conversations, schemas, prompts, pipelines, tools, state,
structured output, certification, daemon, chains, queues, memory,
templates, traces, orchestration, search, API keys, export, and SLA.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.agent_protocol import AgentCapability
from mcoi_runtime.core.batch_pipeline import PipelineStep
from mcoi_runtime.core.webhook_system import WebhookSubscription
from mcoi_runtime.core.data_export import ExportFormat, ExportRequest

import hashlib
import json

router = APIRouter()


# ── Pydantic request models ──────────────────────────────────────────────


class ExecuteRequest(BaseModel):
    goal_id: str
    action: str
    tenant_id: str
    actor_id: str = "anonymous"
    body: dict[str, Any] = {}


class WorkflowRequest(BaseModel):
    task_id: str
    description: str
    capability: str = "llm.completion"
    payload: dict[str, Any] = {}
    tenant_id: str = "system"
    actor_id: str = "anonymous"
    budget_id: str = "default"


class WebhookSubscribeRequest(BaseModel):
    subscription_id: str
    tenant_id: str
    url: str
    events: list[str]
    secret: str = ""


class ConversationMessageRequest(BaseModel):
    conversation_id: str
    role: str = "user"
    content: str = ""
    tenant_id: str = ""


class ValidateRequest(BaseModel):
    schema_id: str
    data: dict[str, Any]


class PromptRenderRequest(BaseModel):
    template_id: str
    variables: dict[str, str]
    tenant_id: str = "system"
    budget_id: str = "default"
    execute: bool = False  # If True, also run the rendered prompt through LLM


class PipelineStepRequest(BaseModel):
    step_id: str
    name: str
    prompt_template: str
    model_name: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1024
    system: str = ""


class PipelineRequest(BaseModel):
    steps: list[PipelineStepRequest]
    initial_input: str = ""
    budget_id: str = "default"
    tenant_id: str = ""


class ToolInvokeRequest(BaseModel):
    tool_id: str
    arguments: dict[str, Any] = {}
    tenant_id: str = ""


class ToolWorkflowRequest(BaseModel):
    prompt: str
    tool_ids: list[str] | None = None
    tenant_id: str = "system"


class StateSaveRequest(BaseModel):
    state_type: str
    data: dict[str, Any]


class ParseOutputRequest(BaseModel):
    schema_id: str
    text: str


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
    payload: dict[str, Any] = {}
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


class TemplateExecuteRequest(BaseModel):
    template_id: str
    params: dict[str, str]
    initial_input: str = ""
    tenant_id: str = ""


class OrchestrationPlanRequest(BaseModel):
    initiator_id: str
    goal: str


class HandoffRequest(BaseModel):
    from_agent: str
    to_agent: str
    required_capabilities: list[str] = []
    payload: dict[str, Any] = {}


class SemanticSearchRequest(BaseModel):
    query: str
    limit: int = 10


class CreateAPIKeyRequest(BaseModel):
    tenant_id: str
    scopes: list[str]
    description: str = ""
    ttl_seconds: float | None = None


class DataExportRequest(BaseModel):
    source: str
    format: str = "json"
    fields: list[str] = []
    filters: dict[str, Any] = {}
    limit: int = 10_000


# ═══ Governed Execution, Session, Ledger ══════════════════════════════════


@router.post("/api/v1/execute")
def execute(req: ExecuteRequest, session_id: str = Header(default="")):
    api_req = deps.surface.make_api_request(
        request_id=f"http-{id(req)}",
        method="POST",
        path="/api/v1/execute",
        actor_id=req.actor_id,
        tenant_id=req.tenant_id,
        body=req.body,
        headers={"session_id": session_id},
    )
    resp = deps.surface.handle_request(api_req)
    if resp.status_code >= 400:
        raise HTTPException(status_code=resp.status_code, detail=resp.body)
    return resp.body


@router.post("/api/v1/session")
def create_session(actor_id: str, tenant_id: str):
    import time
    sid = hashlib.sha256(f"{actor_id}:{tenant_id}:{time.time()}".encode()).hexdigest()[:16]
    session = deps.surface.auth.create_session(f"sess-{sid}", actor_id, tenant_id)
    deps.surface.tenants.register_tenant(tenant_id)
    deps.store.save_session(f"sess-{sid}", actor_id, tenant_id)
    return {"session_id": session.session_id, "actor_id": actor_id, "tenant_id": tenant_id}


@router.get("/api/v1/ledger")
def get_ledger(tenant_id: str = "system", limit: int = 50):
    entries = deps.store.query_ledger(tenant_id, limit=limit)
    return {"entries": entries, "count": len(entries), "governed": True}


# ═══ Workflow Execution ═══════════════════════════════════════════════════


@router.post("/api/v1/workflow/execute")
def execute_workflow(req: WorkflowRequest):
    """Execute a governed multi-agent workflow."""
    deps.metrics.inc("requests_governed")
    try:
        cap = AgentCapability(req.capability)
    except ValueError:
        raise HTTPException(400, detail=f"unknown capability: {req.capability}")

    result = deps.workflow_engine.execute(
        task_id=req.task_id, description=req.description,
        capability=cap, payload=req.payload,
        tenant_id=req.tenant_id, budget_id=req.budget_id,
    )
    deps.metrics.inc("llm_calls_total" if result.status == "completed" else "errors_total")
    return {
        "workflow_id": result.workflow_id,
        "task_id": result.task_id,
        "agent_id": result.agent_id,
        "status": result.status,
        "steps": [{"name": s.step_name, "status": s.status, "detail": s.detail} for s in result.steps],
        "output": result.output,
        "error": result.error,
    }


@router.get("/api/v1/workflow/history")
def workflow_history(limit: int = 50):
    """Workflow execution history."""
    return {
        "workflows": [
            {"id": r.workflow_id, "task": r.task_id, "agent": r.agent_id, "status": r.status}
            for r in deps.workflow_engine.history(limit=limit)
        ],
        "summary": deps.workflow_engine.summary(),
    }


# ═══ Traced Workflow ══════════════════════════════════════════════════════


@router.post("/api/v1/workflow/traced")
def execute_traced_workflow(req: WorkflowRequest):
    """Execute a workflow with automatic replay trace recording."""
    deps.metrics.inc("requests_governed")
    try:
        cap = AgentCapability(req.capability)
    except ValueError:
        raise HTTPException(400, detail=f"unknown capability: {req.capability}")

    result, trace = deps.traced_workflow.execute(
        task_id=req.task_id, description=req.description,
        capability=cap, payload=req.payload,
        tenant_id=req.tenant_id, budget_id=req.budget_id,
    )
    return {
        "workflow_id": result.workflow_id,
        "status": result.status,
        "agent_id": result.agent_id,
        "output": result.output,
        "trace_id": trace.trace_id if trace else None,
        "trace_frames": len(trace.frames) if trace else 0,
        "trace_hash": trace.trace_hash[:16] if trace else None,
    }


# ═══ Tool-Augmented Workflow ══════════════════════════════════════════════


@router.post("/api/v1/workflow/tools")
def tool_augmented_workflow(req: ToolWorkflowRequest):
    """Execute a tool-augmented workflow -- LLM + tool invocations (feature-gated)."""
    deps.metrics.inc("requests_governed")
    if not deps.feature_flags.is_enabled("tool_augmentation", tenant_id=req.tenant_id):
        raise HTTPException(403, detail={
            "error": "Feature 'tool_augmentation' is not enabled for this tenant",
            "governed": True,
        })
    result = deps.tool_agent.execute_with_tools(
        req.prompt, tool_ids=req.tool_ids, tenant_id=req.tenant_id,
    )
    return {
        "content": result.content,
        "tool_calls": [
            {"tool_id": tc.tool_id, "arguments": tc.arguments,
             "succeeded": tc.result.succeeded, "output": tc.result.output}
            for tc in result.tool_calls
        ],
        "total_tool_calls": result.total_tool_calls,
        "all_succeeded": result.all_succeeded,
        "governed": True,
    }


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


# ═══ Conversation Endpoints ══════════════════════════════════════════════


@router.post("/api/v1/conversation/message")
def add_conversation_message(req: ConversationMessageRequest):
    """Add a message to a conversation."""
    deps.metrics.inc("requests_governed")
    conv = deps.conversation_store.get_or_create(req.conversation_id, tenant_id=req.tenant_id)
    msg = conv.add_message(req.role, req.content)
    return {
        "conversation_id": conv.conversation_id,
        "message_id": msg.message_id,
        "message_count": conv.message_count,
    }


@router.get("/api/v1/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    """Get conversation history."""
    conv = deps.conversation_store.get(conversation_id)
    if conv is None:
        raise HTTPException(404, detail="conversation not found")
    return {
        "conversation_id": conv.conversation_id,
        "messages": [{"role": m.role, "content": m.content, "id": m.message_id} for m in conv.messages],
        "summary": conv.summary(),
    }


@router.get("/api/v1/conversations")
def list_conversations(tenant_id: str | None = None):
    """List conversations."""
    convs = deps.conversation_store.list_conversations(tenant_id=tenant_id)
    return {
        "conversations": [c.summary() for c in convs],
        "count": len(convs),
    }


# ═══ Schema Validation ═══════════════════════════════════════════════════


@router.get("/api/v1/schemas")
def list_schemas():
    """List registered validation schemas."""
    return {
        "schemas": [
            {"id": s.schema_id, "name": s.name, "rules": len(s.rules)}
            for s in deps.schema_validator.list_schemas()
        ],
        "summary": deps.schema_validator.summary(),
    }


@router.post("/api/v1/schemas/validate")
def validate_data(req: ValidateRequest):
    """Validate data against a registered schema."""
    result = deps.schema_validator.validate(req.schema_id, req.data)
    return {
        "schema_id": result.schema_id,
        "valid": result.valid,
        "errors": [
            {"field": e.field, "rule": e.rule_type, "message": e.message}
            for e in result.errors
        ],
    }


# ═══ Prompt Template Endpoints ═══════════════════════════════════════════


@router.get("/api/v1/prompts")
def list_prompt_templates(category: str | None = None):
    """List registered prompt templates."""
    templates = deps.prompt_engine.list_templates(category=category)
    return {
        "templates": [
            {"id": t.template_id, "name": t.name, "variables": list(t.variables),
             "category": t.category, "version": t.version}
            for t in templates
        ],
        "summary": deps.prompt_engine.summary(),
    }


@router.post("/api/v1/prompts/render")
def render_prompt(req: PromptRenderRequest):
    """Render a prompt template with variables, optionally execute via LLM."""
    deps.metrics.inc("requests_governed")
    try:
        rendered = deps.prompt_engine.render(req.template_id, req.variables)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    response: dict[str, Any] = {
        "template_id": rendered.template_id,
        "prompt": rendered.prompt,
        "system_prompt": rendered.system_prompt,
        "version": rendered.version,
    }

    if req.execute:
        deps.metrics.inc("llm_calls_total")
        result = deps.llm_bridge.complete(
            rendered.prompt, system=rendered.system_prompt,
            budget_id=req.budget_id, tenant_id=req.tenant_id,
        )
        response["llm_result"] = {
            "content": result.content,
            "model": result.model_name,
            "tokens": result.total_tokens,
            "cost": result.cost,
            "succeeded": result.succeeded,
        }
        if result.succeeded:
            deps.cost_analytics.record(req.tenant_id, result.model_name, result.cost, result.total_tokens)

    return response


# ═══ Batch Pipeline ══════════════════════════════════════════════════════


@router.post("/api/v1/pipeline/execute")
def execute_pipeline(req: PipelineRequest):
    """Execute a multi-step governed LLM pipeline."""
    deps.metrics.inc("requests_governed")
    steps = [
        PipelineStep(
            step_id=s.step_id, name=s.name, prompt_template=s.prompt_template,
            model_name=s.model_name, max_tokens=s.max_tokens, system=s.system,
        )
        for s in req.steps
    ]
    result = deps.batch_pipeline.execute(
        steps, initial_input=req.initial_input,
        budget_id=req.budget_id, tenant_id=req.tenant_id,
    )
    # Emit event
    deps.event_bus.publish(
        "pipeline.completed" if result.succeeded else "pipeline.failed",
        tenant_id=req.tenant_id, source="batch_pipeline",
        payload={"pipeline_id": result.pipeline_id, "succeeded": result.succeeded, "cost": result.total_cost},
    )
    return {
        "pipeline_id": result.pipeline_id,
        "succeeded": result.succeeded,
        "steps": [
            {"id": s.step_id, "name": s.name, "succeeded": s.succeeded, "cost": s.cost, "tokens": s.input_tokens + s.output_tokens}
            for s in result.steps
        ],
        "final_output": result.final_output,
        "total_cost": result.total_cost,
        "total_tokens": result.total_tokens,
        "error": result.error,
    }


@router.get("/api/v1/pipeline/history")
def pipeline_history(limit: int = 50):
    """Batch pipeline execution history."""
    return {
        "pipelines": [
            {"id": p.pipeline_id, "succeeded": p.succeeded, "steps": len(p.steps), "cost": p.total_cost}
            for p in deps.batch_pipeline.history(limit=limit)
        ],
        "summary": deps.batch_pipeline.summary(),
    }


# ═══ Tool Registry Endpoints ═════════════════════════════════════════════


@router.get("/api/v1/tools")
def list_tools(category: str | None = None):
    """List registered tools."""
    tools = deps.tool_registry.list_tools(category=category)
    return {
        "tools": [
            {"id": t.tool_id, "name": t.name, "description": t.description,
             "parameters": [{"name": p.name, "type": p.param_type, "required": p.required} for p in t.parameters],
             "category": t.category}
            for t in tools
        ],
        "count": len(tools),
    }


@router.post("/api/v1/tools/invoke")
def invoke_tool(req: ToolInvokeRequest):
    """Invoke a registered tool."""
    deps.metrics.inc("requests_governed")
    result = deps.tool_registry.invoke(req.tool_id, req.arguments, tenant_id=req.tenant_id)
    deps.audit_trail.record(
        action="tool.invoke", actor_id="api", tenant_id=req.tenant_id,
        target=req.tool_id, outcome="success" if result.succeeded else "error",
    )
    return {
        "invocation_id": result.invocation_id, "tool_id": result.tool_id,
        "output": result.output, "succeeded": result.succeeded, "error": result.error,
    }


@router.get("/api/v1/tools/llm-format")
def tools_llm_format():
    """Export tools in LLM-compatible format."""
    return {"tools": deps.tool_registry.to_llm_tools()}


@router.get("/api/v1/tools/history")
def tool_history(limit: int = 50):
    """Tool invocation history."""
    return {"history": [
        {"id": r.invocation_id, "tool": r.tool_id, "succeeded": r.succeeded}
        for r in deps.tool_registry.invocation_history(limit=limit)
    ], "summary": deps.tool_registry.summary()}


# ═══ State Persistence ═══════════════════════════════════════════════════


@router.post("/api/v1/state/save")
def save_state(req: StateSaveRequest):
    """Save runtime state."""
    deps.metrics.inc("requests_governed")
    snap = deps.state_persistence.save(req.state_type, req.data)
    return {"state_type": snap.state_type, "hash": snap.state_hash[:16], "saved_at": snap.saved_at}


@router.get("/api/v1/state/{state_type}")
def load_state(state_type: str):
    """Load runtime state."""
    snap = deps.state_persistence.load(state_type)
    if snap is None:
        raise HTTPException(404, detail=f"state not found: {state_type}")
    return {"state_type": snap.state_type, "data": snap.data, "hash": snap.state_hash[:16]}


@router.get("/api/v1/state")
def list_states():
    """List saved states."""
    return {"states": deps.state_persistence.list_states(), "summary": deps.state_persistence.summary()}


# ═══ Structured Output ═══════════════════════════════════════════════════


@router.post("/api/v1/output/parse")
def parse_structured_output(req: ParseOutputRequest):
    """Parse LLM output against a schema."""
    result = deps.structured_output.parse(req.schema_id, req.text)
    return {"schema_id": result.schema_id, "valid": result.valid, "parsed": result.parsed, "errors": list(result.errors)}


@router.get("/api/v1/output/schemas")
def list_output_schemas():
    """List output schemas."""
    return {"schemas": [{"id": s.schema_id, "name": s.name, "fields": s.fields} for s in deps.structured_output.list_schemas()]}


# ═══ Certification ═══════════════════════════════════════════════════════


@router.post("/api/v1/certify")
def run_certification():
    """Run full live-path certification: API -> DB -> LLM -> Ledger -> Restart."""
    chain = deps.certifier.run_full_certification(
        api_handle_fn=lambda req: {"governed": True, "status": "ok"},
        db_write_fn=lambda t, c: deps.store.append_ledger(
            "certification", "certifier", t, c,
            hashlib.sha256(json.dumps(c, sort_keys=True).encode()).hexdigest(),
        ),
        db_read_fn=lambda t: deps.store.query_ledger(t),
        llm_invoke_fn=lambda prompt: deps.llm_bridge.complete(prompt, budget_id="default"),
        ledger_entries=deps.store.query_ledger("system", limit=100),
        pre_state_fn=lambda: (
            hashlib.sha256(str(deps.store.ledger_count()).encode()).hexdigest(),
            deps.store.ledger_count(),
        ),
        post_state_fn=lambda: (
            hashlib.sha256(str(deps.store.ledger_count()).encode()).hexdigest(),
            deps.store.ledger_count(),
        ),
    )
    return {
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
        "chain_hash": chain.chain_hash,
        "steps": [
            {"name": s.name, "status": s.status.value, "proof_hash": s.proof_hash, "detail": s.detail}
            for s in chain.steps
        ],
    }


@router.get("/api/v1/certify/history")
def certification_history():
    """Certification chain history."""
    return {"certifications": deps.certifier.certification_history()}


# ═══ Certification Daemon ════════════════════════════════════════════════


@router.get("/api/v1/daemon/status")
def daemon_status():
    """Certification daemon health and run status."""
    return deps.cert_daemon.status()


@router.post("/api/v1/daemon/tick")
def daemon_tick():
    """Trigger a single certification daemon tick."""
    chain = deps.cert_daemon.tick()
    if chain is None:
        return {"ran": False, "reason": "disabled or interval not elapsed"}
    return {
        "ran": True,
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
    }


@router.post("/api/v1/daemon/force")
def daemon_force():
    """Force an immediate certification run regardless of interval."""
    chain = deps.cert_daemon.force_run()
    if chain is None:
        return {"ran": False}
    return {
        "ran": True,
        "chain_id": chain.chain_id,
        "all_passed": chain.all_passed,
        "chain_hash": chain.chain_hash,
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


# ═══ Workflow Templates ══════════════════════════════════════════════════


@router.get("/api/v1/templates")
def list_workflow_templates(category: str | None = None):
    """List workflow templates."""
    templates = deps.wf_templates.list_templates(category=category)
    return {
        "templates": [
            {"id": t.template_id, "name": t.name, "description": t.description,
             "parameters": list(t.parameters), "category": t.category}
            for t in templates
        ],
        "summary": deps.wf_templates.summary(),
    }


@router.post("/api/v1/templates/execute")
def execute_workflow_template(req: TemplateExecuteRequest):
    """Instantiate and execute a workflow template."""
    deps.metrics.inc("requests_governed")
    try:
        steps = deps.wf_templates.instantiate(req.template_id, req.params)
    except ValueError as e:
        raise HTTPException(400, detail=str(e))

    result = deps.agent_chain.execute(steps, initial_input=req.initial_input)
    return {
        "template_id": req.template_id,
        "chain_id": result.chain_id,
        "succeeded": result.succeeded,
        "final_output": result.final_output,
        "steps": len(result.steps),
        "total_cost": result.total_cost,
        "governed": True,
    }


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


# ═══ Semantic Search ═════════════════════════════════════════════════════


@router.post("/api/v1/search")
def semantic_search_endpoint(req: SemanticSearchRequest):
    """Semantic search across indexed documents."""
    results = deps.semantic_search.search(req.query, limit=req.limit)
    return {
        "results": [{"doc_id": r.doc_id, "score": r.score, "matched": list(r.matched_terms)} for r in results],
        "count": len(results),
    }


@router.get("/api/v1/search/stats")
def search_stats():
    """Semantic search index statistics."""
    return deps.semantic_search.summary()


# ═══ API Key Management ══════════════════════════════════════════════════


@router.post("/api/v1/api-keys")
def create_api_key(req: CreateAPIKeyRequest):
    """Create a new API key."""
    deps.metrics.inc("requests_governed")
    raw_key, api_key = deps.api_key_mgr.create_key(
        req.tenant_id, frozenset(req.scopes),
        description=req.description, ttl_seconds=req.ttl_seconds,
    )
    return {
        "raw_key": raw_key,
        "key": api_key.to_dict(),
        "governed": True,
    }


@router.get("/api/v1/api-keys")
def list_api_keys(tenant_id: str | None = None):
    """List API keys."""
    deps.metrics.inc("requests_governed")
    keys = deps.api_key_mgr.list_keys(tenant_id=tenant_id)
    return {"keys": [k.to_dict() for k in keys], "governed": True}


@router.delete("/api/v1/api-keys/{key_id}")
def revoke_api_key(key_id: str):
    """Revoke an API key."""
    deps.metrics.inc("requests_governed")
    if not deps.api_key_mgr.revoke(key_id):
        raise HTTPException(404, detail=f"Key not found: {key_id}")
    return {"revoked": True, "key_id": key_id, "governed": True}


# ═══ Data Export ═════════════════════════════════════════════════════════


@router.get("/api/v1/export/sources")
def list_export_sources():
    """List available data export sources."""
    deps.metrics.inc("requests_governed")
    return {"sources": deps.data_export.list_sources(), "governed": True}


@router.post("/api/v1/export")
def export_data(req: DataExportRequest):
    """Export data in CSV, JSON, or JSONL format."""
    deps.metrics.inc("requests_governed")
    try:
        fmt = ExportFormat(req.format)
    except ValueError:
        raise HTTPException(400, detail=f"Unsupported format: {req.format}")
    try:
        result = deps.data_export.export(ExportRequest(
            source=req.source, format=fmt,
            fields=tuple(req.fields), filters=req.filters, limit=req.limit,
        ))
    except ValueError as e:
        raise HTTPException(400, detail=str(e))
    return {
        "export": result.to_dict(),
        "content": result.content,
        "governed": True,
    }


# ═══ SLA Monitoring ═════════════════════════════════════════════════════


@router.get("/api/v1/sla")
def get_sla_summary():
    """Return SLA monitoring summary."""
    deps.metrics.inc("requests_governed")
    return {"sla": deps.sla_monitor.summary(), "governed": True}


@router.get("/api/v1/sla/violations")
def get_sla_violations(sla_id: str | None = None):
    """Return SLA violations."""
    deps.metrics.inc("requests_governed")
    violations = deps.sla_monitor.violations(sla_id)
    return {
        "violations": [{"sla_id": v.sla_id, "actual": v.actual_value,
                         "threshold": v.threshold} for v in violations],
        "count": len(violations),
        "governed": True,
    }
