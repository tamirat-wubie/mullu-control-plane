"""Subsystem dependency graph endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from mcoi_runtime.app.routers.deps import deps

router = APIRouter()


@router.get("/api/v1/dependencies")
def dependency_graph_endpoint():
    """Subsystem dependency graph."""
    return {
        "startup_order": deps.dep_graph.topological_sort(),
        "summary": deps.dep_graph.summary(),
    }


@router.get("/api/v1/dependencies/{name}/impact")
def dependency_impact(name: str):
    """Impact analysis if a subsystem fails."""
    impacted = deps.dep_graph.impact_of_failure(name)
    return {"subsystem": name, "impacted": impacted, "count": len(impacted)}
