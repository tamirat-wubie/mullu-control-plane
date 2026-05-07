"""SCCCE Cognitive Engine — 15-step constraint propagation cycle."""
from mcoi_runtime.cognition.convergence import (
    ConvergenceDetector,
    ConvergenceReason,
    ConvergenceState,
)
from mcoi_runtime.cognition.cycle import (
    CycleResult,
    CycleStep,
    CycleStepRecord,
    META_RECURSION_DEPTH_LIMIT,
    SCCCECycle,
    StepFn,
)
from mcoi_runtime.cognition.symbol_field import SymbolField
from mcoi_runtime.cognition.tension import (
    TensionCalculator,
    TensionSnapshot,
    TensionWeights,
    TierTensionFn,
)

__all__ = [
    # Cycle
    "CycleResult",
    "CycleStep",
    "CycleStepRecord",
    "META_RECURSION_DEPTH_LIMIT",
    "SCCCECycle",
    "StepFn",
    # Symbol field
    "SymbolField",
    # Tension
    "TensionCalculator",
    "TensionSnapshot",
    "TensionWeights",
    "TierTensionFn",
    # Convergence
    "ConvergenceDetector",
    "ConvergenceReason",
    "ConvergenceState",
]
