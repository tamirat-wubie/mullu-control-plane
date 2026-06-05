"""Lineage query endpoints.

Purpose: expose read-only `lineage://` resolution for governed trace and output
permalinks.
Governance scope: query parsing, bounded depth, explicit unresolved nodes, and
tenant-retaining lineage projection.
Dependencies: FastAPI, shared router dependency container, lineage resolver.
Invariants: endpoints do not mutate trace, replay, tenant, budget, or policy
state.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.app.routers._tenant_scope import enforce_tenant_scope
from mcoi_runtime.core.lineage_query import resolve_lineage_uri

router = APIRouter()


class LineageResolveRequest(BaseModel):
    uri: str = Field(..., min_length=1)


def _enforce_lineage_tenant(request: Request, document: dict[str, Any]) -> None:
    """Reject a non-operator reading lineage nodes owned by another tenant.

    Lineage resolves by trace/output/command/artifact id with no tenant input, so
    a caller could resolve another tenant's graph by naming its id. Each resolved
    node carries its tenant; the "unknown" sentinel (unresolved nodes) is skipped.
    Operators (wildcard scope) and unauthenticated dev requests are unaffected --
    enforce_tenant_scope is a no-op for them.
    """
    for node in document.get("nodes", ()):
        tenant_id = node.get("tenant_id") if isinstance(node, dict) else None
        if tenant_id and tenant_id != "unknown":
            enforce_tenant_scope(request, tenant_id)


def _resolve(request: Request, uri: str) -> dict[str, Any]:
    try:
        deps.metrics.inc("requests_governed")
        document = resolve_lineage_uri(
            uri,
            replay_source=deps.replay_recorder,
            clock=deps._clock,
            command_source=_optional_dependency("command_ledger"),
            artifact_source=_optional_dependency("artifact_lineage"),
            policy_registry=_optional_dependency("policy_version_registry"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid lineage uri",
                "error_code": "invalid_lineage_uri",
                "governed": True,
            },
        ) from exc
    _enforce_lineage_tenant(request, document)
    return document


def _optional_dependency(name: str) -> Any | None:
    try:
        return deps.get(name)
    except RuntimeError:
        return None


@router.post("/api/v1/lineage/resolve")
def resolve_lineage(req: LineageResolveRequest, request: Request) -> dict[str, Any]:
    """Resolve a lineage URI into a bounded causal graph."""
    return _resolve(request, req.uri)


@router.get("/api/v1/lineage/{trace_id}")
def get_trace_lineage(trace_id: str, request: Request, depth: int = 25, verify: bool = True) -> dict[str, Any]:
    """Resolve lineage by trace id."""
    return _resolve(request, f"lineage://trace/{trace_id}?depth={depth}&verify={str(verify).lower()}")


@router.get("/api/v1/lineage/output/{output_id}")
def get_output_lineage(output_id: str, request: Request, depth: int = 25, verify: bool = True) -> dict[str, Any]:
    """Resolve lineage by output id."""
    return _resolve(request, f"lineage://output/{output_id}?depth={depth}&verify={str(verify).lower()}")


@router.get("/api/v1/lineage/command/{command_id}")
def get_command_lineage(command_id: str, request: Request, depth: int = 25, verify: bool = True) -> dict[str, Any]:
    """Resolve lineage by command id."""
    return _resolve(request, f"lineage://command/{command_id}?depth={depth}&verify={str(verify).lower()}")


@router.get("/api/v1/lineage/artifact/{artifact_id}")
def get_artifact_lineage(artifact_id: str, request: Request, depth: int = 25, verify: bool = True) -> dict[str, Any]:
    """Resolve lineage by artifact id."""
    return _resolve(request, f"lineage://artifact/{artifact_id}?depth={depth}&verify={str(verify).lower()}")
