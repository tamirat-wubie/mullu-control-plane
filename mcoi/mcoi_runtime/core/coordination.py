"""Purpose: coordination core engine — delegation routing, handoff tracking, merge/conflict management.
Governance scope: coordination plane core logic only.
Dependencies: coordination contracts, invariant helpers.
Invariants:
  - All coordination preserves provenance and identity.
  - Delegation targets are explicit.
  - Conflicts are recorded, never silently discarded.
  - No multi-agent runtime yet — this is the contract + routing layer.
"""

from __future__ import annotations

from mcoi_runtime.contracts.coordination import (
    ConflictRecord,
    ConflictStrategy,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    HandoffRecord,
    MergeDecision,
    MergeOutcome,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text


class CoordinationEngine:
    """Delegation routing, handoff tracking, and merge/conflict management.

    This engine:
    - Tracks delegation requests and results
    - Records handoffs with full provenance
    - Records merge decisions and conflicts
    - Does NOT execute delegated work — that requires agent runtime
    """

    def __init__(self) -> None:
        self._delegations: dict[str, DelegationRequest] = {}
        self._delegation_results: dict[str, DelegationResult] = {}
        self._handoffs: dict[str, HandoffRecord] = {}
        self._merges: dict[str, MergeDecision] = {}
        self._conflicts: dict[str, ConflictRecord] = {}

    # --- Delegation ---

    def request_delegation(self, request: DelegationRequest) -> DelegationRequest:
        if request.delegation_id in self._delegations:
            raise RuntimeCoreInvariantError(
                f"delegation already exists: {request.delegation_id}"
            )
        self._delegations[request.delegation_id] = request
        return request

    def resolve_delegation(self, result: DelegationResult) -> DelegationResult:
        if result.delegation_id not in self._delegations:
            raise RuntimeCoreInvariantError(
                f"delegation not found: {result.delegation_id}"
            )
        if result.delegation_id in self._delegation_results:
            raise RuntimeCoreInvariantError(
                f"delegation already resolved: {result.delegation_id}"
            )
        self._delegation_results[result.delegation_id] = result
        return result

    def get_delegation(self, delegation_id: str) -> DelegationRequest | None:
        ensure_non_empty_text("delegation_id", delegation_id)
        return self._delegations.get(delegation_id)

    def get_delegation_result(self, delegation_id: str) -> DelegationResult | None:
        ensure_non_empty_text("delegation_id", delegation_id)
        return self._delegation_results.get(delegation_id)

    # --- Handoff ---

    def record_handoff(self, handoff: HandoffRecord) -> HandoffRecord:
        if handoff.handoff_id in self._handoffs:
            raise RuntimeCoreInvariantError(
                f"handoff already recorded: {handoff.handoff_id}"
            )
        self._handoffs[handoff.handoff_id] = handoff
        return handoff

    def get_handoff(self, handoff_id: str) -> HandoffRecord | None:
        ensure_non_empty_text("handoff_id", handoff_id)
        return self._handoffs.get(handoff_id)

    # --- Merge ---

    def record_merge(self, decision: MergeDecision) -> MergeDecision:
        if decision.merge_id in self._merges:
            raise RuntimeCoreInvariantError(
                f"merge already recorded: {decision.merge_id}"
            )
        self._merges[decision.merge_id] = decision
        return decision

    def get_merge(self, merge_id: str) -> MergeDecision | None:
        ensure_non_empty_text("merge_id", merge_id)
        return self._merges.get(merge_id)

    # --- Conflict ---

    def record_conflict(self, conflict: ConflictRecord) -> ConflictRecord:
        if conflict.conflict_id in self._conflicts:
            raise RuntimeCoreInvariantError(
                f"conflict already recorded: {conflict.conflict_id}"
            )
        self._conflicts[conflict.conflict_id] = conflict
        return conflict

    def get_conflict(self, conflict_id: str) -> ConflictRecord | None:
        ensure_non_empty_text("conflict_id", conflict_id)
        return self._conflicts.get(conflict_id)

    def list_unresolved_conflicts(self) -> tuple[ConflictRecord, ...]:
        return tuple(
            c for c in sorted(self._conflicts.values(), key=lambda c: c.conflict_id)
            if not c.resolved
        )

    @property
    def delegation_count(self) -> int:
        return len(self._delegations)

    @property
    def handoff_count(self) -> int:
        return len(self._handoffs)

    @property
    def merge_count(self) -> int:
        return len(self._merges)
