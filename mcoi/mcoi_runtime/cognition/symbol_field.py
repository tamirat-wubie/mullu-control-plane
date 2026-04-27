"""
Symbol Field — working memory for the SCCCE cognitive cycle.

Holds the current set of active constructs the cycle is reasoning over,
indexed by tier and type for fast lookup. Wraps a DependencyGraph so
cascade walks remain available within the cycle.

Loosely models the 𝕊 (state) component of the USCL symbol layer:
constructs are registered, retrieved, and modified through Φ_gov, never
mutated in place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional
from uuid import UUID

from mcoi_runtime.substrate.cascade import DependencyGraph
from mcoi_runtime.substrate.constructs import (
    ConstructBase,
    ConstructType,
    Tier,
)


@dataclass
class SymbolField:
    """The cognitive cycle's view of the construct graph.

    Internally backed by a DependencyGraph so cascade and Φ_gov reuse the
    same registry. The `by_tier` and `by_type` indices are kept in sync on
    register/unregister.
    """

    graph: DependencyGraph = field(default_factory=DependencyGraph)
    by_tier: dict[Tier, set[UUID]] = field(default_factory=dict)
    by_type: dict[ConstructType, set[UUID]] = field(default_factory=dict)

    def register(
        self,
        construct: ConstructBase,
        depends_on: tuple[UUID, ...] = (),
    ) -> None:
        self.graph.register(construct, depends_on=depends_on)
        self.by_tier.setdefault(construct.tier, set()).add(construct.id)
        self.by_type.setdefault(construct.type, set()).add(construct.id)

    def unregister(self, construct_id: UUID) -> None:
        c = self.graph.constructs.get(construct_id)
        self.graph.unregister(construct_id)
        if c is not None:
            tier_set = self.by_tier.get(c.tier)
            if tier_set:
                tier_set.discard(construct_id)
            type_set = self.by_type.get(c.type)
            if type_set:
                type_set.discard(construct_id)

    def get(self, construct_id: UUID) -> Optional[ConstructBase]:
        return self.graph.constructs.get(construct_id)

    def of_tier(self, tier: Tier) -> list[ConstructBase]:
        ids = self.by_tier.get(tier, set())
        return [self.graph.constructs[i] for i in ids if i in self.graph.constructs]

    def of_type(self, ct: ConstructType) -> list[ConstructBase]:
        ids = self.by_type.get(ct, set())
        return [self.graph.constructs[i] for i in ids if i in self.graph.constructs]

    def all_constructs(self) -> Iterable[ConstructBase]:
        return self.graph.constructs.values()

    @property
    def size(self) -> int:
        return len(self.graph.constructs)

    def tier_sizes(self) -> dict[Tier, int]:
        return {t: len(s) for t, s in self.by_tier.items()}

    def type_counts(self) -> dict[str, int]:
        """For domain adapter compatibility — keys are ConstructType.value strings."""
        return {ct.value: len(s) for ct, s in self.by_type.items() if s}
