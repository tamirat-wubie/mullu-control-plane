"""Workflow and pipeline execution endpoints.

Covers governed execution, sessions, ledger, workflow execution
(plain + traced + tool-augmented), batch pipelines, and templates.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.agent_protocol import AgentCapability
from mcoi_runtime.core.batch_pipeline import PipelineStep

import hashlib

router = APIRouter()


def _workflow_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


# ── Pydantic request models ──────────────────────────────────────────────


class ExecuteRequest(BaseModel):
    goal_id: str
    action: str
    tenant_id: str
    actor_id: str = "anonymous"
    body: dict[str, Any] = Field(default_factory=dict)


class WorkflowRequest(BaseModel):
    task_id: str
    description: str
    capability: str = "llm.completion"
    payload: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = "system"
    actor_id: str = "anonymous"
    budget_id: str = "default"


class ToolWorkflowRequest(BaseModel):
    prompt: str
    tool_ids: list[str] | None = None
    tenant_id: str = "system"


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


class TemplateExecuteRequest(BaseModel):
    template_id: str
    params: dict[str, str]
    initial_input: str = ""
    tenant_id: str = ""


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
        raise HTTPException(400, detail=_workflow_error_detail("invalid capability", "invalid_capability"))

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
        raise HTTPException(400, detail=_workflow_error_detail("invalid capability", "invalid_capability"))

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
    except ValueError:
        raise HTTPException(400, detail={"error": "invalid template request", "error_code": "validation_error", "governed": True})

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
