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

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.deps import deps
from mcoi_runtime.core.lineage_query import resolve_lineage_uri

router = APIRouter()


class LineageResolveRequest(BaseModel):
    uri: str = Field(..., min_length=1)


def _resolve(uri: str) -> dict[str, Any]:
    try:
        deps.metrics.inc("requests_governed")
        return resolve_lineage_uri(
            uri,
            replay_source=deps.replay_recorder,
            clock=deps._clock,
            command_source=_optional_dependency("command_ledger"),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid lineage uri",
                "error_code": "invalid_lineage_uri",
                "reason": str(exc),
                "governed": True,
            },
        ) from exc


def _optional_dependency(name: str) -> Any | None:
    try:
        return deps.get(name)
    except RuntimeError:
        return None


@router.post("/api/v1/lineage/resolve")
def resolve_lineage(req: LineageResolveRequest) -> dict[str, Any]:
    """Resolve a lineage URI into a bounded causal graph."""
    return _resolve(req.uri)


@router.get("/api/v1/lineage/{trace_id}")
def get_trace_lineage(trace_id: str, depth: int = 25, verify: bool = True) -> dict[str, Any]:
    """Resolve lineage by trace id."""
    return _resolve(f"lineage://trace/{trace_id}?depth={depth}&verify={str(verify).lower()}")


@router.get("/api/v1/lineage/output/{output_id}")
def get_output_lineage(output_id: str, depth: int = 25, verify: bool = True) -> dict[str, Any]:
    """Resolve lineage by output id."""
    return _resolve(f"lineage://output/{output_id}?depth={depth}&verify={str(verify).lower()}")


@router.get("/api/v1/lineage/command/{command_id}")
def get_command_lineage(command_id: str, depth: int = 25, verify: bool = True) -> dict[str, Any]:
    """Resolve lineage by command id."""
    return _resolve(f"lineage://command/{command_id}?depth={depth}&verify={str(verify).lower()}")
