"""25-construct universal causal framework (5 tiers x 5 constructs)."""
from mcoi_runtime.substrate.constructs.tier1_foundational import (
    Boundary,
    Causation,
    Change,
    Constraint,
    ConstructBase,
    ConstructType,
    MfidelSignature,
    State,
    Tier,
    TIER1_RESPONSIBILITIES,
    verify_tier1_disambiguation,
)
from mcoi_runtime.substrate.constructs.tier2_structural import (
    Composition,
    Conservation,
    Interaction,
    Pattern,
    Transformation,
    TIER2_RESPONSIBILITIES,
    verify_no_cross_tier_overlap,
    verify_tier2_disambiguation,
)
from mcoi_runtime.substrate.constructs.tier3_coordination import (
    Coupling,
    Emergence,
    Equilibrium,
    Resonance,
    Synchronization,
    TIER3_RESPONSIBILITIES,
    verify_tier3_disambiguation,
)
from mcoi_runtime.substrate.constructs.tier4_governance import (
    Binding,
    Evolution,
    Integrity,
    Source,
    Validation,
    TIER4_RESPONSIBILITIES,
    verify_tier4_disambiguation,
)
from mcoi_runtime.substrate.constructs.tier5_cognitive import (
    Decision,
    Execution,
    Inference,
    Learning,
    Observation,
    TIER5_RESPONSIBILITIES,
    verify_tier5_disambiguation,
)

# Run cross-tier check after every tier module is loaded.
verify_no_cross_tier_overlap()


def all_responsibility_tables() -> list[dict]:
    """All 5 tier tables, in order. 25 entries total."""
    return [
        TIER1_RESPONSIBILITIES,
        TIER2_RESPONSIBILITIES,
        TIER3_RESPONSIBILITIES,
        TIER4_RESPONSIBILITIES,
        TIER5_RESPONSIBILITIES,
    ]


__all__ = [
    # Tier 1 — Foundational
    "Boundary",
    "Causation",
    "Change",
    "Constraint",
    "State",
    # Tier 2 — Structural
    "Composition",
    "Conservation",
    "Interaction",
    "Pattern",
    "Transformation",
    # Tier 3 — Coordination
    "Coupling",
    "Emergence",
    "Equilibrium",
    "Resonance",
    "Synchronization",
    # Tier 4 — Governance
    "Binding",
    "Evolution",
    "Integrity",
    "Source",
    "Validation",
    # Tier 5 — Cognitive
    "Decision",
    "Execution",
    "Inference",
    "Learning",
    "Observation",
    # Shared
    "ConstructBase",
    "ConstructType",
    "MfidelSignature",
    "Tier",
    # Disambiguation tables
    "TIER1_RESPONSIBILITIES",
    "TIER2_RESPONSIBILITIES",
    "TIER3_RESPONSIBILITIES",
    "TIER4_RESPONSIBILITIES",
    "TIER5_RESPONSIBILITIES",
    "all_responsibility_tables",
    # Verifiers
    "verify_tier1_disambiguation",
    "verify_tier2_disambiguation",
    "verify_tier3_disambiguation",
    "verify_tier4_disambiguation",
    "verify_tier5_disambiguation",
    "verify_no_cross_tier_overlap",
]
