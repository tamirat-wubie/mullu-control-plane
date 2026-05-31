"""Purpose: canonical Solver Outcome Taxonomy for terminal solver/loop closures.
Governance scope: shared terminal-outcome typing only. This is a naming-stable
    contract surface; subsystem-local copies (OperationalMathOutcome,
    CoordinationOutcome, PuzzleSolverOutcome) carry the identical member set.
Dependencies: Python standard library (enum) only.
Invariants:
  - The eight terminal values are exactly the Solver Outcome Taxonomy:
    SolvedVerified, SolvedUnverified, AwaitingEvidence, SafeHalt,
    GovernanceBlocked, BudgetExhausted, ImpossibleProved, ModelInvalidated.
  - String values are CamelCase and byte-identical to the subsystem-local copies
    (engineering_puzzle.EngineeringVerdict, intelligence_coordination
    .SolverTerminalOutcome) so cross-subsystem comparison by value is exact and a
    receipt asserting ``solver_outcome == "SolvedVerified"`` matches this enum.
  - No behavior, no IO; this module declares typing only.
"""

from __future__ import annotations

from enum import StrEnum


class SolverOutcome(StrEnum):
    """Terminal taxonomy for solver / cognitive-loop closures.

    Member values are byte-identical to the subsystem-local taxonomy copies in
    contracts.engineering_puzzle.EngineeringVerdict and
    contracts.intelligence_coordination.SolverTerminalOutcome.
    """

    SOLVED_VERIFIED = "SolvedVerified"
    SOLVED_UNVERIFIED = "SolvedUnverified"
    AWAITING_EVIDENCE = "AwaitingEvidence"
    SAFE_HALT = "SafeHalt"
    GOVERNANCE_BLOCKED = "GovernanceBlocked"
    BUDGET_EXHAUSTED = "BudgetExhausted"
    IMPOSSIBLE_PROVED = "ImpossibleProved"
    MODEL_INVALIDATED = "ModelInvalidated"


__all__ = ["SolverOutcome"]
