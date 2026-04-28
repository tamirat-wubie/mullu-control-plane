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
import json
import threading
from dataclasses import dataclass, field
from typing import Any, Callable

from mcoi_runtime.contracts.proof import (
    CausalLineage,
    GuardVerdict,
    ProofCapsule,
    TransitionReceipt,
    certify_transition,
)
from mcoi_runtime.contracts.state_machine import (
    StateMachineSpec,
    TransitionAuditRecord,
    TransitionRule,
    TransitionVerdict,
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


class ProofBridge:
    """Bridge between MCOI governance guard evaluations and MAF proof types.

    Converts governance guard chain results into formal transition receipts
    with guard verdicts, maintaining a causal lineage across decisions.
    """

    MAX_LINEAGE_ENTRIES = 10_000  # Evict oldest lineages beyond this

    def __init__(
        self,
        *,
        clock: Callable[[], str],
        machine: StateMachineSpec | None = None,
    ) -> None:
        self._clock = clock
        self._machine = machine or GOVERNANCE_MACHINE
        self._lineage: dict[str, CausalLineage] = {}  # entity_id -> lineage
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

    def get_lineage(self, entity_id: str) -> CausalLineage | None:
        """Get the causal lineage for an entity."""
        return self._lineage.get(entity_id)

    def verify_receipt(self, receipt: TransitionReceipt) -> bool:
        """Verify a receipt's hash matches its content."""
        content = (
            f"{receipt.entity_id}:{receipt.from_state}:{receipt.to_state}:"
            f"{receipt.action}:{receipt.before_state_hash}:{receipt.after_state_hash}:"
            f"{receipt.causal_parent}"
        )
        expected = hashlib.sha256(content.encode()).hexdigest()
        return expected == receipt.receipt_hash

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

    @property
    def receipt_count(self) -> int:
        return self._receipt_count

    @property
    def lineage_count(self) -> int:
        return len(self._lineage)

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

    def _update_lineage(self, entity_id: str, receipt: TransitionReceipt, current_state: str) -> None:
        """Update causal lineage for an entity. Evicts oldest if at capacity."""
        # Evict oldest lineages if at capacity
        if len(self._lineage) >= self.MAX_LINEAGE_ENTRIES and entity_id not in self._lineage:
            oldest_key = next(iter(self._lineage))
            del self._lineage[oldest_key]

        existing = self._lineage.get(entity_id)
        if existing:
            new_chain = existing.receipt_chain + (receipt.receipt_id,)
            self._lineage[entity_id] = CausalLineage(
                lineage_id=existing.lineage_id,
                entity_id=entity_id,
                receipt_chain=new_chain,
                root_receipt_id=existing.root_receipt_id,
                current_state=current_state,
                depth=existing.depth + 1,
            )
        else:
            lineage_id = f"lineage-{hashlib.sha256(entity_id.encode()).hexdigest()[:12]}"
            self._lineage[entity_id] = CausalLineage(
                lineage_id=lineage_id,
                entity_id=entity_id,
                receipt_chain=(receipt.receipt_id,),
                root_receipt_id=receipt.receipt_id,
                current_state=current_state,
                depth=1,
            )
