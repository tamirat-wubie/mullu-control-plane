"""Hosted demo sandbox endpoints.

Purpose: expose read-only demo traces, lineage projections, and policy
evaluations for evaluator-facing sandbox use.
Governance scope: public read-model endpoints only.
Dependencies: hosted demo sandbox read model.
Invariants: endpoints are read-only, deterministic, and never invoke providers.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from mcoi_runtime.core.hosted_demo_sandbox import HostedDemoSandbox


router = APIRouter(tags=["sandbox"])
_sandbox = HostedDemoSandbox()


@router.get("/api/v1/sandbox/summary")
def sandbox_summary() -> dict[str, Any]:
    """Return hosted sandbox summary and query examples."""
    return _sandbox.summary()


@router.get("/api/v1/sandbox/traces")
def sandbox_traces() -> dict[str, Any]:
    """Return read-only sandbox traces."""
    traces = _sandbox.traces()
    return {"traces": traces, "count": len(traces), "read_only": True, "governed": True}


@router.get("/api/v1/sandbox/lineage/{trace_id}")
def sandbox_lineage(trace_id: str) -> dict[str, Any]:
    """Return read-only lineage projection for a sandbox trace."""
    document = _sandbox.lineage(trace_id)
    if document is None:
        raise HTTPException(
            404,
            detail={
                "error": "sandbox trace not found",
                "error_code": "sandbox_trace_not_found",
                "governed": True,
            },
        )
    return document


@router.get("/api/v1/sandbox/policy-evaluations")
def sandbox_policy_evaluations() -> dict[str, Any]:
    """Return read-only sandbox policy evaluations."""
    evaluations = _sandbox.policy_evaluations()
    return {
        "policy_evaluations": evaluations,
        "count": len(evaluations),
        "read_only": True,
        "governed": True,
    }
