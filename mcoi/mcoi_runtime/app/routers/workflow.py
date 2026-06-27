"""Workflow and pipeline execution endpoints.

Covers governed execution, sessions, ledger, workflow execution
(plain + traced + tool-augmented), batch pipelines, and templates.
"""
from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Header, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.cognitive_shadow_integration import (
    read_shadow_observations,
    record_execution_shadow,
)
from mcoi_runtime.app.cognitive_live_integration import (
    evaluate_execution_gate,
    record_execution_learning,
)
from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope, scoped_listing_tenant
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.agent_protocol import AgentCapability
from mcoi_runtime.core.batch_pipeline import PipelineStep
from mcoi_runtime.core.capability_unlock_ladder import build_local_developer_workflow_read_model
from mcoi_runtime.core.request_tracing import TraceContext
from mcoi_runtime.core.tool_use import certify_tool_capability_policy_receipt

import hashlib

router = APIRouter()
_MAX_WORKFLOW_READ_LIMIT = 500


def _workflow_error_detail(error: str, error_code: str) -> dict[str, object]:
    return {"error": error, "error_code": error_code, "governed": True}


def _raise_workflow_validation_error(error: ValueError) -> NoReturn:
    raise HTTPException(
        status_code=422,
        detail=_workflow_error_detail("invalid workflow read request", "workflow_invalid_read_request"),
    ) from error


def _coerce_workflow_read_limit(limit: object) -> int:
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
    if value < 0 or value > _MAX_WORKFLOW_READ_LIMIT:
        raise ValueError("limit is outside the allowed range")
    return value


def _new_http_request_id() -> str:
    """Return a request-unique HTTP witness id for the legacy execution boundary."""
    return f"http-{TraceContext.new().trace_id}"


def _cognitive_block_detail(verdict: str) -> dict[str, object]:
    """Detail for a dispatch withheld by the Stage-B cognitive DECIDE gate.

    Static strings only (the verdict is a fixed enum value, not interpolated
    caller text), so this passes the reflective-contract guard.
    """
    return {
        "error": "cognitive governance gate withheld dispatch pending review",
        "error_code": "cognitive_gate_withheld",
        "verdict": verdict,
        "governed": True,
    }


def _certify_action_proof(
    *,
    endpoint: str,
    tenant_id: str,
    actor_id: str,
    action: str,
    succeeded: bool,
) -> dict[str, object]:
    """Certify a workflow action response with a proof bridge receipt."""
    proof = deps.proof_bridge.certify_governance_decision(
        tenant_id=tenant_id or "system",
        endpoint=endpoint,
        guard_results=[
            {
                "guard_name": "workflow_action_closure",
                "allowed": True,
                "reason": "workflow action reached response boundary",
            }
        ],
        decision="allowed",
        actor_id=actor_id or "anonymous",
        reason="workflow action response certified",
    )
    return {
        "endpoint": endpoint,
        "action": action,
        "succeeded": succeeded,
        "proof_receipt_id": proof.capsule.receipt.receipt_id,
        "proof_hash": proof.receipt_hash,
    }


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
def execute(req: ExecuteRequest, request: Request, session_id: str = Header(default="")):
    enforce_tenant_scope(request, req.tenant_id)
    api_req = deps.surface.make_api_request(
        request_id=_new_http_request_id(),
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
    response_body = dict(resp.body)
    response_body["action_proof"] = _certify_action_proof(
        endpoint="/api/v1/execute",
        tenant_id=req.tenant_id,
        actor_id=req.actor_id,
        action=req.action,
        succeeded=True,
    )
    return response_body


@router.post("/api/v1/session")
def create_session(actor_id: str, tenant_id: str, request: Request):
    enforce_tenant_scope(request, tenant_id)
    import time
    sid = hashlib.sha256(f"{actor_id}:{tenant_id}:{time.time()}".encode()).hexdigest()[:16]
    session = deps.surface.auth.create_session(f"sess-{sid}", actor_id, tenant_id)
    deps.surface.tenants.register_tenant(tenant_id)
    deps.store.save_session(f"sess-{sid}", actor_id, tenant_id)
    return {"session_id": session.session_id, "actor_id": actor_id, "tenant_id": tenant_id}


@router.get("/api/v1/ledger")
def get_ledger(request: Request, tenant_id: str = "system", limit: str = "50"):
    tenant_id = scoped_listing_tenant(request, tenant_id)
    try:
        read_limit = _coerce_workflow_read_limit(limit)
    except ValueError as error:
        _raise_workflow_validation_error(error)
    entries = deps.store.query_ledger(tenant_id, limit=read_limit)
    return {"entries": entries, "count": len(entries), "governed": True}


# ═══ Workflow Execution ═══════════════════════════════════════════════════


@router.post("/api/v1/workflow/execute")
def execute_workflow(req: WorkflowRequest, request: Request):
    """Execute a governed multi-agent workflow."""
    enforce_tenant_scope(request, req.tenant_id)
    deps.metrics.inc("requests_governed")
    try:
        cap = AgentCapability(req.capability)
    except ValueError:
        raise HTTPException(400, detail=_workflow_error_detail("invalid capability", "invalid_capability"))

    # Stage-B cognitive DECIDE gate (default-OFF): may WITHHOLD dispatch on a blocking
    # verdict. fail-OPEN (None => allow); safety-positive (it can only ever refuse).
    _gate = evaluate_execution_gate(deps, capability_id=req.capability)
    if _gate is not None and _gate.blocked:
        raise HTTPException(409, detail=_cognitive_block_detail(_gate.decision_verdict.value))

    result = deps.workflow_engine.execute(
        task_id=req.task_id, description=req.description,
        capability=cap, payload=req.payload,
        tenant_id=req.tenant_id, budget_id=req.budget_id,
    )
    _succeeded = result.status == "completed"
    # Record-only cognitive shadow (default-OFF). No authority over the response.
    record_execution_shadow(deps, capability_id=req.capability, succeeded=_succeeded)
    # Stage-C cognitive learn (default-OFF): feed the outcome back into the organs. Never raises.
    record_execution_learning(
        deps, capability_id=req.capability, succeeded=_succeeded, verified=_succeeded,
        source_ref=result.workflow_id,
    )
    deps.metrics.inc("llm_calls_total" if _succeeded else "errors_total")
    return {
        "workflow_id": result.workflow_id,
        "task_id": result.task_id,
        "agent_id": result.agent_id,
        "status": result.status,
        "steps": [{"name": s.step_name, "status": s.status, "detail": s.detail} for s in result.steps],
        "output": result.output,
        "error": result.error,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/workflow/execute",
            tenant_id=req.tenant_id,
            actor_id=req.actor_id,
            action="workflow.execute",
            succeeded=result.status == "completed",
        ),
    }


@router.get("/api/v1/workflow/history")
def workflow_history(limit: str = "50"):
    """Workflow execution history."""
    try:
        read_limit = _coerce_workflow_read_limit(limit)
    except ValueError as error:
        _raise_workflow_validation_error(error)
    return {
        "workflows": [
            {"id": r.workflow_id, "task": r.task_id, "agent": r.agent_id, "status": r.status}
            for r in deps.workflow_engine.history(limit=read_limit)
        ],
        "summary": deps.workflow_engine.summary(),
    }


@router.get("/api/v1/workflow/local-developer/read-model")
def local_developer_workflow_read_model():
    """Return the read-only Local Developer Workflow v1 operator surface."""
    read_model = build_local_developer_workflow_read_model()
    return {
        "workflow_id": read_model["read_model_id"],
        "read_model": read_model,
        "selectable": read_model["valid"] is True,
        "execution_authority_granted": False,
        "governed": True,
    }


@router.get("/api/v1/cognitive/shadow/observations")
def cognitive_shadow_observations(limit: str = "50"):
    """Read-only view of the cognitive shadow observer's recorded observations.

    Surfaces the evidence the record-only Stage-A shadow gathers on live traffic:
    a ``summary`` (the Stage-B decision signal - how often the cognitive DECIDE
    gate WOULD have withheld dispatch on executions that actually succeeded,
    i.e. ``diverged`` / ``divergence_rate``) plus the recent per-execution
    reports. When shadow mode is OFF (``MULLU_COGNITIVE_LOOP_SHADOW`` unset) the
    observer is absent and this returns ``enabled: false`` with empty data. This
    endpoint holds NO authority - it only reads what the shadow already recorded.
    """
    try:
        read_limit = _coerce_workflow_read_limit(limit)
    except ValueError as error:
        _raise_workflow_validation_error(error)
    return read_shadow_observations(deps, limit=read_limit)


# ═══ Traced Workflow ══════════════════════════════════════════════════════


@router.post("/api/v1/workflow/traced")
def execute_traced_workflow(req: WorkflowRequest, request: Request):
    """Execute a workflow with automatic replay trace recording."""
    enforce_tenant_scope(request, req.tenant_id)
    deps.metrics.inc("requests_governed")
    try:
        cap = AgentCapability(req.capability)
    except ValueError:
        raise HTTPException(400, detail=_workflow_error_detail("invalid capability", "invalid_capability"))

    # Stage-B cognitive DECIDE gate (default-OFF): may WITHHOLD dispatch on a blocking
    # verdict. fail-OPEN (None => allow); safety-positive (it can only ever refuse).
    _gate = evaluate_execution_gate(deps, capability_id=req.capability)
    if _gate is not None and _gate.blocked:
        raise HTTPException(409, detail=_cognitive_block_detail(_gate.decision_verdict.value))

    result, trace = deps.traced_workflow.execute(
        task_id=req.task_id, description=req.description,
        capability=cap, payload=req.payload,
        tenant_id=req.tenant_id, budget_id=req.budget_id,
    )
    _succeeded = result.status == "completed"
    # Record-only cognitive shadow (default-OFF). No authority over the response.
    record_execution_shadow(deps, capability_id=req.capability, succeeded=_succeeded)
    # Stage-C cognitive learn (default-OFF): feed the outcome back into the organs. Never raises.
    record_execution_learning(
        deps, capability_id=req.capability, succeeded=_succeeded, verified=_succeeded,
        source_ref=result.workflow_id,
    )
    return {
        "workflow_id": result.workflow_id,
        "status": result.status,
        "agent_id": result.agent_id,
        "output": result.output,
        "trace_id": trace.trace_id if trace else None,
        "trace_frames": len(trace.frames) if trace else 0,
        "trace_hash": trace.trace_hash[:16] if trace else None,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/workflow/traced",
            tenant_id=req.tenant_id,
            actor_id=req.actor_id,
            action="workflow.traced",
            succeeded=result.status == "completed",
        ),
    }


# ═══ Tool-Augmented Workflow ══════════════════════════════════════════════


@router.post("/api/v1/workflow/tools")
def tool_augmented_workflow(req: ToolWorkflowRequest, request: Request):
    """Execute a tool-augmented workflow -- LLM + tool invocations (feature-gated)."""
    enforce_tenant_scope(request, req.tenant_id)
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
             "succeeded": tc.result.succeeded, "output": tc.result.output,
             "capability_policy_receipt": certify_tool_capability_policy_receipt(
                 tool=deps.tool_registry.get(tc.tool_id),
                 tool_id=tc.tool_id,
                 arguments=tc.arguments,
                 tenant_id=req.tenant_id,
                 invocation_id=tc.result.invocation_id,
                 execution_succeeded=tc.result.succeeded,
             )}
            for tc in result.tool_calls
        ],
        "total_tool_calls": result.total_tool_calls,
        "all_succeeded": result.all_succeeded,
        "governed": True,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/workflow/tools",
            tenant_id=req.tenant_id,
            actor_id="api",
            action="workflow.tools",
            succeeded=result.all_succeeded,
        ),
    }


# ═══ Batch Pipeline ══════════════════════════════════════════════════════


@router.post("/api/v1/pipeline/execute")
def execute_pipeline(req: PipelineRequest, request: Request):
    """Execute a multi-step governed LLM pipeline."""
    enforce_tenant_scope(request, req.tenant_id)
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
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/pipeline/execute",
            tenant_id=req.tenant_id,
            actor_id="api",
            action="pipeline.execute",
            succeeded=result.succeeded,
        ),
    }


@router.get("/api/v1/pipeline/history")
def pipeline_history(limit: str = "50"):
    """Batch pipeline execution history."""
    try:
        read_limit = _coerce_workflow_read_limit(limit)
    except ValueError as error:
        _raise_workflow_validation_error(error)
    return {
        "pipelines": [
            {"id": p.pipeline_id, "succeeded": p.succeeded, "steps": len(p.steps), "cost": p.total_cost}
            for p in deps.batch_pipeline.history(limit=read_limit)
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
def execute_workflow_template(req: TemplateExecuteRequest, request: Request):
    """Instantiate and execute a workflow template."""
    enforce_tenant_scope(request, req.tenant_id)
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
