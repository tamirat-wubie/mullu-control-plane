"""Phase 4C — Proof Bridge: MCOI Governance ↔ MAF Transitions.

Purpose: Bridge that links MCOI governance decisions to MAF transition
    receipts, creating a provable chain from governance guard evaluations
    through to state machine transitions. Produces ProofCapsules from
    governance contexts.
Governance scope: proof generation and verification only.
Dependencies: contracts.proof, contracts.state_machine, core.governance_guard.
Invariants:
  - Every governance decision can produce a transition receipt.
  - Guard verdicts map 1:1 from GovernanceGuard results.
  - Receipt hashes are deterministic (same inputs → same hash).
  - Causal lineage is append-only (no rewriting history).
  - All proof types serialize to JSON matching MAF Rust serde output.
"""

from __future__ import annotations

import hashlib
import threading
from dataclasses import dataclass
from typing import Any, Callable

from mcoi_runtime.contracts.proof import (
    CausalLineage,
    GuardVerdict,
    ProofCapsule,
    TransitionReceipt,
    certify_transition,
)
from mcoi_runtime.contracts.receipt_store import (
    InMemoryReceiptStore,
    ReceiptStore,
)
from mcoi_runtime.contracts.state_machine import (
    StateMachineSpec,
    TransitionRule,
)
from mcoi_runtime.core.temporal_scheduler import (
    ScheduledTemporalAction,
    ScheduleDecisionVerdict,
    TemporalRunReceipt,
)


# ═══ Governance State Machine ═══

# Models the governance decision lifecycle as a formal state machine.
GOVERNANCE_MACHINE = StateMachineSpec(
    machine_id="governance-decision",
    name="Governance Decision Machine",
    version="1.0.0",
    states=("pending", "evaluating", "allowed", "denied", "error"),
    initial_state="pending",
    terminal_states=("allowed", "denied", "error"),
    transitions=(
        TransitionRule(from_state="pending", to_state="evaluating", action="start_evaluation"),
        TransitionRule(from_state="evaluating", to_state="allowed", action="all_guards_passed"),
        TransitionRule(from_state="evaluating", to_state="denied", action="guard_rejected"),
        TransitionRule(from_state="evaluating", to_state="error", action="guard_error"),
    ),
)


TEMPORAL_SCHEDULER_MACHINE = StateMachineSpec(
    machine_id="temporal-scheduler",
    name="Temporal Scheduler Machine",
    version="1.0.0",
    states=("pending", "running", "completed", "expired", "blocked", "missed", "failed", "cancelled"),
    initial_state="pending",
    terminal_states=("completed", "expired", "blocked", "missed", "failed", "cancelled"),
    transitions=(
        TransitionRule(from_state="pending", to_state="pending", action="temporal_action_deferred"),
        TransitionRule(from_state="pending", to_state="running", action="temporal_action_due"),
        TransitionRule(from_state="pending", to_state="expired", action="temporal_action_expired"),
        TransitionRule(from_state="pending", to_state="blocked", action="temporal_action_blocked"),
        TransitionRule(from_state="pending", to_state="missed", action="temporal_action_missed"),
        TransitionRule(from_state="pending", to_state="cancelled", action="temporal_action_cancelled"),
        TransitionRule(from_state="running", to_state="completed", action="temporal_action_completed"),
        TransitionRule(from_state="running", to_state="failed", action="temporal_action_failed"),
        TransitionRule(from_state="running", to_state="cancelled", action="temporal_action_cancelled"),
    ),
)


@dataclass(frozen=True, slots=True)
class GovernanceProof:
    """Proof that a governance decision was made correctly.

    Links a guard chain evaluation to a formal state machine transition,
    producing a cryptographic receipt chain.
    """

    capsule: ProofCapsule
    guard_verdicts: tuple[GuardVerdict, ...]
    decision: str  # "allowed" or "denied"
    tenant_id: str
    endpoint: str
    receipt_hash: str


@dataclass(frozen=True, slots=True)
class TemporalSchedulerProof:
    """Proof that a scheduled temporal action changed state correctly."""

    capsule: ProofCapsule
    scheduler_receipt: TemporalRunReceipt
    decision: str
    tenant_id: str
    schedule_id: str
    receipt_hash: str


class ProofBridge:
    """Bridge between MCOI governance guard evaluations and MAF proof types.

    Converts governance guard chain results into formal transition receipts
    with guard verdicts, maintaining a causal lineage across decisions.
    """

    # Retained for backward compatibility — code that read
    # ``ProofBridge.MAX_LINEAGE_ENTRIES`` continues to see the historical
    # default. New code should configure capacity via the injected
    # `ReceiptStore` (e.g. `InMemoryReceiptStore(max_entries=...)`) so a
    # durable backend can declare its own bound.
    MAX_LINEAGE_ENTRIES = 10_000

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        machine: StateMachineSpec | None = None,
        store: ReceiptStore | None = None,
    ) -> None:
        self._clock = clock
        self._machine = machine or GOVERNANCE_MACHINE
        # Receipt-lineage state lives behind a ReceiptStore Protocol so a
        # durable backend (PostgreSQL, ledger-hashed, ...) can plug in
        # without touching this class. Default preserves the pre-Protocol
        # in-memory behavior with FIFO eviction at MAX_LINEAGE_ENTRIES.
        self._store: ReceiptStore = store if store is not None else InMemoryReceiptStore(
            max_entries=self.MAX_LINEAGE_ENTRIES,
        )
        self._receipt_count: int = 0
        self._last_receipt_hash: str = "genesis"
        self._lock = threading.Lock()

    def certify_governance_decision(
        self,
        *,
        tenant_id: str,
        endpoint: str,
        guard_results: list[dict[str, Any]],
        decision: str,  # "allowed" or "denied"
        actor_id: str = "system",
        reason: str = "",
    ) -> GovernanceProof:
        """Convert a governance guard chain result into a formal proof.

        Args:
            tenant_id: The tenant the decision applies to.
            endpoint: The API endpoint being governed.
            guard_results: List of dicts with {guard_name, allowed, reason}.
            decision: "allowed" or "denied".
            actor_id: Who triggered the request.
            reason: Human-readable reason for the decision.

        Returns:
            GovernanceProof with receipt, verdicts, and lineage.
        """
        with self._lock:
            return self._certify_locked(
                tenant_id=tenant_id, endpoint=endpoint,
                guard_results=guard_results, decision=decision,
                actor_id=actor_id, reason=reason,
            )

    def certify_temporal_run_receipt(
        self,
        *,
        scheduled_action: ScheduledTemporalAction,
        run_receipt: TemporalRunReceipt,
        actor_id: str = "temporal-scheduler",
    ) -> TemporalSchedulerProof:
        """Convert a temporal scheduler receipt into a formal transition proof."""
        if not isinstance(scheduled_action, ScheduledTemporalAction):
            raise ValueError("scheduled_action must be a ScheduledTemporalAction")
        if not isinstance(run_receipt, TemporalRunReceipt):
            raise ValueError("run_receipt must be a TemporalRunReceipt")
        if run_receipt.schedule_id != scheduled_action.schedule_id:
            raise ValueError("run_receipt.schedule_id must match scheduled_action.schedule_id")
        if run_receipt.tenant_id != scheduled_action.tenant_id:
            raise ValueError("run_receipt.tenant_id must match scheduled_action.tenant_id")

        with self._lock:
            return self._certify_temporal_locked(
                scheduled_action=scheduled_action,
                run_receipt=run_receipt,
                actor_id=actor_id,
            )

    def _certify_locked(
        self,
        *,
        tenant_id: str,
        endpoint: str,
        guard_results: list[dict[str, Any]],
        decision: str,
        actor_id: str,
        reason: str,
    ) -> GovernanceProof:
        """Internal: must be called under self._lock."""
        timestamp = self._clock()
        entity_id = f"request:{tenant_id}:{endpoint}"

        # Map guard results to GuardVerdicts
        verdicts = tuple(
            GuardVerdict(
                guard_id=g.get("guard_name", "unknown"),
                passed=g.get("allowed", False),
                reason=g.get("reason", ""),
                detail=g.get("detail", {}),
            )
            for g in guard_results
        )

        # Determine transition
        if decision == "allowed":
            action = "all_guards_passed"
            to_state = "allowed"
        elif decision == "denied":
            action = "guard_rejected"
            to_state = "denied"
        else:
            action = "guard_error"
            to_state = "error"

        # Compute state hashes
        before_hash = self._state_hash("evaluating", entity_id, timestamp)
        after_hash = self._state_hash(to_state, entity_id, timestamp)

        # Build the two-step transition: pending → evaluating → final
        # Step 1: pending → evaluating (always succeeds)
        eval_capsule = certify_transition(
            self._machine,
            entity_id=entity_id,
            from_state="pending",
            to_state="evaluating",
            action="start_evaluation",
            before_state_hash=self._state_hash("pending", entity_id, timestamp),
            after_state_hash=before_hash,
            guards=(),
            actor_id=actor_id,
            reason="evaluating governed request",
            causal_parent=self._last_receipt_hash,
            timestamp=timestamp,
        )

        # Step 2: evaluating → allowed/denied/error
        # Pass the full verdict list (including failed guards). When any
        # guard failed, certify_transition produces a receipt with
        # verdict=DENIED_GUARD_FAILED rather than raising — the receipt
        # IS the proof of the denial, and stripping failed verdicts from
        # it would erase the audit-trail reason for the rejection.
        final_capsule = certify_transition(
            self._machine,
            entity_id=entity_id,
            from_state="evaluating",
            to_state=to_state,
            action=action,
            before_state_hash=before_hash,
            after_state_hash=after_hash,
            guards=verdicts,
            actor_id=actor_id,
            reason=reason or f"governance decision: {decision}",
            causal_parent=eval_capsule.receipt.receipt_hash,
            timestamp=timestamp,
        )

        # Update lineage
        self._receipt_count += 1
        self._last_receipt_hash = final_capsule.receipt.receipt_hash
        self._update_lineage(entity_id, final_capsule.receipt, to_state)

        return GovernanceProof(
            capsule=final_capsule,
            guard_verdicts=verdicts,
            decision=decision,
            tenant_id=tenant_id,
            endpoint=endpoint,
            receipt_hash=final_capsule.receipt.receipt_hash,
        )

    def _certify_temporal_locked(
        self,
        *,
        scheduled_action: ScheduledTemporalAction,
        run_receipt: TemporalRunReceipt,
        actor_id: str,
    ) -> TemporalSchedulerProof:
        """Internal temporal certification path; must be called under self._lock."""
        from_state, to_state, action, guard_passed = self._temporal_transition(run_receipt)
        entity_id = f"temporal_schedule:{run_receipt.tenant_id}:{run_receipt.schedule_id}"
        timestamp = run_receipt.evaluated_at
        guard = GuardVerdict(
            guard_id="temporal_scheduler_receipt",
            passed=guard_passed,
            reason=run_receipt.reason,
            detail={
                "schedule_id": run_receipt.schedule_id,
                "scheduler_receipt_id": run_receipt.receipt_id,
                "scheduler_verdict": run_receipt.verdict.value,
                "worker_id": run_receipt.worker_id,
                "temporal_decision_id": run_receipt.temporal_decision_id,
                "temporal_verdict": run_receipt.temporal_verdict,
                "action_id": scheduled_action.action.action_id,
                "action_type": scheduled_action.action.action_type,
                "execute_at": scheduled_action.execute_at,
                "handler_name": scheduled_action.handler_name,
            },
        )
        before_hash = self._state_hash(from_state, entity_id, timestamp)
        after_hash = self._state_hash(to_state, entity_id, timestamp)
        capsule = certify_transition(
            TEMPORAL_SCHEDULER_MACHINE,
            entity_id=entity_id,
            from_state=from_state,
            to_state=to_state,
            action=action,
            before_state_hash=before_hash,
            after_state_hash=after_hash,
            guards=(guard,),
            actor_id=actor_id,
            reason="temporal scheduler receipt evaluated",
            causal_parent=self._last_receipt_hash,
            timestamp=timestamp,
        )

        self._receipt_count += 1
        self._last_receipt_hash = capsule.receipt.receipt_hash
        self._update_lineage(entity_id, capsule.receipt, to_state)

        return TemporalSchedulerProof(
            capsule=capsule,
            scheduler_receipt=run_receipt,
            decision=to_state,
            tenant_id=run_receipt.tenant_id,
            schedule_id=run_receipt.schedule_id,
            receipt_hash=capsule.receipt.receipt_hash,
        )

    def get_lineage(self, entity_id: str) -> CausalLineage | None:
        """Get the causal lineage for an entity."""
        return self._store.get_lineage(entity_id)

    def verify_receipt(self, receipt: TransitionReceipt) -> bool:
        """Verify a receipt's hash matches its content."""
        content = (
            f"{receipt.entity_id}:{receipt.from_state}:{receipt.to_state}:"
            f"{receipt.action}:{receipt.before_state_hash}:{receipt.after_state_hash}:"
            f"{receipt.causal_parent}"
        )
        expected = hashlib.sha256(content.encode()).hexdigest()
        return expected == receipt.receipt_hash

    @staticmethod
    def verify_replay_token(receipt: TransitionReceipt) -> bool:
        """Verify the receipt's replay_token reconstructs from its content
        and the issued_at timestamp recorded on the receipt itself.

        The replay_token is the deterministic-execution anchor described in
        docs/MAF_RECEIPT_COVERAGE.md as
            "Deterministic token for re-execution validation."
        Construction (matches Rust `maf-kernel::sha256_hex(...)` and
        Python `certify_transition`):
            content      = entity:from:to:action:before:after:causal
            replay_token = "replay-" + sha256(content + ":" + issued_at)[:16]

        A consumer holding a receipt can call this to confirm the token
        was not fabricated and was generated against the timestamp the
        receipt itself records. Returns True iff the reconstructed token
        equals receipt.replay_token. The function is static so it can be
        called without a ProofBridge instance — verification is pure.

        This closes the "replay_token generated but never verified" gap
        from the audit. It does not by itself prove a re-execution
        produced the same outputs; that would require a replay system
        to compare its own derived token against this receipt's token.
        What it DOES prove: the token is consistent with its own
        content fields.
        """
        content = (
            f"{receipt.entity_id}:{receipt.from_state}:{receipt.to_state}:"
            f"{receipt.action}:{receipt.before_state_hash}:{receipt.after_state_hash}:"
            f"{receipt.causal_parent}"
        )
        formatted = f"{content}:{receipt.issued_at}"
        expected = f"replay-{hashlib.sha256(formatted.encode()).hexdigest()[:16]}"
        return expected == receipt.replay_token

    def serialize_proof(self, proof: GovernanceProof) -> dict[str, Any]:
        """Serialize a governance proof to JSON-compatible dict.

        Output format matches MAF Rust serde serialization for cross-language
        interoperability.
        """
        receipt = proof.capsule.receipt
        audit = proof.capsule.audit_record
        return {
            "receipt": {
                "receipt_id": receipt.receipt_id,
                "machine_id": receipt.machine_id,
                "entity_id": receipt.entity_id,
                "from_state": receipt.from_state,
                "to_state": receipt.to_state,
                "action": receipt.action,
                "before_state_hash": receipt.before_state_hash,
                "after_state_hash": receipt.after_state_hash,
                "guard_verdicts": [
                    {"guard_id": v.guard_id, "passed": v.passed, "reason": v.reason}
                    for v in receipt.guard_verdicts
                ],
                "verdict": receipt.verdict.value,
                "replay_token": receipt.replay_token,
                "causal_parent": receipt.causal_parent,
                "issued_at": receipt.issued_at,
                "receipt_hash": receipt.receipt_hash,
            },
            "audit_record": {
                "audit_id": audit.audit_id,
                "machine_id": audit.machine_id,
                "entity_id": audit.entity_id,
                "from_state": audit.from_state,
                "to_state": audit.to_state,
                "action": audit.action,
                "verdict": audit.verdict.value,
                "actor_id": audit.actor_id,
                "reason": audit.reason,
                "transitioned_at": audit.transitioned_at,
                # Mirrors Rust `TransitionAuditRecord.metadata` (HashMap
                # with `#[serde(default)]`). Pre-fix this field was
                # omitted, causing silent cross-language drift: the
                # Python contract carried metadata but the JSON wire
                # format dropped it. Always emitted, possibly as `{}`.
                "metadata": dict(audit.metadata),
            },
            "lineage_depth": proof.capsule.lineage_depth,
            "decision": proof.decision,
            "tenant_id": proof.tenant_id,
            "endpoint": proof.endpoint,
        }

    def serialize_temporal_scheduler_proof(self, proof: TemporalSchedulerProof) -> dict[str, Any]:
        """Serialize a temporal scheduler proof to a JSON-compatible dict."""
        receipt = proof.capsule.receipt
        audit = proof.capsule.audit_record
        return {
            "receipt": {
                "receipt_id": receipt.receipt_id,
                "machine_id": receipt.machine_id,
                "entity_id": receipt.entity_id,
                "from_state": receipt.from_state,
                "to_state": receipt.to_state,
                "action": receipt.action,
                "before_state_hash": receipt.before_state_hash,
                "after_state_hash": receipt.after_state_hash,
                "guard_verdicts": [
                    {
                        "guard_id": v.guard_id,
                        "passed": v.passed,
                        "reason": v.reason,
                        "detail": dict(v.detail),
                    }
                    for v in receipt.guard_verdicts
                ],
                "verdict": receipt.verdict.value,
                "replay_token": receipt.replay_token,
                "causal_parent": receipt.causal_parent,
                "issued_at": receipt.issued_at,
                "receipt_hash": receipt.receipt_hash,
            },
            "audit_record": {
                "audit_id": audit.audit_id,
                "machine_id": audit.machine_id,
                "entity_id": audit.entity_id,
                "from_state": audit.from_state,
                "to_state": audit.to_state,
                "action": audit.action,
                "verdict": audit.verdict.value,
                "actor_id": audit.actor_id,
                "reason": audit.reason,
                "transitioned_at": audit.transitioned_at,
                "metadata": dict(audit.metadata),
            },
            "lineage_depth": proof.capsule.lineage_depth,
            "decision": proof.decision,
            "tenant_id": proof.tenant_id,
            "schedule_id": proof.schedule_id,
            "scheduler_receipt_id": proof.scheduler_receipt.receipt_id,
        }

    @property
    def receipt_count(self) -> int:
        return self._receipt_count

    @property
    def lineage_count(self) -> int:
        return len(self._store)

    def summary(self) -> dict[str, Any]:
        return {
            "receipt_count": self._receipt_count,
            "lineage_count": self.lineage_count,
            "last_receipt_hash": self._last_receipt_hash[:16],
        }

    def _state_hash(self, state: str, entity_id: str, timestamp: str) -> str:
        """Compute a deterministic state hash."""
        content = f"{state}:{entity_id}:{timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def _temporal_transition(receipt: TemporalRunReceipt) -> tuple[str, str, str, bool]:
        """Map a scheduler receipt to a legal temporal scheduler transition."""
        if receipt.verdict is ScheduleDecisionVerdict.DUE:
            return "pending", "running", "temporal_action_due", True
        if receipt.verdict is ScheduleDecisionVerdict.NOT_DUE:
            return "pending", "pending", "temporal_action_deferred", True
        if receipt.verdict is ScheduleDecisionVerdict.COMPLETED:
            return "running", "completed", "temporal_action_completed", True
        if receipt.verdict is ScheduleDecisionVerdict.EXPIRED:
            if receipt.reason == "missed_run":
                return "pending", "missed", "temporal_action_missed", False
            return "pending", "expired", "temporal_action_expired", False
        if receipt.verdict is ScheduleDecisionVerdict.BLOCKED:
            if receipt.reason in {"failed", "missing_handler", "handler_error"}:
                return "running", "failed", "temporal_action_failed", False
            if receipt.reason == "cancelled":
                return "pending", "cancelled", "temporal_action_cancelled", False
            if receipt.reason == "missed_run":
                return "pending", "missed", "temporal_action_missed", False
            return "pending", "blocked", "temporal_action_blocked", False
        raise ValueError("unsupported temporal scheduler verdict")

    def _update_lineage(self, entity_id: str, receipt: TransitionReceipt, current_state: str) -> None:
        """Update causal lineage for an entity. Evicts oldest if at capacity.

        All lineage state goes through `self._store`. For the default
        InMemoryReceiptStore, behavior is identical to the pre-Protocol
        path: FIFO eviction by insertion order at max_entries.
        """
        # Evict oldest lineage if at capacity AND this entity is new.
        if len(self._store) >= self._store.max_entries and not self._store.has_lineage(entity_id):
            self._store.evict_oldest()

        existing = self._store.get_lineage(entity_id)
        if existing:
            new_chain = existing.receipt_chain + (receipt.receipt_id,)
            self._store.record_lineage(entity_id, CausalLineage(
                lineage_id=existing.lineage_id,
                entity_id=entity_id,
                receipt_chain=new_chain,
                root_receipt_id=existing.root_receipt_id,
                current_state=current_state,
                depth=existing.depth + 1,
            ))
        else:
            lineage_id = f"lineage-{hashlib.sha256(entity_id.encode()).hexdigest()[:12]}"
            self._store.record_lineage(entity_id, CausalLineage(
                lineage_id=lineage_id,
                entity_id=entity_id,
                receipt_chain=(receipt.receipt_id,),
                root_receipt_id=receipt.receipt_id,
                current_state=current_state,
                depth=1,
            ))
