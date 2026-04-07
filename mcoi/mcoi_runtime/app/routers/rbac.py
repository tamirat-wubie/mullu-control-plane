"""RBAC endpoints — identity, roles, permissions, and access governance.

Exposes the access_runtime engine through HTTP for managing users,
roles, permissions, and role bindings.
"""
from __future__ import annotations

from hashlib import sha256

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


class CreateIdentityRequest(BaseModel):
    identity_id: str
    display_name: str
    identity_kind: str = "human"
    tenant_id: str = ""


class CreateRoleRequest(BaseModel):
    role_id: str
    name: str
    permissions: list[str] = Field(default_factory=list)
    description: str = ""


class BindRoleRequest(BaseModel):
    identity_id: str
    role_id: str
    scope_kind: str = "tenant"
    scope_ref_id: str = "*"


@router.post("/api/v1/rbac/identities")
def create_identity(req: CreateIdentityRequest):
    """Register a governed identity (user, service, or agent)."""
    from mcoi_runtime.contracts.access_runtime import IdentityKind
    deps.metrics.inc("requests_governed")
    try:
        kind = IdentityKind(req.identity_kind)
    except (ValueError, KeyError):
        kind = IdentityKind.HUMAN
    try:
        identity = deps.access_runtime.register_identity(
            req.identity_id,
            req.display_name,
            kind=kind,
            tenant_id=req.tenant_id,
        )
    except Exception:
        raise HTTPException(400, detail={
            "error": "failed to create identity",
            "error_code": "identity_creation_failed",
            "governed": True,
        })
    deps.audit_trail.record(
        action="rbac.identity.create",
        actor_id="api",
        tenant_id=req.tenant_id,
        target=req.identity_id,
        outcome="success",
        detail={"kind": req.identity_kind},
    )
    return {
        "identity_id": identity.identity_id,
        "display_name": identity.name,
        "kind": identity.kind.value,
        "enabled": identity.enabled,
        "governed": True,
    }


@router.get("/api/v1/rbac/identities")
def list_identities(tenant_id: str = ""):
    """List governed identities."""
    deps.metrics.inc("requests_governed")
    if tenant_id:
        identities = deps.access_runtime.identities_for_tenant(tenant_id)
    else:
        identities = deps.access_runtime.all_identities()
    return {
        "identities": [
            {
                "identity_id": i.identity_id,
                "display_name": i.name,
                "kind": i.kind.value,
                "enabled": i.enabled,
                "tenant_id": i.tenant_id,
            }
            for i in identities
        ],
        "count": len(identities),
        "governed": True,
    }


@router.post("/api/v1/rbac/roles")
def create_role(req: CreateRoleRequest):
    """Create a permission role."""
    deps.metrics.inc("requests_governed")
    try:
        role = deps.access_runtime.register_role(
            req.role_id,
            req.name,
            permissions=req.permissions,
            description=req.description,
        )
    except Exception:
        raise HTTPException(400, detail={
            "error": "failed to create role",
            "error_code": "role_creation_failed",
            "governed": True,
        })
    deps.audit_trail.record(
        action="rbac.role.create",
        actor_id="api",
        tenant_id="system",
        target=req.role_id,
        outcome="success",
        detail={"permissions": req.permissions},
    )
    return {
        "role_id": role.role_id,
        "name": role.name,
        "permissions": list(role.permissions),
        "governed": True,
    }


@router.get("/api/v1/rbac/roles")
def list_roles():
    """List all permission roles."""
    deps.metrics.inc("requests_governed")
    roles = deps.access_runtime.all_roles()
    return {
        "roles": [
            {
                "role_id": r.role_id,
                "name": r.name,
                "permissions": list(r.permissions),
            }
            for r in roles
        ],
        "count": len(roles),
        "governed": True,
    }


@router.post("/api/v1/rbac/bindings")
def bind_role(req: BindRoleRequest):
    """Bind a role to an identity within a scope."""
    from mcoi_runtime.contracts.access_runtime import AuthContextKind
    deps.metrics.inc("requests_governed")
    binding_id = f"bind-{sha256(f'{req.identity_id}:{req.role_id}'.encode()).hexdigest()[:12]}"
    try:
        scope = AuthContextKind(req.scope_kind)
    except (ValueError, KeyError):
        scope = AuthContextKind.TENANT
    try:
        deps.access_runtime.bind_role(
            binding_id,
            req.identity_id,
            req.role_id,
            scope_kind=scope,
            scope_ref_id=req.scope_ref_id,
        )
    except Exception:
        raise HTTPException(400, detail={
            "error": "failed to bind role",
            "error_code": "binding_failed",
            "governed": True,
        })
    deps.audit_trail.record(
        action="rbac.binding.create",
        actor_id="api",
        tenant_id="system",
        target=f"{req.identity_id}:{req.role_id}",
        outcome="success",
    )
    return {
        "binding_id": binding_id,
        "identity_id": req.identity_id,
        "role_id": req.role_id,
        "governed": True,
    }


@router.get("/api/v1/rbac/summary")
def rbac_summary():
    """RBAC system summary."""
    deps.metrics.inc("requests_governed")
    return {
        "identity_count": deps.access_runtime.identity_count,
        "role_count": deps.access_runtime.role_count,
        "binding_count": deps.access_runtime.binding_count,
        "governed": True,
    }
