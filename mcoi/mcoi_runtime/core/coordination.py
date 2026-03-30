"""Purpose: coordination core engine — delegation routing, handoff tracking, merge/conflict management.
Governance scope: coordination plane core logic only.
Dependencies: coordination contracts, invariant helpers, optional persistence store.
Invariants:
  - All coordination preserves provenance and identity.
  - Delegation targets are explicit.
  - Conflicts are recorded, never silently discarded.
  - Checkpoint persistence is explicit — no autosave or hidden restore.
  - Restore is governed: expired leases, policy drift, and retry caps are enforced.
  - No multi-agent runtime yet — this is the contract + routing layer.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from mcoi_runtime.contracts.coordination import (
    ConflictRecord,
    ConflictStrategy,
    CoordinationCheckpoint,
    DelegationRequest,
    DelegationResult,
    DelegationStatus,
    HandoffRecord,
    MergeDecision,
    MergeOutcome,
    RestoreOutcome,
    RestoreStatus,
)
from .invariants import RuntimeCoreInvariantError, ensure_non_empty_text

_MAX_RETRY_COUNT = 3


def _default_clock() -> str:
    return datetime.now(timezone.utc).isoformat()


class CoordinationEngine:
    """Delegation routing, handoff tracking, and merge/conflict management.

    This engine:
    - Tracks delegation requests and results
    - Records handoffs with full provenance
    - Records merge decisions and conflicts
    - Supports explicit checkpoint/restore for coordination persistence
    - Does NOT execute delegated work — that requires agent runtime
    """

    def __init__(
        self,
        *,
        clock: Callable[[], str] | None = None,
        coordination_store: Any | None = None,
        policy_pack_id: str = "",
    ) -> None:
        self._clock = clock or _default_clock
        self._coordination_store = coordination_store
        self._policy_pack_id = policy_pack_id
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

    def summary(self) -> dict[str, Any]:
        """Return a snapshot of coordination state counts for observability."""
        return {
            "delegations": self.delegation_count,
            "handoffs": self.handoff_count,
            "merges": self.merge_count,
            "conflicts": len(self._conflicts),
            "unresolved_conflicts": len(self.list_unresolved_conflicts()),
        }

    # --- Checkpoint / Restore ---

    def save_checkpoint(
        self,
        checkpoint_id: str,
        lease_duration_seconds: int = 3600,
        restore_conditions: dict[str, Any] | None = None,
    ) -> CoordinationCheckpoint:
        """Persist current coordination state as a governed checkpoint.

        This is an explicit operation — the engine never auto-saves.
        """
        if self._coordination_store is None:
            raise RuntimeCoreInvariantError(
                "no coordination store configured"
            )
        ensure_non_empty_text("checkpoint_id", checkpoint_id)

        now = self._clock()
        now_dt = datetime.fromisoformat(now)
        expires_dt = now_dt + timedelta(seconds=lease_duration_seconds)

        checkpoint = CoordinationCheckpoint(
            checkpoint_id=checkpoint_id,
            delegations=tuple(
                sorted(self._delegations.values(), key=lambda d: d.delegation_id)
            ),
            delegation_results=tuple(
                sorted(self._delegation_results.values(), key=lambda r: r.delegation_id)
            ),
            handoffs=tuple(
                sorted(self._handoffs.values(), key=lambda h: h.handoff_id)
            ),
            merges=tuple(
                sorted(self._merges.values(), key=lambda m: m.merge_id)
            ),
            conflicts=tuple(
                sorted(self._conflicts.values(), key=lambda c: c.conflict_id)
            ),
            created_at=now,
            lease_expires_at=expires_dt.isoformat(),
            retry_count=0,
            policy_pack_id=self._policy_pack_id or "default",
            restore_conditions=restore_conditions or {},
        )
        self._coordination_store.save_state(checkpoint_id, checkpoint)
        return checkpoint

    def restore_checkpoint(
        self,
        checkpoint_id: str,
        *,
        current_policy_pack_id: str | None = None,
    ) -> RestoreOutcome:
        """Restore coordination state from a persisted checkpoint with governed guards.

        Guards enforced:
        - Lease expiration: checkpoint rejected if lease has expired
        - Policy pack drift: checkpoint requires review if pack changed
        - Retry cap: checkpoint aborted if retry_count >= MAX_RETRY_COUNT
        """
        if self._coordination_store is None:
            raise RuntimeCoreInvariantError(
                "no coordination store configured"
            )
        ensure_non_empty_text("checkpoint_id", checkpoint_id)

        checkpoint: CoordinationCheckpoint = self._coordination_store.load_state(
            checkpoint_id, CoordinationCheckpoint,
        )
        now = self._clock()

        # Guard: lease expiration
        now_dt = datetime.fromisoformat(now)
        lease_dt = datetime.fromisoformat(checkpoint.lease_expires_at)
        if now_dt > lease_dt:
            return RestoreOutcome(
                checkpoint_id=checkpoint_id,
                status=RestoreStatus.EXPIRED,
                reason=f"lease expired at {checkpoint.lease_expires_at}",
                restored_at=now,
            )

        # Guard: retry cap
        if checkpoint.retry_count >= _MAX_RETRY_COUNT:
            return RestoreOutcome(
                checkpoint_id=checkpoint_id,
                status=RestoreStatus.ABORTED,
                reason=f"max retry count ({_MAX_RETRY_COUNT}) exceeded",
                restored_at=now,
            )

        # Guard: policy pack drift
        if (
            current_policy_pack_id is not None
            and current_policy_pack_id != checkpoint.policy_pack_id
        ):
            return RestoreOutcome(
                checkpoint_id=checkpoint_id,
                status=RestoreStatus.NEEDS_REVIEW,
                reason=(
                    f"policy pack changed: "
                    f"{checkpoint.policy_pack_id} -> {current_policy_pack_id}"
                ),
                restored_at=now,
            )

        # All guards passed — populate engine state
        self._delegations = {d.delegation_id: d for d in checkpoint.delegations}
        self._delegation_results = {
            r.delegation_id: r for r in checkpoint.delegation_results
        }
        self._handoffs = {h.handoff_id: h for h in checkpoint.handoffs}
        self._merges = {m.merge_id: m for m in checkpoint.merges}
        self._conflicts = {c.conflict_id: c for c in checkpoint.conflicts}

        return RestoreOutcome(
            checkpoint_id=checkpoint_id,
            status=RestoreStatus.RESUMED,
            reason="checkpoint restored successfully",
            restored_at=now,
        )

    def increment_retry(self, checkpoint_id: str) -> CoordinationCheckpoint:
        """Atomically increment the retry count on a persisted checkpoint."""
        if self._coordination_store is None:
            raise RuntimeCoreInvariantError(
                "no coordination store configured"
            )
        ensure_non_empty_text("checkpoint_id", checkpoint_id)

        old: CoordinationCheckpoint = self._coordination_store.load_state(
            checkpoint_id, CoordinationCheckpoint,
        )
        updated = CoordinationCheckpoint(
            checkpoint_id=old.checkpoint_id,
            delegations=old.delegations,
            delegation_results=old.delegation_results,
            handoffs=old.handoffs,
            merges=old.merges,
            conflicts=old.conflicts,
            created_at=old.created_at,
            lease_expires_at=old.lease_expires_at,
            retry_count=old.retry_count + 1,
            policy_pack_id=old.policy_pack_id,
            restore_conditions=dict(old.restore_conditions),
        )
        self._coordination_store.save_state(checkpoint_id, updated)
        return updated
