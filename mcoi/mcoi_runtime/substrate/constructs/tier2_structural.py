"""
Tier 2 — Structural Constructs (Composition Mechanics).

Where Tier 1 names irreducible primitives (State, Change, Causation, Constraint,
Boundary), Tier 2 names how those primitives combine into structures large
enough to do real work. Each Tier 2 construct is a disciplined composition
rule, not a primitive.

Tier 2 constructs reference Tier 1 by UUID (the construct's `id` field), not by
Mfidel coordinate. This insulates Tier 2 from substrate convergence questions.

Disambiguation pattern matches Tier 1: each construct has exactly one
irreducible responsibility. Cross-tier overlap is rejected at module load.

Spec source: docs/MUSIA_TIER_2_INTERFACES_DRAFT.md (now implemented).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from mcoi_runtime.substrate.constructs.tier1_foundational import (
    ConstructBase,
    ConstructType,
    Tier,
    TIER1_RESPONSIBILITIES,
)


# ---- TIER 2 CONSTRUCTS ----


@dataclass
class Pattern(ConstructBase):
    """
    WHAT: repeated configuration across instances.

    A Pattern names a template-and-instances relationship. The template is a
    representative State (or State-shape); instances are State IDs that match
    the template under a similarity rule. Variations are documented deviations
    within tolerance.

    Distinct from State (which describes one configuration) and from
    Composition (which nests Patterns).
    """

    type: ConstructType = ConstructType.PATTERN
    tier: Tier = Tier.STRUCTURAL

    template_state_id: Optional[UUID] = None
    instance_state_ids: tuple[UUID, ...] = ()
    similarity_rule: str = "structural_equivalence"
    similarity_threshold: float = 1.0  # [0, 1]
    variation_tolerance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not (0.0 <= self.similarity_threshold <= 1.0):
            raise ValueError(
                f"similarity_threshold {self.similarity_threshold} not in [0,1]"
            )
        if not self.template_state_id and not self.instance_state_ids:
            raise ValueError("Pattern requires either a template or instances")
        if not self.similarity_rule:
            raise ValueError("Pattern requires a similarity_rule identifier")
        if not self.invariants:
            self.invariants = (
                "template_or_instances_present",
                "similarity_rule_decidable",
                "threshold_bounded",
            )
        super().__post_init__()


@dataclass
class Transformation(ConstructBase):
    """
    WHAT: bounded state sequence driven by causation within a boundary.

    The smallest composite construct that names a complete causal step.
    References:
      - initial State + target State (the endpoints)
      - the Change that bridges them
      - the Causation that produces the Change
      - the Boundary the whole sequence operates within

    Distinct from Change (which is just the delta) and Causation (which is
    just the producer). Transformation is the full causal step.
    """

    type: ConstructType = ConstructType.TRANSFORMATION
    tier: Tier = Tier.STRUCTURAL

    initial_state_id: Optional[UUID] = None
    target_state_id: Optional[UUID] = None
    change_id: Optional[UUID] = None
    causation_id: Optional[UUID] = None
    boundary_id: Optional[UUID] = None

    energy_estimate: float = 0.0  # arbitrary scale; >=0
    reversibility: str = "unknown"  # reversible | irreversible | unknown

    def __post_init__(self) -> None:
        if self.energy_estimate < 0:
            raise ValueError(
                f"energy_estimate {self.energy_estimate} must be non-negative"
            )
        if self.reversibility not in {"reversible", "irreversible", "unknown"}:
            raise ValueError(f"invalid reversibility: {self.reversibility}")
        if not self.invariants:
            self.invariants = (
                "tier1_references_required",
                "boundary_contains_states",
                "change_matches_states",
                "causation_produces_change",
            )
        super().__post_init__()


@dataclass
class Composition(ConstructBase):
    """
    WHAT: nested pattern structure.

    The construct that lets Patterns contain other Patterns, bounded by an
    enclosing Boundary. Names that nesting is well-defined and acyclic.

    Distinct from Pattern (which names what repeats) and from Constraint
    (which names what is forbidden).
    """

    type: ConstructType = ConstructType.COMPOSITION
    tier: Tier = Tier.STRUCTURAL

    container_pattern_id: Optional[UUID] = None
    contained_pattern_ids: tuple[UUID, ...] = ()
    boundary_id: Optional[UUID] = None
    nesting_depth: int = 1  # 1 = direct containment

    def __post_init__(self) -> None:
        if self.nesting_depth < 1:
            raise ValueError(
                f"nesting_depth {self.nesting_depth} must be >= 1"
            )
        if self.nesting_depth > 5:
            raise ValueError(
                f"nesting_depth {self.nesting_depth} exceeds bounded-recursion limit (5)"
            )
        if self.container_pattern_id is None:
            raise ValueError("Composition requires container_pattern_id")
        if not self.contained_pattern_ids:
            raise ValueError("Composition requires at least one contained pattern")
        if self.container_pattern_id in self.contained_pattern_ids:
            raise ValueError("Composition: container cannot also be contained (cyclic)")
        if not self.invariants:
            self.invariants = (
                "container_distinct_from_contained",
                "no_cyclic_nesting",
                "depth_bounded",
                "all_within_boundary",
            )
        super().__post_init__()


@dataclass
class Conservation(ConstructBase):
    """
    WHAT: invariant pattern property preserved across change.

    Names something that does NOT change when other things do. Pairs a
    Pattern (the invariant) with a Constraint (the enforcement rule) and a
    scope Boundary.

    Distinct from Constraint alone:
      - Constraint says "X is forbidden"
      - Conservation says "X is preserved even as Y varies"
    A Conservation typically uses a Constraint as enforcement, but adds the
    structural claim of cross-change invariance.
    """

    type: ConstructType = ConstructType.CONSERVATION
    tier: Tier = Tier.STRUCTURAL

    invariant_pattern_id: Optional[UUID] = None
    enforcing_constraint_id: Optional[UUID] = None
    scope_boundary_id: Optional[UUID] = None
    violation_detection: str = "post_change_validation"
    # post_change_validation | pre_change_block | continuous_monitoring

    def __post_init__(self) -> None:
        valid_detection = {
            "post_change_validation",
            "pre_change_block",
            "continuous_monitoring",
        }
        if self.violation_detection not in valid_detection:
            raise ValueError(
                f"invalid violation_detection: {self.violation_detection}"
            )
        if not (
            self.invariant_pattern_id
            and self.enforcing_constraint_id
            and self.scope_boundary_id
        ):
            raise ValueError(
                "Conservation requires invariant_pattern_id, "
                "enforcing_constraint_id, and scope_boundary_id"
            )
        if not self.invariants:
            self.invariants = (
                "pattern_constraint_boundary_resolved",
                "violation_detection_decidable",
                "scope_well_defined",
            )
        super().__post_init__()


@dataclass
class Interaction(ConstructBase):
    """
    WHAT: mutual change relationship between two or more participants.

    Two (or more) Causations facing each other: each participant produces a
    Change in the others.

    Distinct from a single Causation (unidirectional) and from a Composition
    (structural, not dynamic).
    """

    type: ConstructType = ConstructType.INTERACTION
    tier: Tier = Tier.STRUCTURAL

    participant_state_ids: tuple[UUID, ...] = ()
    causation_ids: tuple[UUID, ...] = ()  # one per direction, minimum
    coupling_strength: float = 0.0  # [0, 1]
    feedback_kind: str = "none"  # none | positive | negative | mixed

    def __post_init__(self) -> None:
        if len(self.participant_state_ids) < 2:
            raise ValueError(
                "Interaction requires >= 2 participant_state_ids"
            )
        if len(self.causation_ids) < len(self.participant_state_ids):
            raise ValueError(
                "Interaction requires at least one Causation per participant"
            )
        if not (0.0 <= self.coupling_strength <= 1.0):
            raise ValueError(
                f"coupling_strength {self.coupling_strength} not in [0,1]"
            )
        if self.feedback_kind not in {"none", "positive", "negative", "mixed"}:
            raise ValueError(f"invalid feedback_kind: {self.feedback_kind}")
        # No duplicate participants — each must be distinct
        if len(set(self.participant_state_ids)) != len(self.participant_state_ids):
            raise ValueError("Interaction: participant_state_ids must be distinct")
        if not self.invariants:
            self.invariants = (
                "at_least_two_participants",
                "causation_per_participant",
                "coupling_bounded",
                "feedback_classified",
                "participants_distinct",
            )
        super().__post_init__()


# ---- DISAMBIGUATION ----


TIER2_RESPONSIBILITIES: dict[ConstructType, str] = {
    ConstructType.PATTERN:        "WHAT_REPEATS",
    ConstructType.TRANSFORMATION: "WHAT_DRIVES_BOUNDED_STATE_SEQUENCES",
    ConstructType.COMPOSITION:    "WHAT_NESTS_PATTERNS",
    ConstructType.INTERACTION:    "WHAT_PRODUCES_MUTUAL_CHANGE",
    ConstructType.CONSERVATION:   "WHAT_INVARIANTS_HOLD_ACROSS_CHANGE",
}


def verify_tier2_disambiguation() -> None:
    """No two Tier 2 constructs may share the same irreducible function."""
    seen: set[str] = set()
    for ct, resp in TIER2_RESPONSIBILITIES.items():
        if resp in seen:
            raise ValueError(f"tier 2 responsibility overlap detected: {resp}")
        seen.add(resp)


def verify_no_cross_tier_overlap() -> None:
    """All implemented tiers must have disjoint responsibilities.

    Imports Tier 3-5 responsibility tables lazily so that this verifier sees
    whatever tiers are loaded, regardless of import order.
    """
    tables: list[dict] = [
        TIER1_RESPONSIBILITIES,
        TIER2_RESPONSIBILITIES,
    ]
    try:
        from mcoi_runtime.substrate.constructs.tier3_coordination import (
            TIER3_RESPONSIBILITIES,
        )
        tables.append(TIER3_RESPONSIBILITIES)
    except ImportError:
        pass
    try:
        from mcoi_runtime.substrate.constructs.tier4_governance import (
            TIER4_RESPONSIBILITIES,
        )
        tables.append(TIER4_RESPONSIBILITIES)
    except ImportError:
        pass
    try:
        from mcoi_runtime.substrate.constructs.tier5_cognitive import (
            TIER5_RESPONSIBILITIES,
        )
        tables.append(TIER5_RESPONSIBILITIES)
    except ImportError:
        pass

    all_responsibilities: list[str] = []
    for t in tables:
        all_responsibilities.extend(t.values())
    expected = sum(len(t) for t in tables)
    if len(set(all_responsibilities)) != expected:
        duplicates = {
            r for r in all_responsibilities if all_responsibilities.count(r) > 1
        }
        raise ValueError(
            f"cross-tier responsibility overlap detected: {sorted(duplicates)}"
        )


verify_tier2_disambiguation()
verify_no_cross_tier_overlap()
