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
from .receipt_signing import ReceiptSigner, default_signer
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
    # Authenticity layer (additive, optional). Empty strings == "unsigned",
    # which is the pre-signing default and is byte-identical on the wire.
    # See contracts/receipt_signing.py: the signature is over receipt_hash.
    signature: str = ""
    signing_key_id: str = ""

    def __post_init__(self) -> None:
        for f in ("receipt_id", "machine_id", "entity_id", "from_state",
                   "to_state", "action", "before_state_hash", "after_state_hash"):
            object.__setattr__(self, f, require_non_empty_text(getattr(self, f), f))
        object.__setattr__(self, "guard_verdicts", freeze_value(list(self.guard_verdicts)))
        if not isinstance(self.verdict, TransitionVerdict):
            raise ValueError("verdict must be a TransitionVerdict value")
        object.__setattr__(self, "issued_at", require_datetime_text(self.issued_at, "issued_at"))
        object.__setattr__(self, "receipt_hash", require_non_empty_text(self.receipt_hash, "receipt_hash"))
        if not isinstance(self.signature, str):
            raise ValueError("signature must be a string ('' when unsigned)")
        if not isinstance(self.signing_key_id, str):
            raise ValueError("signing_key_id must be a string ('' when unsigned)")

    @staticmethod
    def _drop_empty_auth(data: dict[str, Any]) -> dict[str, Any]:
        # Authenticity fields are an additive extension. When a receipt is
        # unsigned they are omitted entirely so the serialized form is
        # byte-identical to the pre-signing wire format — preserving
        # cross-language (Rust serde) parity for every receipt Rust
        # currently produces. A *signed* receipt carries them; the Rust
        # mirror declares them `#[serde(default)]`, the same forward-
        # compatibility pattern already used for TransitionAuditRecord.metadata.
        if not data.get("signature"):
            data.pop("signature", None)
            data.pop("signing_key_id", None)
        return data

    # NB: explicit base calls, not super() — @dataclass(slots=True)
    # replaces the class object, which breaks zero-arg super()'s
    # __class__ closure cell.
    def to_dict(self) -> dict[str, Any]:
        return self._drop_empty_auth(ContractRecord.to_dict(self))

    def to_json_dict(self) -> dict[str, Any]:
        return self._drop_empty_auth(ContractRecord.to_json_dict(self))


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
# Canonical transition-content (single source of truth)
# ---------------------------------------------------------------------------


def transition_content(
    *,
    entity_id: str,
    from_state: str,
    to_state: str,
    action: str,
    before_state_hash: str,
    after_state_hash: str,
    causal_parent: str,
) -> str:
    """The exact string a transition receipt is hashed, replay-tokened,
    and signed over. This is the ONLY place the field order/separator is
    defined: receipt_hash, replay_token, the Ed25519 signature, and every
    verifier derive identity from this. Any drift here silently
    invalidates every signature and hash in existence — never inline it.
    Mirrors the Rust `maf-kernel` content layout.
    """
    return (
        f"{entity_id}:{from_state}:{to_state}:{action}:"
        f"{before_state_hash}:{after_state_hash}:{causal_parent}"
    )


def receipt_content(receipt: TransitionReceipt) -> str:
    """`transition_content` for an existing receipt — what every verifier
    recomputes to check a receipt's integrity against its own hash."""
    return transition_content(
        entity_id=receipt.entity_id,
        from_state=receipt.from_state,
        to_state=receipt.to_state,
        action=receipt.action,
        before_state_hash=receipt.before_state_hash,
        after_state_hash=receipt.after_state_hash,
        causal_parent=receipt.causal_parent,
    )


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
    signer: ReceiptSigner | None = None,
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
    content = transition_content(
        entity_id=entity_id,
        from_state=from_state,
        to_state=to_state,
        action=action,
        before_state_hash=before_state_hash,
        after_state_hash=after_state_hash,
        causal_parent=causal_parent,
    )
    receipt_hash = hashlib.sha256(content.encode()).hexdigest()
    receipt_id = f"rcpt-{receipt_hash[:16]}"
    replay_token = f"replay-{hashlib.sha256(f'{content}:{timestamp}'.encode()).hexdigest()[:16]}"

    # Authenticity: sign the content-address. With no key configured the
    # default signer is a no-op and signature/key_id stay "" (unsigned),
    # so existing callers and wire format are unaffected.
    active_signer = signer if signer is not None else default_signer()
    signature, signing_key_id = active_signer.sign(receipt_hash)

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
        signature=signature,
        signing_key_id=signing_key_id,
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
