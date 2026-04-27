"""
/cognition/* — SCCCE cognitive cycle endpoints.

The cycle is run on a freshly-built SymbolField (the registry from
/constructs is the persistent store; the cycle gets a snapshot copy).
Domain-specific step callbacks are not exposed over HTTP — only the
default no-op cycle runs. To use custom steps, call SCCCECycle directly
from Python.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mcoi_runtime.app.routers.musia_auth import (
    require_read,
    require_write,
)
from mcoi_runtime.cognition import (
    ConvergenceDetector,
    SCCCECycle,
    SymbolField,
    TensionCalculator,
    TensionWeights,
)
from mcoi_runtime.substrate.registry_store import STORE


router = APIRouter(prefix="/cognition", tags=["cognition"])


class TensionWeightsPayload(BaseModel):
    foundational: float = 1.0
    structural: float = 1.0
    coordination: float = 1.0
    governance: float = 1.0
    cognitive: float = 1.0


class CycleConfig(BaseModel):
    weights: TensionWeightsPayload = Field(default_factory=TensionWeightsPayload)
    epsilon: float = Field(default=1e-6, ge=0)
    max_iterations: int = Field(default=50, ge=1, le=1000)
    stable_iterations: int = Field(default=3, ge=1, le=100)


class TensionSnapshotPayload(BaseModel):
    foundational: float
    structural: float
    coordination: float
    governance: float
    cognitive: float
    total: float


class StepRecordPayload(BaseModel):
    iteration: int
    step: str
    succeeded: bool
    field_size_after: int


class CycleResultPayload(BaseModel):
    converged: bool
    reason: str
    iterations: int
    final_tension: TensionSnapshotPayload
    proof_state: str
    aborted_at_step: str | None
    construct_graph_summary: dict[str, int]
    step_records: list[StepRecordPayload]


def _build_cycle(cfg: CycleConfig) -> SCCCECycle:
    return SCCCECycle(
        tension=TensionCalculator(
            weights=TensionWeights(
                foundational=cfg.weights.foundational,
                structural=cfg.weights.structural,
                coordination=cfg.weights.coordination,
                governance=cfg.weights.governance,
                cognitive=cfg.weights.cognitive,
            ),
        ),
        convergence=ConvergenceDetector(
            epsilon=cfg.epsilon,
            max_iterations=cfg.max_iterations,
            stable_iterations=cfg.stable_iterations,
        ),
    )


def _snapshot(s) -> TensionSnapshotPayload:
    return TensionSnapshotPayload(
        foundational=s.foundational,
        structural=s.structural,
        coordination=s.coordination,
        governance=s.governance,
        cognitive=s.cognitive,
        total=s.total,
    )


def _field_for_tenant(tenant_id: str) -> SymbolField:
    """Build a SymbolField containing the tenant's constructs."""
    state = STORE.get_or_create(tenant_id)
    field = SymbolField()
    for c in state.graph.constructs.values():
        try:
            field.register(c)
        except ValueError:
            continue
    return field


@router.post("/run", response_model=CycleResultPayload)
def run_cycle(
    cfg: CycleConfig | None = None,
    tenant_id: str = Depends(require_write),
) -> CycleResultPayload:
    """Run the SCCCE cycle over the tenant's construct registry snapshot."""
    cfg = cfg or CycleConfig()
    field = _field_for_tenant(tenant_id)
    cycle = _build_cycle(cfg)
    result = cycle.run(field)

    return CycleResultPayload(
        converged=result.converged,
        reason=result.reason.value,
        iterations=result.iterations,
        final_tension=_snapshot(result.final_tension),
        proof_state=result.to_universal_result_kwargs()["proof_state"],
        aborted_at_step=result.aborted_at_step.name if result.aborted_at_step else None,
        construct_graph_summary=dict(result.construct_graph_summary),
        step_records=[
            StepRecordPayload(
                iteration=r.iteration,
                step=r.step.name,
                succeeded=r.succeeded,
                field_size_after=r.field_size_after,
            )
            for r in result.step_records
        ],
    )


@router.get("/tension", response_model=TensionSnapshotPayload)
def get_tension(
    foundational: float = 1.0,
    structural: float = 1.0,
    coordination: float = 1.0,
    governance: float = 1.0,
    cognitive: float = 1.0,
    tenant_id: str = Depends(require_read),
) -> TensionSnapshotPayload:
    """Tension over the tenant's registry without running a cycle."""
    if any(v < 0 for v in (foundational, structural, coordination, governance, cognitive)):
        raise HTTPException(status_code=400, detail="weights must be non-negative")

    field = _field_for_tenant(tenant_id)
    calc = TensionCalculator(
        weights=TensionWeights(
            foundational=foundational,
            structural=structural,
            coordination=coordination,
            governance=governance,
            cognitive=cognitive,
        ),
    )
    return _snapshot(calc.compute(field))


@router.get("/symbol-field")
def get_symbol_field(
    tenant_id: str = Depends(require_read),
) -> dict[str, Any]:
    """Tenant's symbol field summary."""
    field = _field_for_tenant(tenant_id)
    return {
        "tenant_id": tenant_id,
        "size": field.size,
        "by_tier": {t.name: n for t, n in field.tier_sizes().items()},
        "by_type": field.type_counts(),
    }
