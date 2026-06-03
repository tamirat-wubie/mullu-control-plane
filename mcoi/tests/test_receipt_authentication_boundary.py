"""Pin the transition-receipt authentication boundary.

``receipt_hash`` + the Ed25519 signature bind ONLY the transition identity
(``transition_content``: entity/from/to/action/before/after/causal). The
decision is authenticated as ``to_state``; ``verdict`` and ``guard_verdicts``
are additive metadata outside the content-address and are NOT tamper-evident.

These tests lock that contract:
  - the decision-as-state IS bound (tampering ``to_state`` breaks integrity);
  - ``verdict`` / ``guard_verdicts`` are NOT bound (tampering them leaves the
    hash + signature valid).

If a future change binds verdict/guards into the signed payload (the
Rust-coordinated hardening), the second test must be updated intentionally —
that is the point: the boundary should never move silently.
"""

from __future__ import annotations

import dataclasses
import hashlib

import pytest

from mcoi_runtime.contracts.proof import (
    GuardVerdict,
    TransitionReceipt,
    transition_content,
)
from mcoi_runtime.contracts.receipt_signing import (
    Ed25519ReceiptSigner,
    Ed25519ReceiptVerifier,
)
from mcoi_runtime.contracts.state_machine import TransitionVerdict
from mcoi_runtime.core.proof_bridge import ProofBridge

try:
    import cryptography  # noqa: F401

    CRYPTO_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only without cryptography
    CRYPTO_AVAILABLE = False


def _signed_denied_receipt() -> tuple[TransitionReceipt, Ed25519ReceiptVerifier]:
    entity, frm, to, action = "ent-1", "evaluating", "denied", "guard_rejected"
    before, after, causal = "b" * 64, "a" * 64, "genesis"
    issued_at = "2026-01-01T00:00:00Z"
    content = transition_content(
        entity_id=entity, from_state=frm, to_state=to, action=action,
        before_state_hash=before, after_state_hash=after, causal_parent=causal,
    )
    receipt_hash = hashlib.sha256(content.encode()).hexdigest()
    replay_token = "replay-" + hashlib.sha256(f"{content}:{issued_at}".encode()).hexdigest()[:16]
    signer = Ed25519ReceiptSigner.generate()
    signature, key_id = signer.sign(receipt_hash)
    receipt = TransitionReceipt(
        receipt_id=f"rcpt-{receipt_hash[:16]}", machine_id="m1", entity_id=entity,
        from_state=frm, to_state=to, action=action, before_state_hash=before,
        after_state_hash=after,
        guard_verdicts=(GuardVerdict(guard_id="policy", passed=False, reason="blocked"),),
        verdict=TransitionVerdict.DENIED_GUARD_FAILED, replay_token=replay_token,
        causal_parent=causal, issued_at=issued_at, receipt_hash=receipt_hash,
        signature=signature, signing_key_id=key_id,
    )
    verifier = Ed25519ReceiptVerifier(public_key_hex=signer.public_key_hex)
    return receipt, verifier


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_decision_state_is_authenticated() -> None:
    """The decision (to_state) is inside the content-address — tampering breaks integrity."""
    receipt, verifier = _signed_denied_receipt()
    assert ProofBridge.fully_verify_receipt(receipt, verifier).integrity_ok is True

    flipped = dataclasses.replace(receipt, to_state="allowed")
    verdict = ProofBridge.fully_verify_receipt(flipped, verifier)
    assert verdict.integrity_ok is False
    assert verdict.fully_trusted is False


@pytest.mark.skipif(not CRYPTO_AVAILABLE, reason="cryptography not installed")
def test_verdict_and_guards_are_outside_the_content_address() -> None:
    """verdict + guard_verdicts are additive metadata: tampering them does not
    change receipt_hash/signature. Documents the boundary (and is the tripwire
    for the Rust-coordinated change that would bind them)."""
    receipt, verifier = _signed_denied_receipt()
    tampered = dataclasses.replace(
        receipt, verdict=TransitionVerdict.ALLOWED, guard_verdicts=()
    )

    assert tampered.receipt_hash == receipt.receipt_hash
    assert tampered.signature == receipt.signature
    verdict = ProofBridge.fully_verify_receipt(tampered, verifier)
    assert verdict.integrity_ok is True
    assert verdict.signature_status == "signed_valid"
    # The authenticated decision lives in to_state, which is unchanged + bound.
    assert tampered.to_state == "denied"
