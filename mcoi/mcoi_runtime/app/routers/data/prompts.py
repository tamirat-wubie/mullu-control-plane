"""Prompt template render and execution endpoints."""
from __future__ import annotations

from typing import Any, NoReturn

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope
from mcoi_runtime.app.routers.data._common import deps

router = APIRouter()


class PromptRenderRequest(BaseModel):
    template_id: str
    variables: dict[str, str]
    tenant_id: str = "system"
    budget_id: str = "default"
    execute: bool = False


def _raise_prompt_execution_unavailable(
    *,
    template_id: str,
    tenant_id: str,
    exc: Exception,
) -> NoReturn:
    """Raise a sanitized prompt-execution failure."""
    deps.llm_circuit.record_failure()
    deps.metrics.inc("errors_total")
    deps.audit_trail.record(
        action="prompt.render",
        actor_id="api",
        tenant_id=tenant_id,
        target=template_id,
        outcome="error",
        detail={
            "error_type": type(exc).__name__,
            "reason": "llm_service_unavailable",
        },
    )
    raise HTTPException(
        503,
        detail={
            "error": "LLM service unavailable",
            "error_code": "llm_service_unavailable",
            "governed": True,
        },
    )


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
def render_prompt(req: PromptRenderRequest, request: Request):
    """Render a prompt template with variables, optionally execute via LLM."""
    enforce_tenant_scope(request, req.tenant_id)
    deps.metrics.inc("requests_governed")
    try:
        rendered = deps.prompt_engine.render(req.template_id, req.variables)
    except ValueError:
        raise HTTPException(400, detail={"error": "invalid request", "error_code": "validation_error", "governed": True})

    response: dict[str, Any] = {
        "template_id": rendered.template_id,
        "prompt": rendered.prompt,
        "system_prompt": rendered.system_prompt,
        "version": rendered.version,
    }

    if req.execute:
        deps.metrics.inc("llm_calls_total")
        try:
            result = deps.llm_bridge.complete(
                rendered.prompt, system=rendered.system_prompt,
                budget_id=req.budget_id, tenant_id=req.tenant_id,
            )
        except Exception as exc:
            _raise_prompt_execution_unavailable(
                template_id=rendered.template_id,
                tenant_id=req.tenant_id,
                exc=exc,
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
