"""
Cascade Invalidation Engine.

When a construct is modified, every construct that depends on it must be
checked. The cascade rules are:

  1. If the dependent's invariants are still satisfied → continue.
  2. If the dependent can be auto-repaired → repair it (recurse).
  3. Otherwise → escalate to human review.
  4. If global consistency cannot be re-established → reject the change.

This is the data-side mechanism that Φ_gov calls when validating a Δ.
The Φ_gov wrapper itself lives at runtime/governance/phi_gov.py; this module
is the substrate-level engine.

Loop bounds: cascades are terminated by depth limit (default 16) and by
visited-set tracking. Cycles never produce infinite cascades.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from uuid import UUID

from mcoi_runtime.substrate.constructs import ConstructBase


MAX_CASCADE_DEPTH = 16


class CascadeOutcome(Enum):
    """What happened to a single dependent during cascade processing."""

    PRESERVED = "preserved"          # invariants still hold
    AUTO_REPAIRED = "auto_repaired"  # repair function applied
    ESCALATED = "escalated"          # human review required
    REJECTED = "rejected"            # would violate global consistency


@dataclass
class CascadeStep:
    """One node visited during a cascade."""

    construct_id: UUID
    construct_type: str
    outcome: CascadeOutcome
    reason: str = ""
    repair_description: str = ""


@dataclass
class CascadeResult:
    """Outcome of a full cascade walk from one root change."""

    root_construct_id: UUID
    steps: list[CascadeStep] = field(default_factory=list)
    rejected: bool = False
    escalations: int = 0
    auto_repairs: int = 0
    preserved: int = 0
    truncated_at_depth: bool = False
    cycles_detected: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "root": str(self.root_construct_id),
            "rejected": self.rejected,
            "preserved": self.preserved,
            "auto_repairs": self.auto_repairs,
            "escalations": self.escalations,
            "truncated_at_depth": self.truncated_at_depth,
            "cycles_detected": self.cycles_detected,
            "steps": len(self.steps),
        }


# ---- Dependency graph ----


@dataclass
class DependencyGraph:
    """Bidirectional construct dependency graph.

    `dependents[X]` lists every construct that REFERENCES X. When X changes,
    those are the constructs whose invariants must be re-checked.
    """

    constructs: dict[UUID, ConstructBase] = field(default_factory=dict)
    dependents: dict[UUID, set[UUID]] = field(default_factory=dict)

    def register(
        self,
        construct: ConstructBase,
        depends_on: tuple[UUID, ...] = (),
    ) -> None:
        """Add a construct and the IDs it depends on."""
        if construct.id in self.constructs:
            raise ValueError(f"construct {construct.id} already registered")
        self.constructs[construct.id] = construct
        for dep_id in depends_on:
            if dep_id == construct.id:
                raise ValueError(
                    f"construct {construct.id} cannot depend on itself"
                )
            self.dependents.setdefault(dep_id, set()).add(construct.id)

    def unregister(self, construct_id: UUID) -> None:
        """Remove a construct. Caller must ensure no live dependents remain."""
        if construct_id in self.dependents and self.dependents[construct_id]:
            live = self.dependents[construct_id]
            raise ValueError(
                f"cannot unregister {construct_id}: {len(live)} dependents remain"
            )
        self.constructs.pop(construct_id, None)
        self.dependents.pop(construct_id, None)
        # Remove this id from any other construct's dependent set
        for dep_set in self.dependents.values():
            dep_set.discard(construct_id)

    def direct_dependents_of(self, construct_id: UUID) -> set[UUID]:
        return set(self.dependents.get(construct_id, set()))


# ---- Repair / validation contract ----

InvariantChecker = Callable[[ConstructBase, ConstructBase], bool]
"""Returns True iff the dependent's invariants still hold after the change."""

AutoRepairer = Callable[[ConstructBase, ConstructBase], Optional[str]]
"""Returns a repair description string if auto-repair succeeded, else None."""


def default_invariant_checker(
    dependent: ConstructBase, changed: ConstructBase
) -> bool:
    """Conservative default: if the dependent type is one we know references
    fields by UUID and the changed construct is still present in the graph
    (i.e. not deleted), assume invariants hold. Replace per-type with stricter
    checks once full Tier 2-5 invariant validators are wired.
    """
    # Default is permissive — Φ_gov is expected to wire stricter per-type
    # validators in for production use. This default lets the cascade engine
    # exercise its control flow without false negatives in unit tests.
    return True


def default_auto_repairer(
    dependent: ConstructBase, changed: ConstructBase
) -> Optional[str]:
    """Default repairer: refuses to auto-repair, returning None.

    Auto-repair must be opt-in per construct type, because silent repair is
    the same fabrication pattern as MUSIA_MODE. Better to escalate than to
    quietly mutate state.
    """
    return None


# ---- Cascade engine ----


class CascadeEngine:
    """Walks the dependency graph in BFS order, classifying each dependent."""

    def __init__(
        self,
        graph: DependencyGraph,
        invariant_checker: InvariantChecker = default_invariant_checker,
        auto_repairer: AutoRepairer = default_auto_repairer,
        max_depth: int = MAX_CASCADE_DEPTH,
    ) -> None:
        self._graph = graph
        self._check = invariant_checker
        self._repair = auto_repairer
        self._max_depth = max_depth

    def cascade(self, changed_id: UUID) -> CascadeResult:
        """Walk every transitive dependent of `changed_id`."""
        if changed_id not in self._graph.constructs:
            raise ValueError(f"unknown construct: {changed_id}")
        changed = self._graph.constructs[changed_id]
        result = CascadeResult(root_construct_id=changed_id)

        # BFS frontier with depth tracking. visited prevents cycle blow-up.
        frontier: list[tuple[UUID, int]] = []
        visited: set[UUID] = {changed_id}
        for dep_id in self._graph.direct_dependents_of(changed_id):
            frontier.append((dep_id, 1))

        while frontier:
            current_id, depth = frontier.pop(0)
            if current_id in visited:
                result.cycles_detected += 1
                continue
            visited.add(current_id)

            if depth > self._max_depth:
                result.truncated_at_depth = True
                result.rejected = True
                result.steps.append(
                    CascadeStep(
                        construct_id=current_id,
                        construct_type=self._type_of(current_id),
                        outcome=CascadeOutcome.REJECTED,
                        reason=f"depth limit {self._max_depth} exceeded",
                    )
                )
                break

            dependent = self._graph.constructs.get(current_id)
            if dependent is None:
                # The dependent was unregistered between cascade start and
                # this step — treat as preserved (nothing to invalidate).
                result.preserved += 1
                result.steps.append(
                    CascadeStep(
                        construct_id=current_id,
                        construct_type="<missing>",
                        outcome=CascadeOutcome.PRESERVED,
                        reason="dependent no longer in graph",
                    )
                )
                continue

            if self._check(dependent, changed):
                result.preserved += 1
                result.steps.append(
                    CascadeStep(
                        construct_id=current_id,
                        construct_type=dependent.type.value,
                        outcome=CascadeOutcome.PRESERVED,
                    )
                )
                # Even if preserved, dependents-of-dependents are unaffected
                # by definition of "preserved". No further recursion needed.
                continue

            repair_desc = self._repair(dependent, changed)
            if repair_desc:
                result.auto_repairs += 1
                result.steps.append(
                    CascadeStep(
                        construct_id=current_id,
                        construct_type=dependent.type.value,
                        outcome=CascadeOutcome.AUTO_REPAIRED,
                        repair_description=repair_desc,
                    )
                )
                # Auto-repair may itself invalidate transitive dependents.
                for grand_id in self._graph.direct_dependents_of(current_id):
                    if grand_id not in visited:
                        frontier.append((grand_id, depth + 1))
                continue

            # No repair available → escalate
            result.escalations += 1
            result.steps.append(
                CascadeStep(
                    construct_id=current_id,
                    construct_type=dependent.type.value,
                    outcome=CascadeOutcome.ESCALATED,
                    reason="invariant violated; no auto-repair available",
                )
            )
            # Escalation does NOT auto-reject the cascade — Φ_gov decides
            # whether escalations are blocking. The cascade walk continues
            # so the operator gets a complete picture.

        return result

    def _type_of(self, construct_id: UUID) -> str:
        c = self._graph.constructs.get(construct_id)
        if c is None:
            return "<missing>"
        return c.type.value
