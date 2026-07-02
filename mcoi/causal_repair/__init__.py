"""Reusable causal repair service.

Purpose: expose proof-only failure classification and repair proposal helpers
for governed local workflow failures.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi_runtime.core.causal_repair and JSON schema validators.
Invariants: repair classification never executes rollback, compensation,
connector effects, repository mutation, deployment, or external writes.
"""

from .service import (
    CAPABILITY_ID,
    DEFAULT_FAILURE_IDS,
    FORBIDDEN_EFFECTS,
    build_causal_repair_service_receipt,
    classify_failure,
    run_causal_repair_service,
    validate_causal_repair_service_receipt,
)

__all__ = [
    "CAPABILITY_ID",
    "DEFAULT_FAILURE_IDS",
    "FORBIDDEN_EFFECTS",
    "build_causal_repair_service_receipt",
    "classify_failure",
    "run_causal_repair_service",
    "validate_causal_repair_service_receipt",
]
