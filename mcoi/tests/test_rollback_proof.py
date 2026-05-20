"""Tests for provable rollback (gap #2), anchored on signed receipts.

A rollback proof must be (a) append-only — it never rewrites the chain
it reverts past, (b) bound to a real, previously-attested receipt in the
entity's own lineage, (c) independently re-verifiable from primary
artifacts, and (d) authenticatable via the receipt signer when a key is
configured.
"""

from __future__ import annotations

import dataclasses

import pytest

from mcoi_runtime.contracts.receipt_signing import (
    Ed25519ReceiptSigner,
    Ed25519ReceiptVerifier,
    ReceiptSignatureStatus,
    generate_keypair,
    reset_default_signer_cache,
)
from mcoi_runtime.contracts.receipt_store import InMemoryReceiptStore
from mcoi_runtime.core.proof_bridge import ProofBridge

_ENTITY = "request:t1:/api/x"


class _Clock:
    def __init__(self) -> None:
        self.n = 0

    def __call__(self) -> str:
        self.n += 1
        return f"2026-01-01T00:00:{self.n:02d}Z"


@pytest.fixture(autouse=True)
def _clear_signer_cache():
    reset_default_signer_cache()
    yield
    reset_default_signer_cache()


def _bridge_with_history(decisions: int = 2):
    """A bridge whose entity has `decisions` receipts in its lineage."""
    store = InMemoryReceiptStore()
    bridge = ProofBridge(clock=_Clock(), store=store)
    for i in range(decisions):
        bridge.certify_governance_decision(
            tenant_id="t1", endpoint="/api/x",
            guard_results=[{"guard_name": f"g{i}", "allowed": True, "reason": ""}],
            decision="allowed",
        )
    return bridge, store


# ── happy path + independent verification ───────────────────────────────


def test_rollback_happy_path_is_independently_verifiable():
    bridge, store = _bridge_with_history(2)
    lineage = bridge.get_lineage(_ENTITY)
    target_id = lineage.receipt_chain[0]

    proof = bridge.certify_rollback(
        entity_id=_ENTITY, target_receipt_id=target_id, reason="revert bad change"
    )

    assert proof.target_receipt_id == target_id
    assert proof.capsule.receipt.action == "rollback_applied"

    verification = ProofBridge.verify_rollback_proof(
        proof, store=store, lineage=bridge.get_lineage(_ENTITY)
    )
    assert verification.ok, verification.reason
    assert verification.rollback_signature is ReceiptSignatureStatus.UNSIGNED


def test_rollback_is_append_only():
    bridge, store = _bridge_with_history(2)
    before = bridge.get_lineage(_ENTITY).receipt_chain
    target_id = before[0]
    bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)
    after = bridge.get_lineage(_ENTITY).receipt_chain

    # History is extended, never truncated or rewritten.
    assert len(after) == len(before) + 1
    assert after[: len(before)] == before


# ── misuse: nothing legitimate to prove → raise ─────────────────────────


def test_rollback_unknown_entity_raises():
    bridge, _ = _bridge_with_history(1)
    with pytest.raises(ValueError, match="no lineage"):
        bridge.certify_rollback(entity_id="request:t1:/nope", target_receipt_id="x")


def test_rollback_target_not_in_lineage_raises():
    bridge, _ = _bridge_with_history(2)
    with pytest.raises(ValueError, match="not in the entity's lineage"):
        bridge.certify_rollback(
            entity_id=_ENTITY, target_receipt_id="rcpt-fabricated"
        )


def test_rollback_target_unresolvable_raises():
    class _NoReceiptStore(InMemoryReceiptStore):
        def get_receipt(self, receipt_id):  # noqa: D102
            return None

    store = _NoReceiptStore()
    bridge = ProofBridge(clock=_Clock(), store=store)
    bridge.certify_governance_decision(
        tenant_id="t1", endpoint="/api/x",
        guard_results=[{"guard_name": "g", "allowed": True, "reason": ""}],
        decision="allowed",
    )
    target_id = bridge.get_lineage(_ENTITY).receipt_chain[0]
    with pytest.raises(ValueError, match="not resolvable"):
        bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)


# ── tamper / binding detection in the verifier ──────────────────────────


def test_forged_rollback_receipt_hash_fails_verification():
    bridge, store = _bridge_with_history(2)
    target_id = bridge.get_lineage(_ENTITY).receipt_chain[0]
    proof = bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)

    forged_receipt = dataclasses.replace(proof.capsule.receipt, receipt_hash="f" * 64)
    forged_capsule = dataclasses.replace(proof.capsule, receipt=forged_receipt)
    forged = dataclasses.replace(proof, capsule=forged_capsule)

    v = ProofBridge.verify_rollback_proof(
        forged, store=store, lineage=bridge.get_lineage(_ENTITY)
    )
    assert not v.ok
    assert not v.chain_integrity_ok
    assert v.reason == "rollback verification failed"


def test_target_hash_claim_must_match_store():
    bridge, store = _bridge_with_history(2)
    target_id = bridge.get_lineage(_ENTITY).receipt_chain[0]
    proof = bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)

    lied = dataclasses.replace(proof, target_receipt_hash="0" * 64)
    v = ProofBridge.verify_rollback_proof(
        lied, store=store, lineage=bridge.get_lineage(_ENTITY)
    )
    assert not v.ok
    assert not v.target_integrity_ok


def test_wrong_lineage_entity_fails_target_in_lineage():
    bridge, store = _bridge_with_history(2)
    target_id = bridge.get_lineage(_ENTITY).receipt_chain[0]
    proof = bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)

    other = dataclasses.replace(bridge.get_lineage(_ENTITY), entity_id="other")
    v = ProofBridge.verify_rollback_proof(proof, store=store, lineage=other)
    assert not v.ok
    assert not v.target_in_lineage


# ── authenticity (anchors on gap #1) ────────────────────────────────────


def test_signed_rollback_verifies_under_key(monkeypatch):
    seed_hex, pub_hex, key_id = generate_keypair()
    monkeypatch.setenv("MCOI_RECEIPT_SIGNING_KEY", seed_hex)
    reset_default_signer_cache()

    bridge, store = _bridge_with_history(2)
    target_id = bridge.get_lineage(_ENTITY).receipt_chain[0]
    proof = bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)

    assert proof.capsule.receipt.signing_key_id == key_id
    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    v = ProofBridge.verify_rollback_proof(
        proof, store=store, lineage=bridge.get_lineage(_ENTITY),
        signature_verifier=verifier,
    )
    assert v.ok
    assert v.rollback_signature is ReceiptSignatureStatus.SIGNED_VALID
    assert v.target_signature is ReceiptSignatureStatus.SIGNED_VALID


def test_signed_rollback_with_tampered_hash_fails_signature(monkeypatch):
    seed_hex, pub_hex, _ = generate_keypair()
    monkeypatch.setenv("MCOI_RECEIPT_SIGNING_KEY", seed_hex)
    reset_default_signer_cache()

    bridge, store = _bridge_with_history(2)
    target_id = bridge.get_lineage(_ENTITY).receipt_chain[0]
    proof = bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)

    forged_receipt = dataclasses.replace(
        proof.capsule.receipt, receipt_hash="e" * 64
    )
    forged = dataclasses.replace(
        proof, capsule=dataclasses.replace(proof.capsule, receipt=forged_receipt)
    )
    verifier = Ed25519ReceiptVerifier(public_key_hex=pub_hex)
    v = ProofBridge.verify_rollback_proof(
        forged, store=store, lineage=bridge.get_lineage(_ENTITY),
        signature_verifier=verifier,
    )
    assert not v.ok
    assert v.rollback_signature is ReceiptSignatureStatus.SIGNED_INVALID


# ── serialization ───────────────────────────────────────────────────────


def test_serialize_rollback_proof_omits_signature_when_unsigned():
    bridge, _ = _bridge_with_history(2)
    target_id = bridge.get_lineage(_ENTITY).receipt_chain[0]
    proof = bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)

    data = bridge.serialize_rollback_proof(proof)
    assert data["target_receipt_id"] == target_id
    assert data["restored_to_state"] == proof.restored_to_state
    assert "signature" not in data["receipt"]


def test_serialize_rollback_proof_includes_signature_when_signed(monkeypatch):
    seed_hex, _, key_id = generate_keypair()
    monkeypatch.setenv("MCOI_RECEIPT_SIGNING_KEY", seed_hex)
    reset_default_signer_cache()

    bridge, _ = _bridge_with_history(2)
    target_id = bridge.get_lineage(_ENTITY).receipt_chain[0]
    proof = bridge.certify_rollback(entity_id=_ENTITY, target_receipt_id=target_id)

    data = bridge.serialize_rollback_proof(proof)
    assert data["receipt"]["signing_key_id"] == key_id
    assert data["receipt"]["signature"] != ""
