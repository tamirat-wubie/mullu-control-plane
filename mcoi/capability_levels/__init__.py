"""Capability promotion ladder projections.

Purpose: expose the canonical L0-L9 capability promotion ladder for
operator-facing read models.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: capability registry entries and governed capability records.
Invariants: promotion levels describe authority boundaries and never grant
execution authority by themselves.
"""

from .ladder import (
    CAPABILITY_PROMOTION_LADDER_ID,
    PromotionLevel,
    default_capability_promotion_ladder,
    promotion_level_for_entry,
    promotion_level_projection,
    validate_capability_promotion_ladder,
)

__all__ = [
    "CAPABILITY_PROMOTION_LADDER_ID",
    "PromotionLevel",
    "default_capability_promotion_ladder",
    "promotion_level_for_entry",
    "promotion_level_projection",
    "validate_capability_promotion_ladder",
]
