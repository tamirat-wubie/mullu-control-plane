"""
Tier 3 — Coordination Constructs (System Dynamics).

Where Tier 1 names primitives and Tier 2 names compositions, Tier 3 names how
multiple compositions coordinate over time and across boundaries. These are
the constructs that turn structure into dynamics.

All references across tiers are by UUID, never by Mfidel coordinate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from mcoi_runtime.substrate.constructs.tier1_foundational import (
    ConstructBase,
    ConstructType,
    Tier,
)


@dataclass
class Coupling(ConstructBase):
    """
    WHAT: dependency_relationship between constructs.

    Source produces effect on target with a given strength and type. Distinct
    from Causation (which is about change-production) in that Coupling names
    the *standing* dependency, not the per-event mechanism.
    """

    type: ConstructType = ConstructType.COUPLING
    tier: Tier = Tier.COORDINATION

    source_id: Optional[UUID] = None
    target_id: Optional[UUID] = None
    strength: float = 1.0  # [0, 1]
    coupling_type: str = "directional"  # directional | bidirectional | broadcast

    def __post_init__(self) -> None:
        if not self.source_id or not self.target_id:
            raise ValueError("Coupling requires both source_id and target_id")
        if self.source_id == self.target_id:
            raise ValueError("Coupling: source and target must differ (no self-coupling)")
        if not (0.0 <= self.strength <= 1.0):
            raise ValueError(f"strength {self.strength} not in [0,1]")
        if self.coupling_type not in {"directional", "bidirectional", "broadcast"}:
            raise ValueError(f"invalid coupling_type: {self.coupling_type}")
        if not self.invariants:
            self.invariants = (
                "source_target_distinct",
                "strength_bounded",
                "coupling_type_classified",
            )
        super().__post_init__()


@dataclass
class Synchronization(ConstructBase):
    """
    WHAT: temporal_pattern_alignment.

    Names that two or more Patterns are aligned in time — same phase, same
    frequency, with a bounded drift tolerance. Distinct from Coupling
    (structural dependency) and Resonance (amplification).
    """

    type: ConstructType = ConstructType.SYNCHRONIZATION
    tier: Tier = Tier.COORDINATION

    pattern_ids: tuple[UUID, ...] = ()
    phase_offset: float = 0.0  # radians, in [0, 2π)
    frequency: float = 0.0  # Hz, >=0
    drift_tolerance: float = 0.0  # absolute, >=0

    def __post_init__(self) -> None:
        if len(self.pattern_ids) < 2:
            raise ValueError("Synchronization requires >= 2 patterns")
        if len(set(self.pattern_ids)) != len(self.pattern_ids):
            raise ValueError("Synchronization: pattern_ids must be distinct")
        if self.frequency < 0:
            raise ValueError(f"frequency {self.frequency} must be non-negative")
        if self.drift_tolerance < 0:
            raise ValueError(
                f"drift_tolerance {self.drift_tolerance} must be non-negative"
            )
        if not self.invariants:
            self.invariants = (
                "at_least_two_patterns",
                "patterns_distinct",
                "frequency_non_negative",
                "drift_bounded",
            )
        super().__post_init__()


@dataclass
class Resonance(ConstructBase):
    """
    WHAT: pattern_amplification at a frequency.

    A Resonance names that a Pattern amplifies in response to forcing at a
    particular frequency, up to a damping limit, above a threshold. Distinct
    from Synchronization (alignment without amplification).
    """

    type: ConstructType = ConstructType.RESONANCE
    tier: Tier = Tier.COORDINATION

    pattern_id: Optional[UUID] = None
    natural_frequency: float = 0.0
    amplitude: float = 0.0
    damping_factor: float = 0.0  # [0, 1] — 0 = undamped, 1 = critically damped
    activation_threshold: float = 0.0

    def __post_init__(self) -> None:
        if self.pattern_id is None:
            raise ValueError("Resonance requires pattern_id")
        if self.natural_frequency < 0:
            raise ValueError("natural_frequency must be non-negative")
        if self.amplitude < 0:
            raise ValueError("amplitude must be non-negative")
        if not (0.0 <= self.damping_factor <= 1.0):
            raise ValueError(f"damping_factor {self.damping_factor} not in [0,1]")
        if not self.invariants:
            self.invariants = (
                "pattern_referenced",
                "frequency_non_negative",
                "damping_bounded",
                "amplitude_non_negative",
            )
        super().__post_init__()


@dataclass
class Equilibrium(ConstructBase):
    """
    WHAT: stable_configuration of a system.

    Names attractor states the system tends toward, the basins of attraction
    that lead to them, and the perturbation tolerance before destabilization.
    Distinct from State (which is just a configuration) — Equilibrium is the
    *stability claim* about a configuration.
    """

    type: ConstructType = ConstructType.EQUILIBRIUM
    tier: Tier = Tier.COORDINATION

    attractor_state_ids: tuple[UUID, ...] = ()
    basin_boundary_id: Optional[UUID] = None
    perturbation_tolerance: float = 0.0  # >= 0
    stability_kind: str = "stable"  # stable | metastable | unstable

    def __post_init__(self) -> None:
        if not self.attractor_state_ids:
            raise ValueError("Equilibrium requires at least one attractor state")
        if len(set(self.attractor_state_ids)) != len(self.attractor_state_ids):
            raise ValueError("Equilibrium: attractor_state_ids must be distinct")
        if self.perturbation_tolerance < 0:
            raise ValueError("perturbation_tolerance must be non-negative")
        if self.stability_kind not in {"stable", "metastable", "unstable"}:
            raise ValueError(f"invalid stability_kind: {self.stability_kind}")
        if not self.invariants:
            self.invariants = (
                "attractor_present",
                "attractors_distinct",
                "tolerance_non_negative",
                "stability_classified",
            )
        super().__post_init__()


@dataclass
class Emergence(ConstructBase):
    """
    WHAT: novel_pattern_formation from component interactions.

    Names a Pattern that arises from Interaction(s) among components but is
    not reducible to any single component's State. Distinct from Pattern
    (which can be primitive) — Emergence asserts irreducibility.
    """

    type: ConstructType = ConstructType.EMERGENCE
    tier: Tier = Tier.COORDINATION

    component_ids: tuple[UUID, ...] = ()
    interaction_ids: tuple[UUID, ...] = ()
    novel_pattern_id: Optional[UUID] = None
    irreducibility_evidence: str = ""

    def __post_init__(self) -> None:
        if len(self.component_ids) < 2:
            raise ValueError("Emergence requires >= 2 components")
        if not self.interaction_ids:
            raise ValueError("Emergence requires at least one interaction")
        if self.novel_pattern_id is None:
            raise ValueError("Emergence requires novel_pattern_id")
        if not self.irreducibility_evidence:
            raise ValueError(
                "Emergence requires irreducibility_evidence; "
                "novelty without evidence is unfalsifiable"
            )
        if not self.invariants:
            self.invariants = (
                "components_plural",
                "interactions_present",
                "novelty_named",
                "irreducibility_evidenced",
            )
        super().__post_init__()


# ---- DISAMBIGUATION ----


TIER3_RESPONSIBILITIES: dict[ConstructType, str] = {
    ConstructType.COUPLING:        "WHAT_DEPENDS_ON_WHAT",
    ConstructType.SYNCHRONIZATION: "WHAT_ALIGNS_TEMPORALLY",
    ConstructType.RESONANCE:       "WHAT_AMPLIFIES_AT_FREQUENCY",
    ConstructType.EQUILIBRIUM:     "WHAT_STABILIZES",
    ConstructType.EMERGENCE:       "WHAT_PRODUCES_IRREDUCIBLE_NOVELTY",
}


def verify_tier3_disambiguation() -> None:
    seen: set[str] = set()
    for ct, resp in TIER3_RESPONSIBILITIES.items():
        if resp in seen:
            raise ValueError(f"tier 3 responsibility overlap detected: {resp}")
        seen.add(resp)


verify_tier3_disambiguation()
