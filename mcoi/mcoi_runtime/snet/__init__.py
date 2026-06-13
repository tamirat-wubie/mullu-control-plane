"""Purpose: expose the bounded SNet recursive inquiry prototype.
Governance scope: local Foundation Mode symbolic mesh proof only.
Dependencies: mcoi_runtime.snet.engine and mcoi_runtime.contracts.snet.
Invariants: no connector calls, no route mutation, no execution authority.
"""

from .engine import SNetRecursiveMesh
from .read_model import build_snet_operator_read_model, create_snet_mesh_receipt

__all__ = [
    "SNetRecursiveMesh",
    "build_snet_operator_read_model",
    "create_snet_mesh_receipt",
]
