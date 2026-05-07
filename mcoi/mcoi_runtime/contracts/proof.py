"""Purpose: proof substrate contracts — Python mirrors of MAF maf-kernel proof types.
Governance scope: transition receipts, guard verdicts, causal lineage, proof capsules.
Dependencies: shared contract base helpers, state_machine contracts.
Invariants:
  - TransitionReceipt is immutable and content-addressed.
  - GuardVerdict records whether a guard passed or failed.
  - CausalLineage links receipts into a provable chain.
  - ProofCapsule bundles receipt + audit record for complete transition proof.
  - All types serialize to JSON matching MAF Rust serde output.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
import hashlib

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)
from .state_machine import TransitionAuditRecord, TransitionVerdict


# ---------------------------------------------------------------------------
# Guard verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class GuardVerdict(ContractRecord):
    """Record of a guard evaluation during transition certification."""

    guard_id: str
    passed: bool
    reason: str
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "guard_id", require_non_empty_text(self.guard_id, "guard_id"))
        if not isinstance(self.passed, bool):
            raise ValueError("passed must be a boolean")
        object.__setattr__(self, "detail", freeze_value(dict(self.detail)))


# ---------------------------------------------------------------------------
# Transition receipt
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TransitionReceipt(ContractRecord):
    """Cryptographic proof of a state transition.

    Captures before/after state hashes, guard verdicts, and a replay token
    for deterministic re-execution. Matches MAF Rust TransitionReceipt.
    """

    receipt_id: str
    machine_id: str
    entity_id: str
    from_state: str
    to_state: str
    action: str
    before_state_hash: str
    after_state_hash: str
    guard_verdicts: tuple[GuardVerdict, ...]
    verdict: TransitionVerdict
    replay_token: str
    causal_parent: str
    issued_at: str
    receipt_hash: str

    def __post_init__(self) -> None:
        for f in ("receipt_id", "machine_id", "entity_id", "from_state",
                   "to_state", "action", "before_state_hash", "after_state_hash"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "guard_verdicts", freeze_value(list(self.guard_verdicts)))
        if not isinstance(self.verdict, TransitionVerdict):
            raise ValueError("verdict must be a TransitionVerdict value")
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
        object.__setattr__(self, "receipt_hash", require_non_empty_text(self.receipt_hash, "receipt_hash"))


# ---------------------------------------------------------------------------
# Causal lineage
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CausalLineage(ContractRecord):
    """Links transitions into a provable chain of receipts."""

    lineage_id: str
    entity_id: str
    receipt_chain: tuple[str, ...]
    root_receipt_id: str
    current_state: str
    depth: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "lineage_id", require_non_empty_text(self.lineage_id, "lineage_id"))
        object.__setattr__(self, "entity_id", require_non_empty_text(self.entity_id, "entity_id"))
        object.__setattr__(self, "receipt_chain", freeze_value(list(self.receipt_chain)))
        object.__setattr__(self, "root_receipt_id", require_non_empty_text(self.root_receipt_id, "root_receipt_id"))
        object.__setattr__(self, "current_state", require_non_empty_text(self.current_state, "current_state"))
        object.__setattr__(self, "depth", require_non_negative_int(self.depth, "depth"))


# ---------------------------------------------------------------------------
# Proof capsule
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProofCapsule(ContractRecord):
    """Complete proof of a transition — receipt + audit record + lineage depth."""

    receipt: TransitionReceipt
    audit_record: TransitionAuditRecord
    lineage_depth: int

    def __post_init__(self) -> None:
        if not isinstance(self.receipt, TransitionReceipt):
            raise ValueError("receipt must be a TransitionReceipt instance")
        if not isinstance(self.audit_record, TransitionAuditRecord):
            raise ValueError("audit_record must be a TransitionAuditRecord instance")
        object.__setattr__(self, "lineage_depth", require_non_negative_int(self.lineage_depth, "lineage_depth"))


# ---------------------------------------------------------------------------
# Certification helper
# ---------------------------------------------------------------------------


def certify_transition(
    spec: Any,  # StateMachineSpec
    *,
    entity_id: str,
    from_state: str,
    to_state: str,
    action: str,
    before_state_hash: str,
    after_state_hash: str,
    guards: tuple[GuardVerdict, ...] = (),
    actor_id: str,
    reason: str,
    causal_parent: str = "genesis",
    timestamp: str,
) -> ProofCapsule:
    """Certify a transition: check legality, evaluate guards, produce receipt.

    Behavior:
      - Illegal transition → raises ValueError("transition denied"). No
        receipt is produced because there is no legal transition to prove.
      - Legal transition with all guards passing → receipt with
        verdict=ALLOWED.
      - Legal transition with one or more failed guards → receipt with
        verdict=DENIED_GUARD_FAILED, including the full guard list (passing
        AND failing) so the receipt is a complete proof of the denial.

    The receipt IS the cryptographic record of the decision — including
    denials. Stripping failed guards from the receipt would erase the
    audit-trail reason for denial. Callers that previously caught the
    "guard failed" ValueError should instead inspect
    capsule.receipt.verdict.

    This is the Python equivalent of MAF's StateMachineSpec.certify_transition().
    """
    # Check legality (always raise for illegal transitions; no receipt
    # to emit when the state machine forbids the edge).
    verdict = spec.is_legal(from_state, to_state, action)
    if verdict != TransitionVerdict.ALLOWED:
        raise ValueError("transition denied")

    # Failed guards downgrade verdict to DENIED_GUARD_FAILED but the
    # receipt is still produced with the full guard list.
    if any(not g.passed for g in guards):
        verdict = TransitionVerdict.DENIED_GUARD_FAILED

    # Build receipt
    content = f"{entity_id}:{from_state}:{to_state}:{action}:{before_state_hash}:{after_state_hash}:{causal_parent}"
    receipt_hash = hashlib.sha256(content.encode()).hexdigest()
    receipt_id = f"rcpt-{receipt_hash[:16]}"
    replay_token = f"replay-{hashlib.sha256(f'{content}:{timestamp}'.encode()).hexdigest()[:16]}"

    receipt = TransitionReceipt(
        receipt_id=receipt_id,
        machine_id=spec.machine_id,
        entity_id=entity_id,
        from_state=from_state,
        to_state=to_state,
        action=action,
        before_state_hash=before_state_hash,
        after_state_hash=after_state_hash,
        guard_verdicts=guards,
        verdict=verdict,
        replay_token=replay_token,
        causal_parent=causal_parent,
        issued_at=timestamp,
        receipt_hash=receipt_hash,
    )

    audit = TransitionAuditRecord(
        audit_id=f"audit-{receipt_hash[:12]}",
        machine_id=spec.machine_id,
        entity_id=entity_id,
        from_state=from_state,
        to_state=to_state,
        action=action,
        verdict=verdict,
        actor_id=actor_id,
        reason=reason,
        transitioned_at=timestamp,
    )

    return ProofCapsule(receipt=receipt, audit_record=audit, lineage_depth=0)
