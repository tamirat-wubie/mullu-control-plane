"""Purpose: expose the SNet operator read model through a read-only HTTP route.
Governance scope: SNet runtime integration gate, bounded read-model projection,
    raw-answer suppression, and no-authority route exposure.
Dependencies: FastAPI, SNet recursive mesh runtime, and SNet read-model builder.
Invariants:
  - The route does not accept raw answers or execute external effects.
  - The route returns a bounded operator projection only.
  - The response grants no execution, connector, route, or filesystem authority.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from mcoi_runtime.contracts.snet import SNetWHType
from mcoi_runtime.snet.engine import SNetRecursiveMesh
from mcoi_runtime.snet.read_model import build_snet_operator_read_model


router = APIRouter(prefix="/api/v1/snet", tags=["snet"])


@router.get("/operator/read-model")
def snet_operator_read_model(
    max_symbol_count: int = Query(default=20, ge=0, le=100),
) -> dict[str, Any]:
    """Return the bounded SNet operator read model without changing state."""

    mesh = _build_seed_dependency_mesh()
    return build_snet_operator_read_model(mesh, max_symbol_count=max_symbol_count)


def _build_seed_dependency_mesh() -> SNetRecursiveMesh:
    """Build the deterministic local SNet seed-dependency witness mesh."""

    mesh = SNetRecursiveMesh()
    seed = mesh.add_symbol("Seed", symbol_type="physical_biological_object")
    mesh.run_tick_with_answers(
        seed.symbol_id,
        {
            SNetWHType.DEPENDS_ON: "Water",
            SNetWHType.DEPENDS_ON_ME: "Future plant",
        },
    )
    return mesh
