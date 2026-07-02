"""Safe local action rehearsal capability.

Purpose: expose a proof-only rehearsal runner for local developer actions.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi.govern.safe_local_action_rehearsal.runner.
Invariants: rehearsals do not mutate files, create PRs, merge, rollback,
deploy, call connectors, or prove post-execution state.
"""

from .runner import (
    CAPABILITY_ID,
    DEFAULT_OUTPUT,
    build_safe_local_action_rehearsal_receipt,
    run_safe_local_action_rehearsal,
    validate_safe_local_action_rehearsal_receipt,
)

__all__ = [
    "CAPABILITY_ID",
    "DEFAULT_OUTPUT",
    "build_safe_local_action_rehearsal_receipt",
    "run_safe_local_action_rehearsal",
    "validate_safe_local_action_rehearsal_receipt",
]
