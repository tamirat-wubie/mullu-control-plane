"""
Hierarchical Tension Calculator.

Implements the MUSIA tension function:

    T_total = α₁·T_foundational + α₂·T_structural + α₃·T_coordination
              + α₄·T_governance + α₅·T_cognitive

Each tier-tension is a non-negative scalar measuring "how much work remains"
at that tier. Total tension going to zero indicates the symbol field has
reached coherence — the cycle has converged.

Default tier-level tension functions count under-specified or pending
constructs. Production callers can replace them via dependency injection.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from mcoi_runtime.cognition.symbol_field import SymbolField
from mcoi_runtime.substrate.constructs import (
    ConstructBase,
    ConstructType,
    Tier,
)


# A tier-tension function takes the symbol field and returns a non-negative
# scalar. Higher = more incoherence at that tier.
TierTensionFn = Callable[[SymbolField], float]


# ---- Default per-tier tension functions ----


def t_foundational(field: SymbolField) -> float:
    """Tier 1 incoherence: dangling references in Causation/Change.

    A Causation whose effect_id doesn't resolve in the field, or a Change
    whose state_before_id doesn't resolve, indicates an incomplete causal
    primitive.
    """
    cost = 0.0
    for c in field.of_type(ConstructType.CAUSATION):
        if getattr(c, "effect_id", None) and field.get(c.effect_id) is None:
            cost += 1.0
        if getattr(c, "cause_id", None) and field.get(c.cause_id) is None:
            cost += 1.0
    for c in field.of_type(ConstructType.CHANGE):
        if getattr(c, "state_before_id", None) and field.get(c.state_before_id) is None:
            cost += 1.0
        if getattr(c, "state_after_id", None) and field.get(c.state_after_id) is None:
            cost += 1.0
    return cost


def t_structural(field: SymbolField) -> float:
    """Tier 2 incoherence: Transformations missing Tier 1 references."""
    cost = 0.0
    for t in field.of_type(ConstructType.TRANSFORMATION):
        for attr in (
            "initial_state_id",
            "target_state_id",
            "change_id",
            "causation_id",
            "boundary_id",
        ):
            ref = getattr(t, attr, None)
            if ref is None or field.get(ref) is None:
                cost += 0.5  # transformations have 5 refs; weight each at 0.5
    return cost


def t_coordination(field: SymbolField) -> float:
    """Tier 3 incoherence: Couplings whose endpoints don't resolve."""
    cost = 0.0
    for c in field.of_type(ConstructType.COUPLING):
        if getattr(c, "source_id", None) and field.get(c.source_id) is None:
            cost += 1.0
        if getattr(c, "target_id", None) and field.get(c.target_id) is None:
            cost += 1.0
    return cost


def t_governance(field: SymbolField) -> float:
    """Tier 4 incoherence: Validations with decision='unknown'.

    Unknown decisions are pending governance work. Each pending validation
    contributes 1.0 to governance tension.
    """
    cost = 0.0
    for v in field.of_type(ConstructType.VALIDATION):
        decision = getattr(v, "decision", "")
        if decision in {"unknown", "budget_unknown"}:
            cost += 1.0
    return cost


def t_cognitive(field: SymbolField) -> float:
    """Tier 5 incoherence: Executions in non-terminal state.

    Pending or in-progress executions are unfinished cognitive work.
    """
    cost = 0.0
    for e in field.of_type(ConstructType.EXECUTION):
        state = getattr(e, "completion_state", "")
        if state in {"pending", "in_progress"}:
            cost += 1.0
    return cost


# ---- Tension calculator ----


@dataclass
class TensionWeights:
    """Mixing weights αᵢ for each tier. Default = uniform."""

    foundational: float = 1.0
    structural: float = 1.0
    coordination: float = 1.0
    governance: float = 1.0
    cognitive: float = 1.0

    def __post_init__(self) -> None:
        for name in (
            "foundational",
            "structural",
            "coordination",
            "governance",
            "cognitive",
        ):
            v = getattr(self, name)
            if v < 0:
                raise ValueError(f"weight {name} must be non-negative")


@dataclass
class TensionSnapshot:
    """Per-tier and total tension at one point in time."""

    foundational: float
    structural: float
    coordination: float
    governance: float
    cognitive: float
    total: float

    def to_dict(self) -> dict[str, float]:
        return {
            "foundational": self.foundational,
            "structural": self.structural,
            "coordination": self.coordination,
            "governance": self.governance,
            "cognitive": self.cognitive,
            "total": self.total,
        }


@dataclass
class TensionCalculator:
    """Composable hierarchical tension calculator."""

    weights: TensionWeights = field(default_factory=TensionWeights)
    foundational_fn: TierTensionFn = t_foundational
    structural_fn: TierTensionFn = t_structural
    coordination_fn: TierTensionFn = t_coordination
    governance_fn: TierTensionFn = t_governance
    cognitive_fn: TierTensionFn = t_cognitive

    def compute(self, field: SymbolField) -> TensionSnapshot:
        f = self.foundational_fn(field)
        s = self.structural_fn(field)
        c = self.coordination_fn(field)
        g = self.governance_fn(field)
        cog = self.cognitive_fn(field)
        for name, val in (
            ("foundational", f),
            ("structural", s),
            ("coordination", c),
            ("governance", g),
            ("cognitive", cog),
        ):
            if val < 0:
                raise ValueError(f"tier tension {name} returned negative: {val}")
        total = (
            self.weights.foundational * f
            + self.weights.structural * s
            + self.weights.coordination * c
            + self.weights.governance * g
            + self.weights.cognitive * cog
        )
        return TensionSnapshot(
            foundational=f,
            structural=s,
            coordination=c,
            governance=g,
            cognitive=cog,
            total=total,
        )
