"""
Tier 1 — Foundational Causal Primitives.

The 5 irreducible constructs that ground all higher-tier reasoning.
Every domain (physics, biology, work, math, AI) reduces to these.

NOT anthropocentric. NOT job-shaped. Pure causal primitives.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4


class Tier(Enum):
    FOUNDATIONAL = 1
    STRUCTURAL = 2
    COORDINATION = 3
    GOVERNANCE = 4
    COGNITIVE = 5


class ConstructType(Enum):
    # Tier 1 — Foundational
    STATE = "state"
    CHANGE = "change"
    CAUSATION = "causation"
    CONSTRAINT = "constraint"
    BOUNDARY = "boundary"
    # Tier 2 — Structural (Phase 2)
    PATTERN = "pattern"
    TRANSFORMATION = "transformation"
    COMPOSITION = "composition"
    INTERACTION = "interaction"
    CONSERVATION = "conservation"
    # Tier 3 — Coordination (Phase 2)
    COUPLING = "coupling"
    SYNCHRONIZATION = "synchronization"
    RESONANCE = "resonance"
    EQUILIBRIUM = "equilibrium"
    EMERGENCE = "emergence"
    # Tier 4 — Governance (Phase 2)
    SOURCE = "source"
    BINDING = "binding"
    VALIDATION = "validation"
    EVOLUTION = "evolution"
    INTEGRITY = "integrity"
    # Tier 5 — Cognitive (Phase 2)
    OBSERVATION = "observation"
    INFERENCE = "inference"
    DECISION = "decision"
    EXECUTION = "execution"
    LEARNING = "learning"


@dataclass(frozen=True)
class MfidelSignature:
    """Reference to atomic fidels that encode this construct's causal pattern."""

    coords: tuple[tuple[int, int], ...]  # (row, col) pairs

    def __post_init__(self) -> None:
        if not self.coords:
            raise ValueError("MfidelSignature requires at least one coord")
        for r, c in self.coords:
            if not (1 <= r <= 34 and 1 <= c <= 8):
                raise ValueError(f"coord ({r},{c}) out of grid bounds")


@dataclass
class ConstructBase:
    """
    Every construct shares this structural envelope.
    Disambiguation enforced: each construct has ONE irreducible function.
    """

    id: UUID = field(default_factory=uuid4)
    tier: Tier = Tier.FOUNDATIONAL
    type: ConstructType = ConstructType.STATE
    mfidel_signature: Optional[MfidelSignature] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    invariants: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.invariants:
            raise ValueError(
                f"{self.type.value}: at least one invariant required"
            )


# ---- TIER 1 CONSTRUCTS ----
# Each has exactly ONE responsibility. No semantic overlap.


@dataclass
class State(ConstructBase):
    """
    WHAT: configuration_at_time_t.

    The atomic descriptor of "what exists right now". Pure observable.
    Does NOT include change, cause, limit, or boundary — those are
    separate constructs.
    """

    type: ConstructType = ConstructType.STATE
    tier: Tier = Tier.FOUNDATIONAL
    configuration: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.invariants:
            self.invariants = (
                "observable",
                "definable",
                "bounded_in_scope",
            )
        super().__post_init__()


@dataclass
class Change(ConstructBase):
    """
    WHAT: state_difference (S_before -> S_after).

    Pure delta. Does NOT include the producer of the change (that's CAUSATION)
    or the limits on the change (that's CONSTRAINT).
    """

    type: ConstructType = ConstructType.CHANGE
    tier: Tier = Tier.FOUNDATIONAL
    state_before_id: Optional[UUID] = None
    state_after_id: Optional[UUID] = None
    delta_vector: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.invariants:
            self.invariants = (
                "measurable",
                "directional",
                "finite",
            )
        super().__post_init__()


@dataclass
class Causation(ConstructBase):
    """
    WHAT: change_production_relationship (cause -> effect).

    The mechanism that produces a Change. Does NOT include the change itself
    (that's CHANGE) or what limits it (that's CONSTRAINT).
    """

    type: ConstructType = ConstructType.CAUSATION
    tier: Tier = Tier.FOUNDATIONAL
    cause_id: Optional[UUID] = None
    effect_id: Optional[UUID] = None  # references a Change
    mechanism: str = ""
    strength: float = 1.0  # [0, 1]

    def __post_init__(self) -> None:
        if not (0.0 <= self.strength <= 1.0):
            raise ValueError(f"strength {self.strength} not in [0,1]")
        if not self.mechanism:
            raise ValueError("Causation requires mechanism description")
        if not self.invariants:
            self.invariants = (
                "necessity_or_sufficiency",
                "temporal_ordering",
                "non_circular",
            )
        super().__post_init__()


@dataclass
class Constraint(ConstructBase):
    """
    WHAT: change_limitation_relationship.

    What prevents change or restricts its form. Distinct from BOUNDARY which
    defines system perimeter — Constraint operates within a boundary.
    """

    type: ConstructType = ConstructType.CONSTRAINT
    tier: Tier = Tier.FOUNDATIONAL
    domain: str = ""  # what scope does this restrict?
    restriction: str = ""  # the rule
    violation_response: str = "block"  # block | warn | escalate

    def __post_init__(self) -> None:
        if not self.domain or not self.restriction:
            raise ValueError("Constraint requires domain and restriction")
        if self.violation_response not in {"block", "warn", "escalate"}:
            raise ValueError(
                f"invalid violation_response: {self.violation_response}"
            )
        if not self.invariants:
            self.invariants = (
                "enforceable",
                "decidable",
                "scoped",
            )
        super().__post_init__()


@dataclass
class Boundary(ConstructBase):
    """
    WHAT: system_perimeter_definition.

    What is inside vs. outside the system. Distinct from CONSTRAINT which
    operates within a boundary — Boundary defines what the system IS.
    """

    type: ConstructType = ConstructType.BOUNDARY
    tier: Tier = Tier.FOUNDATIONAL
    inside_predicate: str = ""  # logical description of "inside"
    interface_points: tuple[str, ...] = ()
    permeability: str = "selective"  # closed | selective | open

    def __post_init__(self) -> None:
        if not self.inside_predicate:
            raise ValueError("Boundary requires inside_predicate")
        if self.permeability not in {"closed", "selective", "open"}:
            raise ValueError(f"invalid permeability: {self.permeability}")
        if not self.invariants:
            self.invariants = (
                "closed_definition",
                "interface_specified",
                "defendable",
            )
        super().__post_init__()


# ---- DISAMBIGUATION VERIFIER ----
# Hard rule: no two Tier 1 constructs may share the same irreducible function.


TIER1_RESPONSIBILITIES: dict[ConstructType, str] = {
    ConstructType.STATE:      "WHAT_EXISTS",
    ConstructType.CHANGE:     "WHAT_DIFFERS",
    ConstructType.CAUSATION:  "WHAT_PRODUCES_DIFFERENCE",
    ConstructType.CONSTRAINT: "WHAT_PREVENTS_DIFFERENCE",
    ConstructType.BOUNDARY:   "WHAT_DELIMITS_SYSTEM",
}


def verify_tier1_disambiguation() -> None:
    """No two Tier 1 constructs may have overlapping responsibility."""
    seen: set[str] = set()
    for ct, resp in TIER1_RESPONSIBILITIES.items():
        if resp in seen:
            raise ValueError(f"responsibility overlap detected: {resp}")
        seen.add(resp)


verify_tier1_disambiguation()
