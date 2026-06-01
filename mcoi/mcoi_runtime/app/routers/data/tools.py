"""Tool registry endpoints: list, invoke, history, LLM-format export."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope
from mcoi_runtime.app.routers.data._common import _certify_action_proof, deps
from mcoi_runtime.core.tool_use import certify_tool_capability_policy_receipt

router = APIRouter()


class ToolInvokeRequest(BaseModel):
    tool_id: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    tenant_id: str = ""


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
def invoke_tool(req: ToolInvokeRequest, request: Request):
    """Invoke a registered tool."""
    enforce_tenant_scope(request, req.tenant_id)
    deps.metrics.inc("requests_governed")
    tool = deps.tool_registry.get(req.tool_id)
    result = deps.tool_registry.invoke(req.tool_id, req.arguments, tenant_id=req.tenant_id)
    policy_receipt = certify_tool_capability_policy_receipt(
        tool=tool,
        tool_id=req.tool_id,
        arguments=req.arguments,
        tenant_id=req.tenant_id,
        invocation_id=result.invocation_id,
        execution_succeeded=result.succeeded,
    )
    deps.audit_trail.record(
        action="tool.invoke", actor_id="api", tenant_id=req.tenant_id,
        target=req.tool_id, outcome="success" if result.succeeded else "error",
        detail={
            "capability_policy_receipt_id": policy_receipt["receipt_id"],
            "argument_hash": policy_receipt["argument_hash"],
            "policy_allowed": policy_receipt["policy_allowed"],
        },
    )
    return {
        "invocation_id": result.invocation_id, "tool_id": result.tool_id,
        "output": result.output, "succeeded": result.succeeded, "error": result.error,
        "capability_policy_receipt": policy_receipt,
        "action_proof": _certify_action_proof(
            endpoint="/api/v1/tools/invoke",
            tenant_id=req.tenant_id,
            actor_id="api",
            target=req.tool_id,
            action="tool.invoke",
            succeeded=result.succeeded,
        ),
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
