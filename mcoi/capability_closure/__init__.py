"""Capability debt closure runner package.

Purpose: expose deterministic read-only closure planning over capability debt.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: mcoi_runtime.app.capability_debt_report.
Invariants: closure artifacts do not grant live execution, connector writes,
repository mutation authority, PR creation, or terminal closure.
"""

from .runner import (
    ARTIFACT_FILENAMES,
    DEFAULT_PREFERRED_CAPABILITY_IDS,
    CapabilityClosureRunnerError,
    build_capability_closure_artifacts,
    write_capability_closure_artifacts,
)

__all__ = [
    "ARTIFACT_FILENAMES",
    "DEFAULT_PREFERRED_CAPABILITY_IDS",
    "CapabilityClosureRunnerError",
    "build_capability_closure_artifacts",
    "write_capability_closure_artifacts",
]
