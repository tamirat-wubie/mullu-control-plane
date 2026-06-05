"""Tool permission primitive operator routes.

Purpose: expose tenant-scoped tool-call permission primitives as bounded
operator API read and mutation surfaces.
Governance scope: permission registration, permission listing, and dry-run
permission evaluation without tool execution.
Dependencies: FastAPI, shared dependency registry, and tool permission
primitive contracts.
Invariants: permission absence fails closed; registration requires admin
authority; evaluation never invokes a tool; responses expose bounded decision
codes and deterministic hashes.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope, scoped_listing_tenant
from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers.musia_auth import require_admin
from mcoi_runtime.core.tool_permission_primitives import (
    ToolCallPermission,
    ToolPermissionDecision,
    ToolPermissionRequest,
)

router = APIRouter()


class RegisterToolPermissionRequest(BaseModel):
    tenant_id: str
    tool_name: str
    argument_schema: dict[str, Any] = Field(default_factory=dict)
    budget_ref: str
    audit_required: bool = True
    permission_id: str = ""
    description: str = ""


class EvaluateToolPermissionRequest(BaseModel):
    tenant_id: str
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    budget_ref: str
    audit_present: bool = False


def _registry() -> Any:
    return deps.tool_permission_registry


def _permission_to_dict(permission: ToolCallPermission) -> dict[str, Any]:
    return {
        "permission_id": permission.permission_id,
        "tenant_id": permission.tenant_id,
        "tool_name": permission.tool_name,
        "budget_ref": permission.budget_ref,
        "audit_required": permission.audit_required,
        "schema_hash": permission.schema_hash(),
        "grammar": permission.grammar(),
        "description": permission.description,
        "argument_schema": permission.argument_schema,
    }


def _decision_to_dict(decision: ToolPermissionDecision) -> dict[str, Any]:
    return {
        "allowed": decision.allowed,
        "reason_codes": list(decision.reason_codes),
        "permission_id": decision.permission_id,
        "tenant_id": decision.tenant_id,
        "tool_name": decision.tool_name,
        "budget_ref": decision.budget_ref,
        "argument_hash": decision.argument_hash,
        "schema_hash": decision.schema_hash,
        "grammar": decision.grammar,
        "metadata": decision.metadata,
    }


@router.post("/api/v1/tool-permissions")
def register_tool_permission(
    req: RegisterToolPermissionRequest,
    request: Request,
    _: str = Depends(require_admin),
) -> dict[str, Any]:
    """Register one immutable tool permission primitive."""

    enforce_tenant_scope(request, req.tenant_id)
    deps.metrics.inc("requests_governed")
    try:
        permission = ToolCallPermission(
            tenant_id=req.tenant_id,
            tool_name=req.tool_name,
            argument_schema=req.argument_schema,
            budget_ref=req.budget_ref,
            audit_required=req.audit_required,
            permission_id=req.permission_id,
            description=req.description,
        )
        stored = _registry().register(permission)
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "tool permission registration failed",
            "error_code": "tool_permission_registration_failed",
            "governed": True,
        }) from exc

    deps.audit_trail.record(
        action="tool_permission.register",
        actor_id="api",
        tenant_id=stored.tenant_id,
        target=stored.permission_id,
        outcome="success",
        detail={
            "tool_name": stored.tool_name,
            "schema_hash": stored.schema_hash(),
            "budget_ref": stored.budget_ref,
        },
    )
    return {"permission": _permission_to_dict(stored), "governed": True}


@router.get("/api/v1/tool-permissions")
def list_tool_permissions(request: Request, tenant_id: str = "") -> dict[str, Any]:
    """List registered tool permission primitives."""

    normalized_tenant = scoped_listing_tenant(request, tenant_id.strip() or None)
    deps.metrics.inc("requests_governed")
    permissions = _registry().list_permissions(tenant_id=normalized_tenant)
    return {
        "permissions": [_permission_to_dict(permission) for permission in permissions],
        "count": len(permissions),
        "tenant_id": normalized_tenant or "",
        "governed": True,
    }


@router.post("/api/v1/tool-permissions/evaluate")
def evaluate_tool_permission(req: EvaluateToolPermissionRequest, request: Request) -> dict[str, Any]:
    """Evaluate a proposed tool call against registered permissions without execution."""

    enforce_tenant_scope(request, req.tenant_id)
    deps.metrics.inc("requests_governed")
    try:
        decision = _registry().evaluate(
            ToolPermissionRequest(
                tenant_id=req.tenant_id,
                tool_name=req.tool_name,
                arguments=req.arguments,
                budget_ref=req.budget_ref,
                audit_present=req.audit_present,
            )
        )
    except ValueError as exc:
        raise HTTPException(400, detail={
            "error": "tool permission evaluation failed",
            "error_code": "tool_permission_evaluation_failed",
            "governed": True,
        }) from exc
    return {"decision": _decision_to_dict(decision), "governed": True}
