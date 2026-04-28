"""v4.38.0 (audit F7 Phase 1) - re-export shim.

Real implementation lives at :mod:`mcoi_runtime.core.policy_simulation`. This module
provides the canonical post-reorg import path; callers may use either the
old ``core.policy_simulation`` path or the new ``governance.policy.simulation`` path.
The shim layer is non-breaking by design.

Phase 4 of the F7 reorg will move the implementation here and remove the
shim. See ``docs/GOVERNANCE_PACKAGE_REORG_PLAN.md``.
"""
from mcoi_runtime.core.policy_simulation import (  # noqa: F401
    AdoptionReadiness,
    AdoptionRecommendation,
    DiffDisposition,
    PolicyDiffRecord,
    PolicyImpactLevel,
    PolicySimulationEngine,
    PolicySimulationRequest,
    PolicySimulationResult,
    PolicySimulationScenario,
    RuntimeImpactRecord,
    SandboxAssessment,
    SandboxClosureReport,
    SandboxScope,
    SandboxSnapshot,
    SandboxViolation,
    SimulationMode,
    SimulationStatus,
)

__all__ = (
    "AdoptionReadiness",
    "AdoptionRecommendation",
    "DiffDisposition",
    "PolicyDiffRecord",
    "PolicyImpactLevel",
    "PolicySimulationEngine",
    "PolicySimulationRequest",
    "PolicySimulationResult",
    "PolicySimulationScenario",
    "RuntimeImpactRecord",
    "SandboxAssessment",
    "SandboxClosureReport",
    "SandboxScope",
    "SandboxSnapshot",
    "SandboxViolation",
    "SimulationMode",
    "SimulationStatus",
)
